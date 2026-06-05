"""
User Settings — UAV-CD-APP
============================
Machine-local preferences stored in %APPDATA%/UAV-CD/settings.json.

NOT included in .uavcd project files — settings are per-user, per-machine.

Design:
  - All enum fields typed with unit enums; invalid values silently fall
    back to defaults (protects against hand-edited settings.json).
  - dataclasses.replace() is used for all mutations to preserve immutability
    wherever possible (cascade_unit_system, load fallback).
  - JSON serialisation writes enum .value strings so the file is human-readable.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.enums import (
    AltitudeUnit,
    AreaUnit,
    ForceUnit,
    MassUnit,
    PowerUnit,
    SpeedUnit,
    ThemeOption,
    UnitSystem,
)

_LOG = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Settings file path
# ---------------------------------------------------------------------------

_APP_DIRS_NAME: str = "UAV-CD"
_SETTINGS_FILE: str = "settings.json"

MAX_RECENT: int = 10


def _settings_path() -> str:
    """Return path to the settings JSON file in %APPDATA%/UAV-CD/."""
    base: str = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, _APP_DIRS_NAME, _SETTINGS_FILE)


# ---------------------------------------------------------------------------
# UserSettings dataclass
# ---------------------------------------------------------------------------

@dataclass
class UserSettings:
    """
    Machine-local user preferences.

    All enum fields are validated on load; invalid values silently revert to
    the default (see _safe_enum()).
    """

    # Appearance
    theme: ThemeOption = ThemeOption.DARK

    # Unit system
    unit_system: UnitSystem = UnitSystem.METRIC

    # Individual units (cascade from unit_system, but can be overridden)
    speed_unit:    SpeedUnit    = SpeedUnit.MS
    altitude_unit: AltitudeUnit = AltitudeUnit.METERS
    mass_unit:     MassUnit     = MassUnit.KG
    area_unit:     AreaUnit     = AreaUnit.M2
    power_unit:    PowerUnit    = PowerUnit.WATT
    force_unit:    ForceUnit    = ForceUnit.NEWTON

    # Paths
    database_path:    str = ""
    last_project_dir: str = ""
    recent_projects: list[str] = field(default_factory=list)

    # Solver
    convergence_tolerance: float = 0.001
    max_iterations:        int   = 100

    # UI behaviour
    auto_recalculate: bool  = True
    plot_grid_visible: bool = True

    # Historical data
    use_historical_data: bool = True

    # ── Sensitivity Studio ────────────────────────────────────────────────
    # Perturbation width for tornado / sweep (5–50 %; default Raymer-ish 20 %).
    sens_delta_pct: float = 20.0
    # Number of points in an OAT sweep (odd-only ideal; clamped to 11–51).
    sens_n_points: int = 21
    # Constraint-margin severity tiers as percentages — anything below
    # ``critical`` is red, between ``critical`` and ``tight`` is amber,
    # at or above ``tight`` is green. Industry default 10 / 30.
    sens_severity_critical_pct: float = 10.0
    sens_severity_tight_pct:    float = 30.0
    # Per-slot tornado output picks (3 slots, defaults to the Tier-1 trio).
    # Stored as a tuple of OUTPUT_CATALOG keys; invalid entries silently
    # revert to the slot default on load.
    sens_tornado_output_ids: tuple[str, str, str] = (
        "mtow_kg", "wing_area_m2", "engine_power_w",
    )

    def add_recent(self, path: str) -> None:
        """Prepend *path* to recent_projects, capping at MAX_RECENT."""
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        self.recent_projects[:] = self.recent_projects[:MAX_RECENT]


# ---------------------------------------------------------------------------
# Enum-safe loader helper
# ---------------------------------------------------------------------------

_ENUM_DEFAULTS: dict[str, tuple[type, Any]] = {
    "theme":        (ThemeOption, ThemeOption.DARK),
    "unit_system":  (UnitSystem, UnitSystem.METRIC),
    "speed_unit":   (SpeedUnit, SpeedUnit.MS),
    "altitude_unit": (AltitudeUnit, AltitudeUnit.METERS),
    "mass_unit":    (MassUnit, MassUnit.KG),
    "area_unit":    (AreaUnit, AreaUnit.M2),
    "power_unit":   (PowerUnit, PowerUnit.WATT),
}


def _safe_enum(enum_cls: type, raw_value: str, default: Any) -> Any:
    """
    Try to construct enum_cls(raw_value). Return *default* on failure.
    Logs a warning so developers notice hand-edited settings.
    """
    try:
        return enum_cls(raw_value)
    except (ValueError, KeyError):
        _LOG.warning(
            "settings.json: invalid value %r for %s — using default %r.",
            raw_value, enum_cls.__name__, default.value,
        )
        return default


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _to_dict(settings: UserSettings) -> dict[str, Any]:
    """Serialise UserSettings to a plain dict (enum → .value)."""
    d = asdict(settings)
    for key, (_, _) in _ENUM_DEFAULTS.items():
        if key in d and hasattr(d[key], "value"):
            pass  # already a value after asdict() converts enums
        # asdict() converts dataclass fields but leaves Enum values as-is
        # because asdict() does NOT recurse into Enum members.
        # We manually convert:
    # Re-build with .value for enum fields
    result: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, str) and k in _ENUM_DEFAULTS:
            result[k] = v
        elif hasattr(v, "value"):         # Enum
            result[k] = v.value
        else:
            result[k] = v
    return result


def _raw_settings_dict(settings: UserSettings) -> dict[str, Any]:
    """Return a JSON-serialisable dict of UserSettings."""
    d: dict[str, Any] = {}
    for fname, ftype in settings.__dataclass_fields__.items():  # type: ignore[attr-defined]
        val = getattr(settings, fname)
        if hasattr(val, "value"):   # Enum
            d[fname] = val.value
        else:
            d[fname] = val
    return d


def _from_dict(data: dict[str, Any]) -> UserSettings:
    """Deserialise a plain dict into a UserSettings, using safe enum loading."""
    settings = UserSettings()

    for key, (enum_cls, default) in _ENUM_DEFAULTS.items():
        raw = data.get(key)
        if raw is not None:
            setattr(settings, key, _safe_enum(enum_cls, str(raw), default))

    # Scalar fields
    settings.database_path      = str(data.get("database_path", ""))
    settings.last_project_dir   = str(data.get("last_project_dir", ""))
    settings.recent_projects    = [
        str(p) for p in data.get("recent_projects", [])[:MAX_RECENT]
    ]
    settings.convergence_tolerance = float(
        data.get("convergence_tolerance", 0.001)
    )
    settings.max_iterations   = int(data.get("max_iterations", 100))
    settings.auto_recalculate = bool(data.get("auto_recalculate", True))
    settings.plot_grid_visible = bool(data.get("plot_grid_visible", True))
    settings.use_historical_data = bool(data.get("use_historical_data", True))

    # Sensitivity Studio — clamp to safe ranges so a hand-edited
    # settings.json cannot crash the studio with absurd values.
    settings.sens_delta_pct = _clamp_float(
        data.get("sens_delta_pct", 20.0), 5.0, 50.0, 20.0,
    )
    settings.sens_n_points = _clamp_int(
        data.get("sens_n_points", 21), 11, 51, 21,
    )
    settings.sens_severity_critical_pct = _clamp_float(
        data.get("sens_severity_critical_pct", 10.0), 0.0, 100.0, 10.0,
    )
    settings.sens_severity_tight_pct = _clamp_float(
        data.get("sens_severity_tight_pct", 30.0), 0.0, 100.0, 30.0,
    )
    # Tight must be > critical; if hand-edit broke that, restore defaults.
    if settings.sens_severity_tight_pct <= settings.sens_severity_critical_pct:
        settings.sens_severity_critical_pct = 10.0
        settings.sens_severity_tight_pct    = 30.0
    raw_ids = data.get("sens_tornado_output_ids")
    if isinstance(raw_ids, (list, tuple)) and len(raw_ids) == 3:
        settings.sens_tornado_output_ids = tuple(
            str(x) for x in raw_ids  # type: ignore[misc]
        )

    return settings


def _clamp_float(
    raw: Any, lo: float, hi: float, default: float,
) -> float:
    """Coerce ``raw`` to float and clamp to [lo, hi]; fall back to ``default``."""
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def _clamp_int(raw: Any, lo: int, hi: int, default: int) -> int:
    """Coerce ``raw`` to int and clamp to [lo, hi]; fall back to ``default``."""
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# SettingsManager — load / save lifecycle
# ---------------------------------------------------------------------------

class SettingsManager:
    """
    Handles persistence of UserSettings to/from ``settings.json``.

    Usage::

        mgr = SettingsManager()
        s = mgr.load()
        s.theme = ThemeOption.LIGHT
        mgr.save(s)
    """

    def __init__(self, path: str | None = None) -> None:
        self._path: str = path or _settings_path()

    @property
    def path(self) -> str:
        return self._path

    def load(self) -> UserSettings:
        """
        Load settings from disk. If the file is missing or corrupt, returns
        a fresh UserSettings with all defaults — never raises.
        """
        if not os.path.isfile(self._path):
            return UserSettings()

        try:
            with open(self._path, encoding="utf-8") as fh:
                data: dict[str, Any] = json.load(fh)
            return _from_dict(data)
        except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
            _LOG.warning("Could not load settings (%s). Using defaults.", exc)
            return UserSettings()

    def save(self, settings: UserSettings) -> bool:
        """
        Write *settings* to disk. Returns True on success, False on I/O error.
        Creates the parent directory if necessary.
        """
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(_raw_settings_dict(settings), fh, indent=2)
            return True
        except OSError as exc:
            _LOG.error("Could not save settings: %s", exc)
            return False
