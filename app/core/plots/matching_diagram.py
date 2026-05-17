"""
Matching Diagram Plot Data — UAV-CD-APP
============================================
Pure data builder for the W/S vs W/P (or T/W) constraint diagram.

The same builder feeds:
  - the live pyqtgraph plot in ``app/ui/tabs/sizing/constraints_tab.py``
  - the matplotlib renderer in ``app/services/figure_renderers.py`` (export)

Layer: ``core/`` — pure Python (numpy is allowed). No Qt / no matplotlib.
Display-unit conversion happens here so consumers only have to draw.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from app.core.display_converter import DisplayConverter
from app.core.entities import ConstraintResult, DesignPoint


@dataclass(frozen=True)
class MatchingCurveData:
    """A single constraint curve, already in display units."""
    name: str
    color: str             # hex
    ws: np.ndarray         # display units (e.g. N/m² or lbf/ft²)
    loading: np.ndarray    # display units (e.g. N/W or lbf/hp, or T/W)


@dataclass(frozen=True)
class MatchingPlotData:
    """Everything a plot renderer needs to draw the matching diagram."""
    curves: tuple[MatchingCurveData, ...]
    stall_x:    float                        # vertical-line x in display units
    y_top:      float                        # clipped Y-axis upper bound (display units)
    ws_label:   str                          # axis label, e.g. "Wing Loading W/S [N/m²]"
    loading_label: str                       # axis label, e.g. "W/P [N/W]" or "T/W [—]"
    is_power_loading_mode: bool
    design_point: Optional[tuple[float, float]]  # (ws_display, loading_display) or None


def build_matching_plot_data(
    cr: ConstraintResult,
    dp: Optional[DesignPoint],
    dc: DisplayConverter,
) -> MatchingPlotData:
    """Compose the renderable matching-diagram data.

    The Y-axis upper bound is clipped to roughly 2.5× the design-point
    loading (or 2× the median curve loading when no design point exists)
    so constraint asymptotes don't squeeze the feasible region into a thin
    strip at the bottom and push the design-point marker off-screen.
    """
    is_power = cr.is_power_loading_mode

    # Axis labels — pick the right loading unit based on propulsion mode
    _, ws_unit = dc.wing_loading(0)
    if is_power:
        _, pl_unit = dc.power_loading(0)
        loading_label = f"W/P [{pl_unit}]"
    else:
        _, fl_unit = dc.force_loading(0)
        loading_label = f"T/W [{fl_unit}]"
    ws_label = f"Wing Loading W/S [{ws_unit}]"

    # Convert curves
    curves: list[MatchingCurveData] = []
    for curve in cr.curves:
        xs = np.asarray(curve.wing_loading_values, dtype=float)
        ys = np.asarray(curve.loading_values, dtype=float)
        ws_disp = np.array([dc.wing_loading(float(v))[0] for v in xs])
        if is_power:
            ld_disp = np.array([dc.power_loading(float(v))[0] for v in ys])
        else:
            ld_disp = ys
        curves.append(
            MatchingCurveData(
                name=curve.name,
                color=curve.color_hex,
                ws=ws_disp,
                loading=ld_disp,
            )
        )

    # Design point
    dp_disp: Optional[tuple[float, float]] = None
    if dp is not None:
        dp_ws = dc.wing_loading(dp.wing_loading_nm2)[0]
        dp_ld = (
            dc.power_loading(dp.power_loading_nw)[0]
            if is_power else dp.power_loading_nw
        )
        dp_disp = (dp_ws, dp_ld)

    # Y-axis upper bound (see module docstring for rationale)
    if dp_disp is not None:
        y_top = max(dp_disp[1] * 2.5, 0.05)
    else:
        medians = [float(np.median(c.loading)) for c in curves if len(c.loading)]
        y_top = (max(medians) * 2.0) if medians else 1.0

    # Stall vertical line
    stall_x = dc.wing_loading(cr.stall_ws_nm2)[0]

    return MatchingPlotData(
        curves=tuple(curves),
        stall_x=stall_x,
        y_top=y_top,
        ws_label=ws_label,
        loading_label=loading_label,
        is_power_loading_mode=is_power,
        design_point=dp_disp,
    )
