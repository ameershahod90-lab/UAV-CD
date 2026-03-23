"""
Weight Buildup Engine — UAV-CD-APP
=====================================
Iterative converged takeoff-weight estimation using Sadraey §2.6-2.7
per-segment weight-fraction methodology.

Methodology (Sadraey §2.6 — Figure 2.2 standard mission profile):
  1. Guess W_TO.
  2. Compute empty weight fraction W_E/W_TO from historical regression.
  3. Compute the total fuel/battery fraction by multiplying ALL per-segment
     weight ratios W_i/W_{i-1} across enabled segments.
  4. Compute W_TO = W_payload / (1 - W_E/W_TO - W_F/W_TO).
  5. Iterate until |ΔW_TO| / W_TO < tolerance.

Per-segment weight fractions (Sadraey Table 2.4):
  ─────────────────────────────────────────────────────
  Segment     Piston/Turboprop   Jet/Hydraulic
  ─────────────────────────────────────────────────────
  Takeoff          0.970              0.990
  Climb            0.985              0.990
  Descent          0.990              0.990
  Landing          0.992              0.992
  ─────────────────────────────────────────────────────
  Cruise: Breguet propeller  exp(-R * SFC * g / (η * L/D))
  Loiter: Breguet endurance  exp(-E * SFC * g * V / (η * L/D))
  ─────────────────────────────────────────────────────

For Electric UAVs (§2.7):
  Total energy = Σ P_i * t_i for all segments.
  Fixed segments (takeoff, climb, descent, landing) have a power factor
  relative to cruise power.  W_bat = E_total / (e_bat * η_bat).

For Hybrid UAVs: each segment is tagged FUEL or BATTERY; the appropriate
calculation method is used per-tag and fractions accumulated separately.

CL_cruise calculation:
  CL* = sqrt(CD0 / k)  where k = 1/(π·e·AR)
  This is the CL that minimises drag and therefore maximises L/D (best L/D
  point).  All Breguet calculations assume the UAV flies at this optimum.
  L/D_max = CL* / (2·CD0)  (standard polar identity).

All inputs/outputs in SI units.
"""

from __future__ import annotations

import math
from typing import Final

from app.core.atmosphere import AtmosphereModel
from app.core.entities import (
    CruiseMissionSegment,
    DesignBrief,
    LoiterMissionSegment,
    MissionSegment,
    RegressionCoeffs,
    SegmentFractionResult,
    WeightResult,
)
from app.core.enums import EnergySource, PropulsionType, SegmentType


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_G: Final[float] = 9.806_65        # Gravitational acceleration [m/s²]
_MIN_W_TO: Final[float] = 0.05     # [kg] — prevents degenerate iterations
_INITIAL_GUESS_FACTOR: Final[float] = 5.0  # W_TO_guess = factor * W_payload

# Sadraey Table 2.4 — fixed segment weight fractions (W_i / W_{i-1})
_FIXED_FRACTION_PISTON:  Final[dict[SegmentType, float]] = {
    SegmentType.TAKEOFF: 0.970,
    SegmentType.CLIMB:   0.985,
    SegmentType.DESCENT: 0.990,
    SegmentType.LANDING: 0.992,
}
_FIXED_FRACTION_JET: Final[dict[SegmentType, float]] = {
    SegmentType.TAKEOFF: 0.990,
    SegmentType.CLIMB:   0.990,
    SegmentType.DESCENT: 0.990,
    SegmentType.LANDING: 0.992,
}

# Electric power factors relative to cruise power (per segment type)
# Used to estimate the power draw during non-cruise fixed phases.
_ELECTRIC_POWER_FACTOR: Final[dict[SegmentType, float]] = {
    SegmentType.TAKEOFF: 1.6,   # Higher power during takeoff run
    SegmentType.CLIMB:   1.3,   # Climb power > cruise
    SegmentType.DESCENT: 0.5,   # Reduced power during descent
    SegmentType.LANDING: 0.4,   # Low power on approach
}
# Approximate times for fixed electric phases [seconds] (generic UAV estimates)
_ELECTRIC_PHASE_TIME_S: Final[dict[SegmentType, float]] = {
    SegmentType.TAKEOFF: 60.0,
    SegmentType.CLIMB:   300.0,
    SegmentType.DESCENT: 240.0,
    SegmentType.LANDING: 60.0,
}


# ---------------------------------------------------------------------------
# Aerodynamic helpers (shared)
# ---------------------------------------------------------------------------

class _AeroParams:
    """
    Pre-computed aerodynamic parameters for Breguet calculations.
    Uses the best-L/D CL (Sadraey §2.4) as cruise reference.
    """

    __slots__ = ("k", "cl_cruise", "ld_max")

    def __init__(self, brief: DesignBrief) -> None:
        self.k: float = 1.0 / (math.pi * brief.oswald_efficiency * brief.aspect_ratio)
        # CL* = sqrt(CD0 / k) → maximises L/D
        self.cl_cruise: float = math.sqrt(brief.c_d0 / self.k)
        # L/D_max = CL* / (CD0 + k·CL*²) = CL* / (2·CD0)
        self.ld_max: float = self.cl_cruise / (2.0 * brief.c_d0)


# ---------------------------------------------------------------------------
# Per-segment fraction calculators
# ---------------------------------------------------------------------------

class _SegmentCalculator:
    """Computes W_i / W_{i-1} for a single segment and energy source."""

    def __init__(self, brief: DesignBrief, aero: _AeroParams) -> None:
        self._brief = brief
        self._aero = aero

        # SFC [g/(W·h)] → [kg/(W·s)]
        self._sfc_si: float = (
            brief.specific_fuel_consumption_g_wh / 3_600_000.0
        )
        self._is_jet: bool = brief.propulsion_type is PropulsionType.TURBOJET

        # Battery specific energy [J/kg]
        self._e_bat_j_per_kg: float = (
            brief.battery_energy_density_wh_kg * 3_600.0
        )

    # ── Fixed segments (fuel) ──────────────────────────────────────────────

    def fixed_fuel_fraction(self, seg_type: SegmentType) -> float:
        """Return Sadraey Table 2.4 fixed fraction for a fuel-powered segment."""
        table = _FIXED_FRACTION_JET if self._is_jet else _FIXED_FRACTION_PISTON
        return table.get(seg_type, 1.0)

    # ── Cruise (Range) — fuel Breguet propeller ────────────────────────────

    def cruise_fuel_fraction(self, seg: CruiseMissionSegment) -> float:
        """
        Breguet range (propeller form, Sadraey eq. 2.20):
            W_i/W_{i-1} = exp( -R · SFC · g / (η · L/D) )
        """
        range_m = seg.range_km * 1_000.0
        exponent = (
            range_m * self._sfc_si * _G
            / (self._brief.prop_efficiency * self._aero.ld_max)
        )
        return math.exp(-exponent)

    # ── Loiter (Endurance) — fuel Breguet endurance ───────────────────────

    def loiter_fuel_fraction(self, seg: LoiterMissionSegment) -> float:
        """
        Breguet endurance (propeller form, Sadraey eq. 2.25):
            W_i/W_{i-1} = exp( -E · SFC · g · V / (η · L/D) )
        where E is in seconds and V is cruise speed [m/s].
        """
        endurance_s = seg.endurance_hr * 3_600.0
        exponent = (
            endurance_s
            * self._sfc_si
            * _G
            * self._brief.cruise_speed_ms
            / (self._brief.prop_efficiency * self._aero.ld_max)
        )
        return math.exp(-exponent)

    # ── Cruise (Range) — electric energy budget ────────────────────────────

    def cruise_electric_energy_j(
        self,
        seg: CruiseMissionSegment,
        cruise_power_w: float,
    ) -> float:
        """Energy [J] for a cruise segment at constant cruise power."""
        range_m = seg.range_km * 1_000.0
        time_s = range_m / max(self._brief.cruise_speed_ms, 0.1)
        return cruise_power_w * time_s

    # ── Loiter (Endurance) — electric energy budget ───────────────────────

    def loiter_electric_energy_j(
        self,
        seg: LoiterMissionSegment,
        cruise_power_w: float,
    ) -> float:
        """Energy [J] for a loiter segment (same power assumption as cruise)."""
        endurance_s = seg.endurance_hr * 3_600.0
        return cruise_power_w * endurance_s

    # ── Fixed segment — electric energy budget ────────────────────────────

    def fixed_electric_energy_j(
        self,
        seg_type: SegmentType,
        cruise_power_w: float,
    ) -> float:
        """Energy [J] for a fixed electric phase (takeoff, climb, etc.)."""
        factor = _ELECTRIC_POWER_FACTOR.get(seg_type, 1.0)
        time_s = _ELECTRIC_PHASE_TIME_S.get(seg_type, 0.0)
        return cruise_power_w * factor * time_s


# ---------------------------------------------------------------------------
# Main weight fraction computer
# ---------------------------------------------------------------------------

class _MissionFractionComputer:
    """
    Computes total fuel and battery weight fractions from all mission segments.

    Returns:
        (fuel_fraction, battery_fraction, segment_results)
    """

    def __init__(
        self,
        brief: DesignBrief,
        aero: _AeroParams,
        w_to_kg: float,
    ) -> None:
        self._brief = brief
        self._aero = aero
        self._w_to_kg = w_to_kg
        self._calc = _SegmentCalculator(brief, aero)

    def compute(self) -> tuple[float, float, list[SegmentFractionResult]]:
        """
        Returns (fuel_fraction, battery_fraction, segment_results).
        Both fractions are normalised by w_to_kg.
        """
        segments = self._brief.normalised_segments()

        # For fuel: running product of W_i / W_{i-1}  (starts at W_TO)
        fuel_product: float = 1.0
        # For electric: accumulated energy [J]
        battery_energy_j: float = 0.0

        cruise_power_w = self._estimate_cruise_power()

        results: list[SegmentFractionResult] = []
        running_weight = self._w_to_kg

        for seg in segments:
            seg_type = seg.segment_type
            source = seg.energy_source

            if source is EnergySource.FUEL:
                ratio = self._fuel_ratio(seg, seg_type)
                fuel_product *= ratio
                running_weight *= ratio
                results.append(SegmentFractionResult(
                    segment_label=seg.label,
                    segment_type=seg_type,
                    energy_source=source,
                    weight_fraction=ratio,
                    cumulative_weight_kg=running_weight,
                ))

            else:  # BATTERY
                energy_j = self._battery_energy(seg, seg_type, cruise_power_w)
                battery_energy_j += energy_j
                # Placeholder weight fraction: will be resolved after total energy known
                results.append(SegmentFractionResult(
                    segment_label=seg.label,
                    segment_type=seg_type,
                    energy_source=source,
                    weight_fraction=float("nan"),   # filled below
                    cumulative_weight_kg=running_weight,
                ))

        # Fuel fraction (Sadraey eq. 2.19): W_fuel/W_TO = 1 - ∏(W_i/W_{i-1})
        fuel_fraction = 1.0 - fuel_product
        fuel_fraction = max(0.0, min(fuel_fraction, 0.90))

        # Battery fraction from total energy budget
        e_bat = self._brief.battery_energy_density_wh_kg * 3_600.0  # [J/kg]
        eta_bat = max(self._brief.battery_efficiency, 0.01)
        m_bat_kg = battery_energy_j / (e_bat * eta_bat)
        bat_fraction = m_bat_kg / max(self._w_to_kg, 0.001)
        bat_fraction = max(0.0, min(bat_fraction, 0.90))

        # Fill in nan weight_fractions for battery segments proportionally
        n_bat = sum(1 for r in results if math.isnan(r.weight_fraction))
        if n_bat > 0:
            per_seg_bat = bat_fraction / n_bat
            filled: list[SegmentFractionResult] = []
            for r in results:
                if math.isnan(r.weight_fraction):
                    filled.append(SegmentFractionResult(
                        segment_label=r.segment_label,
                        segment_type=r.segment_type,
                        energy_source=r.energy_source,
                        weight_fraction=1.0 - per_seg_bat,
                        cumulative_weight_kg=r.cumulative_weight_kg,
                    ))
                else:
                    filled.append(r)
            results = filled

        return fuel_fraction, bat_fraction, results

    # ── Helpers ───────────────────────────────────────────────────────────

    def _estimate_cruise_power(self) -> float:
        """Approximate cruise shaft power [W] = W·V / (L/D·η)."""
        return (
            self._w_to_kg * _G * self._brief.cruise_speed_ms
            / (self._aero.ld_max * max(self._brief.prop_efficiency, 0.01))
        )

    def _fuel_ratio(self, seg: MissionSegment, seg_type: SegmentType) -> float:
        if isinstance(seg, CruiseMissionSegment):
            return self._calc.cruise_fuel_fraction(seg)
        if isinstance(seg, LoiterMissionSegment):
            return self._calc.loiter_fuel_fraction(seg)
        # Fixed segment
        return self._calc.fixed_fuel_fraction(seg_type)

    def _battery_energy(
        self,
        seg: MissionSegment,
        seg_type: SegmentType,
        cruise_power_w: float,
    ) -> float:
        if isinstance(seg, CruiseMissionSegment):
            return self._calc.cruise_electric_energy_j(seg, cruise_power_w)
        if isinstance(seg, LoiterMissionSegment):
            return self._calc.loiter_electric_energy_j(seg, cruise_power_w)
        return self._calc.fixed_electric_energy_j(seg_type, cruise_power_w)


# ---------------------------------------------------------------------------
# Weight Buildup Engine (public API)
# ---------------------------------------------------------------------------

class WeightBuildupEngine:
    """
    Iterative converged takeoff-weight estimator — Sadraey §2.6-2.7.

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
            Mission requirements + segments + aero coefficients.
        coefficients:
            Regression coefficients for empty weight fraction from the
            applicable classification range.

        Returns
        -------
        WeightResult
            Full breakdown with segment fractions and convergence history.
        """
        aero = _AeroParams(brief)
        w_payload = brief.payload_mass_kg

        # Initial guess
        w_to: float = max(w_payload * _INITIAL_GUESS_FACTOR, _MIN_W_TO)
        history: list[float] = [w_to]
        converged = False

        for _ in range(1, self._max_iterations + 1):
            # 1. Empty weight fraction (linear regression)
            ewf = coefficients.we_a * w_to + coefficients.we_b
            ewf = max(0.05, min(ewf, 0.90))

            # 2. Mission fractions (per-segment)
            computer = _MissionFractionComputer(brief, aero, w_to)
            fuel_ff, bat_ff, _ = computer.compute()
            ff = min(fuel_ff + bat_ff, 0.90)

            # 3. New W_TO estimate
            denom = max(1.0 - ewf - ff, 0.01)
            w_to_new = w_payload / denom

            history.append(w_to_new)

            rel_change = abs(w_to_new - w_to) / max(w_to, 1e-9)
            w_to = w_to_new

            if rel_change < self._tolerance:
                converged = True
                break

        # Final pass for detailed results
        ewf_final = max(0.05, min(coefficients.we_a * w_to + coefficients.we_b, 0.90))
        computer_final = _MissionFractionComputer(brief, aero, w_to)
        fuel_ff_f, bat_ff_f, seg_results = computer_final.compute()
        ff_final = min(fuel_ff_f + bat_ff_f, 0.90)

        w_empty = ewf_final * w_to
        w_fuel_bat = ff_final * w_to

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
            segment_fractions=tuple(seg_results),
            cl_cruise=aero.cl_cruise,
            ld_max=aero.ld_max,
        )
