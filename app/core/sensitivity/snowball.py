"""
Snowball factors — partial derivatives ∂(output)/∂(input) at the design point.

These are the conceptual designer's rules-of-thumb:

  * ``∂MTOW/∂W_payload`` — the *takeoff-weight derivative* (Raymer §3.5).
    Adding 1 kg of payload grows MTOW by this many kg, because heavier
    payload means more fuel/battery, which means more structure, which
    means more wing, … (the "snowball").
  * ``∂P/∂W_payload`` — extra engine power needed per kg of payload.
  * ``∂S/∂(CL_max)`` — wing area saved by improving high-lift devices.
  * ``∂MTOW/∂Range`` — weight cost of additional mission range.

Computed by central differences with a small perturbation (default ±1 %)
so the derivative is local to the current design point and doesn't drift
through any constraint regime changes.

These factors are unit-aware: each one's interpretation includes the
input and output units so the UI can present them as full sentences in
the user's language ("each extra kilogram of payload adds N kg of MTOW").
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Optional

from app.core.entities import DesignBrief, RegressionCoeffs
from app.core.sensitivity.outcome import OUTPUT_CATALOG
from app.core.sensitivity.parameter_spec import (
    SWEEPABLE_PARAMETERS,
    SweepableParameter,
)
from app.core.sensitivity.predicates import InclusionPredicate, always
from app.core.sensitivity.runner import SizingRunner


@dataclass(frozen=True)
class SnowballFactor:
    """One partial derivative ∂(output)/∂(input) at the design point."""

    output_id:   str
    output_label: str
    output_unit:  str
    parameter:   SweepableParameter
    value:       Optional[float]    # the derivative; None if it couldn't be computed
    # Human-readable phrasing slot — UI fills this in with the translated
    # template, e.g. "Adding 1 {input_unit} of {input_label} grows {output_label}
    # by {value:.2f} {output_unit}". Kept here as a description ID so the
    # i18n layer can swap the phrasing per language.
    phrasing_key: str = "snowball.default_phrasing"


@dataclass(frozen=True)
class SnowballReport:
    """A curated set of design rule-of-thumb derivatives."""
    factors: tuple[SnowballFactor, ...]


# ── Curated default snowball pairs ─────────────────────────────────────────


@dataclass(frozen=True)
class SnowballPair:
    """One ``(output, input)`` derivative the snowball compute will evaluate.

    The pair carries its own ``is_included(brief)`` predicate so a future
    pair like "∂MTOW/∂SFC" could be auto-skipped for electric aircraft
    even without touching the compute loop. Today all default pairs use
    universal inputs/outputs and inherit ``always``.

    Pairs are also auto-skipped when:
      * the referenced ``output_id`` is not in OUTPUT_CATALOG, or
      * the referenced ``field_name`` is not in SWEEPABLE_PARAMETERS, or
      * the input parameter's own predicate excludes it for this brief.
    """

    output_id:    str
    field_name:   str
    phrasing_key: str
    is_included:  InclusionPredicate = field(default=always)


# These are the classic conceptual-design sensitivities every aircraft
# engineer carries in their head. Order matters — list shows top-to-bottom
# in the UI. Pairs are also gated through their input parameter's own
# ``is_included`` predicate at compute time, so propulsion-irrelevant
# pairs (e.g. anything against SFC for an electric aircraft) drop out
# automatically without per-pair maintenance.

_DEFAULT_PAIRS: tuple[SnowballPair, ...] = (
    SnowballPair("mtow_kg",        "payload_mass_kg",     "snowball.mtow_per_payload"),
    SnowballPair("mtow_kg",        "cruise_speed_ms",     "snowball.mtow_per_cruise_speed"),
    SnowballPair("mtow_kg",        "c_d0",                "snowball.mtow_per_cd0"),
    SnowballPair("mtow_kg",        "aspect_ratio",        "snowball.mtow_per_ar"),
    SnowballPair("engine_power_w", "payload_mass_kg",     "snowball.power_per_payload"),
    SnowballPair("engine_power_w", "cruise_speed_ms",     "snowball.power_per_cruise_speed"),
    SnowballPair("wing_area_m2",   "payload_mass_kg",     "snowball.wing_area_per_payload"),
    SnowballPair("wing_area_m2",   "c_l_max",             "snowball.wing_area_per_clmax"),
    SnowballPair("wingspan_m",     "aspect_ratio",        "snowball.wingspan_per_ar"),
)


def compute_snowball_factors(
    base_brief: DesignBrief,
    coeffs: RegressionCoeffs,
    *,
    runner: Optional[SizingRunner] = None,
    delta_pct: float = 1.0,
) -> SnowballReport:
    """Compute the canonical rule-of-thumb derivatives at the current design.

    ``delta_pct`` controls the central-difference width. 1 % keeps the
    derivative truly local; for non-linear inputs the user can compare
    against an OAT curve to see how much the slope changes globally.

    Per-pair inclusion: each ``SnowballPair`` carries its own
    ``is_included(brief)`` predicate; additionally, the referenced
    OutputSpec and SweepableParameter must themselves be included for
    the current brief. Anything else is silently dropped.
    """
    runner = runner or SizingRunner()
    # Index params by field name for quick lookup
    by_field = {p.field_name: p for p in SWEEPABLE_PARAMETERS}

    factors: list[SnowballFactor] = []
    for pair in _DEFAULT_PAIRS:
        spec = OUTPUT_CATALOG.get(pair.output_id)
        param = by_field.get(pair.field_name)
        if spec is None or param is None:
            continue
        # Three-layer inclusion: pair-level, output-level, input-level.
        if not pair.is_included(base_brief):
            continue
        if not spec.is_included(base_brief):
            continue
        if not param.is_included(base_brief):
            continue
        output_id   = pair.output_id
        field_name  = pair.field_name
        phrasing_key = pair.phrasing_key

        # Central difference at ±delta_pct of the parameter's current value
        x0 = float(getattr(base_brief, field_name))
        h  = max(abs(x0) * (delta_pct / 100.0), 1e-9)
        x_lo, x_hi = x0 - h, x0 + h
        # Clamp to physical bounds — if we lose symmetry, fall back to a
        # one-sided difference rather than refusing to compute.
        if x_lo < param.min_value:
            x_lo = param.min_value
        if x_hi > param.max_value:
            x_hi = param.max_value
        if x_hi <= x_lo:
            factors.append(SnowballFactor(
                output_id=output_id,
                output_label=spec.label,
                output_unit=spec.unit,
                parameter=param,
                value=None,
                phrasing_key=phrasing_key,
            ))
            continue

        lo_brief = dataclasses.replace(base_brief, **{field_name: x_lo})
        hi_brief = dataclasses.replace(base_brief, **{field_name: x_hi})
        out_lo = runner.run(lo_brief, coeffs).get(output_id)
        out_hi = runner.run(hi_brief, coeffs).get(output_id)
        if out_lo is None or out_hi is None:
            value: Optional[float] = None
        else:
            value = (out_hi - out_lo) / (x_hi - x_lo)

        factors.append(SnowballFactor(
            output_id=output_id,
            output_label=spec.label,
            output_unit=spec.unit,
            parameter=param,
            value=value,
            phrasing_key=phrasing_key,
        ))

    return SnowballReport(factors=tuple(factors))
