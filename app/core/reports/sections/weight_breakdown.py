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
        rb.add_heading(self.title, level=1)

        wr = ctx.weight_result
        if wr is None:
            rb.add_note(
                "Weight estimation results not available — run sizing first."
            )
            return

        dc  = ctx.display_converter
        b   = ctx.brief
        is_fuel = b.propulsion_type.is_fuel_mode
        is_elec = not b.propulsion_type.is_fuel_mode and not b.propulsion_type.is_hybrid

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
        wfb_v, wfb_u = dc.mass(wr.w_fuel_or_battery_kg)

        pct_empty   = wr.w_empty_kg          / wr.w_to_kg * 100 if wr.w_to_kg else 0
        pct_payload = wr.w_payload_kg        / wr.w_to_kg * 100 if wr.w_to_kg else 0
        pct_fb      = wr.w_fuel_or_battery_kg/ wr.w_to_kg * 100 if wr.w_to_kg else 0

        energy_label = (
            "Fuel" if is_fuel
            else "Battery" if is_elec
            else "Fuel/Battery (Hybrid)"
        )

        summary_rows = [
            ["Maximum Takeoff Weight (MTOW)", f"{wto_v:.3f} {wto_u}", f"{100:.1f} %"],
            ["Empty Weight",                  f"{we_v:.3f} {we_u}",  f"{pct_empty:.1f} %"],
            ["Payload",                       f"{wp_v:.3f} {wp_u}",  f"{pct_payload:.1f} %"],
            [energy_label,                    f"{wfb_v:.3f} {wfb_u}", f"{pct_fb:.1f} %"],
        ]

        rb.add_table(
            headers=["Component", "Mass", "% MTOW"],
            rows=summary_rows,
            caption="UAV mass breakdown",
        )

        # ── Key aerodynamic readouts ──────────────────────────────────────
        k = 1.0 / (math.pi * b.oswald_efficiency * b.aspect_ratio)
        rb.add_key_value_list([
            ("CL* (best L/D CL)",    f"{wr.cl_cruise:.4f}"),
            ("(L/D)max",             f"{wr.ld_max:.2f}"),
            ("k (induced drag factor)", f"{k:.5f}"),
            ("Converged",            "Yes" if wr.converged else "No"),
            ("Iterations",           str(wr.iterations)),
        ])

        # ── Per-segment weight fractions ──────────────────────────────────
        rb.add_heading("Segment Weight Fractions", level=2)
        rb.add_paragraph(
            "Each segment reduces the aircraft weight by its fraction Wi/Wi-1. "
            "The product of all fractions gives the overall mission weight fraction "
            "(Sadraey §2.6, Table 2.4)."
        )

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
            headers=["Segment", "Type", "Energy", "Wi/Wi-1",
                     "Cumulative", "Remaining kg"],
            rows=seg_rows,
            caption="Per-segment weight fractions and cumulative mass",
        )

        # ── Pie chart ─────────────────────────────────────────────────────
        if ctx.weight_pie_chart_png:
            rb.add_figure(
                ctx.weight_pie_chart_png,
                caption="Weight component distribution",
                width_cm=10.0,
            )
