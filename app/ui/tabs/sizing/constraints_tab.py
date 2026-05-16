"""
Constraints Tab — UAV-CD-APP
===============================
Interactive matching diagram: W/S vs T/W (or W/P).

All displayed values and axis labels use the current display units.
Click anywhere on the diagram to move the design point.
Reacts to settings_changed for live unit refresh.

Violation alerts:
  Every time the user clicks a new design point, check_design_point() is
  called on the ConstraintAnalyzer with the new coordinates.  If any
  constraint is violated a coloured banner is shown beneath the plot with
  one line per violation.  Green "feasible" confirmation shown otherwise.
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
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.constraints import ConstraintAnalyzer
from app.core.display_converter import DisplayConverter
from app.core.entities import ConstraintViolation, DesignPoint
from app.core.enums import ConstraintSeverity
from app.state.store import AppStore
from app.ui.widgets.result_card import ResultCard

_G = 9.80665


class ConstraintsTab(QWidget):
    """Matching diagram (constraint plot) for the design space."""

    def __init__(self, store: AppStore, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._store: AppStore = store
        self._dp_scatter: Optional[pg.ScatterPlotItem] = None

        # Scroll wrapper
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Title ─────────────────────────────────────────────────────────
        title = QLabel("Constraint Analysis — Matching Diagram")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        hint = QLabel(
            "Click anywhere on the diagram to move the design point. "
            "Sizing values update immediately."
        )
        hint.setObjectName("InputLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # ── Violation / feasibility banner ────────────────────────────────
        self._banner = QLabel()
        self._banner.setWordWrap(True)
        self._banner.hide()
        layout.addWidget(self._banner)

        # ── Plot ──────────────────────────────────────────────────────────
        self._plot = pg.PlotWidget()
        self._plot.setBackground("transparent")
        self._plot.showGrid(x=True, y=True, alpha=0.25)
        self._plot.setMinimumHeight(360)
        self._plot.addLegend(offset=(-20, 20))
        layout.addWidget(self._plot, stretch=1)
        self._plot.scene().sigMouseClicked.connect(self._on_plot_clicked)

        # ── Design point readout cards ────────────────────────────────────
        dp_label = QLabel("Design Point")
        dp_label.setObjectName("SectionTitle")
        layout.addWidget(dp_label)

        is_power = self._store.state.sizing.brief.propulsion_type.is_power_mode
        dp_row = QHBoxLayout()
        self._card_ws   = ResultCard("W/S",   unit="N/m²")
        self._card_load = ResultCard("W/P" if is_power else "T/W",
                                     unit=self._dc().power_loading(0)[1] if is_power
                                          else self._dc().force_loading(0)[1])
        self._card_wto  = ResultCard("MTOW",       unit="kg")
        self._card_s    = ResultCard("Wing Area S", unit="m²")
        self._card_b    = ResultCard("Wingspan b",  unit="m")
        self._card_p    = ResultCard("Power" if is_power else "Thrust",
                                     unit=self._dc().power(0)[1] if is_power
                                          else self._dc().force(0)[1])
        for card in [self._card_ws, self._card_load, self._card_wto,
                     self._card_s, self._card_b, self._card_p]:
            dp_row.addWidget(card)
        layout.addLayout(dp_row)

        # ── Signals ───────────────────────────────────────────────────────
        self._store.constraint_result_changed.connect(self._on_constraint_result)
        self._store.design_point_changed.connect(self._on_design_point)
        self._store.constraint_violation.connect(self._on_violations)
        self._store.settings_changed.connect(self._on_settings_changed)
        self._store.brief_changed.connect(self._on_brief_changed)

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

        _, ws_unit = dc.wing_loading(0)
        if result.is_power_loading_mode:
            _, pl_unit = dc.power_loading(0)
            y_label = f"W/P [{pl_unit}]"
        else:
            _, fl_unit = dc.force_loading(0)
            y_label = f"T/W [{fl_unit}]"

        self._plot.setLabel("bottom", f"Wing Loading W/S [{ws_unit}]")
        self._plot.setLabel("left", y_label)

        # First pass: convert all curves to display units; remember the
        # design-point loading so we can scale the Y axis around it.
        curves_display: list[tuple[str, str, np.ndarray, np.ndarray]] = []
        for curve in result.curves:
            xs = np.asarray(curve.wing_loading_values)
            ys = np.asarray(curve.loading_values)
            ws_d = np.array([dc.wing_loading(v)[0] for v in xs])
            ld_d = (
                np.array([dc.power_loading(v)[0] for v in ys])
                if result.is_power_loading_mode else ys
            )
            curves_display.append((curve.name, curve.color_hex, ws_d, ld_d))
            pen = pg.mkPen(color=curve.color_hex, width=2)
            self._plot.plot(ws_d, ld_d, pen=pen, name=curve.name)

        # Compute a sensible Y-axis upper bound. The raw curve maxima can
        # exceed the design-point loading by 10×+ at small W/S (asymptotic
        # branches), which squeezes the feasible region to a thin strip at
        # the bottom and pushes the design-point marker out of view. Clip
        # to ~2.5× the highest "envelope" point near the design wing-loading,
        # falling back to the curve median if no design point exists yet.
        dp = self._store.state.sizing.design_point
        if dp is not None:
            dp_ld = (
                dc.power_loading(dp.power_loading_nw)[0]
                if result.is_power_loading_mode else dp.power_loading_nw
            )
            y_top = max(dp_ld * 2.5, 0.05)
        else:
            medians = [float(np.median(ld_d)) for _, _, _, ld_d in curves_display if len(ld_d)]
            y_top = (max(medians) * 2.0) if medians else 1.0

        # Stall vertical line — drawn within the clipped Y range
        stall_x = dc.wing_loading(result.stall_ws_nm2)[0]
        stall_pen = pg.mkPen(color="#e74c3c", width=2, style=Qt.PenStyle.DashLine)
        self._plot.plot(
            [stall_x, stall_x], [0, y_top],
            pen=stall_pen, name="Stall Limit",
        )

        self._plot.setYRange(0.0, y_top, padding=0.05)

        # Re-place the design-point marker if the sizing pipeline has already
        # produced a design point. Without this, refreshing the constraint
        # curves (e.g. on settings or brief change) nukes the marker via
        # self._dp_scatter = None above, and the design_point_changed signal
        # doesn't re-fire — so the ★ silently disappears.
        if dp is not None:
            self._on_design_point()

    def _on_design_point(self) -> None:
        dp = self._store.state.sizing.design_point
        if dp is None:
            return
        self._update_cards(dp)
        dc = self._dc()
        ws_d = dc.wing_loading(dp.wing_loading_nm2)[0]
        cr = self._store.state.sizing.constraint_result
        is_power = cr.is_power_loading_mode if cr else True
        ld_d = (
            dc.power_loading(dp.power_loading_nw)[0]
            if is_power else dp.power_loading_nw
        )
        self._place_marker(ws_d, ld_d)

    def _on_settings_changed(self) -> None:
        self._on_constraint_result()
        self._on_design_point()
        self._update_cards_label()

    def _on_brief_changed(self) -> None:
        self._update_cards_label()

    def _update_cards_label(self) -> None:
        from app.core.enums import PowerUnit
        brief = self._store.state.sizing.brief
        cr = self._store.state.sizing.constraint_result
        is_power = cr.is_power_loading_mode if cr else brief.propulsion_type.is_power_mode
        dc = self._dc()
        if is_power:
            _, ld_u = dc.power_loading(0)
            self._card_load._lbl.setText("W/P")
            self._card_load.set_unit(ld_u)
            _, p_u = dc.power(0)
            self._card_p._lbl.setText("Power")
            self._card_p.set_unit(p_u)
        else:
            _, ld_u = dc.force_loading(0)
            self._card_load._lbl.setText("T/W")
            self._card_load.set_unit(ld_u)
            _, f_u = dc.force(0)
            self._card_p._lbl.setText("Thrust")
            self._card_p.set_unit(f_u)

    # ── Violation banner ──────────────────────────────────────────────────

    def _on_violations(self, violations: list) -> None:
        """Update banner — called whenever AppStore emits constraint_violation."""
        if not violations:
            # Feasible zone — confirm with subtle green banner
            self._banner.setText("Design point is within the feasible region.")
            self._banner.setStyleSheet(
                "QLabel { background: #0d2b0d; color: #2ecc71; "
                "border: 1px solid #2ecc71; border-radius: 5px; "
                "padding: 6px 10px; font-size: 12px; }"
            )
            self._banner.show()
            return

        # Build per-violation lines
        lines: list[str] = []
        has_error = any(
            getattr(v, "severity", None) is ConstraintSeverity.ERROR
            for v in violations
        )
        for v in violations:
            if hasattr(v, "description"):
                lines.append(f"  \u2022  {v.description}")
            else:
                lines.append(f"  \u2022  {v}")

        header = (
            f"\u26a0  {len(violations)} constraint{'s' if len(violations) > 1 else ''} violated:"
        )
        self._banner.setText(header + "\n" + "\n".join(lines))
        self._banner.setStyleSheet(
            "QLabel { background: #2b0d0d; color: #ff6666; "
            "border: 1px solid #e74c3c; border-radius: 5px; "
            "padding: 8px 12px; font-size: 12px; }"
        )
        self._banner.show()

    # ── Click-to-place ────────────────────────────────────────────────────

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
        click_ws_d = float(data_pos.x())
        click_ld_d = float(data_pos.y())

        # Convert display → SI
        dc = self._dc()
        from app.core.enums import AreaUnit, PowerUnit
        new_ws_si = (
            click_ws_d / 0.020_885_4
            if self._store.settings.area_unit == AreaUnit.FT2
            else click_ws_d
        )

        cr = self._store.state.sizing.constraint_result
        is_power = cr.is_power_loading_mode if cr else True
        if is_power:
            pu = self._store.settings.power_unit
            if pu == PowerUnit.HP:
                new_ld_si = click_ld_d / 167.573
            elif pu == PowerUnit.KW:
                new_ld_si = click_ld_d / 1000.0
            else:
                new_ld_si = click_ld_d
        else:
            new_ld_si = click_ld_d

        new_ws_si = max(1.0, new_ws_si)
        new_ld_si = max(1e-6, new_ld_si)

        self._move_design_point(new_ws_si, new_ld_si)

    def _move_design_point(self, new_ws: float, new_loading: float) -> None:
        wr = self._store.state.sizing.weight_result
        if wr is None:
            return

        w_to_kg = wr.w_to_kg
        weight_n = w_to_kg * _G

        wing_area = weight_n / new_ws if new_ws > 0 else 1.0
        brief = self._store.state.sizing.brief
        ar = brief.aspect_ratio
        wingspan = math.sqrt(wing_area * ar)

        cr = self._store.state.sizing.constraint_result
        is_power = cr.is_power_loading_mode if cr else True
        engine_power = (
            weight_n / new_loading if is_power and new_loading > 0
            else new_loading * weight_n
        )

        # Evaluate constraint violations at the clicked point
        violated: tuple[ConstraintViolation, ...] = ()
        if cr is not None:
            analyzer = ConstraintAnalyzer(brief, wr)
            violations = analyzer.check_design_point(new_ws, new_loading, cr)
            violated = tuple(violations)

        # Carry over sanity checks from last full pipeline run
        prev_dp = self._store.state.sizing.design_point
        carried_sanity = prev_dp.sanity_checks if prev_dp is not None else ()

        new_dp = DesignPoint(
            wing_loading_nm2=new_ws,
            power_loading_nw=new_loading,
            w_to_kg=w_to_kg,
            wing_area_m2=wing_area,
            wingspan_m=wingspan,
            aspect_ratio=ar,
            engine_power_w=engine_power,
            sanity_checks=carried_sanity,
            violated_constraints=violated,
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
        is_power = self._store.state.sizing.brief.propulsion_type.is_power_mode

        ws_v, ws_u   = dc.wing_loading(dp.wing_loading_nm2)
        ld_v, ld_u   = (
            dc.power_loading(dp.power_loading_nw)
            if is_power else dc.force_loading(dp.power_loading_nw)
        )
        wto_v, wto_u = dc.mass(dp.w_to_kg)
        s_v, s_u     = dc.area(dp.wing_area_m2)
        b_v, b_u     = dc.length(dp.wingspan_m)
        p_v, p_u     = (
            dc.power(dp.engine_power_w)
            if is_power else dc.force(dp.engine_power_w)
        )

        self._card_ws.set_value(ws_v, decimals=1);    self._card_ws.set_unit(ws_u)
        self._card_load.set_value(ld_v, decimals=5);  self._card_load.set_unit(ld_u)
        self._card_wto.set_value(wto_v, decimals=3);  self._card_wto.set_unit(wto_u)
        self._card_s.set_value(s_v, decimals=4);      self._card_s.set_unit(s_u)
        self._card_b.set_value(b_v, decimals=3);      self._card_b.set_unit(b_u)
        self._card_p.set_value(p_v, decimals=1);      self._card_p.set_unit(p_u)
