"""
Mission Profile Plot Data — UAV-CD-APP
==========================================
Pure data builder for the altitude-vs-distance mission diagram.

The same builder feeds:
  - the live pyqtgraph widget in ``app/ui/widgets/mission_diagram.py``
  - the matplotlib renderer in ``app/services/figure_renderers.py`` (export)

Visual style (mirrors Sadraey Figure 2.2):
  TAKEOFF  → angled ramp from 0 up to ~12 % of cruise altitude
  CLIMB    → rising slope from ground to cruise altitude
  CRUISE   → flat line at cruise altitude (width ∝ range_km)
  LOITER   → wavy sinusoidal line at cruise altitude (visually distinct)
  DESCENT  → declining slope from cruise altitude to 0
  LANDING  → angled ramp from short height down to 0

Disabled segments are still included in the returned data (with
``enabled=False``) so consumers can grey them out or skip them.

Layer: ``core/`` — pure Python (numpy is allowed). No Qt / no matplotlib.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from app.core.entities import (
    CruiseMissionSegment,
    DesignBrief,
    LoiterMissionSegment,
    MissionSegment,
)
from app.core.enums import EnergySource, SegmentType

# Brand colours (kept in sync with the Qt widget for visual consistency)
COLOUR_FUEL    = "#e67e22"   # orange  — fuel-powered segment
COLOUR_BATTERY = "#3498db"   # blue    — battery-powered segment
COLOUR_FIXED   = "#9b59b6"   # purple  — fixed segments (no per-segment energy)
COLOUR_DISABLED = "#888888"  # grey    — disabled segments

# Normalised distance units for the diagram (Sadraey Fig. 2.2 has no scale)
_CLIMB_DIST:   float = 3.0    # notional climb length in diagram units
_DESCENT_DIST: float = 3.0
_TAKEOFF_DIST: float = 1.0
_LANDING_DIST: float = 1.0
_LOITER_WAVES: int   = 3      # number of sine waves drawn in a loiter
_LOITER_AMP:   float = 0.04   # wave amplitude as a fraction of cruise altitude
_CRUISE_SCALE: float = 0.08   # range_km → diagram-units scale factor


@dataclass(frozen=True)
class MissionSegmentRender:
    """A single rendered segment ready for plotting."""
    seg_num:   int           # 1-based segment number (excludes nothing)
    label:    str           # e.g. "Cruise (50 km)"
    xs:       np.ndarray    # x positions in diagram units
    ys:       np.ndarray    # altitudes in metres
    color:    str           # hex e.g. "#3498db"
    enabled:  bool


@dataclass(frozen=True)
class MissionProfileData:
    """Everything a plot renderer needs to draw the mission profile."""
    segments:   tuple[MissionSegmentRender, ...]
    cruise_alt: float                          # cruise altitude in metres
    x_max:      float                          # rightmost x in diagram units


def segment_colour(seg: MissionSegment) -> str:
    """Pick the colour for a segment.

    Disabled → grey; fixed segments → purple; dynamic segments → fuel orange
    or battery blue depending on the segment's energy source.
    """
    if not seg.enabled:
        return COLOUR_DISABLED
    if seg.segment_type.is_fixed:
        return COLOUR_FIXED
    if seg.energy_source is EnergySource.BATTERY:
        return COLOUR_BATTERY
    return COLOUR_FUEL


def _segment_xs_ys(
    seg: MissionSegment,
    x_start: float,
    prev_alt: float,
    cruise_alt: float,
    takeoff_run: float,
) -> Optional[tuple[np.ndarray, np.ndarray, str]]:
    """Return (xs, ys, label) for one segment, or None for unknown types."""
    st = seg.segment_type

    if st is SegmentType.TAKEOFF:
        dx = max(takeoff_run / 50.0, _TAKEOFF_DIST)
        xs = np.linspace(x_start, x_start + dx, 30)
        ys = np.linspace(0.0, cruise_alt * 0.12, 30)
        return xs, ys, "Takeoff"

    if st is SegmentType.CLIMB:
        xs = np.linspace(x_start, x_start + _CLIMB_DIST, 40)
        ys = np.linspace(prev_alt, cruise_alt, 40)
        return xs, ys, "Climb"

    if st is SegmentType.CRUISE:
        assert isinstance(seg, CruiseMissionSegment)
        dx = max(seg.range_km * _CRUISE_SCALE, 2.0)
        xs = np.linspace(x_start, x_start + dx, 20)
        ys = np.full_like(xs, cruise_alt)
        return xs, ys, f"Cruise ({seg.range_km:.0f} km)"

    if st is SegmentType.LOITER:
        assert isinstance(seg, LoiterMissionSegment)
        dx = max(seg.endurance_hr * 2.0, 2.0)
        xs = np.linspace(x_start, x_start + dx, 120)
        wave = np.sin(2 * math.pi * _LOITER_WAVES * (xs - x_start) / dx)
        ys = cruise_alt + wave * cruise_alt * _LOITER_AMP
        return xs, ys, f"Loiter ({seg.endurance_hr:.1f} h)"

    if st is SegmentType.DESCENT:
        xs = np.linspace(x_start, x_start + _DESCENT_DIST, 40)
        ys = np.linspace(cruise_alt, 0.0, 40)
        return xs, ys, "Descent"

    if st is SegmentType.LANDING:
        xs = np.linspace(x_start, x_start + _LANDING_DIST, 20)
        ys = np.linspace(prev_alt, 0.0, 20)
        return xs, ys, "Landing"

    return None


def build_mission_profile_data(brief: DesignBrief) -> MissionProfileData:
    """Compose the renderable mission-profile data from a design brief.

    The brief's mission_segments are normalised to the propulsion type so
    each segment's energy_source colour is correct (fuel vs battery for
    HYBRID, or all-fuel / all-battery for non-hybrid propulsions).
    """
    cruise_alt = max(brief.cruise_altitude_m, 100.0)
    takeoff_run = brief.takeoff_run_m

    rendered: list[MissionSegmentRender] = []
    x = 0.0
    prev_alt = 0.0
    for i, raw in enumerate(brief.mission_segments, 1):
        seg = raw.with_energy_source(brief.propulsion_type)
        result = _segment_xs_ys(seg, x, prev_alt, cruise_alt, takeoff_run)
        if result is None:
            continue
        xs, ys, label = result
        rendered.append(
            MissionSegmentRender(
                seg_num=i,
                label=label,
                xs=xs,
                ys=ys,
                color=segment_colour(seg),
                enabled=seg.enabled,
            )
        )
        x = float(xs[-1])
        prev_alt = float(ys[-1])

    return MissionProfileData(
        segments=tuple(rendered),
        cruise_alt=cruise_alt,
        x_max=x,
    )
