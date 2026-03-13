"""
Constraints Tab — UAV-CD-APP
===============================
Interactive matching diagram: W/S vs T/W (or W/P).
Shows all constraint curves, the stall limit, the feasible region,
the design point, and constraint violation banners.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.core.entities import ConstraintViolation
from app.state.store import AppStore
from app.ui.widgets.result_card import ResultCard


class ConstraintsTab(QWidget):
    """Matching diagram (constraint plot) for the design space."""

    def __init__(self, store: AppStore, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._store: AppStore = store

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Title ─────────────────────────────────────────────────────────
        title = QLabel("Constraint Analysis — Matching Diagram")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        # ── Violation banner (hidden by default) ──────────────────────────
        self._banner = QLabel()
        self._banner.setObjectName("AlertBanner")
        self._banner.setWordWrap(True)
        self._banner.hide()
        layout.addWidget(self._banner)

        # ── Plot ──────────────────────────────────────────────────────────
        self._plot = pg.PlotWidget()
        self._plot.setBackground("transparent")
        self._plot.showGrid(x=True, y=True, alpha=0.25)
        self._plot.setMinimumHeight(350)
        self._plot.addLegend(offset=(-20, 20))
        layout.addWidget(self._plot, stretch=1)

        # ── Design point readout cards ────────────────────────────────────
        dp_label = QLabel("Design Point")
        dp_label.setObjectName("SectionTitle")
        layout.addWidget(dp_label)

        dp_row = QHBoxLayout()
        self._card_ws   = ResultCard("W/S", unit="N/m²")
        self._card_load = ResultCard("Loading", unit="—")
        self._card_wto  = ResultCard("MTOW", unit="kg")
        self._card_s    = ResultCard("Wing Area S", unit="m²")
        self._card_b    = ResultCard("Wingspan b", unit="m")
        self._card_p    = ResultCard("Power / Thrust", unit="W or N")
        for card in [self._card_ws, self._card_load, self._card_wto,
                     self._card_s, self._card_b, self._card_p]:
            dp_row.addWidget(card)
        layout.addLayout(dp_row)

        # ── Signal connections ────────────────────────────────────────────
        self._store.constraint_result_changed.connect(self._on_constraint_result)
        self._store.design_point_changed.connect(self._on_design_point)
        self._store.constraint_violation.connect(self._on_violations)

    # ── Internal ─────────────────────────────────────────────────────────

    def _on_constraint_result(self) -> None:
        result = self._store.state.sizing.constraint_result
        if result is None:
            return

        self._plot.clear()
        ws_arr = np.asarray(result.ws_range)

        # Y axis label
        y_label = "W/P [N/W]" if result.is_power_loading_mode else "T/W [-]"
        self._plot.setLabel("bottom", "Wing Loading W/S", units="N/m²")
        self._plot.setLabel("left", y_label)

        # Draw constraint curves
        for curve in result.curves:
            xs = np.asarray(curve.wing_loading_values)
            ys = np.asarray(curve.loading_values)
            pen = pg.mkPen(color=curve.color_hex, width=2)
            self._plot.plot(xs, ys, pen=pen, name=curve.name)

        # Stall vertical line
        stall_x = result.stall_ws_nm2
        y_max = max(
            (max(c.loading_values) for c in result.curves if c.loading_values),
            default=1.0
        )
        stall_pen = pg.mkPen(color="#e74c3c", width=2, style=Qt.PenStyle.DashLine)
        self._plot.plot(
            [stall_x, stall_x], [0, y_max * 1.1],
            pen=stall_pen, name="Stall Limit"
        )

    def _on_design_point(self) -> None:
        dp = self._store.state.sizing.design_point
        if dp is None:
            return

        cr = self._store.state.sizing.constraint_result

        # Overlay design point marker
        is_power = cr.is_power_loading_mode if cr else True
        load_label = "W/P" if is_power else "T/W"
        load_unit  = "N/W" if is_power else "N/N"

        self._card_ws.set_value(dp.wing_loading_nm2, decimals=1)
        self._card_load.set_value(dp.power_loading_nw, decimals=5)
        self._card_wto.set_value(dp.w_to_kg, decimals=3)
        self._card_s.set_value(dp.wing_area_m2, decimals=4)
        self._card_b.set_value(dp.wingspan_m, decimals=3)
        self._card_p.set_value(dp.engine_power_w, decimals=1)

        # Add star marker on plot
        star = pg.ScatterPlotItem(
            x=[dp.wing_loading_nm2],
            y=[dp.power_loading_nw],
            symbol="star",
            size=18,
            brush=pg.mkBrush("#f1c40f"),
            pen=pg.mkPen(None),
        )
        self._plot.addItem(star)

    def _on_violations(self, violations: list) -> None:
        if not violations:
            self._banner.hide()
            return
        lines = [
            f"⚠  {v.description}" if hasattr(v, "description") else str(v)
            for v in violations
        ]
        self._banner.setText("\n".join(lines))
        self._banner.show()
