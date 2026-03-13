"""
Main Window — UAV-CD-APP
===========================
QMainWindow hosting all top-level tabs and the application menu bar.
Wires together AppStore, SizingService, DatabaseService, and all tab pages.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QWidget,
)

from app.core.enums import ThemeOption
from app.services.database_service import DatabaseService
from app.services.sizing_service import SizingService
from app.state.store import AppStore
from app.ui.tabs.sizing.constraints_tab import ConstraintsTab
from app.ui.tabs.sizing.input_tab import InputTab
from app.ui.tabs.sizing.output_tab import OutputTab
from app.ui.tabs.sizing.weight_tab import WeightTab
from app.ui.themes import QSS_DARK, QSS_LIGHT


_FILTER = "UAV-CD Project (*.uavcd);;All Files (*)"


class MainWindow(QMainWindow):
    """Application main window."""

    def __init__(
        self,
        store: AppStore,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._store: AppStore = store

        # ── Services attached to window for child tab access ─────────────
        self._db_service: DatabaseService = DatabaseService(store)
        self._sizing_service: SizingService = SizingService(store, self)
        self._sizing_service.initialise()

        # ── Window setup ──────────────────────────────────────────────────
        self.setWindowTitle(store.window_title())
        self.resize(1280, 860)
        self.setMinimumSize(900, 600)

        # ── Menu bar ──────────────────────────────────────────────────────
        self._build_menu()

        # ── Tab widget ────────────────────────────────────────────────────
        root = QTabWidget()
        root.setObjectName("MainTabBar")
        self.setCentralWidget(root)

        # Sizing tab (sub-tabbed)
        sizing_tabs = QTabWidget()
        sizing_tabs.addTab(InputTab(store),      "⚙  Input")
        sizing_tabs.addTab(WeightTab(store),     "⚖  Weight")
        sizing_tabs.addTab(ConstraintsTab(store), "📊  Constraints")
        sizing_tabs.addTab(OutputTab(store),     "🎯  Output")
        root.addTab(sizing_tabs, "Phase 1 — Initial Sizing")

        # Historical data tab (placeholder for now — full implementation next)
        hist_placeholder = QLabel(
            "Historical Data Analysis\n\n"
            "Classification Manager · Data Explorer · Analysis Playground · "
            "Regression Results\n\n"
            "(Under active development — Phase 1 core complete)"
        )
        hist_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addTab(hist_placeholder, "📁  Historical Data")

        # Settings tab
        from app.ui.tabs.settings_tab import SettingsTab
        root.addTab(SettingsTab(store), "⚙  Settings")

        # ── Status bar ────────────────────────────────────────────────────
        sb: QStatusBar = QStatusBar()
        self.setStatusBar(sb)
        self._status_lbl = QLabel("Ready")
        sb.addWidget(self._status_lbl)

        # ── Apply theme ───────────────────────────────────────────────────
        self._apply_theme(store.settings.theme)

        # ── React to store signals ────────────────────────────────────────
        store.state_dirty_changed.connect(self._update_title)
        store.meta_changed.connect(self._update_title)
        store.project_loaded.connect(self._update_title)
        store.settings_changed.connect(
            lambda: self._apply_theme(self._store.settings.theme)
        )
        store.constraint_violation.connect(self._on_violations)
        store.weight_result_changed.connect(
            lambda: self._status_lbl.setText("Weight analysis complete")
        )
        store.design_point_changed.connect(
            lambda: self._status_lbl.setText("Design point computed ✓")
        )

        # ── Load database ─────────────────────────────────────────────────
        db_path = store.settings.database_path or None
        self._db_service.initialise(db_path)

    # ── Menu ──────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("&File")
        file_menu.addAction("New Project",      self._new_project,   "Ctrl+N")
        file_menu.addAction("Open Project…",    self._open_project,  "Ctrl+O")
        file_menu.addSeparator()
        file_menu.addAction("Save",             self._save,          "Ctrl+S")
        file_menu.addAction("Save As…",         self._save_as,       "Ctrl+Shift+S")
        file_menu.addSeparator()
        file_menu.addAction("Exit",             self.close,          "Alt+F4")

        # View
        view_menu = mb.addMenu("&View")
        view_menu.addAction("Toggle Dark/Light Theme", self._toggle_theme, "Ctrl+T")

        # Help
        help_menu = mb.addMenu("&Help")
        help_menu.addAction("About UAV-CD-APP", self._show_about)

    # ── File actions ──────────────────────────────────────────────────────

    def _new_project(self) -> None:
        if self._confirm_discard():
            self._store.new_project()

    def _open_project(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", self._store.settings.last_project_dir, _FILTER
        )
        if path:
            if not self._store.open_project(path):
                QMessageBox.critical(self, "Error", f"Could not open:\n{path}")

    def _save(self) -> None:
        if not self._store.current_path:
            self._save_as()
        else:
            self._store.save()

    def _save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", self._store.settings.last_project_dir, _FILTER
        )
        if path:
            if not path.endswith(".uavcd"):
                path += ".uavcd"
            self._store.save(path)

    # ── Theme ─────────────────────────────────────────────────────────────

    def _apply_theme(self, theme: ThemeOption) -> None:
        from PyQt6.QtWidgets import QApplication
        qss = QSS_DARK if theme is ThemeOption.DARK else QSS_LIGHT
        QApplication.instance().setStyleSheet(qss)  # type: ignore[union-attr]

    def _toggle_theme(self) -> None:
        s = self._store.settings
        new_theme = ThemeOption.LIGHT if s.theme is ThemeOption.DARK else ThemeOption.DARK
        import dataclasses
        self._store.update_settings(dataclasses.replace(s, theme=new_theme))

    # ── Window title ──────────────────────────────────────────────────────

    def _update_title(self) -> None:
        self.setWindowTitle(self._store.window_title())

    # ── Violation badge ───────────────────────────────────────────────────

    def _on_violations(self, violations: list) -> None:
        if violations:
            self._status_lbl.setText(
                f"⚠  {len(violations)} constraint violation(s) detected"
            )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _confirm_discard(self) -> bool:
        if not self._store.is_dirty:
            return True
        reply = QMessageBox.question(
            self, "Unsaved Changes",
            "You have unsaved changes. Discard them?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        )
        return reply == QMessageBox.StandardButton.Discard

    def _show_about(self) -> None:
        QMessageBox.information(
            self, "About UAV-CD-APP",
            "UAV Conceptual Design Application\n"
            "Phase 1 — Initial Sizing Engine\n\n"
            "Architecture: Reactive Property Store\n"
            "Tech Stack: Python 3.14 · PyQt6 · pyqtgraph\n"
        )

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if not self._confirm_discard():
            event.ignore()
            return
        event.accept()
