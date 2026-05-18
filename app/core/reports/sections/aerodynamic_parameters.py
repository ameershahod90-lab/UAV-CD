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
        t = ctx.t
        rb.add_heading(t("section.aero_params.title"), level=1)

        b  = ctx.brief
        wr = ctx.weight_result
        rb.add_paragraph(t("section.aero_params.intro"))

        # Derived values
        k       = 1.0 / (math.pi * b.oswald_efficiency * b.aspect_ratio)
        ld_max  = 1.0 / (2.0 * math.sqrt(b.c_d0 * k)) if b.c_d0 * k > 1e-12 else 0.0
        cl_star = math.sqrt(b.c_d0 / k) if k > 1e-12 else 0.0

        rb.add_key_value_list([
            (t("ap.row.c_d0"),            f"{b.c_d0:.4f}"),
            (t("ap.row.c_l_max"),         f"{b.c_l_max:.3f}"),
            (t("ap.row.ar"),              f"{b.aspect_ratio:.2f}"),
            (t("ap.row.oswald"),          f"{b.oswald_efficiency:.3f}"),
            (t("ap.row.k"),               f"{k:.5f}"),
            (t("ap.row.cl_star"),         f"{cl_star:.4f}"),
            (t("ap.row.ld_max"),          f"{ld_max:.2f}"),
            (t("ap.row.prop_efficiency"), f"{b.prop_efficiency:.2f}"),
        ])

        if wr is not None:
            rb.add_paragraph(t("section.aero_params.engine_intro"), italic=True)
            rb.add_key_value_list([
                (t("ap.row.cl_star_engine"), f"{wr.cl_cruise:.4f}"),
                (t("ap.row.ld_max_engine"),  f"{wr.ld_max:.2f}"),
            ])
