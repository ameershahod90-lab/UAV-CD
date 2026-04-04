"""Design Point Summary — order 80."""
from __future__ import annotations
from app.core.reports.base import ReportSection, ReportContext, SectionCategory
from app.core.reports.renderer import ReportBuilder


class DesignPointSummarySection(ReportSection):
    section_id    = "design_point_summary"
    title         = "Design Point and Sizing Results"
    default_order = 80
    category      = SectionCategory.ANALYSIS
    description   = "Final sizing: MTOW, wing area, wingspan, engine power/thrust"

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        rb.add_heading(self.title, level=1)
        rb.add_paragraph(
            "From the selected design point on the matching diagram, the "
            "fundamental aircraft sizing quantities are derived using the "
            "following relationships (Sadraey §2.9, Eq. 2.49-2.51)."
        )

        dp = ctx.design_point
        if dp is None:
            rb.add_note("Design point not available — run sizing first.")
            return

        cr = ctx.constraint_result
        is_power = cr.is_power_loading_mode if cr else True

        # Equations
        if ctx.include_equations:
            rb.add_heading("Sizing Equations", level=2)
            ref = "Sadraey §2.9" if ctx.include_sadraey_refs else ""
            rb.add_equation(
                "S = W_TO / (W/S)_d",
                eq_number="2.49",
                reference=ref,
            )
            if is_power:
                rb.add_equation(
                    "P = W_TO / (W/P)_d",
                    eq_number="2.50",
                    reference=ref,
                )
            else:
                rb.add_equation(
                    "T = (T/W)_d · W_TO",
                    eq_number="2.51",
                    reference=ref,
                )
            rb.add_equation(
                "b = sqrt(AR · S)",
            )
            rb.add_key_value_list([
                ("S",         "Wing reference area [m²]"),
                ("W_TO",      "Maximum takeoff weight [N] = m_TO · g"),
                ("(W/S)_d",   "Wing loading at design point [N/m²]"),
                ("(W/P)_d",   "Power loading at design point [N/W]"),
                ("(T/W)_d",   "Thrust-to-weight ratio at design point"),
                ("b",         "Wingspan [m]"),
                ("AR",        "Wing aspect ratio"),
            ])

        # Results table
        rb.add_heading("Sizing Results", level=2)

        g = 9.81
        ws  = dp.wing_loading_nm2
        wto = dp.w_to_kg
        s   = dp.wing_area_m2
        b   = dp.wingspan_m
        ar  = dp.aspect_ratio
        pwr = dp.engine_power_w
        wp  = dp.power_loading_nw

        rows = [
            ["Max Takeoff Weight (MTOW)",
             f"{wto:.3f} kg",
             f"{wto * g:.1f} N"],
            ["Wing Loading (W/S)_d",
             f"{ws:.1f} N/m²",
             f"{ws / g:.2f} kg/m²"],
            ["Power/Thrust Loading",
             f"{wp:.6f}",
             "N/W (power) or N/N (thrust)"],
            ["Wing Reference Area S",
             f"{s:.4f} m²",
             "—"],
            ["Wingspan b",
             f"{b:.3f} m",
             "—"],
            ["Aspect Ratio AR",
             f"{ar:.2f}",
             "—"],
            ["Required Engine Power/Thrust",
             f"{pwr:.1f} W" if is_power else f"{pwr:.1f} N",
             f"{pwr/1000:.3f} kW" if is_power else "—"],
        ]
        rb.add_table(
            headers=["Parameter", "Value (SI)", "Alternative / Notes"],
            rows=rows,
            caption="Primary Phase 1 sizing outputs",
        )
