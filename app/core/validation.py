"""
Validation Framework — UAV-CD-APP
===================================
Declarative field-level validation for domain entities.

Design:
  - FieldSpec defines constraints (min, max, gt_zero, etc.) as a tiny value
    object attached to a field via a registry — no runtime magic, no decorators.
  - validate_entity() iterates the registry and collects ALL violations at once
    (fail-fast = bad UX; collect-all = engineer-friendly).
  - ValidatedInput (UI layer) reads FieldSpec to configure QDoubleSpinBox ranges
    and display error labels — zero duplication of constraint knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


# ===========================================================================
# Value object: FieldSpec
# ===========================================================================

@dataclass(frozen=True)
class FieldSpec:
    """
    Validation specification for a single field on a dataclass entity.

    Attributes
    ----------
    label:
        Human-readable field name shown in error messages and input labels.
    unit:
        SI unit string (e.g. "kg", "m/s"). Purely informational for the UI.
    hint:
        Tooltip / helper text describing the field.
    min_val:
        Inclusive lower bound. ``None`` = no lower bound.
    max_val:
        Inclusive upper bound. ``None`` = no upper bound.
    gt_zero:
        If True, value must be strictly > 0 (overrides min_val = 0).
    gte_zero:
        If True, value must be >= 0.
    required:
        If True, ``None`` is not allowed.
    """

    label: str
    unit: str = ""
    hint: str = ""
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    gt_zero: bool = False
    gte_zero: bool = False
    required: bool = True


# ===========================================================================
# Value object: ValidationError
# ===========================================================================

@dataclass(frozen=True)
class ValidationError:
    """A single field validation failure."""

    field_name: str
    message: str
    value: Any
    spec: FieldSpec


# ===========================================================================
# Registry: (EntityType, field_name) → FieldSpec
# ===========================================================================

from app.core.entities import (
    ClassificationRange,
    CruiseMissionSegment,
    DesignBrief,
    LoiterMissionSegment,
)  # noqa: E402

FIELD_SPECS: dict[tuple[type, str], FieldSpec] = {

    # ── DesignBrief ─────────────────────────────────────────────────────────

    (DesignBrief, "payload_mass_kg"): FieldSpec(
        label="Payload Mass", unit="kg",
        hint="Total mass of all payloads (cameras, sensors, comms, etc.) "
             "excluding structure and energy.",
        gt_zero=True, max_val=50_000.0,
    ),
    (DesignBrief, "cruise_speed_ms"): FieldSpec(
        label="Cruise Speed", unit="m/s",
        hint="Nominal straight-and-level cruise speed.",
        gt_zero=True, max_val=900.0,
    ),
    (DesignBrief, "stall_speed_ms"): FieldSpec(
        label="Stall Speed", unit="m/s",
        hint="Minimum flight speed at CLmax (defines the stall constraint).",
        gt_zero=True, max_val=200.0,
    ),
    (DesignBrief, "max_speed_ms"): FieldSpec(
        label="Max Speed", unit="m/s",
        hint="Never-exceed speed (VNE). Must be > cruise speed.",
        gt_zero=True, max_val=900.0,
    ),
    (DesignBrief, "takeoff_run_m"): FieldSpec(
        label="Takeoff Run", unit="m",
        hint="Available ground roll distance (TOFL constraint).",
        gt_zero=True, max_val=10_000.0,
    ),
    (DesignBrief, "rate_of_climb_ms"): FieldSpec(
        label="Rate of Climb", unit="m/s",
        hint="Required climb rate at sea level, MTOW.",
        gt_zero=True, max_val=200.0,
    ),
    (DesignBrief, "service_ceiling_m"): FieldSpec(
        label="Service Ceiling", unit="m",
        hint="Altitude at which ROC falls to 100 fpm (0.508 m/s).",
        gt_zero=True, max_val=30_000.0,
    ),
    (DesignBrief, "cruise_altitude_m"): FieldSpec(
        label="Cruise Altitude", unit="m",
        hint="Nominal cruise altitude for ISA atmosphere lookup.",
        gte_zero=True, max_val=30_000.0,
    ),
    (DesignBrief, "c_l_max"): FieldSpec(
        label="CLmax", unit="-",
        hint="Maximum lift coefficient (clean or with high-lift devices). "
             "Typical fixed-wing UAV range: 1.0 – 2.2.",
        min_val=0.5, max_val=4.0,
    ),
    (DesignBrief, "c_d0"): FieldSpec(
        label="CD0", unit="-",
        hint="Zero-lift (parasite) drag coefficient. "
             "Typical clean UAV: 0.015 – 0.040.",
        min_val=0.001, max_val=0.50,
    ),
    (DesignBrief, "oswald_efficiency"): FieldSpec(
        label="Oswald e", unit="-",
        hint="Oswald span efficiency. Typical elliptical wing: 0.85–0.95; "
             "tapered: 0.75–0.90.",
        min_val=0.1, max_val=1.0,
    ),
    (DesignBrief, "aspect_ratio"): FieldSpec(
        label="Aspect Ratio", unit="-",
        hint="Wing aspect ratio AR = b² / S. Typical UAV range: 5 – 20.",
        min_val=2.0, max_val=50.0,
    ),
    (DesignBrief, "prop_efficiency"): FieldSpec(
        label="Propulsive Efficiency η", unit="-",
        hint="Fraction of shaft power converted to thrust power. Typical: 0.65–0.85.",
        min_val=0.1, max_val=1.0,
    ),
    (DesignBrief, "battery_energy_density_wh_kg"): FieldSpec(
        label="Battery Energy Density", unit="Wh/kg",
        hint="Specific energy of battery pack. LiPo ~150–250 Wh/kg; "
             "Li-Metal future ~400 Wh/kg.",
        gt_zero=True, max_val=2000.0,
    ),
    (DesignBrief, "battery_efficiency"): FieldSpec(
        label="Battery Efficiency", unit="-",
        hint="Discharge system efficiency (motor + ESC + wiring). Typical: 0.80–0.92.",
        min_val=0.1, max_val=1.0,
    ),
    (DesignBrief, "specific_fuel_consumption_g_wh"): FieldSpec(
        label="SFC", unit="g/(W·h)",
        hint="Brake specific fuel consumption. Typical piston: 0.30–0.45 g/(W·h).",
        gt_zero=True, max_val=5.0,
    ),

    # ── CruiseMissionSegment ────────────────────────────────────────────────

    (CruiseMissionSegment, "range_km"): FieldSpec(
        label="Range", unit="km",
        hint="Distance to fly in this cruise segment.",
        gt_zero=True, max_val=50_000.0,
    ),

    # ── LoiterMissionSegment ────────────────────────────────────────────────

    (LoiterMissionSegment, "endurance_hr"): FieldSpec(
        label="Endurance", unit="h",
        hint="On-station loiter time for this segment.",
        gt_zero=True, max_val=500.0,
    ),

    # ── ClassificationRange ──────────────────────────────────────────────────

    (ClassificationRange, "name"): FieldSpec(
        label="Class Name", unit="",
        hint="Short label for this MTOW classification bin.",
    ),
    (ClassificationRange, "min_mtow_kg"): FieldSpec(
        label="Min MTOW", unit="kg",
        hint="Inclusive lower bound of this MTOW range.",
        gte_zero=True, max_val=100_000.0,
    ),
    (ClassificationRange, "max_mtow_kg"): FieldSpec(
        label="Max MTOW", unit="kg",
        hint="Exclusive upper bound of this MTOW range (last bin is inclusive).",
        gt_zero=True, max_val=100_000.0,
    ),
}


# ===========================================================================
# Validator
# ===========================================================================

class EntityValidator:
    """
    Validates a dataclass entity against the FIELD_SPECS registry.
    Returns ALL violations, not just the first one.
    """

    @staticmethod
    def validate(entity: object) -> list[ValidationError]:
        """Validate all registered fields on *entity*. Returns [] on success."""
        entity_type: type = type(entity)
        errors: list[ValidationError] = []

        for (cls, field_name), spec in FIELD_SPECS.items():
            if cls is not entity_type:
                continue

            value: Any = getattr(entity, field_name, None)

            # Required check
            if spec.required and value is None:
                errors.append(ValidationError(
                    field_name=field_name,
                    message=f"{spec.label} is required.",
                    value=value,
                    spec=spec,
                ))
                continue

            if value is None:
                continue

            # String fields — only emptiness check
            if isinstance(value, str):
                if spec.required and not value.strip():
                    errors.append(ValidationError(
                        field_name=field_name,
                        message=f"{spec.label} must not be empty.",
                        value=value,
                        spec=spec,
                    ))
                continue

            # Numeric fields
            fval: float = float(value)

            if spec.gt_zero and fval <= 0:
                errors.append(ValidationError(
                    field_name=field_name,
                    message=f"{spec.label} must be greater than 0 {spec.unit}.",
                    value=fval,
                    spec=spec,
                ))
            elif spec.gte_zero and fval < 0:
                errors.append(ValidationError(
                    field_name=field_name,
                    message=f"{spec.label} must be ≥ 0 {spec.unit}.",
                    value=fval,
                    spec=spec,
                ))
            elif spec.min_val is not None and fval < spec.min_val:
                errors.append(ValidationError(
                    field_name=field_name,
                    message=(
                        f"{spec.label} must be ≥ {spec.min_val} {spec.unit}. "
                        f"Got {fval:.4g}."
                    ),
                    value=fval,
                    spec=spec,
                ))
            elif spec.max_val is not None and fval > spec.max_val:
                errors.append(ValidationError(
                    field_name=field_name,
                    message=(
                        f"{spec.label} must be ≤ {spec.max_val} {spec.unit}. "
                        f"Got {fval:.4g}."
                    ),
                    value=fval,
                    spec=spec,
                ))

        return errors

    @staticmethod
    def is_valid(entity: object) -> bool:
        """Convenience helper — returns True when validation passes."""
        return len(EntityValidator.validate(entity)) == 0


def get_field_spec(entity_type: type, field_name: str) -> Optional[FieldSpec]:
    """Look up the FieldSpec for a given entity type and field name."""
    return FIELD_SPECS.get((entity_type, field_name))
