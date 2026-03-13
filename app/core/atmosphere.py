"""
ISA Standard Atmosphere Model — UAV-CD-APP
============================================
ICAO International Standard Atmosphere (ISA) implementation.

Covers the troposphere (0–11 000 m) only, which is sufficient for all
UAV classes in Phase 1. The stratosphere layer is included for the
service-ceiling constraint (some MALE/HALE UAVs cruise above 11 km).

Reference: ICAO Doc 7488-CD, "Manual of the ICAO Standard Atmosphere"

All outputs are in SI units.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# ISA constants
# ---------------------------------------------------------------------------

_T0:     float = 288.15    # Sea-level temperature [K]
_P0:     float = 101_325.0 # Sea-level pressure [Pa]
_RHO0:   float = 1.225     # Sea-level density [kg/m³]
_LAPSE:  float = 0.006_5   # Troposphere lapse rate [K/m]
_G:      float = 9.806_65  # Standard gravity [m/s²]
_R:      float = 287.058   # Specific gas constant for dry air [J/(kg·K)]
_GAMMA:  float = 1.4       # Ratio of specific heats [-]

_T_TROP: float = 216.65    # Temperature at tropopause (11 000 m) [K]
_P_TROP: float = 22_632.1  # Pressure at tropopause [Pa]
_H_TROP: float = 11_000.0  # Tropopause altitude [m]


# ---------------------------------------------------------------------------
# Result value object
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AtmosphereState:
    """
    ISA atmosphere properties at a given altitude.
    All values in SI units.
    """

    altitude_m: float       # Geopotential altitude [m]
    temperature_k: float    # Static temperature [K]
    pressure_pa: float      # Static pressure [Pa]
    density_kg_m3: float    # Air density ρ [kg/m³]
    speed_of_sound_ms: float  # Speed of sound a [m/s]

    @property
    def temperature_c(self) -> float:
        """Temperature in degrees Celsius."""
        return self.temperature_k - 273.15

    @property
    def dynamic_pressure_pa(self) -> float:
        """
        Dynamic pressure q = ½ρV² is NOT available here without airspeed.
        Use AtmosphereModel.dynamic_pressure(h, V) instead.
        """
        raise NotImplementedError(
            "Use AtmosphereModel.dynamic_pressure(altitude_m, speed_ms) "
            "to compute q."
        )


# ---------------------------------------------------------------------------
# Atmosphere model — stateless, class-method API
# ---------------------------------------------------------------------------

class AtmosphereModel:
    """
    ICAO ISA standard atmosphere calculator.

    All methods are pure functions (no mutable state).
    Thread-safe by design.
    """

    @classmethod
    def at_altitude(cls, altitude_m: float) -> AtmosphereState:
        """
        Compute ISA atmospheric state at *altitude_m* geopotential altitude.

        Parameters
        ----------
        altitude_m:
            Geopotential altitude in metres. Clamped to [-500, 25 000] m.

        Returns
        -------
        AtmosphereState
            Atmospheric properties at the given altitude.
        """
        h: float = max(-500.0, min(altitude_m, 25_000.0))

        if h <= _H_TROP:
            # Troposphere: temperature decreases linearly
            T: float = _T0 - _LAPSE * h
            P: float = _P0 * (T / _T0) ** (_G / (_LAPSE * _R))
        else:
            # Lower stratosphere: isothermal (T = constant = 216.65 K)
            T = _T_TROP
            P = _P_TROP * math.exp(-_G * (h - _H_TROP) / (_R * _T_TROP))

        rho: float = P / (_R * T)
        a:   float = math.sqrt(_GAMMA * _R * T)

        return AtmosphereState(
            altitude_m=h,
            temperature_k=T,
            pressure_pa=P,
            density_kg_m3=rho,
            speed_of_sound_ms=a,
        )

    @classmethod
    def density_at(cls, altitude_m: float) -> float:
        """Convenience: return air density [kg/m³] at *altitude_m*."""
        return cls.at_altitude(altitude_m).density_kg_m3

    @classmethod
    def dynamic_pressure(cls, altitude_m: float, speed_ms: float) -> float:
        """
        Compute dynamic pressure q = ½ρV² [Pa].

        Parameters
        ----------
        altitude_m: Altitude in metres.
        speed_ms:   True airspeed in m/s.
        """
        rho: float = cls.density_at(altitude_m)
        return 0.5 * rho * speed_ms ** 2

    @classmethod
    def sea_level(cls) -> AtmosphereState:
        """Convenience: return ISA sea-level conditions."""
        return cls.at_altitude(0.0)
