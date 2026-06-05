"""
SensitivityService + UI-tab smoke tests.

The pure-Python core is exhaustively tested in ``test_sensitivity.py``.
This file covers the Qt-aware wiring:

  * SensitivityService produces a snapshot after design_point_changed.
  * Snapshot contains the Tier-1 tornados, all margins, and the snowball
    factors.
  * run_sweep returns an OATSweep and emits sweep_completed.
  * SensitivityTab constructs and wires to the service without errors.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PyQt6.QtWidgets import QApplication

from app.services.sensitivity_service import SensitivityService, SensitivitySnapshot
from app.services.sizing_service import SizingService
from app.state.store import AppStore


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def store(qapp):
    return AppStore()


@pytest.fixture
def sized_store(store):
    SizingService(store).run_now()
    return store


# ── Service ────────────────────────────────────────────────────────────────


class TestSensitivityService:
    def test_initial_snapshot_is_none(self, store):
        svc = SensitivityService(store)
        assert svc.snapshot is None

    def test_refresh_populates_snapshot_after_sizing(self, sized_store):
        svc = SensitivityService(sized_store)
        ok = svc.refresh()
        assert ok is True
        snap = svc.snapshot
        assert isinstance(snap, SensitivitySnapshot)
        # Tier-1 outputs
        assert set(snap.tornado_by_output.keys()) == {
            "mtow_kg", "wing_area_m2", "engine_power_w",
        }
        # 5 constraint margins (Stall + 4 curves)
        assert len(snap.margins.margins) == 5
        # 9 default snowball pairs for Electric default brief (Battery + SFC
        # gating may drop some; assert ≥ 7 to allow for variance)
        assert len(snap.snowball.factors) >= 7

    def test_initialise_reacts_to_design_point_changed(self, sized_store):
        """After initialise() the service should refresh automatically when
        the store's design_point_changed signal fires (which happens during
        SizingService.run_now)."""
        svc = SensitivityService(sized_store)
        svc.initialise()
        # Re-run sizing to fire design_point_changed again
        SizingService(sized_store).run_now()
        assert svc.snapshot is not None

    def test_sweepable_parameters_filtered_by_propulsion(self, sized_store):
        svc = SensitivityService(sized_store)
        # Default brief is ELECTRIC — SFC should not appear
        params = svc.sweepable_parameters()
        names = {p.field_name for p in params}
        assert "specific_fuel_consumption_g_wh" not in names
        assert "battery_energy_density_wh_kg" in names

    def test_run_sweep_returns_oat_sweep(self, sized_store):
        svc = SensitivityService(sized_store)
        svc.refresh()
        params = svc.sweepable_parameters()
        payload = next(p for p in params if p.field_name == "payload_mass_kg")
        sweep = svc.run_sweep(payload, n_points=11)
        assert sweep is not None
        assert len(sweep.points) == 11
        assert sweep.parameter is payload

    def test_run_sweep_emits_sweep_completed_signal(self, sized_store, qapp):
        svc = SensitivityService(sized_store)
        svc.refresh()
        params = svc.sweepable_parameters()
        payload = next(p for p in params if p.field_name == "payload_mass_kg")
        received: list = []
        svc.sweep_completed.connect(lambda s: received.append(s))
        svc.run_sweep(payload, n_points=5)
        # Process Qt event loop briefly so the signal is delivered
        qapp.processEvents()
        assert len(received) == 1

    def test_run_sweep_falls_back_to_settings_n_points(self, sized_store):
        """When ``n_points`` is omitted, the service must use
        ``settings.sens_n_points`` (not the old hard-coded 21)."""
        import dataclasses
        sized_store.update_settings(dataclasses.replace(
            sized_store.settings, sens_n_points=15,
        ))
        svc = SensitivityService(sized_store)
        params = svc.sweepable_parameters()
        payload = next(p for p in params if p.field_name == "payload_mass_kg")
        sweep = svc.run_sweep(payload)   # no kwargs
        assert sweep is not None
        assert len(sweep.points) == 15

    def test_settings_change_triggers_snapshot_recompute(self, sized_store, qapp):
        """When the user changes Δ% in settings, ``sensitivity_updated``
        must fire so the tab repaints the tornados at the new perturbation."""
        import dataclasses
        svc = SensitivityService(sized_store)
        svc.initialise()
        svc.refresh()
        fired: list[int] = []
        svc.sensitivity_updated.connect(lambda: fired.append(1))
        # Change sens_delta_pct from 20 → 35
        sized_store.update_settings(dataclasses.replace(
            sized_store.settings, sens_delta_pct=35.0,
        ))
        qapp.processEvents()
        assert len(fired) >= 1, "sensitivity_updated did not fire on settings_changed"

    def test_custom_tornado_output_ids_in_snapshot(self, sized_store):
        """``sens_tornado_output_ids`` swaps which outputs the snapshot eagerly tornados."""
        import dataclasses
        sized_store.update_settings(dataclasses.replace(
            sized_store.settings,
            sens_tornado_output_ids=("mtow_kg", "wingspan_m", "ld_max"),
        ))
        svc = SensitivityService(sized_store)
        svc.refresh()
        assert set(svc.snapshot.tornado_by_output.keys()) == {
            "mtow_kg", "wingspan_m", "ld_max",
        }


class TestSettingsRoundtrip:
    """``UserSettings`` JSON roundtrip preserves the sensitivity fields."""

    def test_sensitivity_fields_survive_json_roundtrip(self, tmp_path):
        from app.state.settings import SettingsManager, UserSettings
        import dataclasses
        mgr = SettingsManager(path=str(tmp_path / "settings.json"))
        custom = dataclasses.replace(
            UserSettings(),
            sens_delta_pct=27.5,
            sens_n_points=33,
            sens_severity_critical_pct=15.0,
            sens_severity_tight_pct=45.0,
            sens_tornado_output_ids=("mtow_kg", "wingspan_m", "ld_max"),
        )
        assert mgr.save(custom)
        restored = mgr.load()
        assert restored.sens_delta_pct == 27.5
        assert restored.sens_n_points == 33
        assert restored.sens_severity_critical_pct == 15.0
        assert restored.sens_severity_tight_pct == 45.0
        assert restored.sens_tornado_output_ids == (
            "mtow_kg", "wingspan_m", "ld_max",
        )

    def test_corrupt_severity_thresholds_revert_to_defaults(self, tmp_path):
        """If critical >= tight in settings.json, both revert to safe defaults."""
        from app.state.settings import SettingsManager
        import json
        path = tmp_path / "settings.json"
        json.dump({
            "sens_severity_critical_pct": 80.0,
            "sens_severity_tight_pct":    50.0,  # inverted!
        }, path.open("w"))
        restored = SettingsManager(path=str(path)).load()
        assert restored.sens_severity_critical_pct == 10.0
        assert restored.sens_severity_tight_pct    == 30.0


# ── Tab construction ───────────────────────────────────────────────────────


class TestSensitivityTab:
    def test_tab_constructs_and_renders_snapshot(self, sized_store):
        from app.ui.tabs.sizing.sensitivity_tab import SensitivityTab
        svc = SensitivityService(sized_store)
        svc.refresh()
        tab = SensitivityTab(sized_store, svc)
        # Trigger the slot manually to verify wiring
        tab._on_snapshot_updated()
        # 3 tornado slots, each a (combo, widget) pair
        assert len(tab._tornado_slots) == 3
        for _combo, widget in tab._tornado_slots:
            assert widget._current_data is not None

    def test_tab_handles_no_snapshot_gracefully(self, store):
        from app.ui.tabs.sizing.sensitivity_tab import SensitivityTab
        svc = SensitivityService(store)
        # No refresh — service.snapshot is None
        tab = SensitivityTab(store, svc)
        # _on_snapshot_updated should NOT crash with no snapshot
        tab._on_snapshot_updated()  # returns early — no widgets updated
