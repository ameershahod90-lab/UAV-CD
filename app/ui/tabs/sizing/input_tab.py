"""
Sizing Input Tab — UAV-CD-APP
================================
Design Brief input form: mission requirements, propulsion, aero coefficients.

Unit conversion:
  - All internal values are SI.  ValidatedInput.value_changed always emits SI.
  - When settings change, set_unit_converter() is called on each widget so
    the spinbox value is recalculated (e.g. 25 m/s → 90 km/h) and the label
    suffix updates to reflect the new unit name.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from app.core.entities import DesignBrief
from app.core.enums import PropulsionType
from app.core.units import UnitConverter
from app.core.validation import EntityValidator, get_field_spec
from app.state.store import AppStore
from app.ui.widgets.enum_combo import EnumCombo
from app.ui.widgets.slider_input import SliderInput
from app.ui.widgets.validated_input import ValidatedInput


# ---------------------------------------------------------------------------
# Field → conversion category mapping
# ---------------------------------------------------------------------------

# Each entry:  field_name → (settings_attr, to_display_func, to_si_func)
# where the funcs take (si_val, unit_enum) or (display_val, unit_enum).

def _make_converters(settings_attr: str,
                     to_display: Callable,
                     to_si: Callable) -> tuple[str, Callable, Callable]:
    return (settings_attr, to_display, to_si)

_FIELD_UNIT_INFO: dict[str, tuple[str, Callable, Callable]] = {
    "payload_mass_kg":      _make_converters("mass_unit",     UnitConverter.mass_to_display,     UnitConverter.mass_to_si),
    "cruise_speed_ms":      _make_converters("speed_unit",    UnitConverter.speed_to_display,    UnitConverter.speed_to_si),
    "stall_speed_ms":       _make_converters("speed_unit",    UnitConverter.speed_to_display,    UnitConverter.speed_to_si),
    "max_speed_ms":         _make_converters("speed_unit",    UnitConverter.speed_to_display,    UnitConverter.speed_to_si),
    "rate_of_climb_ms":     _make_converters("speed_unit",    UnitConverter.speed_to_display,    UnitConverter.speed_to_si),
    "service_ceiling_m":    _make_converters("altitude_unit", UnitConverter.altitude_to_display, UnitConverter.altitude_to_si),
    "cruise_altitude_m":    _make_converters("altitude_unit", UnitConverter.altitude_to_display, UnitConverter.altitude_to_si),
    "takeoff_run_m":        _make_converters("altitude_unit", UnitConverter.altitude_to_display, UnitConverter.altitude_to_si),
}


class InputTab(QWidget):
    """Mission requirements and aerodynamic coefficient input form."""

    def __init__(self, store: AppStore, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._store: AppStore = store

        # Scroll area wrapper
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)

        content = QWidget()
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        main = QVBoxLayout(content)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(16)

        # ── Classification ────────────────────────────────────────────────
        cls_box = self._make_group("UAV Classification")
        cls_form = QFormLayout()
        cls_form.setSpacing(8)
        self._class_combo = QComboBox()
        self._refresh_class_combo()
        self._class_combo.currentTextChanged.connect(self._on_class_changed)
        cls_form.addRow("Classification Class:", self._class_combo)
        cls_box.layout().addLayout(cls_form)
        main.addWidget(cls_box)

        # ── Mission Requirements ──────────────────────────────────────────
        mission_box = self._make_group("Mission Requirements")
        mission_form = QFormLayout()
        mission_form.setSpacing(8)

        self._inputs: dict[str, ValidatedInput] = {}
        mission_fields = [
            "payload_mass_kg", "cruise_speed_ms", "stall_speed_ms",
            "max_speed_ms", "range_km", "endurance_hr",
            "takeoff_run_m", "rate_of_climb_ms",
            "service_ceiling_m", "cruise_altitude_m",
        ]
        for fname in mission_fields:
            spec = get_field_spec(DesignBrief, fname)
            if spec:
                widget = ValidatedInput(spec)
                widget.set_value(getattr(self._store.state.sizing.brief, fname), block_signals=True)
                widget.value_changed.connect(
                    lambda val, f=fname: self._on_field_changed(f, val)
                )
                self._inputs[fname] = widget
                mission_form.addRow(widget)

        mission_box.layout().addLayout(mission_form)
        main.addWidget(mission_box)

        # ── Propulsion ────────────────────────────────────────────────────
        prop_box = self._make_group("Propulsion")
        prop_form = QFormLayout()
        prop_form.setSpacing(8)

        self._prop_combo = EnumCombo(PropulsionType)
        self._prop_combo.set_value(self._store.state.sizing.brief.propulsion_type, block_signals=True)
        self._prop_combo.enum_changed.connect(self._on_propulsion_changed)
        prop_form.addRow("Propulsion Type:", self._prop_combo)

        prop_fields = [
            "battery_energy_density_wh_kg",
            "battery_efficiency",
            "specific_fuel_consumption_g_wh",
        ]
        for fname in prop_fields:
            spec = get_field_spec(DesignBrief, fname)
            if spec:
                widget = ValidatedInput(spec)
                widget.set_value(getattr(self._store.state.sizing.brief, fname), block_signals=True)
                widget.value_changed.connect(
                    lambda val, f=fname: self._on_field_changed(f, val)
                )
                self._inputs[fname] = widget
                prop_form.addRow(widget)

        prop_box.layout().addLayout(prop_form)
        main.addWidget(prop_box)

        # ── Aero Coefficients ─────────────────────────────────────────────
        aero_box = self._make_group("Aerodynamic Coefficients")
        aero_layout = QVBoxLayout()
        aero_layout.setSpacing(12)

        brief = self._store.state.sizing.brief
        self._sliders: dict[str, SliderInput] = {}

        for fname, min_v, max_v, spec_label in [
            ("c_l_max", 0.5, 4.0, "CLmax"),
            ("c_d0", 0.001, 0.2, "CD₀"),
            ("oswald_efficiency", 0.1, 1.0, "Oswald e"),
            ("aspect_ratio", 2.0, 40.0, "Aspect Ratio AR"),
            ("prop_efficiency", 0.1, 1.0, "Propulsive Efficiency η"),
        ]:
            sv = getattr(brief, fname)
            slider = SliderInput(spec_label, min_v, max_v, sv)
            slider.value_changed.connect(
                lambda val, f=fname: self._on_field_changed(f, val)
            )
            self._sliders[fname] = slider
            aero_layout.addWidget(slider)

        aero_box.layout().addLayout(aero_layout)
        main.addWidget(aero_box)

        # ── Run button + status ───────────────────────────────────────────
        run_row = QHBoxLayout()
        run_row.addStretch()

        self._status_label = QLabel()
        self._status_label.setObjectName("InputLabel")
        run_row.addWidget(self._status_label)

        self._run_btn = QPushButton("▶  Run Sizing Analysis")
        self._run_btn.setFixedHeight(38)
        self._run_btn.setMinimumWidth(200)
        self._run_btn.clicked.connect(self._on_run)
        run_row.addWidget(self._run_btn)
        main.addLayout(run_row)
        main.addSpacerItem(QSpacerItem(0, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # ── Signals ───────────────────────────────────────────────────────
        self._store.brief_changed.connect(self._on_store_brief_changed)
        self._store.classification_changed.connect(self._refresh_class_combo)
        self._store.settings_changed.connect(self._on_settings_changed)
        self._store.project_loaded.connect(self._on_project_loaded)
        self._store.design_point_changed.connect(self._on_run_complete)
        self._store.weight_result_changed.connect(
            lambda: self._show_status("⏳  Weight converged, computing constraints…", 0)
        )

        # Apply current unit settings on startup
        self._apply_unit_converters()

    # ── Helpers ──────────────────────────────────────────────────────────

    def _make_group(self, title: str) -> QGroupBox:
        box = QGroupBox(title)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(12, 12, 12, 12)
        return box

    def _refresh_class_combo(self) -> None:
        self._class_combo.blockSignals(True)
        self._class_combo.clear()
        ranges = self._store.state.historical_data.classification_ranges
        current = self._store.state.sizing.brief.classification_name
        for i, cr in enumerate(ranges):
            self._class_combo.addItem(cr.name)
            if cr.name == current:
                self._class_combo.setCurrentIndex(i)
        self._class_combo.blockSignals(False)

    # ── Unit conversion wiring ───────────────────────────────────────────

    def _apply_unit_converters(self) -> None:
        """
        Wire current settings' unit enums into each ValidatedInput.
        Called once at startup and on every settings_changed signal.
        """
        settings = self._store.settings
        for fname, (settings_attr, to_disp_fn, to_si_fn) in _FIELD_UNIT_INFO.items():
            if fname not in self._inputs:
                continue
            unit_enum = getattr(settings, settings_attr, None)
            if unit_enum is None:
                continue

            # Build partial functions bound to the current unit enum
            to_display = lambda si_val, fn=to_disp_fn, u=unit_enum: fn(si_val, u)
            to_si      = lambda disp_val, fn=to_si_fn, u=unit_enum: fn(disp_val, u)
            label = UnitConverter.label(unit_enum)

            self._inputs[fname].set_unit_converter(to_display, to_si, label)

    # ── Event handlers ───────────────────────────────────────────────────

    def _on_class_changed(self, name: str) -> None:
        self._store.update_brief_field("classification_name", name)

    def _on_field_changed(self, field_name: str, si_value: float) -> None:
        """Called with SI values (ValidatedInput always emits SI)."""
        self._store.update_brief_field(field_name, si_value)
        # Validate
        errors = EntityValidator.validate(self._store.state.sizing.brief)
        error_map = {e.field_name: e.message for e in errors}
        for fn, widget in self._inputs.items():
            if fn in error_map:
                widget.set_error(error_map[fn])
            else:
                widget.clear_error()

    def _on_propulsion_changed(self, pt: PropulsionType) -> None:
        self._store.update_brief_field("propulsion_type", pt)

    def _on_run(self) -> None:
        from app.services.sizing_service import SizingService
        app_root = self.window()
        svc = getattr(app_root, "_sizing_service", None)
        if svc and isinstance(svc, SizingService):
            self._run_btn.setEnabled(False)
            self._run_btn.setText("⏳  Running…")
            self._show_status("Running sizing pipeline…", 0)
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()
            success = svc.run_now(save_to_history=True)
            if not success:
                self._show_status("❌  Sizing failed — check console.", 5000)
            self._run_btn.setEnabled(True)
            self._run_btn.setText("▶  Run Sizing Analysis")

    def _on_run_complete(self) -> None:
        dp = self._store.state.sizing.design_point
        if dp:
            self._show_status(
                f"✅  Done — MTOW = {dp.w_to_kg:.2f} kg  |  "
                f"S = {dp.wing_area_m2:.4f} m²  |  b = {dp.wingspan_m:.3f} m",
                8000,
            )

    def _show_status(self, text: str, timeout_ms: int) -> None:
        self._status_label.setText(text)
        if timeout_ms > 0:
            QTimer.singleShot(timeout_ms, lambda: self._status_label.setText(""))

    def _on_store_brief_changed(self) -> None:
        brief = self._store.state.sizing.brief
        idx = self._class_combo.findText(brief.classification_name)
        if idx >= 0:
            self._class_combo.blockSignals(True)
            self._class_combo.setCurrentIndex(idx)
            self._class_combo.blockSignals(False)

    def _on_settings_changed(self) -> None:
        """Recalculate all display values when units change."""
        self._apply_unit_converters()

    def _on_project_loaded(self) -> None:
        """Refresh all widgets when a full project is loaded from disk."""
        brief = self._store.state.sizing.brief
        # First apply unit converters (so set_value does correct conversion)
        self._apply_unit_converters()
        for fname, widget in self._inputs.items():
            widget.set_value(getattr(brief, fname), block_signals=True)
        for fname, slider in self._sliders.items():
            slider.set_value(getattr(brief, fname))
        self._prop_combo.set_value(brief.propulsion_type, block_signals=True)
        self._refresh_class_combo()
