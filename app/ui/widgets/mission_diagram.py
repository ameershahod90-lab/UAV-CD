"""
Mission Profile Diagram — UAV-CD-APP
=======================================
Live pyqtgraph rendering of the altitude-vs-distance mission diagram.

The segment-shape math lives in ``app/core/plots/mission_profile.py`` so the
matplotlib renderer used by the report export shares it (DRY). This widget
only handles the Qt/pyqtgraph drawing — it takes a ``DesignBrief`` and
re-renders whenever called.
"""

from __future__ import annotations

from typing import Optional

import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from app.core.entities import DesignBrief
from app.core.plots.mission_profile import build_mission_profile_data


class MissionDiagram(QWidget):
    """Live-updating mission altitude profile diagram.

    Call ``update_from_brief(brief)`` whenever the brief or its segments
    change. The widget never owns plot-data logic — it just draws whatever
    ``build_mission_profile_data`` produces.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        pg.setConfigOptions(antialias=True)
        self._plot = pg.PlotWidget(background="#1e1e2e")
        self._plot.setLabel("left", "Altitude", units="")
        self._plot.setLabel("bottom", "Distance", units="")
        self._plot.showGrid(x=False, y=False)
        self._plot.getAxis("left").setTextPen("#888aaa")
        self._plot.getAxis("bottom").setTextPen("#888aaa")
        layout.addWidget(self._plot)

    # ── Public API ────────────────────────────────────────────────────────

    def update_from_brief(self, brief: DesignBrief) -> None:
        """Rebuild the diagram from a design brief."""
        data = build_mission_profile_data(brief)
        self._plot.clear()

        for seg in data.segments:
            pen = pg.mkPen(seg.color, width=2.5, style=(
                Qt.PenStyle.SolidLine if seg.enabled
                else Qt.PenStyle.DashLine
            ))
            self._plot.plot(seg.xs, seg.ys, pen=pen)

            mid_x = float((seg.xs[0] + seg.xs[-1]) / 2.0)
            mid_y = float(max(seg.ys) + data.cruise_alt * 0.07)
            text = pg.TextItem(
                text=f"  {seg.seg_num}. {seg.label}",
                color=pg.mkColor(seg.color),
                anchor=(0.5, 1.0),
            )
            text.setPos(mid_x, mid_y)
            self._plot.addItem(text)

        # Ground reference line
        self._plot.plot(
            [0, data.x_max + 1], [0, 0],
            pen=pg.mkPen("#3a3a5c", width=1, style=Qt.PenStyle.DotLine),
        )

        self._plot.setYRange(-data.cruise_alt * 0.15, data.cruise_alt * 1.25)
        self._plot.getAxis("left").setTicks(
            [[(0, "0"), (data.cruise_alt, "Cruise")]]
        )
