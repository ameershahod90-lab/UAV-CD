"""
Mission Profile Tab — UAV-CD-APP
===================================
The Mission tab handles everything related to the mission definition:

  1. Scalar mission requirements (payload, speeds, altitude, etc.)
     Dynamic: takeoff_run_m only shown when TAKEOFF segment is enabled.

  2. Mission Segments Panel:
     • Fixed segments (Takeoff, Climb, Descent, Landing) — checkbox-only rows
     • Dynamic segments (Cruise, Loiter) — draggable rows with params
     • "Add Segment" button: choose Cruise (range) or Loiter (endurance)
     • Drag-and-drop reordering via DragContainer (mouse-event-based, no QDrag)
     • Validation: at least one dynamic segment required

  3. Mission Profile Diagram:
     Live-updating altitude profile (see MissionDiagram widget).

Drag-and-drop implementation:
  DragContainer is a QFrame subclass that:
    – Holds a QVBoxLayout of MissionSegmentWidget rows.
    – Connects each dynamic row's `drag_handle_pressed` signal.
    – On that signal, starts tracking mouseMoveEvent on the *container*
      (which is the common parent) via Qt.MouseEventFilter.
    – Calculates which slot the cursor is nearest, swaps the widget order
      in the layout, and updates the store on mouseRelease.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from app.core.entities import (
    CruiseMissionSegment,
    DesignBrief,
    LoiterMissionSegment,
    MissionSegment,
)
from app.core.enums import EnergySource, PropulsionType, SegmentType
from app.core.units import UnitConverter
from app.core.validation import get_field_spec
from app.state.store import AppStore
from app.ui.widgets.mission_diagram import MissionDiagram
from app.ui.widgets.mission_segment_widget import MissionSegmentWidget
from app.ui.widgets.validated_input import ValidatedInput


# ---------------------------------------------------------------------------
# Field → unit conversion mapping for scalar mission fields
# ---------------------------------------------------------------------------

def _mc(attr, to_d, to_si):
    return (attr, to_d, to_si)


_FIELD_UNIT_INFO: dict = {
    "payload_mass_kg":   _mc("mass_unit",     UnitConverter.mass_to_display,     UnitConverter.mass_to_si),
    "cruise_speed_ms":   _mc("speed_unit",    UnitConverter.speed_to_display,    UnitConverter.speed_to_si),
    "stall_speed_ms":    _mc("speed_unit",    UnitConverter.speed_to_display,    UnitConverter.speed_to_si),
    "max_speed_ms":      _mc("speed_unit",    UnitConverter.speed_to_display,    UnitConverter.speed_to_si),
    "rate_of_climb_ms":  _mc("speed_unit",    UnitConverter.speed_to_display,    UnitConverter.speed_to_si),
    "service_ceiling_m": _mc("altitude_unit", UnitConverter.altitude_to_display, UnitConverter.altitude_to_si),
    "cruise_altitude_m": _mc("altitude_unit", UnitConverter.altitude_to_display, UnitConverter.altitude_to_si),
    "takeoff_run_m":     _mc("altitude_unit", UnitConverter.altitude_to_display, UnitConverter.altitude_to_si),
}

_SCALAR_FIELDS = [
    "payload_mass_kg",
    "cruise_speed_ms",
    "stall_speed_ms",
    "max_speed_ms",
    "rate_of_climb_ms",
    "service_ceiling_m",
    "cruise_altitude_m",
]


# ---------------------------------------------------------------------------
# DragContainer — manages drag-to-reorder for dynamic segment rows
# ---------------------------------------------------------------------------

class DragContainer(QFrame):
    """
    A vertical list of MissionSegmentWidget rows with mouse-based drag reordering.

    Only dynamic segment rows are draggable. Fixed rows stay in place.

    order_changed() is emitted after a successful drag-reorder.
    """

    order_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

        # Drag state
        self._dragging: bool = False
        self._drag_widget: Optional[MissionSegmentWidget] = None
        self._drag_start_y: int = 0
        self._drag_origin_idx: int = 0

        # Enable mouse tracking for the container during drag
        self.setMouseTracking(True)

    # ── Public API ────────────────────────────────────────────────────────

    def add_row(self, w: MissionSegmentWidget) -> None:
        w.drag_handle_pressed.connect(self._on_drag_start)
        self._layout.addWidget(w)

    def clear_rows(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def row_widgets(self) -> list[MissionSegmentWidget]:
        result = []
        for i in range(self._layout.count()):
            item = self._layout.itemAt(i)
            if item and isinstance(item.widget(), MissionSegmentWidget):
                result.append(item.widget())
        return result

    def segment_order(self) -> list[MissionSegment]:
        """Return segments in their current visual order."""
        return [w.segment for w in self.row_widgets()]

    # ── Mouse-based drag ──────────────────────────────────────────────────

    def _on_drag_start(self, global_pos: QPoint) -> None:
        """Called when a drag handle is pressed."""
        sender = self.sender()
        if not isinstance(sender, MissionSegmentWidget):
            return
        if sender.segment.segment_type.is_fixed:
            return   # Fixed rows cannot be dragged

        self._dragging = True
        self._drag_widget = sender
        local_pos = self.mapFromGlobal(global_pos)
        self._drag_start_y = local_pos.y()
        self._drag_origin_idx = self._widget_index(sender)
        sender.setStyleSheet(
            "MissionSegmentWidget { background: #2a2a4a; border: 1px solid #7c6af7; }"
        )
        self.grabMouse()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._dragging or self._drag_widget is None:
            return
        y = event.position().y()
        target_idx = self._y_to_index(int(y))
        current_idx = self._widget_index(self._drag_widget)
        if target_idx != current_idx and target_idx >= 0:
            self._swap_to(current_idx, target_idx)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if not self._dragging:
            return
        self.releaseMouse()
        self._dragging = False
        if self._drag_widget is not None:
            self._drag_widget.setStyleSheet("")   # reset highlight
            self._drag_widget = None
        self.order_changed.emit()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _widget_index(self, w: QWidget) -> int:
        for i in range(self._layout.count()):
            if self._layout.itemAt(i) and self._layout.itemAt(i).widget() is w:
                return i
        return -1

    def _y_to_index(self, y: int) -> int:
        """Return the layout index that contains the given y coordinate."""
        for i in range(self._layout.count()):
            item = self._layout.itemAt(i)
            if item and item.widget():
                geo = item.widget().geometry()
                if geo.top() <= y <= geo.bottom():
                    return i
        # If below all items, clamp to last
        count = self._layout.count()
        if count > 0 and y > 0:
            return count - 1
        return 0

    def _swap_to(self, src: int, dst: int) -> None:
        """
        Move the widget at src to dst position.
        Enforces that dynamic segments cannot be moved before fixed-top segments
        or after fixed-bottom segments.
        """
        widgets = self.row_widgets()
        if src < 0 or src >= len(widgets):
            return

        drag_seg = widgets[src].segment

        # Determine allowed zone: between first non-top-fixed and last non-bottom-fixed
        top_fixed_count = 0
        for w in widgets:
            if w.segment.segment_type in (SegmentType.TAKEOFF, SegmentType.CLIMB):
                top_fixed_count += 1
            else:
                break
        bot_fixed_count = 0
        for w in reversed(widgets):
            if w.segment.segment_type in (SegmentType.DESCENT, SegmentType.LANDING):
                bot_fixed_count += 1
            else:
                break

        min_idx = top_fixed_count
        max_idx = len(widgets) - 1 - bot_fixed_count

        dst = max(min_idx, min(dst, max_idx))
        if dst == src:
            return

        # Re-insert widget at new position
        widget_to_move = self._drag_widget
        if widget_to_move is None:
            return
        self._layout.removeWidget(widget_to_move)
        self._layout.insertWidget(dst, widget_to_move)


# ---------------------------------------------------------------------------
# MissionTab
# ---------------------------------------------------------------------------

class MissionTab(QWidget):
    """Mission requirements tab with segment panel and profile diagram."""

    def __init__(self, store: AppStore, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._store: AppStore = store
        self._inputs: dict[str, ValidatedInput] = {}

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._main = QVBoxLayout(content)
        self._main.setContentsMargins(16, 16, 16, 16)
        self._main.setSpacing(16)

        self._build_scalar_fields()
        self._build_segment_panel()
        self._build_diagram()

        self._main.addSpacerItem(
            QSpacerItem(0, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )

        # ── Signals ───────────────────────────────────────────────────────
        self._store.brief_changed.connect(self._on_brief_changed)
        self._store.settings_changed.connect(self._on_settings_changed)
        self._store.project_loaded.connect(self._on_project_loaded)

        self._apply_unit_converters()
        self._rebuild_segment_panel()

    # ── Build helpers ─────────────────────────────────────────────────────

    def _build_scalar_fields(self) -> None:
        box = QGroupBox("Mission Requirements")
        form = QFormLayout(box)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(8)

        brief = self._store.state.sizing.brief
        for fname in _SCALAR_FIELDS:
            spec = get_field_spec(DesignBrief, fname)
            if not spec:
                continue
            w = ValidatedInput(spec)
            w.set_value(getattr(brief, fname), block_signals=True)
            w.value_changed.connect(lambda val, f=fname: self._on_field_changed(f, val))
            self._inputs[fname] = w
            form.addRow(w)

        # Takeoff run — dynamic visibility
        spec_to = get_field_spec(DesignBrief, "takeoff_run_m")
        if spec_to:
            w = ValidatedInput(spec_to)
            w.set_value(brief.takeoff_run_m, block_signals=True)
            w.value_changed.connect(
                lambda val: self._on_field_changed("takeoff_run_m", val)
            )
            self._inputs["takeoff_run_m"] = w
            form.addRow(w)
            self._takeoff_run_widget: Optional[ValidatedInput] = w
        else:
            self._takeoff_run_widget = None

        self._main.addWidget(box)
        self._sync_takeoff_run_visibility()

    def _build_segment_panel(self) -> None:
        panel_box = QGroupBox("Mission Profile Segments")
        panel_layout = QVBoxLayout(panel_box)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSpacing(6)

        # ── Legend / header row ───────────────────────────────────────────
        header = QLabel(
            "  Drag  On   Segment                     Parameters          "
            "                              Energy"
        )
        header.setStyleSheet(
            "color: #666888; font-size: 10px; font-weight: 600; "
            "border-bottom: 1px solid #3a3a5c; padding-bottom: 4px;"
        )
        panel_layout.addWidget(header)

        # ── Validation warning ────────────────────────────────────────────
        self._seg_warning = QLabel("")
        self._seg_warning.setObjectName("AlertBanner")
        self._seg_warning.setStyleSheet(
            "QLabel#AlertBanner { color: #ffaa55; font-size: 12px; "
            "padding: 4px; background: #3a2a00; border-radius: 4px; }"
        )
        self._seg_warning.setVisible(False)
        panel_layout.addWidget(self._seg_warning)

        # ── Drag container ────────────────────────────────────────────────
        self._drag_container = DragContainer()
        self._drag_container.order_changed.connect(self._on_order_changed)
        panel_layout.addWidget(self._drag_container)

        # ── Add Segment controls ──────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #3a3a5c; margin-top: 6px;")
        panel_layout.addWidget(sep)

        add_row = QHBoxLayout()
        add_row.addStretch()

        self._add_combo = QComboBox()
        self._add_combo.addItem("Add Cruise segment (Range)", SegmentType.CRUISE)
        self._add_combo.addItem("Add Loiter segment (Endurance)", SegmentType.LOITER)
        self._add_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._add_combo.setMinimumWidth(220)
        add_row.addWidget(self._add_combo)

        add_btn = QPushButton("+ Add")
        add_btn.clicked.connect(self._on_add_segment)
        add_btn.setFixedHeight(30)
        add_btn.setMinimumWidth(70)
        add_row.addWidget(add_btn)
        panel_layout.addLayout(add_row)

        self._main.addWidget(panel_box)

    def _build_diagram(self) -> None:
        diag_box = QGroupBox("Mission Profile Diagram")
        diag_layout = QVBoxLayout(diag_box)
        diag_layout.setContentsMargins(8, 8, 8, 8)
        self._diagram = MissionDiagram()
        diag_layout.addWidget(self._diagram)
        self._main.addWidget(diag_box)
        self._refresh_diagram()

    # ── Segment panel ─────────────────────────────────────────────────────

    def _rebuild_segment_panel(self) -> None:
        """Re-create all segment rows from store state."""
        self._drag_container.clear_rows()

        brief = self._store.state.sizing.brief
        pt = brief.propulsion_type

        for seg in brief.mission_segments:
            row = MissionSegmentWidget(seg, pt, self._drag_container)
            row.segment_changed.connect(self._on_segment_changed)
            row.delete_requested.connect(
                lambda _, w=row: self._on_delete_segment(w)
            )
            self._drag_container.add_row(row)

        self._validate_segments()
        self._sync_takeoff_run_visibility()
        self._refresh_diagram()

    # ── Diagram refresh ───────────────────────────────────────────────────

    def _refresh_diagram(self) -> None:
        brief = self._store.state.sizing.brief
        self._diagram.update_segments(
            brief.mission_segments,
            cruise_altitude_m=brief.cruise_altitude_m,
            takeoff_run_m=brief.takeoff_run_m,
        )

    # ── Validation ────────────────────────────────────────────────────────

    def _validate_segments(self) -> bool:
        brief = self._store.state.sizing.brief
        if not brief.has_valid_mission:
            self._seg_warning.setText(
                "At least one Cruise or Loiter segment must be enabled."
            )
            self._seg_warning.setVisible(True)
            return False
        self._seg_warning.setVisible(False)
        return True

    # ── Unit converters ───────────────────────────────────────────────────

    def _apply_unit_converters(self) -> None:
        settings = self._store.settings
        brief = self._store.state.sizing.brief
        for fname, widget in self._inputs.items():
            if fname not in _FIELD_UNIT_INFO:
                continue
            attr, to_d, to_si = _FIELD_UNIT_INFO[fname]
            ue = getattr(settings, attr)
            widget.set_unit_converter(
                lambda v, u=ue, fn=to_d: fn(v, u),
                lambda v, u=ue, fn=to_si: fn(v, u),
                ue.value,
            )
            widget.set_value(getattr(brief, fname), block_signals=True)

    # ── Takeoff run visibility ────────────────────────────────────────────

    def _sync_takeoff_run_visibility(self) -> None:
        if self._takeoff_run_widget is None:
            return
        brief = self._store.state.sizing.brief
        enabled = any(
            s.segment_type is SegmentType.TAKEOFF and s.enabled
            for s in brief.mission_segments
        )
        self._takeoff_run_widget.setVisible(enabled)

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_field_changed(self, field: str, val: float) -> None:
        self._store.update_brief_field(field, val)
        if field == "cruise_altitude_m":
            self._refresh_diagram()

    def _on_brief_changed(self) -> None:
        brief = self._store.state.sizing.brief
        for fname, widget in self._inputs.items():
            si_val = getattr(brief, fname, None)
            if si_val is not None:
                widget.set_value(si_val, block_signals=True)
        self._sync_takeoff_run_visibility()
        # Update propulsion on existing rows
        pt = brief.propulsion_type
        for w in self._drag_container.row_widgets():
            w.update_propulsion(pt)

    def _on_segment_changed(self) -> None:
        """Widget mutated the segment in-place — notify store."""
        self._push_order_to_store()
        self._validate_segments()
        self._sync_takeoff_run_visibility()
        self._refresh_diagram()

    def _on_order_changed(self) -> None:
        """Drag reorder completed — push new order to store."""
        self._push_order_to_store()
        self._refresh_diagram()

    def _on_add_segment(self) -> None:
        seg_type_data = self._add_combo.currentData()
        if not isinstance(seg_type_data, SegmentType):
            return
        brief = self._store.state.sizing.brief
        pt = brief.propulsion_type
        default_src = (
            EnergySource.BATTERY if pt is PropulsionType.ELECTRIC
            else EnergySource.FUEL
        )

        if seg_type_data is SegmentType.CRUISE:
            new_seg = CruiseMissionSegment(
                range_km=50.0, enabled=True, energy_source=default_src
            )
        else:
            new_seg = LoiterMissionSegment(
                endurance_hr=1.0, enabled=True, energy_source=default_src
            )

        # Insert before DESCENT/LANDING
        segs = list(brief.mission_segments)
        insert_pos = len(segs)
        for i, s in enumerate(segs):
            if s.segment_type in (SegmentType.DESCENT, SegmentType.LANDING):
                insert_pos = i
                break
        segs.insert(insert_pos, new_seg)
        self._store.update_brief_field("mission_segments", segs)
        self._rebuild_segment_panel()

    def _on_delete_segment(self, row_widget: MissionSegmentWidget) -> None:
        seg = row_widget.segment
        brief = self._store.state.sizing.brief
        new_segs = [s for s in brief.mission_segments if s is not seg]

        has_dynamic = any(
            s.enabled and s.segment_type.is_dynamic for s in new_segs
        )
        if not has_dynamic:
            QMessageBox.warning(
                self, "Cannot Delete",
                "At least one Cruise or Loiter segment must remain."
            )
            return
        self._store.update_brief_field("mission_segments", new_segs)
        self._rebuild_segment_panel()

    def _on_settings_changed(self) -> None:
        self._apply_unit_converters()

    def _on_project_loaded(self) -> None:
        self._apply_unit_converters()
        self._rebuild_segment_panel()

    def _push_order_to_store(self) -> None:
        """Write current visual order back to AppStore."""
        new_order = self._drag_container.segment_order()
        self._store.update_brief_field("mission_segments", new_order)
