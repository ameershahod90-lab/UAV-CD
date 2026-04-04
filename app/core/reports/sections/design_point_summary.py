"""Design Point Summary — order 80."""
from __future__ import annotations
from app.core.reports.base import ReportSection, ReportContext, SectionCategory
from app.core.reports.renderer import ReportBuilder


class DesignPointSummarySection(ReportSection):
    section_id    = "design_point_summary"
    title         = "Design Point & Sizing Results"
    default_order = 80
    category      = SectionCategory.ANALYSIS
    description   = "Final sizing: MTOW, wing area, wingspan, engine power/thrust"

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        rb.add_heading(self.title, level=1)
        rb.add_paragraph(
            "From the selected design point on the matching diagram, the "
            "fundamental aircraft sizing quantities are derived using the "
            "following relationships (Sadraey §2.9, Eq. 2.49–2.51)."
        )

        dp = ctx.design_point
        if dp is None:
            rb.add_note("Design point not available — run sizing first.")
            return

        cr  = ctx.constraint_result
        dc  = ctx.display_converter
        is_power = cr.is_power_loading_mode if cr else True

        # Equations
        if ctx.include_equations:
            rb.add_equation("S_ref = W_TO / (W/S)_d",
                            eq_number="2.49",
                            reference="Sadraey §2.9" if ctx.include_sadraey_refs else "")
            if is_power:
                rb.add_equation("P = W_TO / (W/P)_d",
                                eq_number="2.50",
                                reference="Sadraey §2.9" if ctx.include_sadraey_refs else "")
            else:
                rb.add_equation("T = (T/W)_d · W_TO",
                                eq_number="2.51",
                                reference="Sadraey §2.9" if ctx.include_sadraey_refs else "")

        # Results
        rb.add_heading("Sizing Results", level=2)

        ws_v,  ws_u  = dc.wing_loading(dp.wing_loading_nm2)
        wto_v, wto_u = dc.mass(dp.w_to_kg)
        s_v,   s_u   = dc.area(dp.wing_area_m2)
        b_v,   b_u   = dc.length(dp.wingspan_m)
        p_v,   p_u   = dc.power(dp.engine_power_w) if is_power else dc.force(dp.engine_power_w)
        if is_power:
            ld_v, ld_u = dc.power_loading(dp.power_loading_nw)
        else:
            ld_v, ld_u = dc.force_loading(dp.power_loading_nw)

        rows = [
            ["Max Takeoff Weight (MTOW)",   f"{wto_v:.3f} {wto_u}",
             f"{dp.w_to_kg:.3f} kg"],
            ["Wing Loading (W/S)_d",        f"{ws_v:.1f} {ws_u}",
             f"{dp.wing_loading_nm2:.1f} N/m²"],
            ["Power/Thrust Loading",        f"{ld_v:.5f} {ld_u}", "—"],
            ["Wing Reference Area S",       f"{s_v:.4f} {s_u}",
             f"{dp.wing_area_m2:.4f} m²"],
            ["Wingspan b",                  f"{b_v:.3f} {b_u}",
             f"{dp.wingspan_m:.3f} m"],
            ["Aspect Ratio AR",             f"{dp.aspect_ratio:.2f}",       "—"],
            ["Req. Engine Power / Thrust",  f"{p_v:.1f} {p_u}",             "—"],
        ]
        rb.add_table(
            headers=["Parameter", "Value (display units)", "Value (SI)"],
            rows=rows,
            caption="Primary sizing outputs",
        )
