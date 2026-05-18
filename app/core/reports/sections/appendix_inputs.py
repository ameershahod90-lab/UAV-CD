"""Appendix: Full Inputs — order 100."""
from __future__ import annotations
from app.core.reports.base import ReportSection, ReportContext, SectionCategory
from app.core.reports.renderer import ReportBuilder


class AppendixInputsSection(ReportSection):
    section_id    = "appendix_inputs"
    title         = "Appendix A: Full Input Summary"
    default_order = 100
    category      = SectionCategory.APPENDIX
    description   = "Complete design brief and segment parameters in one reference table"

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        t = ctx.t
        rb.add_heading(t("section.appendix_inputs.title"), level=1)
        rb.add_paragraph(t("section.appendix_inputs.intro"))

        b = ctx.brief

        # Field names are intentionally code identifiers (snake_case English)
        # since they correspond to .uavcd file keys. Engineers tracing values
        # between report and file need them as-is.
        all_rows = [
            ["payload_mass_kg",         f"{b.payload_mass_kg:.4f}",         "kg"],
            ["cruise_speed_ms",         f"{b.cruise_speed_ms:.4f}",         "m/s"],
            ["stall_speed_ms",          f"{b.stall_speed_ms:.4f}",          "m/s"],
            ["max_speed_ms",            f"{b.max_speed_ms:.4f}",            "m/s"],
            ["takeoff_run_m",           f"{b.takeoff_run_m:.4f}",           "m"],
            ["rate_of_climb_ms",        f"{b.rate_of_climb_ms:.4f}",        "m/s"],
            ["service_ceiling_m",       f"{b.service_ceiling_m:.4f}",       "m"],
            ["cruise_altitude_m",       f"{b.cruise_altitude_m:.4f}",       "m"],
            ["propulsion_type",         b.propulsion_type.name,             "—"],
            ["aspect_ratio",            f"{b.aspect_ratio:.4f}",            "—"],
            ["c_d0",                    f"{b.c_d0:.6f}",                    "—"],
            ["c_l_max",                 f"{b.c_l_max:.4f}",                 "—"],
            ["oswald_efficiency",       f"{b.oswald_efficiency:.4f}",       "—"],
            ["prop_efficiency",         f"{b.prop_efficiency:.4f}",         "—"],
        ]

        if hasattr(b, "sfc_kg_ns"):
            all_rows.append(["sfc_kg_ns", f"{b.sfc_kg_ns:.6e}", "kg/(N·s)"])
        if hasattr(b, "battery_specific_energy_wh_kg"):
            all_rows.append(["battery_specific_energy_wh_kg",
                              f"{b.battery_specific_energy_wh_kg:.2f}", "Wh/kg"])
        if hasattr(b, "battery_efficiency"):
            all_rows.append(["battery_efficiency",
                              f"{b.battery_efficiency:.4f}", "—"])

        rb.add_table(
            headers=[
                t("section.appendix_inputs.col.field"),
                t("section.appendix_inputs.col.value_si"),
                t("section.appendix_inputs.col.unit"),
            ],
            rows=all_rows,
            caption=t("section.appendix_inputs.table.brief_caption"),
        )

        # Mission segments — detail listing
        rb.add_heading(
            t("section.appendix_inputs.heading.segments"), level=2,
        )
        yes = t("common.yes")
        no  = t("common.no")
        dash = t("common.dash")
        seg_rows = []
        for i, seg in enumerate(b.mission_segments, 1):
            params: dict[str, str] = {}
            if hasattr(seg, "range_km"):
                params["range_km"] = f"{seg.range_km:.2f} km"
            if hasattr(seg, "endurance_hr"):
                params["endurance_hr"] = f"{seg.endurance_hr:.3f} hr"
            param_str = ", ".join(f"{k}={v}" for k, v in params.items()) or dash
            seg_rows.append([
                str(i),
                seg.segment_type.name,
                yes if seg.enabled else no,
                seg.energy_source.value if hasattr(seg, "energy_source") else dash,
                param_str,
            ])
        rb.add_table(
            headers=[
                "#",
                t("section.appendix_inputs.col.type"),
                t("section.appendix_inputs.col.enabled"),
                t("section.appendix_inputs.col.energy"),
                t("section.appendix_inputs.col.parameters"),
            ],
            rows=seg_rows,
            caption=t("section.appendix_inputs.table.segments_caption"),
        )
