"""
Regression Engine — UAV-CD-APP
================================
Pure statistical functions operating on lists of UavRecord objects.

Design:
  - Every function is stateless (no class state, no globals).
  - numpy is used for linear algebra; scipy.optimize for curve fitting.
  - All inputs/outputs are plain Python dicts / tuples — no pandas frames.
  - Minimum sample threshold: MIN_SAMPLES (default 5). Below this the
    caller should use textbook fallbacks.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
from scipy.optimize import curve_fit  # type: ignore[import-untyped]

from app.core.database import UavRecord
from app.core.entities import FieldStatistics, RegressionCoeffs
from app.core.enums import DataSource


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_SAMPLES: int = 5  # Regression below this count is statistically unreliable


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_xy(
    records: list[UavRecord],
    x_field: str,
    y_field: str,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Extract paired (x, y) arrays of floats from *records*, dropping any
    record where either field is None or non-positive.
    """
    xs: list[float] = []
    ys: list[float] = []
    for r in records:
        x = getattr(r, x_field, None)
        y = getattr(r, y_field, None)
        if x is not None and y is not None and x > 0 and y > 0:
            xs.append(x)
            ys.append(y)
    return np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)


def _r_squared(y: np.ndarray, y_pred: np.ndarray) -> float:
    """Coefficient of determination R²."""
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    if ss_tot < 1e-12:
        return 0.0
    return max(0.0, 1.0 - ss_res / ss_tot)


# ---------------------------------------------------------------------------
# Public regression functions
# ---------------------------------------------------------------------------

def fit_linear(
    x: np.ndarray,
    y: np.ndarray,
) -> tuple[float, float, float]:
    """
    Fit y = a*x + b to data using least-squares.

    Returns
    -------
    tuple (a, b, r2)
    """
    if len(x) < 2:
        return 0.0, float(np.mean(y)) if len(y) else 0.0, 0.0
    coeffs = np.polyfit(x, y, 1)
    a, b = float(coeffs[0]), float(coeffs[1])
    y_pred = a * x + b
    r2 = _r_squared(y, y_pred)
    return a, b, r2


def _power_law(x: np.ndarray, c: float, e: float) -> np.ndarray:
    """Model: y = c * x^e."""
    return c * np.power(x, e)


def fit_power_law(
    x: np.ndarray,
    y: np.ndarray,
    p0: tuple[float, float] = (1.0, 0.333),
) -> tuple[float, float, float]:
    """
    Fit y = c * x^e using non-linear least squares (scipy curve_fit).

    Parameters
    ----------
    x: Independent variable array (must be > 0).
    y: Dependent variable array (must be > 0).
    p0: Initial guess for (c, e).

    Returns
    -------
    tuple (c, e, r2)
    """
    if len(x) < MIN_SAMPLES:
        return p0[0], p0[1], 0.0
    try:
        popt, _ = curve_fit(
            _power_law, x, y, p0=list(p0), maxfev=5000,
            bounds=([1e-6, -5.0], [1e6, 5.0]),
        )
        c, e = float(popt[0]), float(popt[1])
        r2 = _r_squared(y, _power_law(x, c, e))
        return c, e, r2
    except (RuntimeError, ValueError):
        # If fitting fails, fall back to log-linearised least-squares
        log_x = np.log(x)
        log_y = np.log(y)
        a_log, b_log, r2 = fit_linear(log_x, log_y)
        c = math.exp(b_log)
        e = a_log
        return c, e, max(0.0, r2)


def fit_empty_weight_fraction(
    records: list[UavRecord],
) -> tuple[float, float, float]:
    """
    Fit the linear empty-weight-fraction model:
        W_E / W_TO = a * W_TO + b

    Parameters
    ----------
    records: List of UavRecord with non-None mtow_kg and enough entries.

    Returns
    -------
    tuple (a, b, r2)
        a: slope [1/kg], b: intercept [-]
    """
    ewf_pairs: list[tuple[float, float]] = []
    for r in records:
        if r.mtow_kg is None or r.payload_kg is None:
            continue
        if r.mtow_kg <= 0:
            continue
        # Empty weight = MTOW - payload (structure + propulsion, no fuel term
        # for sizing loop — fuel is computed separately)
        w_empty_approx = r.mtow_kg - r.payload_kg
        if w_empty_approx <= 0:
            continue
        ewf = w_empty_approx / r.mtow_kg
        if 0 < ewf < 1:
            ewf_pairs.append((r.mtow_kg, ewf))

    if len(ewf_pairs) < MIN_SAMPLES:
        return 0.0, 0.6, 0.0

    x = np.asarray([p[0] for p in ewf_pairs], dtype=float)
    y = np.asarray([p[1] for p in ewf_pairs], dtype=float)
    return fit_linear(x, y)


def fit_wingspan_scaling(
    records: list[UavRecord],
) -> tuple[float, float, float]:
    """
    Fit power law: b = c * m^e  [m vs kg].
    Returns (c, e, r2).
    """
    x, y = _extract_xy(records, "mtow_kg", "wingspan_m")
    if len(x) < MIN_SAMPLES:
        return 1.10, 0.333, 0.0
    return fit_power_law(x, y, p0=(1.10, 0.333))


def fit_wing_area_scaling(
    records: list[UavRecord],
) -> tuple[float, float, float]:
    """
    Fit power law: S = c * m^e  [m² vs kg].
    Returns (c, e, r2).
    """
    x, y = _extract_xy(records, "mtow_kg", "wing_area_m2")
    if len(x) < MIN_SAMPLES:
        return 0.16, 0.667, 0.0
    return fit_power_law(x, y, p0=(0.16, 0.667))


def compute_regression_coeffs(
    class_name: str,
    records: list[UavRecord],
) -> RegressionCoeffs:
    """
    Compute full RegressionCoeffs for *class_name* from *records*.
    If insufficient data, returns textbook fallbacks.
    """
    from app.core.coefficients import get_closest_textbook

    mtow_records = [r for r in records if r.mtow_kg is not None]

    if len(mtow_records) < MIN_SAMPLES:
        midpoint: Optional[float] = None
        if mtow_records:
            vals = [r.mtow_kg for r in mtow_records if r.mtow_kg]
            midpoint = float(np.median(vals)) if vals else None
        return get_closest_textbook(class_name, midpoint)

    we_a, we_b, we_r2 = fit_empty_weight_fraction(mtow_records)
    b_coeff, b_exp, b_r2 = fit_wingspan_scaling(mtow_records)
    s_coeff, s_exp, s_r2 = fit_wing_area_scaling(mtow_records)

    return RegressionCoeffs(
        class_name=class_name,
        we_a=we_a, we_b=we_b, we_r2=we_r2,
        b_coeff=b_coeff, b_exp=b_exp, b_r2=b_r2,
        s_coeff=s_coeff, s_exp=s_exp, s_r2=s_r2,
        sample_count=len(mtow_records),
        data_source=DataSource.DATABASE,
    )


# ---------------------------------------------------------------------------
# Descriptive statistics
# ---------------------------------------------------------------------------

def compute_statistics(
    records: list[UavRecord],
    field_name: str,
    class_name: str,
) -> Optional[FieldStatistics]:
    """
    Compute descriptive statistics for *field_name* across *records*.
    Returns None when fewer than 2 values are available.
    """
    from app.core.entities import FieldStatistics

    values: list[float] = [
        getattr(r, field_name)
        for r in records
        if getattr(r, field_name, None) is not None
    ]

    if len(values) < 2:
        return None

    arr = np.asarray(values, dtype=float)
    return FieldStatistics(
        field_name=field_name,
        class_name=class_name,
        count=int(len(arr)),
        mean=float(np.mean(arr)),
        std=float(np.std(arr, ddof=1)),
        minimum=float(np.min(arr)),
        maximum=float(np.max(arr)),
        median=float(np.median(arr)),
    )
