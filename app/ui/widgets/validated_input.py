"""
ValidatedInput Widget — UAV-CD-APP
=====================================
A QDoubleSpinBox paired with an error-state indicator and unit conversion.

Reads FieldSpec from the validation registry to auto-configure:
  - min / max range
  - tooltip (hint)

Supports live unit conversion:
  - Internally always stores and emits SI values.
  - Displays values in the current display unit.
  - When the display unit changes, the spinbox value is recalculated.
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
    Labelled, validated numeric input widget with unit conversion.

    Signals
    -------
    value_changed(float)
        Emitted whenever the spin-box value changes.
        The emitted value is ALWAYS in SI units.
    """

    value_changed: pyqtSignal = pyqtSignal(float)

    def __init__(
        self,
        spec: FieldSpec,
        parent: Optional[QWidget] = None,
        *,
        decimals: int = 4,
        step: float = 0.1,
    ) -> None:
        super().__init__(parent)
        self._spec: FieldSpec = spec
        self._is_valid: bool = True

        # Unit conversion callables (default: identity / no conversion)
        self._to_display: Callable[[float], float] = lambda v: v
        self._to_si: Callable[[float], float] = lambda v: v
        self._unit_label_str: str = spec.unit or ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 2)
        layout.setSpacing(1)

        # Label row: "Field Name [unit]"
        self._label = QLabel()
        self._label.setObjectName("InputLabel")
        self._update_label_text()
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

    def get_value_si(self) -> float:
        """Return the current value converted to SI units."""
        return self._to_si(self._spin.value())

    def get_value(self) -> float:
        """Return the raw spinbox (display-unit) value."""
        return self._spin.value()

    def set_value(self, si_value: float, block_signals: bool = False) -> None:
        """Set the spinbox value from an SI value."""
        display_val = self._to_display(si_value)
        if block_signals:
            self._spin.blockSignals(True)
        self._spin.setValue(display_val)
        if block_signals:
            self._spin.blockSignals(False)

    def set_unit_converter(
        self,
        to_display: Callable[[float], float],
        to_si: Callable[[float], float],
        unit_label: str,
    ) -> None:
        """
        Change the display unit. Recalculates the spinbox value from the
        current SI value (inferred from the old converter).

        Parameters
        ----------
        to_display : SI → display conversion.
        to_si      : display → SI conversion.
        unit_label : Human-readable unit string for the label/suffix.
        """
        # Get current value in SI (using OLD converter)
        current_si = self._to_si(self._spin.value())

        # Install new converter
        self._to_display = to_display
        self._to_si = to_si
        self._unit_label_str = unit_label
        self._update_label_text()

        # Recalculate displayed value
        new_display = self._to_display(current_si)
        self._spin.blockSignals(True)
        self._spin.setValue(new_display)
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

    def _update_label_text(self) -> None:
        unit_str = f"  [{self._unit_label_str}]" if self._unit_label_str and self._unit_label_str != "-" else ""
        self._label.setText(f"{self._spec.label}{unit_str}")

    def _on_value_changed(self, display_value: float) -> None:
        self.clear_error()
        si_value = self._to_si(display_value)
        self.value_changed.emit(si_value)
