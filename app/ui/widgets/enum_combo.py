"""
EnumCombo Widget — UAV-CD-APP
================================
A QComboBox auto-populated from any Python Enum class.
Maps display value (.value) → enum member for two-way binding.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Type, TypeVar

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QWidget

E = TypeVar("E", bound=Enum)


class EnumCombo(QComboBox):
    """
    A QComboBox that binds directly to an Enum type.

    Usage::

        combo = EnumCombo(PropulsionType)
        combo.set_value(PropulsionType.ELECTRIC)
        pt: PropulsionType = combo.current_enum()

    Signals
    -------
    enum_changed(object)
        Emitted with the selected enum member when selection changes.
    """

    enum_changed: pyqtSignal = pyqtSignal(object)

    def __init__(
        self,
        enum_cls: Type[E],
        parent: Optional[QWidget] = None,
        *,
        exclude: Optional[list[E]] = None,
    ) -> None:
        super().__init__(parent)
        self._enum_cls: Type[E] = enum_cls
        self._members: list[E] = [
            m for m in enum_cls
            if exclude is None or m not in exclude
        ]

        for member in self._members:
            # Use .label if available (our enums have it), else .value
            label: str = (
                getattr(member, "label", None) or str(member.value)
            )
            self.addItem(label)

        self.currentIndexChanged.connect(self._on_index_changed)

    # ── Public API ───────────────────────────────────────────────────────

    def current_enum(self) -> E:
        """Return the currently selected enum member."""
        idx = self.currentIndex()
        if 0 <= idx < len(self._members):
            return self._members[idx]
        return self._members[0]

    def set_value(self, member: E, block_signals: bool = False) -> None:
        """Select the combo item matching *member*."""
        try:
            idx = self._members.index(member)
        except ValueError:
            return
        if block_signals:
            self.blockSignals(True)
        self.setCurrentIndex(idx)
        if block_signals:
            self.blockSignals(False)

    # ── Internal ─────────────────────────────────────────────────────────

    def _on_index_changed(self, idx: int) -> None:
        if 0 <= idx < len(self._members):
            self.enum_changed.emit(self._members[idx])
