"""
SliderInput Widget — UAV-CD-APP
==================================
A horizontal slider paired with a spin-box for tunable coefficients.
The slider is displayed as a compact, labelled knob with live value readout.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class SliderInput(QWidget):
    """
    Label + slider + spin-box combination for coefficient tuning.

    The slider maps its integer range [0, 1000] to the float domain
    [min_val, max_val] for smooth dragging.

    Signals
    -------
    value_changed(float)
        Emitted whenever the value changes (slider drag or spinbox edit).
    """

    value_changed: pyqtSignal = pyqtSignal(float)

    def __init__(
        self,
        label: str,
        min_val: float,
        max_val: float,
        initial: float,
        *,
        decimals: int = 3,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._min: float = min_val
        self._max: float = max_val
        self._decimals: int = decimals
        self._updating: bool = False   # Re-entrancy guard

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)

        # Header row: label left, current value right
        hdr = QHBoxLayout()
        self._lbl = QLabel(label)
        self._lbl.setObjectName("SliderLabel")
        self._val_lbl = QLabel(f"{initial:.{decimals}f}")
        self._val_lbl.setObjectName("SliderValueLabel")
        hdr.addWidget(self._lbl)
        hdr.addStretch()
        hdr.addWidget(self._val_lbl)
        root.addLayout(hdr)

        # Slider + spinbox row
        row = QHBoxLayout()
        row.setSpacing(8)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 1000)
        self._slider.setValue(self._to_int(initial))
        row.addWidget(self._slider, stretch=1)

        self._spin = QDoubleSpinBox()
        self._spin.setDecimals(decimals)
        self._spin.setRange(min_val, max_val)
        self._spin.setValue(initial)
        self._spin.setFixedWidth(90)
        row.addWidget(self._spin)

        root.addLayout(row)

        # Wire up
        self._slider.valueChanged.connect(self._on_slider)
        self._spin.valueChanged.connect(self._on_spin)

    # ── Public API ───────────────────────────────────────────────────────

    def get_value(self) -> float:
        return self._spin.value()

    def set_value(self, value: float) -> None:
        self._updating = True
        self._spin.setValue(value)
        self._slider.setValue(self._to_int(value))
        self._val_lbl.setText(f"{value:.{self._decimals}f}")
        self._updating = False

    # ── Internal ─────────────────────────────────────────────────────────

    def _to_int(self, v: float) -> int:
        span = self._max - self._min
        if span < 1e-12:
            return 0
        return int(round((v - self._min) / span * 1000))

    def _to_float(self, i: int) -> float:
        return self._min + (i / 1000.0) * (self._max - self._min)

    def _on_slider(self, int_val: int) -> None:
        if self._updating:
            return
        fval = self._to_float(int_val)
        self._updating = True
        self._spin.setValue(fval)
        self._val_lbl.setText(f"{fval:.{self._decimals}f}")
        self._updating = False
        self.value_changed.emit(fval)

    def _on_spin(self, fval: float) -> None:
        if self._updating:
            return
        self._updating = True
        self._slider.setValue(self._to_int(fval))
        self._val_lbl.setText(f"{fval:.{self._decimals}f}")
        self._updating = False
        self.value_changed.emit(fval)
