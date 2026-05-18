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
        t = ctx.t
        rb.add_heading(t("section.mission_requirements.title"), level=1)
        rb.add_paragraph(t("section.mission_requirements.intro"))

        b = ctx.brief

        # Row labels and descriptions translate; values/units stay numeric/SI.
        rows = [
            [t("mr.row.payload_mass"),    f"{b.payload_mass_kg:.3f} kg",   t("mr.desc.payload_mass")],
            [t("mr.row.cruise_speed"),    f"{b.cruise_speed_ms:.1f} m/s",  t("mr.desc.cruise_speed")],
            [t("mr.row.stall_speed"),     f"{b.stall_speed_ms:.1f} m/s",   t("mr.desc.stall_speed")],
            [t("mr.row.max_speed"),       f"{b.max_speed_ms:.1f} m/s",     t("mr.desc.max_speed")],
            [t("mr.row.rate_of_climb"),   f"{b.rate_of_climb_ms:.2f} m/s", t("mr.desc.rate_of_climb")],
            [t("mr.row.cruise_altitude"), f"{b.cruise_altitude_m:.0f} m",  t("mr.desc.cruise_altitude")],
            [t("mr.row.service_ceiling"), f"{b.service_ceiling_m:.0f} m",  t("mr.desc.service_ceiling")],
            [t("mr.row.takeoff_run"),     f"{b.takeoff_run_m:.0f} m",      t("mr.desc.takeoff_run")],
            [t("mr.row.propulsion_type"), b.propulsion_type.label,         t("mr.desc.propulsion_type")],
            [t("mr.row.aspect_ratio"),    f"{b.aspect_ratio:.2f}",         t("mr.desc.aspect_ratio")],
            [t("mr.row.c_d0"),            f"{b.c_d0:.4f}",                 t("mr.desc.c_d0")],
            [t("mr.row.c_l_max"),         f"{b.c_l_max:.2f}",              t("mr.desc.c_l_max")],
            [t("mr.row.oswald"),          f"{b.oswald_efficiency:.3f}",    t("mr.desc.oswald")],
            [t("mr.row.prop_efficiency"), f"{b.prop_efficiency:.2f}",      t("mr.desc.prop_efficiency")],
        ]

        # Propulsion-specific rows
        if b.propulsion_type.uses_fuel:
            rows.append([
                t("mr.row.sfc"),
                f"{b.specific_fuel_consumption_g_wh:.4f} g/(W·h)",
                t("mr.desc.sfc"),
            ])
        if not b.propulsion_type.uses_fuel:
            rows.append([
                t("mr.row.battery_energy_density"),
                f"{b.battery_energy_density_wh_kg:.1f} Wh/kg",
                t("mr.desc.battery_energy_density"),
            ])
            rows.append([
                t("mr.row.battery_efficiency"),
                f"{b.battery_efficiency:.3f}",
                t("mr.desc.battery_efficiency"),
            ])

        rb.add_table(
            headers=[t("col.parameter"), t("col.value"), t("col.description")],
            rows=rows,
            caption=t("section.mission_requirements.table.brief_caption"),
        )

        # Mission segments — energy_source normalised per propulsion so the
        # report mirrors what the weight engine actually computes.
        rb.add_heading(t("section.mission_requirements.heading.segments"), level=2)
        yes = t("common.yes")
        no  = t("common.no")
        fixed_fraction = t("common.fixed_fraction")
        seg_rows = []
        for i, seg in enumerate(b.mission_segments, 1):
            normalised = seg.with_energy_source(b.propulsion_type)
            kind = normalised.segment_type.name
            enabled = yes if normalised.enabled else no
            energy = normalised.energy_source.value
            if isinstance(normalised, CruiseMissionSegment):
                params = t("mr.params.cruise_range", range_km=normalised.range_km)
            elif isinstance(normalised, LoiterMissionSegment):
                params = t("mr.params.loiter_endurance",
                           endurance_hr=normalised.endurance_hr)
            else:
                params = fixed_fraction
            seg_rows.append([str(i), kind, enabled, energy, params])

        rb.add_table(
            headers=[
                "#",
                t("section.mission_requirements.col.segment_type"),
                t("section.mission_requirements.col.enabled"),
                t("section.mission_requirements.col.energy_source"),
                t("section.mission_requirements.col.parameters"),
            ],
            rows=seg_rows,
            caption=t("section.mission_requirements.table.segments_caption"),
        )

        # Totals
        total_range     = b.total_range_km
        total_endurance = b.total_endurance_hr
        if total_range > 0 or total_endurance > 0:
            rb.add_key_value_list([
                (t("section.mission_requirements.kv.total_range"),
                 f"{total_range:.1f} km"),
                (t("section.mission_requirements.kv.total_endurance"),
                 f"{total_endurance:.2f} hr"),
            ])
