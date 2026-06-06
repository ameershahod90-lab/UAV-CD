"""
Sensitivity Analysis — order 95.

Customisable report section that emits the user-curated subset of the
Sensitivity Studio's output: tornado figures, OAT-sweep figures,
constraint-margin table, and snowball factor table. Every choice is
captured by a ``SensitivityReportConfig`` (concrete subclass of the
``SectionConfig`` abstract base) which the export dialog populates.

Default config: tornados for the three slots configured on the live
Sensitivity tab (``settings.sens_tornado_output_ids``), no sweeps,
margins + snowball both included. The user can replace any of those
choices via the Customise dialog in the export popup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.core.entities import DesignBrief
from app.core.reports.base import (
    ReportContext,
    ReportSection,
    SectionCategory,
    SectionConfig,
)
from app.core.reports.renderer import ReportBuilder
from app.core.sensitivity import (
    OUTPUT_CATALOG,
    SWEEPABLE_PARAMETERS,
    compute_constraint_margins,
    compute_snowball_factors,
    compute_tornado,
    display_label_for_output,
    display_label_for_parameter,
    run_oat_sweep,
    sweepable_parameters_for,
    unit_kind_for_output,
    unit_kind_for_parameter,
)


# ── Per-export config ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class SensitivityReportConfig(SectionConfig):
    """User-customisable export payload for the sensitivity section.

    Fields
    ──────
    tornado_output_ids : tuple of OUTPUT_CATALOG keys — one tornado figure
                         is emitted per entry. Order preserved.
    sweep_specs        : tuple of (output_id, input_field_name) pairs —
                         one OAT-sweep figure is emitted per entry.
    include_margins    : add the constraint-margins table.
    include_snowball   : add the snowball-factor table.

    Validation: ``validate(brief)`` drops any output_id whose
    ``OutputSpec.is_included(brief)`` returns False, and any sweep spec
    whose input parameter is gated out for this propulsion (e.g. SFC on
    a pure-Electric brief). The unvalidated config never reaches the
    renderer — ``ExportService`` calls ``validate`` before ``build``.
    """

    tornado_output_ids: tuple[str, ...] = field(default_factory=tuple)
    sweep_specs:        tuple[tuple[str, str], ...] = field(default_factory=tuple)
    include_margins:    bool = True
    include_snowball:   bool = True

    def validate(self, brief: DesignBrief) -> "SensitivityReportConfig":
        params_by_field = {p.field_name: p for p in SWEEPABLE_PARAMETERS}

        valid_tornados: tuple[str, ...] = tuple(
            oid for oid in self.tornado_output_ids
            if oid in OUTPUT_CATALOG
            and OUTPUT_CATALOG[oid].is_included(brief)
        )

        valid_sweeps: tuple[tuple[str, str], ...] = tuple(
            (oid, fn) for (oid, fn) in self.sweep_specs
            if oid in OUTPUT_CATALOG
            and OUTPUT_CATALOG[oid].is_included(brief)
            and fn in params_by_field
            and params_by_field[fn].is_included(brief)
        )

        return SensitivityReportConfig(
            tornado_output_ids=valid_tornados,
            sweep_specs=valid_sweeps,
            include_margins=self.include_margins,
            include_snowball=self.include_snowball,
        )

    def summary(self) -> str:
        parts: list[str] = []
        n_t = len(self.tornado_output_ids)
        if n_t:
            parts.append(f"{n_t} tornado" + ("s" if n_t != 1 else ""))
        n_s = len(self.sweep_specs)
        if n_s:
            parts.append(f"{n_s} sweep" + ("s" if n_s != 1 else ""))
        if self.include_margins:
            parts.append("margins")
        if self.include_snowball:
            parts.append("snowball")
        return " · ".join(parts) if parts else "(empty)"


# ── Section ────────────────────────────────────────────────────────────────


class SensitivityAnalysisSection(ReportSection[SensitivityReportConfig]):
    """Design-sensitivity studio output, rendered into the report.

    Customisable: the export dialog shows a "Customise…" button next to
    this section so the user can pick which tornados / sweeps appear.
    Default config mirrors the live Sensitivity tab's three tornado
    slots (``settings.sens_tornado_output_ids``) and includes margins +
    snowball; sweeps default to empty (the user opts in per export).
    """

    section_id      = "sensitivity_analysis"
    title           = "Design Sensitivity Analysis"
    default_order   = 95   # after sanity_checks (90), before appendix_inputs (100)
    category        = SectionCategory.ANALYSIS
    description     = (
        "Tornados, sweeps, constraint margins, snowball factors — "
        "the design rule-of-thumb pack."
    )
    is_customizable = True

    @classmethod
    def default_config(cls, ctx: ReportContext) -> SensitivityReportConfig:
        """Default = the live page's tornado slots, no sweeps, margins +
        snowball ON. Mirrors the studio view so the report matches the
        designer's working session unless they customise it."""
        return SensitivityReportConfig(
            tornado_output_ids=tuple(ctx.settings.sens_tornado_output_ids),
            sweep_specs=(),
            include_margins=True,
            include_snowball=True,
        )

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        # Importing here keeps the section module side-effect-free at
        # import time (the live tab tests import OUTPUT_CATALOG / etc.
        # before the Qt loop is up).
        from app.services.figure_renderers import (
            render_sweep_png,
            render_tornado_png,
        )

        rb.add_heading(self.title, level=1)

        # ── Intro ─────────────────────────────────────────────────────────
        rb.add_paragraph(
            "Sensitivity analysis quantifies how the design responds to "
            "uncertainty in each requirement and aerodynamic coefficient. "
            "Methodology follows Raymer (2018) Ch. 19 (tornado / trade "
            "studies), Sadraey (2020) Sec. 2.10 (takeoff-weight "
            "derivatives), and Keane et al. (2017) Ch. 4 (screening "
            "sensitivity)."
        )
        if ctx.constraint_result is None or ctx.design_point is None:
            rb.add_note(
                "Sensitivity content requires a sized design point — run "
                "sizing on the General tab before exporting."
            )
            return

        config = self._config or self.default_config(ctx)
        # Defensive — ExportService already calls validate, but a hand-
        # written caller (or future test) may not.
        config = config.validate(ctx.brief)

        if not (
            config.tornado_output_ids
            or config.sweep_specs
            or config.include_margins
            or config.include_snowball
        ):
            rb.add_note(
                "Section configured with no content (no tornados, no "
                "sweeps, margins/snowball disabled)."
            )
            return

        coeffs = ctx.regression_coeffs
        propulsion = ctx.brief.propulsion_type
        dc = ctx.display_converter

        # ── Tornados ──────────────────────────────────────────────────────
        if config.tornado_output_ids:
            params = sweepable_parameters_for(ctx.brief)
            for output_id in config.tornado_output_ids:
                out_label = display_label_for_output(output_id, propulsion)
                rb.add_heading(f"Tornado — {out_label}", level=2)
                if coeffs is None:
                    rb.add_note(
                        "Regression coefficients unavailable — skipped."
                    )
                    continue
                td = compute_tornado(ctx.brief, coeffs, params, output_id)
                png = render_tornado_png(td, propulsion, dc)
                if png is None:
                    rb.add_note(
                        f"Could not render the {out_label} tornado figure."
                    )
                else:
                    rb.add_figure(
                        png,
                        caption=(
                            f"Tornado of input impact on {out_label} "
                            f"(±{ctx.settings.sens_delta_pct:.0f} % perturbation, "
                            f"sorted by magnitude)."
                        ),
                        width_cm=15.0,
                    )

        # ── Sweeps ────────────────────────────────────────────────────────
        if config.sweep_specs:
            params_by_field = {p.field_name: p for p in SWEEPABLE_PARAMETERS}
            for output_id, input_field in config.sweep_specs:
                out_label = display_label_for_output(output_id, propulsion)
                param = params_by_field.get(input_field)
                if param is None:
                    continue
                in_label = display_label_for_parameter(param, propulsion)
                rb.add_heading(
                    f"Sweep — {out_label} vs {in_label}", level=2,
                )
                if coeffs is None:
                    rb.add_note(
                        "Regression coefficients unavailable — skipped."
                    )
                    continue
                sweep = run_oat_sweep(
                    ctx.brief, coeffs, param,
                    n_points=ctx.settings.sens_n_points,
                    delta_pct=ctx.settings.sens_delta_pct,
                )
                png = render_sweep_png(sweep, [output_id], propulsion, dc)
                if png is None:
                    rb.add_note(
                        f"Could not render the {out_label} vs {in_label} sweep."
                    )
                else:
                    rb.add_figure(
                        png,
                        caption=(
                            f"OAT sweep of {out_label} as {in_label} varies by "
                            f"±{ctx.settings.sens_delta_pct:.0f} % around the design point."
                        ),
                        width_cm=15.0,
                    )

        # ── Constraint margins ────────────────────────────────────────────
        if config.include_margins:
            rb.add_heading("Constraint Margins", level=2)
            report = compute_constraint_margins(
                ctx.design_point, ctx.constraint_result,
                critical_pct=ctx.settings.sens_severity_critical_pct,
                tight_pct=ctx.settings.sens_severity_tight_pct,
            )
            if report.most_violated is not None:
                rb.add_paragraph(
                    f"VIOLATED: {report.most_violated.name} "
                    f"({report.most_violated.margin_pct:+.1f} %).",
                    bold=True,
                )
            elif report.binding is not None:
                rb.add_paragraph(
                    f"Binding constraint: {report.binding.name} — "
                    f"{report.binding.margin_pct:.1f} % margin "
                    f"(bites first if requirements tighten).",
                )
            rows: list[list[str]] = []
            severity_label = {
                "critical": "Critical",
                "tight":    "Tight",
                "ok":       "OK",
            }
            for m in report.margins:
                rows.append([
                    m.name,
                    f"{m.margin_pct:+.1f} %",
                    severity_label.get(m.severity, m.severity),
                ])
            rb.add_table(
                headers=["Constraint", "Margin", "Severity"],
                rows=rows,
                caption="Constraint margins at the design point.",
            )

        # ── Snowball factors ──────────────────────────────────────────────
        if config.include_snowball:
            rb.add_heading("Design Rules of Thumb (Snowball Factors)", level=2)
            if coeffs is None:
                rb.add_note(
                    "Regression coefficients unavailable — snowball factors skipped."
                )
            else:
                snowball = compute_snowball_factors(ctx.brief, coeffs)
                rows = self._snowball_rows(snowball, propulsion, dc)
                rb.add_table(
                    headers=["Sensitivity", "Value", "Interpretation"],
                    rows=rows,
                    caption=(
                        "Local partial derivatives ∂(output)/∂(input) at the "
                        "current design point."
                    ),
                )

    # ── helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _snowball_rows(
        snowball, propulsion, dc,
    ) -> list[list[str]]:
        """Build the snowball-factor table rows, display-converted in both
        numerator and denominator (matches the live snowball widget)."""
        rows: list[list[str]] = []
        for f in snowball.factors:
            out_label = display_label_for_output(f.output_id, propulsion)
            in_label  = display_label_for_parameter(f.parameter, propulsion)

            # Output factor / unit
            out_kind = unit_kind_for_output(f.output_id, propulsion)
            out_conv = getattr(dc, out_kind, None)
            if out_conv is not None:
                out_factor, out_unit = out_conv(1.0)
            else:
                out_factor, out_unit = 1.0, f.output_unit

            # Input factor / unit
            in_kind = unit_kind_for_parameter(f.parameter)
            in_conv = getattr(dc, in_kind, None)
            if in_conv is None or in_kind == "ratio":
                in_factor, in_unit = 1.0, f.parameter.unit
            else:
                in_factor, in_unit = in_conv(1.0)

            symbol = f"∂{out_label} / ∂{in_label}"
            if f.value is None or in_factor == 0:
                rows.append([symbol, "—", "Could not compute"])
                continue
            display_value = f.value * out_factor / in_factor
            sign = "increase" if display_value >= 0 else "decrease"
            interp = (
                f"Each +1 {in_unit} of {in_label} → "
                f"{sign} of {abs(display_value):.3g} {out_unit} in {out_label}"
            )
            rows.append([
                symbol,
                f"{display_value:+.4g} {out_unit}/{in_unit}",
                interp,
            ])
        return rows
