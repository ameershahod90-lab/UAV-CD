"""
Export Dialog — UAV-CD-APP
============================
Qt dialog for configuring and triggering report export.

Responsibilities:
  - Shows all registered sections in a checklist that the user can
    enable/disable and reorder (up/down) before exporting.
  - Collects report metadata: title, author, revision, format.
  - Captures figure PNGs from live pyqtgraph widgets via grabber callables.
  - Calls ExportService.export(config) in a QThread to keep UI responsive.
  - Shows a progress bar during rendering and a result toast when done.
"""

from __future__ import annotations

import logging
import os
from typing import Callable, Optional

from PyQt6.QtCore import (
    QThread, QObject, pyqtSignal, Qt
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.i18n import Language
from app.core.reports.base import SectionEntry, SectionRegistry
from app.core.reports.renderer import ExportFormat, ReportConfig
from app.core.reports.sections.sensitivity_analysis import (
    SensitivityReportConfig,
)

# Trigger auto-registration of all sections
import app.core.reports.sections  # noqa: F401

from app.services.export_service import ExportService
from app.state.store import AppStore
from app.ui.dialogs.section_customize_dialog import SectionCustomizeDialog
from app.ui.widgets.checkmark_box import CheckmarkBox

_LOG = logging.getLogger(__name__)


# ===========================================================================
# Worker thread
# ===========================================================================

class _ExportWorker(QObject):
    """Runs the export in a background thread to keep the UI responsive."""

    finished = pyqtSignal(bool, str)   # (success, message)

    def __init__(
        self,
        service: ExportService,
        config: ReportConfig,
    ) -> None:
        super().__init__()
        self._service = service
        self._config  = config

    def run(self) -> None:
        ok, msg = self._service.export(self._config)
        self.finished.emit(ok, msg)


# ===========================================================================
# Section row widget
# ===========================================================================

class _SectionRow(QWidget):
    """One row in the sections list: grip + checkbox + summary + optional
    customise button + category badge.

    Customisable sections (``cls.is_customizable == True``) carry a
    "⚙ Customise…" button that fires ``customise_requested(entry)``;
    the parent dialog handles the per-section dispatch. A small
    "★ <summary>" badge appears next to the title when
    ``entry.config is not None``, summarising the user's picks.
    """

    customise_requested = pyqtSignal(object)   # SectionEntry payload

    def __init__(
        self,
        entry: SectionEntry,
        title: str,
        description: str,
        category_label: str,
        is_customizable: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._entry = entry
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        # Drag grip indicator — visible cue so users know they can drag rows
        grip = QLabel("⠿")
        grip.setFixedWidth(18)
        grip.setToolTip("Drag to reorder")
        grip.setStyleSheet(
            "color: #1A5C96; font-size: 18px; font-weight: bold;"
            "background: transparent;"
        )
        layout.addWidget(grip)

        # CheckmarkBox carrying the section title — drop-in QCheckBox
        # subclass with the checkmark-only visual (see app/ui/widgets/
        # checkmark_box.py). All standard QCheckBox interactions still
        # work: click to toggle, space-bar when focused, etc.
        self._check = CheckmarkBox(title)
        self._check.setChecked(entry.enabled)
        self._check.setToolTip(description)
        self._check.toggled.connect(self._on_toggle)
        layout.addWidget(self._check, stretch=1)

        # Customisation summary badge (visible only when entry.config set)
        self._summary_lbl = QLabel("")
        self._summary_lbl.setStyleSheet(
            "color: #1A5C96; font-size: 10px; font-style: italic; "
            "background: transparent;"
        )
        self._refresh_summary_badge()
        layout.addWidget(self._summary_lbl)

        # Customise button — only shown for sections that opt in.
        if is_customizable:
            customise_btn = QPushButton("⚙")
            customise_btn.setObjectName("IconButton")
            customise_btn.setFixedSize(26, 22)
            customise_btn.setToolTip(
                f"Customise the {title} section's content."
            )
            customise_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            customise_btn.clicked.connect(
                lambda: self.customise_requested.emit(self._entry)
            )
            layout.addWidget(customise_btn)

        # Category badge
        badge = QLabel(category_label)
        badge.setStyleSheet(
            "color: #888; font-size: 9px; background: transparent;"
        )
        layout.addWidget(badge)

    def _on_toggle(self, checked: bool) -> None:
        self._entry.enabled = checked

    def _refresh_summary_badge(self) -> None:
        """Update the "★ <summary>" badge from entry.config (or hide if
        the section is using its default configuration)."""
        if self._entry.config is not None:
            self._summary_lbl.setText(
                f"★ {self._entry.config.summary()}"
            )
        else:
            self._summary_lbl.setText("")

    def refresh(self) -> None:
        """Public refresh hook so the parent dialog can update the badge
        after a successful customise dialog."""
        self._refresh_summary_badge()

    @property
    def entry(self) -> SectionEntry:
        return self._entry

    @property
    def is_enabled(self) -> bool:
        return self._check.isChecked()


# ===========================================================================
# Export Dialog
# ===========================================================================

class ExportDialog(QDialog):
    """Modal dialog for configuring and triggering report export.

    Figures (matching diagram, mission profile, weight pie chart) are
    rendered server-side by ``app/services/figure_renderers.py`` — no
    widget-grab callables are passed in. The ``figure_grabbers`` keyword
    argument is retained for backward compatibility but is unused.
    """

    def __init__(
        self,
        store: AppStore,
        figure_grabbers: Optional[dict[str, Callable[[], bytes]]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._store    = store
        self._service  = ExportService(store)
        self._entries: list[SectionEntry] = SectionRegistry.default_manifest()
        self._thread: Optional[QThread]   = None

        self.setWindowTitle("Export Report")
        # 560 (was 520) — eliminates the horizontal scrollbar the user
        # reported on the section row when the customise button and
        # category badge were present at the same time.
        self.setMinimumWidth(560)
        self.setMinimumHeight(640)
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Outer dialog layout: scroll wrapper + persistent button row.
        # The user reported that on shorter viewports the action buttons
        # (Move Up / Move Down / Select All / Select None) appeared to
        # overlap the last visible section row. The list's flexible
        # height was pushing them out of view. Wrapping the content in a
        # QScrollArea ensures any overflow scrolls cleanly.
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        # Vertical-scroll-only — horizontal scroll on the export dialog
        # body adds no value and clutters small viewports.
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        content = QWidget()
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── Metadata group ────────────────────────────────────────────────
        meta_group = QGroupBox("Report Metadata")
        form = QFormLayout(meta_group)

        self._title_edit = QLineEdit("UAV Conceptual Design Report")
        self._author_edit = QLineEdit(
            self._store.state.meta.author or ""
        )
        self._revision_edit = QLineEdit("1.0")

        # Language selector — defaults to English. (A Settings-level default
        # is planned for a later phase when the live UI itself gains i18n.)
        self._language_combo = QComboBox()
        for lang in Language:
            self._language_combo.addItem(lang.display_name, lang)

        form.addRow("Report Title:", self._title_edit)
        form.addRow("Author:",       self._author_edit)
        form.addRow("Revision:",     self._revision_edit)
        form.addRow("Language:",     self._language_combo)
        layout.addWidget(meta_group)

        # ── Output path ───────────────────────────────────────────────────
        path_group = QGroupBox("Output File")
        path_layout = QHBoxLayout(path_group)
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Choose save location…")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        path_layout.addWidget(self._path_edit, stretch=1)
        path_layout.addWidget(browse_btn)
        layout.addWidget(path_group)

        # ── Options ───────────────────────────────────────────────────────
        opts_group = QGroupBox("Options")
        opts_layout = QVBoxLayout(opts_group)
        self._eq_check  = CheckmarkBox("Include equation blocks")
        self._ref_check = CheckmarkBox("Include Sadraey section/equation references")
        self._eq_check.setChecked(True)
        self._ref_check.setChecked(True)
        opts_layout.addWidget(self._eq_check)
        opts_layout.addWidget(self._ref_check)
        layout.addWidget(opts_group)

        # ── Sections list ─────────────────────────────────────────────────
        sec_group = QGroupBox(
            "Sections  —  ☑ to include  •  ⠿ drag or ▲/▼ buttons to reorder"
        )
        sec_outer = QVBoxLayout(sec_group)
        sec_outer.setSpacing(8)

        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list.setDragEnabled(True)
        self._list.setAcceptDrops(True)
        self._list.setDropIndicatorShown(True)
        self._list.setMinimumHeight(280)
        self._populate_sections()
        sec_outer.addWidget(self._list)

        # Section action buttons sit on a real widget BELOW the list so
        # the layout never lets the QListWidget overflow on top of them
        # (the user reported the buttons appearing to float above the
        # last list row on shorter viewports).
        btn_widget = QWidget()
        btn_row = QHBoxLayout(btn_widget)
        btn_row.setContentsMargins(0, 4, 0, 0)
        btn_row.setSpacing(6)
        up_btn   = QPushButton("▲  Move Up")
        down_btn = QPushButton("▼  Move Down")
        all_btn  = QPushButton("✓  Select All")
        none_btn = QPushButton("✗  Select None")
        up_btn.clicked.connect(self._move_up)
        down_btn.clicked.connect(self._move_down)
        all_btn.clicked.connect(lambda: self._set_all(True))
        none_btn.clicked.connect(lambda: self._set_all(False))
        for b in [up_btn, down_btn, all_btn, none_btn]:
            btn_row.addWidget(b)
        sec_outer.addWidget(btn_widget)
        layout.addWidget(sec_group)

        # ── Progress (inside the scrollable body) ─────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)   # indeterminate
        self._progress.hide()
        layout.addWidget(self._progress)

        # ── Persistent footer (OUTSIDE the scroll area) ───────────────────
        # Export / Cancel always pinned to the bottom of the dialog so
        # they remain visible regardless of how the user scrolls the body.
        btn_box = QDialogButtonBox()
        self._export_btn = btn_box.addButton(
            "Export ▶", QDialogButtonBox.ButtonRole.AcceptRole
        )
        cancel_btn = btn_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        self._export_btn.clicked.connect(self._export)
        cancel_btn.clicked.connect(self.reject)
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 8, 12, 12)
        footer_layout.addWidget(btn_box)
        root.addWidget(footer)

    def _populate_sections(self, selected_row: int = -1) -> None:
        """
        Rebuild the QListWidget entirely from self._entries.

        self._entries is the single source of truth for order and enabled state.
        This approach avoids the Qt bug where takeItem/insertItem drops itemWidget
        associations, causing rows to appear blank after reordering.
        """
        # Before rebuilding, sync enabled states from existing widgets
        self._sync_enabled_from_widgets()

        self._list.clear()
        sections_by_id = {
            cls.section_id: cls
            for cls in SectionRegistry.all_sections()
        }
        for entry in self._entries:   # already in desired order
            cls = sections_by_id.get(entry.section_id)
            if cls is None:
                continue
            row_widget = _SectionRow(
                entry, cls.title, cls.description,
                cls.category.value,
                is_customizable=cls.is_customizable,
            )
            if cls.is_customizable:
                row_widget.customise_requested.connect(self._open_customise)
            item = QListWidgetItem(self._list)
            item.setSizeHint(row_widget.sizeHint())
            self._list.setItemWidget(item, row_widget)

        if 0 <= selected_row < self._list.count():
            self._list.setCurrentRow(selected_row)

    def _sync_enabled_from_widgets(self) -> None:
        """Copy enabled state from current widgets into self._entries."""
        for i in range(self._list.count()):
            item   = self._list.item(i)
            widget = self._list.itemWidget(item)
            if isinstance(widget, _SectionRow):
                widget.entry.enabled = widget.is_enabled

    def _move_up(self) -> None:
        row = self._list.currentRow()
        if row <= 0 or row >= len(self._entries):
            return
        # Sync enabled state first, then swap in the source-of-truth list
        self._sync_enabled_from_widgets()
        self._entries[row], self._entries[row - 1] = (
            self._entries[row - 1], self._entries[row]
        )
        self._populate_sections(selected_row=row - 1)

    def _move_down(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._entries) - 1:
            return
        self._sync_enabled_from_widgets()
        self._entries[row], self._entries[row + 1] = (
            self._entries[row + 1], self._entries[row]
        )
        self._populate_sections(selected_row=row + 1)

    def _set_all(self, checked: bool) -> None:
        self._sync_enabled_from_widgets()
        for entry in self._entries:
            entry.enabled = checked
        self._populate_sections(selected_row=self._list.currentRow())

    # ── Customise dispatch ────────────────────────────────────────────────

    def _open_customise(self, entry: SectionEntry) -> None:
        """Open the customise dialog appropriate for ``entry.section_id``.

        Today the dispatch table has exactly one entry. When a second
        customisable section appears, add one branch here — the
        per-section dialog hierarchy keeps each implementation isolated.
        """
        dlg: Optional[SectionCustomizeDialog] = None
        if entry.section_id == "sensitivity_analysis":
            from app.ui.dialogs.sensitivity_report_dialog import (
                SensitivityReportConfigDialog,
            )
            initial = (
                entry.config
                if isinstance(entry.config, SensitivityReportConfig)
                else None
            )
            dlg = SensitivityReportConfigDialog(
                self._store, initial_config=initial, parent=self,
            )
        else:
            _LOG.warning(
                "No customise dialog registered for section_id=%r",
                entry.section_id,
            )
            return

        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.config is not None:
            entry.config = dlg.config
            # Refresh the row's "★ <summary>" badge.
            for i in range(self._list.count()):
                item = self._list.item(i)
                row = self._list.itemWidget(item)
                if isinstance(row, _SectionRow) and row.entry is entry:
                    row.refresh()
                    break

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Report As", "", "Word Document (*.docx)"
        )
        if path:
            if not path.lower().endswith(".docx"):
                path += ".docx"
            self._path_edit.setText(path)

    # ── Export ────────────────────────────────────────────────────────────

    def _collect_manifest(self) -> list[SectionEntry]:
        """Sync enabled state from widgets and return self._entries as manifest."""
        self._sync_enabled_from_widgets()
        for i, entry in enumerate(self._entries):
            entry.order = i * 10
        return list(self._entries)

    def _export(self) -> None:
        output_path = self._path_edit.text().strip()
        if not output_path:
            QMessageBox.warning(self, "Export", "Please choose an output file location.")
            return

        config = ReportConfig(
            report_title=self._title_edit.text().strip() or "UAV Report",
            author=self._author_edit.text().strip(),
            revision=self._revision_edit.text().strip() or "1.0",
            format=ExportFormat.DOCX,
            output_path=output_path,
            sections=self._collect_manifest(),
            include_equations=self._eq_check.isChecked(),
            include_sadraey_refs=self._ref_check.isChecked(),
            language=self._language_combo.currentData(),
        )

        self._export_btn.setEnabled(False)
        self._progress.show()

        # Run in background thread
        self._thread  = QThread()
        self._worker  = _ExportWorker(self._service, config)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_done)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    def _on_done(self, success: bool, msg: str) -> None:
        self._progress.hide()
        self._export_btn.setEnabled(True)

        if success:
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Export Complete")
            dlg.setText(f"Report saved successfully.")
            dlg.setInformativeText(msg)
            dlg.setIcon(QMessageBox.Icon.Information)
            open_btn = dlg.addButton("Open File", QMessageBox.ButtonRole.ActionRole)
            dlg.addButton(QMessageBox.StandardButton.Ok)
            dlg.exec()
            if dlg.clickedButton() == open_btn:
                os.startfile(msg)  # type: ignore[attr-defined]
            self.accept()
        else:
            QMessageBox.critical(self, "Export Failed", f"Export error:\n\n{msg}")
