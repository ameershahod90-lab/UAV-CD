"""
Tornado chart data — rank inputs by influence on a chosen output.

A tornado chart is the conceptual designer's "where do I focus?" view.
For each candidate input, we re-run the sizing pipeline at the input's
``-delta_pct`` and ``+delta_pct`` values and record how the chosen output
moves relative to the baseline. Bars are sorted by absolute magnitude so
the dominant drivers float to the top of the chart.

Unlike OAT (which produces a full curve per parameter), the tornado
needs just two extra runs per parameter — 2N runs total for N inputs.
Fast enough to be interactive.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Optional

from app.core.entities import DesignBrief, RegressionCoeffs
from app.core.sensitivity.outcome import SizingOutcome
from app.core.sensitivity.parameter_spec import SweepableParameter
from app.core.sensitivity.runner import SizingRunner


@dataclass(frozen=True)
class TornadoBar:
    """One row of a tornado chart — the impact of varying one parameter."""

    parameter:   SweepableParameter
    baseline_in: float                 # parameter's value at the current design
    baseline_out: Optional[float]      # output value at the baseline

    # Output values at the perturbed ends. ``None`` if the pipeline failed.
    output_at_low:  Optional[float]
    output_at_high: Optional[float]

    # Corresponding input values (after clamping to parameter bounds).
    input_at_low:   float
    input_at_high:  float

    @property
    def delta_low(self) -> Optional[float]:
        """Signed change in output from baseline → low-end perturbation."""
        if self.output_at_low is None or self.baseline_out is None:
            return None
        return self.output_at_low - self.baseline_out

    @property
    def delta_high(self) -> Optional[float]:
        """Signed change in output from baseline → high-end perturbation."""
        if self.output_at_high is None or self.baseline_out is None:
            return None
        return self.output_at_high - self.baseline_out

    @property
    def magnitude(self) -> float:
        """Absolute spread used for sorting: max(|Δlow|, |Δhigh|)."""
        m = 0.0
        if self.delta_low is not None:
            m = max(m, abs(self.delta_low))
        if self.delta_high is not None:
            m = max(m, abs(self.delta_high))
        return m


@dataclass(frozen=True)
class TornadoData:
    """A complete tornado chart for one output."""

    output_id:    str
    baseline_out: Optional[float]
    bars:         tuple[TornadoBar, ...]   # sorted: largest impact first


def compute_tornado(
    base_brief: DesignBrief,
    coeffs: RegressionCoeffs,
    parameters: list[SweepableParameter],
    output_id: str,
    *,
    runner: Optional[SizingRunner] = None,
    delta_pct: float = 20.0,
) -> TornadoData:
    """Compute the tornado data for ``output_id`` across ``parameters``.

    Cost: ``1 + 2*len(parameters)`` sizing runs (baseline + low/high for
    each parameter). With ~14 parameters that's ~29 runs ≈ 0.3 s total —
    well within an interactive UI budget.
    """
    runner = runner or SizingRunner()
    baseline_outcome = runner.run(base_brief, coeffs)
    baseline_out = baseline_outcome.get(output_id)

    bars: list[TornadoBar] = []
    for p in parameters:
        base_value = float(getattr(base_brief, p.field_name))
        v_lo = max(base_value * (1 - delta_pct / 100.0), p.min_value)
        v_hi = min(base_value * (1 + delta_pct / 100.0), p.max_value)
        if v_lo == base_value and v_hi == base_value:
            # Parameter is pinned at a bound — record a degenerate bar.
            bars.append(TornadoBar(
                parameter=p, baseline_in=base_value, baseline_out=baseline_out,
                output_at_low=baseline_out, output_at_high=baseline_out,
                input_at_low=base_value, input_at_high=base_value,
            ))
            continue

        lo_brief = dataclasses.replace(base_brief, **{p.field_name: v_lo})
        hi_brief = dataclasses.replace(base_brief, **{p.field_name: v_hi})
        out_lo = runner.run(lo_brief, coeffs).get(output_id)
        out_hi = runner.run(hi_brief, coeffs).get(output_id)

        bars.append(TornadoBar(
            parameter=p,
            baseline_in=base_value,
            baseline_out=baseline_out,
            output_at_low=out_lo,
            output_at_high=out_hi,
            input_at_low=v_lo,
            input_at_high=v_hi,
        ))

    # Sort by magnitude descending — biggest movers float to the top.
    bars.sort(key=lambda b: b.magnitude, reverse=True)
    return TornadoData(
        output_id=output_id, baseline_out=baseline_out, bars=tuple(bars),
    )
