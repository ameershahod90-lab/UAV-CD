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
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

import dataclasses

from app.core.display_converter import DisplayConverter
from app.core.enums import PropulsionType
from app.core.sensitivity import (
    OUTPUT_CATALOG,
    SweepableParameter,
    display_label_for_output,
    unit_kind_for_output,
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
        # Most recently dispatched sweep — cached so unit / propulsion
        # changes can re-render without re-running the pipeline.
        self._last_sweep = None
        self._build_ui()
        # Connect service signals — refresh when the snapshot updates
        self._service.sensitivity_updated.connect(self._on_snapshot_updated)
        # React to display-unit changes: the widgets all consume
        # DisplayConverter, so flipping mass/area/power units in
        # Settings must repaint every panel.
        self._store.settings_changed.connect(self._rerender_from_cache)

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Scroll wrapper — consistent with WeightTab / SettingsTab / etc.
        # so the studio remains usable on shorter viewports without clipping
        # the four-panel layout.
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        content = QWidget()
        scroll.setWidget(content)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        outer = QVBoxLayout(content)
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

        # ── Inline config toolbar ─────────────────────────────────────────
        # Δ% (tornado / sweep perturbation width) and N points (sweep
        # sample count) are persisted in UserSettings so the studio
        # remembers them across sessions. The toolbar writes back to
        # the store on commit; the service re-runs the snapshot on
        # settings_changed automatically.
        config_row = QHBoxLayout()
        config_row.setSpacing(8)

        config_row.addWidget(QLabel("Δ %:"))
        self._delta_spin = QDoubleSpinBox()
        self._delta_spin.setRange(5.0, 50.0)
        self._delta_spin.setDecimals(1)
        self._delta_spin.setSingleStep(1.0)
        self._delta_spin.setSuffix(" %")
        self._delta_spin.setValue(self._store.settings.sens_delta_pct)
        self._delta_spin.setToolTip(
            "Perturbation width applied to each input for the tornado and "
            "sweep charts (default 20 %).",
        )
        self._delta_spin.editingFinished.connect(self._on_delta_changed)
        config_row.addWidget(self._delta_spin)

        config_row.addSpacing(16)
        config_row.addWidget(QLabel("Sweep N points:"))
        self._npts_spin = QSpinBox()
        self._npts_spin.setRange(11, 51)
        self._npts_spin.setSingleStep(2)
        self._npts_spin.setValue(self._store.settings.sens_n_points)
        self._npts_spin.setToolTip(
            "Number of sample points along an OAT sweep (odd-only).",
        )
        self._npts_spin.editingFinished.connect(self._on_npts_changed)
        config_row.addWidget(self._npts_spin)

        config_row.addStretch(1)
        config_row.addWidget(QLabel(
            "<i>Severity thresholds: Settings → Sensitivity</i>"
        ))
        outer.addLayout(config_row)

        # ── Section 1: tornado row (3 slots, each switchable) ─────────────
        #
        # Vertical sections are STACKED, not split. Each section owns a
        # comfortable preferred height; if the total exceeds the viewport
        # the QScrollArea engages and the user scrolls. Resizing one
        # section does NOT steal space from siblings (the old QSplitter
        # behaviour was incompatible with QScrollArea — growing one panel
        # would shrink the next instead of growing total page height).
        # The horizontal splitter between margins / snowball is kept
        # because side-by-side has no vertical-scroll conflict.
        #
        # Each of the three slots has its own output dropdown so the
        # designer can swap any of the 12 OUTPUT_CATALOG entries into
        # any slot. Default = the Tier-1 trio (MTOW / Wing Area /
        # Engine Power). Selection is persisted in UserSettings.
        tornado_group = QGroupBox(
            "What drives the design? — tornado of input impact"
        )
        tornado_group.setMinimumHeight(360)
        tornado_layout = QHBoxLayout(tornado_group)
        tornado_layout.setSpacing(8)

        # Per-slot containers — each is (combo, widget) so we can swap
        # the displayed output_id while keeping the slot's position.
        self._tornado_slots: list[tuple[QComboBox, TornadoWidget]] = []
        configured = self._store.settings.sens_tornado_output_ids
        for slot_idx in range(3):
            slot_box = QVBoxLayout()
            slot_box.setContentsMargins(0, 0, 0, 0)
            slot_box.setSpacing(2)

            slot_combo = QComboBox()
            for output_id in OUTPUT_CATALOG.keys():
                # Label populated propulsion-agnostically here; the
                # _refresh_tornado_slot_combos call after first
                # snapshot rewrites them with the right propulsion label.
                spec = OUTPUT_CATALOG[output_id]
                slot_combo.addItem(f"{spec.label} [{spec.unit}]", output_id)
            # Preselect from persisted settings (fallback to the
            # corresponding Tier-1 entry if invalid).
            chosen = (
                configured[slot_idx] if slot_idx < len(configured)
                else _TIER_1[slot_idx]
            )
            for i in range(slot_combo.count()):
                if slot_combo.itemData(i) == chosen:
                    slot_combo.setCurrentIndex(i)
                    break
            slot_combo.currentIndexChanged.connect(
                lambda _idx, s=slot_idx: self._on_tornado_slot_changed(s),
            )
            slot_box.addWidget(slot_combo)

            tw = TornadoWidget()
            tw.parameter_clicked.connect(self._on_tornado_bar_clicked)
            slot_box.addWidget(tw, stretch=1)

            container = QWidget()
            container.setLayout(slot_box)
            tornado_layout.addWidget(container, stretch=1)
            self._tornado_slots.append((slot_combo, tw))
        outer.addWidget(tornado_group)

        # ── Section 2: sweep panel ────────────────────────────────────────
        sweep_group = QGroupBox(
            "Deep-dive — vary one input across the configured Δ %, "
            "watch outputs respond"
        )
        sweep_group.setMinimumHeight(320)
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
        outer.addWidget(sweep_group)

        # ── Section 3: margins | snowball row (horizontal splitter) ───────
        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        h_splitter.setMinimumHeight(280)

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
        outer.addWidget(h_splitter)

    # ── Signal handlers ───────────────────────────────────────────────────

    def _dc(self) -> DisplayConverter:
        """Build a fresh DisplayConverter from current settings."""
        return DisplayConverter(self._store.settings)

    def _propulsion_type(self) -> PropulsionType:
        return self._store.state.sizing.brief.propulsion_type

    def _on_snapshot_updated(self) -> None:
        snap = self._service.snapshot
        if snap is None:
            return
        dc = self._dc()
        propulsion = self._propulsion_type()

        # Refresh tornado slot combos so their labels reflect the
        # current propulsion (Engine Power ↔ Engine Thrust etc).
        self._refresh_tornado_slot_combos()

        # Tornado: render each of the three slots with whatever output
        # is currently selected in that slot's combo.
        for slot_idx, (combo, widget) in enumerate(self._tornado_slots):
            output_id = combo.currentData()
            data = snap.tornado_by_output.get(output_id)
            if data is None:
                widget.clear()
                continue
            self._update_tornado_title(output_id, widget, dc, propulsion)
            widget.set_data(
                data, converter=dc, propulsion_type=propulsion,
            )

        # Margins (% values, no SI conversion needed)
        self._margins_widget.set_margins(snap.margins)

        # Snowball: propulsion-aware labels + DC ratio rescale
        self._snowball_widget.set_factors(
            snap.snowball,
            converter=dc,
            propulsion_type=propulsion,
        )

        # Sweep: re-render the cached sweep (if any) under new propulsion
        # so the existing curve picks up the right label / units.
        if self._last_sweep is not None:
            self._sweep_widget.set_sweep(
                self._last_sweep, self._sweep_output_ids,
                converter=dc, propulsion_type=propulsion,
            )

        # Refresh sweep combos so propulsion gating / units reflect
        # the current state.
        self._refresh_sweep_param_combo()
        self._refresh_sweep_output_combo()

        self._status_lbl.setText(
            "Sensitivity analysis — click any tornado bar to deep-dive that "
            "parameter; pick any output in a slot's dropdown."
        )

    def _update_tornado_title(
        self,
        output_id: str,
        widget: TornadoWidget,
        dc: DisplayConverter,
        propulsion: PropulsionType,
    ) -> None:
        """Refresh a tornado's group title with propulsion + unit."""
        label = display_label_for_output(output_id, propulsion)
        kind = unit_kind_for_output(output_id, propulsion)
        method = getattr(dc, kind, None)
        unit = method(1.0)[1] if method is not None else ""
        widget._plot.setTitle(
            f"{label} [{unit}]", color="#ccccdd", size="10pt",
        )

    def _rerender_from_cache(self) -> None:
        """Re-render widgets when the user changes display-unit settings.

        Does NOT re-run the sizing pipeline — the cached
        ``SensitivitySnapshot`` is replayed through the widgets with a
        fresh ``DisplayConverter``. (Settings that *do* invalidate the
        snapshot — Δ%, severity thresholds, tornado output slots — are
        handled in ``SensitivityService._on_settings_changed`` which
        recomputes the snapshot and fires ``sensitivity_updated``.)
        """
        snap = self._service.snapshot
        if snap is None:
            return
        dc = self._dc()
        propulsion = self._propulsion_type()
        # Sync the toolbar widgets in case settings changed elsewhere.
        self._sync_toolbar_from_settings()
        self._refresh_tornado_slot_combos()
        for combo, widget in self._tornado_slots:
            output_id = combo.currentData()
            data = snap.tornado_by_output.get(output_id)
            if data is None:
                widget.clear()
                continue
            self._update_tornado_title(output_id, widget, dc, propulsion)
            widget.set_data(
                data, converter=dc, propulsion_type=propulsion,
            )
        self._snowball_widget.set_factors(
            snap.snowball, converter=dc, propulsion_type=propulsion,
        )
        if self._last_sweep is not None:
            self._sweep_widget.set_sweep(
                self._last_sweep, self._sweep_output_ids,
                converter=dc, propulsion_type=propulsion,
            )
        # Settings change can also flip displayed units in the combos.
        self._refresh_sweep_param_combo()
        self._refresh_sweep_output_combo()

    def _refresh_sweep_param_combo(self) -> None:
        """Rebuild the parameter dropdown with current units + propulsion gating."""
        from app.core.sensitivity import unit_kind_for_parameter

        params = self._service.sweepable_parameters()
        dc = self._dc()
        current_field = (
            self._current_sweep_param.field_name
            if self._current_sweep_param else None
        )
        self._sweep_param_combo.blockSignals(True)
        self._sweep_param_combo.clear()
        for p in params:
            kind = unit_kind_for_parameter(p)
            method = getattr(dc, kind, None)
            if method is None or kind == "ratio":
                unit_label = p.unit
            else:
                unit_label = method(1.0)[1]
            self._sweep_param_combo.addItem(
                f"{p.label}  [{unit_label}]", p,
            )
        # Try to restore previous selection
        if current_field:
            for i in range(self._sweep_param_combo.count()):
                p = self._sweep_param_combo.itemData(i)
                if p and p.field_name == current_field:
                    self._sweep_param_combo.setCurrentIndex(i)
                    break
        self._sweep_param_combo.blockSignals(False)

    def _refresh_sweep_output_combo(self) -> None:
        """Rebuild the output dropdown with propulsion-aware labels + units."""
        dc = self._dc()
        propulsion = self._propulsion_type()
        current_data = self._sweep_output_combo.currentData()
        self._sweep_output_combo.blockSignals(True)
        self._sweep_output_combo.clear()
        self._sweep_output_combo.addItem("All Tier-1 (MTOW, S, P)", _TIER_1)
        for output_id in OUTPUT_CATALOG.keys():
            label = display_label_for_output(output_id, propulsion)
            kind = unit_kind_for_output(output_id, propulsion)
            method = getattr(dc, kind, None)
            unit_label = method(1.0)[1] if method is not None else ""
            self._sweep_output_combo.addItem(
                f"{label} only [{unit_label}]", (output_id,),
            )
        # Restore the previous selection by payload comparison
        if current_data is not None:
            for i in range(self._sweep_output_combo.count()):
                if self._sweep_output_combo.itemData(i) == current_data:
                    self._sweep_output_combo.setCurrentIndex(i)
                    break
        self._sweep_output_combo.blockSignals(False)

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
        # PR4 behaviour: re-render the cached sweep against the new
        # output set immediately — no pipeline run required because the
        # OATSweep already carries every output via outcome.get().
        if self._last_sweep is not None:
            self._sweep_widget.set_sweep(
                self._last_sweep, self._sweep_output_ids,
                converter=self._dc(),
                propulsion_type=self._propulsion_type(),
            )

    def _run_sweep(self) -> None:
        param = self._sweep_param_combo.currentData()
        if param is None:
            return
        # n_points / delta_pct fall through to UserSettings defaults
        # when omitted (see SensitivityService.run_sweep).
        sweep = self._service.run_sweep(param)
        if sweep is None:
            return
        self._last_sweep = sweep
        self._sweep_widget.set_sweep(
            sweep, self._sweep_output_ids,
            converter=self._dc(),
            propulsion_type=self._propulsion_type(),
        )

    # ── Config toolbar handlers ───────────────────────────────────────────

    def _on_delta_changed(self) -> None:
        """Persist the new Δ% to UserSettings — service auto-recomputes."""
        new_val = float(self._delta_spin.value())
        if new_val == self._store.settings.sens_delta_pct:
            return
        self._store.update_settings(dataclasses.replace(
            self._store.settings, sens_delta_pct=new_val,
        ))

    def _on_npts_changed(self) -> None:
        """Persist the new N points — only the next ``Run sweep`` reads it."""
        new_val = int(self._npts_spin.value())
        if new_val == self._store.settings.sens_n_points:
            return
        self._store.update_settings(dataclasses.replace(
            self._store.settings, sens_n_points=new_val,
        ))

    def _sync_toolbar_from_settings(self) -> None:
        """Pull current settings into the toolbar widgets without echoing."""
        s = self._store.settings
        self._delta_spin.blockSignals(True)
        self._delta_spin.setValue(s.sens_delta_pct)
        self._delta_spin.blockSignals(False)
        self._npts_spin.blockSignals(True)
        self._npts_spin.setValue(s.sens_n_points)
        self._npts_spin.blockSignals(False)

    # ── Tornado-slot handlers ─────────────────────────────────────────────

    def _on_tornado_slot_changed(self, slot_idx: int) -> None:
        """Persist the new output pick for ``slot_idx`` and recompute."""
        new_id = self._tornado_slots[slot_idx][0].currentData()
        if not new_id:
            return
        current = list(self._store.settings.sens_tornado_output_ids)
        while len(current) < 3:
            current.append(_TIER_1[len(current)])
        if current[slot_idx] == new_id:
            return
        current[slot_idx] = new_id
        self._store.update_settings(dataclasses.replace(
            self._store.settings,
            sens_tornado_output_ids=tuple(current),  # type: ignore[arg-type]
        ))

    def _refresh_tornado_slot_combos(self) -> None:
        """Re-label slot combos with propulsion-aware names + DC units."""
        dc = self._dc()
        propulsion = self._propulsion_type()
        for slot_idx, (combo, _widget) in enumerate(self._tornado_slots):
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for output_id in OUTPUT_CATALOG.keys():
                label = display_label_for_output(output_id, propulsion)
                kind = unit_kind_for_output(output_id, propulsion)
                method = getattr(dc, kind, None)
                unit_label = method(1.0)[1] if method is not None else ""
                combo.addItem(f"{label} [{unit_label}]", output_id)
            # Restore selection (or fall back to the slot's default).
            target = current or _TIER_1[slot_idx]
            for i in range(combo.count()):
                if combo.itemData(i) == target:
                    combo.setCurrentIndex(i)
                    break
            combo.blockSignals(False)
