"""Weight Breakdown — order 50."""
from __future__ import annotations
import math
from app.core.reports.base import ReportSection, ReportContext, SectionCategory
from app.core.reports.renderer import ReportBuilder


class WeightBreakdownSection(ReportSection):
    section_id    = "weight_breakdown"
    title         = "Weight Estimation"
    default_order = 50
    category      = SectionCategory.ANALYSIS
    description   = (
        "MTOW convergence, mass components, per-segment weight fractions, "
        "and weight pie chart"
    )

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        t = ctx.t
        rb.add_heading(t("section.weight_breakdown.title"), level=1)

        wr = ctx.weight_result
        if wr is None:
            rb.add_note(t("section.weight_breakdown.no_result_note"))
            return

        dc  = ctx.display_converter
        b   = ctx.brief
        is_fuel = b.propulsion_type.uses_fuel
        is_elec = not b.propulsion_type.uses_fuel

        rb.add_paragraph(t("section.weight_breakdown.intro"))

        # ── Top-level weight summary ──────────────────────────────────────
        rb.add_heading(t("section.weight_breakdown.heading.mass_summary"), level=2)

        wto_v, wto_u = dc.mass(wr.w_to_kg)
        we_v,  we_u  = dc.mass(wr.w_empty_kg)
        wp_v,  wp_u  = dc.mass(wr.w_payload_kg)
        wfb_v, wfb_u = dc.mass(wr.w_fuel_or_battery_kg)

        pct_empty   = wr.w_empty_kg          / wr.w_to_kg * 100 if wr.w_to_kg else 0
        pct_payload = wr.w_payload_kg        / wr.w_to_kg * 100 if wr.w_to_kg else 0
        pct_fb      = wr.w_fuel_or_battery_kg/ wr.w_to_kg * 100 if wr.w_to_kg else 0

        if is_fuel and not is_elec:
            energy_label = t("section.weight_breakdown.label.fuel")
        elif is_elec and not is_fuel:
            energy_label = t("section.weight_breakdown.label.battery")
        else:
            energy_label = t("section.weight_breakdown.label.hybrid_energy")

        summary_rows = [
            [t("section.weight_breakdown.label.mtow"),
             f"{wto_v:.3f} {wto_u}", f"{100:.1f} %"],
            [t("section.weight_breakdown.label.empty"),
             f"{we_v:.3f} {we_u}",  f"{pct_empty:.1f} %"],
            [t("section.weight_breakdown.label.payload"),
             f"{wp_v:.3f} {wp_u}",  f"{pct_payload:.1f} %"],
            [energy_label,
             f"{wfb_v:.3f} {wfb_u}", f"{pct_fb:.1f} %"],
        ]

        rb.add_table(
            headers=[
                t("section.weight_breakdown.col.component"),
                t("section.weight_breakdown.col.mass"),
                t("section.weight_breakdown.col.pct_mtow"),
            ],
            rows=summary_rows,
            caption=t("section.weight_breakdown.table.summary_caption"),
        )

        # ── Key aerodynamic readouts ──────────────────────────────────────
        k = 1.0 / (math.pi * b.oswald_efficiency * b.aspect_ratio)
        rb.add_key_value_list([
            (t("section.weight_breakdown.kv.cl_star"),  f"{wr.cl_cruise:.4f}"),
            (t("section.weight_breakdown.kv.ld_max"),   f"{wr.ld_max:.2f}"),
            (t("section.weight_breakdown.kv.k"),        f"{k:.5f}"),
            (t("section.weight_breakdown.kv.converged"),
             t("common.yes") if wr.converged else t("common.no")),
            (t("section.weight_breakdown.kv.iterations"), str(wr.iterations)),
        ])

        # ── Per-segment weight fractions ──────────────────────────────────
        rb.add_heading(
            t("section.weight_breakdown.heading.segment_fractions"), level=2,
        )
        rb.add_paragraph(t("section.weight_breakdown.segments_intro"))

        seg_rows = []
        cumulative = 1.0
        for sf in wr.segment_fractions:
            cumulative *= sf.weight_fraction
            seg_rows.append([
                sf.segment_label,
                sf.segment_type.name,
                sf.energy_source.value,
                f"{sf.weight_fraction:.4f}",
                f"{cumulative:.4f}",
                f"{sf.cumulative_weight_kg:.3f} kg",
            ])

        rb.add_table(
            headers=[
                t("section.weight_breakdown.col.segment"),
                t("section.weight_breakdown.col.type"),
                t("section.weight_breakdown.col.energy"),
                t("section.weight_breakdown.col.fraction"),
                t("section.weight_breakdown.col.cumulative"),
                t("section.weight_breakdown.col.remaining_kg"),
            ],
            rows=seg_rows,
            caption=t("section.weight_breakdown.table.fractions_caption"),
        )

        # ── Pie chart ─────────────────────────────────────────────────────
        if ctx.weight_pie_chart_png:
            rb.add_figure(
                ctx.weight_pie_chart_png,
                caption=t("section.weight_breakdown.figure_caption"),
                width_cm=10.0,
            )
