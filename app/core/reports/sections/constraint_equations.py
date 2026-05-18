"""Constraint Equations — order 65."""
from __future__ import annotations
from app.core.reports.base import ReportSection, ReportContext, SectionCategory
from app.core.reports.renderer import ReportBuilder


class ConstraintEquationsSection(ReportSection):
    section_id    = "constraint_equations"
    title         = "Constraint Analysis — Equations"
    default_order = 65
    category      = SectionCategory.ANALYSIS
    description   = "Sadraey Sec. 2.9 constraint equations (Eq. 2.38-2.46)"

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        if not ctx.include_equations:
            return

        t = ctx.t
        rb.add_heading(t("section.constraint_equations.title"), level=1)
        is_jet = not ctx.brief.propulsion_type.is_power_mode

        if ctx.include_sadraey_refs:
            rb.add_paragraph(t("section.constraint_equations.intro.with_refs"))
        else:
            rb.add_paragraph(t("section.constraint_equations.intro"))

        # Stall
        rb.add_heading(t("section.constraint_equations.heading.stall"), level=2)
        rb.add_equation(
            r"(W/S)_{V_s} = \tfrac{1}{2}\,\rho_0\,V_s^{2}\,C_{L_{\max}}"
        )

        # Max speed
        rb.add_heading(
            t("section.constraint_equations.heading.max_speed"), level=2,
        )
        if is_jet:
            rb.add_equation(
                r"T/W = \frac{q\,C_{D_0}}{W/S} + \frac{k(W/S)}{q}"
            )
            rb.add_paragraph(
                t("section.constraint_equations.max_speed.q_note"),
                italic=True, indent=True,
            )
        else:
            rb.add_equation(
                r"W/P = \frac{\eta_p}{\tfrac{1}{2}\rho_0 \sigma V_{\max}^{3}\,C_{D_0}/(W/S) + 2k(W/S)/(\rho_0 \sigma V_{\max})}"
            )

        # Takeoff
        rb.add_heading(
            t("section.constraint_equations.heading.takeoff"), level=2,
        )
        rb.add_equation(
            r"\chi = \exp\!\left(-\frac{0.6\,\rho\,g\,C_{DG}\,S_{TO}}{W/S}\right)"
        )
        rb.add_equation(r"C_{DG} = C_{D_0} - \mu\,C_{LR}")
        if is_jet:
            rb.add_equation(
                r"T/W = \frac{\mu - (\mu + C_{DG}/C_{LR})\chi}{1 - \chi}"
            )
        else:
            rb.add_equation(
                r"W/P = \frac{\eta_p}{V_{TO}} \cdot \frac{1 - \chi}{\mu(1 - \chi) - (C_{DG}/C_{LR})\chi}"
            )

        # Rate of climb
        rb.add_heading(t("section.constraint_equations.heading.roc"), level=2)
        if is_jet:
            rb.add_equation(
                r"T/W = \frac{ROC}{V_{md}} + \frac{1}{(L/D)_{\max}}"
            )
            rb.add_equation(
                r"V_{md} = \sqrt{\frac{2(W/S)}{\rho\sqrt{C_{D_0}/k}}}"
            )
        else:
            rb.add_equation(
                r"W/P = \frac{1}{ROC/\eta_p + V_{mp}\,(1.155)/((L/D)_{\max}\,\eta_p)}"
            )
            rb.add_equation(
                r"V_{mp} = \sqrt{\frac{2(W/S)}{\rho\sqrt{3\,C_{D_0}/k}}}"
            )

        # Ceiling
        rb.add_heading(
            t("section.constraint_equations.heading.ceiling"), level=2,
        )
        rb.add_paragraph(
            t("section.constraint_equations.ceiling.note"),
            italic=True, indent=True,
        )
        if is_jet:
            rb.add_equation(
                r"T_{SL}/W = \frac{ROC_C}{\sigma_C\,V_{md,C}} + \frac{1}{\sigma_C\,(L/D)_{\max}}"
            )
        else:
            rb.add_equation(
                r"W/P_{SL} = \frac{\sigma_C}{ROC_C/\eta_p + V_{mp,C}\,(1.155)/((L/D)_{\max}\,\eta_p)}"
            )

        # Wing and engine sizing
        rb.add_heading(
            t("section.constraint_equations.heading.wing_engine"), level=2,
        )
        rb.add_equation(r"S_{ref} = \frac{W_{TO}}{(W/S)_{d}}")
        if is_jet:
            rb.add_equation(r"T = (T/W)_{d} \cdot W_{TO}")
        else:
            rb.add_equation(r"P = \frac{W_{TO}}{(W/P)_{d}}")
