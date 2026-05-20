"""
Tornado bar-chart widget.

Visualises which input parameters dominate a given output. Each row
shows a parameter's name on the left axis and a horizontal bar that
extends from the baseline to the ±delta-perturbation output value. Bars
are sorted (largest impact at top) by the data builder upstream.

Visual encoding:
  * Bar extending RIGHT  → input increase RAISES the output
  * Bar extending LEFT   → input increase LOWERS the output (split bar)
  * Width                → magnitude of the effect
  * Numeric label at end → exact Δ value (helps when bars are short)

The widget is interactive — clicking a bar emits ``parameter_clicked``
so the parent tab can wire it to the OAT sweep panel.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from app.core.sensitivity import OUTPUT_CATALOG, SweepableParameter, TornadoData


# Colour palette — distinct positive / negative; matches Sadraey-style plots
_POS_COLOR = "#2980b9"   # blue — input increase raises the output
_NEG_COLOR = "#c0392b"   # red  — input increase lowers the output
_BASELINE  = "#7f8c8d"


class TornadoWidget(QWidget):
    """One tornado plot, optionally bound to a single output ID.

    Signals
    -------
    parameter_clicked(SweepableParameter)
        Emitted when the user clicks a bar — the parent tab uses this to
        drive the OAT sweep panel.
    """

    parameter_clicked = pyqtSignal(object)   # SweepableParameter

    # Cap on how many bars to draw — beyond ~10 the chart becomes unreadable.
    _MAX_BARS = 10

    def __init__(
        self,
        title: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        self.setMinimumHeight(280)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        pg.setConfigOptions(antialias=True)
        self._plot = pg.PlotWidget()
        self._plot.setBackground("transparent")
        self._plot.showGrid(x=True, y=False, alpha=0.2)
        self._plot.getAxis("left").setTextPen("#aaaacc")
        self._plot.getAxis("bottom").setTextPen("#aaaacc")
        self._plot.getAxis("left").setStyle(showValues=True)
        # Disable y zoom — we set the y range explicitly per bar set.
        self._plot.getViewBox().setMouseEnabled(x=True, y=False)
        if title:
            self._plot.setTitle(title, color="#ccccdd", size="10pt")
        layout.addWidget(self._plot)

        # Cached so we can hit-test clicks against bars
        self._current_data: Optional[TornadoData] = None
        self._plot.scene().sigMouseClicked.connect(self._on_click)

    # ── Public ────────────────────────────────────────────────────────────

    def set_data(self, data: TornadoData) -> None:
        """Render a tornado for one output."""
        self._current_data = data
        self._plot.clear()

        bars = list(data.bars)[: self._MAX_BARS]
        if not bars:
            return

        spec = OUTPUT_CATALOG.get(data.output_id)
        unit = spec.unit if spec else ""

        # Y positions: top of chart is index 0 (most influential)
        y_positions = list(range(len(bars)))

        # Two BarGraphItems — one for "below baseline" (delta_low side),
        # one for "above baseline" (delta_high side). Drawn in opposite
        # directions from the zero axis.
        widths_low  = [-(b.delta_low  or 0.0) for b in bars]   # negate so they go left
        widths_high = [ (b.delta_high or 0.0) for b in bars]
        # When delta_low itself is positive (e.g. input decrease RAISES
        # output), the bar should still extend to the right of zero.
        # That makes a "two-sided" tornado where both segments can be on
        # either side of zero — we just clamp to whichever side is correct.
        widths_low_signed  = [(b.delta_low  or 0.0) for b in bars]
        widths_high_signed = [(b.delta_high or 0.0) for b in bars]

        # Bars: split into two BarGraphItems so we can colour each side.
        bar_low = pg.BarGraphItem(
            x0=0, y=y_positions, height=0.6,
            width=widths_low_signed,
            brush=_NEG_COLOR, pen=pg.mkPen("#7c1f15", width=0.5),
        )
        bar_high = pg.BarGraphItem(
            x0=0, y=y_positions, height=0.6,
            width=widths_high_signed,
            brush=_POS_COLOR, pen=pg.mkPen("#1a4f70", width=0.5),
        )
        self._plot.addItem(bar_low)
        self._plot.addItem(bar_high)

        # Zero (baseline) line
        zero_line = pg.InfiniteLine(
            pos=0, angle=90,
            pen=pg.mkPen(_BASELINE, width=1.5, style=Qt.PenStyle.DashLine),
        )
        self._plot.addItem(zero_line)

        # Y-axis labels: parameter names
        labels = [(y, bars[y].parameter.label) for y in y_positions]
        self._plot.getAxis("left").setTicks([labels])
        # Invert Y so the largest impact appears at the TOP
        self._plot.getViewBox().invertY(True)

        # Bottom-axis label
        self._plot.setLabel(
            "bottom",
            f"Δ {spec.label if spec else data.output_id} [{unit}]",
            color="#aaaacc",
        )

        # Set the X range with some padding
        all_deltas = widths_low_signed + widths_high_signed
        max_abs = max((abs(v) for v in all_deltas if v), default=1.0)
        self._plot.setXRange(-max_abs * 1.15, max_abs * 1.15, padding=0)
        self._plot.setYRange(-0.5, len(bars) - 0.5)

        # Inline text labels at the bar tips so the reader sees exact Δ.
        for y, b in zip(y_positions, bars):
            for delta, side in (
                (b.delta_low,  -1),
                (b.delta_high,  1),
            ):
                if delta is None or delta == 0:
                    continue
                text = pg.TextItem(
                    text=f"{delta:+.2f}",
                    color=(_NEG_COLOR if side < 0 else _POS_COLOR),
                    anchor=(0 if delta >= 0 else 1, 0.5),
                )
                text.setPos(delta * 1.02, y)
                self._plot.addItem(text)

    def clear(self) -> None:
        self._plot.clear()
        self._current_data = None

    # ── Click hit-test ────────────────────────────────────────────────────

    def _on_click(self, evt) -> None:
        if self._current_data is None or not self._current_data.bars:
            return
        # Map scene → data coords
        try:
            vb = self._plot.plotItem.vb
            scene_pos = evt.scenePos()
            data_pos = vb.mapSceneToView(scene_pos)
            y = data_pos.y()
            bars = list(self._current_data.bars)[: self._MAX_BARS]
            idx = int(round(y))
            if 0 <= idx < len(bars):
                self.parameter_clicked.emit(bars[idx].parameter)
        except Exception:
            pass
