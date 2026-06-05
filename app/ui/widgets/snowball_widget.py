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

from app.core.display_converter import DisplayConverter
from app.core.enums import PropulsionType
from app.core.sensitivity import (
    SnowballFactor,
    SnowballReport,
    display_label_for_output,
    display_label_for_parameter,
    unit_kind_for_output,
    unit_kind_for_parameter,
)


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
        # Reduced from 180 → 140 so the snowball + margins row fits on a
        # 1280×860 viewport. QScrollArea on the tab handles overflow when
        # the user wants more rows visible at once.
        self._table.setMinimumHeight(140)
        layout.addWidget(self._table)

        # Cached for live re-render when the user changes units.
        self._current_report: Optional[SnowballReport] = None
        self._current_converter: Optional[DisplayConverter] = None
        self._current_propulsion_type: Optional[PropulsionType] = None

    # ── Public ────────────────────────────────────────────────────────────

    def set_factors(
        self,
        report: SnowballReport,
        *,
        converter: DisplayConverter,
        propulsion_type: PropulsionType,
    ) -> None:
        """Render the snowball table with propulsion-aware labels + units.

        Output and input values are converted via ``DisplayConverter`` so
        the table honours the user's unit preferences. Derivative values
        are linearly scaled — for a derivative ``∂Y/∂X`` measured in
        SI, the display value is ``si_value × (Y_factor / X_factor)`` —
        and reflect the displayed units in both the numerator and
        denominator.
        """
        self._current_report = report
        self._current_converter = converter
        self._current_propulsion_type = propulsion_type

        self._table.setRowCount(len(report.factors))
        for row, f in enumerate(report.factors):
            out_factor, out_unit = self._convert_output(f, converter, propulsion_type)
            in_factor,  in_unit  = self._convert_parameter(f, converter)

            label_in  = display_label_for_parameter(f.parameter, propulsion_type)
            label_out = display_label_for_output(f.output_id, propulsion_type)

            sym_item = QTableWidgetItem(f"∂{label_out} / ∂{label_in}")
            sym_item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )
            self._table.setItem(row, 0, sym_item)

            if f.value is None or in_factor == 0:
                value_item = QTableWidgetItem("—")
                interp_item = QTableWidgetItem("Could not compute (pipeline failed)")
            else:
                # ∂Y_display / ∂X_display = (∂Y_si / ∂X_si) × Y_factor / X_factor
                display_value = f.value * out_factor / in_factor
                value_item = QTableWidgetItem(
                    f"{display_value:+.4g} {out_unit}/{in_unit}"
                )
                interp_item = QTableWidgetItem(
                    self._format_interpretation(
                        label_in, label_out,
                        in_unit, out_unit, display_value,
                    )
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
    def _convert_output(
        f: SnowballFactor,
        converter: DisplayConverter,
        propulsion_type: PropulsionType,
    ) -> tuple[float, str]:
        """Resolve (factor, unit) for the snowball factor's output side."""
        kind = unit_kind_for_output(f.output_id, propulsion_type)
        method = getattr(converter, kind, None)
        if method is None:
            return 1.0, f.output_unit
        return method(1.0)

    @staticmethod
    def _convert_parameter(
        f: SnowballFactor, converter: DisplayConverter,
    ) -> tuple[float, str]:
        """Resolve (factor, unit) for the snowball factor's input side."""
        kind = unit_kind_for_parameter(f.parameter)
        method = getattr(converter, kind, None)
        if method is None:
            return 1.0, f.parameter.unit
        # Dimensionless parameters (CD0, AR, …) use the "ratio"
        # passthrough method which returns the bland "—" placeholder;
        # the parameter's own unit string is more informative for those.
        if kind == "ratio":
            return 1.0, f.parameter.unit
        return method(1.0)

    @staticmethod
    def _format_interpretation(
        label_in: str,
        label_out: str,
        unit_in: str,
        unit_out: str,
        display_value: float,
    ) -> str:
        """One-line plain-English sentence for the derivative (display units)."""
        sign = "increase" if display_value >= 0 else "decrease"
        return (
            f"Each +1 {unit_in} of {label_in} → "
            f"{sign} of {abs(display_value):.3g} {unit_out} in {label_out}"
        )
