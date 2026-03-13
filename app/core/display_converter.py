"""
Display Converter — UAV-CD-APP
=================================
Centralized SI → display-unit conversion for the entire UI layer.

Every UI component that shows a value with units uses this class to:
  1. Convert an SI value to the current display unit.
  2. Get the human-readable unit label.

Usage::

    dc = DisplayConverter(store.settings)
    val, label = dc.speed(25.0)   # → (90.0, "km/h")  if speed_unit == KMH
    val, label = dc.mass(32.0)    # → (70.55, "lb")    if mass_unit == LB

Rebuilt automatically when settings change; caller just creates a new instance.
"""

from __future__ import annotations

from typing import Callable

from app.core.enums import (
    AltitudeUnit,
    AreaUnit,
    ForceUnit,
    LengthUnit,
    MassUnit,
    PowerUnit,
    SpeedUnit,
)
from app.core.units import UnitConverter
from app.state.settings import UserSettings


class DisplayConverter:
    """
    Stateless converter that reads units from a UserSettings snapshot.

    Each method returns ``(display_value, unit_label_string)``.
    """

    __slots__ = ("_settings",)

    def __init__(self, settings: UserSettings) -> None:
        self._settings: UserSettings = settings

    # ── Dimension converters (SI → display, label) ────────────────────────

    def speed(self, si_ms: float) -> tuple[float, str]:
        u = self._settings.speed_unit
        return UnitConverter.speed_to_display(si_ms, u), u.value

    def speed_to_si(self, display_val: float) -> float:
        return UnitConverter.speed_to_si(display_val, self._settings.speed_unit)

    def altitude(self, si_m: float) -> tuple[float, str]:
        u = self._settings.altitude_unit
        return UnitConverter.altitude_to_display(si_m, u), u.value

    def altitude_to_si(self, display_val: float) -> float:
        return UnitConverter.altitude_to_si(display_val, self._settings.altitude_unit)

    def mass(self, si_kg: float) -> tuple[float, str]:
        u = self._settings.mass_unit
        return UnitConverter.mass_to_display(si_kg, u), u.value

    def mass_to_si(self, display_val: float) -> float:
        return UnitConverter.mass_to_si(display_val, self._settings.mass_unit)

    def area(self, si_m2: float) -> tuple[float, str]:
        u = self._settings.area_unit
        return UnitConverter.area_to_display(si_m2, u), u.value

    def area_to_si(self, display_val: float) -> float:
        return UnitConverter.area_to_si(display_val, self._settings.area_unit)

    def power(self, si_w: float) -> tuple[float, str]:
        u = self._settings.power_unit
        return UnitConverter.power_to_display(si_w, u), u.value

    def power_to_si(self, display_val: float) -> float:
        return UnitConverter.power_to_si(display_val, self._settings.power_unit)

    def force(self, si_n: float) -> tuple[float, str]:
        return si_n, "N"   # force display not yet configurable

    def length(self, si_m: float) -> tuple[float, str]:
        """Length uses altitude_unit by default (m / ft)."""
        u = self._settings.altitude_unit
        return UnitConverter.altitude_to_display(si_m, u), u.value

    # ── Dimensionless / ratio (pass-through) ──────────────────────────────

    @staticmethod
    def ratio(value: float) -> tuple[float, str]:
        return value, "—"

    # ── Wing loading (N/m² or lbf/ft²) ───────────────────────────────────

    def wing_loading(self, si_nm2: float) -> tuple[float, str]:
        """Convert wing loading N/m² to display units."""
        area_u = self._settings.area_unit
        if area_u == AreaUnit.FT2:
            # Convert N/m² → lbf/ft²
            val = si_nm2 * 0.020_885_4  # 1 N/m² = 0.0208854 lbf/ft²
            return val, "lbf/ft²"
        return si_nm2, "N/m²"

    # ── Power loading (N/W → depends on power unit) ──────────────────────

    def power_loading(self, si_nw: float) -> tuple[float, str]:
        """Power loading N/W stays as-is; unit label reflects power unit."""
        pu = self._settings.power_unit
        if pu == PowerUnit.HP:
            # N/W → lbf/hp (multiply by 745.7/4.448)
            return si_nw * 167.573, "lbf/hp"
        if pu == PowerUnit.KW:
            return si_nw * 1000.0, "N/kW"
        return si_nw, "N/W"

    # ── Convenience: formatted string ─────────────────────────────────────

    @staticmethod
    def fmt(val: float, label: str, decimals: int = 2) -> str:
        """Return 'value unit' string, e.g. '32.12 kg'."""
        return f"{val:.{decimals}f} {label}"
