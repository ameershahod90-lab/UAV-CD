"""
Unit Conversion — UAV-CD-APP
==============================
Stateless conversion between SI storage units and display units.

Design principles:
  - All internal computation and file storage uses SI units ONLY.
  - Conversion happens exclusively at the UI boundary (read: display,
    write: parse back to SI).
  - No magic globals; callers pass the enum variant explicitly.
  - Cascade helper synchronises unit_system → all individual unit choices.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.state.settings import UserSettings

from app.core.enums import (
    AltitudeUnit,
    AreaUnit,
    ForceUnit,
    LengthUnit,
    MassUnit,
    PowerUnit,
    SpeedUnit,
    UnitSystem,
)


# ---------------------------------------------------------------------------
# Conversion factors: SI → display unit
# ---------------------------------------------------------------------------

_SPEED_FACTORS: dict[SpeedUnit, float] = {
    SpeedUnit.MS:    1.0,
    SpeedUnit.KMH:   3.6,
    SpeedUnit.KNOTS: 1.943_844,
    SpeedUnit.FTS:   3.280_840,
}

_ALTITUDE_FACTORS: dict[AltitudeUnit, float] = {
    AltitudeUnit.METERS: 1.0,
    AltitudeUnit.FEET:   3.280_840,
}

_MASS_FACTORS: dict[MassUnit, float] = {
    MassUnit.KG: 1.0,
    MassUnit.LB: 2.204_623,
}

_AREA_FACTORS: dict[AreaUnit, float] = {
    AreaUnit.M2:  1.0,
    AreaUnit.FT2: 10.763_910,
}

_POWER_FACTORS: dict[PowerUnit, float] = {
    PowerUnit.WATT: 1.0,
    PowerUnit.KW:   0.001,
    PowerUnit.HP:   0.001_341_022,
}

_FORCE_FACTORS: dict[ForceUnit, float] = {
    ForceUnit.NEWTON: 1.0,
    ForceUnit.LBF:    0.224_809,
}

_LENGTH_FACTORS: dict[LengthUnit, float] = {
    LengthUnit.METERS: 1.0,
    LengthUnit.FEET:   3.280_840,
    LengthUnit.INCHES: 39.370_079,
}


# ---------------------------------------------------------------------------
# UnitConverter — stateless, static-method API
# ---------------------------------------------------------------------------

class UnitConverter:
    """
    Converts scalar values between SI and display units.

    Usage
    -----
    >>> si_value = 25.0  # m/s
    >>> knots = UnitConverter.speed_to_display(si_value, SpeedUnit.KNOTS)
    >>> back  = UnitConverter.speed_to_si(knots, SpeedUnit.KNOTS)
    """

    # ── Speed ────────────────────────────────────────────────────────────
    @staticmethod
    def speed_to_display(si_ms: float, unit: SpeedUnit) -> float:
        return si_ms * _SPEED_FACTORS[unit]

    @staticmethod
    def speed_to_si(display_val: float, unit: SpeedUnit) -> float:
        return display_val / _SPEED_FACTORS[unit]

    # ── Altitude / Length (dimensionally identical categories) ───────────
    @staticmethod
    def altitude_to_display(si_m: float, unit: AltitudeUnit) -> float:
        return si_m * _ALTITUDE_FACTORS[unit]

    @staticmethod
    def altitude_to_si(display_val: float, unit: AltitudeUnit) -> float:
        return display_val / _ALTITUDE_FACTORS[unit]

    @staticmethod
    def length_to_display(si_m: float, unit: LengthUnit) -> float:
        return si_m * _LENGTH_FACTORS[unit]

    @staticmethod
    def length_to_si(display_val: float, unit: LengthUnit) -> float:
        return display_val / _LENGTH_FACTORS[unit]

    # ── Mass ─────────────────────────────────────────────────────────────
    @staticmethod
    def mass_to_display(si_kg: float, unit: MassUnit) -> float:
        return si_kg * _MASS_FACTORS[unit]

    @staticmethod
    def mass_to_si(display_val: float, unit: MassUnit) -> float:
        return display_val / _MASS_FACTORS[unit]

    # ── Area ─────────────────────────────────────────────────────────────
    @staticmethod
    def area_to_display(si_m2: float, unit: AreaUnit) -> float:
        return si_m2 * _AREA_FACTORS[unit]

    @staticmethod
    def area_to_si(display_val: float, unit: AreaUnit) -> float:
        return display_val / _AREA_FACTORS[unit]

    # ── Power ─────────────────────────────────────────────────────────────
    @staticmethod
    def power_to_display(si_w: float, unit: PowerUnit) -> float:
        return si_w * _POWER_FACTORS[unit]

    @staticmethod
    def power_to_si(display_val: float, unit: PowerUnit) -> float:
        return display_val / _POWER_FACTORS[unit]

    # ── Force ─────────────────────────────────────────────────────────────
    @staticmethod
    def force_to_display(si_n: float, unit: ForceUnit) -> float:
        return si_n * _FORCE_FACTORS[unit]

    @staticmethod
    def force_to_si(display_val: float, unit: ForceUnit) -> float:
        return display_val / _FORCE_FACTORS[unit]

    # ── Convenience label ─────────────────────────────────────────────────
    @staticmethod
    def label(unit: object) -> str:
        """Return the display string for any unit enum."""
        return getattr(unit, "value", str(unit))


# ---------------------------------------------------------------------------
# Cascade helper: UnitSystem → individual units
# ---------------------------------------------------------------------------

def cascade_unit_system(settings: "UserSettings") -> "UserSettings":
    """
    Return a new UserSettings with individual unit fields cascaded from
    ``settings.unit_system``. Called whenever the user changes the system.
    Individual overrides can still be made afterwards.
    """
    if settings.unit_system is UnitSystem.METRIC:
        return replace(
            settings,
            speed_unit=SpeedUnit.MS,
            altitude_unit=AltitudeUnit.METERS,
            mass_unit=MassUnit.KG,
            area_unit=AreaUnit.M2,
            power_unit=PowerUnit.WATT,
        )
    else:  # IMPERIAL
        return replace(
            settings,
            speed_unit=SpeedUnit.KNOTS,
            altitude_unit=AltitudeUnit.FEET,
            mass_unit=MassUnit.LB,
            area_unit=AreaUnit.FT2,
            power_unit=PowerUnit.HP,
        )
