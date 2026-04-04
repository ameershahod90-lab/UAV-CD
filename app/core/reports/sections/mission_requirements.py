"""Mission Requirements — order 30."""
from __future__ import annotations
from app.core.reports.base import ReportSection, ReportContext, SectionCategory
from app.core.reports.renderer import ReportBuilder
from app.core.entities import CruiseMissionSegment, LoiterMissionSegment


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
            "All calculations are performed in SI units."
        )

        b = ctx.brief

        rows = [
            ["Payload Mass",          f"{b.payload_mass_kg:.3f} kg",   "Design payload"],
            ["Cruise Speed",          f"{b.cruise_speed_ms:.1f} m/s",  "Nominal cruise airspeed"],
            ["Stall Speed",           f"{b.stall_speed_ms:.1f} m/s",   "Minimum safe speed"],
            ["Max Speed",             f"{b.max_speed_ms:.1f} m/s",     "Maximum level speed"],
            ["Rate of Climb",         f"{b.rate_of_climb_ms:.2f} m/s", "Climb rate at SL"],
            ["Cruise Altitude",       f"{b.cruise_altitude_m:.0f} m",  "Nominal altitude"],
            ["Service Ceiling",       f"{b.service_ceiling_m:.0f} m",  "Max altitude (ROC = 0.508 m/s)"],
            ["Takeoff Run",           f"{b.takeoff_run_m:.0f} m",      "Ground roll distance"],
            ["Propulsion Type",       b.propulsion_type.label,          "Propulsion category"],
            ["Aspect Ratio (AR)",     f"{b.aspect_ratio:.2f}",          "Wing aspect ratio"],
            ["CD0",                   f"{b.c_d0:.4f}",                  "Zero-lift drag coefficient"],
            ["CLmax",                 f"{b.c_l_max:.2f}",               "Maximum lift coefficient"],
            ["Oswald Efficiency (e)", f"{b.oswald_efficiency:.3f}",     "Span efficiency"],
            ["Prop. Efficiency (eta_p)", f"{b.prop_efficiency:.2f}",   "Propulsive efficiency"],
        ]

        # Propulsion-specific fields
        if b.propulsion_type.is_fuel_mode or b.propulsion_type.is_hybrid:
            rows.append(["SFC", f"{b.specific_fuel_consumption_g_wh:.4f} g/(W·h)", "Specific fuel consumption"])
        if not b.propulsion_type.is_fuel_mode or b.propulsion_type.is_hybrid:
            rows.append(["Battery Energy Density",
                         f"{b.battery_energy_density_wh_kg:.1f} Wh/kg",
                         "Li-Po cell specific energy"])
            rows.append(["Battery Efficiency",
                         f"{b.battery_efficiency:.3f}",
                         "Charge/discharge efficiency"])

        rb.add_table(
            headers=["Parameter", "Value", "Description"],
            rows=rows,
            caption="Mission design requirements and aerodynamic parameters",
        )

        # Mission segments
        rb.add_heading("Mission Segments", level=2)
        seg_rows = []
        for i, seg in enumerate(b.mission_segments, 1):
            kind   = seg.segment_type.name
            enabled = "Yes" if seg.enabled else "No"
            energy = seg.energy_source.value if hasattr(seg, "energy_source") else "—"
            if isinstance(seg, CruiseMissionSegment):
                params = f"Range: {seg.range_km:.1f} km"
            elif isinstance(seg, LoiterMissionSegment):
                params = f"Endurance: {seg.endurance_hr:.2f} hr"
            else:
                params = "Fixed fraction"
            seg_rows.append([str(i), kind, enabled, energy, params])

        rb.add_table(
            headers=["#", "Segment Type", "Enabled", "Energy Source", "Parameters"],
            rows=seg_rows,
            caption="Mission segment profile",
        )

        # Totals
        total_range     = b.total_range_km
        total_endurance = b.total_endurance_hr
        if total_range > 0 or total_endurance > 0:
            rb.add_key_value_list([
                ("Total Range from enabled cruise segments",
                 f"{total_range:.1f} km"),
                ("Total Endurance from enabled loiter segments",
                 f"{total_endurance:.2f} hr"),
            ])
