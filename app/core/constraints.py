"""
Constraint Analysis Engine — UAV-CD-APP
=========================================
Computes the five fundamental performance constraint boundaries in the
Wing Loading (W/S) vs Power Loading (W/P) or Thrust Loading (T/W) space.

Constraints implemented (Sadraey §2.9, Eq. 2.38–2.47):
  1. Stall speed          → maximum W/S vertical boundary       (Eq. 2.38)
  2. Maximum level speed  → W/P or T/W as function of W/S       (Eq. 2.39–2.40)
  3. Takeoff ground roll  → W/P or T/W as function of W/S       (Eq. 2.41–2.42)
  4. Rate of climb        → W/P or T/W as function of W/S       (Eq. 2.43–2.44)
  5. Service ceiling      → W/P or T/W as function of W/S       (Eq. 2.45–2.46)

Wing sizing (Eq. 2.49):  S   = W_TO / (W/S)_d
Engine sizing (Eq. 2.50–2.51):
  Prop: P = W_TO / (W/P)_d
  Jet:  T = (T/W)_d × W_TO

All inputs in SI units (m, s, kg, N, W).
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
_N_WS: Final[int]   = 150       # Number of W/S samples per curve

# Runway friction coefficients (Sadraey Table 2.2)
_MU_PAVED:    Final[float] = 0.04   # Concrete / asphalt
_MU_GRASS:    Final[float] = 0.07
_MU_DIRT:     Final[float] = 0.10

# ROC at service ceiling (Sadraey §2.9 — FAA UAV convention)
_ROC_CEIL: Final[float] = 0.508   # m/s  (100 ft/min)

# Plot colours — readable on both light and dark themes
_COLOR_STALL:   Final[str] = "#e74c3c"  # red
_COLOR_VMAX:    Final[str] = "#e67e22"  # orange
_COLOR_TAKEOFF: Final[str] = "#f1c40f"  # yellow
_COLOR_CLIMB:   Final[str] = "#2ecc71"  # green
_COLOR_CEILING: Final[str] = "#3498db"  # blue

# Tolerance for feasibility checks (5 % margin on constraint boundary)
_INFEASIBLE_MARGIN: Final[float] = 0.05


# ---------------------------------------------------------------------------
# Constraint Analyzer
# ---------------------------------------------------------------------------

class ConstraintAnalyzer:
    """
    Computes all constraint curves for the matching diagram.

    Equations follow Sadraey (2020) §2.9, Eq. 2.38–2.47.
    All intermediate variables computed in SI; display conversion done in UI.
    """

    def __init__(
        self,
        brief: DesignBrief,
        weight_result: WeightResult,
    ) -> None:
        self._brief  = brief
        self._weight = weight_result

        b = brief
        # Induced drag factor k = 1/(π e AR)
        self._k: float = 1.0 / (math.pi * b.oswald_efficiency * b.aspect_ratio)
        # Maximum lift-to-drag ratio: LD_max = 1 / (2 √(CD0 k))
        self._ld_max: float = (
            1.0 / (2.0 * math.sqrt(b.c_d0 * self._k))
            if b.c_d0 * self._k > 1e-12 else 20.0
        )

        self._rho_sl:      float = AtmosphereModel.density_at(0.0)
        self._rho_cruise:  float = AtmosphereModel.density_at(b.cruise_altitude_m)
        self._rho_ceiling: float = AtmosphereModel.density_at(b.service_ceiling_m)
        # Density ratio at service ceiling σ_C = ρ_ceiling / ρ_SL
        self._sigma_c: float = self._rho_ceiling / self._rho_sl
        self._is_power_mode: bool = brief.propulsion_type.is_power_mode

    # ── Public API ─────────────────────────────────────────────────────────

    def analyze(self) -> ConstraintResult:
        """Compute all constraints and return the full ConstraintResult."""
        ws_max = self._stall_ws() * 2.5
        ws_arr = np.linspace(50.0, ws_max, _N_WS)

        curves = [
            self._vmax_curve(ws_arr),
            self._takeoff_curve(ws_arr),
            self._climb_curve(ws_arr),
            self._ceiling_curve(ws_arr),
        ]

        # Pre-flight violation check at estimated design point
        violations = self._detect_violations(ws_arr)

        return ConstraintResult(
            stall_ws_nm2=self._stall_ws(),
            curves=tuple(curves),
            ws_range=tuple(float(v) for v in ws_arr),
            is_power_loading_mode=self._is_power_mode,
            violations=tuple(violations),
        )

    def check_design_point(
        self,
        ws_nm2: float,
        loading: float,
        constraint_result: ConstraintResult,
    ) -> list[ConstraintViolation]:
        """
        Evaluate whether the given (W/S, W/P or T/W) design point
        violates any constraint.

        Called each time the user clicks a new design point on the plot.
        Returns a (possibly empty) list of ConstraintViolation objects.
        """
        violations: list[ConstraintViolation] = []
        is_power = constraint_result.is_power_loading_mode
        ws_arr = np.asarray(constraint_result.ws_range, dtype=float)

        # 1. Stall: W/S must not exceed stall limit
        stall_limit = constraint_result.stall_ws_nm2
        if ws_nm2 > stall_limit * (1.0 + _INFEASIBLE_MARGIN):
            violations.append(ConstraintViolation(
                constraint_name="Stall",
                description=(
                    f"W/S = {ws_nm2:.0f} N/m² exceeds stall limit "
                    f"{stall_limit:.0f} N/m².  Reduce wing loading."
                ),
                severity=ConstraintSeverity.ERROR,
                current_value=ws_nm2,
                limit_value=stall_limit,
                unit="N/m²",
            ))

        # 2. Check each performance-curve constraint
        for curve in constraint_result.curves:
            curve_ws = np.asarray(curve.wing_loading_values, dtype=float)
            curve_ld = np.asarray(curve.loading_values, dtype=float)

            # Interpolate constraint boundary at the clicked W/S
            if ws_nm2 < curve_ws.min() or ws_nm2 > curve_ws.max():
                continue
            boundary_loading = float(np.interp(ws_nm2, curve_ws, curve_ld))
            if boundary_loading <= 0:
                continue

            if is_power:
                # For power loading (W/P): higher is better for the UAV.
                # Constraint lines represent the MINIMUM required W/P
                # (maximum allowable power consumption) — actually for W/P
                # the design must be BELOW the constraint curve in the
                # feasible region (the feasible region is under the lower
                # envelope). A point is infeasible if loading > boundary:
                # i.e., the engine is too weak (too high W/P = too little P).
                #
                # Exception: the stall constraint is handled separately above.
                #
                # For W/P: feasible means loading <= boundary_loading (NOT above it)
                # Because W/P constraint gives _upper_ bound on W/P:
                # You need enough power → W/P must be BELOW the line
                # (i.e., actual W/P ≤ constraint W/P → engine is strong enough).
                if loading > boundary_loading * (1.0 + _INFEASIBLE_MARGIN):
                    diff_pct = (loading - boundary_loading) / boundary_loading * 100
                    violations.append(ConstraintViolation(
                        constraint_name=curve.name,
                        description=(
                            f"{curve.name}: W/P = {loading:.5f} N/W "
                            f"exceeds constraint limit {boundary_loading:.5f} N/W "
                            f"(+{diff_pct:.1f}% — engine under-powered)."
                        ),
                        severity=ConstraintSeverity.ERROR,
                        current_value=loading,
                        limit_value=boundary_loading,
                        unit="N/W",
                    ))
            else:
                # T/W mode: feasible means T/W >= boundary (enough thrust)
                if loading < boundary_loading * (1.0 - _INFEASIBLE_MARGIN):
                    diff_pct = (boundary_loading - loading) / boundary_loading * 100
                    violations.append(ConstraintViolation(
                        constraint_name=curve.name,
                        description=(
                            f"{curve.name}: T/W = {loading:.4f} is below "
                            f"required {boundary_loading:.4f} "
                            f"(-{diff_pct:.1f}% — insufficient thrust)."
                        ),
                        severity=ConstraintSeverity.ERROR,
                        current_value=loading,
                        limit_value=boundary_loading,
                        unit="N/N",
                    ))

        return violations

    # ── Stall (Eq. 2.38) ─────────────────────────────────────────────────

    def _stall_ws(self) -> float:
        """
        Stall constraint (Eq. 2.38):
            (W/S)_Vs = ½ ρ₀ V_s² C_Lmax
        """
        b = self._brief
        return 0.5 * self._rho_sl * b.stall_speed_ms ** 2 * b.c_l_max

    # ── Maximum speed (Eq. 2.39 / 2.40) ─────────────────────────────────

    def _vmax_curve(self, ws: np.ndarray) -> ConstraintCurve:
        """
        Maximum speed constraint (Sadraey Eq. 2.39 / 2.40).

        Prop (Eq. 2.40):
            W/P = η_p / [½ρ₀σ V_max³ C_D0/(W/S) + 2K(W/S)/(ρ₀σ V_max)]
                = η_p / (T/W × V_max)

        Jet (Eq. 2.39):
            T/W = ½ρ₀σ V_max² C_D0 / (W/S) + 2K(W/S) / (ρ₀σ V_max²)

        Note: Sadraey Eq 2.39/2.40 use ρ₀σ (not ρ_cruise directly), but
        ρ₀σ ≡ ρ_cruise by definition, so using ρ_cruise is equivalent.
        """
        b   = self._brief
        rho = self._rho_cruise   # ρ = ρ₀ σ at cruise altitude
        k   = self._k
        v   = b.max_speed_ms
        q   = 0.5 * rho * v ** 2

        loading = np.empty_like(ws)
        for i, ws_i in enumerate(ws):
            tw = q * b.c_d0 / ws_i + k * ws_i / q   # T/W (Eq. 2.39)
            if self._is_power_mode:
                loading[i] = b.prop_efficiency / tw   # W/P = η_p / (T/W) (Eq. 2.40)
            else:
                loading[i] = tw

        return ConstraintCurve(
            name="Max Speed",
            color_hex=_COLOR_VMAX,
            wing_loading_values=tuple(float(v) for v in ws),
            loading_values=tuple(float(v) for v in loading),
        )

    # ── Takeoff ground roll (Eq. 2.41 / 2.42) ───────────────────────────

    def _takeoff_curve(self, ws: np.ndarray) -> ConstraintCurve:
        """
        Takeoff ground roll constraint (Sadraey §2.9, Eq. 2.41 / 2.42).

        Key terms:
            V_TO   = 1.1 V_s          (typical takeoff speed)
            C_L_TO = C_Lmax / 1.21    (lift coefficient at rotation ≈ C_Lmax/1.21)
            C_D_G  = C_D0 - μ C_L_TO  (ground drag: induced drag near zero on ground)
                      (Sadraey's formulation uses C_D_TO, approximated as C_D0)

        Prop (Eq. 2.42):
            χ      = exp(0.6 ρ g C_D_G S_TO / (W/S))
            W/P    = η_p / V_TO × (1 - χ) / [μ(1-χ) - (C_D_G/C_L_TO)χ]
              where μ = ground friction coefficient

        Jet (Eq. 2.41):
            T/W    = [μ - (μ + C_D_G/C_L_TO) χ] / (1 - χ)
        """
        b     = self._brief
        rho   = self._rho_sl
        mu    = _MU_PAVED
        v_to  = b.stall_speed_ms * 1.1
        c_l_r = b.c_l_max / 1.21           # C_L at rotation
        c_d_g = b.c_d0 - mu * c_l_r        # Ground drag coefficient
        s_to  = max(b.takeoff_run_m, 5.0)  # Safety clamp

        # Pre-compute 0.6 ρ g C_D_G S_TO  (scalar factor in exponent)
        exp_factor = 0.6 * rho * _G * abs(c_d_g) * s_to
        # Keep C_D_G sign-correct (can be negative if high CL)
        c_d_g_signed = c_d_g

        loading = np.empty_like(ws)
        for i, ws_i in enumerate(ws):
            exponent = exp_factor / max(ws_i, 1.0)
            χ = math.exp(-min(exponent, 30.0))   # clamp to avoid overflow; note sign

            # Denominator must be non-zero; handle carefully
            denom_ratio = c_d_g_signed / max(c_l_r, 0.01)

            if self._is_power_mode:
                # Eq. 2.42 — note: the expo sign in Sadraey reads correctly as:
                # numerator = (1 - χ), denominator = μ(1-χ) - (CD_G/CL_R)χ
                numer = 1.0 - χ
                denom = mu * (1.0 - χ) - denom_ratio * χ
                if abs(denom) < 1e-8:
                    loading[i] = 0.001
                else:
                    loading[i] = max(b.prop_efficiency * numer / (v_to * denom), 0.001)
            else:
                # Eq. 2.41
                numer = mu - (mu + denom_ratio) * χ
                denom = 1.0 - χ
                if abs(denom) < 1e-8:
                    loading[i] = 0.001
                else:
                    tw = numer / denom
                    loading[i] = max(tw, 0.001)

        return ConstraintCurve(
            name="Takeoff Run",
            color_hex=_COLOR_TAKEOFF,
            wing_loading_values=tuple(float(v) for v in ws),
            loading_values=tuple(float(v) for v in loading),
        )

    # ── Rate of climb (Eq. 2.43 / 2.44) ────────────────────────────────

    def _climb_curve(self, ws: np.ndarray) -> ConstraintCurve:
        """
        Rate-of-climb constraint at sea level (Sadraey §2.9, Eq. 2.43 / 2.44).

        Prop (Eq. 2.44):
            W/P = 1 / (ROC/η_p + √[2(W/S)/(ρ√(3 CD0/K))] × 1.155/(LD_max η_p))

        Jet (Eq. 2.43):
            V_md = √[2(W/S)/(ρ√(CD0/K))]   ← speed at max L/D
            T/W  = ROC/V_md + 1/LD_max

        Key difference vs previous implementation:
            Previous used simplified ROC/V_cl + CD/CL at an arbitrary V_cl.
            Sadraey Eq. 2.44 uses √(3 CD0/K) (speed at max power excess)
            and the 1.155/LD_max coefficient.
        """
        b    = self._brief
        rho  = self._rho_sl
        k    = self._k
        ld   = self._ld_max
        roc  = b.rate_of_climb_ms

        loading = np.empty_like(ws)
        for i, ws_i in enumerate(ws):
            if self._is_power_mode:
                # Prop: speed at max power excess = √(2(W/S)/(ρ√(3 CD0/K)))
                v_mp = math.sqrt(2.0 * ws_i / (rho * math.sqrt(3.0 * b.c_d0 / k)))
                # Eq. 2.44
                loading[i] = 1.0 / (
                    roc / b.prop_efficiency
                    + v_mp * 1.155 / (ld * b.prop_efficiency)
                )
            else:
                # Jet: speed at max L/D = √(2(W/S)/(ρ√(CD0/K)))
                v_md = math.sqrt(2.0 * ws_i / (rho * math.sqrt(b.c_d0 / k)))
                # Eq. 2.43
                loading[i] = roc / v_md + 1.0 / ld

        return ConstraintCurve(
            name="Rate of Climb",
            color_hex=_COLOR_CLIMB,
            wing_loading_values=tuple(float(v) for v in ws),
            loading_values=tuple(float(v) for v in loading),
        )

    # ── Service ceiling (Eq. 2.45 / 2.46) ───────────────────────────────

    def _ceiling_curve(self, ws: np.ndarray) -> ConstraintCurve:
        """
        Service ceiling constraint (Sadraey §2.9, Eq. 2.45 / 2.46).

        At service ceiling, ROC drops to 0.508 m/s (100 ft/min).

        Prop (Eq. 2.46):
            W/P_SL = σ_C / (ROC_C/η_p + √[2(W/S)/(ρ_C√(3 CD0/K))] × 1.155/(LD_max η_p))

        Jet (Eq. 2.45):
            V_md_C = √[2(W/S)/(ρ_C√(CD0/K))]
            T_SL/W = ROC_C/(σ_C V_md_C) + 1/(σ_C LD_max)

        Key difference vs previous: σ_C (density ratio) scaling was missing.
        """
        b     = self._brief
        rho_c = self._rho_ceiling
        sigma = self._sigma_c         # σ_C = ρ_ceiling / ρ_SL
        k     = self._k
        ld    = self._ld_max
        roc_c = _ROC_CEIL             # 0.508 m/s at service ceiling

        loading = np.empty_like(ws)
        for i, ws_i in enumerate(ws):
            if self._is_power_mode:
                # Prop (Eq. 2.46): sea-level power basis with σ_C factor
                v_mp_c = math.sqrt(2.0 * ws_i / (rho_c * math.sqrt(3.0 * b.c_d0 / k)))
                loading[i] = sigma / (
                    roc_c / b.prop_efficiency
                    + v_mp_c * 1.155 / (ld * b.prop_efficiency)
                )
            else:
                # Jet (Eq. 2.45): T_SL/W at ceiling
                v_md_c = math.sqrt(2.0 * ws_i / (rho_c * math.sqrt(b.c_d0 / k)))
                loading[i] = roc_c / (sigma * v_md_c) + 1.0 / (sigma * ld)

        return ConstraintCurve(
            name="Service Ceiling",
            color_hex=_COLOR_CEILING,
            wing_loading_values=tuple(float(v) for v in ws),
            loading_values=tuple(float(v) for v in loading),
        )

    # ── Pre-flight violation check (run after weight result) ─────────────

    def _detect_violations(
        self, ws_arr: np.ndarray
    ) -> list[ConstraintViolation]:
        """
        Quick sanity check at the estimated optimal design point
        (run during the full sizing pipeline).
        Detailed per-click checking is in check_design_point().
        """
        violations: list[ConstraintViolation] = []

        # Estimate design W/S ≈ 95 % of stall limit
        approx_ws = self._stall_ws() * 0.95
        stall_limit = self._stall_ws()

        if approx_ws > stall_limit:
            violations.append(ConstraintViolation(
                constraint_name="Stall",
                description=(
                    f"Estimated W/S ({approx_ws:.0f} N/m²) "
                    f"exceeds stall limit ({stall_limit:.0f} N/m²)."
                ),
                severity=ConstraintSeverity.ERROR,
                current_value=approx_ws,
                limit_value=stall_limit,
                unit="N/m²",
            ))

        return violations
