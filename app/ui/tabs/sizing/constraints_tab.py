"""
Constraints Tab — UAV-CD-APP
===============================
Interactive matching diagram: W/S vs T/W (or W/P).
Shows all constraint curves, the stall limit, the feasible region,
the design point, and constraint violation banners.

DRAGGABLE DESIGN POINT: The user can click-and-drag the gold star
marker to any feasible position on the diagram. When released, the
app recomputes wing geometry from the new W/S and W/P values and
updates the AppStore.
"""

from __future__ import annotations

import dataclasses
import math
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

from app.core.entities import (
    ConstraintResult,
    DesignPoint,
    SanityCheck,
)
from app.core.enums import SanityCheckStatus
from app.state.store import AppStore
from app.ui.widgets.result_card import ResultCard


class _DraggablePoint(pg.ScatterPlotItem):
    """
    A ScatterPlotItem that can be dragged with the mouse.
    Emits sigPointMoved(x, y) when the user releases the mouse.
    """

    def __init__(self, x: float, y: float, **kwargs) -> None:
        super().__init__(x=[x], y=[y], **kwargs)
        self._dragging: bool = False
        self._callback: Optional[object] = None

    def set_on_moved(self, callback) -> None:
        self._callback = callback

    def mouseDragEvent(self, ev) -> None:
        if ev.button() != Qt.MouseButton.LeftButton:
            ev.ignore()
            return

        ev.accept()
        if ev.isStart():
            self._dragging = True
        elif ev.isFinish():
            self._dragging = False
            # Get position in data coordinates
            pos = ev.pos()
            view_box = self.parentItem()
            if view_box is not None:
                scene_pos = ev.scenePos()
                data_pos = view_box.mapSceneToView(scene_pos)
                new_x, new_y = float(data_pos.x()), float(data_pos.y())
                # Clamp to positive
                new_x = max(1.0, new_x)
                new_y = max(1e-6, new_y)
                self.setData(x=[new_x], y=[new_y])
                if self._callback:
                    self._callback(new_x, new_y)
        else:
            if self._dragging:
                pos = ev.pos()
                view_box = self.parentItem()
                if view_box is not None:
                    scene_pos = ev.scenePos()
                    data_pos = view_box.mapSceneToView(scene_pos)
                    self.setData(x=[float(data_pos.x())], y=[float(data_pos.y())])


class ConstraintsTab(QWidget):
    """Matching diagram (constraint plot) for the design space."""

    def __init__(self, store: AppStore, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._store: AppStore = store
        self._dp_marker: Optional[_DraggablePoint] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Title ─────────────────────────────────────────────────────────
        title = QLabel("Constraint Analysis — Matching Diagram")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        # Instruction hint
        hint = QLabel(
            "💡 Drag the ★ design point marker to explore alternative locations within the feasible region."
        )
        hint.setObjectName("InputLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

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
        self._card_load = ResultCard("W/P or T/W", unit="—")
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
        self._dp_marker = None  # cleared with plot

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
            default=1.0,
        )
        stall_pen = pg.mkPen(color="#e74c3c", width=2, style=Qt.PenStyle.DashLine)
        self._plot.plot(
            [stall_x, stall_x], [0, y_max * 1.1],
            pen=stall_pen, name="Stall Limit",
        )

    def _on_design_point(self) -> None:
        dp = self._store.state.sizing.design_point
        if dp is None:
            return

        self._update_cards(dp)

        # Remove old marker if exists
        if self._dp_marker is not None:
            self._plot.removeItem(self._dp_marker)

        # Create draggable star marker
        self._dp_marker = _DraggablePoint(
            dp.wing_loading_nm2,
            dp.power_loading_nw,
            symbol="star",
            size=22,
            brush=pg.mkBrush("#f1c40f"),
            pen=pg.mkPen("#b38f00", width=1.5),
        )
        self._dp_marker.set_on_moved(self._on_dp_dragged)
        self._plot.addItem(self._dp_marker)

    def _on_dp_dragged(self, new_ws: float, new_loading: float) -> None:
        """
        Called when the user releases the dragged design point marker.
        Recomputes geometry from the new W/S and W/P (or T/W) values.
        """
        wr = self._store.state.sizing.weight_result
        if wr is None:
            return

        w_to_kg = wr.w_to_kg
        _G = 9.80665
        weight_n = w_to_kg * _G

        # Derive wing geometry from new W/S
        wing_area = weight_n / new_ws if new_ws > 0 else 1.0
        brief = self._store.state.sizing.brief
        ar = brief.aspect_ratio
        wingspan = math.sqrt(wing_area * ar)

        # Derive power / thrust
        cr = self._store.state.sizing.constraint_result
        is_power = cr.is_power_loading_mode if cr else True
        if is_power:
            # new_loading = W/P [N/W], so P = W / (W/P)
            engine_power = weight_n / new_loading if new_loading > 0 else 0.0
        else:
            # T/W, so T = (T/W) * W
            engine_power = new_loading * weight_n

        # Create updated design point (no sanity checks for manual placement)
        new_dp = DesignPoint(
            wing_loading_nm2=new_ws,
            power_loading_nw=new_loading,
            w_to_kg=w_to_kg,
            wing_area_m2=wing_area,
            wingspan_m=wingspan,
            aspect_ratio=ar,
            engine_power_w=engine_power,
            sanity_checks=(),
        )

        self._update_cards(new_dp)
        # Update store (this will re-emit design_point_changed, but we've
        # already placed the marker so _on_design_point will just refresh cards)
        self._store.update_design_point(new_dp)

    def _update_cards(self, dp: DesignPoint) -> None:
        """Populate result cards from a DesignPoint."""
        self._card_ws.set_value(dp.wing_loading_nm2, decimals=1)
        self._card_load.set_value(dp.power_loading_nw, decimals=5)
        self._card_wto.set_value(dp.w_to_kg, decimals=3)
        self._card_s.set_value(dp.wing_area_m2, decimals=4)
        self._card_b.set_value(dp.wingspan_m, decimals=3)
        self._card_p.set_value(dp.engine_power_w, decimals=1)

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
