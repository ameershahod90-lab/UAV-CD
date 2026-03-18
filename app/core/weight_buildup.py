"""
Weight Buildup Engine — UAV-CD-APP
=====================================
Iterative converged takeoff-weight estimation using the Breguet /
energy-fraction method.

Methodology (Sadraey Ch.4, Raymer Ch.3):
  1. Guess W_TO.
  2. Compute empty weight fraction W_E/W_TO from regression.
  3. Compute fuel/battery fraction W_F/W_TO (Breguet for fuel,
     energy-density for battery).
  4. Compute W_TO = W_payload / (1 - W_E/W_TO - W_F/W_TO).
  5. Iterate until |ΔW_TO| / W_TO < tolerance.

All inputs/outputs in SI units.
"""

from __future__ import annotations

import math
from typing import Final

from app.core.atmosphere import AtmosphereModel
from app.core.entities import DesignBrief, RegressionCoeffs, WeightResult
from app.core.enums import PropulsionType

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_G:            Final[float] = 9.806_65  # Gravitational acceleration [m/s²]
_MIN_W_TO:     Final[float] = 0.05      # [kg] — prevents degenerate iterations
_INITIAL_GUESS_FACTOR: Final[float] = 5.0  # Initial W_TO = factor * payload


# ---------------------------------------------------------------------------
# Fuel/Battery fraction strategies  (Strategy pattern)
# ---------------------------------------------------------------------------

class _FuelFractionStrategy:
    """Abstract strategy for computing the energy-source weight fraction."""

    def compute(
        self,
        brief: DesignBrief,
        w_to_kg: float,
    ) -> float:
        """Return W_energy / W_TO  [-]."""
        raise NotImplementedError


class _ElectricStrategy(_FuelFractionStrategy):
    """
    Electric propulsion — battery weight fraction.

    E = P * t = (T * V / η) * t   →   m_bat = E / (e_bat * η_bat)

    where:
      T   = thrust required  ≈ W_TO * C_D0 / C_L at cruise
      e_bat = battery energy density [Wh/kg] → converted to J/kg
      η_bat = battery discharge efficiency
    """

    def compute(self, brief: DesignBrief, w_to_kg: float) -> float:
        atm = AtmosphereModel.at_altitude(brief.cruise_altitude_m)
        # Approximate L/D at cruise (Raymer eq. 3.22 simplified)
        k: float = 1.0 / (math.pi * brief.oswald_efficiency * brief.aspect_ratio)
        cl_cruise: float = math.sqrt(brief.c_d0 / k)  # CL at best L/D
        l_d: float = cl_cruise / (brief.c_d0 + k * cl_cruise ** 2)

        # Power required [W]  P = W * V / (L/D) / η_prop
        power_w: float = (
            w_to_kg * _G * brief.cruise_speed_ms
            / (l_d * brief.prop_efficiency)
        )

        # Energy [J] = power * endurance
        endurance_s: float = brief.endurance_hr * 3_600.0
        energy_j: float = power_w * endurance_s

        # Battery mass [kg] = Energy / (e_specific [J/kg] * η_bat)
        e_j_per_kg: float = brief.battery_energy_density_wh_kg * 3_600.0
        m_battery_kg: float = energy_j / (e_j_per_kg * brief.battery_efficiency)
        fraction: float = m_battery_kg / w_to_kg
        return max(0.0, min(fraction, 0.95))


class _ICEngineStrategy(_FuelFractionStrategy):
    """
    Internal combustion (Piston / Turboprop) — fuel weight fraction.
    Uses Breguet range equation (mass-fraction form):
        W_f/W_0 = 1 - exp(- R * g * SFC / (η_prop * L/D))

    SFC here is in g/(W·h) which must be converted to kg/(W·s).
    """

    def compute(self, brief: DesignBrief, w_to_kg: float) -> float:
        k: float = 1.0 / (math.pi * brief.oswald_efficiency * brief.aspect_ratio)
        cl_cruise = math.sqrt(brief.c_d0 / k)
        l_d: float = cl_cruise / (brief.c_d0 + k * cl_cruise ** 2)

        range_m: float = brief.range_km * 1_000.0
        # SFC [g/(W·h)] → [kg/(W·s)]  ÷ (1e3 * 3600)
        sfc_si: float = brief.specific_fuel_consumption_g_wh / 3_600_000.0

        # Breguet (propeller form): W_f/W_0 = 1 - exp(-R * SFC * g / (η * L_D))
        exponent: float = (
            range_m * sfc_si * _G
            / (brief.prop_efficiency * l_d)
        )
        fraction: float = 1.0 - math.exp(-exponent)
        return max(0.0, min(fraction, 0.95))


class _HybridStrategy(_FuelFractionStrategy):
    """
    Hybrid: electric for loiter, fuel for transit.
    Simplified as weighted sum of electric + ICE fractions.
    """

    def __init__(self) -> None:
        self._electric = _ElectricStrategy()
        self._ice = _ICEngineStrategy()

    def compute(self, brief: DesignBrief, w_to_kg: float) -> float:
        f_elec = self._electric.compute(brief, w_to_kg) * 0.4
        f_fuel = self._ice.compute(brief, w_to_kg) * 0.6
        return min(f_elec + f_fuel, 0.95)


_STRATEGY_MAP: dict[PropulsionType, _FuelFractionStrategy] = {
    PropulsionType.ELECTRIC:  _ElectricStrategy(),
    PropulsionType.PISTON:    _ICEngineStrategy(),
    PropulsionType.TURBOPROP: _ICEngineStrategy(),
    PropulsionType.TURBOJET: _ICEngineStrategy(),
    PropulsionType.HYBRID:    _HybridStrategy(),
}


# ---------------------------------------------------------------------------
# Weight Buildup Engine
# ---------------------------------------------------------------------------

class WeightBuildupEngine:
    """
    Iterative converged takeoff-weight estimator.

    Usage::

        engine = WeightBuildupEngine(tolerance=0.001, max_iterations=200)
        result = engine.solve(brief, coefficients)
    """

    def __init__(
        self,
        tolerance: float = 0.001,
        max_iterations: int = 100,
    ) -> None:
        self._tolerance: float = tolerance
        self._max_iterations: int = max_iterations

    def solve(
        self,
        brief: DesignBrief,
        coefficients: RegressionCoeffs,
    ) -> WeightResult:
        """
        Run the W_TO convergence loop.

        Parameters
        ----------
        brief:
            Mission requirements (payload, speeds, propulsion, etc.).
        coefficients:
            Regression coefficients for empty weight fraction from the
            applicable classification range.

        Returns
        -------
        WeightResult
            Full breakdown with convergence history.
        """
        strategy: _FuelFractionStrategy = _STRATEGY_MAP[brief.propulsion_type]
        w_payload: float = brief.payload_mass_kg

        # Initial guess
        w_to: float = max(
            w_payload * _INITIAL_GUESS_FACTOR, _MIN_W_TO
        )

        history: list[float] = [w_to]
        converged: bool = False

        for iteration in range(1, self._max_iterations + 1):
            # 1. Empty weight fraction from linear regression
            ewf: float = (
                coefficients.we_a * w_to + coefficients.we_b
            )
            ewf = max(0.05, min(ewf, 0.95))

            # 2. Fuel / battery fraction
            ff: float = strategy.compute(brief, w_to)

            # 3. New W_TO estimate
            denom: float = 1.0 - ewf - ff
            if denom <= 0.01:
                # Degenerate: payload fraction too small to converge
                denom = 0.01
            w_to_new: float = w_payload / denom

            history.append(w_to_new)

            # 4. Convergence check
            rel_change: float = abs(w_to_new - w_to) / max(w_to, 1e-9)
            w_to = w_to_new

            if rel_change < self._tolerance:
                converged = True
                break

        # Derived quantities
        ewf_final = coefficients.we_a * w_to + coefficients.we_b
        ewf_final = max(0.05, min(ewf_final, 0.95))
        ff_final = strategy.compute(brief, w_to)

        w_empty: float = ewf_final * w_to
        w_fuel_bat: float = ff_final * w_to

        return WeightResult(
            w_to_kg=w_to,
            w_empty_kg=w_empty,
            w_fuel_or_battery_kg=w_fuel_bat,
            w_payload_kg=w_payload,
            empty_weight_fraction=ewf_final,
            fuel_battery_fraction=ff_final,
            iterations=len(history) - 1,
            converged=converged,
            convergence_history=tuple(history),
        )
