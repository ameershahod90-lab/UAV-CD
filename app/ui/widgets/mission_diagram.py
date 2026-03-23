"""
Mission Profile Diagram — UAV-CD-APP
=======================================
Altitude-vs-distance diagram that dynamically updates as mission segments
change. Visual style mirrors Sadraey Figure 2.2 with numbered phases.

Rendering rules per segment type:
  TAKEOFF  → angled ramp from 0 up to cruise altitude (distance ∝ takeoff_run_m)
  CLIMB    → rising slope from ground (or takeoff end) to cruise altitude
  CRUISE   → flat line at cruise altitude (width proportional to range_km)
  LOITER   → wavy sinusoidal line at cruise altitude (visually distinct from cruise)
  DESCENT  → declining slope from cruise altitude to 0
  LANDING  → angled ramp from short height down to 0

Disabled segments are shown greyed-out at the same position.

Powered by pyqtgraph for anti-aliased drawing and dynamic updates.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from app.core.entities import (
    CruiseMissionSegment,
    LoiterMissionSegment,
    MissionSegment,
)
from app.core.enums import EnergySource, SegmentType


# Colour map per segment type (matches energy source for hybrid awareness)
_COLOUR_FUEL    = "#e67e22"   # orange  — fuel
_COLOUR_BATTERY = "#3498db"   # blue    — battery
_COLOUR_FIXED   = "#9b59b6"   # purple  — fixed segments
_COLOUR_DISABLED = "#444466"  # dim grey — disabled


def _seg_colour(seg: MissionSegment) -> str:
    if not seg.enabled:
        return _COLOUR_DISABLED
    if seg.segment_type.is_fixed:
        return _COLOUR_FIXED
    if seg.energy_source is EnergySource.BATTERY:
        return _COLOUR_BATTERY
    return _COLOUR_FUEL


class MissionDiagram(QWidget):
    """
    Live-updating mission altitude profile diagram.

    Call `update_segments(segments, cruise_altitude_m, takeoff_run_m)`
    whenever the segment list or parameters change.
    """

    # Normalised units for the diagram
    _CLIMB_DIST:   float = 3.0    # notional climb length [diagram units]
    _DESCENT_DIST: float = 3.0
    _TAKEOFF_DIST: float = 1.0
    _LANDING_DIST: float = 1.0
    _LOITER_WAVES: int   = 3      # number of sine waves in loiter segment
    _LOITER_AMP:   float = 0.04   # wave amplitude as fraction of cruise altitude
    _CRUISE_SCALE: float = 0.08   # range_km to diagram units scale factor

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

        self._curves: list[pg.PlotDataItem] = []
        self._texts: list[pg.TextItem] = []

    # ── Public API ────────────────────────────────────────────────────────

    def update_segments(
        self,
        segments: list[MissionSegment],
        cruise_altitude_m: float = 1500.0,
        takeoff_run_m: float = 50.0,
    ) -> None:
        """Rebuild the diagram from the given segment list."""
        self._plot.clear()
        self._curves = []
        self._texts = []

        cruise_alt = max(cruise_altitude_m, 100.0)

        # Build altitude profile
        x = 0.0
        prev_alt = 0.0
        seg_num = 1

        for seg in segments:
            colour = _seg_colour(seg)
            xs, ys, label = self._segment_profile(seg, x, prev_alt, cruise_alt, takeoff_run_m)
            if xs is None or len(xs) == 0:
                continue

            # Draw segment curve
            pen = pg.mkPen(colour, width=2.5, style=(
                Qt.PenStyle.SolidLine if seg.enabled
                else Qt.PenStyle.DashLine
            ))
            curve = self._plot.plot(xs, ys, pen=pen)
            self._curves.append(curve)

            # Numbered label at mid-segment
            mid_x = (xs[0] + xs[-1]) / 2.0
            mid_y = max(ys) + cruise_alt * 0.07
            text = pg.TextItem(
                text=f"  {seg_num}. {label}",
                color=pg.mkColor(colour),
                anchor=(0.5, 1.0),
            )
            text.setPos(mid_x, mid_y)
            self._plot.addItem(text)
            self._texts.append(text)

            x = xs[-1]
            prev_alt = ys[-1]
            seg_num += 1

        # Ground reference line
        self._plot.plot(
            [0, x + 1],
            [0, 0],
            pen=pg.mkPen("#3a3a5c", width=1, style=Qt.PenStyle.DotLine),
        )

        self._plot.setYRange(-cruise_alt * 0.15, cruise_alt * 1.25)
        self._plot.getAxis("left").setTicks([[(0, "0"), (cruise_alt, "Cruise")]])

    # ── Private helpers ───────────────────────────────────────────────────

    def _segment_profile(
        self,
        seg: MissionSegment,
        x_start: float,
        prev_alt: float,
        cruise_alt: float,
        takeoff_run: float,
    ) -> tuple[Optional[np.ndarray], Optional[np.ndarray], str]:
        """Return (xs, ys, label) arrays for a segment."""
        st = seg.segment_type

        if st is SegmentType.TAKEOFF:
            dx = max(takeoff_run / 50.0, self._TAKEOFF_DIST)
            xs = np.linspace(x_start, x_start + dx, 30)
            ys = np.linspace(0.0, cruise_alt * 0.12, 30)
            return xs, ys, "Takeoff"

        elif st is SegmentType.CLIMB:
            xs = np.linspace(x_start, x_start + self._CLIMB_DIST, 40)
            ys = np.linspace(prev_alt, cruise_alt, 40)
            return xs, ys, "Climb"

        elif st is SegmentType.CRUISE:
            assert isinstance(seg, CruiseMissionSegment)
            dx = max(seg.range_km * self._CRUISE_SCALE, 2.0)
            xs = np.linspace(x_start, x_start + dx, 20)
            ys = np.full_like(xs, cruise_alt)
            return xs, ys, f"Cruise ({seg.range_km:.0f} km)"

        elif st is SegmentType.LOITER:
            assert isinstance(seg, LoiterMissionSegment)
            dx = max(seg.endurance_hr * 2.0, 2.0)
            xs = np.linspace(x_start, x_start + dx, 120)
            # Sinusoidal wave to discriminate from flat cruise
            wave = np.sin(2 * math.pi * self._LOITER_WAVES * (xs - x_start) / dx)
            ys = cruise_alt + wave * cruise_alt * self._LOITER_AMP
            return xs, ys, f"Loiter ({seg.endurance_hr:.1f} h)"

        elif st is SegmentType.DESCENT:
            xs = np.linspace(x_start, x_start + self._DESCENT_DIST, 40)
            ys = np.linspace(cruise_alt, 0.0, 40)
            return xs, ys, "Descent"

        elif st is SegmentType.LANDING:
            xs = np.linspace(x_start, x_start + self._LANDING_DIST, 20)
            ys = np.linspace(prev_alt, 0.0, 20)
            return xs, ys, "Landing"

        return None, None, ""
