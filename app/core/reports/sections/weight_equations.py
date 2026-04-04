"""Weight Equations — order 55."""
from __future__ import annotations
from app.core.reports.base import ReportSection, ReportContext, SectionCategory
from app.core.reports.renderer import ReportBuilder


class WeightEquationsSection(ReportSection):
    section_id    = "weight_equations"
    title         = "Weight Estimation — Equations"
    default_order = 55
    category      = SectionCategory.ANALYSIS
    description   = "Sadraey §2.6-2.7 Breguet equations and electric energy budget"

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        if not ctx.include_equations:
            return

        rb.add_heading(self.title, level=1)
        rb.add_paragraph(
            "The weight estimation follows the mission fraction method "
            "(Sadraey §2.6-2.7).  For each segment, a weight fraction "
            "Wi/Wi₋₁ is calculated; the MTOW is found iteratively from "
            "the product of all fractions."
        )

        rb.add_heading("Fuel-Based Propulsion (Breguet Equations)", level=2)

        rb.add_paragraph("Cruise segment — Breguet range equation:", italic=True)
        rb.add_equation(
            "Wi/Wi₋₁ = exp(−R · g · SFC / (ηₚ · (L/D)))",
            eq_number="2.17",
            reference="Sadraey §2.6" if ctx.include_sadraey_refs else "",
        )
        rb.add_key_value_list([
            ("R",    "Range [m]"),
            ("SFC",  "Specific fuel consumption [kg/(N·s)]"),
            ("ηₚ",   "Propulsive efficiency (prop) or 1.0 (jet)"),
            ("L/D",  "Lift-to-drag ratio at cruise"),
        ])

        rb.add_paragraph("Loiter segment — Breguet endurance equation:", italic=True)
        rb.add_equation(
            "Wi/Wi₋₁ = exp(−E · g · SFC / (L/D))",
            eq_number="2.18",
            reference="Sadraey §2.6" if ctx.include_sadraey_refs else "",
        )
        rb.add_key_value_list([
            ("E", "Endurance [s]"),
        ])

        rb.add_paragraph(
            "Fixed segments (takeoff, climb, descent, landing) use "
            "tabulated weight fractions from Sadraey Table 2.4."
        )

        rb.add_heading("Electric Propulsion (Energy Budget)", level=2)
        rb.add_equation(
            "E_seg = P_avg · t_seg",
            eq_number="2.25",
            reference="Sadraey §2.7" if ctx.include_sadraey_refs else "",
        )
        rb.add_equation(
            "W_battery = E_total / (η_bat · e_bat)",
        )
        rb.add_key_value_list([
            ("E_total", "Total electrical energy required [J]"),
            ("η_bat",   "Battery charge/discharge efficiency"),
            ("e_bat",   "Battery specific energy density [J/kg]"),
        ])

        rb.add_heading("Maximum Lift-to-Drag Ratio", level=2)
        rb.add_equation(
            "(L/D)max = 1 / (2 √(CD₀ · k))",
            reference="Sadraey §2.4" if ctx.include_sadraey_refs else "",
        )
        rb.add_equation(
            "CL* = √(CD₀ / k)",
            reference="Sadraey §2.4" if ctx.include_sadraey_refs else "",
        )
        rb.add_equation(
            "k = 1 / (π · e · AR)",
        )
        rb.add_key_value_list([
            ("CD₀", "Zero-lift (parasitic) drag coefficient"),
            ("k",   "Induced drag factor"),
            ("e",   "Oswald span efficiency factor"),
            ("AR",  "Wing aspect ratio"),
        ])
