"""Aerodynamic Parameters — order 85."""
from __future__ import annotations
import math
from app.core.reports.base import ReportSection, ReportContext, SectionCategory
from app.core.reports.renderer import ReportBuilder


class AerodynamicParametersSection(ReportSection):
    section_id    = "aerodynamic_parameters"
    title         = "Aerodynamic Parameters"
    default_order = 85
    category      = SectionCategory.ANALYSIS
    description   = "CD₀, k, CL*, (L/D)max, and key aerodynamic coefficients"

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        rb.add_heading(self.title, level=1)

        b  = ctx.brief
        wr = ctx.weight_result
        rb.add_paragraph(
            "Key aerodynamic parameters derived from the design brief inputs "
            "and used throughout the sizing analysis."
        )

        # Compute derived values
        k     = 1.0 / (math.pi * b.oswald_efficiency * b.aspect_ratio)
        ld_max = 1.0 / (2.0 * math.sqrt(b.c_d0 * k)) if b.c_d0 * k > 1e-12 else 0.0
        cl_star = math.sqrt(b.c_d0 / k) if k > 1e-12 else 0.0

        rb.add_key_value_list([
            ("CD₀ (zero-lift drag)",       f"{b.c_d0:.4f}"),
            ("CLmax (max lift coeff.)",    f"{b.c_l_max:.3f}"),
            ("Aspect Ratio (AR)",          f"{b.aspect_ratio:.2f}"),
            ("Oswald efficiency (e)",      f"{b.oswald_efficiency:.3f}"),
            ("Induced drag factor k",      f"{k:.5f}"),
            ("CL* (best L/D speed)",       f"{cl_star:.4f}"),
            ("(L/D)max",                   f"{ld_max:.2f}"),
            ("Propeller efficiency (ηₚ)", f"{b.prop_efficiency:.2f}"),
        ])

        if wr is not None:
            rb.add_paragraph(
                "Values from weight estimation engine:",
                italic=True,
            )
            rb.add_key_value_list([
                ("CL* (engine)",    f"{wr.cl_cruise:.4f}"),
                ("(L/D)max (engine)", f"{wr.ld_max:.2f}"),
            ])
