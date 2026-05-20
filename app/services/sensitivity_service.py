"""
Sensitivity Service — orchestrates the design-sensitivity studio.

Subscribes to ``AppStore.design_point_changed`` and recomputes the cheap
(re-)analyses (tornado, margins, snowball) whenever the design moves.
OAT sweeps are on-demand because they're more expensive and the UI
exposes them per-parameter behind a click.

Layer: ``services/`` — imports from ``core/`` and ``state/``, NOT from ``ui/``.
Qt is used only for signal/slot plumbing (QObject).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from app.core.coefficients import get_closest_textbook
from app.core.entities import DesignBrief, RegressionCoeffs
from app.core.sensitivity import (
    MarginsReport,
    OATSweep,
    SizingRunner,
    SnowballReport,
    SweepableParameter,
    TornadoData,
    compute_constraint_margins,
    compute_snowball_factors,
    compute_tornado,
    run_oat_sweep,
    sweepable_parameters_for,
)
from app.state.store import AppStore

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class SensitivitySnapshot:
    """Bundle of analyses for the current design point.

    Held by the service and re-emitted on every design-point change so the
    UI's four widgets can refresh in lock-step.
    """

    tornado_by_output:  dict[str, TornadoData]   # output_id → TornadoData
    margins:            MarginsReport
    snowball:           SnowballReport


class SensitivityService(QObject):
    """Reactive analysis layer for the Design Sensitivity Studio.

    Signals
    -------
    sensitivity_updated()
        Emitted after a new SensitivitySnapshot is computed. The UI reads
        ``service.snapshot`` to pick up the latest data.
    sweep_completed(OATSweep)
        Emitted when an OAT sweep requested via ``run_sweep`` finishes.
        Carries the OATSweep payload directly.
    """

    sensitivity_updated = pyqtSignal()
    sweep_completed     = pyqtSignal(object)   # OATSweep

    # Output IDs the service eagerly tornadoes on every design change.
    # Keeping this to the Tier-1 set ("MTOW", "Wing Area", "Engine Power")
    # keeps re-computation under ~50 ms (each tornado = ~30 sizing runs).
    _EAGER_TORNADO_OUTPUTS: tuple[str, ...] = (
        "mtow_kg", "wing_area_m2", "engine_power_w",
    )

    def __init__(self, store: AppStore, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._store = store
        self._runner = SizingRunner(
            tolerance=store.settings.convergence_tolerance,
            max_iterations=store.settings.max_iterations,
        )
        self._snapshot: Optional[SensitivitySnapshot] = None

    # ── Public ────────────────────────────────────────────────────────────

    def initialise(self) -> None:
        """Connect signals; call once after the store is ready."""
        self._store.design_point_changed.connect(self._on_design_point_changed)

    @property
    def snapshot(self) -> Optional[SensitivitySnapshot]:
        """The most recently computed snapshot, or None if no design yet."""
        return self._snapshot

    def refresh(self) -> bool:
        """Force-recompute the snapshot from the current design.

        Returns True on success, False if the store isn't ready (e.g. no
        design point yet).
        """
        return self._compute_snapshot()

    def run_sweep(
        self,
        parameter: SweepableParameter,
        *,
        n_points: int = 21,
        delta_pct: float = 20.0,
    ) -> Optional[OATSweep]:
        """Run an OAT sweep for one parameter.

        Returns the OATSweep payload synchronously and also emits the
        ``sweep_completed`` signal (kept for parity with future async
        implementations). Returns None if the store has no design yet.
        """
        coeffs = self._current_coeffs()
        if coeffs is None:
            return None
        brief = self._store.state.sizing.brief
        sweep = run_oat_sweep(
            brief, coeffs, parameter,
            runner=self._runner, n_points=n_points, delta_pct=delta_pct,
        )
        self.sweep_completed.emit(sweep)
        return sweep

    def sweepable_parameters(self) -> list[SweepableParameter]:
        """Return the parameters relevant to the current propulsion type."""
        return sweepable_parameters_for(self._store.state.sizing.brief.propulsion_type)

    # ── Internal ──────────────────────────────────────────────────────────

    def _on_design_point_changed(self) -> None:
        self._compute_snapshot()

    def _compute_snapshot(self) -> bool:
        s = self._store.state.sizing
        if s.design_point is None or s.constraint_result is None:
            return False

        coeffs = self._current_coeffs()
        if coeffs is None:
            return False

        try:
            brief = s.brief
            params = sweepable_parameters_for(brief.propulsion_type)

            tornado_by_output = {
                output_id: compute_tornado(
                    brief, coeffs, params, output_id, runner=self._runner,
                )
                for output_id in self._EAGER_TORNADO_OUTPUTS
            }
            margins  = compute_constraint_margins(s.design_point, s.constraint_result)
            snowball = compute_snowball_factors(brief, coeffs, runner=self._runner)

            self._snapshot = SensitivitySnapshot(
                tornado_by_output=tornado_by_output,
                margins=margins,
                snowball=snowball,
            )
            self.sensitivity_updated.emit()
            return True
        except Exception as exc:  # noqa: BLE001
            _LOG.error("Sensitivity refresh failed: %s", exc, exc_info=True)
            return False

    def _current_coeffs(self) -> Optional[RegressionCoeffs]:
        """Resolve the active regression coefficients (same logic as SizingService)."""
        brief = self._store.state.sizing.brief
        coeffs = (
            self._store.state.historical_data
            .regression_coefficients
            .get(brief.classification_name)
        )
        if coeffs is None:
            hd = self._store.state.historical_data
            cr = hd.find_range_for_mtow(brief.payload_mass_kg * 5)
            mid = (cr.min_mtow_kg + cr.max_mtow_kg) / 2 if cr else None
            coeffs = get_closest_textbook(brief.classification_name, mid)
        return coeffs
