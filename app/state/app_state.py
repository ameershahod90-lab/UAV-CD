"""
Application State Tree — UAV-CD-APP
======================================
Pure-Python dataclasses representing the entire application state.

Design:
  - AppState is the root; sub-states are nested dataclasses.
  - All types use Optional[...] with None meaning "not yet computed".
  - run_history uses list (not tuple) because it grows over time.
  - HistoricalDataState owns both the classification config AND
    the regression results, keeping them co-located.
  - AppState is mutable (no frozen=True) because the AppStore mutates
    it via typed setters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.core.entities import (
    ClassificationRange,
    ConstraintResult,
    DesignBrief,
    DesignPoint,
    RegressionCoeffs,
    SizingRun,
    WeightResult,
)


# ---------------------------------------------------------------------------
# Project metadata
# ---------------------------------------------------------------------------

@dataclass
class ProjectMeta:
    """Identification and provenance information for a project file."""

    name: str = "Untitled Project"
    author: str = ""
    description: str = ""
    created_at: str = ""     # ISO 8601 timestamp
    modified_at: str = ""    # ISO 8601 timestamp
    app_version: str = "1.0.0"
    phase_version: int = 1   # Phase that produced this file


# ---------------------------------------------------------------------------
# Historical Data State
# ---------------------------------------------------------------------------

@dataclass
class HistoricalDataState:
    """
    All state related to the Historical Data tab.

    classification_ranges: User-defined MTOW bins (non-overlapping, full coverage).
    regression_coefficients: Computed per-class regression (class_name → RegressionCoeffs).
    active_plot_x / _y: Currently selected analysis playground axes.
    """

    classification_ranges: list[ClassificationRange] = field(
        default_factory=lambda: [
            ClassificationRange("Micro/Mini", 0.0,    25.0,    "#4fc3f7"),
            ClassificationRange("Small",      25.0,   150.0,   "#81c784"),
            ClassificationRange("Medium",     150.0,  1500.0,  "#ffb74d"),
            ClassificationRange("Large",      1500.0, 100_000.0, "#e57373"),
        ]
    )

    regression_coefficients: dict[str, RegressionCoeffs] = field(
        default_factory=dict
    )

    # Analysis playground axis selections
    active_plot_x: str = "mtow_kg"
    active_plot_y: str = "wingspan_m"

    # Plot display options
    log_scale_x: bool = True
    log_scale_y: bool = True
    show_regression_line: bool = True
    show_class_legend: bool = True

    def get_coefficients_for(
        self, class_name: str
    ) -> Optional[RegressionCoeffs]:
        """Return regression coefficients for class_name, or None if absent."""
        return self.regression_coefficients.get(class_name)

    def find_range_for_mtow(
        self, mtow_kg: float
    ) -> Optional[ClassificationRange]:
        """Return the first ClassificationRange that contains *mtow_kg*."""
        for cr in self.classification_ranges:
            if cr.contains(mtow_kg):
                return cr
        # Last bin: inclusive upper bound
        if self.classification_ranges:
            last = self.classification_ranges[-1]
            if mtow_kg >= last.min_mtow_kg:
                return last
        return None


# ---------------------------------------------------------------------------
# Sizing State
# ---------------------------------------------------------------------------

@dataclass
class SizingState:
    """
    All state related to the Phase-1 Sizing tab.

    brief: The current design brief (mutable input).
    weight_result / constraint_result / design_point: Latest computation outputs.
    run_history: Completed sizing runs for the comparison table.
    """

    brief: DesignBrief = field(default_factory=DesignBrief)

    weight_result:     Optional[WeightResult]    = None
    constraint_result: Optional[ConstraintResult] = None
    design_point:      Optional[DesignPoint]      = None

    run_history: list[SizingRun] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Root Application State
# ---------------------------------------------------------------------------

@dataclass
class AppState:
    """
    Root state object owned exclusively by AppStore.

    Order of fields reflects logical dependency:
      - meta: project identity
      - historical_data: classification drives regression which drives sizing
      - sizing: consumes regression coefficients from historical_data
    """

    meta:            ProjectMeta        = field(default_factory=ProjectMeta)
    historical_data: HistoricalDataState = field(default_factory=HistoricalDataState)
    sizing:          SizingState        = field(default_factory=SizingState)
    # Future phases: geometry, aero, structures, optimisation
