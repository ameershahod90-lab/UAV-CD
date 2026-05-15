"""Sanity Checks — order 90."""
from __future__ import annotations
from app.core.reports.base import ReportSection, ReportContext, SectionCategory
from app.core.reports.renderer import ReportBuilder
from app.core.enums import SanityCheckStatus


class SanityChecksSection(ReportSection):
    section_id    = "sanity_checks"
    title         = "Scaling-Law Sanity Checks"
    default_order = 90
    category      = SectionCategory.ANALYSIS
    description   = "Historical scaling-law comparison (wingspan, wing area, etc.)"

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        rb.add_heading(self.title, level=1)
        rb.add_paragraph(
            "The computed geometry is compared against historical scaling laws "
            "derived from the DSTO UAV database.  These checks flag outliers "
            "that may indicate an impractical design."
        )

        dp = ctx.design_point
        if dp is None or not dp.sanity_checks:
            rb.add_note("Sanity checks not available — run sizing first.")
            return

        _ICONS = {
            SanityCheckStatus.PASS:    "✓  PASS",
            SanityCheckStatus.WARN: "⚠  WARN",
            SanityCheckStatus.FAIL:    "✗  FAIL",
        }

        rows = []
        for sc in dp.sanity_checks:
            rows.append([
                sc.parameter_name,
                f"{sc.computed_value:.3f} {sc.unit}",
                f"{sc.expected_value:.3f} {sc.unit}",
                f"{sc.band_low:.3f} – {sc.band_high:.3f}",
                _ICONS.get(sc.status, "?"),
            ])

        rb.add_table(
            headers=["Parameter", "Computed", "Expected", "Acceptable Band", "Status"],
            rows=rows,
            caption="Historical scaling-law sanity checks",
        )

        rb.add_note(
            "DSTO scaling law data is currently limited. "
            "Warnings and failures may reflect sparse historical data "
            "rather than a design error."
        )
