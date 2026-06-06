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
from app.core.sensitivity import (
    OATSweep,
    TornadoData,
    display_label_for_output,
    display_label_for_parameter,
    unit_kind_for_output,
    unit_kind_for_parameter,
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


# ── Sensitivity: tornado bar chart ──────────────────────────────────────────


# Colour palette mirrors the live TornadoWidget in the UI so report
# figures match what the designer sees on the Sensitivity tab.
_TORNADO_POS = "#2980b9"   # input increase RAISES the output
_TORNADO_NEG = "#c0392b"   # input increase LOWERS the output
_TORNADO_BASELINE = "#7f8c8d"


def render_tornado_png(
    tornado_data: TornadoData,
    propulsion: PropulsionType,
    dc: DisplayConverter,
    *,
    max_bars: int = 10,
) -> Optional[bytes]:
    """Render a single tornado chart for one output as PNG bytes.

    Bar widths and X-axis labels are display-converted via ``dc``; the
    output's name is resolved via ``display_label_for_output`` so jet
    designs render "Engine Thrust" instead of "Engine Power".

    Returns ``None`` if the tornado has no bars (which happens before
    the design point is computed).
    """
    bars = list(tornado_data.bars)[:max_bars]
    if not bars:
        return None
    try:
        out_label = display_label_for_output(tornado_data.output_id, propulsion)
        kind = unit_kind_for_output(tornado_data.output_id, propulsion)
        conv = getattr(dc, kind, None)
        if conv is not None:
            out_factor, out_unit = conv(1.0)
        else:
            out_factor, out_unit = 1.0, ""

        # Convert all delta widths to display units.
        widths_low  = [(b.delta_low  or 0.0) * out_factor for b in bars]
        widths_high = [(b.delta_high or 0.0) * out_factor for b in bars]
        # Y positions: top of chart = index 0 (most influential bar).
        y_pos = list(range(len(bars)))

        plt = _pyplot()
        # Height scales with bar count so labels never overlap.
        fig_h = max(2.4, 0.45 * len(bars) + 0.8)
        fig, ax = plt.subplots(figsize=(8.5, fig_h))
        fig.patch.set_facecolor(_FIG_FACE)
        ax.set_facecolor(_AX_FACE)

        # Two passes: split by colour. Bars are signed widths so they
        # extend either side of the zero baseline.
        ax.barh(y_pos, widths_low,  height=0.6,
                color=_TORNADO_NEG, edgecolor="#7c1f15", linewidth=0.5)
        ax.barh(y_pos, widths_high, height=0.6,
                color=_TORNADO_POS, edgecolor="#1a4f70", linewidth=0.5)

        # Zero baseline (current design value)
        ax.axvline(0.0, color=_TORNADO_BASELINE,
                   linewidth=1.4, linestyle="--", zorder=1)

        # Parameter names on Y axis (top = most influential).
        ax.set_yticks(y_pos)
        ax.set_yticklabels(
            [b.parameter.label for b in bars],
            color=_AX_TEXT, fontsize=9,
        )
        ax.invert_yaxis()

        ax.set_xlabel(
            f"Δ {out_label} [{out_unit}]",
            color=_AX_TEXT, fontsize=10,
        )
        ax.tick_params(colors=_AX_TEXT, labelsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(_AX_TEXT)
        ax.grid(True, axis="x", color=_GRID, linestyle="-",
                linewidth=0.5, alpha=0.6)
        ax.set_axisbelow(True)

        # Pad X range so numeric tip labels don't clip.
        all_deltas = widths_low + widths_high
        max_abs = max((abs(v) for v in all_deltas if v), default=1.0)
        ax.set_xlim(-max_abs * 1.30, max_abs * 1.30)

        # Numeric Δ at each bar tip, anchored outside the bar.
        offset = max_abs * 0.04
        for y, lo, hi in zip(y_pos, widths_low, widths_high):
            for delta, color in ((lo, _TORNADO_NEG), (hi, _TORNADO_POS)):
                if delta == 0:
                    continue
                ha = "left" if delta >= 0 else "right"
                x  = (delta + offset) if delta >= 0 else (delta - offset)
                ax.text(x, y, f"{delta:+.2f}",
                        ha=ha, va="center",
                        color=color, fontsize=8)

        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception:
        return None


# ── Sensitivity: OAT sweep curve ────────────────────────────────────────────


# Per-output curve colours mirror SweepWidget so report and UI match.
_SWEEP_COLORS = {
    "mtow_kg":              "#e67e22",
    "wing_area_m2":         "#27ae60",
    "engine_power_w":       "#3498db",
    "wingspan_m":           "#9b59b6",
    "w_empty_kg":           "#c0392b",
    "empty_weight_fraction": "#16a085",
    "ld_max":               "#1abc9c",
    "cl_cruise":            "#f1c40f",
    "wing_loading_nm2":     "#34495e",
    "power_loading_nw":     "#8e44ad",
    "w_fuel_or_battery_kg": "#d35400",
    "fuel_battery_fraction": "#7f8c8d",
}
_SWEEP_DEFAULT_COLOR = "#888899"
_SWEEP_BASELINE_COLOR = "#888899"


def render_sweep_png(
    sweep: OATSweep,
    output_ids: list[str],
    propulsion: PropulsionType,
    dc: DisplayConverter,
) -> Optional[bytes]:
    """Render an OAT-sweep figure as PNG bytes.

    For a single output: one large panel. For N outputs: N horizontal
    small multiples — the same shape as the live ``SweepWidget``. Every
    axis is display-converted; titles use propulsion-aware labels.

    Returns ``None`` if no requested output has any valid sample.
    """
    if not output_ids:
        return None
    try:
        param = sweep.parameter
        # X-axis label + factor (the swept input). Sensitivity inputs
        # that are dimensionless return a 1.0 factor and the raw unit
        # symbol — see ``unit_kind_for_parameter``.
        x_kind = unit_kind_for_parameter(param)
        x_conv = getattr(dc, x_kind, None)
        if x_conv is None or x_kind == "ratio":
            x_factor, x_unit = 1.0, param.unit
        else:
            x_factor, x_unit = x_conv(1.0)
        x_label = display_label_for_parameter(param, propulsion)
        baseline_display = sweep.baseline * x_factor

        plt = _pyplot()
        n = len(output_ids)
        fig, axes = plt.subplots(
            1, n, figsize=(4.6 * n, 3.6), squeeze=False,
        )
        fig.patch.set_facecolor(_FIG_FACE)
        any_curve = False
        for ax, output_id in zip(axes[0], output_ids):
            ax.set_facecolor(_AX_FACE)

            out_label = display_label_for_output(output_id, propulsion)
            y_kind = unit_kind_for_output(output_id, propulsion)
            y_conv = getattr(dc, y_kind, None)
            if y_conv is not None:
                y_factor, y_unit = y_conv(1.0)
            else:
                y_factor, y_unit = 1.0, ""

            xs_raw, ys_raw = sweep.outputs_for(output_id)
            valid = [(x, y) for x, y in zip(xs_raw, ys_raw) if y is not None]
            if not valid:
                ax.text(
                    0.5, 0.5, "No data",
                    ha="center", va="center",
                    color=_AX_TEXT, fontsize=10, fontstyle="italic",
                    transform=ax.transAxes,
                )
                ax.set_title(out_label, color=_TITLE_BLUE, fontsize=10)
                continue
            any_curve = True
            xs_d = [x * x_factor for x, _ in valid]
            ys_d = [y * y_factor for _, y in valid]
            ax.plot(
                xs_d, ys_d,
                color=_SWEEP_COLORS.get(output_id, _SWEEP_DEFAULT_COLOR),
                linewidth=2.2,
            )

            # Vertical baseline marker at the swept-parameter's current value.
            ax.axvline(
                baseline_display, color=_SWEEP_BASELINE_COLOR,
                linewidth=1.2, linestyle="--",
            )
            ax.set_title(out_label, color=_TITLE_BLUE, fontsize=10)
            ax.set_xlabel(f"{x_label} [{x_unit}]",
                          color=_AX_TEXT, fontsize=9)
            ax.set_ylabel(f"{out_label} [{y_unit}]",
                          color=_AX_TEXT, fontsize=9)
            ax.tick_params(colors=_AX_TEXT, labelsize=8)
            ax.grid(True, color=_GRID, linestyle="-",
                    linewidth=0.5, alpha=0.6)
            ax.set_axisbelow(True)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            for s in ("left", "bottom"):
                ax.spines[s].set_color(_AX_TEXT)

        if not any_curve:
            plt.close(fig)
            return None

        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception:
        return None
