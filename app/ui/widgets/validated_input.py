"""
ValidatedInput Widget — UAV-CD-APP
=====================================
A QDoubleSpinBox paired with an error-state indicator.

Reads FieldSpec from the validation registry to auto-configure:
  - min / max range
  - suffix (unit label)
  - tooltip (hint)

Displays a red border + error label when validation fails.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.validation import FieldSpec


class ValidatedInput(QWidget):
    """
    Labelled, validated numeric input widget.

    Signals
    -------
    value_changed(float)
        Emitted whenever the spin-box value changes.
    """

    value_changed: pyqtSignal = pyqtSignal(float)

    def __init__(
        self,
        spec: FieldSpec,
        parent: Optional[QWidget] = None,
        *,
        decimals: int = 3,
        step: float = 0.1,
    ) -> None:
        super().__init__(parent)
        self._spec: FieldSpec = spec
        self._is_valid: bool = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 2)
        layout.setSpacing(1)

        # Label row: "Field Name [unit]"
        unit_str = f"  [{spec.unit}]" if spec.unit and spec.unit != "-" else ""
        self._label = QLabel(f"{spec.label}{unit_str}")
        self._label.setObjectName("InputLabel")
        layout.addWidget(self._label)

        # Spin box
        self._spin = QDoubleSpinBox()
        self._spin.setObjectName("ValidatedSpinBox")
        self._spin.setDecimals(decimals)
        self._spin.setSingleStep(step)

        if spec.min_val is not None:
            self._spin.setMinimum(spec.min_val)
        elif spec.gt_zero:
            self._spin.setMinimum(1e-6)
        elif spec.gte_zero:
            self._spin.setMinimum(0.0)
        else:
            self._spin.setMinimum(-1e9)

        if spec.max_val is not None:
            self._spin.setMaximum(spec.max_val)
        else:
            self._spin.setMaximum(1e9)

        if spec.hint:
            self._spin.setToolTip(spec.hint)

        self._spin.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self._spin)

        # Error label (hidden by default)
        self._error_label = QLabel()
        self._error_label.setObjectName("ErrorLabel")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def spin_box(self) -> QDoubleSpinBox:
        return self._spin

    def get_value(self) -> float:
        return self._spin.value()

    def set_value(self, value: float, block_signals: bool = False) -> None:
        if block_signals:
            self._spin.blockSignals(True)
        self._spin.setValue(value)
        if block_signals:
            self._spin.blockSignals(False)

    def set_error(self, message: str) -> None:
        self._is_valid = False
        self._error_label.setText(f"⚠ {message}")
        self._error_label.setVisible(True)
        self._spin.setProperty("state", "error")
        self._spin.style().unpolish(self._spin)
        self._spin.style().polish(self._spin)

    def clear_error(self) -> None:
        self._is_valid = True
        self._error_label.setVisible(False)
        self._error_label.setText("")
        self._spin.setProperty("state", "")
        self._spin.style().unpolish(self._spin)
        self._spin.style().polish(self._spin)

    @property
    def is_valid(self) -> bool:
        return self._is_valid

    # ── Internal ─────────────────────────────────────────────────────────

    def _on_value_changed(self, value: float) -> None:
        self.clear_error()
        self.value_changed.emit(value)
