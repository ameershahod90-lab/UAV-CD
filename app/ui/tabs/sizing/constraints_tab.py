"""
Constraints Tab — UAV-CD-APP
===============================
Interactive matching diagram: W/S vs T/W (or W/P).

All displayed values and axis labels use the current display units.
Click anywhere on the diagram to move the design point.
Reacts to settings_changed for live unit refresh.
"""

from __future__ import annotations

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

from app.core.display_converter import DisplayConverter
from app.core.entities import DesignPoint
from app.state.store import AppStore
from app.ui.widgets.result_card import ResultCard


class ConstraintsTab(QWidget):
    """Matching diagram (constraint plot) for the design space."""

    def __init__(self, store: AppStore, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._store: AppStore = store
        self._dp_scatter: Optional[pg.ScatterPlotItem] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Title ─────────────────────────────────────────────────────────
        title = QLabel("Constraint Analysis — Matching Diagram")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        hint = QLabel(
            "💡 Click anywhere on the diagram to move the design point. "
            "The sizing values update immediately."
        )
        hint.setObjectName("InputLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # ── Violation banner ──────────────────────────────────────────────
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

        self._plot.scene().sigMouseClicked.connect(self._on_plot_clicked)

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
        self._card_p    = ResultCard("Power / Thrust", unit="W")
        for card in [self._card_ws, self._card_load, self._card_wto,
                     self._card_s, self._card_b, self._card_p]:
            dp_row.addWidget(card)
        layout.addLayout(dp_row)

        # ── Signals ───────────────────────────────────────────────────────
        self._store.constraint_result_changed.connect(self._on_constraint_result)
        self._store.design_point_changed.connect(self._on_design_point)
        self._store.constraint_violation.connect(self._on_violations)
        self._store.settings_changed.connect(self._on_settings_changed)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _dc(self) -> DisplayConverter:
        return DisplayConverter(self._store.settings)

    # ── Plot rendering ───────────────────────────────────────────────────

    def _on_constraint_result(self) -> None:
        result = self._store.state.sizing.constraint_result
        if result is None:
            return

        dc = self._dc()

        self._plot.clear()
        self._dp_scatter = None
        self._plot.addLegend(offset=(-20, 20))

        # Axis labels with current units
        _, ws_unit = dc.wing_loading(0)
        if result.is_power_loading_mode:
            _, pl_unit = dc.power_loading(0)
            y_label = f"W/P [{pl_unit}]"
        else:
            y_label = "T/W [-]"

        self._plot.setLabel("bottom", f"Wing Loading W/S [{ws_unit}]")
        self._plot.setLabel("left", y_label)

        # Draw constraint curves (convert W/S axis to display units)
        for curve in result.curves:
            xs = np.asarray(curve.wing_loading_values)
            ys = np.asarray(curve.loading_values)
            # Convert axes to display units
            ws_display = np.array([dc.wing_loading(v)[0] for v in xs])
            if result.is_power_loading_mode:
                ld_display = np.array([dc.power_loading(v)[0] for v in ys])
            else:
                ld_display = ys
            pen = pg.mkPen(color=curve.color_hex, width=2)
            self._plot.plot(ws_display, ld_display, pen=pen, name=curve.name)

        # Stall vertical line
        stall_x_disp = dc.wing_loading(result.stall_ws_nm2)[0]
        y_max = max(
            (max(c.loading_values) for c in result.curves if c.loading_values),
            default=1.0,
        )
        if result.is_power_loading_mode:
            y_max_disp = dc.power_loading(y_max)[0]
        else:
            y_max_disp = y_max

        stall_pen = pg.mkPen(color="#e74c3c", width=2, style=Qt.PenStyle.DashLine)
        self._plot.plot(
            [stall_x_disp, stall_x_disp], [0, y_max_disp * 1.1],
            pen=stall_pen, name="Stall Limit",
        )

    def _on_design_point(self) -> None:
        dp = self._store.state.sizing.design_point
        if dp is None:
            return

        self._update_cards(dp)

        dc = self._dc()
        ws_disp = dc.wing_loading(dp.wing_loading_nm2)[0]
        cr = self._store.state.sizing.constraint_result
        is_power = cr.is_power_loading_mode if cr else True
        if is_power:
            ld_disp = dc.power_loading(dp.power_loading_nw)[0]
        else:
            ld_disp = dp.power_loading_nw

        self._place_marker(ws_disp, ld_disp)

    def _on_settings_changed(self) -> None:
        """Re-render everything with new units."""
        self._on_constraint_result()
        self._on_design_point()

    # ── Click-to-place ───────────────────────────────────────────────────

    def _on_plot_clicked(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        wr = self._store.state.sizing.weight_result
        if wr is None:
            return

        vb = self._plot.plotItem.vb
        scene_pos = event.scenePos()
        if not vb.sceneBoundingRect().contains(scene_pos):
            return

        data_pos = vb.mapSceneToView(scene_pos)
        click_ws_disp = float(data_pos.x())
        click_ld_disp = float(data_pos.y())

        # Convert display coordinates back to SI
        dc = self._dc()
        # Reverse wing_loading conversion
        from app.core.enums import AreaUnit
        if self._store.settings.area_unit == AreaUnit.FT2:
            new_ws_si = click_ws_disp / 0.020_885_4
        else:
            new_ws_si = click_ws_disp

        # Reverse power_loading conversion
        cr = self._store.state.sizing.constraint_result
        is_power = cr.is_power_loading_mode if cr else True
        from app.core.enums import PowerUnit
        if is_power:
            pu = self._store.settings.power_unit
            if pu == PowerUnit.HP:
                new_ld_si = click_ld_disp / 167.573
            elif pu == PowerUnit.KW:
                new_ld_si = click_ld_disp / 1000.0
            else:
                new_ld_si = click_ld_disp
        else:
            new_ld_si = click_ld_disp

        new_ws_si = max(1.0, new_ws_si)
        new_ld_si = max(1e-6, new_ld_si)

        self._move_design_point(new_ws_si, new_ld_si)

    def _move_design_point(self, new_ws: float, new_loading: float) -> None:
        wr = self._store.state.sizing.weight_result
        if wr is None:
            return

        _G = 9.80665
        w_to_kg = wr.w_to_kg
        weight_n = w_to_kg * _G

        wing_area = weight_n / new_ws if new_ws > 0 else 1.0
        brief = self._store.state.sizing.brief
        ar = brief.aspect_ratio
        wingspan = math.sqrt(wing_area * ar)

        cr = self._store.state.sizing.constraint_result
        is_power = cr.is_power_loading_mode if cr else True
        if is_power:
            engine_power = weight_n / new_loading if new_loading > 0 else 0.0
        else:
            engine_power = new_loading * weight_n

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
        self._store.update_design_point(new_dp)

    def _place_marker(self, x: float, y: float) -> None:
        if self._dp_scatter is not None:
            self._dp_scatter.setData(x=[x], y=[y])
        else:
            self._dp_scatter = pg.ScatterPlotItem(
                x=[x], y=[y],
                symbol="star",
                size=22,
                brush=pg.mkBrush("#f1c40f"),
                pen=pg.mkPen("#b38f00", width=1.5),
            )
            self._plot.addItem(self._dp_scatter)

    def _update_cards(self, dp: DesignPoint) -> None:
        dc = self._dc()

        ws_v, ws_u     = dc.wing_loading(dp.wing_loading_nm2)
        ld_v, ld_u     = dc.power_loading(dp.power_loading_nw)
        wto_v, wto_u   = dc.mass(dp.w_to_kg)
        s_v, s_u       = dc.area(dp.wing_area_m2)
        b_v, b_u       = dc.length(dp.wingspan_m)
        p_v, p_u       = dc.power(dp.engine_power_w)

        self._card_ws.set_value(ws_v, decimals=1);     self._card_ws.set_unit(ws_u)
        self._card_load.set_value(ld_v, decimals=5);    self._card_load.set_unit(ld_u)
        self._card_wto.set_value(wto_v, decimals=3);    self._card_wto.set_unit(wto_u)
        self._card_s.set_value(s_v, decimals=4);        self._card_s.set_unit(s_u)
        self._card_b.set_value(b_v, decimals=3);        self._card_b.set_unit(b_u)
        self._card_p.set_value(p_v, decimals=1);        self._card_p.set_unit(p_u)

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
