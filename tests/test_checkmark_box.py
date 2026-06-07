"""
CheckmarkBox — focused tests.

The widget subclasses QCheckBox; this file asserts that the public
interaction model survives the paintEvent override:

  * isChecked() / setChecked() round-trip
  * toggled signal fires on programmatic state change
  * left-mouse click anywhere on the widget toggles the state
    (i.e. the override doesn't drop click forwarding)
  * Two instances of CheckmarkBox are valid QCheckBox instances
    (so isinstance dispatch in tests/legacy code keeps working)
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QCheckBox

from app.ui.widgets.checkmark_box import CheckmarkBox


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


class TestCheckmarkBox:
    def test_is_a_qcheckbox_subclass(self, qapp):
        box = CheckmarkBox("test")
        assert isinstance(box, QCheckBox)
        assert isinstance(box, CheckmarkBox)

    def test_set_and_get_checked(self, qapp):
        box = CheckmarkBox("test")
        assert box.isChecked() is False
        box.setChecked(True)
        assert box.isChecked() is True
        box.setChecked(False)
        assert box.isChecked() is False

    def test_toggled_signal_fires_on_set_checked(self, qapp):
        box = CheckmarkBox("test")
        received: list[bool] = []
        box.toggled.connect(received.append)
        box.setChecked(True)
        box.setChecked(False)
        assert received == [True, False]

    def test_left_click_toggles(self, qapp):
        """A left-mouse click anywhere on the widget must flip its check
        state — this is the canonical interaction that the QListWidget
        hack broke. Confirms the paintEvent override doesn't intercept
        QCheckBox's mouse handling."""
        box = CheckmarkBox("test")
        box.resize(160, 22)
        # Click in the middle of the indicator area.
        click_point = QPointF(8.0, 11.0)
        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress, click_point,
            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        release = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease, click_point,
            Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(box, press)
        QApplication.sendEvent(box, release)
        assert box.isChecked() is True
        # Click again — toggles back off.
        QApplication.sendEvent(box, press)
        QApplication.sendEvent(box, release)
        assert box.isChecked() is False

    def test_size_hint_accommodates_text_and_indicator(self, qapp):
        short = CheckmarkBox("A")
        long  = CheckmarkBox("A long descriptive label for the option")
        assert long.sizeHint().width() > short.sizeHint().width()
        # Height covers the indicator (16) plus a small margin.
        assert short.sizeHint().height() >= 16
