"""Weight Breakdown — order 50."""
from __future__ import annotations
from app.core.reports.base import ReportSection, ReportContext, SectionCategory
from app.core.reports.renderer import ReportBuilder


class WeightBreakdownSection(ReportSection):
    section_id    = "weight_breakdown"
    title         = "Weight Estimation"
    default_order = 50
    category      = SectionCategory.ANALYSIS
    description   = (
        "MTOW convergence, mass components, per-segment weight fractions, "
        "and optional weight pie chart"
    )

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        rb.add_heading(self.title, level=1)

        wr = ctx.weight_result
        if wr is None:
            rb.add_note(
                "Weight estimation results not available — run sizing first."
            )
            return

        dc = ctx.display_converter

        rb.add_paragraph(
            "Takeoff weight is estimated using the iterative Breguet mission "
            "fraction method (Sadraey §2.6-2.7).  The weight loop converges "
            "when successive MTOW estimates differ by less than 0.1 g."
        )

        # ── Top-level weight summary ──────────────────────────────────────
        rb.add_heading("Mass Summary", level=2)
        wto_v, wto_u = dc.mass(wr.w_to_kg)
        we_v,  we_u  = dc.mass(wr.w_empty_kg)
        wp_v,  wp_u  = dc.mass(wr.w_payload_kg)
        wf_v,  wf_u  = dc.mass(wr.w_fuel_kg)   if wr.w_fuel_kg    > 0 else (0, "kg")
        wb_v,  wb_u  = dc.mass(wr.w_battery_kg) if wr.w_battery_kg > 0 else (0, "kg")

        summary_rows = [
            ["Maximum Takeoff Weight", f"{wto_v:.3f} {wto_u}", f"{100:.1f} %"],
            ["Empty Weight",           f"{we_v:.3f}  {we_u}",  f"{wr.w_empty_kg/wr.w_to_kg*100:.1f} %"],
            ["Payload",                f"{wp_v:.3f}  {wp_u}",  f"{wr.w_payload_kg/wr.w_to_kg*100:.1f} %"],
        ]
        if wr.w_fuel_kg > 0:
            summary_rows.append(
                ["Fuel",  f"{wf_v:.3f} {wf_u}", f"{wr.w_fuel_kg/wr.w_to_kg*100:.1f} %"]
            )
        if wr.w_battery_kg > 0:
            summary_rows.append(
                ["Battery", f"{wb_v:.3f} {wb_u}", f"{wr.w_battery_kg/wr.w_to_kg*100:.1f} %"]
            )

        rb.add_table(
            headers=["Component", "Mass", "% MTOW"],
            rows=summary_rows,
            caption="UAV mass breakdown",
        )

        # ── Aerodynamic readouts ──────────────────────────────────────────
        rb.add_key_value_list([
            ("CL* (best L/D speed)", f"{wr.cl_cruise:.4f}"),
            ("(L/D)max",             f"{wr.ld_max:.2f}"),
        ])

        # ── Per-segment weight fractions ──────────────────────────────────
        rb.add_heading("Segment Weight Fractions", level=2)
        rb.add_paragraph(
            "Each segment reduces the aircraft weight by its fraction Wi/Wi-1. "
            "The product of all fractions gives the overall mission weight fraction."
        )

        seg_rows = []
        cumulative = 1.0
        for sf in wr.segment_fractions:
            cumulative *= sf.fraction
            seg_rows.append([
                sf.segment_label,
                sf.energy_source_label,
                f"{sf.fraction:.4f}",
                f"{cumulative:.4f}",
            ])

        rb.add_table(
            headers=["Segment", "Energy Source", "Wi/Wi-1", "Cumulative"],
            rows=seg_rows,
            caption="Per-segment weight fractions",
        )

        # ── Pie chart ─────────────────────────────────────────────────────
        if ctx.weight_pie_chart_png:
            rb.add_figure(
                ctx.weight_pie_chart_png,
                caption="Weight component distribution",
                width_cm=10.0,
            )
