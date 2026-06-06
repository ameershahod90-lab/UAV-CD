"""
Active-regression-coefficient resolution — shared helper.

Every service that runs a sizing-style analysis pipeline (``SizingService``,
``SensitivityService``, ``ExportService``) needs to pick a
``RegressionCoeffs`` from the brief's classification, with a textbook
fallback when the user's database holds nothing for that class. The rule
was previously duplicated across three call sites; this module is the
single source of truth.

Resolution order:
  1. Database coefficients keyed by ``brief.classification_name``
     (populated by ``DatabaseService`` when the historical CSV loads).
  2. Closest-textbook fallback via ``get_closest_textbook(...)`` based on
     classification + estimated mid-range MTOW (5 × payload as a crude
     proxy).

Either step may return ``None``; callers must handle that.
"""

from __future__ import annotations

from typing import Optional

from app.core.coefficients import get_closest_textbook
from app.core.entities import DesignBrief, RegressionCoeffs
from app.state.store import AppStore


def resolve_active_coeffs(
    store: AppStore,
    brief: DesignBrief,
) -> Optional[RegressionCoeffs]:
    """Return the regression coefficients active for ``brief`` in ``store``."""
    hd = store.state.historical_data
    coeffs = hd.regression_coefficients.get(brief.classification_name)
    if coeffs is None:
        cr = hd.find_range_for_mtow(brief.payload_mass_kg * 5)
        mid = (cr.min_mtow_kg + cr.max_mtow_kg) / 2 if cr else None
        coeffs = get_closest_textbook(brief.classification_name, mid)
    return coeffs
