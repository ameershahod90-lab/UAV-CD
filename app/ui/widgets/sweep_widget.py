"""
OAT-sweep curve widget.

Shows how multiple design outputs respond when a single input parameter
is swept across ±delta_pct around its current value. The vertical dashed
line marks the baseline (current brief value).

The widget displays up to three output curves on a single chart using
pyqtgraph's multi-axis support. By default it shows MTOW, Wing Area,
and Engine Power — the Tier-1 outputs — so the designer can see how
they move together as the input varies.
"""

from __future__ import annotations

from typing import Optional

import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from app.core.sensitivity import OATSweep, OUTPUT_CATALOG


# Distinct colours per output curve so the designer can scan quickly.
_CURVE_COLORS = {
    "mtow_kg":         "#e67e22",
    "wing_area_m2":    "#27ae60",
    "engine_power_w":  "#3498db",
    "wingspan_m":      "#9b59b6",
    "w_empty_kg":      "#c0392b",
    "ld_max":          "#1abc9c",
}


class SweepWidget(QWidget):
    """Multi-output OAT sweep curve plot."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        self.setMinimumHeight(260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        pg.setConfigOptions(antialias=True)
        self._plot = pg.PlotWidget()
        self._plot.setBackground("transparent")
        self._plot.showGrid(x=True, y=True, alpha=0.2)
        self._plot.getAxis("left").setTextPen("#aaaacc")
        self._plot.getAxis("bottom").setTextPen("#aaaacc")
        self._plot.addLegend(offset=(-10, 10))
        layout.addWidget(self._plot)

    # ── Public ────────────────────────────────────────────────────────────

    def set_sweep(
        self,
        sweep: OATSweep,
        output_ids: list[str],
    ) -> None:
        """Plot one or more outputs against the swept input."""
        self._plot.clear()
        self._plot.addLegend(offset=(-10, 10))

        param = sweep.parameter
        self._plot.setLabel(
            "bottom",
            f"{param.label} [{param.unit}]",
            color="#aaaacc",
        )

        # Single-output → use the left Y axis with the output's unit.
        # Multi-output → normalise per curve so they share the [0, 1.2]
        # range; show the unit in the legend label instead.
        if len(output_ids) == 1:
            spec = OUTPUT_CATALOG.get(output_ids[0])
            unit = spec.unit if spec else ""
            xs, ys = sweep.outputs_for(output_ids[0])
            valid = [(x, y) for x, y in zip(xs, ys) if y is not None]
            if not valid:
                return
            self._plot.setLabel(
                "left",
                f"{spec.label if spec else output_ids[0]} [{unit}]",
                color="#aaaacc",
            )
            pen = pg.mkPen(_CURVE_COLORS.get(output_ids[0], "#cccccc"), width=2.2)
            self._plot.plot(
                [x for x, _ in valid], [y for _, y in valid],
                pen=pen, name=spec.label if spec else output_ids[0],
            )
        else:
            # Multi-output: normalise each curve to its baseline so the
            # designer reads them as "% change from current design".
            self._plot.setLabel(
                "left", "Output (% of baseline)", color="#aaaacc",
            )
            for output_id in output_ids:
                spec = OUTPUT_CATALOG.get(output_id)
                xs, ys = sweep.outputs_for(output_id)
                # Find baseline (sample closest to sweep.baseline)
                # so we can normalise.
                if not any(y is not None for y in ys):
                    continue
                baseline_y = self._baseline_value(xs, ys, sweep.baseline)
                if baseline_y is None or baseline_y == 0:
                    continue
                norm_x = [x for x, y in zip(xs, ys) if y is not None]
                norm_y = [y / baseline_y * 100.0 for y in ys if y is not None]
                pen = pg.mkPen(_CURVE_COLORS.get(output_id, "#cccccc"), width=2.2)
                self._plot.plot(
                    norm_x, norm_y,
                    pen=pen,
                    name=f"{spec.label if spec else output_id} [{spec.unit if spec else ''}]",
                )

        # Vertical line at the baseline input value
        baseline_line = pg.InfiniteLine(
            pos=sweep.baseline, angle=90,
            pen=pg.mkPen("#aaaacc", width=1.2, style=Qt.PenStyle.DashLine),
            label=f" baseline = {sweep.baseline:.3g}",
            labelOpts={"position": 0.98, "color": "#aaaacc"},
        )
        self._plot.addItem(baseline_line)

        # Horizontal 100% line when normalising
        if len(output_ids) > 1:
            zero_line = pg.InfiniteLine(
                pos=100, angle=0,
                pen=pg.mkPen("#888899", width=1, style=Qt.PenStyle.DashLine),
            )
            self._plot.addItem(zero_line)

    def clear(self) -> None:
        self._plot.clear()
        self._plot.addLegend(offset=(-10, 10))

    @staticmethod
    def _baseline_value(xs, ys, baseline_x) -> Optional[float]:
        """Linear-interpolate the output value at the baseline x."""
        valid = [(x, y) for x, y in zip(xs, ys) if y is not None]
        if not valid:
            return None
        # Find the closest x to baseline_x
        valid.sort(key=lambda xy: abs(xy[0] - baseline_x))
        return valid[0][1]
