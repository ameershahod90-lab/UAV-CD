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
from dataclasses import dataclass
from typing import Optional

from app.core.entities import DesignBrief, RegressionCoeffs
from app.core.sensitivity.outcome import OUTPUT_CATALOG
from app.core.sensitivity.parameter_spec import (
    SWEEPABLE_PARAMETERS,
    SweepableParameter,
)
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


# ── Pre-curated pairs (output_id, parameter_field_name) ─────────────────────
#
# These are the classic conceptual-design sensitivities every aircraft
# engineer carries in their head. Order matters — list shows top-to-bottom
# in the UI. Pairs gated on propulsion are filtered at compute time.

_DEFAULT_PAIRS: tuple[tuple[str, str, str], tuple[str, ...]] = (
    # (output_id, parameter_field_name, phrasing_key)
    ("mtow_kg",        "payload_mass_kg",     "snowball.mtow_per_payload"),
    ("mtow_kg",        "cruise_speed_ms",     "snowball.mtow_per_cruise_speed"),
    ("mtow_kg",        "c_d0",                "snowball.mtow_per_cd0"),
    ("mtow_kg",        "aspect_ratio",        "snowball.mtow_per_ar"),
    ("engine_power_w", "payload_mass_kg",     "snowball.power_per_payload"),
    ("engine_power_w", "cruise_speed_ms",     "snowball.power_per_cruise_speed"),
    ("wing_area_m2",   "payload_mass_kg",     "snowball.wing_area_per_payload"),
    ("wing_area_m2",   "c_l_max",             "snowball.wing_area_per_clmax"),
    ("wingspan_m",     "aspect_ratio",        "snowball.wingspan_per_ar"),
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
    """
    runner = runner or SizingRunner()
    # Index params by field name for quick lookup
    by_field = {p.field_name: p for p in SWEEPABLE_PARAMETERS}

    factors: list[SnowballFactor] = []
    for output_id, field_name, phrasing_key in (
        (oid, fn, pk) for oid, fn, pk in _DEFAULT_PAIRS
    ):
        spec = OUTPUT_CATALOG.get(output_id)
        param = by_field.get(field_name)
        if spec is None or param is None:
            continue
        # Propulsion gating on the input parameter
        if param.requires_uses_fuel and not base_brief.propulsion_type.uses_fuel:
            continue
        if param.requires_is_electric and not base_brief.propulsion_type.is_electric:
            continue

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
