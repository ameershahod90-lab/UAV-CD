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
        rb.add_heading(self.title, level=1)
        rb.add_bulleted_list([
            "Sadraey, M. H. (2020). Design of Unmanned Aerial Systems. "
            "Aerospace Series. Wiley & Sons. ISBN 978-1-119-50862-5.",

            "DSTO UAV Database — Historical scaling laws for fixed-wing UAVs, "
            "used for regression coefficients and sanity checks.",

            "UAV-CD-APP — UAV Conceptual Design Application. "
            f"Design report generated on {ctx.date_str}.",
        ])
