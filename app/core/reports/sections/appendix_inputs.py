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
        rb.add_heading(self.title, level=1)
        rb.add_paragraph(
            "A complete record of all inputs used in this sizing study.  "
            "Values are shown in both SI units and the display units configured at export time."
        )

        b  = ctx.brief
        dc = ctx.display_converter

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
            headers=["Field", "Value (SI)", "Unit"],
            rows=all_rows,
            caption="Complete design brief — raw SI values",
        )

        # Mission segments
        rb.add_heading("Mission Segments (Detail)", level=2)
        seg_rows = []
        for i, seg in enumerate(b.mission_segments, 1):
            params = {}
            if hasattr(seg, "range_km"):
                params["range_km"] = f"{seg.range_km:.2f} km"
            if hasattr(seg, "endurance_hr"):
                params["endurance_hr"] = f"{seg.endurance_hr:.3f} hr"
            param_str = ", ".join(f"{k}={v}" for k, v in params.items()) or "—"
            seg_rows.append([
                str(i),
                seg.segment_type.name,
                "Yes" if seg.enabled else "No",
                seg.energy_source.value if hasattr(seg, "energy_source") else "—",
                param_str,
            ])
        rb.add_table(
            headers=["#", "Type", "Enabled", "Energy", "Parameters"],
            rows=seg_rows,
            caption="Mission segment definitions",
        )
