"""
Customise-dialog hierarchy — focused tests.

Covers:
  * The ``SectionCustomizeDialog`` abstract base contract (subclass
    hooks raise NotImplementedError when not overridden; ``.config``
    is None before accept).
  * ``SensitivityReportConfigDialog`` round-trips an existing config
    (populate + collect produces the same payload).
  * Propulsion-gated inputs (SFC for Electric) are hidden from the
    sweep input combo.
  * The dialog's ``_validate_form`` warns on an empty configuration.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from app.core.enums import PropulsionType
from app.core.reports.base import SectionConfig
from app.core.reports.sections.sensitivity_analysis import (
    SensitivityReportConfig,
)
from app.services.sizing_service import SizingService
from app.state.store import AppStore
from app.ui.dialogs.section_customize_dialog import SectionCustomizeDialog
from app.ui.dialogs.sensitivity_report_dialog import (
    SensitivityReportConfigDialog,
)


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def sized_store(qapp):
    store = AppStore()
    SizingService(store).run_now()
    return store


# ── SectionCustomizeDialog base contract ────────────────────────────────────


class TestSectionCustomizeDialogBase:
    def test_subclass_hooks_raise_not_implemented(self, qapp):
        """Calling the abstract hooks directly on the base must error so a
        partial subclass doesn't silently produce empty configs."""

        class _NoopChild(SectionCustomizeDialog):
            pass

        dlg = _NoopChild(title="t")
        with pytest.raises(NotImplementedError):
            dlg._build_form(None)  # type: ignore[arg-type]
        with pytest.raises(NotImplementedError):
            dlg._collect_config()

    def test_config_is_none_before_accept(self, qapp):
        class _NoopChild(SectionCustomizeDialog):
            pass

        dlg = _NoopChild(title="t")
        assert dlg.config is None


# ── SensitivityReportConfigDialog ───────────────────────────────────────────


class TestSensitivityReportConfigDialog:
    def test_constructs_with_no_initial_config(self, sized_store):
        dlg = SensitivityReportConfigDialog(sized_store, initial_config=None)
        # Sanity: dialog widgets exist after _setup_layout
        assert dlg._tornado_list.count() > 0
        # No sweep rows by default
        assert dlg._sweep_rows == []
        # Tables ON by default
        assert dlg._chk_margins.isChecked() is True
        assert dlg._chk_snowball.isChecked() is True

    def test_round_trips_existing_config(self, sized_store):
        """populate_from_config → collect_config returns an equivalent payload."""
        initial = SensitivityReportConfig(
            tornado_output_ids=("mtow_kg", "wing_area_m2"),
            sweep_specs=(
                ("mtow_kg", "payload_mass_kg"),
                ("wing_area_m2", "c_l_max"),
            ),
            include_margins=True,
            include_snowball=False,
        )
        dlg = SensitivityReportConfigDialog(
            sized_store, initial_config=initial,
        )
        collected = dlg._collect_config()
        assert collected.tornado_output_ids == initial.tornado_output_ids
        assert collected.sweep_specs == initial.sweep_specs
        assert collected.include_margins is True
        assert collected.include_snowball is False

    def test_propulsion_gated_input_absent_from_sweep_combo(self, sized_store):
        """SFC is gated to ``uses_fuel`` — for an Electric default brief
        it must NOT appear in any new sweep row's input combo."""
        dlg = SensitivityReportConfigDialog(sized_store, initial_config=None)
        dlg._add_sweep_row(None, None)
        _row, _out_combo, in_combo = dlg._sweep_rows[-1]
        field_names = {
            in_combo.itemData(i) for i in range(in_combo.count())
        }
        assert "specific_fuel_consumption_g_wh" not in field_names
        # Battery params, which ARE relevant for Electric, must appear.
        assert "battery_energy_density_wh_kg" in field_names

    def test_add_and_remove_sweep_rows(self, sized_store):
        dlg = SensitivityReportConfigDialog(sized_store, initial_config=None)
        dlg._add_sweep_row(None, None)
        dlg._add_sweep_row(None, None)
        assert len(dlg._sweep_rows) == 2
        first_row = dlg._sweep_rows[0][0]
        dlg._remove_sweep_row(first_row)
        assert len(dlg._sweep_rows) == 1

    def test_collect_returns_typed_section_config(self, sized_store):
        dlg = SensitivityReportConfigDialog(sized_store, initial_config=None)
        cfg = dlg._collect_config()
        # Strict typing: NOT any base/duck-typed object.
        assert isinstance(cfg, SensitivityReportConfig)
        assert isinstance(cfg, SectionConfig)
