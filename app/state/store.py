"""
AppStore — UAV-CD-APP
=======================
The single source of truth for all application state.

Architecture:
  - Singleton via module-level instance ``store`` (imported everywhere).
  - Inherits QObject so Qt signals work.
  - Typed setters mutate AppState; each setter emits the finest-grain
    signal possible so only relevant widgets re-render.
  - ``is_dirty`` tracks unsaved changes; resets on save/load.
  - No business logic here — purely state + notification.

Thread safety:
  - All methods must be called from the Qt main thread.
    (Standard for PyQt6 desktop apps; no special locking needed.)
"""

from __future__ import annotations

import copy
import logging
from datetime import datetime, timezone
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from app.core.entities import (
    ClassificationRange,
    ConstraintResult,
    ConstraintViolation,
    DesignBrief,
    DesignPoint,
    RegressionCoeffs,
    SizingRun,
    WeightResult,
)
from app.state.app_state import AppState, HistoricalDataState, SizingState
from app.state.project_file import load_project, new_project, save_project
from app.state.settings import SettingsManager, UserSettings

_LOG = logging.getLogger(__name__)


class AppStore(QObject):
    """
    Reactive AppState container with Qt signals.

    Signals
    -------
    brief_changed
        Emitted when DesignBrief is updated.
    weight_result_changed
        Emitted when a new WeightResult is stored.
    constraint_result_changed
        Emitted when a new ConstraintResult is stored.
    design_point_changed
        Emitted when a new DesignPoint is stored.
    run_history_changed
        Emitted when a SizingRun is appended or removed.
    meta_changed
        Emitted when ProjectMeta changes (name, author, etc.).
    classification_changed
        Emitted when user edits classification ranges.
    regression_updated
        Emitted when DatabaseService posts new regression coefficients.
    settings_changed
        Emitted when UserSettings change.
    project_loaded
        Emitted after a full project file is loaded (state fully replaced).
    state_dirty_changed(bool)
        Emitted when the unsaved-changes flag flips.
    constraint_violation(list)
        Emitted with the list of ConstraintViolation objects.
    """

    # ── Fine-grained signals ─────────────────────────────────────────────
    brief_changed              = pyqtSignal()
    weight_result_changed      = pyqtSignal()
    constraint_result_changed  = pyqtSignal()
    design_point_changed       = pyqtSignal()
    run_history_changed        = pyqtSignal()
    meta_changed               = pyqtSignal()
    classification_changed     = pyqtSignal()
    regression_updated         = pyqtSignal()
    settings_changed           = pyqtSignal()
    project_loaded             = pyqtSignal()
    state_dirty_changed        = pyqtSignal(bool)
    constraint_violation       = pyqtSignal(list)

    # ── Lifecycle ────────────────────────────────────────────────────────

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._state: AppState = new_project()
        self._settings_manager: SettingsManager = SettingsManager()
        self._settings: UserSettings = self._settings_manager.load()
        self._current_path: Optional[str] = None
        self._is_dirty: bool = False

    # ── State accessors (read-only snapshots) ────────────────────────────

    @property
    def state(self) -> AppState:
        """The current full AppState (read-only view)."""
        return self._state

    @property
    def settings(self) -> UserSettings:
        return self._settings

    @property
    def current_path(self) -> Optional[str]:
        """Absolute path to the open project file, or None."""
        return self._current_path

    @property
    def is_dirty(self) -> bool:
        """True if there are unsaved changes."""
        return self._is_dirty

    # ── Dirty flag management ─────────────────────────────────────────────

    def _mark_dirty(self) -> None:
        was_dirty = self._is_dirty
        self._is_dirty = True
        if not was_dirty:
            self.state_dirty_changed.emit(True)

    def _mark_clean(self) -> None:
        was_dirty = self._is_dirty
        self._is_dirty = False
        if was_dirty:
            self.state_dirty_changed.emit(False)

    # ── Sizing state setters ─────────────────────────────────────────────

    def update_brief(self, brief: DesignBrief) -> None:
        self._state.sizing.brief = brief
        self._mark_dirty()
        self.brief_changed.emit()

    def update_brief_field(self, field_name: str, value: object) -> None:
        """Update a single field on the DesignBrief."""
        setattr(self._state.sizing.brief, field_name, value)
        self._mark_dirty()
        self.brief_changed.emit()

    def update_weight_result(self, result: WeightResult) -> None:
        self._state.sizing.weight_result = result
        self._mark_dirty()
        self.weight_result_changed.emit()

    def update_constraint_result(
        self,
        result: ConstraintResult,
        violations: list[ConstraintViolation],
    ) -> None:
        self._state.sizing.constraint_result = result
        self._mark_dirty()
        self.constraint_result_changed.emit()
        if violations:
            self.constraint_violation.emit(violations)

    def update_design_point(self, point: DesignPoint) -> None:
        self._state.sizing.design_point = point
        self._mark_dirty()
        self.design_point_changed.emit()
        # Also fire violation signal so banner updates on every design point change
        if point.violated_constraints:
            self.constraint_violation.emit(list(point.violated_constraints))
        else:
            self.constraint_violation.emit([])


    def append_sizing_run(self, run: SizingRun) -> None:
        self._state.sizing.run_history.append(run)
        self._mark_dirty()
        self.run_history_changed.emit()

    def remove_sizing_run(self, index: int) -> None:
        if 0 <= index < len(self._state.sizing.run_history):
            del self._state.sizing.run_history[index]
            self._mark_dirty()
            self.run_history_changed.emit()

    def rename_sizing_run(self, index: int, new_label: str) -> None:
        runs = self._state.sizing.run_history
        if 0 <= index < len(runs):
            # SizingRun is frozen — replace at index
            run = runs[index]
            import dataclasses
            runs[index] = dataclasses.replace(run, label=new_label)
            self._mark_dirty()
            self.run_history_changed.emit()

    # ── Historical data state setters ────────────────────────────────────

    def update_classification_ranges(
        self, ranges: list[ClassificationRange]
    ) -> None:
        self._state.historical_data.classification_ranges = ranges
        self._mark_dirty()
        self.classification_changed.emit()

    def update_regression_coefficients(
        self, coefficients: dict[str, RegressionCoeffs]
    ) -> None:
        self._state.historical_data.regression_coefficients = coefficients
        self.regression_updated.emit()

    def update_plot_axes(self, x_field: str, y_field: str) -> None:
        hd = self._state.historical_data
        hd.active_plot_x = x_field
        hd.active_plot_y = y_field
        # No dirty mark — plot axes are a cosmetic UI preference

    # ── Meta setters ─────────────────────────────────────────────────────

    def update_meta_name(self, name: str) -> None:
        self._state.meta.name = name
        self._mark_dirty()
        self.meta_changed.emit()

    def update_meta(self, name: str, author: str, description: str) -> None:
        m = self._state.meta
        m.name, m.author, m.description = name, author, description
        self._mark_dirty()
        self.meta_changed.emit()

    # ── Settings setters ─────────────────────────────────────────────────

    def update_settings(self, settings: UserSettings) -> None:
        self._settings = settings
        self._settings_manager.save(settings)
        self.settings_changed.emit()

    # ── File operations ──────────────────────────────────────────────────

    def new_project(self, name: str = "Untitled Project") -> None:
        """Replace state with a fresh project."""
        self._state = new_project(name)
        self._current_path = None
        self._mark_clean()
        self.project_loaded.emit()

    def save(self, path: Optional[str] = None) -> bool:
        """
        Save current state. Uses *path* or the existing current_path.
        Returns True on success.
        """
        target = path or self._current_path
        if not target:
            _LOG.error("save(): no path specified.")
            return False

        if save_project(self._state, target):
            self._current_path = target
            self._settings.add_recent(target)
            self._settings_manager.save(self._settings)
            self._mark_clean()
            return True
        return False

    def open_project(self, path: str) -> bool:
        """
        Load a .uavcd file and replace the current state.
        Returns True on success.
        """
        loaded = load_project(path)
        if loaded is None:
            return False
        self._state = loaded
        self._current_path = path
        self._settings.add_recent(path)
        self._settings_manager.save(self._settings)
        self._mark_clean()
        self.project_loaded.emit()
        return True

    # ── Window title helper ──────────────────────────────────────────────

    def window_title(self) -> str:
        """Return a window-title string like 'ProjectName — UAV-CD-APP *'."""
        name = self._state.meta.name or "Untitled"
        dirty_marker = " *" if self._is_dirty else ""
        return f"{name}{dirty_marker} — UAV-CD-APP"


# ---------------------------------------------------------------------------
# Module-level singleton — import and use directly
# ---------------------------------------------------------------------------

# Instantiated once the QApplication exists (called from main.py)
_store_instance: Optional[AppStore] = None


def create_store(parent: Optional[QObject] = None) -> AppStore:
    """Create and return the global AppStore. Call once from main.py."""
    global _store_instance
    _store_instance = AppStore(parent)
    return _store_instance


def get_store() -> AppStore:
    """Return the global AppStore. Raises if not yet created."""
    if _store_instance is None:
        raise RuntimeError(
            "AppStore not initialised. Call create_store() first."
        )
    return _store_instance
