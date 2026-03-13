"""
ResultCard Widget — UAV-CD-APP
================================
A read-only card displaying a computed result value with:
  - a label (parameter name)
  - a formatted value string
  - a dynamic unit suffix (updated via set_unit)
  - an optional status indicator (for sanity checks)
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.core.enums import SanityCheckStatus


_STATUS_COLORS: dict[SanityCheckStatus, str] = {
    SanityCheckStatus.PASS: "#2ecc71",   # green
    SanityCheckStatus.WARN: "#f39c12",   # orange
    SanityCheckStatus.FAIL: "#e74c3c",   # red
}


class ResultCard(QFrame):
    """
    Compact read-only result card with dynamic unit label.

    Usage::

        card = ResultCard("MTOW", unit="kg")
        card.set_value(12.4)
        card.set_unit("lb")           # changes unit label dynamically
        card.set_value(27.3)          # re-set with new display value
        card.set_status(SanityCheckStatus.PASS)
    """

    def __init__(
        self,
        label: str,
        *,
        unit: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ResultCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        # Label
        self._lbl = QLabel(label)
        self._lbl.setObjectName("ResultCardLabel")
        layout.addWidget(self._lbl)

        # Value row
        val_row = QHBoxLayout()
        self._val_lbl = QLabel("—")
        self._val_lbl.setObjectName("ResultCardValue")
        val_row.addWidget(self._val_lbl)

        self._unit_lbl = QLabel(unit)
        self._unit_lbl.setObjectName("ResultCardUnit")
        if not unit:
            self._unit_lbl.hide()
        val_row.addWidget(self._unit_lbl)

        val_row.addStretch()

        # Status dot
        self._status_dot = QLabel()
        self._status_dot.setFixedSize(10, 10)
        self._status_dot.setVisible(False)
        val_row.addWidget(self._status_dot)

        layout.addLayout(val_row)

    def set_value(self, value: Optional[float], decimals: int = 3) -> None:
        if value is None:
            self._val_lbl.setText("—")
        else:
            self._val_lbl.setText(f"{value:.{decimals}f}")

    def set_unit(self, unit_label: str) -> None:
        """Dynamically change the displayed unit label."""
        self._unit_lbl.setText(unit_label)
        self._unit_lbl.setVisible(bool(unit_label))

    def set_text(self, text: str) -> None:
        self._val_lbl.setText(text)

    def set_status(self, status: SanityCheckStatus) -> None:
        color = _STATUS_COLORS.get(status, "#888888")
        self._status_dot.setVisible(True)
        self._status_dot.setStyleSheet(
            f"background-color: {color}; border-radius: 5px;"
        )
        self._status_dot.setToolTip(status.value.upper())
