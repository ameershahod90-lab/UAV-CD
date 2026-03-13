"""
Database Service — UAV-CD-APP
================================
Orchestrates the classification → regression → AppStore pipeline.

Responsibilities:
  1. Load the database CSV on startup (or when path changes).
  2. On classification_changed: re-run regression for every range.
  3. Push updated RegressionCoeffs to AppStore.
  4. Validate classification ranges (no gaps, no overlaps, full coverage).

Triggered by: AppStore.classification_changed signal.
Pushes to: AppStore.update_regression_coefficients()
"""

from __future__ import annotations

import logging
from typing import Optional

from app.core.database import DatabaseLoader, UavRecord
from app.core.entities import ClassificationRange, RegressionCoeffs
from app.core.regression import compute_regression_coeffs
from app.state.store import AppStore

_LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Classification range validation
# ---------------------------------------------------------------------------

class ClassificationValidationError(Exception):
    """Raised when ranges fail structural validation."""


def validate_ranges(ranges: list[ClassificationRange]) -> list[str]:
    """
    Validate a list of ClassificationRange objects.

    Returns a list of human-readable error strings (empty = valid).

    Rules:
      - At least one range.
      - Every range must have min_mtow < max_mtow.
      - Ranges must be sorted in ascending order of min_mtow.
      - No gaps between adjacent ranges (range[i].max == range[i+1].min).
      - No overlaps.
      - Unique names.
    """
    errors: list[str] = []

    if not ranges:
        errors.append("At least one classification range is required.")
        return errors

    names = [r.name.strip() for r in ranges]
    if len(set(names)) != len(names):
        errors.append("Each classification range must have a unique name.")

    for i, r in enumerate(ranges):
        if not r.name.strip():
            errors.append(f"Range at index {i} has an empty name.")
        if r.min_mtow_kg < 0:
            errors.append(f"'{r.name}': min MTOW must be ≥ 0 kg.")
        if r.min_mtow_kg >= r.max_mtow_kg:
            errors.append(
                f"'{r.name}': min MTOW ({r.min_mtow_kg:.1f}) "
                f"must be < max MTOW ({r.max_mtow_kg:.1f})."
            )

    # Check ordering and no gaps/overlaps
    sorted_ranges = sorted(ranges, key=lambda r: r.min_mtow_kg)
    if sorted_ranges != ranges:
        errors.append("Ranges must be ordered by ascending min MTOW.")

    for i in range(len(sorted_ranges) - 1):
        cur = sorted_ranges[i]
        nxt = sorted_ranges[i + 1]
        if abs(cur.max_mtow_kg - nxt.min_mtow_kg) > 1e-6:
            errors.append(
                f"Gap or overlap between '{cur.name}' (max {cur.max_mtow_kg:.1f} kg) "
                f"and '{nxt.name}' (min {nxt.min_mtow_kg:.1f} kg). "
                f"Adjacent ranges must share boundary values exactly."
            )

    return errors


# ---------------------------------------------------------------------------
# DatabaseService
# ---------------------------------------------------------------------------

class DatabaseService:
    """
    Manages the lifecycle of the historical UAV database and
    drives the classification → regression pipeline.

    Usage::

        svc = DatabaseService(store)
        svc.initialise()   # Load DB, run initial regressions
        # AppStore.classification_changed → svc.on_classification_changed()
    """

    def __init__(self, store: AppStore) -> None:
        self._store: AppStore = store
        store.classification_changed.connect(self.on_classification_changed)

    def initialise(self, csv_path: Optional[str] = None) -> None:
        """
        Load the database and compute initial regression coefficients.
        Called once from main.py after the store is created.
        """
        DatabaseLoader.load(csv_path)
        _LOG.info(
            "DB loaded: %d total, %d fixed-wing",
            DatabaseLoader.record_count(),
            DatabaseLoader.fixed_wing_count(),
        )
        self._run_regressions()

    def reload_database(self, csv_path: Optional[str] = None) -> None:
        """Force a DB reload (e.g., after user changes path in Settings)."""
        DatabaseLoader.reload(csv_path)
        self._run_regressions()

    def on_classification_changed(self) -> None:
        """Connected to AppStore.classification_changed signal."""
        self._run_regressions()

    def validate_current_ranges(self) -> list[str]:
        """Return validation errors for the store's current ranges."""
        ranges = self._store.state.historical_data.classification_ranges
        return validate_ranges(ranges)

    # ── Internal ─────────────────────────────────────────────────────────

    def _run_regressions(self) -> None:
        """
        For each classification range, filter DB records and compute
        regression coefficients. Push result to AppStore.
        """
        ranges = self._store.state.historical_data.classification_ranges
        all_fw = DatabaseLoader.get_fixed_wing()
        results: dict[str, RegressionCoeffs] = {}

        for cr in ranges:
            records = self._filter_records(all_fw, cr)
            coeffs = compute_regression_coeffs(cr.name, records)
            results[cr.name] = coeffs
            _LOG.debug(
                "Regression '%s': %d samples, source=%s, we_b=%.3f",
                cr.name, coeffs.sample_count,
                coeffs.data_source.value, coeffs.we_b,
            )

        self._store.update_regression_coefficients(results)

    @staticmethod
    def _filter_records(
        records: list[UavRecord],
        cr: ClassificationRange,
    ) -> list[UavRecord]:
        """Filter *records* to those within *cr* MTOW bounds."""
        result: list[UavRecord] = []
        for r in records:
            if r.mtow_kg is None:
                continue
            if cr.contains(r.mtow_kg):
                result.append(r)
            elif r.mtow_kg >= cr.min_mtow_kg:
                # Handle last-bin inclusive upper edge
                result.append(r)
        # De-duplicate
        seen: set[str] = set()
        deduped: list[UavRecord] = []
        for r in result:
            if r.name not in seen:
                seen.add(r.name)
                deduped.append(r)
        # Re-filter strictly
        return [
            r for r in deduped
            if r.mtow_kg is not None
            and (cr.contains(r.mtow_kg) or
                 (r.mtow_kg >= cr.min_mtow_kg and r == deduped[-1]))
        ]
