"""
Design Point Finder & Scaling Law Sanity Checks — UAV-CD-APP
=============================================================
Locates the optimal design point on the matching diagram and
derives wing geometry. Performs sanity checks against historical
scaling laws from the DSTO/Raymer databases.

Methodology:
  - The optimal point is at the intersection of the most restrictive
    constraints in the feasible region.
  - For electric/piston props the ordinate is W/P [N/W];
    for turboprop/jet it is T/W [N/N].
  - W/S is selected as the maximum feasible value (closest to stall limit)
    to minimise wing area.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np

from app.core.atmosphere import AtmosphereModel
from app.core.entities import (
    ConstraintResult,
    DesignBrief,
    DesignPoint,
    RegressionCoeffs,
    SanityCheck,
    WeightResult,
)
from app.core.enums import SanityCheckStatus

_G: Final[float] = 9.806_65


# ---------------------------------------------------------------------------
# Design Point Finder
# ---------------------------------------------------------------------------

class DesignPointFinder:
    """
    Determines the optimal design point (W/S*, W/P* or T/W*) from the
    constraint result and derives wing geometry.
    """

    def find(
        self,
        brief: DesignBrief,
        weight_result: WeightResult,
        constraint_result: ConstraintResult,
        regression_coeffs: RegressionCoeffs,
    ) -> DesignPoint:
        """
        Locate the optimal design point and return a frozen DesignPoint.

        The optimal wing loading is the largest W/S that lies within the
        feasible region (i.e., to the left of the stall line and above
        all constraint curves — which, for power loading, means below).
        """
        ws_arr = np.asarray(constraint_result.ws_range, dtype=float)

        # ── Stall limit: only consider W/S < stall limit ─────────────────
        stall_limit: float = constraint_result.stall_ws_nm2
        feasible_mask = ws_arr < stall_limit * 0.98   # 2 % margin

        if not np.any(feasible_mask):
            # Emergency fallback: use 80 % of stall limit
            ws_star: float = stall_limit * 0.80
        else:
            # Among feasible W/S values, choose the maximum (smallest wing)
            ws_star = float(np.max(ws_arr[feasible_mask]))

        # ── Derive loading at the chosen W/S ─────────────────────────────
        loading_star: float = self._envelope_loading(
            ws_star, constraint_result
        )

        # ── Derive wing geometry ──────────────────────────────────────────
        w_to_kg = weight_result.w_to_kg
        w_to_n  = w_to_kg * _G

        wing_area_m2: float = w_to_n / ws_star

        aspect_ratio: float = brief.aspect_ratio
        wingspan_m: float = math.sqrt(aspect_ratio * wing_area_m2)

        # Engine power or thrust from loading
        if constraint_result.is_power_loading_mode:
            # W/P = N/W → P = W / (W/P)
            engine_power_w: float = w_to_n / loading_star
        else:
            # T/W → T = T/W * W
            engine_power_w = loading_star * w_to_n  # T [N] stored in engine_power_w

        # ── Sanity checks ─────────────────────────────────────────────────
        sanity_checker = ScalingLawChecker()
        checks = sanity_checker.check_all(
            w_to_kg=w_to_kg,
            wingspan_m=wingspan_m,
            wing_area_m2=wing_area_m2,
            regression_coeffs=regression_coeffs,
        )

        return DesignPoint(
            wing_loading_nm2=ws_star,
            power_loading_nw=loading_star,
            w_to_kg=w_to_kg,
            wing_area_m2=wing_area_m2,
            wingspan_m=wingspan_m,
            aspect_ratio=aspect_ratio,
            engine_power_w=engine_power_w,
            sanity_checks=tuple(checks),
        )

    # ── Internal ─────────────────────────────────────────────────────────

    @staticmethod
    def _envelope_loading(
        ws: float,
        constraint_result: ConstraintResult,
    ) -> float:
        """
        Interpolate the most-restrictive constraint loading at given W/S.
        For power-loading mode (W/P) the minimum loading is most restrictive.
        For thrust-loading (T/W) the maximum is most restrictive.
        """
        ws_arr = np.asarray(constraint_result.ws_range, dtype=float)
        is_power = constraint_result.is_power_loading_mode

        all_loadings: list[float] = []
        for curve in constraint_result.curves:
            loading_arr = np.asarray(curve.loading_values, dtype=float)
            val = float(np.interp(ws, ws_arr, loading_arr))
            if val > 0:
                all_loadings.append(val)

        if not all_loadings:
            return 0.05  # fallback

        return min(all_loadings) if is_power else max(all_loadings)


# ---------------------------------------------------------------------------
# Scaling Law Sanity Checker
# ---------------------------------------------------------------------------

class ScalingLawChecker:
    """
    Compares computed wing geometry against historical scaling laws.

    Pass bands:
      ±25 % → SanityCheckStatus.PASS  (green)
      ±50 % → SanityCheckStatus.WARN  (yellow)
      > ±50% → SanityCheckStatus.FAIL (red)

    Scaling laws (DSTO TN-1601, Sadraey (2020)):
      Wingspan: b     = b_coeff * m_kg ^ b_exp  [m]  (≈ 1.10 * m^{1/3})
      Wing area: S    = s_coeff * m_kg ^ s_exp  [m²] (≈ 0.16 * m^{2/3})
    """

    _WARN_BAND: Final[float] = 0.25   # ±25 %
    _FAIL_BAND: Final[float] = 0.50   # ±50 %

    def check_all(
        self,
        w_to_kg: float,
        wingspan_m: float,
        wing_area_m2: float,
        regression_coeffs: RegressionCoeffs,
    ) -> list[SanityCheck]:
        checks: list[SanityCheck] = []

        checks.append(self._check_wingspan(
            w_to_kg, wingspan_m, regression_coeffs
        ))
        checks.append(self._check_wing_area(
            w_to_kg, wing_area_m2, regression_coeffs
        ))

        return checks

    def _check_wingspan(
        self,
        m_kg: float,
        b_computed: float,
        rc: RegressionCoeffs,
    ) -> SanityCheck:
        b_expected = rc.b_coeff * (m_kg ** rc.b_exp)
        status = self._band_status(b_computed, b_expected)
        return SanityCheck(
            parameter_name="Wingspan",
            computed_value=b_computed,
            expected_value=b_expected,
            band_low=b_expected * (1.0 - self._WARN_BAND),
            band_high=b_expected * (1.0 + self._WARN_BAND),
            status=status,
            unit="m",
        )

    def _check_wing_area(
        self,
        m_kg: float,
        s_computed: float,
        rc: RegressionCoeffs,
    ) -> SanityCheck:
        s_expected = rc.s_coeff * (m_kg ** rc.s_exp)
        status = self._band_status(s_computed, s_expected)
        return SanityCheck(
            parameter_name="Wing Area",
            computed_value=s_computed,
            expected_value=s_expected,
            band_low=s_expected * (1.0 - self._WARN_BAND),
            band_high=s_expected * (1.0 + self._WARN_BAND),
            status=status,
            unit="m²",
        )

    def _band_status(self, computed: float, expected: float) -> SanityCheckStatus:
        if expected < 1e-9:
            return SanityCheckStatus.WARN
        deviation = abs(computed - expected) / expected
        if deviation <= self._WARN_BAND:
            return SanityCheckStatus.PASS
        if deviation <= self._FAIL_BAND:
            return SanityCheckStatus.WARN
        return SanityCheckStatus.FAIL
