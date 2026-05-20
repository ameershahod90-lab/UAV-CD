"""
Snowball-factor table widget.

Renders the partial-derivative "rules of thumb" the design-sensitivity
engine produces (∂MTOW/∂Payload, ∂P/∂Payload, ∂S/∂CL_max, …) as a
compact, scannable table. Each row reads as a natural-language sentence
so the designer's eye picks up the magnitude AND direction at a glance.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.sensitivity import SnowballReport


class SnowballWidget(QWidget):
    """Compact table of ∂output/∂input rules-of-thumb."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(
            ["Sensitivity", "Value", "Interpretation"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents,
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents,
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch,
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setShowGrid(True)
        self._table.setAlternatingRowColors(True)
        self._table.setMinimumHeight(180)
        layout.addWidget(self._table)

    # ── Public ────────────────────────────────────────────────────────────

    def set_factors(self, report: SnowballReport) -> None:
        self._table.setRowCount(len(report.factors))
        for row, f in enumerate(report.factors):
            label_in  = f.parameter.label
            label_out = f.output_label
            unit_in   = f.parameter.unit
            unit_out  = f.output_unit

            sym_item = QTableWidgetItem(f"∂{label_out} / ∂{label_in}")
            sym_item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )
            self._table.setItem(row, 0, sym_item)

            if f.value is None:
                value_item = QTableWidgetItem("—")
                interp_item = QTableWidgetItem("Could not compute (pipeline failed)")
            else:
                value_item = QTableWidgetItem(
                    f"{f.value:+.4g} {unit_out}/{unit_in}"
                )
                interp_item = QTableWidgetItem(
                    self._format_interpretation(f, unit_in, unit_out)
                )
            value_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            self._table.setItem(row, 1, value_item)
            self._table.setItem(row, 2, interp_item)

        self._table.resizeRowsToContents()

    def clear(self) -> None:
        self._table.setRowCount(0)

    # ── Private ───────────────────────────────────────────────────────────

    @staticmethod
    def _format_interpretation(f, unit_in: str, unit_out: str) -> str:
        """Render a one-line plain-English sentence for the derivative."""
        if f.value is None:
            return "—"
        sign = "increase" if f.value >= 0 else "decrease"
        return (
            f"Each +1 {unit_in} of {f.parameter.label} → "
            f"{sign} of {abs(f.value):.3g} {unit_out} in {f.output_label}"
        )
