"""
OAT-sweep small-multiples widget.

Renders one independent plot per selected output, all side-by-side,
sharing the swept-input X axis. Each panel has its own auto-ranged
Y axis in the user's display units; a vertical dashed baseline marker
sits at the parameter's current value on every panel.

Why small multiples instead of an overlaid plot:
  * Each output's Y axis can use its native unit (MTOW in kg/lb, Wing
    Area in m²/ft², Power in W/kW/hp) — no normalisation hack required.
  * Three independent panels are easier to compare than three lines
    sharing one normalised axis, especially when one curve is highly
    non-linear.
  * Re-render is instant when the user changes the "Show" combo — no
    pipeline call needed because the cached ``OATSweep`` carries every
    output via ``outcome.get(output_id)``.

Layout: dynamic ``QHBoxLayout`` rebuilt on every ``set_sweep`` call.
With 1 output → 1 wide panel; with 3 outputs → 3 panels in a row.
"""

from __future__ import annotations

from typing import Optional

import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.display_converter import DisplayConverter
from app.core.enums import PropulsionType
from app.core.sensitivity import (
    OATSweep,
    SweepableParameter,
    display_label_for_output,
    display_label_for_parameter,
    unit_kind_for_output,
    unit_kind_for_parameter,
)


# Distinct colours per output curve so the designer scans quickly.
_CURVE_COLORS = {
    "mtow_kg":              "#e67e22",
    "wing_area_m2":         "#27ae60",
    "engine_power_w":       "#3498db",
    "wingspan_m":           "#9b59b6",
    "w_empty_kg":           "#c0392b",
    "empty_weight_fraction": "#16a085",
    "ld_max":               "#1abc9c",
    "cl_cruise":            "#f1c40f",
    "wing_loading_nm2":     "#34495e",
    "power_loading_nw":     "#8e44ad",
    "w_fuel_or_battery_kg": "#d35400",
    "fuel_battery_fraction": "#7f8c8d",
}

_DEFAULT_COLOR = "#cccccc"
_BASELINE_COLOR = "#aaaacc"
_AXIS_TEXT     = "#aaaacc"
_TITLE_COLOR   = "#ccccdd"


class SweepWidget(QWidget):
    """Horizontal small-multiples renderer for an ``OATSweep``."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        # Reduced from 260 → 200 — same rationale as tornado_widget.
        self.setMinimumHeight(200)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 2)
        outer.setSpacing(0)

        # Inner container that holds the small multiples — replaced
        # wholesale on each ``set_sweep`` call.
        self._panels_host = QWidget()
        self._panels_layout = QHBoxLayout(self._panels_host)
        self._panels_layout.setContentsMargins(0, 0, 0, 0)
        self._panels_layout.setSpacing(6)
        outer.addWidget(self._panels_host)

        pg.setConfigOptions(antialias=True)

        # Cached for re-render on settings / propulsion change. The tab
        # also caches the last sweep on its side; this copy lets the
        # widget repaint itself if asked.
        self._current_sweep: Optional[OATSweep] = None
        self._current_output_ids: list[str] = []
        self._current_converter: Optional[DisplayConverter] = None
        self._current_propulsion_type: Optional[PropulsionType] = None

        # Start with an empty placeholder panel.
        self._show_empty_state("Run a sweep to populate.")

    # ── Public ────────────────────────────────────────────────────────────

    def set_sweep(
        self,
        sweep: OATSweep,
        output_ids: list[str],
        *,
        converter: DisplayConverter,
        propulsion_type: PropulsionType,
    ) -> None:
        """Render one small-multiples panel per output in ``output_ids``.

        All numbers are display-converted: the X axis carries the swept
        parameter in user units, each Y axis carries its output in user
        units. The vertical baseline marker sits at the parameter's
        current value (also display-converted).
        """
        self._current_sweep = sweep
        self._current_output_ids = list(output_ids)
        self._current_converter = converter
        self._current_propulsion_type = propulsion_type

        self._clear_panels()

        if not output_ids:
            self._show_empty_state("Choose an output to plot.")
            return

        param = sweep.parameter
        x_factor, x_unit = self._param_factor_unit(param, converter)
        x_label = display_label_for_parameter(param, propulsion_type)
        baseline_display = sweep.baseline * x_factor

        for output_id in output_ids:
            panel = self._build_panel(
                sweep=sweep,
                output_id=output_id,
                x_factor=x_factor,
                x_unit=x_unit,
                x_label=x_label,
                baseline_display=baseline_display,
                converter=converter,
                propulsion_type=propulsion_type,
            )
            self._panels_layout.addWidget(panel, stretch=1)

    def clear(self) -> None:
        """Discard the current sweep and show the empty-state placeholder."""
        self._current_sweep = None
        self._current_output_ids = []
        self._clear_panels()
        self._show_empty_state("Run a sweep to populate.")

    # ── Private ───────────────────────────────────────────────────────────

    def _clear_panels(self) -> None:
        """Remove every child PlotWidget / placeholder from the host."""
        while self._panels_layout.count():
            item = self._panels_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _show_empty_state(self, message: str) -> None:
        """Replace the panels with a single message placeholder."""
        placeholder = QLabel(message)
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(
            f"color: {_AXIS_TEXT}; font-style: italic; padding: 24px;"
        )
        self._panels_layout.addWidget(placeholder, stretch=1)

    def _build_panel(
        self,
        *,
        sweep: OATSweep,
        output_id: str,
        x_factor: float,
        x_unit: str,
        x_label: str,
        baseline_display: float,
        converter: DisplayConverter,
        propulsion_type: PropulsionType,
    ) -> QWidget:
        """Build one small-multiples panel for ``output_id``."""
        plot = pg.PlotWidget()
        plot.setBackground("transparent")
        plot.showGrid(x=True, y=True, alpha=0.2)
        plot.getAxis("left").setTextPen(_AXIS_TEXT)
        plot.getAxis("bottom").setTextPen(_AXIS_TEXT)

        out_label = display_label_for_output(output_id, propulsion_type)
        y_factor, y_unit = self._output_factor_unit(
            output_id, converter, propulsion_type,
        )
        plot.setTitle(out_label, color=_TITLE_COLOR, size="10pt")
        plot.setLabel("bottom", f"{x_label} [{x_unit}]", color=_AXIS_TEXT)
        plot.setLabel("left",   f"{out_label} [{y_unit}]", color=_AXIS_TEXT)

        xs_raw, ys_raw = sweep.outputs_for(output_id)
        # Mask missing pipeline points so they don't break the curve.
        valid = [(x, y) for x, y in zip(xs_raw, ys_raw) if y is not None]
        if not valid:
            # Output not available for this configuration — show empty
            # axes with a small annotation so the panel still appears.
            self._set_default_range(plot)
            note = pg.TextItem(
                text="No data", color=_AXIS_TEXT,
                anchor=(0.5, 0.5),
            )
            note.setPos(0.5, 0.5)
            plot.addItem(note)
            return plot

        xs_display = [x * x_factor for x, _ in valid]
        ys_display = [y * y_factor for _, y in valid]

        pen = pg.mkPen(
            _CURVE_COLORS.get(output_id, _DEFAULT_COLOR),
            width=2.4,
        )
        plot.plot(xs_display, ys_display, pen=pen, name=out_label)

        # Padded Y range so the curve is centred vertically in the panel.
        y_min, y_max = min(ys_display), max(ys_display)
        y_pad = (y_max - y_min) * 0.10 if y_max > y_min else max(abs(y_max), 1e-6) * 0.10
        plot.setYRange(y_min - y_pad, y_max + y_pad)

        # X range covers the swept band with a touch of headroom so the
        # baseline marker label doesn't get clipped.
        x_min, x_max = min(xs_display), max(xs_display)
        x_pad = (x_max - x_min) * 0.05 if x_max > x_min else max(abs(x_max), 1e-6) * 0.05
        plot.setXRange(x_min - x_pad, x_max + x_pad)

        # Baseline marker — vertical dashed line at the parameter's
        # current value, labelled with the numeric value in display units.
        baseline_line = pg.InfiniteLine(
            pos=baseline_display, angle=90,
            pen=pg.mkPen(_BASELINE_COLOR, width=1.2,
                         style=Qt.PenStyle.DashLine),
            label=f" baseline = {baseline_display:.3g}",
            labelOpts={
                "position": 0.95,
                "color": _BASELINE_COLOR,
                "movable": False,
            },
        )
        plot.addItem(baseline_line)

        return plot

    @staticmethod
    def _set_default_range(plot: pg.PlotWidget) -> None:
        """Tame default empty-state range so an empty pyqtgraph PlotWidget
        doesn't render its native ±100 000 viewBox."""
        plot.getViewBox().disableAutoRange()
        plot.setXRange(0, 1, padding=0)
        plot.setYRange(0, 1, padding=0)

    @staticmethod
    def _param_factor_unit(
        param: SweepableParameter,
        converter: DisplayConverter,
    ) -> tuple[float, str]:
        kind = unit_kind_for_parameter(param)
        method = getattr(converter, kind, None)
        if method is None or kind == "ratio":
            return 1.0, param.unit
        return method(1.0)

    @staticmethod
    def _output_factor_unit(
        output_id: str,
        converter: DisplayConverter,
        propulsion_type: PropulsionType,
    ) -> tuple[float, str]:
        kind = unit_kind_for_output(output_id, propulsion_type)
        method = getattr(converter, kind, None)
        if method is None:
            return 1.0, ""
        return method(1.0)
