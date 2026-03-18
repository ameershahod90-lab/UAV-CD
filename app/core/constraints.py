"""
Constraint Analysis Engine — UAV-CD-APP
=========================================
Computes the five fundamental performance constraint boundaries in the
Wing Loading (W/S) vs Power Loading (W/P) or Thrust Loading (T/W) space.

Constraints implemented:
  1. Stall speed          → maximum W/S (vertical boundary)
  2. Maximum level speed  → W/P (or T/W) as function of W/S
  3. Takeoff ground roll  → W/P as function of W/S
  4. Rate of climb        → W/P as function of W/S
  5. Service ceiling      → W/P as function of W/S

References:
  - Sadraey (2020) Ch.3 — Constraint Analysis
  - Raymer (2018) Ch.5 — Constraint Analysis for UAVs
  - Anderson (2017) — Introduction to Flight

All inputs in SI units.
All outputs in SI units (N/m², N/W for power loading or N/N for T/W).
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np

from app.core.atmosphere import AtmosphereModel
from app.core.entities import (
    ConstraintCurve,
    ConstraintResult,
    ConstraintViolation,
    DesignBrief,
    WeightResult,
)
from app.core.enums import ConstraintSeverity, PropulsionType

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_G:    Final[float] = 9.806_65
_N_WS: Final[int]   = 150       # Number of W/S samples for each curve

# Plot colours — chosen to be readable on both light and dark themes
_COLOR_STALL:   Final[str] = "#e74c3c"   # red
_COLOR_VMAX:    Final[str] = "#e67e22"   # orange
_COLOR_TAKEOFF: Final[str] = "#f1c40f"   # yellow
_COLOR_CLIMB:   Final[str] = "#2ecc71"   # green
_COLOR_CEILING: Final[str] = "#3498db"   # blue


# ---------------------------------------------------------------------------
# Constraint Analyzer
# ---------------------------------------------------------------------------

class ConstraintAnalyzer:
    """
    Computes all constraint curves for the matching diagram.

    Instantiate once per brief; call ``analyze()`` to get results.
    """

    def __init__(
        self,
        brief: DesignBrief,
        weight_result: WeightResult,
    ) -> None:
        self._brief: DesignBrief = brief
        self._weight: WeightResult = weight_result

        # Pre-compute frequently used derived quantities
        b = brief
        self._k: float = 1.0 / (math.pi * b.oswald_efficiency * b.aspect_ratio)
        self._rho_sl: float = AtmosphereModel.density_at(0.0)
        self._rho_cruise: float = AtmosphereModel.density_at(b.cruise_altitude_m)
        self._rho_ceiling: float = AtmosphereModel.density_at(b.service_ceiling_m)
        self._is_power_mode: bool = brief.propulsion_type.is_power_mode

    # ── Public API ───────────────────────────────────────────────────────

    def analyze(self) -> ConstraintResult:
        """Compute all constraints and return the full ConstraintResult."""
        b = self._brief

        # W/S axis in [N/m²]
        ws_max: float = self._stall_ws() * 2.5
        ws_arr: np.ndarray = np.linspace(50.0, ws_max, _N_WS)

        curves: list[ConstraintCurve] = [
            self._vmax_curve(ws_arr),
            self._takeoff_curve(ws_arr),
            self._climb_curve(ws_arr),
            self._ceiling_curve(ws_arr),
        ]

        violations = self._detect_violations(ws_arr)

        return ConstraintResult(
            stall_ws_nm2=self._stall_ws(),
            curves=tuple(curves),
            ws_range=tuple(float(v) for v in ws_arr),
            is_power_loading_mode=self._is_power_mode,
            violations=tuple(violations),
        )

    # ── Stall ────────────────────────────────────────────────────────────

    def _stall_ws(self) -> float:
        """
        Stall constraint: maximum wing loading.
        W/S ≤ ½ρ₀ V_stall² C_Lmax
        """
        b = self._brief
        return 0.5 * self._rho_sl * b.stall_speed_ms ** 2 * b.c_l_max

    # ── Maximum speed ────────────────────────────────────────────────────

    def _vmax_curve(self, ws: np.ndarray) -> ConstraintCurve:
        """
        Maximum speed constraint.
        Power loading: W/P = η_p * ρ_cruise * V_max / (q_max * C_D0 / (W/S) + (W/S) / (q_max * π e AR))
        Thrust loading: T/W = q * C_D0 / (W/S) + (W/S) / (q * π e AR)
        """
        b = self._brief
        q_max: float = 0.5 * self._rho_cruise * b.max_speed_ms ** 2

        cd0 = b.c_d0
        k = self._k

        loading = np.zeros_like(ws)
        for i, ws_val in enumerate(ws):
            tw: float = q_max * cd0 / ws_val + k * ws_val / q_max
            if self._is_power_mode:
                loading[i] = b.prop_efficiency * b.max_speed_ms / tw / b.max_speed_ms
                # Simplify: W/P = η_p / (T/W * V_max) * V_max = η_p / (T/W)
                loading[i] = b.prop_efficiency / tw
            else:
                loading[i] = tw

        return ConstraintCurve(
            name="Max Speed",
            color_hex=_COLOR_VMAX,
            wing_loading_values=tuple(float(v) for v in ws),
            loading_values=tuple(float(v) for v in loading),
        )

    # ── Takeoff ground roll ──────────────────────────────────────────────

    def _takeoff_curve(self, ws: np.ndarray) -> ConstraintCurve:
        """
        Takeoff ground roll constraint (Sadraey §3.4).
        Approximation: T/W = 0.5*ρ*V_TO²*C_L_TO / (W/S) + μ*(1 - 0.5*ρ*V_TO²*C_L_TO/(W/S))
        + W_S / (ρ*g*s_TO*C_L_TO) for propeller case.

        Simplified: W/P = η_p / (T/W)  for power-loading mode.
        """
        b = self._brief
        v_to: float = b.stall_speed_ms * 1.1   # Typical V_TO = 1.1 * V_s
        q_to: float = 0.5 * self._rho_sl * v_to ** 2
        c_l_to: float = b.c_l_max / 1.21       # CL at takeoff (not max)
        s_to: float = b.takeoff_run_m
        mu: float = 0.04                        # Rolling friction coefficient (paved)

        loading = np.zeros_like(ws)
        for i, ws_val in enumerate(ws):
            # T/W required for ground roll (from energy balance, Raymer eq. 17.100)
            tw = (
                ws_val / (self._rho_sl * _G * s_to * c_l_to)
                + _G * q_to * b.c_d0 / ws_val
                + mu * (1.0 - q_to * c_l_to / ws_val)
            )
            tw = max(tw, 0.001)
            if self._is_power_mode:
                loading[i] = b.prop_efficiency / tw
            else:
                loading[i] = tw

        return ConstraintCurve(
            name="Takeoff Run",
            color_hex=_COLOR_TAKEOFF,
            wing_loading_values=tuple(float(v) for v in ws),
            loading_values=tuple(float(v) for v in loading),
        )

    # ── Rate of climb ────────────────────────────────────────────────────

    def _climb_curve(self, ws: np.ndarray) -> ConstraintCurve:
        """
        Rate-of-climb constraint (sea level, full power).
        W/P = η_p / (ROC/V_climb + C_D/C_L)
        where C_L is chosen for max L/D speed.
        """
        b = self._brief
        roc: float = b.rate_of_climb_ms
        k = self._k
        # Climbing speed ≈ best L/D speed
        v_cl: float = max(b.stall_speed_ms, b.cruise_speed_ms * 0.8)
        q_cl: float = 0.5 * self._rho_sl * v_cl ** 2

        loading = np.zeros_like(ws)
        for i, ws_val in enumerate(ws):
            cl: float = ws_val / q_cl
            cd: float = b.c_d0 + k * cl ** 2
            if self._is_power_mode:
                # W/P = η_p * V / (ROC * V + D * V / W)
                # Simplify: W/P = η_p / (ROC/V + cd/cl)
                loading[i] = b.prop_efficiency / (roc / v_cl + cd / cl)
            else:
                loading[i] = roc / v_cl + cd / cl

        return ConstraintCurve(
            name="Rate of Climb",
            color_hex=_COLOR_CLIMB,
            wing_loading_values=tuple(float(v) for v in ws),
            loading_values=tuple(float(v) for v in loading),
        )

    # ── Service ceiling ──────────────────────────────────────────────────

    def _ceiling_curve(self, ws: np.ndarray) -> ConstraintCurve:
        """
        Service ceiling constraint.
        At service ceiling the ROC drops to 0.508 m/s (100 fpm).
        Same formula as climb but at ceiling density and ROC = 0.508 m/s.
        """
        b = self._brief
        roc_ceil: float = 0.508
        k = self._k
        v_cl: float = max(b.stall_speed_ms, b.cruise_speed_ms * 0.7)
        q_cl: float = 0.5 * self._rho_ceiling * v_cl ** 2

        loading = np.zeros_like(ws)
        for i, ws_val in enumerate(ws):
            cl: float = ws_val / max(q_cl, 0.001)
            cd: float = b.c_d0 + k * cl ** 2
            if self._is_power_mode:
                loading[i] = b.prop_efficiency / (roc_ceil / v_cl + cd / cl)
            else:
                loading[i] = roc_ceil / v_cl + cd / cl

        return ConstraintCurve(
            name="Service Ceiling",
            color_hex=_COLOR_CEILING,
            wing_loading_values=tuple(float(v) for v in ws),
            loading_values=tuple(float(v) for v in loading),
        )

    # ── Violation detection ──────────────────────────────────────────────

    def _detect_violations(
        self,
        ws_arr: np.ndarray,
    ) -> list[ConstraintViolation]:
        """
        Check if the estimated design W/S would violate any constraints.
        Called after weight result is available.
        """
        violations: list[ConstraintViolation] = []

        w_to_n: float = self._weight.w_to_kg * _G
        # Approximate optimal W/S as 80 % of stall limit
        approx_ws: float = self._stall_ws() * 0.80

        stall_limit = self._stall_ws()
        if approx_ws > stall_limit:
            violations.append(ConstraintViolation(
                constraint_name="Stall",
                description=(
                    f"Design W/S ({approx_ws:.0f} N/m²) exceeds "
                    f"stall limit ({stall_limit:.0f} N/m²)."
                ),
                severity=ConstraintSeverity.ERROR,
                current_value=approx_ws,
                limit_value=stall_limit,
                unit="N/m²",
            ))

        return violations
