"""
Constraint-margin analysis — "which constraint bites first?".

For each constraint curve on the matching diagram, compute the slack
between the current design point and the boundary at the same wing-loading.
Expressed as a percentage so the views can colour-code (red < 10 %,
amber < 30 %, green ≥ 30 %).

Convention:
  * Power-loading mode (W/P, prop): boundary is an UPPER limit on W/P —
    designs must lie ABOVE the curve (lower W/P = more power = ok).
    Wait — re-read constraint sense: actually the constraint curves bound
    the feasible region from one side; the design point at W/P > boundary
    is infeasible (under-powered). Margin = (boundary − dp_loading) / boundary.
  * Thrust-loading mode (T/W, jet): boundary is a LOWER limit on T/W —
    designs must lie ABOVE the curve. Margin = (dp_loading − boundary) / boundary.
  * Stall: a vertical line in (W/S); design must lie LEFT of it. Margin
    = (stall_ws − dp_ws) / stall_ws.

A NEGATIVE margin means the design point is on the wrong side of that
constraint — i.e. already violated. The matching plot's violation banner
catches this elsewhere; here we surface the magnitude.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Optional

import numpy as np

from app.core.entities import (
    ConstraintCurve,
    ConstraintResult,
    DesignPoint,
)

# Industry defaults — Sadraey-style early-design slack convention.
# Caller may override via ``compute_constraint_margins`` keyword args.
_DEFAULT_CRITICAL_PCT: Final[float] = 10.0
_DEFAULT_TIGHT_PCT:    Final[float] = 30.0


@dataclass(frozen=True)
class ConstraintMargin:
    """How much slack the design point has against one constraint."""

    name:         str                 # constraint label (e.g. "Max Speed")
    margin_pct:   float               # % slack (negative = violated)
    boundary_value: Optional[float]   # the loading at the constraint at this W/S
    dp_value:     Optional[float]     # design point's loading
    # Severity tier (computed from margin_pct):
    #   "critical" → margin <  10 %   (red)
    #   "tight"    → margin <  30 %   (amber)
    #   "ok"       → margin >= 30 %   (green)
    severity:     str

    @property
    def is_violated(self) -> bool:
        return self.margin_pct < 0


@dataclass(frozen=True)
class MarginsReport:
    """All constraint margins + which one is most critical."""

    margins:        tuple[ConstraintMargin, ...]
    binding:        Optional[ConstraintMargin]   # the smallest non-violated margin
    most_violated:  Optional[ConstraintMargin]   # the most violated (if any)


def _severity(
    margin_pct: float,
    critical_pct: float,
    tight_pct: float,
) -> str:
    """Map a margin to a severity tier using configurable thresholds.

    ``critical_pct`` and ``tight_pct`` are the cut points: anything
    below ``critical_pct`` (or negative) is "critical", between
    ``critical_pct`` and ``tight_pct`` is "tight", at or above
    ``tight_pct`` is "ok".
    """
    if margin_pct < 0:
        return "critical"
    if margin_pct < critical_pct:
        return "critical"
    if margin_pct < tight_pct:
        return "tight"
    return "ok"


def _stall_margin(
    dp: DesignPoint,
    cr: ConstraintResult,
    critical_pct: float,
    tight_pct: float,
) -> ConstraintMargin:
    """Stall is a vertical line in (W/S). Margin = (stall − dp) / stall."""
    stall_ws = cr.stall_ws_nm2
    dp_ws    = dp.wing_loading_nm2
    margin   = (stall_ws - dp_ws) / stall_ws * 100.0 if stall_ws > 0 else 0.0
    return ConstraintMargin(
        name="Stall",
        margin_pct=margin,
        boundary_value=stall_ws,
        dp_value=dp_ws,
        severity=_severity(margin, critical_pct, tight_pct),
    )


def _curve_margin(
    dp: DesignPoint,
    cr: ConstraintResult,
    curve: ConstraintCurve,
    critical_pct: float,
    tight_pct: float,
) -> ConstraintMargin:
    """Curve margin: interpolate the boundary loading at dp's W/S, compare."""
    ws_arr = np.asarray(curve.wing_loading_values, dtype=float)
    ld_arr = np.asarray(curve.loading_values,      dtype=float)
    if len(ws_arr) < 2:
        return ConstraintMargin(
            name=curve.name, margin_pct=float("nan"),
            boundary_value=None, dp_value=dp.power_loading_nw,
            severity="ok",
        )

    boundary = float(np.interp(dp.wing_loading_nm2, ws_arr, ld_arr))
    dp_loading = dp.power_loading_nw

    if cr.is_power_loading_mode:
        # Power loading: feasible if dp_loading <= boundary; margin from
        # design point UP to the boundary as % of the boundary.
        margin = (boundary - dp_loading) / boundary * 100.0 if boundary > 0 else 0.0
    else:
        # Thrust loading: feasible if dp_loading >= boundary; margin from
        # design point DOWN to the boundary.
        margin = (dp_loading - boundary) / boundary * 100.0 if boundary > 0 else 0.0

    return ConstraintMargin(
        name=curve.name,
        margin_pct=margin,
        boundary_value=boundary,
        dp_value=dp_loading,
        severity=_severity(margin, critical_pct, tight_pct),
    )


def compute_constraint_margins(
    design_point: DesignPoint,
    constraint_result: ConstraintResult,
    *,
    critical_pct: float = _DEFAULT_CRITICAL_PCT,
    tight_pct:    float = _DEFAULT_TIGHT_PCT,
) -> MarginsReport:
    """Compute margins for all 5 constraints + identify the binding one.

    ``critical_pct`` / ``tight_pct`` are the severity tier cut-points
    (% margin). Defaults reproduce the previous hard-coded 10 / 30
    behaviour; the service layer plumbs in the user's configured values
    from ``UserSettings`` so designers can tighten or loosen the bands.
    """
    margins = [_stall_margin(
        design_point, constraint_result, critical_pct, tight_pct,
    )]
    for curve in constraint_result.curves:
        margins.append(_curve_margin(
            design_point, constraint_result, curve, critical_pct, tight_pct,
        ))

    # Binding = smallest non-violated margin (the one that bites first if
    # the design moves).
    non_violated = [m for m in margins if not m.is_violated]
    binding = min(non_violated, key=lambda m: m.margin_pct) if non_violated else None

    # Most-violated = most negative margin (if any constraint is violated).
    violated = [m for m in margins if m.is_violated]
    most_violated = min(violated, key=lambda m: m.margin_pct) if violated else None

    return MarginsReport(
        margins=tuple(margins),
        binding=binding,
        most_violated=most_violated,
    )
