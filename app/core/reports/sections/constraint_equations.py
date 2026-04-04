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
            "(W/S)_Vs = ½ · ρ₀ · Vs² · CLmax",
            eq_number="2.38", reference=ref,
        )

        # Max speed
        rb.add_heading("2. Maximum Level Speed", level=2)
        if is_jet:
            rb.add_equation(
                "T/W = q·CD₀/(W/S) + k·(W/S)/q   where q = ½ρ₀σVmax²",
                eq_number="2.39", reference=ref,
            )
        else:
            rb.add_equation(
                "W/P = ηₚ / [½ρ₀σVmax³·CD₀/(W/S) + 2k·(W/S)/(ρ₀σVmax)]",
                eq_number="2.40", reference=ref,
            )

        # Takeoff
        rb.add_heading("3. Takeoff Ground Roll", level=2)
        rb.add_paragraph(
            "Where: χ = exp(−0.6ρg·CDG·STO / (W/S))   and   "
            "CDG = CD₀ − μ·CLR",
            italic=True, indent=True,
        )
        if is_jet:
            rb.add_equation(
                "T/W = [μ − (μ + CDG/CLR)·χ] / (1 − χ)",
                eq_number="2.41", reference=ref,
            )
        else:
            rb.add_equation(
                "W/P = ηₚ/VTO · (1 − χ) / [μ·(1 − χ) − (CDG/CLR)·χ]",
                eq_number="2.42", reference=ref,
            )

        # Rate of climb
        rb.add_heading("4. Rate of Climb", level=2)
        if is_jet:
            rb.add_equation(
                "T/W = ROC/Vmd + 1/(L/D)max   where Vmd = √(2(W/S)/ρ√(CD₀/k))",
                eq_number="2.43", reference=ref,
            )
        else:
            rb.add_equation(
                "W/P = 1 / (ROC/ηₚ + Vmp·1.155/((L/D)max·ηₚ))",
                eq_number="2.44", reference=ref,
            )
            rb.add_equation("Vmp = √(2(W/S) / (ρ·√(3·CD₀/k)))")

        # Ceiling
        rb.add_heading("5. Service Ceiling", level=2)
        rb.add_paragraph(
            f"At service ceiling ROC_C = 0.508 m/s (100 ft/min); "
            f"σ_C = ρ_ceiling / ρ_SL",
            italic=True, indent=True,
        )
        if is_jet:
            rb.add_equation(
                "T_SL/W = ROC_C/(σ_C·Vmd_C) + 1/(σ_C·(L/D)max)",
                eq_number="2.45", reference=ref,
            )
        else:
            rb.add_equation(
                "W/P_SL = σ_C / (ROC_C/ηₚ + Vmp_C·1.155/((L/D)max·ηₚ))",
                eq_number="2.46", reference=ref,
            )

        # Wing and engine sizing
        rb.add_heading("Wing and Engine Sizing", level=2)
        rb.add_equation("S_ref = W_TO / (W/S)_d",   eq_number="2.49", reference=ref)
        if is_jet:
            rb.add_equation("T = (T/W)_d · W_TO",   eq_number="2.51", reference=ref)
        else:
            rb.add_equation("P = W_TO / (W/P)_d",   eq_number="2.50", reference=ref)
