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
        intro = (
            "From the selected design point on the matching diagram, the "
            "fundamental aircraft sizing quantities — wing reference area "
            "{{{S}}}, wingspan {{{b}}}, and required engine power or thrust "
            "— are derived using the following relationships"
        )
        if ctx.include_sadraey_refs:
            intro += " (Sadraey 2020, Sec. 2.9, Eq. 2.49-2.51)"
        intro += "."
        rb.add_paragraph(intro)

        dp = ctx.design_point
        if dp is None:
            rb.add_note("Design point not available — run sizing first.")
            return

        cr = ctx.constraint_result
        is_power = cr.is_power_loading_mode if cr else True
        dc = ctx.display_converter

        # Equations — only the one relevant to the propulsion loading mode
        if ctx.include_equations:
            rb.add_heading("Sizing Equations", level=2)
            rb.add_equation(r"S = \frac{W_{TO}}{(W/S)_{d}}")
            if is_power:
                rb.add_equation(r"P = \frac{W_{TO}}{(W/P)_{d}}")
            else:
                rb.add_equation(r"T = (T/W)_{d} \cdot W_{TO}")
            rb.add_equation(r"b = \sqrt{AR \cdot S}")

            # Variable definitions — show only the loading row that applies
            var_defs: list[tuple[str, str]] = [
                ("S",       "Wing reference area"),
                ("W_TO",    "Maximum takeoff weight (= m_TO · g)"),
                ("(W/S)_d", "Wing loading at design point"),
            ]
            if is_power:
                var_defs.append(("(W/P)_d", "Power loading at design point"))
            else:
                var_defs.append(("(T/W)_d", "Thrust-to-weight ratio at design point"))
            var_defs.extend([
                ("b",  "Wingspan"),
                ("AR", "Wing aspect ratio"),
            ])
            rb.add_key_value_list(var_defs)

        # Results table — values in user's display units; no SI / alternative column
        rb.add_heading("Sizing Results", level=2)

        wto_v, wto_u = dc.mass(dp.w_to_kg)
        ws_v,  ws_u  = dc.wing_loading(dp.wing_loading_nm2)
        s_v,   s_u   = dc.area(dp.wing_area_m2)
        b_v,   b_u   = dc.length(dp.wingspan_m)

        if is_power:
            ld_v, ld_u = dc.power_loading(dp.power_loading_nw)
            ld_label   = "Power Loading (W/P)"
            pwr_v, pwr_u = dc.power(dp.engine_power_w)
            pwr_label  = "Required Engine Power"
        else:
            ld_v, ld_u = dc.force_loading(dp.power_loading_nw)
            ld_label   = "Thrust-to-Weight Ratio (T/W)"
            pwr_v, pwr_u = dc.force(dp.engine_power_w)
            pwr_label  = "Required Engine Thrust"

        rows = [
            ["Max Takeoff Weight (MTOW)", f"{wto_v:.3f} {wto_u}"],
            ["Wing Loading (W/S)",        f"{ws_v:.2f} {ws_u}"],
            [ld_label,                    f"{ld_v:.5f} {ld_u}"],
            ["Wing Reference Area (S)",   f"{s_v:.4f} {s_u}"],
            ["Wingspan (b)",              f"{b_v:.3f} {b_u}"],
            ["Aspect Ratio (AR)",         f"{dp.aspect_ratio:.2f}"],
            [pwr_label,                   f"{pwr_v:.2f} {pwr_u}"],
        ]
        rb.add_table(
            headers=["Parameter", "Value"],
            rows=rows,
            caption="Primary Phase 1 sizing outputs",
        )
