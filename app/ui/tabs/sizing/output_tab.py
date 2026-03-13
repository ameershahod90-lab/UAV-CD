"""
Output Tab — UAV-CD-APP
=========================
Final design point, scaling-law sanity checks, and multi-run comparison table.

All values shown in current display units from settings.
Reacts to settings_changed for live unit refresh.
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

from app.core.display_converter import DisplayConverter
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

        # Cards keyed by internal field name
        # (key, label, initial_unit, decimals)
        self._dp_field_defs: list[tuple[str, str, str, int]] = [
            ("w_to_kg",          "MTOW",           "kg",   3),
            ("wing_area_m2",     "Wing Area S",     "m²",   4),
            ("wingspan_m",       "Wingspan b",      "m",    3),
            ("aspect_ratio",     "AR",              "—",    2),
            ("engine_power_w",   "Power / Thrust",  "W",    1),
            ("wing_loading_nm2", "W/S",             "N/m²", 1),
        ]
        self._dp_cards: dict[str, ResultCard] = {}
        for i, (key, label, unit, _) in enumerate(self._dp_field_defs):
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

        self._run_table = QTableWidget(0, 8)
        self._run_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._run_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._run_table, stretch=1)

        # ── Connect ───────────────────────────────────────────────────────
        self._store.design_point_changed.connect(self._refresh_dp)
        self._store.run_history_changed.connect(self._refresh_history)
        self._store.settings_changed.connect(self._refresh_all)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _dc(self) -> DisplayConverter:
        return DisplayConverter(self._store.settings)

    def _refresh_all(self) -> None:
        self._refresh_dp()
        self._refresh_history()

    # ── Design point ─────────────────────────────────────────────────────

    def _refresh_dp(self) -> None:
        dp = self._store.state.sizing.design_point
        if dp is None:
            return

        dc = self._dc()

        # Map each field to its converted (value, unit, decimals)
        wto_v, wto_u     = dc.mass(dp.w_to_kg)
        area_v, area_u   = dc.area(dp.wing_area_m2)
        span_v, span_u   = dc.length(dp.wingspan_m)
        pwr_v, pwr_u     = dc.power(dp.engine_power_w)
        ws_v, ws_u       = dc.wing_loading(dp.wing_loading_nm2)

        display_map: dict[str, tuple[float, str, int]] = {
            "w_to_kg":          (wto_v,             wto_u,  3),
            "wing_area_m2":     (area_v,            area_u, 4),
            "wingspan_m":       (span_v,            span_u, 3),
            "aspect_ratio":     (dp.aspect_ratio,   "—",    2),
            "engine_power_w":   (pwr_v,             pwr_u,  1),
            "wing_loading_nm2": (ws_v,              ws_u,   1),
        }

        for key, (val, unit, dec) in display_map.items():
            card = self._dp_cards.get(key)
            if card:
                card.set_value(val, decimals=dec)
                card.set_unit(unit)

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

    # ── Run history ──────────────────────────────────────────────────────

    def _refresh_history(self) -> None:
        dc = self._dc()
        _, mass_u = dc.mass(0)
        _, area_u = dc.area(0)
        _, span_u = dc.length(0)
        _, pwr_u  = dc.power(0)

        # Update column headers with current units
        run_cols = [
            "Label", "Propulsion",
            f"Payload ({mass_u})", f"MTOW ({mass_u})",
            f"S ({area_u})", f"b ({span_u})",
            f"P/T ({pwr_u})", "Converged",
        ]
        self._run_table.setHorizontalHeaderLabels(run_cols)

        runs = self._store.state.sizing.run_history
        self._run_table.setRowCount(0)
        for run in runs:
            dp = run.design_point
            row = self._run_table.rowCount()
            self._run_table.insertRow(row)

            pay_v, _ = dc.mass(run.brief.payload_mass_kg)
            wto_v, _ = dc.mass(run.weight_result.w_to_kg) if run.weight_result else (0, "")
            s_v, _   = dc.area(dp.wing_area_m2) if dp else (0, "")
            b_v, _   = dc.length(dp.wingspan_m) if dp else (0, "")
            p_v, _   = dc.power(dp.engine_power_w) if dp else (0, "")

            cells = [
                run.label,
                run.brief.propulsion_type.label,
                f"{pay_v:.1f}",
                f"{wto_v:.3f}" if run.weight_result else "—",
                f"{s_v:.4f}" if dp else "—",
                f"{b_v:.3f}" if dp else "—",
                f"{p_v:.1f}" if dp else "—",
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
