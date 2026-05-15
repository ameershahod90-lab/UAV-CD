"""Weight Equations — order 55.

Shows every equation used in the weight estimation pipeline.
Gated on ctx.include_equations so user can toggle with the
'Include equation blocks' checkbox in the export dialog.
"""
from __future__ import annotations

from app.core.enums import PropulsionType
from app.core.reports.base import ReportSection, ReportContext, SectionCategory
from app.core.reports.renderer import ReportBuilder


class WeightEquationsSection(ReportSection):
    section_id    = "weight_equations"
    title         = "Weight Estimation — Equations"
    default_order = 55
    category      = SectionCategory.ANALYSIS
    description   = (
        "All Sadraey §2.6-2.7 equations: Breguet range/endurance, fixed-segment "
        "fractions, electric energy budget, empty-weight fraction, (L/D)max, CL*"
    )

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        if not ctx.include_equations:
            return

        rb.add_heading(self.title, level=1)
        rb.add_paragraph(
            "The weight estimation follows the mission fraction method "
            "(Sadraey §2.6-2.7).  The MTOW is found by iterating on the "
            "equation below until two successive estimates agree to within "
            "0.1 g."
        )

        ref   = "Sadraey §2.6" if ctx.include_sadraey_refs else ""
        ref27 = "Sadraey §2.7" if ctx.include_sadraey_refs else ""
        ref24 = "Sadraey §2.4" if ctx.include_sadraey_refs else ""
        b     = ctx.brief

        # ── MTOW convergence loop ─────────────────────────────────────────
        rb.add_heading("1.  MTOW Convergence Identity", level=2)
        rb.add_equation(
            "W_TO = W_payload / (1 - W_E/W_TO - W_F/W_TO)",
            reference=ref,
        )
        rb.add_key_value_list([
            ("W_TO",        "Maximum takeoff weight [kg]"),
            ("W_payload",   "Payload mass [kg]"),
            ("W_E / W_TO",  "Empty-weight fraction (from historical regression)"),
            ("W_F / W_TO",  "Fuel or battery fraction (from mission fractions)"),
        ])

        # ── Empty weight fraction ─────────────────────────────────────────
        rb.add_heading("2.  Empty-Weight Fraction (Regression)", level=2)
        rb.add_paragraph(
            "The empty-weight fraction is obtained from a power-law regression "
            "fitted to the UAV historical database (Sadraey Table 2.4):"
        )
        rb.add_equation(
            "W_E / W_TO = a · W_TO^b",
            reference=ref,
        )
        rb.add_key_value_list([
            ("a, b", "Regression coefficients (propulsion-class specific)"),
        ])

        # ── Mission fraction product ──────────────────────────────────────
        rb.add_heading("3.  Mission Weight Fraction", level=2)
        rb.add_equation(
            "W_final / W_initial = product(Wi/Wi-1) for all enabled segments",
            reference=ref,
        )
        rb.add_equation(
            "W_F / W_TO = 1 - W_final / W_initial",
            reference=ref,
        )

        # ── Maximum aerodynamic efficiency ────────────────────────────────
        rb.add_heading("4.  Aerodynamic Efficiency", level=2)
        rb.add_equation(
            "k = 1 / (pi · e · AR)",
            reference=ref24,
        )
        rb.add_equation(
            "CL* = sqrt(CD0 / k)",
            reference=ref24,
        )
        rb.add_equation(
            "(L/D)max = 1 / (2 · sqrt(CD0 · k))",
            reference=ref24,
        )
        rb.add_key_value_list([
            ("CD0",  "Zero-lift (parasitic) drag coefficient"),
            ("k",    "Induced drag factor"),
            ("e",    "Oswald span efficiency factor"),
            ("AR",   "Wing aspect ratio"),
            ("CL*",  "Lift coefficient at maximum L/D (best-glide speed)"),
        ])

        # ── Fixed segments ────────────────────────────────────────────────
        rb.add_heading("5.  Fixed Segment Fractions (Tabulated)", level=2)
        rb.add_paragraph(
            "Start, taxi, takeoff, climb, descent, and landing segments use "
            "tabulated fractions from Sadraey Table 2.4.  Representative values:"
        )
        rb.add_table(
            headers=["Segment", "Typical Wi/Wi-1"],
            rows=[
                ["Engine start / warm-up", "0.990"],
                ["Taxi",                   "0.990"],
                ["Takeoff",                "0.995"],
                ["Climb",                  "0.980"],
                ["Descent",                "0.990"],
                ["Landing",                "0.995"],
            ],
            caption="Sadraey Table 2.4 — fixed-segment weight fractions",
        )

        is_fuel = b.propulsion_type.uses_fuel
        is_elec = not b.propulsion_type.uses_fuel

        if is_fuel:
            # Fuel-based propulsion
            rb.add_heading("6a.  Cruise Segment — Breguet Range Equation", level=2)
            rb.add_equation(
                "Wi/Wi-1 = exp( -(R · SFC · g) / (eta_p · V · (L/D)) )",
                eq_number="2.17",
                reference=ref,
            )
            rb.add_key_value_list([
                ("R",      "Cruise range [m]"),
                ("SFC",    "Specific fuel consumption [kg/(N·s)]"),
                ("g",      "Gravitational acceleration [9.81 m/s²]"),
                ("eta_p",  "Propulsive efficiency (prop) or 1.0 (jet)"),
                ("V",      "Cruise airspeed [m/s]"),
                ("L/D",    "Lift-to-drag ratio at cruise"),
            ])

            rb.add_heading("6b.  Loiter Segment — Breguet Endurance Equation", level=2)
            rb.add_equation(
                "Wi/Wi-1 = exp( -(E · SFC · g) / (eta_p · (L/D)) )",
                eq_number="2.18",
                reference=ref,
            )
            rb.add_key_value_list([
                ("E",      "Loiter endurance [s]"),
            ])

        if is_elec:
            rb.add_heading("6.  Electric Energy Budget", level=2)
            rb.add_paragraph(
                "For electric UAVs the weight fraction is replaced by a "
                "battery mass calculation based on energy consumption:"
            )
            rb.add_equation(
                "P_avg = (W_TO · g) / (eta_p · (L/D)) · V",
            )
            rb.add_equation(
                "E_seg = P_avg · t_seg",
                eq_number="2.25",
                reference=ref27,
            )
            rb.add_equation(
                "E_total = sum(E_seg) for all enabled segments",
            )
            rb.add_equation(
                "W_battery = E_total / (eta_bat · e_bat · 3600)",
            )
            rb.add_key_value_list([
                ("P_avg",    "Average power required [W]"),
                ("t_seg",    "Duration of segment [s]"),
                ("E_total",  "Total electrical energy [J]"),
                ("eta_bat",  "Battery charge/discharge efficiency"),
                ("e_bat",    "Battery specific energy density [Wh/kg]"),
            ])

        if b.propulsion_type is PropulsionType.HYBRID:
            rb.add_heading("6.  Hybrid Propulsion — Mixed Fractions", level=2)
            rb.add_paragraph(
                "Each segment uses either the Breguet fuel fraction or the "
                "electric energy budget depending on the segment's assigned "
                "energy source.  The overall mass budget combines both "
                "fuel and battery contributions."
            )
