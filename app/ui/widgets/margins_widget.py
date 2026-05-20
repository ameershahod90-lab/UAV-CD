"""
Constraint-margin gauges.

Shows how far the design point is from each constraint boundary, with
colour-coded severity (red <10 %, amber <30 %, green ≥30 %). The binding
constraint — the smallest positive margin — is highlighted because it's
the one that will bite first if any requirement tightens.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.sensitivity import MarginsReport


_SEVERITY_COLORS = {
    "critical": "#c0392b",   # red
    "tight":    "#e67e22",   # amber
    "ok":       "#27ae60",   # green
}


class MarginsWidget(QWidget):
    """Stack of constraint margins with coloured bars."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)

        self._binding_lbl = QLabel("")
        self._binding_lbl.setStyleSheet(
            "color: #cccccc; font-size: 10pt; padding: 4px;"
        )
        self._binding_lbl.setWordWrap(True)
        self._layout.addWidget(self._binding_lbl)

        # Grid for the rows
        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(8)
        self._grid.setVerticalSpacing(4)
        self._layout.addWidget(self._grid_widget)
        self._layout.addStretch(1)

    # ── Public ────────────────────────────────────────────────────────────

    def set_margins(self, report: MarginsReport) -> None:
        """Render the margins; highlight the binding constraint."""
        # Clear existing
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        # Headline
        if report.most_violated is not None:
            self._binding_lbl.setText(
                f"⚠  VIOLATED: {report.most_violated.name} "
                f"({report.most_violated.margin_pct:+.1f} %)"
            )
            self._binding_lbl.setStyleSheet(
                "color: #ff6b5d; font-size: 11pt; font-weight: bold; padding: 4px;"
            )
        elif report.binding is not None:
            self._binding_lbl.setText(
                f"Binding: {report.binding.name} — design has "
                f"{report.binding.margin_pct:.1f} % margin (bites first)"
            )
            self._binding_lbl.setStyleSheet(
                f"color: {_SEVERITY_COLORS[report.binding.severity]}; "
                "font-size: 11pt; font-weight: bold; padding: 4px;"
            )
        else:
            self._binding_lbl.setText("")

        # Rows
        for row, m in enumerate(report.margins):
            name_lbl = QLabel(m.name)
            name_lbl.setStyleSheet("color: #cccccc; font-size: 10pt;")
            name_lbl.setMinimumWidth(120)

            bar = QProgressBar()
            bar.setRange(-50, 100)
            # Clamp to display range — actual value still shown in text
            clamped = max(-50, min(100, m.margin_pct))
            bar.setValue(int(clamped))
            bar.setTextVisible(False)
            bar.setFixedHeight(14)
            color = _SEVERITY_COLORS[m.severity]
            bar.setStyleSheet(
                f"""
                QProgressBar {{
                    background: #222230;
                    border: 1px solid #3a3a4a;
                    border-radius: 3px;
                }}
                QProgressBar::chunk {{
                    background: {color};
                    border-radius: 2px;
                }}
                """
            )

            pct_lbl = QLabel(f"{m.margin_pct:+.1f} %")
            pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            pct_lbl.setStyleSheet(f"color: {color}; font-size: 10pt; font-weight: bold;")
            pct_lbl.setMinimumWidth(60)

            self._grid.addWidget(name_lbl, row, 0)
            self._grid.addWidget(bar,      row, 1)
            self._grid.addWidget(pct_lbl,  row, 2)

    def clear(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._binding_lbl.setText("")
