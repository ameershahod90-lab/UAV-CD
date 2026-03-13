"""
Weight Tab — UAV-CD-APP
=========================
Displays weight buildup results: summary cards, convergence history plot,
and a weight breakdown pie chart.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.state.store import AppStore
from app.ui.widgets.result_card import ResultCard


class WeightTab(QWidget):
    """Weight convergence and breakdown visualisation."""

    def __init__(self, store: AppStore, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._store: AppStore = store

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # ── Result summary cards ──────────────────────────────────────────
        title = QLabel("Weight Summary")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        cards_row = QGridLayout()
        cards_row.setSpacing(10)

        self._card_wto   = ResultCard("MTOW", unit="kg")
        self._card_empty = ResultCard("Empty Weight", unit="kg")
        self._card_fb    = ResultCard("Fuel / Battery", unit="kg")
        self._card_ewf   = ResultCard("Empty Weight Fraction", unit="-")
        self._card_fbf   = ResultCard("Fuel/Battery Fraction", unit="-")
        self._card_iter  = ResultCard("Iterations")

        for i, card in enumerate([
            self._card_wto, self._card_empty, self._card_fb,
            self._card_ewf, self._card_fbf, self._card_iter,
        ]):
            cards_row.addWidget(card, i // 3, i % 3)

        layout.addLayout(cards_row)

        # ── Convergence plot ──────────────────────────────────────────────
        conv_title = QLabel("Convergence History")
        conv_title.setObjectName("SectionTitle")
        layout.addWidget(conv_title)

        self._conv_plot = pg.PlotWidget()
        self._conv_plot.setLabel("left", "W_TO", units="kg")
        self._conv_plot.setLabel("bottom", "Iteration")
        self._conv_plot.setMinimumHeight(200)
        self._conv_plot.setBackground("transparent")
        self._conv_plot.showGrid(x=True, y=True, alpha=0.3)
        layout.addWidget(self._conv_plot)

        # Connect to store
        self._store.weight_result_changed.connect(self._on_weight_result)

    # ── Internal ─────────────────────────────────────────────────────────

    def _on_weight_result(self) -> None:
        result = self._store.state.sizing.weight_result
        if result is None:
            return

        self._card_wto.set_value(result.w_to_kg, decimals=3)
        self._card_empty.set_value(result.w_empty_kg, decimals=3)
        self._card_fb.set_value(result.w_fuel_or_battery_kg, decimals=3)
        self._card_ewf.set_value(result.empty_weight_fraction, decimals=4)
        self._card_fbf.set_value(result.fuel_battery_fraction, decimals=4)
        self._card_iter.set_text(
            f"{result.iterations} {'✓' if result.converged else '⚠'}"
        )

        # Convergence plot
        self._conv_plot.clear()
        history = list(result.convergence_history)
        if len(history) >= 2:
            xs = list(range(len(history)))
            pen = pg.mkPen(color="#7c6af7", width=2)
            self._conv_plot.plot(xs, history, pen=pen, symbol="o",
                                 symbolSize=5, symbolBrush="#7c6af7")
