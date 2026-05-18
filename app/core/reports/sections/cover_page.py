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
        t = ctx.t

        rb.add_page_break()

        if ctx.report_title:
            rb.add_heading(ctx.report_title, level=1)

        rb.add_paragraph(t("cover.subtitle"), bold=True)
        rb.add_paragraph("")

        rb.add_key_value_list([
            (t("cover.label.project"),  ctx.project_name or "—"),
            (t("cover.label.author"),   ctx.author       or "—"),
            (t("cover.label.revision"), ctx.revision     or "1.0"),
            (t("cover.label.date"),     ctx.date_str     or "—"),
        ])

        rb.add_paragraph("")
        rb.add_note(t("cover.note.auto_generated"))
        rb.add_page_break()
