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
        t = ctx.t
        rb.add_heading(t("section.sanity_checks.title"), level=1)
        rb.add_paragraph(t("section.sanity_checks.intro"))

        dp = ctx.design_point
        if dp is None or not dp.sanity_checks:
            rb.add_note(t("section.sanity_checks.no_result_note"))
            return

        # Status labels translate per language; the icon (✓/⚠/✗) stays the same.
        icons = {
            SanityCheckStatus.PASS: t("status.icon_pass"),
            SanityCheckStatus.WARN: t("status.icon_warn"),
            SanityCheckStatus.FAIL: t("status.icon_fail"),
        }

        rows = []
        for sc in dp.sanity_checks:
            # parameter_name is a domain identifier produced by the engine —
            # carried through unchanged until/unless we add catalogue entries
            # for each scaling-law variable.
            rows.append([
                sc.parameter_name,
                f"{sc.computed_value:.3f} {sc.unit}",
                f"{sc.expected_value:.3f} {sc.unit}",
                f"{sc.band_low:.3f} – {sc.band_high:.3f}",
                icons.get(sc.status, "?"),
            ])

        rb.add_table(
            headers=[
                t("col.parameter"),
                t("section.sanity_checks.col.computed"),
                t("section.sanity_checks.col.expected"),
                t("section.sanity_checks.col.band"),
                t("col.status"),
            ],
            rows=rows,
            caption=t("section.sanity_checks.table.caption"),
        )

        rb.add_note(t("section.sanity_checks.disclaimer"))
