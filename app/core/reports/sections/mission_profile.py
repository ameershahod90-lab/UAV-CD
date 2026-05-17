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
        rb.add_heading(self.title, level=1)
        rb.add_paragraph(
            "The mission profile defines the sequence of flight phases from "
            "takeoff to landing.  Each segment contributes to the total weight "
            "fraction and energy budget of the aircraft."
        )

        if ctx.mission_profile_png:
            rb.add_figure(
                ctx.mission_profile_png,
                caption="Mission altitude profile — altitude vs. cumulative range/time",
                width_cm=15.0,
            )
        else:
            rb.add_note("Mission profile diagram not available — run sizing first.")

        rb.add_paragraph(
            "The sizing methodology follows Sadraey 2020, Sec. 2.6-2.7, where "
            "each segment contributes a weight fraction $${W_i/W_{i-1}}$$ to the "
            "overall MTOW buildup. Fixed segments use tabulated fractions "
            "(Table 2.4); cruise and loiter segments use the Breguet "
            "range/endurance equations."
        )
