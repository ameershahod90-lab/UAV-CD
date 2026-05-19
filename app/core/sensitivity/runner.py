"""
SizingRunner — pure-Python sizing pipeline (no AppStore dependency).

The live UI's ``SizingService`` is a Qt orchestrator: it reads the brief
from AppStore, runs the engines, and writes results back. For sensitivity
work we need to run the same pipeline thousands of times on perturbed
briefs without touching AppStore.

SizingRunner wraps the same three engines (WeightBuildupEngine,
ConstraintAnalyzer, DesignPointFinder) that the live UI uses, so a
sensitivity run produces results identical to what the user would see in
the sizing tabs for that brief. It returns a ``SizingOutcome`` carrying
WeightResult + ConstraintResult + DesignPoint together.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.core.constraints import ConstraintAnalyzer
from app.core.design_point import DesignPointFinder
from app.core.entities import DesignBrief, RegressionCoeffs
from app.core.sensitivity.outcome import SizingOutcome
from app.core.weight_buildup import WeightBuildupEngine

_LOG = logging.getLogger(__name__)


class SizingRunner:
    """Stateless wrapper that runs the Phase-1 sizing pipeline.

    Construction is cheap (just instantiates the underlying engines). The
    runner is intentionally NOT a singleton — sensitivity sweeps often want
    multiple parallel runners.
    """

    def __init__(
        self,
        *,
        tolerance: float = 0.0001,
        max_iterations: int = 100,
    ) -> None:
        self._weight_engine = WeightBuildupEngine(
            tolerance=tolerance, max_iterations=max_iterations,
        )
        self._dp_finder = DesignPointFinder()

    def run(
        self,
        brief: DesignBrief,
        coeffs: RegressionCoeffs,
    ) -> SizingOutcome:
        """Run the full pipeline and return a SizingOutcome.

        Any stage that fails leaves its slot ``None`` in the outcome — the
        sensitivity engine handles this gracefully (a parameter value that
        produces no valid design simply contributes ``None`` to that
        sweep point).
        """
        try:
            weight = self._weight_engine.solve(brief, coeffs)
        except Exception as exc:  # noqa: BLE001
            _LOG.debug("weight solve failed: %s", exc)
            return SizingOutcome()

        try:
            cr = ConstraintAnalyzer(brief, weight).analyze()
        except Exception as exc:  # noqa: BLE001
            _LOG.debug("constraint analysis failed: %s", exc)
            return SizingOutcome(weight=weight)

        try:
            dp = self._dp_finder.find(brief, weight, cr, coeffs)
        except Exception as exc:  # noqa: BLE001
            _LOG.debug("design-point search failed: %s", exc)
            return SizingOutcome(weight=weight, constraint_result=cr)

        return SizingOutcome(
            weight=weight, constraint_result=cr, design_point=dp,
        )
