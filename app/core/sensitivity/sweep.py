"""
One-at-a-time (OAT) sweep — vary one input parameter, observe outputs.

OAT is the standard first step in aircraft sensitivity analysis
(Raymer Ch. 19, Keane et al. Ch. 4): it answers "how does this design
respond when I change one requirement?". It can't detect interactions
between inputs — for that you need Sobol / Morris / DOE — but in
conceptual design, where the dominant inputs are typically uncoupled
(payload, range, CD₀ each act through different terms of the Breguet
equation), OAT captures 90% of the useful insight.

This module produces ``OATSweep`` data — a list of (input_value, outcome)
tuples — that the UI consumes to draw the sweep curves and the tornado.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Optional

import numpy as np

from app.core.entities import DesignBrief, RegressionCoeffs
from app.core.sensitivity.outcome import SizingOutcome
from app.core.sensitivity.parameter_spec import SweepableParameter
from app.core.sensitivity.runner import SizingRunner


@dataclass(frozen=True)
class SweepPoint:
    """One sample of an OAT sweep."""
    input_value: float
    outcome:     SizingOutcome   # may have all-None fields if pipeline failed


@dataclass(frozen=True)
class OATSweep:
    """Result of one OAT sweep over a single parameter."""
    parameter:   SweepableParameter
    baseline:    float                    # the brief's current value
    points:      tuple[SweepPoint, ...]

    def outputs_for(self, output_id: str) -> tuple[list[float], list[Optional[float]]]:
        """Return parallel ``(x, y)`` arrays for plotting one output.

        ``y`` entries are ``None`` for failed pipeline runs; callers should
        mask those out before plotting.
        """
        xs: list[float] = []
        ys: list[Optional[float]] = []
        for sp in self.points:
            xs.append(sp.input_value)
            ys.append(sp.outcome.get(output_id))
        return xs, ys


def run_oat_sweep(
    base_brief: DesignBrief,
    coeffs: RegressionCoeffs,
    parameter: SweepableParameter,
    *,
    runner: Optional[SizingRunner] = None,
    n_points: int = 11,
    delta_pct: float = 20.0,
) -> OATSweep:
    """Sweep ``parameter`` across ``±delta_pct`` around its current value.

    The sweep range is clamped to the parameter's physical
    ``[min_value, max_value]`` bounds. Some sweep points may fail (e.g.
    an absurd CD₀ producing a non-convergent weight loop); those points
    are recorded with empty SizingOutcome so the UI can mask them.

    Default ``delta_pct=20``: a ±20 % band balances "wide enough to see
    non-linearity" against "narrow enough to remain near the current
    design's operating regime". This is the conceptual-design default
    used in Raymer's trade-study examples.
    """
    if n_points < 2:
        raise ValueError(f"n_points must be ≥ 2 (got {n_points})")
    runner = runner or SizingRunner()

    base_value = float(getattr(base_brief, parameter.field_name))
    lo = max(base_value * (1 - delta_pct / 100.0), parameter.min_value)
    hi = min(base_value * (1 + delta_pct / 100.0), parameter.max_value)
    # Defensive: if the band collapses to a single point (parameter pinned
    # at its bound), expand to whatever room we have on the other side.
    if hi <= lo:
        if base_value < parameter.max_value:
            hi = min(parameter.max_value, base_value * 1.001)
        if hi <= lo:
            lo = max(parameter.min_value, base_value * 0.999)

    values = np.linspace(lo, hi, n_points)
    samples: list[SweepPoint] = []
    for v in values:
        modified = dataclasses.replace(base_brief, **{parameter.field_name: float(v)})
        outcome = runner.run(modified, coeffs)
        samples.append(SweepPoint(input_value=float(v), outcome=outcome))

    return OATSweep(
        parameter=parameter,
        baseline=base_value,
        points=tuple(samples),
    )
