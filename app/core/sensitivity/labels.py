"""
Propulsion-aware display labels + DisplayConverter unit-kind mapping
for sensitivity outputs and parameters.

Why a separate module:
  ``OUTPUT_CATALOG`` carries a single static ``label`` per entry, which
  was sufficient for the initial commit but cannot express labels that
  depend on propulsion (engine power vs thrust, fuel vs battery mass,
  W/P vs T/W). These helpers resolve the correct label at render time
  AND tell the widget which ``DisplayConverter`` method to call so all
  numeric displays follow the user's unit preferences.

Layer
-----
``app/core/sensitivity/`` is pure-Python — these helpers return plain
strings and method-name strings. The widget layer owns the actual
``DisplayConverter`` invocation.

Pattern follows ``app/core/reports/sections/design_point_summary.py``:
  - ``is_power_mode`` switches "Engine Power"/"Power Loading W/P" ↔
    "Engine Thrust"/"Thrust Loading T/W".
  - ``is_electric`` / ``uses_fuel`` / HYBRID switch fuel/battery phrasing.
"""

from __future__ import annotations

from typing import Final

from app.core.enums import PropulsionType
from app.core.sensitivity.outcome import OUTPUT_CATALOG
from app.core.sensitivity.parameter_spec import SweepableParameter


# ── DisplayConverter method names ──────────────────────────────────────────
#
# A short string referencing one of the ``DisplayConverter`` methods
# (``mass``, ``area``, ``power``, ``force``, ``speed``, ``altitude``,
# ``length``, ``wing_loading``, ``power_loading``, ``force_loading``,
# ``ratio``). The widget code calls ``getattr(dc, kind)(si_value)`` to
# get back ``(display_value, unit_label)``.

_UNIT_KIND_RATIO: Final[str] = "ratio"


def display_label_for_output(
    output_id: str,
    propulsion_type: PropulsionType,
) -> str:
    """Human-readable, propulsion-aware label for one tracked output.

    Falls back to ``OUTPUT_CATALOG[output_id].label`` for outputs whose
    label is fixed across propulsion types (MTOW, Wing Area, Wingspan,
    Empty Weight, L/D, CL*, Wing Loading).
    """
    spec = OUTPUT_CATALOG.get(output_id)
    if spec is None:
        return output_id

    if output_id == "engine_power_w":
        # Stored field carries P [W] for prop modes and T [N] for jets.
        return "Engine Power" if propulsion_type.is_power_mode else "Engine Thrust"

    if output_id == "power_loading_nw":
        # W/P matching diagram axis vs T/W jet axis.
        return "Power Loading W/P" if propulsion_type.is_power_mode else "Thrust Loading T/W"

    if output_id == "w_fuel_or_battery_kg":
        if propulsion_type is PropulsionType.HYBRID:
            return "Fuel + Battery Mass"
        if propulsion_type.is_electric:
            return "Battery Mass"
        return "Fuel Mass"

    if output_id == "fuel_battery_fraction":
        if propulsion_type is PropulsionType.HYBRID:
            return "Fuel + Battery Fraction"
        if propulsion_type.is_electric:
            return "Battery Fraction"
        return "Fuel Fraction"

    return spec.label


def display_label_for_parameter(
    parameter: SweepableParameter,
    propulsion_type: PropulsionType,
) -> str:
    """Propulsion-aware label for an input parameter.

    Currently a passthrough — the existing ``SweepableParameter.label``
    strings ("Payload Mass", "Cruise Speed", …) are propulsion-neutral
    because propulsion-specific parameters (SFC, battery_*) are gated
    out by ``sweepable_parameters_for`` before they ever reach a widget.

    Kept as a function so the widget layer never inlines parameter
    labels and a future relabel only changes this module.
    """
    return parameter.label


def unit_kind_for_output(
    output_id: str,
    propulsion_type: PropulsionType,
) -> str:
    """Return a ``DisplayConverter`` method name for the output's unit.

    Returns ``"ratio"`` for dimensionless quantities (the ratio method
    is a passthrough so widgets can call ``getattr(dc, kind)(v)``
    uniformly without conditional branches).
    """
    if output_id in ("mtow_kg", "w_empty_kg", "w_fuel_or_battery_kg"):
        return "mass"
    if output_id == "wing_area_m2":
        return "area"
    if output_id == "engine_power_w":
        # Power [W] for prop modes, Force [N] for jets (matches the
        # ``engine_power_w`` field's dual-meaning convention used in
        # design_point.py and design_point_summary.py).
        return "power" if propulsion_type.is_power_mode else "force"
    if output_id == "wingspan_m":
        return "length"
    if output_id == "wing_loading_nm2":
        return "wing_loading"
    if output_id == "power_loading_nw":
        return "power_loading" if propulsion_type.is_power_mode else "force_loading"
    # empty_weight_fraction, ld_max, cl_cruise, fuel_battery_fraction
    return _UNIT_KIND_RATIO


def unit_kind_for_parameter(parameter: SweepableParameter) -> str:
    """Return a ``DisplayConverter`` method name for a sweep parameter.

    Some parameters are dimensionless coefficients (CD0, CL_max, e, AR,
    propulsive / battery efficiency) or composite (SFC); those return
    ``"ratio"`` so the widget passes the raw value through with the
    parameter's own unit string.
    """
    fn = parameter.field_name
    if fn == "payload_mass_kg":
        return "mass"
    if fn in ("cruise_speed_ms", "stall_speed_ms", "max_speed_ms",
              "rate_of_climb_ms"):
        return "speed"
    if fn in ("cruise_altitude_m", "service_ceiling_m", "takeoff_run_m"):
        return "altitude"
    return _UNIT_KIND_RATIO
