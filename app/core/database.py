"""
UAV Database Loader — UAV-CD-APP
==================================
Parses the DSTO/CTRM historical UAV database CSV into typed Python objects.

Key responsibilities:
  1. Read CSV robustly (handle missing cells, comma-in-numbers, text annotations).
  2. Filter to fixed-wing entries only.
  3. Expose a clean DataFrame-free, dependency-light record list for
     downstream use by DatabaseService and the Analysis Playground.

Design:
  - UavRecord is a frozen dataclass; Optional[float] for every numeric field
    because the database is sparse.
  - DatabaseLoader is a singleton-safe loader: parse once, cache result.
  - Zero pandas dependency in this module — just stdlib csv.
    The regression and analysis layers may convert to numpy arrays as needed.
"""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from typing import Optional

from app.resources import data_path


# ---------------------------------------------------------------------------
# UAV Record — mirrors the columns in 02_Database.csv
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UavRecord:
    """A single UAV entry from the historical database."""

    # Identification
    name: str
    manufacturer: str
    country: str
    uav_type: str                     # "fixed-wing", "rotary-wing", etc.
    configuration: str                # e.g. "tractor", "pusher"
    operational_status: str

    # Weight & Geometry
    mtow_kg: Optional[float]
    payload_kg: Optional[float]
    wingspan_m: Optional[float]
    wing_area_m2: Optional[float]
    aspect_ratio: Optional[float]
    fuselage_length_m: Optional[float]

    # Performance
    max_speed_ms: Optional[float]
    cruise_speed_ms: Optional[float]
    stall_speed_ms: Optional[float]
    range_km: Optional[float]
    endurance_hr: Optional[float]
    service_ceiling_m: Optional[float]
    rate_of_climb_ms: Optional[float]
    max_altitude_m: Optional[float]

    # Power
    engine_power_w: Optional[float]
    engine_type: str

    @property
    def is_fixed_wing(self) -> bool:
        """True for all airframes that are not rotary-wing."""
        return "rotary" not in self.uav_type.lower()

    @property
    def label(self) -> str:
        """Short display label."""
        return f"{self.name} ({self.manufacturer})"


# ---------------------------------------------------------------------------
# CSV column name → UavRecord field mapping
# The CSV column names come from 02_Database.csv header.
# ---------------------------------------------------------------------------

# Mapping: (csv_column_name) → (uavrecord_field_name, unit_multiplier)
# unit_multiplier converts the raw CSV value to SI:
#   km/h → m/s: × (1/3.6)
#   ft → m:     × 0.3048
#   km → km:    × 1  (range stays as km)
#   fpm → m/s:  × 0.00508

_COL_MAP: dict[str, tuple[str, float]] = {
    "Name":                     ("name",                  0),
    "Manufacturer":             ("manufacturer",           0),
    "Country":                  ("country",                0),
    "Type":                     ("uav_type",               0),
    "Configuration":            ("configuration",          0),
    "Operational Status":       ("operational_status",     0),
    "MTOW [kg]":                ("mtow_kg",                1.0),
    "Payload [kg]":             ("payload_kg",             1.0),
    "Wingspan [m]":             ("wingspan_m",             1.0),
    "Wing Area [m2]":           ("wing_area_m2",           1.0),
    "AR":                       ("aspect_ratio",           1.0),
    "Length [m]":               ("fuselage_length_m",      1.0),
    "Max Speed [km/h]":         ("max_speed_ms",           1.0 / 3.6),
    "Cruise Speed [km/h]":      ("cruise_speed_ms",        1.0 / 3.6),
    "Stall Speed [km/h]":       ("stall_speed_ms",         1.0 / 3.6),
    "Range [km]":               ("range_km",               1.0),
    "Endurance [hr]":           ("endurance_hr",           1.0),
    "Service Ceiling [m]":      ("service_ceiling_m",      1.0),
    "ROC [m/s]":                ("rate_of_climb_ms",       1.0),
    "Max Altitude [m]":         ("max_altitude_m",         1.0),
    "Engine Power [W]":         ("engine_power_w",         1.0),
    "Engine Type":              ("engine_type",            0),
}

_STRING_FIELDS: frozenset[str] = frozenset({
    "name", "manufacturer", "country", "uav_type",
    "configuration", "operational_status", "engine_type",
})


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_STRIP_RE = re.compile(r"[^\d.\-eE]")


def _parse_float(raw: str) -> Optional[float]:
    """
    Attempt to extract a float from a raw CSV cell.
    Handles commas (thousand separators), bracketed text, and mixed strings.
    Returns None on failure.
    """
    cleaned: str = _STRIP_RE.sub("", raw.strip())
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# DatabaseLoader — parse-once, cache result
# ---------------------------------------------------------------------------

class DatabaseLoader:
    """
    Loads and caches the UAV database CSV.

    Thread safety: load() is not thread-safe during the very first call.
    For the desktop app this is fine — all IO happens on the main thread
    during startup.

    Usage::

        records = DatabaseLoader.get_all()
        fixed_wing = DatabaseLoader.get_fixed_wing()
    """

    _cache: Optional[list[UavRecord]] = None
    _csv_path: Optional[str] = None

    @classmethod
    def load(cls, csv_path: Optional[str] = None) -> None:
        """
        Parse the CSV and populate the internal cache.

        Parameters
        ----------
        csv_path:
            Override path to the database CSV. Defaults to the bundled
            ``data/uav_database.csv`` via ``data_path()``.
        """
        path: str = csv_path or data_path("uav_database.csv")

        if not os.path.isfile(path):
            cls._cache = []
            return

        records: list[UavRecord] = []
        cls._csv_path = path

        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                record = cls._parse_row(row)
                if record is not None:
                    records.append(record)

        cls._cache = records

    @classmethod
    def _parse_row(cls, row: dict[str, str]) -> Optional[UavRecord]:
        """Convert one CSV dict-row into a UavRecord. Returns None on error."""
        kwargs: dict[str, object] = {}

        for col, (field_name, multiplier) in _COL_MAP.items():
            raw: str = row.get(col, "").strip()

            if field_name in _STRING_FIELDS:
                kwargs[field_name] = raw
            else:
                val = _parse_float(raw)
                if val is not None and multiplier != 1.0 and multiplier != 0:
                    val = val * multiplier
                kwargs[field_name] = val

        try:
            return UavRecord(**kwargs)  # type: ignore[arg-type]
        except (TypeError, KeyError):
            return None

    @classmethod
    def get_all(cls) -> list[UavRecord]:
        """Return all records (fixed-wing and rotary-wing)."""
        if cls._cache is None:
            cls.load()
        return list(cls._cache or [])

    @classmethod
    def get_fixed_wing(cls) -> list[UavRecord]:
        """Return only fixed-wing entries."""
        return [r for r in cls.get_all() if r.is_fixed_wing]

    @classmethod
    def reload(cls, csv_path: Optional[str] = None) -> None:
        """Force a re-parse of the CSV (e.g., after user changes the path)."""
        cls._cache = None
        cls.load(csv_path)

    @classmethod
    def is_loaded(cls) -> bool:
        """Return True if the database has been loaded."""
        return cls._cache is not None

    @classmethod
    def record_count(cls) -> int:
        """Total number of parsed records."""
        return len(cls.get_all())

    @classmethod
    def fixed_wing_count(cls) -> int:
        """Number of fixed-wing records."""
        return len(cls.get_fixed_wing())

    # ── Filtering helpers ────────────────────────────────────────────────

    @classmethod
    def filter_by_mtow(
        cls,
        min_kg: float,
        max_kg: float,
        fixed_wing_only: bool = True,
    ) -> list[UavRecord]:
        """Return records whose MTOW falls in [min_kg, max_kg)."""
        source = cls.get_fixed_wing() if fixed_wing_only else cls.get_all()
        return [
            r for r in source
            if r.mtow_kg is not None and min_kg <= r.mtow_kg < max_kg
        ]

    @classmethod
    def get_numeric_field(
        cls,
        field_name: str,
        fixed_wing_only: bool = True,
    ) -> list[tuple[str, float]]:
        """
        Return a list of (uav_name, value) pairs for *field_name*,
        excluding records where the field is None.
        """
        source = cls.get_fixed_wing() if fixed_wing_only else cls.get_all()
        result: list[tuple[str, float]] = []
        for r in source:
            val = getattr(r, field_name, None)
            if val is not None:
                result.append((r.name, val))
        return result
