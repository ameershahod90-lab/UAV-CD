"""Appendix: References — order 110."""
from __future__ import annotations
from app.core.reports.base import ReportSection, ReportContext, SectionCategory
from app.core.reports.renderer import ReportBuilder


class AppendixReferencesSection(ReportSection):
    section_id    = "appendix_references"
    title         = "Appendix B: References"
    default_order = 110
    category      = SectionCategory.APPENDIX
    description   = "Bibliography: Sadraey textbook and other cited sources"

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        t = ctx.t
        # Section title — translated. The numerical "B" stays in Latin
        # script because it's a cross-reference identifier.
        rb.add_heading(t("section.appendix_references.title"), level=1)
        rb.add_paragraph(t("section.appendix_references.intro"))
        rb.add_bulleted_list([
            t("section.appendix_references.ref.sadraey"),
            t("section.appendix_references.ref.keane"),
            t("section.appendix_references.ref.dsto"),
        ])
        rb.add_heading(t("section.appendix_references.heading.tooling"), level=2)
        rb.add_paragraph(t("section.appendix_references.tooling.note"))
