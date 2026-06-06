"""
Sensitivity-section customise dialog.

Concrete child of ``SectionCustomizeDialog``. Lets the user pick which
tornado figures, sweep figures, and tables land in the report's
sensitivity section.

UI is English-only (consistent with the live Sensitivity tab — the live
UI is not i18n'd per the project plan; only the report content
translates). Output / parameter labels in the dropdowns come from the
propulsion-aware ``display_label_for_*`` helpers so jets see "Engine
Thrust", Electric sees "Battery Energy Density", etc.

Form layout
───────────
  * Tornados — checkbox list of all 12 OUTPUT_CATALOG entries (filtered
    by ``is_included`` for the current brief). Default selection
    matches the live tab's three slots, or whatever the existing
    ``SensitivityReportConfig`` carries.
  * Sweeps — dynamic list of (output, input) pairs with "+ Add sweep"
    and per-row "−" buttons. Empty by default (the user opts in).
    Inputs are filtered to only those relevant for the current
    propulsion (see ``sweepable_parameters_for``).
  * Margins / Snowball — single checkbox each.

The dialog produces a ``SensitivityReportConfig`` on accept;
``ExportDialog`` stores it on the section's ``SectionEntry.config``.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.reports.base import SectionConfig
from app.core.reports.sections.sensitivity_analysis import (
    SensitivityReportConfig,
)
from app.core.sensitivity import (
    OUTPUT_CATALOG,
    SweepableParameter,
    display_label_for_output,
    display_label_for_parameter,
    sweepable_parameters_for,
)
from app.state.store import AppStore
from app.ui.dialogs.section_customize_dialog import SectionCustomizeDialog


class SensitivityReportConfigDialog(SectionCustomizeDialog):
    """Customise dialog for the Design Sensitivity Analysis section."""

    def __init__(
        self,
        store: AppStore,
        initial_config: Optional[SensitivityReportConfig] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(
            title="Customise — Design Sensitivity Analysis",
            parent=parent,
        )
        # Stored BEFORE _setup_layout so _build_form / _populate_from_config
        # can read them.
        self._store = store
        self._brief = store.state.sizing.brief
        self._propulsion = self._brief.propulsion_type

        # Widget refs populated in _build_form so _populate_from_config
        # and _collect_config can address them by name.
        self._tornado_list: QListWidget
        self._sweep_rows_layout: QVBoxLayout
        self._sweep_rows: list[tuple[QWidget, QComboBox, QComboBox]] = []
        self._chk_margins: QCheckBox
        self._chk_snowball: QCheckBox

        self._setup_layout(initial_config)

    # ── SectionCustomizeDialog hooks ──────────────────────────────────────

    def _build_form(self, layout: QVBoxLayout) -> None:
        # Tornados — checkable list of every output relevant to this brief
        tornado_group = QGroupBox("Tornado figures")
        tornado_layout = QVBoxLayout(tornado_group)
        tornado_help = QLabel(
            "Pick the outputs you want a tornado for. Default = the "
            "three slots on the Sensitivity tab."
        )
        tornado_help.setWordWrap(True)
        tornado_help.setStyleSheet("color: #888; font-size: 11px;")
        tornado_layout.addWidget(tornado_help)

        self._tornado_list = QListWidget()
        self._tornado_list.setMinimumHeight(180)
        self._populate_tornado_list()
        tornado_layout.addWidget(self._tornado_list)
        layout.addWidget(tornado_group)

        # Sweeps — dynamic (output, input) rows
        sweep_group = QGroupBox("Sweep figures")
        sweep_outer = QVBoxLayout(sweep_group)
        sweep_help = QLabel(
            "Add an OAT sweep for each (output, input) pair you want to "
            "trace. Each sweep adds ~210 ms to export time. Empty by "
            "default."
        )
        sweep_help.setWordWrap(True)
        sweep_help.setStyleSheet("color: #888; font-size: 11px;")
        sweep_outer.addWidget(sweep_help)

        # Container that owns the dynamic rows. Each row is a QHBoxLayout
        # of (output combo, input combo, "−" button).
        sweep_scroll = QScrollArea()
        sweep_scroll.setWidgetResizable(True)
        sweep_scroll.setFrameShape(sweep_scroll.Shape.NoFrame)
        sweep_scroll.setMinimumHeight(120)
        sweep_host = QWidget()
        self._sweep_rows_layout = QVBoxLayout(sweep_host)
        self._sweep_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._sweep_rows_layout.setSpacing(4)
        self._sweep_rows_layout.addStretch(1)
        sweep_scroll.setWidget(sweep_host)
        sweep_outer.addWidget(sweep_scroll)

        add_btn = QPushButton("+  Add sweep")
        add_btn.clicked.connect(lambda: self._add_sweep_row(None, None))
        sweep_outer.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(sweep_group)

        # Tables — include flags
        tables_group = QGroupBox("Tables")
        tables_layout = QVBoxLayout(tables_group)
        self._chk_margins = QCheckBox("Include constraint margins table")
        self._chk_margins.setChecked(True)
        self._chk_snowball = QCheckBox("Include snowball factor table")
        self._chk_snowball.setChecked(True)
        tables_layout.addWidget(self._chk_margins)
        tables_layout.addWidget(self._chk_snowball)
        layout.addWidget(tables_group)

    def _populate_from_config(self, config: SectionConfig) -> None:
        if not isinstance(config, SensitivityReportConfig):
            return
        # Tornados — tick the items matching the config
        chosen = set(config.tornado_output_ids)
        for i in range(self._tornado_list.count()):
            item = self._tornado_list.item(i)
            oid = item.data(Qt.ItemDataRole.UserRole)
            item.setCheckState(
                Qt.CheckState.Checked if oid in chosen
                else Qt.CheckState.Unchecked
            )
        # Sweeps — clear existing rows, then add one per spec
        self._clear_sweep_rows()
        for output_id, input_field in config.sweep_specs:
            self._add_sweep_row(output_id, input_field)
        # Tables
        self._chk_margins.setChecked(config.include_margins)
        self._chk_snowball.setChecked(config.include_snowball)

    def _collect_config(self) -> SensitivityReportConfig:
        # Tornados — preserve list order
        tornado_ids: list[str] = []
        for i in range(self._tornado_list.count()):
            item = self._tornado_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                tornado_ids.append(item.data(Qt.ItemDataRole.UserRole))

        # Sweeps — collect each row's (output, input)
        sweep_specs: list[tuple[str, str]] = []
        for _row_widget, out_combo, in_combo in self._sweep_rows:
            out_id = out_combo.currentData()
            in_field = in_combo.currentData()
            if out_id and in_field:
                sweep_specs.append((out_id, in_field))

        return SensitivityReportConfig(
            tornado_output_ids=tuple(tornado_ids),
            sweep_specs=tuple(sweep_specs),
            include_margins=self._chk_margins.isChecked(),
            include_snowball=self._chk_snowball.isChecked(),
        )

    def _validate_form(self) -> bool:
        # Warn (not block) when everything is disabled — the export will
        # produce a placeholder note. User can confirm if they meant it.
        cfg = self._collect_config()
        if not (cfg.tornado_output_ids or cfg.sweep_specs
                or cfg.include_margins or cfg.include_snowball):
            ans = QMessageBox.question(
                self,
                "Empty section",
                "No tornados, no sweeps, no tables — the section will "
                "render only a placeholder note. Continue?",
            )
            return ans == QMessageBox.StandardButton.Yes
        return True

    # ── Internal helpers ──────────────────────────────────────────────────

    def _populate_tornado_list(self) -> None:
        """Add one checkable row per OUTPUT_CATALOG entry that's
        ``is_included`` for the current brief."""
        for output_id, spec in OUTPUT_CATALOG.items():
            if not spec.is_included(self._brief):
                continue
            label = display_label_for_output(output_id, self._propulsion)
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, output_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._tornado_list.addItem(item)

    def _add_sweep_row(
        self,
        preselected_output: Optional[str],
        preselected_input: Optional[str],
    ) -> None:
        """Create one (output, input, remove) row in the sweep list."""
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)

        out_combo = QComboBox()
        out_combo.setMinimumWidth(180)
        for output_id, spec in OUTPUT_CATALOG.items():
            if not spec.is_included(self._brief):
                continue
            label = display_label_for_output(output_id, self._propulsion)
            out_combo.addItem(label, output_id)
        if preselected_output is not None:
            for i in range(out_combo.count()):
                if out_combo.itemData(i) == preselected_output:
                    out_combo.setCurrentIndex(i)
                    break

        in_combo = QComboBox()
        in_combo.setMinimumWidth(200)
        for param in sweepable_parameters_for(self._brief):
            label = display_label_for_parameter(param, self._propulsion)
            in_combo.addItem(label, param.field_name)
        if preselected_input is not None:
            for i in range(in_combo.count()):
                if in_combo.itemData(i) == preselected_input:
                    in_combo.setCurrentIndex(i)
                    break

        remove_btn = QPushButton("−")
        remove_btn.setFixedWidth(28)
        remove_btn.setToolTip("Remove this sweep")

        row_layout.addWidget(QLabel("Output:"))
        row_layout.addWidget(out_combo, stretch=2)
        row_layout.addWidget(QLabel("vs"))
        row_layout.addWidget(in_combo, stretch=3)
        row_layout.addWidget(remove_btn)

        # Insert above the trailing stretch so new rows stack from the top.
        insert_index = max(self._sweep_rows_layout.count() - 1, 0)
        self._sweep_rows_layout.insertWidget(insert_index, row_widget)
        self._sweep_rows.append((row_widget, out_combo, in_combo))

        remove_btn.clicked.connect(
            lambda: self._remove_sweep_row(row_widget)
        )

    def _remove_sweep_row(self, row_widget: QWidget) -> None:
        for i, (rw, _o, _in) in enumerate(self._sweep_rows):
            if rw is row_widget:
                self._sweep_rows.pop(i)
                rw.setParent(None)
                rw.deleteLater()
                return

    def _clear_sweep_rows(self) -> None:
        for rw, _o, _in in self._sweep_rows:
            rw.setParent(None)
            rw.deleteLater()
        self._sweep_rows.clear()
