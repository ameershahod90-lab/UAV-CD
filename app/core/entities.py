"""
Domain Entities — UAV-CD-APP
==============================
All domain dataclasses with strict typing and field metadata.
No Qt, no pandas, no scipy — pure Python domain objects.

Design decisions:
  - Dataclasses with default values for serialisation compatibility.
  - Field metadata carries physical units (always SI), labels, and hints
    so the UI can auto-generate labelled inputs without hard-coding.
  - Immutable result types (frozen=True) prevent accidental mutation
    after computation.
  - Mutable input types (DesignBrief, ClassificationRange) are plain
    dataclasses so the store can mutate them via typed setters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.core.enums import (
    PropulsionType,
    SanityCheckStatus,
    ConstraintSeverity,
    DataSource,
)


# ===========================================================================
# Historical Data / Classification
# ===========================================================================

@dataclass
class ClassificationRange:
    """
    A single user-defined MTOW classification bin.

    Constraints enforced by DatabaseService:
      - Ranges must be non-overlapping.
      - Together they must span [0, max_mtow_in_db].
      - min_mtow < max_mtow.
      - At least one range must exist.
    """

    name: str = "Untitled Class"
    min_mtow_kg: float = 0.0     # inclusive lower bound [kg]
    max_mtow_kg: float = 0.0     # exclusive upper bound [kg], last bin is inclusive
    color_hex: str = "#007acc"   # Legend / plot colour

    def contains(self, mtow_kg: float) -> bool:
        """Return True if *mtow_kg* falls within this range."""
        return self.min_mtow_kg <= mtow_kg < self.max_mtow_kg

    def __str__(self) -> str:
        return (
            f"{self.name} "
            f"({self.min_mtow_kg:.0f} – {self.max_mtow_kg:.0f} kg)"
        )


@dataclass(frozen=True)
class RegressionCoeffs:
    """
    Regression coefficients for one classification range.
    Produced by regression.py; consumed by weight_buildup.py and scaling_laws.py.
    """

    class_name: str

    # Empty weight fraction: W_E / W_TO = we_a * W_TO + we_b  (linear)
    we_a: float = 0.0
    we_b: float = 0.0
    we_r2: float = 0.0               # Goodness-of-fit

    # Wingspan power law: b = b_coeff * m_kg ^ b_exp  [m]
    b_coeff: float = 1.10
    b_exp: float = 0.333
    b_r2: float = 0.0

    # Wing area power law: S = s_coeff * m_kg ^ s_exp  [m²]
    s_coeff: float = 0.16
    s_exp: float = 0.667
    s_r2: float = 0.0

    sample_count: int = 0
    data_source: DataSource = DataSource.TEXTBOOK


@dataclass(frozen=True)
class FieldStatistics:
    """Descriptive statistics for a single database column within one class."""

    field_name: str
    class_name: str
    count: int
    mean: float
    std: float
    minimum: float
    maximum: float
    median: float


# ===========================================================================
# Design Brief — Mutable Input
# ===========================================================================

@dataclass
class DesignBrief:
    """
    Mission requirements and aerodynamic coefficients entered by the user.
    All physical quantities stored in SI units.

    The UI layer is responsible for display-unit conversion via UnitConverter.
    """

    # ── Mission requirements ──────────────────────────────────────────────
    payload_mass_kg: float = 5.0          # [kg]
    cruise_speed_ms: float = 25.0         # [m/s]
    stall_speed_ms: float = 12.0          # [m/s]
    max_speed_ms: float = 40.0            # [m/s]
    range_km: float = 50.0               # [km]
    endurance_hr: float = 2.0            # [h]
    takeoff_run_m: float = 50.0          # [m]
    rate_of_climb_ms: float = 3.0        # [m/s]
    service_ceiling_m: float = 3000.0    # [m]
    cruise_altitude_m: float = 1500.0    # [m]

    # ── Propulsion ────────────────────────────────────────────────────────
    propulsion_type: PropulsionType = PropulsionType.ELECTRIC

    # ── Aerodynamic coefficients (slider-tuneable) ────────────────────────
    c_l_max: float = 1.5                 # Maximum lift coefficient [-]
    c_d0: float = 0.025                  # Zero-lift drag coefficient [-]
    oswald_efficiency: float = 0.80      # Oswald span efficiency factor [-]
    aspect_ratio: float = 10.0           # Wing aspect ratio [-]
    prop_efficiency: float = 0.75        # Propulsive efficiency η [-]

    # ── Electric-specific (active when PropulsionType.ELECTRIC) ──────────
    battery_energy_density_wh_kg: float = 200.0   # [Wh/kg] Li-Po typical
    battery_efficiency: float = 0.85              # Discharge efficiency [-]

    # ── Fuel-specific (active when PropulsionType.PISTON / TURBOPROP) ────
    specific_fuel_consumption_g_wh: float = 0.35  # SFC [g/(W·h)]

    # ── Target classification (links to HistoricalDataState.ranges) ──────
    classification_name: str = "Micro/Mini"


# ===========================================================================
# Weight Buildup Results — Immutable Output
# ===========================================================================

@dataclass(frozen=True)
class WeightResult:
    """
    Result of the iterative W_TO convergence loop.
    All masses in [kg].
    """

    w_to_kg: float                      # Maximum takeoff weight [kg]
    w_empty_kg: float                   # Empty weight [kg]
    w_fuel_or_battery_kg: float         # Fuel or battery mass [kg]
    w_payload_kg: float                 # Payload mass [kg]

    empty_weight_fraction: float        # W_E / W_TO [-]
    fuel_battery_fraction: float        # W_F or W_B / W_TO [-]

    iterations: int                     # Convergence iteration count
    converged: bool                     # True if tolerance met
    convergence_history: tuple[float, ...] = field(default_factory=tuple)


# ===========================================================================
# Constraint Analysis Results — Immutable Output
# ===========================================================================

@dataclass(frozen=True)
class ConstraintViolation:
    """
    Documents a constraint that the current design point violates.
    Emitted by AppStore.constraint_violation signal.
    """

    constraint_name: str
    description: str
    severity: ConstraintSeverity
    current_value: float
    limit_value: float
    unit: str = ""


@dataclass(frozen=True)
class ConstraintCurve:
    """
    One constraint boundary on the matching plot.
    x = wing loading [N/m²], y = T/W or W/P [N/N or N/W].
    """

    name: str
    color_hex: str
    wing_loading_values: tuple[float, ...]   # W/S [N/m²]
    loading_values: tuple[float, ...]        # T/W [-] or W/P [N/W]


@dataclass(frozen=True)
class ConstraintResult:
    """
    Full matching-plot output from ConstraintAnalyzer.
    Contains all five constraint curves and the feasible region boundary.
    """

    stall_ws_nm2: float                          # Vertical stall limit [N/m²]
    curves: tuple[ConstraintCurve, ...]          # All non-stall curves
    ws_range: tuple[float, ...]                  # Shared W/S axis [N/m²]
    is_power_loading_mode: bool                  # True → W/P, False → T/W
    violations: tuple[ConstraintViolation, ...]  # Any active violations


# ===========================================================================
# Design Point — Immutable Output
# ===========================================================================

@dataclass(frozen=True)
class SanityCheck:
    """Result of a single scaling-law sanity check."""

    parameter_name: str
    computed_value: float
    expected_value: float
    band_low: float
    band_high: float
    status: SanityCheckStatus
    unit: str


@dataclass(frozen=True)
class DesignPoint:
    """
    The balanced design point — primary output of Phase 1.
    All quantities in SI units.
    """

    # ── Design point coordinates ──────────────────────────────────────────
    wing_loading_nm2: float      # W/S [N/m²]
    power_loading_nw: float      # W/P [N/W] (electric/piston) or T/W [N/N]

    # ── Derived geometry ──────────────────────────────────────────────────
    w_to_kg: float               # MTOW [kg]
    wing_area_m2: float          # S [m²]
    wingspan_m: float            # b [m]
    aspect_ratio: float          # AR [-]
    engine_power_w: float        # P or T [W or N]

    # ── Sanity checks ─────────────────────────────────────────────────────
    sanity_checks: tuple[SanityCheck, ...]


# ===========================================================================
# Sizing Run Snapshot — for multi-run comparison
# ===========================================================================

@dataclass(frozen=True)
class SizingRun:
    """
    Snapshot of a completed sizing computation.
    Stored in SizingState.run_history for comparison table and overlay plots.
    """

    label: str
    timestamp_iso: str
    brief: DesignBrief
    weight_result: WeightResult
    design_point: Optional[DesignPoint]

    @property
    def propulsion_label(self) -> str:
        return self.brief.propulsion_type.label
