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
        t = ctx.t
        rb.add_heading(t("section.design_point_summary.title"), level=1)

        if ctx.include_sadraey_refs:
            rb.add_paragraph(t("section.design_point_summary.intro.with_refs"))
        else:
            rb.add_paragraph(t("section.design_point_summary.intro"))

        dp = ctx.design_point
        if dp is None:
            rb.add_note(t("section.design_point_summary.no_dp_note"))
            return

        cr = ctx.constraint_result
        is_power = cr.is_power_loading_mode if cr else True
        dc = ctx.display_converter

        # Equations — only the one relevant to the propulsion loading mode
        if ctx.include_equations:
            rb.add_heading(
                t("section.design_point_summary.heading.equations"), level=2,
            )
            rb.add_equation(r"S = \frac{W_{TO}}{(W/S)_{d}}")
            if is_power:
                rb.add_equation(r"P = \frac{W_{TO}}{(W/P)_{d}}")
            else:
                rb.add_equation(r"T = (T/W)_{d} \cdot W_{TO}")
            rb.add_equation(r"b = \sqrt{AR \cdot S}")

            # Variable definitions — labels stay as math IDs ($${...}$$),
            # descriptions translate.
            var_defs: list[tuple[str, str]] = [
                ("$${S}$$",       t("dp.var.s")),
                ("$${W_{TO}}$$",  t("dp.var.wto")),
                ("$${(W/S)_d}$$", t("dp.var.ws_d")),
            ]
            if is_power:
                var_defs.append(("$${(W/P)_d}$$", t("dp.var.wp_d")))
            else:
                var_defs.append(("$${(T/W)_d}$$", t("dp.var.tw_d")))
            var_defs.extend([
                ("$${b}$$",  t("dp.var.b")),
                ("$${AR}$$", t("dp.var.ar")),
            ])
            rb.add_key_value_list(var_defs)

        # Results table — values in user's display units
        rb.add_heading(
            t("section.design_point_summary.heading.results"), level=2,
        )

        wto_v, wto_u = dc.mass(dp.w_to_kg)
        ws_v,  ws_u  = dc.wing_loading(dp.wing_loading_nm2)
        s_v,   s_u   = dc.area(dp.wing_area_m2)
        b_v,   b_u   = dc.length(dp.wingspan_m)

        if is_power:
            ld_v, ld_u     = dc.power_loading(dp.power_loading_nw)
            ld_label       = t("section.design_point_summary.row.power_loading")
            pwr_v, pwr_u   = dc.power(dp.engine_power_w)
            pwr_label      = t("section.design_point_summary.row.engine_power")
        else:
            ld_v, ld_u     = dc.force_loading(dp.power_loading_nw)
            ld_label       = t("section.design_point_summary.row.thrust_loading")
            pwr_v, pwr_u   = dc.force(dp.engine_power_w)
            pwr_label      = t("section.design_point_summary.row.engine_thrust")

        rows = [
            [t("section.design_point_summary.row.mtow"),
             f"{wto_v:.3f} {wto_u}"],
            [t("section.design_point_summary.row.wing_loading"),
             f"{ws_v:.2f} {ws_u}"],
            [ld_label,                       f"{ld_v:.5f} {ld_u}"],
            [t("section.design_point_summary.row.wing_area"),
             f"{s_v:.4f} {s_u}"],
            [t("section.design_point_summary.row.wingspan"),
             f"{b_v:.3f} {b_u}"],
            [t("section.design_point_summary.row.aspect_ratio"),
             f"{dp.aspect_ratio:.2f}"],
            [pwr_label,                      f"{pwr_v:.2f} {pwr_u}"],
        ]
        rb.add_table(
            headers=[t("col.parameter"), t("col.value")],
            rows=rows,
            caption=t("section.design_point_summary.table.caption"),
        )
