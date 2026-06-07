"""
Settings Tab — UAV-CD-APP
============================
User preferences: theme, units, solver, database path.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

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
from app.core.units import cascade_unit_system
from app.state.store import AppStore
from app.ui.widgets.checkmark_box import CheckmarkBox
from app.ui.widgets.enum_combo import EnumCombo

import dataclasses


class SettingsTab(QWidget):
    """Global application settings form."""

    def __init__(self, store: AppStore, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._store: AppStore = store

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        content = QWidget()
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        main = QVBoxLayout(content)
        main.setContentsMargins(24, 24, 24, 24)
        main.setSpacing(20)

        # Title
        title = QLabel("Application Settings")
        title.setObjectName("SectionTitle")
        main.addWidget(title)

        s = store.settings

        # ── Appearance ────────────────────────────────────────────────────
        appear_box = QGroupBox("Appearance")
        appear_form = QFormLayout(appear_box)
        self._theme_combo = EnumCombo(ThemeOption)
        self._theme_combo.set_value(s.theme, block_signals=True)
        appear_form.addRow("Theme:", self._theme_combo)
        main.addWidget(appear_box)

        # ── Units ─────────────────────────────────────────────────────────
        units_box = QGroupBox("Unit System")
        units_form = QFormLayout(units_box)

        self._unit_sys  = EnumCombo(UnitSystem)
        self._speed_u   = EnumCombo(SpeedUnit)
        self._alt_u     = EnumCombo(AltitudeUnit)
        self._mass_u    = EnumCombo(MassUnit)
        self._area_u    = EnumCombo(AreaUnit)
        self._power_u   = EnumCombo(PowerUnit)
        self._force_u   = EnumCombo(ForceUnit)

        self._unit_sys.set_value(s.unit_system, block_signals=True)
        self._speed_u.set_value(s.speed_unit, block_signals=True)
        self._alt_u.set_value(s.altitude_unit, block_signals=True)
        self._mass_u.set_value(s.mass_unit, block_signals=True)
        self._area_u.set_value(s.area_unit, block_signals=True)
        self._power_u.set_value(s.power_unit, block_signals=True)
        self._force_u.set_value(s.force_unit, block_signals=True)

        units_form.addRow("Unit System:", self._unit_sys)
        units_form.addRow("Speed:", self._speed_u)
        units_form.addRow("Altitude:", self._alt_u)
        units_form.addRow("Mass:", self._mass_u)
        units_form.addRow("Area:", self._area_u)
        units_form.addRow("Power:", self._power_u)
        units_form.addRow("Force:", self._force_u)
        main.addWidget(units_box)

        # ── Solver ────────────────────────────────────────────────────────
        solver_box = QGroupBox("Solver Configuration")
        solver_form = QFormLayout(solver_box)
        self._max_iter = QSpinBox()
        self._max_iter.setRange(10, 10_000)
        self._max_iter.setValue(s.max_iterations)
        solver_form.addRow("Max Iterations:", self._max_iter)
        self._auto_calc = CheckmarkBox("Auto-recalculate on input change")
        self._auto_calc.setChecked(s.auto_recalculate)
        solver_form.addRow(self._auto_calc)
        main.addWidget(solver_box)

        # ── Sensitivity Studio ────────────────────────────────────────────
        sens_box = QGroupBox("Sensitivity Studio")
        sens_form = QFormLayout(sens_box)

        self._sens_critical = QDoubleSpinBox()
        self._sens_critical.setRange(0.0, 100.0)
        self._sens_critical.setDecimals(1)
        self._sens_critical.setSingleStep(1.0)
        self._sens_critical.setSuffix(" %")
        self._sens_critical.setValue(s.sens_severity_critical_pct)
        self._sens_critical.setToolTip(
            "Constraint margins below this percentage are flagged RED "
            "(critical). Default 10 %.",
        )

        self._sens_tight = QDoubleSpinBox()
        self._sens_tight.setRange(0.0, 100.0)
        self._sens_tight.setDecimals(1)
        self._sens_tight.setSingleStep(1.0)
        self._sens_tight.setSuffix(" %")
        self._sens_tight.setValue(s.sens_severity_tight_pct)
        self._sens_tight.setToolTip(
            "Margins between the critical threshold and this value are "
            "AMBER (tight); at or above are GREEN (ok). Default 30 %.",
        )

        sens_form.addRow("Critical margin:", self._sens_critical)
        sens_form.addRow("Tight margin:",    self._sens_tight)
        sens_help = QLabel(
            "<i>Δ % and Sweep N points are configured on the "
            "Sensitivity sub-tab.</i>"
        )
        sens_help.setWordWrap(True)
        sens_form.addRow(sens_help)
        main.addWidget(sens_box)

        # ── Database ──────────────────────────────────────────────────────
        db_box = QGroupBox("Historical Database")
        db_form = QFormLayout(db_box)
        db_row = QHBoxLayout()
        self._db_path = QLineEdit(s.database_path)
        self._db_path.setReadOnly(True)
        browse_btn = QPushButton("Browse…")
        browse_btn.setObjectName("SecondaryButton")
        browse_btn.clicked.connect(self._browse_db)
        db_row.addWidget(self._db_path, stretch=1)
        db_row.addWidget(browse_btn)
        db_form.addRow("CSV Path:", db_row)
        self._use_hist = CheckmarkBox(
            "Use historical data for regression (geometry scaling laws)"
        )
        self._use_hist.setToolTip(
            "When unchecked, all regression coefficients use textbook values.\n"
            "Useful when the database is small or incomplete."
        )
        self._use_hist.setChecked(s.use_historical_data)
        db_form.addRow(self._use_hist)
        main.addWidget(db_box)

        # ── Save button + status ───────────────────────────────────────────
        save_row = QHBoxLayout()
        save_row.addStretch()
        self._save_status = QLabel()
        self._save_status.setObjectName("InputLabel")
        save_row.addWidget(self._save_status)
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self._save_settings)
        save_row.addWidget(save_btn)
        main.addLayout(save_row)

        # Cascade on unit system change
        self._unit_sys.enum_changed.connect(self._on_unit_system_changed)

    # ── Internal ─────────────────────────────────────────────────────────

    def _on_unit_system_changed(self, us: UnitSystem) -> None:
        """Cascade unit system → individual unit combos."""
        s = dataclasses.replace(self._store.settings, unit_system=us)
        cascaded = cascade_unit_system(s)
        self._speed_u.set_value(cascaded.speed_unit, block_signals=True)
        self._alt_u.set_value(cascaded.altitude_unit, block_signals=True)
        self._mass_u.set_value(cascaded.mass_unit, block_signals=True)
        self._area_u.set_value(cascaded.area_unit, block_signals=True)
        self._power_u.set_value(cascaded.power_unit, block_signals=True)
        self._force_u.set_value(cascaded.force_unit, block_signals=True)

    def _browse_db(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Database CSV", "", "CSV Files (*.csv);;All Files (*)"
        )
        if path:
            self._db_path.setText(path)

    def _save_settings(self) -> None:
        from PyQt6.QtCore import QTimer
        s = self._store.settings
        # Enforce critical < tight; if the user inverted them, swap so
        # the severity classifier doesn't break.
        crit = float(self._sens_critical.value())
        tight = float(self._sens_tight.value())
        if tight <= crit:
            tight = crit + 1.0
            self._sens_tight.blockSignals(True)
            self._sens_tight.setValue(tight)
            self._sens_tight.blockSignals(False)
        new_s = dataclasses.replace(
            s,
            theme=self._theme_combo.current_enum(),
            unit_system=self._unit_sys.current_enum(),
            speed_unit=self._speed_u.current_enum(),
            altitude_unit=self._alt_u.current_enum(),
            mass_unit=self._mass_u.current_enum(),
            area_unit=self._area_u.current_enum(),
            power_unit=self._power_u.current_enum(),
            force_unit=self._force_u.current_enum(),
            max_iterations=self._max_iter.value(),
            auto_recalculate=self._auto_calc.isChecked(),
            database_path=self._db_path.text(),
            use_historical_data=self._use_hist.isChecked(),
            sens_severity_critical_pct=crit,
            sens_severity_tight_pct=tight,
        )
        self._store.update_settings(new_s)
        self._save_status.setText("✅  Settings saved")
        QTimer.singleShot(3000, lambda: self._save_status.setText(""))
