"""Constraint Status — order 70."""
from __future__ import annotations
from app.core.reports.base import ReportSection, ReportContext, SectionCategory
from app.core.reports.renderer import ReportBuilder


class ConstraintStatusSection(ReportSection):
    section_id    = "constraint_status"
    title         = "Constraint Status"
    default_order = 70
    category      = SectionCategory.ANALYSIS
    description   = "Feasible/violated status of each constraint at the design point"

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        t = ctx.t
        rb.add_heading(t("section.constraint_status.title"), level=1)

        dp = ctx.design_point
        cr = ctx.constraint_result

        if dp is None or cr is None:
            rb.add_note(t("section.constraint_status.note.no_result"))
            return

        violations = dp.violated_constraints   # tuple[ConstraintViolation, ...]

        if violations:
            rb.add_paragraph(
                t("section.constraint_status.banner.violations",
                  count=len(violations)),
                bold=True,
            )
            viol_rows = []
            for v in violations:
                viol_rows.append([
                    # Constraint names are domain identifiers (Max Speed,
                    # Takeoff Run, etc.); they currently come from the analyser
                    # in English. A follow-up will move them through ctx.t too.
                    v.constraint_name,
                    t("status.fail"),
                    v.description[:120] if v.description else "—",
                    f"{v.current_value:.3f} {v.unit}",
                    f"{v.limit_value:.3f} {v.unit}",
                ])
            rb.add_table(
                headers=[
                    t("section.constraint_status.col.constraint"),
                    t("section.constraint_status.col.status"),
                    t("section.constraint_status.col.details"),
                    t("section.constraint_status.col.current"),
                    t("section.constraint_status.col.limit"),
                ],
                rows=viol_rows,
                caption=t("section.constraint_status.table.violations_caption"),
            )
        else:
            rb.add_paragraph(t("section.constraint_status.banner.pass"), bold=True)

        # Per-constraint summary table
        rb.add_heading(t("section.constraint_status.heading.summary"), level=2)
        violated_names = {v.constraint_name for v in violations}

        status_rows = [
            ["Stall",
             t("status.fail") if "Stall" in violated_names else t("status.pass"),
             t("section.constraint_status.notes.stall_limit",
               limit=cr.stall_ws_nm2)],
        ]
        for curve in cr.curves:
            status_rows.append([
                curve.name,
                t("status.fail") if curve.name in violated_names else t("status.pass"),
                t("section.constraint_status.notes.see_diagram"),
            ])

        rb.add_table(
            headers=[
                t("section.constraint_status.col.constraint"),
                t("section.constraint_status.col.status"),
                t("section.constraint_status.col.notes"),
            ],
            rows=status_rows,
            caption=t("section.constraint_status.table.summary_caption"),
        )
