"""
Sweepable input parameters for sensitivity analysis.

Each entry declares one DesignBrief field as sweep-able + the physical
range it makes sense to vary over (clamps the ±% sweep against absurd
values like negative aspect ratio).

Inputs that don't apply to every propulsion mode carry an
``is_included(brief) -> bool`` predicate that the fetching pipeline
checks before exposing the parameter. Examples:

  * ``prop_efficiency`` — only valid for power-mode propulsion
    (Electric / Piston / Turboprop / Hybrid); the jet branches in
    ``constraints.py`` never read it.
  * ``specific_fuel_consumption_g_wh`` — only valid when the engine
    burns fuel (Piston / Turboprop / Turbojet / Hybrid).
  * ``battery_energy_density_wh_kg`` / ``battery_efficiency`` — only
    valid when the engine draws on a battery (Electric / Hybrid).

See ``app/core/sensitivity/predicates.py`` for the named predicate
functions used here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.entities import DesignBrief
from app.core.sensitivity.predicates import (
    InclusionPredicate,
    always,
    requires_is_electric,
    requires_is_power_mode,
    requires_uses_fuel,
)


@dataclass(frozen=True)
class SweepableParameter:
    """A DesignBrief field that the sensitivity engine can sweep."""

    field_name: str            # attribute name on DesignBrief
    label:      str            # human-readable (EN fallback)
    label_key:  str            # i18n key
    unit:       str            # SI unit symbol
    min_value:  float          # physical lower bound (clamp)
    max_value:  float          # physical upper bound (clamp)
    # Single declarative predicate that tells the fetching pipeline
    # whether this parameter is relevant for the given brief. Defaults
    # to ``always`` (universal). Replaces the previous
    # ``requires_uses_fuel`` / ``requires_is_electric`` boolean pair.
    is_included: InclusionPredicate = field(default=always)


# ── Master parameter list ───────────────────────────────────────────────────

SWEEPABLE_PARAMETERS: tuple[SweepableParameter, ...] = (
    # ── Mission requirements ─────────────────────────────────────────────
    SweepableParameter(
        "payload_mass_kg", "Payload Mass", "sens.param.payload_mass",
        "kg", 0.1, 5000.0,
    ),
    SweepableParameter(
        "cruise_speed_ms", "Cruise Speed", "sens.param.cruise_speed",
        "m/s", 5.0, 250.0,
    ),
    SweepableParameter(
        "stall_speed_ms", "Stall Speed", "sens.param.stall_speed",
        "m/s", 3.0, 60.0,
    ),
    SweepableParameter(
        "max_speed_ms", "Max Speed", "sens.param.max_speed",
        "m/s", 10.0, 350.0,
    ),
    SweepableParameter(
        "rate_of_climb_ms", "Rate of Climb", "sens.param.rate_of_climb",
        "m/s", 0.1, 30.0,
    ),
    SweepableParameter(
        "cruise_altitude_m", "Cruise Altitude", "sens.param.cruise_altitude",
        "m", 0.0, 20000.0,
    ),
    SweepableParameter(
        "service_ceiling_m", "Service Ceiling", "sens.param.service_ceiling",
        "m", 0.0, 25000.0,
    ),
    SweepableParameter(
        "takeoff_run_m", "Takeoff Run", "sens.param.takeoff_run",
        "m", 0.0, 2000.0,
    ),

    # ── Aerodynamic coefficients ─────────────────────────────────────────
    SweepableParameter(
        "aspect_ratio", "Aspect Ratio (AR)", "sens.param.aspect_ratio",
        "-", 3.0, 30.0,
    ),
    SweepableParameter(
        "c_d0", "CD₀", "sens.param.c_d0",
        "-", 0.005, 0.10,
    ),
    SweepableParameter(
        "c_l_max", "CL max", "sens.param.c_l_max",
        "-", 0.8, 3.5,
    ),
    SweepableParameter(
        "oswald_efficiency", "Oswald Efficiency (e)", "sens.param.oswald",
        "-", 0.5, 0.99,
    ),
    SweepableParameter(
        # η_p only enters power-mode equations — gated to is_power_mode.
        "prop_efficiency", "Propulsive Efficiency (ηₚ)",
        "sens.param.prop_efficiency", "-", 0.3, 0.95,
        is_included=requires_is_power_mode,
    ),

    # ── Propulsion-specific ──────────────────────────────────────────────
    SweepableParameter(
        "specific_fuel_consumption_g_wh", "SFC",
        "sens.param.sfc", "g/(W·h)", 0.05, 1.5,
        is_included=requires_uses_fuel,
    ),
    SweepableParameter(
        "battery_energy_density_wh_kg", "Battery Energy Density",
        "sens.param.battery_energy_density", "Wh/kg", 100.0, 800.0,
        is_included=requires_is_electric,
    ),
    SweepableParameter(
        "battery_efficiency", "Battery Efficiency",
        "sens.param.battery_efficiency", "-", 0.5, 0.99,
        is_included=requires_is_electric,
    ),
)


def sweepable_parameters_for(brief: DesignBrief) -> list[SweepableParameter]:
    """Return the subset of parameters relevant to the current brief.

    A parameter is included iff ``parameter.is_included(brief)`` returns
    True. The default predicate is ``always`` (universal); propulsion-
    gated parameters use ``requires_*`` predicates from
    ``app/core/sensitivity/predicates.py``.
    """
    return [p for p in SWEEPABLE_PARAMETERS if p.is_included(brief)]
