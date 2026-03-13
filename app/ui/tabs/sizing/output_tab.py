"""
Output Tab — UAV-CD-APP
=========================
Final design point, scaling-law sanity checks, and multi-run comparison table.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.enums import SanityCheckStatus
from app.state.store import AppStore
from app.ui.widgets.result_card import ResultCard


_STATUS_ICONS = {
    SanityCheckStatus.PASS: "✅",
    SanityCheckStatus.WARN: "⚠️",
    SanityCheckStatus.FAIL: "❌",
}


class OutputTab(QWidget):
    """Design point summary, sanity checks, and run history comparison."""

    def __init__(self, store: AppStore, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._store: AppStore = store

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # ── Design Point Summary ──────────────────────────────────────────
        dp_title = QLabel("Optimal Design Point")
        dp_title.setObjectName("SectionTitle")
        layout.addWidget(dp_title)

        grid = QGridLayout()
        grid.setSpacing(10)
        self._dp_cards: dict[str, ResultCard] = {}
        fields = [
            ("w_to_kg",        "MTOW",        "kg",   3),
            ("wing_area_m2",   "Wing Area S", "m²",   4),
            ("wingspan_m",     "Wingspan b",  "m",    3),
            ("aspect_ratio",   "AR",          "—",    2),
            ("engine_power_w", "Power / Thrust", "W or N", 1),
            ("wing_loading_nm2", "W/S",       "N/m²", 1),
        ]
        for i, (key, label, unit, _) in enumerate(fields):
            card = ResultCard(label, unit=unit)
            self._dp_cards[key] = card
            grid.addWidget(card, i // 3, i % 3)

        layout.addLayout(grid)

        # ── Sanity Checks ─────────────────────────────────────────────────
        sanity_title = QLabel("Scaling-Law Sanity Checks")
        sanity_title.setObjectName("SectionTitle")
        layout.addWidget(sanity_title)

        self._sanity_table = QTableWidget(0, 6)
        self._sanity_table.setHorizontalHeaderLabels([
            "Parameter", "Computed", "Expected", "Band ±25%", "Status", ""
        ])
        self._sanity_table.horizontalHeader().setStretchLastSection(True)
        self._sanity_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._sanity_table.setMaximumHeight(160)
        layout.addWidget(self._sanity_table)

        # ── Multi-Run History ─────────────────────────────────────────────
        hist_hdr = QHBoxLayout()
        hist_title = QLabel("Run History Comparison")
        hist_title.setObjectName("SectionTitle")
        hist_hdr.addWidget(hist_title, stretch=1)
        clear_btn = QPushButton("Clear History")
        clear_btn.setObjectName("SecondaryButton")
        clear_btn.clicked.connect(self._clear_history)
        hist_hdr.addWidget(clear_btn)
        layout.addLayout(hist_hdr)

        run_cols = ["Label", "Propulsion", "Payload (kg)",
                    "MTOW (kg)", "S (m²)", "b (m)", "P/T (W|N)", "Converged"]
        self._run_table = QTableWidget(0, len(run_cols))
        self._run_table.setHorizontalHeaderLabels(run_cols)
        self._run_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._run_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._run_table, stretch=1)

        # ── Connect ───────────────────────────────────────────────────────
        self._store.design_point_changed.connect(self._on_design_point)
        self._store.run_history_changed.connect(self._on_run_history)

    # ── Internal ─────────────────────────────────────────────────────────

    def _on_design_point(self) -> None:
        dp = self._store.state.sizing.design_point
        if dp is None:
            return

        fields_map = {
            "w_to_kg":          (dp.w_to_kg,          3),
            "wing_area_m2":     (dp.wing_area_m2,      4),
            "wingspan_m":       (dp.wingspan_m,         3),
            "aspect_ratio":     (dp.aspect_ratio,       2),
            "engine_power_w":   (dp.engine_power_w,     1),
            "wing_loading_nm2": (dp.wing_loading_nm2,   1),
        }
        for key, (val, dec) in fields_map.items():
            if key in self._dp_cards:
                self._dp_cards[key].set_value(val, decimals=dec)

        # Sanity checks
        self._sanity_table.setRowCount(0)
        for check in dp.sanity_checks:
            row = self._sanity_table.rowCount()
            self._sanity_table.insertRow(row)
            items = [
                check.parameter_name,
                f"{check.computed_value:.3f} {check.unit}",
                f"{check.expected_value:.3f} {check.unit}",
                f"{check.band_low:.3f} – {check.band_high:.3f} {check.unit}",
                f"{_STATUS_ICONS.get(check.status, '')} {check.status.value.upper()}",
                "",
            ]
            for col, text in enumerate(items):
                self._sanity_table.setItem(row, col, QTableWidgetItem(text))

    def _on_run_history(self) -> None:
        runs = self._store.state.sizing.run_history
        self._run_table.setRowCount(0)
        for run in runs:
            dp = run.design_point
            row = self._run_table.rowCount()
            self._run_table.insertRow(row)
            cells = [
                run.label,
                run.brief.propulsion_type.label,
                f"{run.brief.payload_mass_kg:.1f}",
                f"{run.weight_result.w_to_kg:.3f}" if run.weight_result else "—",
                f"{dp.wing_area_m2:.4f}" if dp else "—",
                f"{dp.wingspan_m:.3f}" if dp else "—",
                f"{dp.engine_power_w:.1f}" if dp else "—",
                "✓" if run.weight_result and run.weight_result.converged else "✗",
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._run_table.setItem(row, col, item)

    def _clear_history(self) -> None:
        runs = self._store.state.sizing.run_history
        for i in range(len(runs) - 1, -1, -1):
            self._store.remove_sizing_run(i)
