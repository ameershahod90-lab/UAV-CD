"""
Section Customise Dialog — abstract base.

The export dialog (``ExportDialog``) renders a row for every registered
``ReportSection``. When the section declares ``is_customizable = True``,
the row carries a "Customise…" button that opens a section-specific
dialog so the user can pick which content lands in the report.

Every customise dialog inherits from ``SectionCustomizeDialog`` so they
share:
  * OK / Cancel button wiring,
  * a typed ``.config`` property exposing the produced
    ``SectionConfig`` (None when cancelled),
  * an optional ``_validate_form() -> bool`` hook for pre-accept checks.

Subclasses implement three hooks:
  * ``_build_form(layout)`` — populate the form area with controls.
  * ``_populate_from_config(config)`` — push the initial state into the
    controls when a config is supplied.
  * ``_collect_config() -> SectionConfig`` — read control state into a
    fresh ``SectionConfig`` subclass.

Design note: ``QDialog`` and ``ABC`` have a metaclass conflict in
PyQt6, so the hooks raise ``NotImplementedError`` instead of being
``@abstractmethod`` decorated. The contract is enforced by code review
and unit tests.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QWidget,
)

from app.core.reports.base import SectionConfig


class SectionCustomizeDialog(QDialog):
    """Abstract base for per-section customise dialogs."""

    def __init__(
        self,
        title: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(560)
        self.setMinimumHeight(420)
        self._final_config: Optional[SectionConfig] = None

    # ── Layout scaffold ────────────────────────────────────────────────────

    def _setup_layout(
        self, initial_config: Optional[SectionConfig],
    ) -> None:
        """Build the form + OK/Cancel row.

        Called by the SUBCLASS after its own ``__init__`` has stored any
        dependencies the form needs (store, dc, propulsion). Two-step
        construction avoids the awkward "set deps before super init"
        dance that would otherwise be required so the abstract hook
        ``_build_form`` can read them.
        """
        outer = QVBoxLayout(self)
        outer.setSpacing(8)
        outer.setContentsMargins(12, 12, 12, 12)

        body = QVBoxLayout()
        body.setSpacing(10)
        self._build_form(body)
        outer.addLayout(body)

        outer.addStretch(1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._try_accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

        if initial_config is not None:
            self._populate_from_config(initial_config)

    def _try_accept(self) -> None:
        """Run pre-accept validation; on success store the collected
        config and call ``QDialog.accept()``. Subclasses that want a
        validation gate override ``_validate_form()``."""
        if not self._validate_form():
            return
        self._final_config = self._collect_config()
        self.accept()

    def _validate_form(self) -> bool:
        """Pre-accept hook. Default: no validation."""
        return True

    # ── Subclass hooks (override these) ───────────────────────────────────

    def _build_form(self, layout: QVBoxLayout) -> None:
        raise NotImplementedError(
            "Subclasses must implement _build_form(layout)"
        )

    def _populate_from_config(self, config: SectionConfig) -> None:
        raise NotImplementedError(
            "Subclasses must implement _populate_from_config(config)"
        )

    def _collect_config(self) -> SectionConfig:
        raise NotImplementedError(
            "Subclasses must implement _collect_config() -> SectionConfig"
        )

    # ── Public ────────────────────────────────────────────────────────────

    @property
    def config(self) -> Optional[SectionConfig]:
        """The config produced on accept; None when the dialog was cancelled."""
        return self._final_config
