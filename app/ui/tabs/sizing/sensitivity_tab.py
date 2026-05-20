"""
Sensitivity Studio — sub-tab of Phase 1.

Composes four coordinated views:
  1. Tornado (top)         — Tier-1 small multiples (MTOW / S / P)
  2. OAT sweep (below)     — drilled-down curve, triggered by clicking a bar
  3. Constraint margins    — right-hand panel
  4. Snowball factors      — bottom-left panel

Layout uses QSplitter so the user can drag the panel boundaries to suit
their screen. No drag-and-drop dashboarding — see Session decision log
for the rationale (opinionated curated layout beats free-form for
domain-specific design tools).
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.core.sensitivity import (
    OUTPUT_CATALOG,
    SweepableParameter,
)
from app.services.sensitivity_service import SensitivityService
from app.state.store import AppStore
from app.ui.widgets.margins_widget import MarginsWidget
from app.ui.widgets.snowball_widget import SnowballWidget
from app.ui.widgets.sweep_widget import SweepWidget
from app.ui.widgets.tornado_widget import TornadoWidget


_TIER_1 = ("mtow_kg", "wing_area_m2", "engine_power_w")


class SensitivityTab(QWidget):
    """Phase 1 → Sensitivity sub-tab."""

    def __init__(
        self,
        store: AppStore,
        service: SensitivityService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._service = service
        self._sweep_output_ids: list[str] = list(_TIER_1)
        self._current_sweep_param: Optional[SweepableParameter] = None
        self._build_ui()
        # Connect service signals — refresh when the snapshot updates
        self._service.sensitivity_updated.connect(self._on_snapshot_updated)

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # Headline / status row
        self._status_lbl = QLabel(
            "Sensitivity analysis — run sizing to populate."
        )
        self._status_lbl.setStyleSheet(
            "color: #aaaacc; padding: 4px;"
        )
        outer.addWidget(self._status_lbl)

        # ── Top splitter: tornado row + sweep ─────────────────────────────
        v_splitter = QSplitter(Qt.Orientation.Vertical)

        # Tornado row: 3 charts (MTOW | S | P) side by side
        tornado_group = QGroupBox(
            "What drives the design? — tornado of ±20 % input impact"
        )
        tornado_layout = QHBoxLayout(tornado_group)
        tornado_layout.setSpacing(4)
        self._tornado_widgets: dict[str, TornadoWidget] = {}
        for output_id in _TIER_1:
            spec = OUTPUT_CATALOG[output_id]
            tw = TornadoWidget(title=f"{spec.label} [{spec.unit}]")
            tw.parameter_clicked.connect(self._on_tornado_bar_clicked)
            self._tornado_widgets[output_id] = tw
            tornado_layout.addWidget(tw, stretch=1)
        v_splitter.addWidget(tornado_group)

        # Sweep panel (lower)
        sweep_group = QGroupBox(
            "Deep-dive — vary one input across ±20 %, watch all outputs respond"
        )
        sweep_outer = QVBoxLayout(sweep_group)

        # Sweep controls row
        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("Sweep parameter:"))
        self._sweep_param_combo = QComboBox()
        self._sweep_param_combo.setMinimumWidth(200)
        self._sweep_param_combo.currentIndexChanged.connect(
            self._on_sweep_param_changed,
        )
        ctrl_row.addWidget(self._sweep_param_combo, stretch=1)

        ctrl_row.addWidget(QLabel("Show:"))
        self._sweep_output_combo = QComboBox()
        self._sweep_output_combo.addItem("All Tier-1 (MTOW, S, P)", _TIER_1)
        for output_id, spec in OUTPUT_CATALOG.items():
            self._sweep_output_combo.addItem(
                f"{spec.label} only [{spec.unit}]", (output_id,),
            )
        self._sweep_output_combo.currentIndexChanged.connect(
            self._on_sweep_output_changed,
        )
        ctrl_row.addWidget(self._sweep_output_combo)

        self._run_sweep_btn = QPushButton("Run sweep")
        self._run_sweep_btn.clicked.connect(self._run_sweep)
        ctrl_row.addWidget(self._run_sweep_btn)
        sweep_outer.addLayout(ctrl_row)

        self._sweep_widget = SweepWidget()
        sweep_outer.addWidget(self._sweep_widget, stretch=1)
        v_splitter.addWidget(sweep_group)
        v_splitter.setStretchFactor(0, 3)
        v_splitter.setStretchFactor(1, 2)

        # ── Bottom row: margins | snowball ────────────────────────────────
        h_splitter = QSplitter(Qt.Orientation.Horizontal)

        margins_group = QGroupBox(
            "What bites first? — margin to each constraint"
        )
        margins_layout = QVBoxLayout(margins_group)
        self._margins_widget = MarginsWidget()
        margins_layout.addWidget(self._margins_widget)
        h_splitter.addWidget(margins_group)

        snowball_group = QGroupBox(
            "Design rules of thumb — ∂(output)/∂(input) at the design point"
        )
        snowball_layout = QVBoxLayout(snowball_group)
        self._snowball_widget = SnowballWidget()
        snowball_layout.addWidget(self._snowball_widget)
        h_splitter.addWidget(snowball_group)
        h_splitter.setStretchFactor(0, 2)
        h_splitter.setStretchFactor(1, 3)

        # Vertical splitter to combine the top half + bottom row
        master_splitter = QSplitter(Qt.Orientation.Vertical)
        master_splitter.addWidget(v_splitter)
        master_splitter.addWidget(h_splitter)
        master_splitter.setStretchFactor(0, 3)
        master_splitter.setStretchFactor(1, 2)
        outer.addWidget(master_splitter, stretch=1)

    # ── Signal handlers ───────────────────────────────────────────────────

    def _on_snapshot_updated(self) -> None:
        snap = self._service.snapshot
        if snap is None:
            return
        # Tornado: render the three Tier-1 charts
        for output_id, widget in self._tornado_widgets.items():
            data = snap.tornado_by_output.get(output_id)
            if data is not None:
                widget.set_data(data)

        # Margins + snowball
        self._margins_widget.set_margins(snap.margins)
        self._snowball_widget.set_factors(snap.snowball)

        # Refresh sweep parameter combo if the propulsion type changed
        self._refresh_sweep_param_combo()

        self._status_lbl.setText(
            "Sensitivity analysis — click any tornado bar to deep-dive that "
            "parameter; drag the splitters to resize panels."
        )

    def _refresh_sweep_param_combo(self) -> None:
        params = self._service.sweepable_parameters()
        current_field = (
            self._current_sweep_param.field_name
            if self._current_sweep_param else None
        )
        self._sweep_param_combo.blockSignals(True)
        self._sweep_param_combo.clear()
        for p in params:
            self._sweep_param_combo.addItem(
                f"{p.label}  [{p.unit}]", p,
            )
        # Try to restore previous selection
        if current_field:
            for i in range(self._sweep_param_combo.count()):
                p = self._sweep_param_combo.itemData(i)
                if p and p.field_name == current_field:
                    self._sweep_param_combo.setCurrentIndex(i)
                    break
        self._sweep_param_combo.blockSignals(False)

    def _on_tornado_bar_clicked(self, parameter: SweepableParameter) -> None:
        # Select that parameter in the sweep combo and trigger a sweep
        for i in range(self._sweep_param_combo.count()):
            p = self._sweep_param_combo.itemData(i)
            if p and p.field_name == parameter.field_name:
                self._sweep_param_combo.setCurrentIndex(i)
                break
        self._run_sweep()

    def _on_sweep_param_changed(self, idx: int) -> None:
        self._current_sweep_param = self._sweep_param_combo.currentData()

    def _on_sweep_output_changed(self, idx: int) -> None:
        data = self._sweep_output_combo.itemData(idx)
        if data:
            self._sweep_output_ids = list(data)

    def _run_sweep(self) -> None:
        param = self._sweep_param_combo.currentData()
        if param is None:
            return
        sweep = self._service.run_sweep(param, n_points=21)
        if sweep is None:
            return
        self._sweep_widget.set_sweep(sweep, self._sweep_output_ids)
