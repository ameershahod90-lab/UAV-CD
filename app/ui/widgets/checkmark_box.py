"""
CheckmarkBox — drop-in QCheckBox with a checkmark-only indicator.

Subclasses ``QCheckBox`` and overrides ``paintEvent`` so the indicator
renders as:

  * Unchecked → empty rounded box with a thin border.
  * Checked   → accent-coloured checkmark **only** (no filled box).
  * Hover     → border lightens to the accent colour.
  * Focus     → dotted ring around the text.

Because the widget inherits ``QCheckBox`` it keeps every standard
interaction unchanged: mouse-click toggle (anywhere on the widget area
including text), space-bar toggle when focused, ``toggled``/``stateChanged``
signals, ``isChecked``/``setChecked`` API, accessibility, keyboard tab
order, palette handling. Existing code and tests using ``QCheckBox``
substitute it transparently.

The widget paints itself with ``QPainter`` directly so it bypasses
Qt's ``QStyle`` engine — the only reliable way to get a consistent
indicator visual across platforms and themes.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import (
    QColor,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
)
from PyQt6.QtWidgets import QCheckBox, QWidget


class CheckmarkBox(QCheckBox):
    """QCheckBox with a checkmark-only custom indicator. See module docstring."""

    # Indicator geometry
    _INDICATOR_SIZE: int       = 16
    _INDICATOR_LEFT_PAD: int   = 2     # so the indicator's left border isn't
                                       # clipped against the widget edge
    _INDICATOR_MARGIN: int     = 8     # gap between indicator and text
    _BORDER_RADIUS: int        = 3
    _CHECK_PEN_WIDTH: float    = 2.4

    # Theme-agnostic palette — these colours work on both the dark
    # (#1e1e2e) and light (#f5f5fa) backgrounds the app ships. Override
    # via ``setObjectName`` + a targeted QSS rule if a single instance
    # needs a different accent.
    _BORDER_NORMAL = QColor("#5a5a8a")
    _BORDER_HOVER  = QColor("#7c6af7")
    _ACCENT        = QColor("#7c6af7")

    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(text, parent)
        self._hover: bool = False

    # ── Size hint ──────────────────────────────────────────────────────────

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self.font())
        text_h = fm.height()
        if self.text():
            text_w = fm.horizontalAdvance(self.text())
            width = (
                self._INDICATOR_LEFT_PAD + self._INDICATOR_SIZE
                + self._INDICATOR_MARGIN + text_w + 4
            )
        else:
            # No label — width is just enough for the indicator with its
            # left padding (and a matching right pad for symmetry).
            width = (
                self._INDICATOR_LEFT_PAD * 2 + self._INDICATOR_SIZE
            )
        return QSize(width, max(self._INDICATOR_SIZE, text_h) + 4)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    # ── Hover tracking ─────────────────────────────────────────────────────

    def enterEvent(self, event) -> None:    # type: ignore[override]
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:    # type: ignore[override]
        self._hover = False
        self.update()
        super().leaveEvent(event)

    # ── Paint ──────────────────────────────────────────────────────────────

    def paintEvent(self, event: QPaintEvent) -> None:    # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Indicator — vertically centred, anchored to the left of the
        # widget's content area. The 2 px left padding gives the
        # unchecked border room so it isn't clipped at the widget edge.
        ind_y = (self.height() - self._INDICATOR_SIZE) // 2
        ind_rect = QRect(
            self._INDICATOR_LEFT_PAD, ind_y,
            self._INDICATOR_SIZE, self._INDICATOR_SIZE,
        )

        if self.isChecked():
            # Accent-coloured border + accent-coloured checkmark inside.
            # The border keeps the indicator legible as a "this is a
            # checkbox" affordance even after the user has ticked it.
            painter.setPen(QPen(self._ACCENT, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                ind_rect, self._BORDER_RADIUS, self._BORDER_RADIUS,
            )
            sz = float(self._INDICATOR_SIZE)
            x = float(ind_rect.x())
            y = float(ind_rect.y())
            path = QPainterPath()
            path.moveTo(x + sz * 0.18, y + sz * 0.52)
            path.lineTo(x + sz * 0.42, y + sz * 0.78)
            path.lineTo(x + sz * 0.85, y + sz * 0.22)
            painter.setPen(QPen(
                self._ACCENT,
                self._CHECK_PEN_WIDTH,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            ))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
        else:
            border_color = (
                self._BORDER_HOVER if self._hover else self._BORDER_NORMAL
            )
            painter.setPen(QPen(border_color, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                ind_rect, self._BORDER_RADIUS, self._BORDER_RADIUS,
            )

        # Text + focus ring are only painted when there's a label.
        # An empty-label CheckmarkBox is effectively an "indicator-only"
        # toggle — drawing a stray dotted rectangle next to it (the
        # previous behaviour) misled the user into thinking it was a
        # separate control.
        if self.text():
            text_x = (
                self._INDICATOR_LEFT_PAD + self._INDICATOR_SIZE
                + self._INDICATOR_MARGIN
            )
            text_rect = QRect(
                text_x, 0, self.width() - text_x, self.height(),
            )
            painter.setPen(self.palette().color(self.foregroundRole()))
            painter.drawText(
                text_rect,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                self.text(),
            )

            if self.hasFocus():
                fm = QFontMetrics(self.font())
                tw = fm.horizontalAdvance(self.text())
                focus_rect = QRect(
                    text_x - 2,
                    (self.height() - fm.height()) // 2 - 1,
                    tw + 4,
                    fm.height() + 2,
                )
                painter.setPen(QPen(self._ACCENT, 1, Qt.PenStyle.DotLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(focus_rect)

        painter.end()
