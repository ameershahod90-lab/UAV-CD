"""
Mission Segment Row Widget — UAV-CD-APP
=========================================
A single draggable/configurable row representing one mission segment.

Fixes vs previous version:
  1. Icons: Uses Qt-standard text/Unicode that renders on all platforms.
     Checkboxes are native QCheckBox. Delete is a styled QPushButton with
     text "✕" (U+2715 — reliable in all system fonts). Drag handle uses
     "⠿" (U+28FF braille — narrow and clear) with SizeVerCursor.

  2. Drag-and-drop: The widget emits `drag_started(widget)` with itself as
     the payload. The parent MissionTab's `_DragContainer` intercepts
     mousePressEvent/mouseMoveEvent on the drag handle label via an event
     filter, then reorders the layout and updates the store.
     This is pure-Qt (QDrag-free) approach: we track drag state ourselves
     and use a placeholder widget to animate the slot during drag.

Architecture:
  • MissionSegmentWidget  — the row widget (this file)
  • DragContainer         — a QWidget subclass that owns a QVBoxLayout and
    manages reorder logic; lives in mission_tab.py
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QMouseEvent
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QWidget,
)

from app.core.entities import (
    CruiseMissionSegment,
    LoiterMissionSegment,
    MissionSegment,
)
from app.core.enums import EnergySource, PropulsionType, SegmentType
from app.core.validation import get_field_spec
from app.ui.widgets.checkmark_box import CheckmarkBox
from app.ui.widgets.validated_input import ValidatedInput

# ---------------------------------------------------------------------------
# Reliable Unicode glyphs (render on Windows with standard system fonts)
# ---------------------------------------------------------------------------
_ICON_DRAG   = "⠿"    # U+28FF  — braille square, visible drag grip
_ICON_DELETE = "✕"    # U+2715  — multiplication X
_ICON_FUEL   = "Fuel"   # plain text — most reliable
_ICON_BAT    = "Batt."  # plain text


class MissionSegmentWidget(QFrame):
    """
    One row in the mission panel representing a single `MissionSegment`.

    Signals
    -------
    segment_changed():
        Emitted whenever the user changes enabled state, parameter value,
        or energy source. Parent reads `self.segment` for new state.
    delete_requested():
        Emitted when the user clicks ✕ (dynamic segments only).
    drag_handle_pressed(QPoint):
        Emitted (with global cursor pos) when pointer presses the drag grip.
        The parent DragContainer listens to this to initiate reorder.
    """

    segment_changed     = pyqtSignal()
    delete_requested    = pyqtSignal()
    drag_handle_pressed = pyqtSignal(QPoint)       # global cursor position

    def __init__(
        self,
        segment: MissionSegment,
        propulsion_type: PropulsionType,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._segment: MissionSegment = segment
        self._prop_type: PropulsionType = propulsion_type
        self._param_widget: Optional[ValidatedInput] = None

        self.setObjectName("SegmentRow")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._build()

    # ── Public interface ──────────────────────────────────────────────────

    @property
    def segment(self) -> MissionSegment:
        return self._segment

    def update_propulsion(self, pt: PropulsionType) -> None:
        """Show/hide energy source buttons when propulsion type changes."""
        self._prop_type = pt
        if hasattr(self, "_energy_widget"):
            self._energy_widget.setVisible(pt is PropulsionType.HYBRID)

    # ── Build ─────────────────────────────────────────────────────────────

    def _build(self) -> None:
        seg = self._segment
        is_dynamic = seg.segment_type.is_dynamic
        is_hybrid  = self._prop_type is PropulsionType.HYBRID

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 2, 6, 2)
        row.setSpacing(8)

        # ── Drag handle (dynamic segments only) ───────────────────────────
        if is_dynamic:
            self._drag_handle = QLabel(_ICON_DRAG)
            self._drag_handle.setObjectName("DragHandle")
            self._drag_handle.setFixedWidth(18)
            self._drag_handle.setCursor(Qt.CursorShape.SizeVerCursor)
            self._drag_handle.setToolTip("Drag to reorder")
            self._drag_handle.setStyleSheet(
                "QLabel#DragHandle { font-size: 16px; color: #888aaa; "
                "padding: 0 2px; }"
            )
            # Install mouse press handler for drag-start detection
            self._drag_handle.mousePressEvent = self._on_drag_handle_press
            row.addWidget(self._drag_handle)
        else:
            # Spacer to keep alignment with dynamic rows
            spacer = QLabel("")
            spacer.setFixedWidth(18)
            row.addWidget(spacer)

        # ── Enable / disable checkbox ────────────────────────────────────
        self._enabled_cb = CheckmarkBox()
        self._enabled_cb.setChecked(seg.enabled)
        self._enabled_cb.setToolTip("Enable / disable this segment")
        self._enabled_cb.toggled.connect(self._on_enabled_changed)
        row.addWidget(self._enabled_cb)

        # ── Segment icon + type label ─────────────────────────────────────
        icon_lbl = QLabel(f"{seg.icon}  {seg.segment_type.label}")
        icon_lbl.setMinimumWidth(160)
        icon_lbl.setObjectName("SegmentLabel")
        icon_lbl.setStyleSheet(
            "QLabel#SegmentLabel { font-weight: 500; font-size: 13px; }"
        )
        row.addWidget(icon_lbl)

        # ── Parameter input ───────────────────────────────────────────────
        if isinstance(seg, CruiseMissionSegment):
            spec = get_field_spec(CruiseMissionSegment, "range_km")
            if spec:
                self._param_widget = ValidatedInput(spec)
                self._param_widget.set_value(seg.range_km, block_signals=True)
                self._param_widget.value_changed.connect(self._on_range_changed)
                row.addWidget(self._param_widget)

        elif isinstance(seg, LoiterMissionSegment):
            spec = get_field_spec(LoiterMissionSegment, "endurance_hr")
            if spec:
                self._param_widget = ValidatedInput(spec)
                self._param_widget.set_value(seg.endurance_hr, block_signals=True)
                self._param_widget.value_changed.connect(self._on_endurance_changed)
                row.addWidget(self._param_widget)

        else:
            # Fixed segment — show k-factor from Sadraey Table 2.4
            _k_text = {
                SegmentType.TAKEOFF: "k = 0.970 / 0.990",
                SegmentType.CLIMB:   "k = 0.985 / 0.990",
                SegmentType.DESCENT: "k = 0.990",
                SegmentType.LANDING: "k = 0.992",
            }
            hint = QLabel(_k_text.get(seg.segment_type, ""))
            hint.setObjectName("InputLabel")
            hint.setStyleSheet("QLabel#InputLabel { color: #666888; font-size: 11px; }")
            hint.setToolTip("Fixed weight fraction from Sadraey Table 2.4 (piston / jet)")
            row.addWidget(hint)

        row.addStretch()

        # ── Energy source (Hybrid only) ───────────────────────────────────
        self._energy_widget = QWidget()
        ew_layout = QHBoxLayout(self._energy_widget)
        ew_layout.setContentsMargins(0, 0, 0, 0)
        ew_layout.setSpacing(4)

        self._btn_fuel = QRadioButton("Fuel")
        self._btn_bat  = QRadioButton("Batt.")
        self._btn_fuel.setStyleSheet("font-size: 11px;")
        self._btn_bat.setStyleSheet("font-size: 11px;")

        self._energy_group = QButtonGroup(self)
        self._energy_group.addButton(self._btn_fuel, 0)
        self._energy_group.addButton(self._btn_bat,  1)

        if seg.energy_source is EnergySource.BATTERY:
            self._btn_bat.setChecked(True)
        else:
            self._btn_fuel.setChecked(True)

        ew_layout.addWidget(self._btn_fuel)
        ew_layout.addWidget(self._btn_bat)
        self._energy_group.idToggled.connect(self._on_energy_changed)

        row.addWidget(self._energy_widget)
        self._energy_widget.setVisible(is_hybrid)

        # ── Delete button (dynamic only) ──────────────────────────────────
        if is_dynamic:
            del_btn = QPushButton(_ICON_DELETE)
            del_btn.setObjectName("DangerButton")
            del_btn.setFixedSize(26, 26)
            del_btn.setToolTip("Remove this segment")
            del_btn.setStyleSheet(
                "QPushButton#DangerButton {"
                "  background: #5a1e1e; color: #ff6666; border-radius: 4px;"
                "  font-size: 13px; font-weight: bold; padding: 0;"
                "}"
                "QPushButton#DangerButton:hover { background: #7a2222; }"
            )
            del_btn.clicked.connect(self.delete_requested.emit)
            row.addWidget(del_btn)

        self._sync_enabled_visual()

    # ── Drag handle mouse event ───────────────────────────────────────────

    def _on_drag_handle_press(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_handle_pressed.emit(event.globalPosition().toPoint())

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_enabled_changed(self, checked: bool) -> None:
        self._segment.enabled = checked
        self._sync_enabled_visual()
        self.segment_changed.emit()

    def _on_range_changed(self, value: float) -> None:
        if isinstance(self._segment, CruiseMissionSegment):
            self._segment.range_km = value
            self.segment_changed.emit()

    def _on_endurance_changed(self, value: float) -> None:
        if isinstance(self._segment, LoiterMissionSegment):
            self._segment.endurance_hr = value
            self.segment_changed.emit()

    def _on_energy_changed(self, btn_id: int, checked: bool) -> None:
        if not checked:
            return
        self._segment.energy_source = (
            EnergySource.BATTERY if btn_id == 1 else EnergySource.FUEL
        )
        self.segment_changed.emit()

    def _sync_enabled_visual(self) -> None:
        """Grey-out the frame when disabled."""
        alpha = "1.0" if self._segment.enabled else "0.45"
        self.setStyleSheet(
            f"MissionSegmentWidget {{ opacity: {alpha}; }}"
        )
