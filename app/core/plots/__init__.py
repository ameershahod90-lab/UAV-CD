"""
Pure-Python plot-data builders.

Each module produces an immutable data structure that captures everything
needed to draw a chart — curves, decorations, labels, ranges. The same
structure is consumed by both the live Qt/pyqtgraph UI plots AND the
matplotlib renderers used by the report export.

Layer: ``core/`` — zero Qt and matplotlib imports here.
"""

from app.core.plots.matching_diagram import (
    MatchingCurveData,
    MatchingPlotData,
    build_matching_plot_data,
)
from app.core.plots.mission_profile import (
    MissionProfileData,
    MissionSegmentRender,
    build_mission_profile_data,
)

__all__ = [
    "MatchingCurveData",
    "MatchingPlotData",
    "MissionProfileData",
    "MissionSegmentRender",
    "build_matching_plot_data",
    "build_mission_profile_data",
]
