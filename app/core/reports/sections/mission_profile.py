"""Mission Profile Diagram — order 40."""
from __future__ import annotations
from app.core.reports.base import ReportSection, ReportContext, SectionCategory
from app.core.reports.renderer import ReportBuilder


class MissionProfileSection(ReportSection):
    section_id    = "mission_profile"
    title         = "Mission Profile"
    default_order = 40
    category      = SectionCategory.ANALYSIS
    description   = "Mission altitude profile diagram and segment timeline"

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        t = ctx.t
        rb.add_heading(t("section.mission_profile.title"), level=1)
        rb.add_paragraph(t("section.mission_profile.intro"))

        if ctx.mission_profile_png:
            rb.add_figure(
                ctx.mission_profile_png,
                caption=t("section.mission_profile.figure_caption"),
                width_cm=15.0,
            )
        else:
            rb.add_note(t("section.mission_profile.no_diagram_note"))

        rb.add_paragraph(t("section.mission_profile.methodology"))
