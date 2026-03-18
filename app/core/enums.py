"""
Core Enumerations — UAV-CD-APP
================================
All app-wide enumerations live here. Zero external dependencies.
Every enum includes human-readable labels for UI display.
"""

from __future__ import annotations

from enum import Enum


# ---------------------------------------------------------------------------
# Propulsion
# ---------------------------------------------------------------------------

class PropulsionType(Enum):
    """Primary propulsion category, drives fuel-vs-battery fraction logic."""

    ELECTRIC = "Electric"
    PISTON = "Piston"
    TURBOPROP = "Turboprop"
    HYBRID = "Hybrid"
    TURBOJET = "Turbojet"

    @property
    def label(self) -> str:
        return self.value

    @property
    def is_electric(self) -> bool:
        return self in (PropulsionType.ELECTRIC, PropulsionType.HYBRID)

    @property
    def uses_fuel(self) -> bool:
        return self in (PropulsionType.PISTON, PropulsionType.TURBOPROP, PropulsionType.HYBRID, PropulsionType.TURBOJET)

    @property
    def is_power_mode(self) -> bool:
        return self in (PropulsionType.ELECTRIC, PropulsionType.PISTON, PropulsionType.TURBOPROP, PropulsionType.HYBRID)
    
    @property
    def power_source(self) -> str:
        return 'FUEL + BATTERY' if (self.is_electric and self.uses_fuel) else ('FUEL' if self.uses_fuel else 'BATTERY')

# ---------------------------------------------------------------------------
# Unit System Enums
# ---------------------------------------------------------------------------

class UnitSystem(Enum):
    METRIC = "Metric"
    IMPERIAL = "Imperial"


class SpeedUnit(Enum):
    MS = "m/s"
    KMH = "km/h"
    KNOTS = "knots"
    FTS = "ft/s"


class AltitudeUnit(Enum):
    METERS = "m"
    FEET = "ft"


class MassUnit(Enum):
    KG = "kg"
    LB = "lb"


class AreaUnit(Enum):
    M2 = "m²"
    FT2 = "ft²"


class PowerUnit(Enum):
    WATT = "W"
    KW = "kW"
    HP = "hp"


class ForceUnit(Enum):
    NEWTON = "N"
    LBF = "lbf"


class LengthUnit(Enum):
    METERS = "m"
    FEET = "ft"
    INCHES = "in"


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

class ThemeOption(Enum):
    LIGHT = "light"
    DARK = "dark"


# ---------------------------------------------------------------------------
# Analysis / Plot
# ---------------------------------------------------------------------------

class ScaleType(Enum):
    """Axis scale for scatter plots in Historical Data tab."""
    LINEAR = "Linear"
    LOG = "Log"


class ConstraintSeverity(Enum):
    """Severity of a constraint violation."""
    WARNING = "warning"
    ERROR = "error"


class SanityCheckStatus(Enum):
    """Result of a scaling-law sanity check."""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class DataSource(Enum):
    """Origin of regression coefficients."""
    DATABASE = "From historical database"
    TEXTBOOK = "Textbook fallback (insufficient data)"
