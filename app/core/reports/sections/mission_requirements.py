"""Mission Requirements — order 30."""
from __future__ import annotations
from app.core.reports.base import ReportSection, ReportContext, SectionCategory
from app.core.reports.renderer import ReportBuilder


class MissionRequirementsSection(ReportSection):
    section_id    = "mission_requirements"
    title         = "Mission Requirements"
    default_order = 30
    category      = SectionCategory.ANALYSIS
    description   = "All design brief inputs formatted as a requirements table"

    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        rb.add_heading(self.title, level=1)
        rb.add_paragraph(
            "The following mission requirements form the basis of the sizing study. "
            "All calculations are performed in SI units; display units shown below "
            "reflect the user's selected preferences."
        )

        b   = ctx.brief
        dc  = ctx.display_converter

        spd_v, spd_u = dc.speed(b.cruise_speed_ms)
        vs_v,  vs_u  = dc.speed(b.stall_speed_ms)
        vm_v,  vm_u  = dc.speed(b.max_speed_ms)
        roc_v, roc_u = dc.speed(b.rate_of_climb_ms)
        alt_v, alt_u = dc.length(b.cruise_altitude_m)
        sc_v,  sc_u  = dc.length(b.service_ceiling_m)
        to_v,  to_u  = dc.length(b.takeoff_run_m)
        pm_v,  pm_u  = dc.mass(b.payload_mass_kg)

        rows = [
            ["Payload Mass",        f"{pm_v:.2f} {pm_u}",        "Design payload carried by the UAV"],
            ["Cruise Speed",        f"{spd_v:.1f} {spd_u}",      "Nominal cruise airspeed"],
            ["Stall Speed",         f"{vs_v:.1f} {vs_u}",        "Minimum safe flight speed"],
            ["Max Speed",           f"{vm_v:.1f} {vm_u}",        "Maximum level flight speed"],
            ["Rate of Climb",       f"{roc_v:.2f} {roc_u}",      "Climb rate at sea level"],
            ["Cruise Altitude",     f"{alt_v:.0f} {alt_u}",      "Nominal operating altitude"],
            ["Service Ceiling",     f"{sc_v:.0f} {sc_u}",        "Maximum altitude (ROC = 0.508 m/s)"],
            ["Takeoff Run",         f"{to_v:.0f} {to_u}",        "Ground roll distance required"],
            ["Propulsion Type",     b.propulsion_type.label,     "Propulsion system category"],
            ["Aspect Ratio",        f"{b.aspect_ratio:.2f}",     "Wing aspect ratio"],
            ["CD₀",                 f"{b.c_d0:.4f}",             "Zero-lift drag coefficient"],
            ["CLmax",               f"{b.c_l_max:.2f}",          "Maximum lift coefficient"],
            ["Oswald Efficiency",   f"{b.oswald_efficiency:.3f}","Oswald span efficiency factor e"],
            ["Propeller Efficiency",f"{b.prop_efficiency:.2f}", "Propulsive efficiency ηp (prop/turboprop)"],
        ]

        rb.add_table(
            headers=["Parameter", "Value", "Description"],
            rows=rows,
            caption="Mission design requirements and aerodynamic parameters",
        )

        # Mission segments summary
        rb.add_heading("Mission Segments", level=2)
        seg_rows = []
        for seg in b.mission_segments:
            params = "—"
            if hasattr(seg, "range_km"):
                r_v, r_u = dc.length(seg.range_km * 1000)
                params = f"Range: {r_v:.1f} {r_u}"
            elif hasattr(seg, "endurance_hr"):
                params = f"Endurance: {seg.endurance_hr:.2f} hr"
            seg_rows.append([
                seg.label,
                "Enabled" if seg.enabled else "Disabled",
                getattr(seg, "energy_source", "—").value if hasattr(seg, "energy_source") else "—",
                params,
            ])
        rb.add_table(
            headers=["Segment", "Status", "Energy Source", "Parameters"],
            rows=seg_rows,
            caption="Mission segment profile",
        )

        # Totals
        total_range = b.total_range_km
        total_endurance = b.total_endurance_hr
        if total_range > 0 or total_endurance > 0:
            rb.add_key_value_list([
                ("Total Range",     f"{total_range:.1f} km"),
                ("Total Endurance", f"{total_endurance:.2f} hr"),
            ])
