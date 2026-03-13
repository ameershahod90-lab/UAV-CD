"""
Textbook Fallback Coefficients — UAV-CD-APP
=============================================
When the historical database has insufficient samples (< 5) for a given
classification range, these textbook values are used instead.

Sources:
  - Sadraey, M.H. (2020). Design of Unmanned Aerial Systems. Wiley.
  - Raymer, D.P. (2018). Aircraft Design: A Conceptual Approach, 6th Ed.
  - Roskam, J. (2005). Airplane Design, Parts I–VIII.
  - DSTO TN-1601 (2014). Palmer, J.L. — UAS Database Analysis.
  - Keane, A.J., Sobester, A., Scanlan, J.P. (2017). Small Unmanned
    Fixed-Wing Aircraft Design. Wiley.

Coefficients are keyed by class name (string) matching ClassificationRange.name.
At startup, DatabaseService maps each user range onto the closest textbook
class by MTOW midpoint when no exact-name match is found.
"""

from __future__ import annotations

from app.core.entities import RegressionCoeffs
from app.core.enums import DataSource


# ---------------------------------------------------------------------------
# Default classification names (must match classification_tab defaults)
# ---------------------------------------------------------------------------

CLASS_MICRO_MINI = "Micro/Mini"   # 0–25 kg
CLASS_SMALL      = "Small"        # 25–150 kg
CLASS_MEDIUM     = "Medium"       # 150–1500 kg
CLASS_LARGE      = "Large"        # 1500+ kg


# ---------------------------------------------------------------------------
# Textbook coefficient table
# ---------------------------------------------------------------------------

TEXTBOOK_COEFFICIENTS: dict[str, RegressionCoeffs] = {

    CLASS_MICRO_MINI: RegressionCoeffs(
        class_name=CLASS_MICRO_MINI,
        # Empty weight fraction: W_E/W_TO = we_a * W_TO + we_b
        # Fitted to small electric UAV data (Sadraey Table 4.4, Roskam I)
        we_a=-0.001_5, we_b=0.65,
        # Wingspan scaling: b ≈ 1.10 * m_kg^(1/3) [m]   (DSTO TN-1601)
        b_coeff=1.10, b_exp=0.333,
        # Wing area scaling: S ≈ 0.16 * m_kg^(2/3) [m²]  (DSTO TN-1601)
        s_coeff=0.16, s_exp=0.667,
        sample_count=0,
        data_source=DataSource.TEXTBOOK,
    ),

    CLASS_SMALL: RegressionCoeffs(
        class_name=CLASS_SMALL,
        # Slightly heavier structure fraction for 25–150 kg range
        we_a=-0.000_8, we_b=0.60,
        b_coeff=1.10, b_exp=0.333,
        s_coeff=0.16, s_exp=0.667,
        sample_count=0,
        data_source=DataSource.TEXTBOOK,
    ),

    CLASS_MEDIUM: RegressionCoeffs(
        class_name=CLASS_MEDIUM,
        # Medium UAVs: more capable propulsion, heavier structure ratio
        # Raymer Table 3.1 (jet-powered UAV approximation)
        we_a=-0.000_3, we_b=0.55,
        b_coeff=1.10, b_exp=0.333,
        s_coeff=0.16, s_exp=0.667,
        sample_count=0,
        data_source=DataSource.TEXTBOOK,
    ),

    CLASS_LARGE: RegressionCoeffs(
        class_name=CLASS_LARGE,
        # MALE-class approximation (Predator-like)
        we_a=-0.000_1, we_b=0.50,
        b_coeff=1.10, b_exp=0.333,
        s_coeff=0.16, s_exp=0.667,
        sample_count=0,
        data_source=DataSource.TEXTBOOK,
    ),
}


def get_closest_textbook(
    class_name: str,
    mtow_midpoint_kg: float | None = None,
) -> RegressionCoeffs:
    """
    Return textbook coefficients for *class_name*, or fall back to the
    closest MTOW-midpoint match if no exact name is found.

    This handles user-defined classes whose names don't match the defaults.
    """
    if class_name in TEXTBOOK_COEFFICIENTS:
        return TEXTBOOK_COEFFICIENTS[class_name]

    # Midpoint-based fallback
    if mtow_midpoint_kg is not None:
        if mtow_midpoint_kg < 25.0:
            base = TEXTBOOK_COEFFICIENTS[CLASS_MICRO_MINI]
        elif mtow_midpoint_kg < 150.0:
            base = TEXTBOOK_COEFFICIENTS[CLASS_SMALL]
        elif mtow_midpoint_kg < 1500.0:
            base = TEXTBOOK_COEFFICIENTS[CLASS_MEDIUM]
        else:
            base = TEXTBOOK_COEFFICIENTS[CLASS_LARGE]
        # Return a copy with the correct class_name
        import dataclasses
        return dataclasses.replace(base, class_name=class_name)

    # Last resort: micro/mini defaults
    return TEXTBOOK_COEFFICIENTS[CLASS_MICRO_MINI]
