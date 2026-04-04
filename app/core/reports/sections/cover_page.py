"""Cover Page — order 10."""
from __future__ import annotations
from app.core.reports.base import ReportSection, ReportContext, SectionCategory
from app.core.reports.renderer import ReportBuilder


class CoverPageSection(ReportSection):
    section_id    = "cover_page"
    title         = "Cover Page"
    default_order = 10
    category      = SectionCategory.FRONT_MATTER
    description   = "Title, author, date, revision, and optional company logo"

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        rb.add_page_break()

        # Logo (if provided)
        if ctx.report_title:
            rb.add_heading(ctx.report_title, level=1)

        rb.add_paragraph("Fixed-Wing UAV Conceptual Design Study", bold=True)
        rb.add_paragraph("")

        rb.add_key_value_list([
            ("Project",  ctx.project_name or "—"),
            ("Author",   ctx.author       or "—"),
            ("Revision", ctx.revision     or "1.0"),
            ("Date",     ctx.date_str     or "—"),
        ])

        rb.add_paragraph("")
        rb.add_note(
            "This report was generated automatically by UAV-CD-APP "
            "(UAV Conceptual Design Application). All engineering calculations "
            "follow Sadraey (2020), Design of Unmanned Aerial Systems."
        )
        rb.add_page_break()
