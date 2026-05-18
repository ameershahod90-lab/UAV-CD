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
        "All Sadraey Sec. 2.6-2.7 equations: Breguet range/endurance, "
        "fixed-segment fractions, electric energy budget, empty-weight "
        "fraction, (L/D)max, CL*"
    )

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        if not ctx.include_equations:
            return

        t = ctx.t
        rb.add_heading(t("section.weight_equations.title"), level=1)

        if ctx.include_sadraey_refs:
            rb.add_paragraph(t("section.weight_equations.intro.with_refs"))
        else:
            rb.add_paragraph(t("section.weight_equations.intro"))

        b = ctx.brief

        # ── MTOW convergence loop ─────────────────────────────────────────
        rb.add_heading(
            t("section.weight_equations.heading.mtow_identity"), level=2,
        )
        rb.add_equation(
            r"W_{TO} = \frac{W_{payload}}{1 - W_E/W_{TO} - W_F/W_{TO}}"
        )
        rb.add_key_value_list([
            ("$${W_{TO}}$$",       t("var.w_to.full")),
            ("$${W_{payload}}$$",  t("var.w_payload.full")),
            ("$${W_E / W_{TO}}$$", t("var.we_wto")),
            ("$${W_F / W_{TO}}$$", t("var.wf_wto")),
        ])

        # ── Empty weight fraction ─────────────────────────────────────────
        rb.add_heading(
            t("section.weight_equations.heading.empty_fraction"), level=2,
        )
        rb.add_paragraph(t("section.weight_equations.empty_intro"))
        rb.add_equation(r"\frac{W_E}{W_{TO}} = a \cdot W_{TO}^{\,b}")
        rb.add_key_value_list([("$${a, b}$$", t("var.a_b"))])

        # ── Mission fraction product ──────────────────────────────────────
        rb.add_heading(
            t("section.weight_equations.heading.mission_fraction"), level=2,
        )
        rb.add_equation(
            r"\frac{W_{final}}{W_{initial}} = \prod_{i} \frac{W_i}{W_{i-1}}"
        )
        rb.add_equation(
            r"\frac{W_F}{W_{TO}} = 1 - \frac{W_{final}}{W_{initial}}"
        )

        # ── Maximum aerodynamic efficiency ────────────────────────────────
        rb.add_heading(
            t("section.weight_equations.heading.aero_efficiency"), level=2,
        )
        rb.add_equation(r"k = \frac{1}{\pi\,e\,AR}")
        rb.add_equation(r"C_L^{*} = \sqrt{\frac{C_{D_0}}{k}}")
        rb.add_equation(r"(L/D)_{\max} = \frac{1}{2\sqrt{C_{D_0}\,k}}")
        rb.add_key_value_list([
            ("$${C_{D_0}}$$",  t("var.c_d0")),
            ("$${k}$$",        t("var.k")),
            ("$${e}$$",        t("var.e")),
            ("$${AR}$$",       t("var.ar")),
            ("$${C_L^{*}}$$",  t("var.cl_star")),
        ])

        # ── Fixed segments ────────────────────────────────────────────────
        rb.add_heading(
            t("section.weight_equations.heading.fixed_segments"), level=2,
        )
        rb.add_paragraph(t("section.weight_equations.fixed_intro"))
        rb.add_table(
            headers=[
                t("section.weight_breakdown.col.segment"),
                t("section.weight_equations.col.typical_fraction"),
            ],
            rows=[
                [t("wq.fixed.engine_start"), "0.990"],
                [t("wq.fixed.taxi"),         "0.990"],
                [t("wq.fixed.takeoff"),      "0.995"],
                [t("wq.fixed.climb"),        "0.980"],
                [t("wq.fixed.descent"),      "0.990"],
                [t("wq.fixed.landing"),      "0.995"],
            ],
            caption=t("section.weight_equations.table.fixed_caption"),
        )

        is_fuel = b.propulsion_type.uses_fuel
        is_elec = not b.propulsion_type.uses_fuel

        if is_fuel:
            # Fuel-based propulsion
            rb.add_heading(
                t("section.weight_equations.heading.cruise_breguet"), level=2,
            )
            rb.add_equation(
                r"\frac{W_i}{W_{i-1}} = \exp\!\left(-\frac{R \cdot SFC \cdot g}{\eta_p \cdot V \cdot (L/D)}\right)"
            )
            rb.add_key_value_list([
                ("$${R}$$",       t("var.r_range")),
                ("$${SFC}$$",     t("var.sfc")),
                ("$${g}$$",       t("var.g")),
                ("$${\\eta_p}$$", t("var.eta_p")),
                ("$${V}$$",       t("var.v_cruise")),
                ("$${L/D}$$",     t("var.l_d")),
            ])

            rb.add_heading(
                t("section.weight_equations.heading.loiter_breguet"), level=2,
            )
            rb.add_equation(
                r"\frac{W_i}{W_{i-1}} = \exp\!\left(-\frac{E \cdot SFC \cdot g}{\eta_p \cdot (L/D)}\right)"
            )
            rb.add_key_value_list([("$${E}$$", t("var.e_endurance"))])

        if is_elec:
            rb.add_heading(
                t("section.weight_equations.heading.electric_budget"), level=2,
            )
            rb.add_paragraph(t("section.weight_equations.electric_intro"))
            rb.add_equation(
                r"P_{avg} = \frac{W_{TO} \cdot g}{\eta_p \cdot (L/D)} \cdot V"
            )
            rb.add_equation(r"E_{seg} = P_{avg} \cdot t_{seg}")
            rb.add_equation(r"E_{total} = \sum_{i} E_{seg,i}")
            rb.add_equation(
                r"W_{battery} = \frac{E_{total}}{\eta_{bat} \cdot e_{bat} \cdot 3600}"
            )
            rb.add_key_value_list([
                ("$${P_{avg}}$$",      t("var.p_avg")),
                ("$${t_{seg}}$$",      t("var.t_seg")),
                ("$${E_{total}}$$",    t("var.e_total")),
                ("$${\\eta_{bat}}$$",  t("var.eta_bat")),
                ("$${e_{bat}}$$",      t("var.e_bat")),
            ])

        if b.propulsion_type is PropulsionType.HYBRID:
            rb.add_heading(
                t("section.weight_equations.heading.hybrid"), level=2,
            )
            rb.add_paragraph(t("section.weight_equations.hybrid_intro"))
