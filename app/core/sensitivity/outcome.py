"""
SizingOutcome — unified view over all Phase-1 outputs.

The sensitivity engine consumes a single "outcome" object per sized
configuration rather than juggling the trio of WeightResult /
ConstraintResult / DesignPoint independently. This keeps the sweep,
tornado, snowball, and margins modules small and uniform.

Every output a designer might want to track is registered in
``OUTPUT_CATALOG`` with a stable string ID + i18n key + display unit.
Adding a new tracked output is one line in this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from app.core.entities import (
    ConstraintResult,
    DesignPoint,
    WeightResult,
)
from app.core.sensitivity.predicates import InclusionPredicate, always


@dataclass(frozen=True)
class OutputSpec:
    """Metadata for a single design output exposed to sensitivity."""

    output_id:  str            # stable key, e.g. "mtow_kg"
    label:      str            # human-readable label (EN fallback)
    label_key:  str            # i18n key for translation
    unit:       str            # SI unit symbol shown in plots
    tier:       int            # 1 = headline, 2 = structural, 3 = aero, 4 = energy
    accessor:   Callable[["SizingOutcome"], Optional[float]]
    # Same inclusion-predicate pattern as SweepableParameter — every
    # output currently uses ``always``, but the field exists so future
    # outputs (e.g. a fuel-specific output) can declare gating without
    # schema migration.
    is_included: InclusionPredicate = field(default=always)


@dataclass(frozen=True)
class SizingOutcome:
    """All Phase-1 outputs from one sizing run, in one place.

    Any field may be ``None`` if the corresponding pipeline stage didn't
    run (e.g. design-point computation skipped). The ``get`` method handles
    that gracefully and returns ``None`` rather than raising.
    """

    weight:            Optional[WeightResult]      = None
    constraint_result: Optional[ConstraintResult]  = None
    design_point:      Optional[DesignPoint]       = None

    def get(self, output_id: str) -> Optional[float]:
        """Look up an output by its stable ID, or return None if unavailable."""
        spec = OUTPUT_CATALOG.get(output_id)
        if spec is None:
            return None
        try:
            return spec.accessor(self)
        except (AttributeError, TypeError):
            return None


# ── Output accessors ────────────────────────────────────────────────────────
# Each function pulls one float from a SizingOutcome (or None). Defined as
# free functions so they're easy to swap and unit-test independently.

def _wt(name: str) -> Callable[[SizingOutcome], Optional[float]]:
    def _f(o: SizingOutcome) -> Optional[float]:
        return getattr(o.weight, name, None) if o.weight is not None else None
    return _f


def _dp(name: str) -> Callable[[SizingOutcome], Optional[float]]:
    def _f(o: SizingOutcome) -> Optional[float]:
        return getattr(o.design_point, name, None) if o.design_point is not None else None
    return _f


# ── OUTPUT_CATALOG ─────────────────────────────────────────────────────────
#
# Ordered tiers (T1 headline → T4 energy). Tier 1 outputs are shown in the
# default tornado small-multiples view; any output can be picked from the
# dropdown for a focused single-tornado.

OUTPUT_CATALOG: dict[str, OutputSpec] = {
    # ── Tier 1 — the "big three" of conceptual aircraft design ───────────
    "mtow_kg": OutputSpec(
        "mtow_kg", "MTOW", "sens.output.mtow", "kg", 1, _dp("w_to_kg"),
    ),
    "wing_area_m2": OutputSpec(
        "wing_area_m2", "Wing Area (S)", "sens.output.wing_area", "m²", 1, _dp("wing_area_m2"),
    ),
    "engine_power_w": OutputSpec(
        "engine_power_w", "Engine Power / Thrust", "sens.output.engine_power",
        "W", 1, _dp("engine_power_w"),
    ),

    # ── Tier 2 — structural / operational ─────────────────────────────────
    "wingspan_m": OutputSpec(
        "wingspan_m", "Wingspan (b)", "sens.output.wingspan", "m", 2, _dp("wingspan_m"),
    ),
    "w_empty_kg": OutputSpec(
        "w_empty_kg", "Empty Weight", "sens.output.empty_weight",
        "kg", 2, _wt("w_empty_kg"),
    ),
    "empty_weight_fraction": OutputSpec(
        "empty_weight_fraction", "Empty Weight Fraction",
        "sens.output.empty_weight_fraction", "-", 2,
        _wt("empty_weight_fraction"),
    ),

    # ── Tier 3 — aerodynamic efficiency ──────────────────────────────────
    "ld_max": OutputSpec(
        "ld_max", "(L/D) max", "sens.output.ld_max", "-", 3, _wt("ld_max"),
    ),
    "cl_cruise": OutputSpec(
        "cl_cruise", "CL* (cruise)", "sens.output.cl_cruise",
        "-", 3, _wt("cl_cruise"),
    ),
    "wing_loading_nm2": OutputSpec(
        "wing_loading_nm2", "Wing Loading W/S", "sens.output.wing_loading",
        "N/m²", 3, _dp("wing_loading_nm2"),
    ),
    "power_loading_nw": OutputSpec(
        "power_loading_nw", "Power Loading W/P", "sens.output.power_loading",
        "N/W", 3, _dp("power_loading_nw"),
    ),

    # ── Tier 4 — energy / mission budget ─────────────────────────────────
    "w_fuel_or_battery_kg": OutputSpec(
        "w_fuel_or_battery_kg", "Fuel / Battery Mass",
        "sens.output.energy_mass", "kg", 4, _wt("w_fuel_or_battery_kg"),
    ),
    "fuel_battery_fraction": OutputSpec(
        "fuel_battery_fraction", "Fuel / Battery Fraction",
        "sens.output.energy_fraction", "-", 4,
        _wt("fuel_battery_fraction"),
    ),
}


def tier_1_output_ids() -> list[str]:
    """Output IDs to display in the default small-multiples tornado view."""
    return [k for k, v in OUTPUT_CATALOG.items() if v.tier == 1]
