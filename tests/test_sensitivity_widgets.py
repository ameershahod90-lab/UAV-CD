"""
Sensitivity widget — headless smoke tests.

Validates that the four sensitivity widgets honour the mandatory rules
in `.agents/ui_ux.md`:

  * Every value-displaying widget consumes ``DisplayConverter`` and
    labels with the unit string the converter returns.
  * Every propulsion-sensitive label resolves through ``PropulsionType``
    via the propulsion-aware helpers in
    ``app/core/sensitivity/labels.py`` — never hardcoded.

These tests construct the widgets directly (no full SensitivityTab) and
call their public render methods with controlled converters /
propulsion types so we can assert the resulting axis labels, table
strings, and titles.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import dataclasses

import pytest

from PyQt6.QtWidgets import QApplication

from app.core.coefficients import get_closest_textbook
from app.core.display_converter import DisplayConverter
from app.core.enums import (
    AreaUnit,
    ForceUnit,
    MassUnit,
    PowerUnit,
    PropulsionType,
)
from app.core.sensitivity import (
    SWEEPABLE_PARAMETERS,
    compute_constraint_margins,
    compute_snowball_factors,
    compute_tornado,
    run_oat_sweep,
    sweepable_parameters_for,
)
from app.services.sizing_service import SizingService
from app.state.settings import UserSettings
from app.state.store import AppStore
from app.ui.widgets.margins_widget import MarginsWidget
from app.ui.widgets.snowball_widget import SnowballWidget
from app.ui.widgets.sweep_widget import SweepWidget
from app.ui.widgets.tornado_widget import TornadoWidget


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def sized_store(qapp):
    store = AppStore()
    SizingService(store).run_now()
    return store


@pytest.fixture
def coeffs(sized_store):
    brief = sized_store.state.sizing.brief
    return (
        sized_store.state.historical_data.regression_coefficients.get(
            brief.classification_name
        )
        or get_closest_textbook(brief.classification_name, brief.payload_mass_kg * 5)
    )


def _dc_with_lb_ft2_hp() -> DisplayConverter:
    """Build a converter with mass=lb, area=ft², power=hp, force=lbf."""
    settings = dataclasses.replace(
        UserSettings(),
        mass_unit=MassUnit.LB,
        area_unit=AreaUnit.FT2,
        power_unit=PowerUnit.HP,
        force_unit=ForceUnit.LBF,
    )
    return DisplayConverter(settings)


# ── TornadoWidget ───────────────────────────────────────────────────────────


class TestTornadoWidget:
    def test_axis_label_uses_dc_unit_string(self, qapp, sized_store, coeffs):
        """Axis label must reflect the unit DC returns, never hardcoded."""
        brief = sized_store.state.sizing.brief
        params = sweepable_parameters_for(brief)
        td = compute_tornado(brief, coeffs, params, "mtow_kg")

        # Default DC (SI) → kg
        w = TornadoWidget()
        dc_si = DisplayConverter(UserSettings())
        w.set_data(td, converter=dc_si, propulsion_type=PropulsionType.ELECTRIC)
        axis_text = w._plot.getAxis("bottom").labelString()
        assert "kg" in axis_text, f"Expected kg in axis label, got: {axis_text!r}"

        # Imperial DC → lb
        w2 = TornadoWidget()
        w2.set_data(
            td, converter=_dc_with_lb_ft2_hp(),
            propulsion_type=PropulsionType.ELECTRIC,
        )
        axis_text2 = w2._plot.getAxis("bottom").labelString()
        assert "lb" in axis_text2, f"Expected lb in axis label, got: {axis_text2!r}"
        assert "kg" not in axis_text2, (
            f"SI unit leaked into Imperial axis: {axis_text2!r}"
        )

    def test_engine_power_axis_flips_with_propulsion(
        self, qapp, sized_store, coeffs,
    ):
        """Engine-power tornado axis label must flip Power→Thrust for Turbojet."""
        brief = sized_store.state.sizing.brief
        params = sweepable_parameters_for(brief)
        td = compute_tornado(brief, coeffs, params, "engine_power_w")
        dc = DisplayConverter(UserSettings())

        prop_widget = TornadoWidget()
        prop_widget.set_data(
            td, converter=dc, propulsion_type=PropulsionType.PISTON,
        )
        assert "Power" in prop_widget._plot.getAxis("bottom").labelString()

        jet_widget = TornadoWidget()
        jet_widget.set_data(
            td, converter=dc, propulsion_type=PropulsionType.TURBOJET,
        )
        jet_label = jet_widget._plot.getAxis("bottom").labelString()
        assert "Thrust" in jet_label, (
            f"Expected 'Thrust' for Turbojet engine_power_w axis, got: {jet_label!r}"
        )


# ── SnowballWidget ──────────────────────────────────────────────────────────


class TestSnowballWidget:
    def test_interpretation_uses_display_units(self, qapp, sized_store, coeffs):
        """The 'Each +1 {unit} of {input} → {value} {unit} in {output}' sentence
        must use the converter's unit strings on both sides."""
        brief = sized_store.state.sizing.brief
        snowball = compute_snowball_factors(brief, coeffs)

        w = SnowballWidget()
        w.set_factors(
            snowball,
            converter=_dc_with_lb_ft2_hp(),
            propulsion_type=brief.propulsion_type,
        )
        # Find the ∂MTOW/∂Payload Mass row — both kg→lb on both sides
        for row in range(w._table.rowCount()):
            sym = w._table.item(row, 0).text()
            if "MTOW" in sym and "Payload Mass" in sym:
                interp = w._table.item(row, 2).text()
                # Both numerator and denominator carry "lb" — never "kg"
                assert "lb" in interp, (
                    f"Display unit lb not found in interpretation: {interp!r}"
                )
                assert "kg" not in interp, (
                    f"SI unit kg leaked through to display: {interp!r}"
                )
                return
        pytest.skip("∂MTOW/∂Payload pair not present for this propulsion")

    def test_value_column_uses_display_units(self, qapp, sized_store, coeffs):
        """The ratio column must format as '{value} {out_unit}/{in_unit}'."""
        brief = sized_store.state.sizing.brief
        snowball = compute_snowball_factors(brief, coeffs)

        w = SnowballWidget()
        w.set_factors(
            snowball,
            converter=_dc_with_lb_ft2_hp(),
            propulsion_type=brief.propulsion_type,
        )
        for row in range(w._table.rowCount()):
            sym = w._table.item(row, 0).text()
            val = w._table.item(row, 1).text()
            if "MTOW" in sym and "Payload Mass" in sym and val != "—":
                assert "lb/lb" in val, (
                    f"Expected 'lb/lb' in mass/mass derivative, got: {val!r}"
                )
                return
        pytest.skip("∂MTOW/∂Payload value not present for this propulsion")


# ── SweepWidget ─────────────────────────────────────────────────────────────


class TestSweepWidget:
    def test_panel_count_matches_output_ids_length(self, qapp, sized_store, coeffs):
        """N selected outputs → N small-multiples panels (not 1 overlay)."""
        brief = sized_store.state.sizing.brief
        params = sweepable_parameters_for(brief)
        payload = next(p for p in params if p.field_name == "payload_mass_kg")
        sweep = run_oat_sweep(brief, coeffs, payload, n_points=11)
        dc = DisplayConverter(UserSettings())

        w = SweepWidget()
        w.set_sweep(
            sweep, ["mtow_kg", "wing_area_m2", "engine_power_w"],
            converter=dc, propulsion_type=brief.propulsion_type,
        )
        # The panels host should now carry 3 child plot widgets.
        assert w._panels_layout.count() == 3, (
            f"Expected 3 small multiples, got {w._panels_layout.count()}"
        )

        # Changing the output set re-renders the panel count.
        w.set_sweep(
            sweep, ["mtow_kg"],
            converter=dc, propulsion_type=brief.propulsion_type,
        )
        assert w._panels_layout.count() == 1

    def test_clear_returns_to_empty_state_placeholder(self, qapp):
        """clear() must replace the panels with the empty-state placeholder."""
        w = SweepWidget()
        # Construction already shows the placeholder
        assert w._panels_layout.count() == 1
        w.clear()
        # Still 1 child after clear — the placeholder label.
        assert w._panels_layout.count() == 1


# ── MarginsWidget ───────────────────────────────────────────────────────────


class TestMarginsWidget:
    def test_severity_thresholds_drive_bar_count(self, qapp, sized_store):
        """Loosening thresholds must move at least one bar from red→green."""
        s = sized_store.state.sizing
        # Strict — every margin <50% is critical
        strict = compute_constraint_margins(
            s.design_point, s.constraint_result,
            critical_pct=50.0, tight_pct=60.0,
        )
        strict_crit = sum(1 for m in strict.margins if m.severity == "critical")
        # Loose — every margin >=5% is ok
        loose = compute_constraint_margins(
            s.design_point, s.constraint_result,
            critical_pct=1.0, tight_pct=5.0,
        )
        loose_ok = sum(1 for m in loose.margins if m.severity == "ok")
        # At least one margin moved from "critical" → "ok"
        assert strict_crit > 0
        assert loose_ok > 0
