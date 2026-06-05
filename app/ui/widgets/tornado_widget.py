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

import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from app.core.display_converter import DisplayConverter
from app.core.enums import PropulsionType
from app.core.sensitivity import (
    SweepableParameter,
    TornadoData,
    display_label_for_output,
    unit_kind_for_output,
)


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
        # Reduced from 280 → 220 so the four-panel layout fits on a 1280×860
        # viewport without clipping; the QScrollArea wrapper in SensitivityTab
        # handles overflow when the user wants the chart taller.
        self.setMinimumHeight(220)

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
        # Reserve a wide left axis so long parameter names like
        # "Battery Energy Density" or "Propulsive Efficiency (ηₚ)" don't
        # clip on the chart edge. 150 px is comfortable for the longest
        # SWEEPABLE_PARAMETERS label without stealing too much chart area.
        self._plot.getAxis("left").setWidth(150)
        # Disable y zoom — we set the y range explicitly per bar set.
        self._plot.getViewBox().setMouseEnabled(x=True, y=False)
        if title:
            self._plot.setTitle(title, color="#ccccdd", size="10pt")
        layout.addWidget(self._plot)

        # Cached so we can hit-test clicks against bars + re-render
        # when settings change without re-running the sizing pipeline.
        self._current_data: Optional[TornadoData] = None
        self._current_converter: Optional[DisplayConverter] = None
        self._current_propulsion_type: Optional[PropulsionType] = None
        self._plot.scene().sigMouseClicked.connect(self._on_click)

    # ── Public ────────────────────────────────────────────────────────────

    def set_data(
        self,
        data: TornadoData,
        *,
        converter: DisplayConverter,
        propulsion_type: PropulsionType,
    ) -> None:
        """Render a tornado for one output.

        Output values (the bar widths) and the axis unit label are
        converted via ``converter`` so the chart honours the user's
        unit preferences. The output's label is resolved via
        ``display_label_for_output`` so propulsion-specific outputs
        (engine_power_w, power_loading_nw, …) show the right wording.
        """
        self._current_data = data
        self._current_converter = converter
        self._current_propulsion_type = propulsion_type
        self._plot.clear()

        bars = list(data.bars)[: self._MAX_BARS]
        if not bars:
            return

        # Propulsion-aware label + DC-driven unit conversion factor for
        # the output's SI value (delta = output_at_high − baseline_out, etc.).
        out_label = display_label_for_output(data.output_id, propulsion_type)
        kind = unit_kind_for_output(data.output_id, propulsion_type)
        conv_method = getattr(converter, kind, None)
        if conv_method is not None:
            # All DC methods are linear (display = factor × SI), so we
            # only need one conversion of a unit-magnitude value to get
            # both the multiplicative factor and the user-facing unit
            # label.
            out_factor, out_unit = conv_method(1.0)
        else:
            out_factor, out_unit = 1.0, ""

        # Y positions: top of chart is index 0 (most influential)
        y_positions = list(range(len(bars)))

        # Signed delta values converted to display units. pyqtgraph
        # BarGraphItem with x0=0 places each bar from the zero axis out
        # to width — positive width extends right, negative extends left.
        # Split into two BarGraphItems so each side carries its own
        # colour (red for delta_low, blue for delta_high). "low"/"high"
        # refer to the input-perturbation side (−delta_pct / +delta_pct),
        # not the sign of the output change.
        widths_low  = [(b.delta_low  or 0.0) * out_factor for b in bars]
        widths_high = [(b.delta_high or 0.0) * out_factor for b in bars]

        bar_low = pg.BarGraphItem(
            x0=0, y=y_positions, height=0.6,
            width=widths_low,
            brush=_NEG_COLOR, pen=pg.mkPen("#7c1f15", width=0.5),
        )
        bar_high = pg.BarGraphItem(
            x0=0, y=y_positions, height=0.6,
            width=widths_high,
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

        # Bottom-axis label — propulsion-aware label + DC-converted unit
        self._plot.setLabel(
            "bottom",
            f"Δ {out_label} [{out_unit}]",
            color="#aaaacc",
        )

        # Set the X range with extra headroom on both sides so the
        # numeric labels we drop next don't get cropped at the chart edge.
        all_deltas = widths_low + widths_high
        max_abs = max((abs(v) for v in all_deltas if v), default=1.0)
        self._plot.setXRange(-max_abs * 1.30, max_abs * 1.30, padding=0)
        self._plot.setYRange(-0.5, len(bars) - 0.5)

        # Inline text labels at the bar tips so the reader sees exact Δ.
        # Anchor by sign so labels always sit OUTSIDE the bar tip — never
        # overlapping the coloured fill. Offset is a small fraction of
        # max_abs so it scales with the chart range. Tip values are in
        # display units (already multiplied by out_factor when we built
        # widths_low / widths_high above).
        offset = max_abs * 0.04
        for y, (low, high) in zip(y_positions, zip(widths_low, widths_high)):
            for delta, side in ((low, -1), (high, 1)):
                if delta == 0:
                    continue
                # anchor=(0, 0.5) means the text's LEFT edge sits at setPos
                # anchor=(1, 0.5) means the text's RIGHT edge sits at setPos
                # Place left-anchored labels just past a positive bar tip;
                # place right-anchored labels just before a negative bar tip.
                if delta >= 0:
                    anchor = (0, 0.5)
                    x_pos = delta + offset
                else:
                    anchor = (1, 0.5)
                    x_pos = delta - offset
                text = pg.TextItem(
                    text=f"{delta:+.2f}",
                    color=(_NEG_COLOR if side < 0 else _POS_COLOR),
                    anchor=anchor,
                )
                text.setPos(x_pos, y)
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
