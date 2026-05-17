"""
Figure Renderers — UAV-CD-APP
================================
Matplotlib renderers used by the report export to produce PNG bytes for
embedded figures.  These run server-side (no Qt dependency), so they work
regardless of which UI tab is visible — and they render the same data the
live pyqtgraph plots show because both consume the same plot-data builders
in ``app/core/plots/``.

Each render function returns PNG bytes ready for ``ReportBuilder.add_figure``.
"""

from __future__ import annotations

import io
from typing import Optional

from app.core.display_converter import DisplayConverter
from app.core.entities import (
    ConstraintResult,
    DesignBrief,
    DesignPoint,
    WeightResult,
)
from app.core.enums import PropulsionType
from app.core.plots import (
    build_matching_plot_data,
    build_mission_profile_data,
)

# Plot styling — kept consistent with the Qt UI brand palette
_FIG_FACE   = "#ffffff"   # page-friendly white background
_AX_FACE    = "#fafafa"   # subtle off-white axes
_GRID       = "#dddde2"
_AX_TEXT    = "#333344"
_STALL_RED  = "#e74c3c"
_GROUND     = "#9b9bab"
_DESIGN_STAR = "#f39c12"
_TITLE_BLUE = "#1A5C96"


def _pyplot():
    """Lazy import of matplotlib in Agg mode (no GUI backend)."""
    import matplotlib
    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt
    return plt


# ── Mission profile ─────────────────────────────────────────────────────────


def render_mission_profile_png(brief: DesignBrief) -> Optional[bytes]:
    """Render the mission altitude profile as PNG bytes.

    Returns None if no segments are enabled or the brief has no usable
    mission. Errors during rendering are caught and propagated as None so
    the caller can fall back to a placeholder note in the report.
    """
    try:
        data = build_mission_profile_data(brief)
        if not data.segments:
            return None

        plt = _pyplot()
        fig, ax = plt.subplots(figsize=(9, 3.5))
        fig.patch.set_facecolor(_FIG_FACE)
        ax.set_facecolor(_AX_FACE)

        for seg in data.segments:
            linestyle = "-" if seg.enabled else "--"
            ax.plot(
                seg.xs, seg.ys,
                color=seg.color, linewidth=2.4, linestyle=linestyle,
                solid_capstyle="round",
            )
            mid_x = float((seg.xs[0] + seg.xs[-1]) / 2.0)
            mid_y = float(max(seg.ys) + data.cruise_alt * 0.06)
            ax.annotate(
                f"{seg.seg_num}. {seg.label}",
                xy=(mid_x, mid_y),
                ha="center", va="bottom",
                color=seg.color, fontsize=8, fontweight="bold",
            )

        # Ground reference
        ax.plot(
            [0, data.x_max + 1], [0, 0],
            color=_GROUND, linewidth=1.0, linestyle=":",
        )

        ax.set_xlim(-0.5, data.x_max + 1)
        ax.set_ylim(-data.cruise_alt * 0.15, data.cruise_alt * 1.30)
        ax.set_xlabel("Distance (relative)", color=_AX_TEXT, fontsize=9)
        ax.set_ylabel("Altitude [m]", color=_AX_TEXT, fontsize=9)
        ax.tick_params(colors=_AX_TEXT, labelsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(_AX_TEXT)
        ax.set_yticks([0.0, data.cruise_alt])
        ax.set_yticklabels(["0", f"{data.cruise_alt:.0f}"])
        ax.set_xticks([])   # x scale is notional, no need to display ticks
        ax.grid(False)

        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception:
        return None


# ── Matching diagram ────────────────────────────────────────────────────────


def render_matching_diagram_png(
    cr: Optional[ConstraintResult],
    dp: Optional[DesignPoint],
    dc: DisplayConverter,
) -> Optional[bytes]:
    """Render the W/S vs W/P (or T/W) matching diagram as PNG bytes.

    The Y-axis is clipped to a sensible range around the design point so
    constraint asymptotes don't squeeze the feasible region off-screen.
    """
    if cr is None:
        return None
    try:
        data = build_matching_plot_data(cr, dp, dc)
        plt = _pyplot()
        fig, ax = plt.subplots(figsize=(9, 5.4))
        fig.patch.set_facecolor(_FIG_FACE)
        ax.set_facecolor(_AX_FACE)

        for curve in data.curves:
            ax.plot(
                curve.ws, curve.loading,
                color=curve.color, linewidth=2.0, label=curve.name,
            )

        # Stall vertical line
        ax.plot(
            [data.stall_x, data.stall_x], [0.0, data.y_top],
            color=_STALL_RED, linewidth=2.0, linestyle="--",
            label="Stall Limit",
        )

        # Design-point ★
        if data.design_point is not None:
            dp_x, dp_y = data.design_point
            ax.scatter(
                [dp_x], [dp_y],
                marker="*", s=240, color=_DESIGN_STAR,
                edgecolors="#7a4e00", linewidths=1.2,
                zorder=10, label="Design Point",
            )

        ax.set_xlabel(data.ws_label, color=_AX_TEXT, fontsize=10)
        ax.set_ylabel(data.loading_label, color=_AX_TEXT, fontsize=10)
        ax.set_ylim(0.0, data.y_top)
        ax.tick_params(colors=_AX_TEXT, labelsize=9)
        ax.grid(True, color=_GRID, linestyle="-", linewidth=0.5, alpha=0.7)
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(_AX_TEXT)

        ax.legend(
            loc="best",
            fontsize=8,
            frameon=True,
            facecolor="white",
            edgecolor=_GRID,
        )

        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception:
        return None


# ── Weight pie chart ────────────────────────────────────────────────────────


def render_weight_pie_png(
    wr: Optional[WeightResult],
    propulsion: PropulsionType,
) -> Optional[bytes]:
    """Render the weight breakdown as a pie chart.

    WeightResult stores a single combined ``w_fuel_or_battery_kg`` field;
    the slice is labelled per propulsion type (Battery for electric, Fuel
    for fuel-based, Fuel + Battery for hybrid).
    """
    if wr is None:
        return None
    try:
        if propulsion.is_electric and not propulsion.uses_fuel:
            energy_label, energy_color = "Battery", "#9b59b6"
        elif propulsion.uses_fuel and not propulsion.is_electric:
            energy_label, energy_color = "Fuel", "#e67e22"
        else:  # HYBRID
            energy_label, energy_color = "Fuel + Battery", "#e67e22"

        labels: list[str] = []
        sizes:  list[float] = []
        colors: list[str] = []
        if wr.w_payload_kg > 0:
            labels.append(f"Payload\n{wr.w_payload_kg:.2f} kg")
            sizes.append(wr.w_payload_kg)
            colors.append("#3498db")
        if wr.w_fuel_or_battery_kg > 0:
            labels.append(f"{energy_label}\n{wr.w_fuel_or_battery_kg:.2f} kg")
            sizes.append(wr.w_fuel_or_battery_kg)
            colors.append(energy_color)
        if wr.w_empty_kg > 0:
            labels.append(f"Empty\n{wr.w_empty_kg:.2f} kg")
            sizes.append(wr.w_empty_kg)
            colors.append("#2ecc71")
        if not sizes:
            return None

        plt = _pyplot()
        fig, ax = plt.subplots(figsize=(6, 4))
        fig.patch.set_facecolor(_FIG_FACE)
        ax.pie(
            sizes, labels=labels, colors=colors,
            autopct="%1.1f%%", startangle=90, pctdistance=0.8,
        )
        ax.set_title(f"MTOW = {wr.w_to_kg:.3f} kg", fontsize=12, color=_TITLE_BLUE)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except ImportError:
        return None
    except Exception:
        return None
