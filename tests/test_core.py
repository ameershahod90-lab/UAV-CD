"""
Tests — Core Domain Layer — UAV-CD-APP
=========================================
Unit tests for: atmosphere, validation, units, classification,
weight buildup, and design point engines.
"""

from __future__ import annotations

import math
import pytest

# ---------------------------------------------------------------------------
# Atmosphere
# ---------------------------------------------------------------------------

class TestAtmosphereModel:
    def test_sea_level(self) -> None:
        from app.core.atmosphere import AtmosphereModel
        atm = AtmosphereModel.sea_level()
        assert abs(atm.temperature_k - 288.15) < 0.01
        assert abs(atm.pressure_pa - 101_325.0) < 10
        assert abs(atm.density_kg_m3 - 1.225) < 0.002

    def test_11km_isothermal(self) -> None:
        from app.core.atmosphere import AtmosphereModel
        atm = AtmosphereModel.at_altitude(11_000.0)
        assert abs(atm.temperature_k - 216.65) < 1.0

    def test_density_decreases_with_altitude(self) -> None:
        from app.core.atmosphere import AtmosphereModel
        rho_sl = AtmosphereModel.density_at(0.0)
        rho_1k = AtmosphereModel.density_at(1_000.0)
        rho_5k = AtmosphereModel.density_at(5_000.0)
        assert rho_sl > rho_1k > rho_5k

    def test_speed_of_sound_sea_level(self) -> None:
        from app.core.atmosphere import AtmosphereModel
        atm = AtmosphereModel.sea_level()
        # ISA a₀ ≈ 340.29 m/s
        assert abs(atm.speed_of_sound_ms - 340.29) < 1.0

    def test_altitude_clamping(self) -> None:
        from app.core.atmosphere import AtmosphereModel
        atm_high = AtmosphereModel.at_altitude(100_000.0)
        atm_25k  = AtmosphereModel.at_altitude(25_000.0)
        # Both should return clamped result at 25 000 m
        assert abs(atm_high.altitude_m - atm_25k.altitude_m) < 1.0


# ---------------------------------------------------------------------------
# Unit Converter
# ---------------------------------------------------------------------------

class TestUnitConverter:
    def test_speed_roundtrip_knots(self) -> None:
        from app.core.units import UnitConverter
        from app.core.enums import SpeedUnit
        si = 25.0
        knots = UnitConverter.speed_to_display(si, SpeedUnit.KNOTS)
        back  = UnitConverter.speed_to_si(knots, SpeedUnit.KNOTS)
        assert abs(back - si) < 1e-9

    def test_mass_roundtrip_lb(self) -> None:
        from app.core.units import UnitConverter
        from app.core.enums import MassUnit
        kg = 10.0
        lb = UnitConverter.mass_to_display(kg, MassUnit.LB)
        assert abs(lb - 22.046) < 0.01
        back = UnitConverter.mass_to_si(lb, MassUnit.LB)
        assert abs(back - kg) < 1e-9

    def test_area_roundtrip_ft2(self) -> None:
        from app.core.units import UnitConverter
        from app.core.enums import AreaUnit
        m2 = 1.0
        ft2 = UnitConverter.area_to_display(m2, AreaUnit.FT2)
        back = UnitConverter.area_to_si(ft2, AreaUnit.FT2)
        assert abs(back - m2) < 1e-9


# ---------------------------------------------------------------------------
# Entity Validation
# ---------------------------------------------------------------------------

class TestEntityValidator:
    def test_valid_brief_passes(self) -> None:
        from app.core.entities import DesignBrief
        from app.core.validation import EntityValidator
        brief = DesignBrief()  # defaults should pass
        errors = EntityValidator.validate(brief)
        assert errors == [], f"Unexpected errors: {[e.message for e in errors]}"

    def test_negative_payload_fails(self) -> None:
        from app.core.entities import DesignBrief
        from app.core.validation import EntityValidator
        brief = DesignBrief(payload_mass_kg=-1.0)
        errors = EntityValidator.validate(brief)
        fields = [e.field_name for e in errors]
        assert "payload_mass_kg" in fields

    def test_aspect_ratio_below_min_fails(self) -> None:
        from app.core.entities import DesignBrief
        from app.core.validation import EntityValidator
        brief = DesignBrief(aspect_ratio=1.0)  # min is 2.0
        errors = EntityValidator.validate(brief)
        assert any(e.field_name == "aspect_ratio" for e in errors)

    def test_multiple_errors_collected(self) -> None:
        from app.core.entities import DesignBrief
        from app.core.validation import EntityValidator
        brief = DesignBrief(payload_mass_kg=-1.0, c_d0=0.0)
        errors = EntityValidator.validate(brief)
        assert len(errors) >= 2


# ---------------------------------------------------------------------------
# Classification Validation
# ---------------------------------------------------------------------------

class TestClassificationValidation:
    def test_valid_ranges_pass(self) -> None:
        from app.core.entities import ClassificationRange
        from app.services.database_service import validate_ranges
        ranges = [
            ClassificationRange("A", 0.0, 25.0, "#fff"),
            ClassificationRange("B", 25.0, 150.0, "#fff"),
        ]
        errors = validate_ranges(ranges)
        assert errors == []

    def test_gap_detected(self) -> None:
        from app.core.entities import ClassificationRange
        from app.services.database_service import validate_ranges
        ranges = [
            ClassificationRange("A", 0.0, 20.0, "#fff"),
            ClassificationRange("B", 25.0, 100.0, "#fff"),  # gap 20–25
        ]
        errors = validate_ranges(ranges)
        assert len(errors) > 0
        assert any("gap" in e.lower() or "overlap" in e.lower() for e in errors)

    def test_empty_ranges_fail(self) -> None:
        from app.services.database_service import validate_ranges
        errors = validate_ranges([])
        assert len(errors) > 0

    def test_duplicate_names_fail(self) -> None:
        from app.core.entities import ClassificationRange
        from app.services.database_service import validate_ranges
        ranges = [
            ClassificationRange("A", 0.0, 50.0, "#fff"),
            ClassificationRange("A", 50.0, 100.0, "#fff"),
        ]
        errors = validate_ranges(ranges)
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# Weight Buildup
# ---------------------------------------------------------------------------

class TestWeightBuildup:
    def _solve(self, propulsion: str = "Electric") -> object:
        from app.core.entities import DesignBrief, RegressionCoeffs
        from app.core.enums import DataSource, PropulsionType
        from app.core.weight_buildup import WeightBuildupEngine
        brief = DesignBrief(
            payload_mass_kg=5.0,
            propulsion_type=PropulsionType(propulsion),
        )
        coeffs = RegressionCoeffs(
            class_name="Test",
            we_a=-0.001, we_b=0.65,
            data_source=DataSource.TEXTBOOK,
        )
        engine = WeightBuildupEngine()
        return engine.solve(brief, coeffs)

    def test_electric_converges(self) -> None:
        result = self._solve("Electric")
        assert result.converged
        assert result.w_to_kg > result.w_payload_kg
        assert 0 < result.empty_weight_fraction < 1

    def test_piston_converges(self) -> None:
        result = self._solve("Piston")
        assert result.converged

    def test_masses_sum_to_wto(self) -> None:
        result = self._solve()
        total = result.w_empty_kg + result.w_fuel_or_battery_kg + result.w_payload_kg
        assert abs(total - result.w_to_kg) < 0.01  # ≤1 g discrepancy


# ---------------------------------------------------------------------------
# Regression
# ---------------------------------------------------------------------------

class TestRegression:
    def test_fit_linear_perfect(self) -> None:
        import numpy as np
        from app.core.regression import fit_linear
        x = np.linspace(1, 10, 20)
        y = 2.0 * x + 3.0
        a, b, r2 = fit_linear(x, y)
        assert abs(a - 2.0) < 1e-6
        assert abs(b - 3.0) < 1e-6
        assert r2 > 0.999

    def test_fit_power_law(self) -> None:
        import numpy as np
        from app.core.regression import fit_power_law
        x = np.linspace(1, 100, 50)
        y = 1.1 * x ** 0.333
        c, e, r2 = fit_power_law(x, y, p0=(1.0, 0.3))
        assert abs(c - 1.1) < 0.05
        assert abs(e - 0.333) < 0.02
        assert r2 > 0.99


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class TestSettings:
    def test_defaults(self) -> None:
        from app.state.settings import UserSettings
        from app.core.enums import ThemeOption, UnitSystem
        s = UserSettings()
        assert s.theme is ThemeOption.DARK
        assert s.unit_system is UnitSystem.METRIC

    def test_invalid_enum_falls_back(self) -> None:
        from app.state.settings import _from_dict
        d = {"theme": "INVALID_THEME_VALUE"}
        s = _from_dict(d)
        from app.core.enums import ThemeOption
        assert s.theme is ThemeOption.DARK  # default

    def test_cascade_metric(self) -> None:
        from app.state.settings import UserSettings
        from app.core.units import cascade_unit_system
        from app.core.enums import UnitSystem, SpeedUnit, MassUnit
        import dataclasses
        s = dataclasses.replace(UserSettings(), unit_system=UnitSystem.METRIC)
        cascaded = cascade_unit_system(s)
        assert cascaded.speed_unit is SpeedUnit.MS
        assert cascaded.mass_unit is MassUnit.KG

    def test_cascade_imperial(self) -> None:
        from app.state.settings import UserSettings
        from app.core.units import cascade_unit_system
        from app.core.enums import UnitSystem, SpeedUnit, MassUnit
        import dataclasses
        s = dataclasses.replace(UserSettings(), unit_system=UnitSystem.IMPERIAL)
        cascaded = cascade_unit_system(s)
        assert cascaded.speed_unit is SpeedUnit.KNOTS
        assert cascaded.mass_unit is MassUnit.LB


# ---------------------------------------------------------------------------
# Project File Roundtrip
# ---------------------------------------------------------------------------

class TestProjectFile:
    def test_save_load_roundtrip(self, tmp_path) -> None:
        from app.state.project_file import new_project, save_project, load_project
        state = new_project("Test Project")
        state.sizing.brief.payload_mass_kg = 7.5
        path = str(tmp_path / "test.uavcd")
        assert save_project(state, path)
        loaded = load_project(path)
        assert loaded is not None
        assert loaded.meta.name == "Test Project"
        assert abs(loaded.sizing.brief.payload_mass_kg - 7.5) < 1e-9
