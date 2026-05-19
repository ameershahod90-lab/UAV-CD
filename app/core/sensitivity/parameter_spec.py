"""
Sweepable input parameters for sensitivity analysis.

Each entry declares one DesignBrief field as sweep-able + the physical
range it makes sense to vary over (clamps the ±% sweep against absurd
values like negative aspect ratio).

A few inputs are only meaningful for certain propulsion types
(battery params for electric / hybrid; SFC for fuel / hybrid).
``sweepable_parameters_for(propulsion_type)`` returns the relevant subset.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.enums import PropulsionType


@dataclass(frozen=True)
class SweepableParameter:
    """A DesignBrief field that the sensitivity engine can sweep."""

    field_name: str            # attribute name on DesignBrief
    label:      str            # human-readable (EN fallback)
    label_key:  str            # i18n key
    unit:       str            # SI unit symbol
    min_value:  float          # physical lower bound (clamp)
    max_value:  float          # physical upper bound (clamp)
    # Propulsion gating — None means "always relevant"
    requires_uses_fuel:    Optional[bool] = None
    requires_is_electric:  Optional[bool] = None


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
        "prop_efficiency", "Propulsive Efficiency (ηₚ)",
        "sens.param.prop_efficiency", "-", 0.3, 0.95,
    ),

    # ── Propulsion-specific ──────────────────────────────────────────────
    SweepableParameter(
        "specific_fuel_consumption_g_wh", "SFC",
        "sens.param.sfc", "g/(W·h)", 0.05, 1.5,
        requires_uses_fuel=True,
    ),
    SweepableParameter(
        "battery_energy_density_wh_kg", "Battery Energy Density",
        "sens.param.battery_energy_density", "Wh/kg", 100.0, 800.0,
        requires_is_electric=True,
    ),
    SweepableParameter(
        "battery_efficiency", "Battery Efficiency",
        "sens.param.battery_efficiency", "-", 0.5, 0.99,
        requires_is_electric=True,
    ),
)


def sweepable_parameters_for(
    propulsion_type: PropulsionType,
) -> list[SweepableParameter]:
    """Return the subset of parameters relevant to ``propulsion_type``.

    Battery params drop out for fuel-only propulsion. SFC drops out for
    pure electric. HYBRID keeps everything.
    """
    out: list[SweepableParameter] = []
    for p in SWEEPABLE_PARAMETERS:
        if p.requires_uses_fuel is not None:
            if p.requires_uses_fuel and not propulsion_type.uses_fuel:
                continue
        if p.requires_is_electric is not None:
            if p.requires_is_electric and not propulsion_type.is_electric:
                continue
        out.append(p)
    return out
