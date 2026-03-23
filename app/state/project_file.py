"""
Project File Serialisation — UAV-CD-APP
=========================================
Save and load .uavcd project files (JSON format).

File contract:
  - All numeric values stored in SI units.
  - Enum fields stored as .value strings.
  - dataclasses serialised via recursive to_dict() helper.
  - Optional fields serialised as null when None.
  - run_history is stored with full brief + results per run.

Versioning:
  - "format_version" field allows future migration.
  - Current version: "1.0"
"""

from __future__ import annotations

import dataclasses
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.entities import (
    ClassificationRange,
    ConstraintCurve,
    ConstraintResult,
    ConstraintViolation,
    CruiseMissionSegment,
    DesignBrief,
    DesignPoint,
    LoiterMissionSegment,
    MissionSegment,
    RegressionCoeffs,
    SanityCheck,
    SizingRun,
    WeightResult,
)
from app.core.enums import (
    ConstraintSeverity,
    DataSource,
    EnergySource,
    PropulsionType,
    SanityCheckStatus,
    SegmentType,
)
from app.state.app_state import AppState, HistoricalDataState, ProjectMeta, SizingState

_LOG = logging.getLogger(__name__)

_FORMAT_VERSION: str = "1.0"
_FILE_FORMAT:    str = "uavcd"
_STORAGE_UNITS:  str = "SI"


# ---------------------------------------------------------------------------
# Serialisation: Python → JSON-compatible dict
# ---------------------------------------------------------------------------

def _enum_val(v: Any) -> Any:
    """Return enum.value, or the value itself if not an Enum."""
    return v.value if hasattr(v, "value") else v


def _ser_mission_segment(s: MissionSegment) -> dict[str, Any]:
    base: dict[str, Any] = {
        "segment_class": type(s).__name__,
        "segment_type": _enum_val(s.segment_type),
        "enabled": s.enabled,
        "energy_source": _enum_val(s.energy_source),
    }
    if isinstance(s, CruiseMissionSegment):
        base["range_km"] = s.range_km
        base["label_override"] = s.label_override
    elif isinstance(s, LoiterMissionSegment):
        base["endurance_hr"] = s.endurance_hr
        base["label_override"] = s.label_override
    return base


def _ser_design_brief(b: DesignBrief) -> dict[str, Any]:
    d: dict[str, Any] = {
        "payload_mass_kg": b.payload_mass_kg,
        "cruise_speed_ms": b.cruise_speed_ms,
        "stall_speed_ms": b.stall_speed_ms,
        "max_speed_ms": b.max_speed_ms,
        "takeoff_run_m": b.takeoff_run_m,
        "rate_of_climb_ms": b.rate_of_climb_ms,
        "service_ceiling_m": b.service_ceiling_m,
        "cruise_altitude_m": b.cruise_altitude_m,
        "propulsion_type": _enum_val(b.propulsion_type),
        "c_l_max": b.c_l_max,
        "c_d0": b.c_d0,
        "oswald_efficiency": b.oswald_efficiency,
        "aspect_ratio": b.aspect_ratio,
        "prop_efficiency": b.prop_efficiency,
        "battery_energy_density_wh_kg": b.battery_energy_density_wh_kg,
        "battery_efficiency": b.battery_efficiency,
        "specific_fuel_consumption_g_wh": b.specific_fuel_consumption_g_wh,
        "classification_name": b.classification_name,
        "mission_segments": [_ser_mission_segment(s) for s in b.mission_segments],
    }
    return d


def _ser_weight_result(w: WeightResult) -> dict[str, Any]:
    return {
        "w_to_kg": w.w_to_kg,
        "w_empty_kg": w.w_empty_kg,
        "w_fuel_or_battery_kg": w.w_fuel_or_battery_kg,
        "w_payload_kg": w.w_payload_kg,
        "empty_weight_fraction": w.empty_weight_fraction,
        "fuel_battery_fraction": w.fuel_battery_fraction,
        "iterations": w.iterations,
        "converged": w.converged,
        "convergence_history": list(w.convergence_history),
        "cl_cruise": w.cl_cruise,
        "ld_max": w.ld_max,
        # segment_fractions omitted from file (re-computed on load)
    }


def _ser_constraint_curve(c: ConstraintCurve) -> dict[str, Any]:
    return {
        "name": c.name,
        "color_hex": c.color_hex,
        "wing_loading_values": list(c.wing_loading_values),
        "loading_values": list(c.loading_values),
    }


def _ser_constraint_violation(v: ConstraintViolation) -> dict[str, Any]:
    return {
        "constraint_name": v.constraint_name,
        "description": v.description,
        "severity": _enum_val(v.severity),
        "current_value": v.current_value,
        "limit_value": v.limit_value,
        "unit": v.unit,
    }


def _ser_constraint_result(cr: ConstraintResult) -> dict[str, Any]:
    return {
        "stall_ws_nm2": cr.stall_ws_nm2,
        "curves": [_ser_constraint_curve(c) for c in cr.curves],
        "ws_range": list(cr.ws_range),
        "is_power_loading_mode": cr.is_power_loading_mode,
        "violations": [_ser_constraint_violation(v) for v in cr.violations],
    }


def _ser_sanity_check(s: SanityCheck) -> dict[str, Any]:
    return {
        "parameter_name": s.parameter_name,
        "computed_value": s.computed_value,
        "expected_value": s.expected_value,
        "band_low": s.band_low,
        "band_high": s.band_high,
        "status": _enum_val(s.status),
        "unit": s.unit,
    }


def _ser_design_point(dp: DesignPoint) -> dict[str, Any]:
    return {
        "wing_loading_nm2": dp.wing_loading_nm2,
        "power_loading_nw": dp.power_loading_nw,
        "w_to_kg": dp.w_to_kg,
        "wing_area_m2": dp.wing_area_m2,
        "wingspan_m": dp.wingspan_m,
        "aspect_ratio": dp.aspect_ratio,
        "engine_power_w": dp.engine_power_w,
        "sanity_checks": [_ser_sanity_check(s) for s in dp.sanity_checks],
    }


def _ser_regression_coeffs(rc: RegressionCoeffs) -> dict[str, Any]:
    d = dataclasses.asdict(rc)
    d["data_source"] = _enum_val(rc.data_source)
    return d


def _ser_classification_range(cr: ClassificationRange) -> dict[str, Any]:
    return dataclasses.asdict(cr)


def _ser_sizing_run(run: SizingRun) -> dict[str, Any]:
    return {
        "label": run.label,
        "timestamp_iso": run.timestamp_iso,
        "brief": _ser_design_brief(run.brief),
        "weight_result": _ser_weight_result(run.weight_result),
        "design_point": (
            _ser_design_point(run.design_point)
            if run.design_point else None
        ),
    }


def _ser_historical_state(hd: HistoricalDataState) -> dict[str, Any]:
    return {
        "classification_ranges": [
            _ser_classification_range(cr) for cr in hd.classification_ranges
        ],
        "regression_coefficients": {
            name: _ser_regression_coeffs(rc)
            for name, rc in hd.regression_coefficients.items()
        },
        "active_plot_x": hd.active_plot_x,
        "active_plot_y": hd.active_plot_y,
        "log_scale_x": hd.log_scale_x,
        "log_scale_y": hd.log_scale_y,
        "show_regression_line": hd.show_regression_line,
        "show_class_legend": hd.show_class_legend,
    }


def _ser_app_state(state: AppState) -> dict[str, Any]:
    meta = dataclasses.asdict(state.meta)
    sizing = state.sizing
    return {
        "file_format": _FILE_FORMAT,
        "format_version": _FORMAT_VERSION,
        "storage_units": _STORAGE_UNITS,
        "meta": meta,
        "historical_data": _ser_historical_state(state.historical_data),
        "sizing": {
            "brief": _ser_design_brief(sizing.brief),
            "weight_result": (
                _ser_weight_result(sizing.weight_result)
                if sizing.weight_result else None
            ),
            "constraint_result": (
                _ser_constraint_result(sizing.constraint_result)
                if sizing.constraint_result else None
            ),
            "design_point": (
                _ser_design_point(sizing.design_point)
                if sizing.design_point else None
            ),
            "run_history": [_ser_sizing_run(r) for r in sizing.run_history],
        },
    }


# ---------------------------------------------------------------------------
# Deserialisation: JSON dict → Python
# ---------------------------------------------------------------------------

def _deser_mission_segment(d: dict[str, Any]) -> MissionSegment:
    """Reconstruct the correct MissionSegment child class from a saved dict."""
    seg_type = SegmentType(d.get("segment_type", SegmentType.CRUISE.value))
    enabled = bool(d.get("enabled", True))
    energy_source = EnergySource(d.get("energy_source", EnergySource.FUEL.value))
    cls_name = d.get("segment_class", "MissionSegment")

    if cls_name == "CruiseMissionSegment" or seg_type is SegmentType.CRUISE:
        return CruiseMissionSegment(
            segment_type=SegmentType.CRUISE,
            enabled=enabled,
            energy_source=energy_source,
            range_km=float(d.get("range_km", 50.0)),
            label_override=d.get("label_override", ""),
        )
    if cls_name == "LoiterMissionSegment" or seg_type is SegmentType.LOITER:
        return LoiterMissionSegment(
            segment_type=SegmentType.LOITER,
            enabled=enabled,
            energy_source=energy_source,
            endurance_hr=float(d.get("endurance_hr", 1.0)),
            label_override=d.get("label_override", ""),
        )
    return MissionSegment(
        segment_type=seg_type,
        enabled=enabled,
        energy_source=energy_source,
    )


def _deser_design_brief(d: dict[str, Any]) -> DesignBrief:
    d = dict(d)
    pt = PropulsionType(d.pop("propulsion_type", "Electric"))
    # Reconstruct mission segments if present
    raw_segs = d.pop("mission_segments", None)
    if raw_segs is not None:
        segments = [_deser_mission_segment(s) for s in raw_segs]
    else:
        from app.core.entities import _default_mission_segments
        segments = _default_mission_segments()
    # Remove any stale legacy fields that are no longer in DesignBrief
    for legacy in ("range_km", "endurance_hr"):
        d.pop(legacy, None)
    valid_fields = DesignBrief.__dataclass_fields__.keys()
    return DesignBrief(
        **{k: v for k, v in d.items() if k in valid_fields},
        propulsion_type=pt,
        mission_segments=segments,
    )


def _deser_weight_result(d: dict[str, Any]) -> WeightResult:
    history_list = d.get("convergence_history", [])
    return WeightResult(
        w_to_kg=float(d["w_to_kg"]),
        w_empty_kg=float(d["w_empty_kg"]),
        w_fuel_or_battery_kg=float(d["w_fuel_or_battery_kg"]),
        w_payload_kg=float(d["w_payload_kg"]),
        empty_weight_fraction=float(d["empty_weight_fraction"]),
        fuel_battery_fraction=float(d["fuel_battery_fraction"]),
        iterations=int(d["iterations"]),
        converged=bool(d["converged"]),
        convergence_history=tuple(float(v) for v in history_list),
        cl_cruise=float(d.get("cl_cruise", 0.0)),
        ld_max=float(d.get("ld_max", 0.0)),
        # segment_fractions not persisted — re-computed on next run
    )


def _deser_constraint_curve(d: dict[str, Any]) -> ConstraintCurve:
    return ConstraintCurve(
        name=d["name"],
        color_hex=d["color_hex"],
        wing_loading_values=tuple(float(v) for v in d["wing_loading_values"]),
        loading_values=tuple(float(v) for v in d["loading_values"]),
    )


def _deser_constraint_violation(d: dict[str, Any]) -> ConstraintViolation:
    return ConstraintViolation(
        constraint_name=d["constraint_name"],
        description=d["description"],
        severity=ConstraintSeverity(d.get("severity", "warning")),
        current_value=float(d["current_value"]),
        limit_value=float(d["limit_value"]),
        unit=d.get("unit", ""),
    )


def _deser_constraint_result(d: dict[str, Any]) -> ConstraintResult:
    return ConstraintResult(
        stall_ws_nm2=float(d["stall_ws_nm2"]),
        curves=tuple(_deser_constraint_curve(c) for c in d.get("curves", [])),
        ws_range=tuple(float(v) for v in d.get("ws_range", [])),
        is_power_loading_mode=bool(d.get("is_power_loading_mode", True)),
        violations=tuple(
            _deser_constraint_violation(v) for v in d.get("violations", [])
        ),
    )


def _deser_sanity_check(d: dict[str, Any]) -> SanityCheck:
    return SanityCheck(
        parameter_name=d["parameter_name"],
        computed_value=float(d["computed_value"]),
        expected_value=float(d["expected_value"]),
        band_low=float(d["band_low"]),
        band_high=float(d["band_high"]),
        status=SanityCheckStatus(d.get("status", "pass")),
        unit=d.get("unit", ""),
    )


def _deser_design_point(d: dict[str, Any]) -> DesignPoint:
    return DesignPoint(
        wing_loading_nm2=float(d["wing_loading_nm2"]),
        power_loading_nw=float(d["power_loading_nw"]),
        w_to_kg=float(d["w_to_kg"]),
        wing_area_m2=float(d["wing_area_m2"]),
        wingspan_m=float(d["wingspan_m"]),
        aspect_ratio=float(d["aspect_ratio"]),
        engine_power_w=float(d["engine_power_w"]),
        sanity_checks=tuple(
            _deser_sanity_check(s) for s in d.get("sanity_checks", [])
        ),
    )


def _deser_regression_coeffs(d: dict[str, Any]) -> RegressionCoeffs:
    return RegressionCoeffs(
        class_name=d["class_name"],
        we_a=float(d.get("we_a", 0.0)),
        we_b=float(d.get("we_b", 0.6)),
        we_r2=float(d.get("we_r2", 0.0)),
        b_coeff=float(d.get("b_coeff", 1.10)),
        b_exp=float(d.get("b_exp", 0.333)),
        b_r2=float(d.get("b_r2", 0.0)),
        s_coeff=float(d.get("s_coeff", 0.16)),
        s_exp=float(d.get("s_exp", 0.667)),
        s_r2=float(d.get("s_r2", 0.0)),
        sample_count=int(d.get("sample_count", 0)),
        data_source=DataSource(d.get("data_source", "Textbook fallback (insufficient data)")),
    )


def _deser_classification_range(d: dict[str, Any]) -> ClassificationRange:
    return ClassificationRange(
        name=d.get("name", ""),
        min_mtow_kg=float(d.get("min_mtow_kg", 0.0)),
        max_mtow_kg=float(d.get("max_mtow_kg", 0.0)),
        color_hex=d.get("color_hex", "#007acc"),
    )


def _deser_sizing_run(d: dict[str, Any]) -> SizingRun:
    dp_d = d.get("design_point")
    return SizingRun(
        label=d.get("label", ""),
        timestamp_iso=d.get("timestamp_iso", ""),
        brief=_deser_design_brief(d["brief"]),
        weight_result=_deser_weight_result(d["weight_result"]),
        design_point=_deser_design_point(dp_d) if dp_d else None,
    )


def _deser_historical_state(d: dict[str, Any]) -> HistoricalDataState:
    return HistoricalDataState(
        classification_ranges=[
            _deser_classification_range(cr)
            for cr in d.get("classification_ranges", [])
        ],
        regression_coefficients={
            name: _deser_regression_coeffs(rc)
            for name, rc in d.get("regression_coefficients", {}).items()
        },
        active_plot_x=d.get("active_plot_x", "mtow_kg"),
        active_plot_y=d.get("active_plot_y", "wingspan_m"),
        log_scale_x=bool(d.get("log_scale_x", True)),
        log_scale_y=bool(d.get("log_scale_y", True)),
        show_regression_line=bool(d.get("show_regression_line", True)),
        show_class_legend=bool(d.get("show_class_legend", True)),
    )


def _deser_app_state(d: dict[str, Any]) -> AppState:
    meta_d = d.get("meta", {})
    meta = ProjectMeta(**{
        k: v for k, v in meta_d.items()
        if k in ProjectMeta.__dataclass_fields__
    })

    hd = _deser_historical_state(d.get("historical_data", {}))

    sizing_d = d.get("sizing", {})
    brief = _deser_design_brief(sizing_d.get("brief", {}))
    wr_d = sizing_d.get("weight_result")
    cr_d = sizing_d.get("constraint_result")
    dp_d = sizing_d.get("design_point")
    run_history = [
        _deser_sizing_run(r) for r in sizing_d.get("run_history", [])
    ]

    sizing = SizingState(
        brief=brief,
        weight_result=_deser_weight_result(wr_d) if wr_d else None,
        constraint_result=_deser_constraint_result(cr_d) if cr_d else None,
        design_point=_deser_design_point(dp_d) if dp_d else None,
        run_history=run_history,
    )

    return AppState(meta=meta, historical_data=hd, sizing=sizing)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_project(state: AppState, path: str) -> bool:
    """
    Serialise *state* to a .uavcd file at *path*.
    Stamps modified_at with the current UTC time.
    Returns True on success.
    """
    state.meta.modified_at = datetime.now(timezone.utc).isoformat()
    doc = _ser_app_state(state)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
        return True
    except OSError as exc:
        _LOG.error("save_project failed: %s", exc)
        return False


def load_project(path: str) -> Optional[AppState]:
    """
    Deserialise a .uavcd file.
    Returns None if the file cannot be read or parsed.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        if d.get("file_format") != _FILE_FORMAT:
            _LOG.warning("load_project: unexpected file_format in %s", path)
        return _deser_app_state(d)
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        _LOG.error("load_project failed: %s", exc)
        return None


def new_project(name: str = "Untitled Project") -> AppState:
    """Create a fresh AppState for a new project."""
    now = datetime.now(timezone.utc).isoformat()
    state = AppState()
    state.meta.name = name
    state.meta.created_at = now
    state.meta.modified_at = now
    return state
