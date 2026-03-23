"""
General Input Tab — UAV-CD-APP
================================
Replaced the original monolithic InputTab with two focused tabs.
This tab (GeneralTab) handles:
  • Propulsion type selection + dynamic battery/fuel sub-groups
  • Aerodynamic coefficients (sliders) with live CL_cruise, (L/D)_max readouts
  • Target classification selector
  • Run Sizing button

Design:
  - 'Range' and 'Endurance' have moved to the Mission tab (via segments).
  - CL_cruise and (L/D)_max are computed from current slider state and shown
    as read-only info cards that update live — fixing the previous confusion
    about what CL_cruise meant.
  - Propulsion-specific groups (battery / fuel) show/hide exactly as before.
"""

from __future__ import annotations

import math
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
# Field → unit-conversion mapping  (same as previous InputTab)
# ---------------------------------------------------------------------------

def _make_converters(attr: str, to_d: Callable, to_si: Callable):
    return (attr, to_d, to_si)

_FIELD_UNIT_INFO: dict[str, tuple] = {
    "payload_mass_kg":   _make_converters("mass_unit",     UnitConverter.mass_to_display,     UnitConverter.mass_to_si),
    "cruise_speed_ms":   _make_converters("speed_unit",    UnitConverter.speed_to_display,    UnitConverter.speed_to_si),
    "stall_speed_ms":    _make_converters("speed_unit",    UnitConverter.speed_to_display,    UnitConverter.speed_to_si),
    "max_speed_ms":      _make_converters("speed_unit",    UnitConverter.speed_to_display,    UnitConverter.speed_to_si),
    "rate_of_climb_ms":  _make_converters("speed_unit",    UnitConverter.speed_to_display,    UnitConverter.speed_to_si),
    "service_ceiling_m": _make_converters("altitude_unit", UnitConverter.altitude_to_display, UnitConverter.altitude_to_si),
    "cruise_altitude_m": _make_converters("altitude_unit", UnitConverter.altitude_to_display, UnitConverter.altitude_to_si),
    "takeoff_run_m":     _make_converters("altitude_unit", UnitConverter.altitude_to_display, UnitConverter.altitude_to_si),
}


class GeneralTab(QWidget):
    """Propulsion, aerodynamic coefficients and Run button."""

    def __init__(self, store: AppStore, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._store: AppStore = store
        self._inputs: dict[str, ValidatedInput] = {}
        self._sliders: dict[str, SliderInput]  = {}

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

        self._build_propulsion(main)
        self._build_aero(main)
        self._build_classification(main)
        self._build_run_button(main)
        main.addSpacerItem(QSpacerItem(0, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # ── Status label ──────────────────────────────────────────────────
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setObjectName("InputLabel")
        main.addWidget(self._status_label)

        # ── Signals ───────────────────────────────────────────────────────
        self._store.brief_changed.connect(self._on_store_brief_changed)
        self._store.settings_changed.connect(self._on_settings_changed)
        self._store.design_point_changed.connect(self._on_run_complete)
        self._store.project_loaded.connect(self._on_project_loaded)
        self._apply_unit_converters()

    # ── Build helpers ─────────────────────────────────────────────────────

    def _make_group(self, title: str) -> QGroupBox:
        box = QGroupBox(title)
        QVBoxLayout(box).setContentsMargins(12, 12, 12, 12)
        return box

    def _build_propulsion(self, main: QVBoxLayout) -> None:
        prop_box = self._make_group("Propulsion")
        prop_layout = QVBoxLayout()
        prop_layout.setSpacing(8)

        type_row = QFormLayout()
        type_row.setSpacing(8)
        self._prop_combo = EnumCombo(PropulsionType)
        self._prop_combo.set_value(self._store.state.sizing.brief.propulsion_type, block_signals=True)
        self._prop_combo.enum_changed.connect(self._on_propulsion_changed)
        type_row.addRow("Propulsion Type:", self._prop_combo)
        prop_layout.addLayout(type_row)

        # Battery sub-group
        self._battery_group = QGroupBox("⚡ Battery Parameters")
        self._battery_group.setObjectName("PropSubGroup")
        bat_form = QFormLayout(self._battery_group)
        bat_form.setSpacing(8)
        for fname in ["battery_energy_density_wh_kg", "battery_efficiency"]:
            spec = get_field_spec(DesignBrief, fname)
            if spec:
                w = ValidatedInput(spec)
                w.set_value(getattr(self._store.state.sizing.brief, fname), block_signals=True)
                w.value_changed.connect(lambda val, f=fname: self._on_field_changed(f, val))
                self._inputs[fname] = w
                bat_form.addRow(w)
        prop_layout.addWidget(self._battery_group)

        # Fuel sub-group
        self._fuel_group = QGroupBox("⛽ Fuel Parameters")
        self._fuel_group.setObjectName("PropSubGroup")
        fuel_form = QFormLayout(self._fuel_group)
        fuel_form.setSpacing(8)
        sfc_spec = get_field_spec(DesignBrief, "specific_fuel_consumption_g_wh")
        if sfc_spec:
            sfc_w = ValidatedInput(sfc_spec)
            sfc_w.set_value(self._store.state.sizing.brief.specific_fuel_consumption_g_wh, block_signals=True)
            sfc_w.value_changed.connect(lambda val: self._on_field_changed("specific_fuel_consumption_g_wh", val))
            self._inputs["specific_fuel_consumption_g_wh"] = sfc_w
            fuel_form.addRow(sfc_w)
        prop_layout.addWidget(self._fuel_group)

        prop_box.layout().addLayout(prop_layout)
        main.addWidget(prop_box)
        self._update_propulsion_visibility(self._store.state.sizing.brief.propulsion_type)

    def _build_aero(self, main: QVBoxLayout) -> None:
        aero_box = self._make_group("Aerodynamic Coefficients")
        aero_layout = QVBoxLayout()
        aero_layout.setSpacing(12)

        brief = self._store.state.sizing.brief
        for fname, lo, hi, lbl in [
            ("c_l_max",           0.5, 4.0,  "CLmax"),
            ("c_d0",              0.001, 0.2, "CD₀"),
            ("oswald_efficiency", 0.1, 1.0,  "Oswald e"),
            ("aspect_ratio",      2.0, 40.0,  "Aspect Ratio AR"),
            ("prop_efficiency",   0.1, 1.0,  "Propulsive Efficiency η"),
        ]:
            sv = getattr(brief, fname)
            sl = SliderInput(label=lbl, min_val=lo, max_val=hi, initial=sv)
            sl.value_changed.connect(lambda val, f=fname: self._on_slider_changed(f, val))
            self._sliders[fname] = sl
            aero_layout.addWidget(sl)

        # ── Read-only aerodynamic readouts ────────────────────────────────
        readout_row = QHBoxLayout()
        readout_row.setSpacing(16)

        self._cl_label = QLabel("CL✱ = —")
        self._cl_label.setObjectName("AeroReadout")
        self._cl_label.setToolTip(
            "CL* = √(CD0 / k)  — the lift coefficient that maximises L/D.\n"
            "All Breguet range/endurance calculations use this value."
        )
        self._ld_label = QLabel("(L/D)max = —")
        self._ld_label.setObjectName("AeroReadout")
        self._ld_label.setToolTip("Maximum lift-to-drag ratio = CL* / (2·CD0)")

        for lbl in [self._cl_label, self._ld_label]:
            lbl.setStyleSheet("font-weight: 600; color: #7c6af7; font-size: 13px;")
            readout_row.addWidget(lbl)
        readout_row.addStretch()

        aero_layout.addLayout(readout_row)
        aero_box.layout().addLayout(aero_layout)
        main.addWidget(aero_box)
        self._refresh_aero_readouts()

    def _build_classification(self, main: QVBoxLayout) -> None:
        class_box = self._make_group("Target Classification")
        class_layout = QFormLayout()
        class_layout.setSpacing(8)

        self._class_combo = QComboBox()
        self._refresh_class_combo()
        self._class_combo.currentTextChanged.connect(self._on_class_changed)
        self._store.classification_changed.connect(self._refresh_class_combo)
        class_layout.addRow("Classification:", self._class_combo)
        class_box.layout().addLayout(class_layout)
        main.addWidget(class_box)

    def _build_run_button(self, main: QVBoxLayout) -> None:
        run_row = QHBoxLayout()
        self._run_btn = QPushButton("▶  Run Sizing Analysis")
        self._run_btn.setFixedHeight(38)
        self._run_btn.setMinimumWidth(200)
        self._run_btn.clicked.connect(self._on_run)
        run_row.addWidget(self._run_btn)
        main.addLayout(run_row)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _refresh_aero_readouts(self) -> None:
        brief = self._store.state.sizing.brief
        k = 1.0 / (math.pi * brief.oswald_efficiency * brief.aspect_ratio)
        cl_star = math.sqrt(brief.c_d0 / k) if k > 0 else 0.0
        ld_max = cl_star / (2.0 * brief.c_d0) if brief.c_d0 > 0 else 0.0
        self._cl_label.setText(f"CL✱ = {cl_star:.4f}")
        self._ld_label.setText(f"(L/D)max = {ld_max:.2f}")

    def _refresh_class_combo(self) -> None:
        ranges = self._store.state.historical_data.classification_ranges
        current = self._store.state.sizing.brief.classification_name
        self._class_combo.blockSignals(True)
        self._class_combo.clear()
        for r in ranges:
            self._class_combo.addItem(r.name)
        idx = self._class_combo.findText(current)
        if idx >= 0:
            self._class_combo.setCurrentIndex(idx)
        self._class_combo.blockSignals(False)

    def _apply_unit_converters(self) -> None:
        settings = self._store.settings
        for fname, widget in self._inputs.items():
            if fname not in _FIELD_UNIT_INFO:
                continue
            attr, to_d, to_si = _FIELD_UNIT_INFO[fname]
            unit_enum = getattr(settings, attr)
            unit_name = unit_enum.value
            widget.set_unit_converter(
                lambda v, u=unit_enum, fn=to_d: fn(v, u),
                lambda v, u=unit_enum, fn=to_si: fn(v, u),
                unit_name,
            )
            si_val = getattr(self._store.state.sizing.brief, fname, None)
            if si_val is not None:
                widget.set_value(si_val, block_signals=True)

    def _show_status(self, msg: str, timeout_ms: int = 4000) -> None:
        self._status_label.setText(msg)
        if timeout_ms > 0:
            QTimer.singleShot(timeout_ms, lambda: self._status_label.setText(""))

    def _update_propulsion_visibility(self, pt: PropulsionType) -> None:
        self._battery_group.setVisible(pt.is_electric)
        self._fuel_group.setVisible(pt.uses_fuel)

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_field_changed(self, field: str, val: float) -> None:
        self._store.update_brief_field(field, val)

    def _on_slider_changed(self, field: str, val: float) -> None:
        self._store.update_brief_field(field, val)
        self._refresh_aero_readouts()

    def _on_propulsion_changed(self, pt: PropulsionType) -> None:
        self._store.update_brief_field("propulsion_type", pt)
        self._update_propulsion_visibility(pt)

    def _on_class_changed(self, name: str) -> None:
        self._store.update_brief_field("classification_name", name)

    def _on_store_brief_changed(self) -> None:
        brief = self._store.state.sizing.brief
        idx = self._class_combo.findText(brief.classification_name)
        if idx >= 0:
            self._class_combo.blockSignals(True)
            self._class_combo.setCurrentIndex(idx)
            self._class_combo.blockSignals(False)
        self._refresh_aero_readouts()

    def _on_settings_changed(self) -> None:
        self._apply_unit_converters()

    def _on_project_loaded(self) -> None:
        brief = self._store.state.sizing.brief
        self._apply_unit_converters()
        for fname, widget in self._inputs.items():
            widget.set_value(getattr(brief, fname), block_signals=True)
        for fname, slider in self._sliders.items():
            slider.set_value(getattr(brief, fname))
        self._prop_combo.set_value(brief.propulsion_type, block_signals=True)
        self._update_propulsion_visibility(brief.propulsion_type)
        self._refresh_class_combo()
        self._refresh_aero_readouts()

    def _on_run(self) -> None:
        from app.services.sizing_service import SizingService
        svc = getattr(self.window(), "_sizing_service", None)
        if svc and isinstance(svc, SizingService):
            self._run_btn.setEnabled(False)
            self._run_btn.setText("⏳  Running…")
            self._show_status("Running sizing pipeline…", 0)
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()
            ok = svc.run_now(save_to_history=True)
            self._run_btn.setEnabled(True)
            self._run_btn.setText("▶  Run Sizing Analysis")
            if not ok:
                self._show_status("❌  Sizing failed — check inputs.", 6000)

    def _on_run_complete(self) -> None:
        from app.core.display_converter import DisplayConverter
        dp = self._store.state.sizing.design_point
        if dp is None:
            return
        dc = DisplayConverter(self._store.settings)
        mtow_v, mtow_u = dc.mass(dp.w_to_kg)
        s_v, s_u       = dc.area(dp.wing_area_m2)
        b_v, b_u       = dc.length(dp.wingspan_m)
        self._show_status(
            f"✅  MTOW = {mtow_v:.2f} {mtow_u} | "
            f"S = {s_v:.3f} {s_u} | "
            f"b = {b_v:.2f} {b_u}",
            8000,
        )
