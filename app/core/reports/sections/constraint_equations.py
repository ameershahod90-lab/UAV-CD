"""Constraint Equations — order 65."""
from __future__ import annotations
from app.core.reports.base import ReportSection, ReportContext, SectionCategory
from app.core.reports.renderer import ReportBuilder


class ConstraintEquationsSection(ReportSection):
    section_id    = "constraint_equations"
    title         = "Constraint Analysis — Equations"
    default_order = 65
    category      = SectionCategory.ANALYSIS
    description   = "Sadraey §2.9 constraint equations (Eq. 2.38–2.46)"

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        if not ctx.include_equations:
            return

        rb.add_heading(self.title, level=1)
        is_jet = not ctx.brief.propulsion_type.is_power_mode
        ref = "Sadraey §2.9" if ctx.include_sadraey_refs else ""

        rb.add_paragraph(
            "All five performance constraints are derived as functions of wing "
            "loading (W/S) and plotted on the matching diagram.  The equations "
            "below follow Sadraey (2020) §2.9."
        )

        # Stall
        rb.add_heading("1. Stall Speed Constraint", level=2)
        rb.add_equation(
            r"(W/S)_{V_s} = \tfrac{1}{2}\,\rho_0\,V_s^{2}\,C_{L_{\max}}",
            eq_number="2.38", reference=ref,
        )

        # Max speed
        rb.add_heading("2. Maximum Level Speed", level=2)
        if is_jet:
            rb.add_equation(
                r"T/W = \frac{q\,C_{D_0}}{W/S} + \frac{k(W/S)}{q}",
                eq_number="2.39", reference=ref,
            )
            rb.add_paragraph(
                "where q = ½ρ₀σVmax²", italic=True, indent=True,
            )
        else:
            rb.add_equation(
                r"W/P = \frac{\eta_p}{\tfrac{1}{2}\rho_0 \sigma V_{\max}^{3}\,C_{D_0}/(W/S) + 2k(W/S)/(\rho_0 \sigma V_{\max})}",
                eq_number="2.40", reference=ref,
            )

        # Takeoff
        rb.add_heading("3. Takeoff Ground Roll", level=2)
        rb.add_equation(
            r"\chi = \exp\!\left(-\frac{0.6\,\rho\,g\,C_{DG}\,S_{TO}}{W/S}\right)",
        )
        rb.add_equation(
            r"C_{DG} = C_{D_0} - \mu\,C_{LR}",
        )
        if is_jet:
            rb.add_equation(
                r"T/W = \frac{\mu - (\mu + C_{DG}/C_{LR})\chi}{1 - \chi}",
                eq_number="2.41", reference=ref,
            )
        else:
            rb.add_equation(
                r"W/P = \frac{\eta_p}{V_{TO}} \cdot \frac{1 - \chi}{\mu(1 - \chi) - (C_{DG}/C_{LR})\chi}",
                eq_number="2.42", reference=ref,
            )

        # Rate of climb
        rb.add_heading("4. Rate of Climb", level=2)
        if is_jet:
            rb.add_equation(
                r"T/W = \frac{ROC}{V_{md}} + \frac{1}{(L/D)_{\max}}",
                eq_number="2.43", reference=ref,
            )
            rb.add_equation(
                r"V_{md} = \sqrt{\frac{2(W/S)}{\rho\sqrt{C_{D_0}/k}}}",
            )
        else:
            rb.add_equation(
                r"W/P = \frac{1}{ROC/\eta_p + V_{mp}\,(1.155)/((L/D)_{\max}\,\eta_p)}",
                eq_number="2.44", reference=ref,
            )
            rb.add_equation(
                r"V_{mp} = \sqrt{\frac{2(W/S)}{\rho\sqrt{3\,C_{D_0}/k}}}",
            )

        # Ceiling
        rb.add_heading("5. Service Ceiling", level=2)
        rb.add_paragraph(
            "At service ceiling ROC_C = 0.508 m/s (100 ft/min); "
            "σ_C = ρ_ceiling / ρ_SL",
            italic=True, indent=True,
        )
        if is_jet:
            rb.add_equation(
                r"T_{SL}/W = \frac{ROC_C}{\sigma_C\,V_{md,C}} + \frac{1}{\sigma_C\,(L/D)_{\max}}",
                eq_number="2.45", reference=ref,
            )
        else:
            rb.add_equation(
                r"W/P_{SL} = \frac{\sigma_C}{ROC_C/\eta_p + V_{mp,C}\,(1.155)/((L/D)_{\max}\,\eta_p)}",
                eq_number="2.46", reference=ref,
            )

        # Wing and engine sizing
        rb.add_heading("Wing and Engine Sizing", level=2)
        rb.add_equation(r"S_{ref} = \frac{W_{TO}}{(W/S)_{d}}",
                        eq_number="2.49", reference=ref)
        if is_jet:
            rb.add_equation(r"T = (T/W)_{d} \cdot W_{TO}",
                            eq_number="2.51", reference=ref)
        else:
            rb.add_equation(r"P = \frac{W_{TO}}{(W/P)_{d}}",
                            eq_number="2.50", reference=ref)
