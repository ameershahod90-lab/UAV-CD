"""Matching Diagram — order 60."""
from __future__ import annotations
from app.core.reports.base import ReportSection, ReportContext, SectionCategory
from app.core.reports.renderer import ReportBuilder


class MatchingDiagramSection(ReportSection):
    section_id    = "matching_diagram"
    title         = "Constraint Analysis — Matching Diagram"
    default_order = 60
    category      = SectionCategory.ANALYSIS
    description   = (
        "W/S vs W/P (or T/W) matching diagram with feasible region "
        "and design point"
    )

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        t = ctx.t
        rb.add_heading(t("section.matching_diagram.title"), level=1)

        cr = ctx.constraint_result
        dp = ctx.design_point
        dc = ctx.display_converter
        is_power = cr.is_power_loading_mode if cr else True

        # Propulsion-mode-specific intro paragraph (different translation
        # keys for the power-loading vs thrust-loading variants).
        if is_power:
            rb.add_paragraph(t("section.matching_diagram.intro_power"))
        else:
            rb.add_paragraph(t("section.matching_diagram.intro_thrust"))

        if ctx.matching_diagram_png:
            rb.add_figure(
                ctx.matching_diagram_png,
                caption=t("section.matching_diagram.figure_caption"),
                width_cm=15.0,
            )
        else:
            rb.add_note(t("section.matching_diagram.no_diagram_note"))

        if cr is not None:
            rb.add_heading(t("section.matching_diagram.heading.boundaries"), level=2)
            rb.add_paragraph(
                t("section.matching_diagram.stall_limit_paragraph",
                  ws=cr.stall_ws_nm2)
            )
            see_diagram = t("common.see_diagram")
            rows = [[curve.name, see_diagram] for curve in cr.curves]
            rb.add_table(
                headers=[
                    t("section.matching_diagram.col.constraint"),
                    t("section.matching_diagram.col.source"),
                ],
                rows=rows,
                caption=t("section.matching_diagram.table.boundaries_caption"),
            )

        if dp is not None:
            rb.add_heading(
                t("section.matching_diagram.heading.coordinates"), level=2,
            )
            ws_v, ws_u = dc.wing_loading(dp.wing_loading_nm2)
            if is_power:
                ld_v, ld_u = dc.power_loading(dp.power_loading_nw)
                ld_label = t("section.matching_diagram.label.power_loading")
            else:
                ld_v, ld_u = dc.force_loading(dp.power_loading_nw)
                ld_label = t("section.matching_diagram.label.thrust_loading")

            rb.add_key_value_list([
                (t("section.matching_diagram.label.wing_loading"),
                 f"{ws_v:.2f} {ws_u}"),
                (ld_label, f"{ld_v:.5f} {ld_u}"),
            ])
