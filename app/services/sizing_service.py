"""
Sizing Service — UAV-CD-APP
=============================
Application-layer facade connecting the AppStore to the Phase-1 computation
engines (WeightBuildup, ConstraintAnalyzer, DesignPointFinder).

Responsibilities:
  - Subscribe to signals: brief_changed, regression_updated.
  - When triggered: run the full sizing pipeline (if auto_recalculate=True).
  - Post results back to AppStore via typed setters.
  - Expose a public ``run_now()`` for the Manual Run button.

Design:
  - No UI imports — purely orchestration.
  - Catches any computation error and logs it without crashing the app.
  - Creates SizingRun snapshots and appends them to run_history.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from PyQt6.QtCore import QObject

from app.core.constraints import ConstraintAnalyzer
from app.core.design_point import DesignPointFinder
from app.core.entities import (
    DesignBrief,
    RegressionCoeffs,
    SizingRun,
    WeightResult,
)
from app.core.weight_buildup import WeightBuildupEngine
from app.state.store import AppStore

_LOG = logging.getLogger(__name__)


class SizingService(QObject):
    """
    Orchestrates the sizing pipeline.

    Usage::

        svc = SizingService(store)
        svc.initialise()    # Wire up signal connections
        svc.run_now()       # Run once manually
    """

    def __init__(self, store: AppStore, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._store: AppStore = store
        self._weight_engine: WeightBuildupEngine = WeightBuildupEngine(
            tolerance=store.settings.convergence_tolerance,
            max_iterations=store.settings.max_iterations,
        )
        self._dp_finder: DesignPointFinder = DesignPointFinder()

    def initialise(self) -> None:
        """Connect to AppStore signals. Call once after store is created."""
        self._store.brief_changed.connect(self._on_brief_changed)
        self._store.regression_updated.connect(self._on_regression_updated)
        self._store.settings_changed.connect(self._on_settings_changed)

    # ── Signal handlers ──────────────────────────────────────────────────

    def _on_brief_changed(self) -> None:
        if self._store.settings.auto_recalculate:
            self._run_pipeline()

    def _on_regression_updated(self) -> None:
        if self._store.settings.auto_recalculate:
            self._run_pipeline()

    def _on_settings_changed(self) -> None:
        """Update engine parameters when solver settings change."""
        s = self._store.settings
        self._weight_engine = WeightBuildupEngine(
            tolerance=s.convergence_tolerance,
            max_iterations=s.max_iterations,
        )

    # ── Public ───────────────────────────────────────────────────────────

    def run_now(self, save_to_history: bool = True) -> bool:
        """
        Execute the full sizing pipeline immediately.
        Returns True on success.
        """
        return self._run_pipeline(save_to_history=save_to_history)

    # ── Pipeline ─────────────────────────────────────────────────────────

    def _run_pipeline(self, save_to_history: bool = False) -> bool:
        """
        Full Phase-1 pipeline:
          1. Resolve regression coefficients for the brief's class.
          2. Converge W_TO.
          3. Compute constraint curves.
          4. Find design point.
          5. Post results to store.
        """
        brief: DesignBrief = self._store.state.sizing.brief

        # 1 — Get regression coefficients
        coeffs: Optional[RegressionCoeffs] = (
            self._store.state.historical_data
            .regression_coefficients
            .get(brief.classification_name)
        )
        if coeffs is None:
            _LOG.warning(
                "No regression coefficients for class '%s'. "
                "Falling back to textbook defaults.",
                brief.classification_name,
            )
            from app.core.coefficients import get_closest_textbook
            hd = self._store.state.historical_data
            cr = hd.find_range_for_mtow(brief.payload_mass_kg * 5)
            mid = (cr.min_mtow_kg + cr.max_mtow_kg) / 2 if cr else None
            coeffs = get_closest_textbook(brief.classification_name, mid)

        try:
            # 2 — Weight buildup
            weight_result: WeightResult = self._weight_engine.solve(
                brief, coeffs
            )
            self._store.update_weight_result(weight_result)

            # 3 — Constraint analysis
            analyzer = ConstraintAnalyzer(brief, weight_result)
            constraint_result = analyzer.analyze()
            violations = list(constraint_result.violations)
            self._store.update_constraint_result(constraint_result, violations)

            # 4 — Design point
            design_point = self._dp_finder.find(
                brief, weight_result, constraint_result, coeffs
            )
            self._store.update_design_point(design_point)

            # 5 — Optionally save run to history
            if save_to_history:
                run = SizingRun(
                    label=self._make_run_label(brief),
                    timestamp_iso=datetime.now(timezone.utc).isoformat(),
                    brief=brief,
                    weight_result=weight_result,
                    design_point=design_point,
                )
                self._store.append_sizing_run(run)

            return True

        except Exception as exc:  # noqa: BLE001
            _LOG.error("Sizing pipeline failed: %s", exc, exc_info=True)
            return False

    @staticmethod
    def _make_run_label(brief: DesignBrief) -> str:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        return (
            f"{brief.propulsion_type.label} — "
            f"{brief.classification_name} — "
            f"{brief.payload_mass_kg:.1f} kg payload  [{ts}]"
        )
