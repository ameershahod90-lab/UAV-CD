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
        rb.add_heading(self.title, level=1)
        rb.add_paragraph(
            "The matching diagram maps all performance constraints onto a "
            "single plot of Wing Loading (W/S) vs Power Loading (W/P) or "
            "Thrust Loading (T/W).  The feasible design region is bounded by "
            "the constraint envelope; the design point is selected from within "
            "this region — ideally at the intersection that maximises W/S and "
            "W/P to minimise wing area and engine size."
        )

        cr = ctx.constraint_result
        dp = ctx.design_point
        dc = ctx.display_converter

        if ctx.matching_diagram_png:
            rb.add_figure(
                ctx.matching_diagram_png,
                caption="Matching diagram — performance constraint boundaries "
                        "and selected design point (★)",
                width_cm=15.0,
            )
        else:
            rb.add_note(
                "Matching diagram not available — run constraint analysis first."
            )

        if cr is not None:
            rb.add_heading("Constraint Boundaries", level=2)
            rb.add_paragraph(
                f"Stall limit (vertical line): W/S = "
                f"{cr.stall_ws_nm2:.1f} N/m²"
            )
            rows = []
            for curve in cr.curves:
                rows.append([curve.name, "See matching diagram"])
            rb.add_table(
                headers=["Constraint", "Source"],
                rows=rows,
                caption="Active constraint boundaries (Sadraey §2.9)",
            )

        if dp is not None:
            rb.add_heading("Selected Design Point Coordinates", level=2)
            ws_v, ws_u = dc.wing_loading(dp.wing_loading_nm2)
            is_power = cr.is_power_loading_mode if cr else True
            if is_power:
                ld_v, ld_u = dc.power_loading(dp.power_loading_nw)
            else:
                ld_v, ld_u = dc.force_loading(dp.power_loading_nw)

            rb.add_key_value_list([
                ("Wing Loading (W/S)",
                 f"{ws_v:.1f} {ws_u}  |  {dp.wing_loading_nm2:.1f} N/m²"),
                ("Loading (W/P or T/W)",
                 f"{ld_v:.5f} {ld_u}"),
            ])
