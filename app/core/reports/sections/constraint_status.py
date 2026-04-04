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
        rb.add_heading(self.title, level=1)

        dp = ctx.design_point
        cr = ctx.constraint_result

        if dp is None or cr is None:
            rb.add_note("Constraint analysis not available — run sizing first.")
            return

        violations = dp.violated_constraints   # tuple[ConstraintViolation, ...]

        if violations:
            rb.add_paragraph(
                f"WARNING:  The selected design point violates "
                f"{len(violations)} constraint(s).  Review the matching diagram "
                f"and adjust the design point or mission requirements.",
                bold=True,
            )
            viol_rows = []
            for v in violations:
                viol_rows.append([
                    v.constraint_name,
                    "VIOLATED",
                    v.description[:120] if v.description else "—",
                    f"{v.current_value:.3f} {v.unit}",
                    f"{v.limit_value:.3f} {v.unit}",
                ])
            rb.add_table(
                headers=["Constraint", "Status", "Details", "Current", "Limit"],
                rows=viol_rows,
                caption="Constraint violations at selected design point",
            )
        else:
            rb.add_paragraph(
                "PASS:  The selected design point satisfies all performance "
                "constraints.  The design is within the feasible region of "
                "the matching diagram.",
                bold=True,
            )

        # Per-constraint summary table
        rb.add_heading("Per-Constraint Summary", level=2)
        violated_names = {v.constraint_name for v in violations}

        status_rows = [
            ["Stall", "FAIL" if "Stall" in violated_names else "PASS",
             f"W/S limit = {cr.stall_ws_nm2:.1f} N/m²"],
        ]
        for curve in cr.curves:
            status_rows.append([
                curve.name,
                "FAIL" if curve.name in violated_names else "PASS",
                "See matching diagram",
            ])

        rb.add_table(
            headers=["Constraint", "Status", "Notes"],
            rows=status_rows,
            caption="Constraint check summary at design point",
        )
