import numpy as np
import pytest

from backend.energy.sun_visibility import (
    occulted_fraction,
    sun_visibility_from_samples,
)
from backend.energy.solar_power import (
    AU_KM,
    PanelConfig,
    solar_flux_w_m2,
    panel_cosine,
    solar_power_w,
)
from backend.energy.battery import (
    BatteryConfig,
    step_seconds,
    simulate_battery,
    load_profile,
)
from backend.visibility.disc_visibility import HorizonModel


def flat_horizon(angle=0.0, n=360):
    azimuth = np.arange(n, dtype=float) * (360.0 / n)
    return HorizonModel(
        azimuth,
        np.full(n, angle, dtype=float),
    )


def sun_sample(azimuth=90.0, elevation=2.0, radius=0.25):
    return {
        "time": "2026-11-14T00:00:00Z",
        "azimuth_deg": azimuth,
        "elevation_deg": elevation,
        "angular_radius_deg": radius,
        "distance_km": AU_KM,
    }


def earth_sample(azimuth=90.0, elevation=2.0, radius=0.25):
    return {
        "azimuth_deg": azimuth,
        "elevation_deg": elevation,
        "angular_radius_deg": radius,
    }


# ============================================================
# ECLIPSE CIRCLE OVERLAP
# ============================================================

def test_occultation_no_overlap():
    assert occulted_fraction(2.0, 0.25, 0.5) == pytest.approx(0.0)


def test_occultation_full_coverage():
    assert occulted_fraction(0.0, 0.25, 0.5) == pytest.approx(1.0)


def test_occultation_known_equal_circle_overlap():
    result = occulted_fraction(0.25, 0.25, 0.25)
    assert result == pytest.approx(0.39100221895577)


def test_occultation_matches_brute_force_sampling():
    rng = np.random.default_rng(42)
    count = 300_000
    radius = 1.0
    separation = 0.7

    x = rng.uniform(-radius, radius, count)
    y = rng.uniform(-radius, radius, count)

    in_sun = x**2 + y**2 <= radius**2
    in_earth = (x - separation)**2 + y**2 <= radius**2

    sampled = np.count_nonzero(in_sun & in_earth) / np.count_nonzero(in_sun)
    exact = float(occulted_fraction(separation, radius, radius))

    assert sampled == pytest.approx(exact, abs=0.006)


def test_occultation_decreases_with_separation():
    values = [
        float(occulted_fraction(d, 0.25, 0.25))
        for d in [0.0, 0.1, 0.25, 0.4, 0.5, 1.0]
    ]
    assert all(a >= b for a, b in zip(values, values[1:]))


# ============================================================
# SOLAR FLUX AND PANEL ORIENTATION
# ============================================================

def test_solar_flux_at_one_au():
    assert solar_flux_w_m2(AU_KM) == pytest.approx(1361.0)


def test_solar_flux_obeys_inverse_square_law():
    near = solar_flux_w_m2(AU_KM)
    far = solar_flux_w_m2(2.0 * AU_KM)
    assert far == pytest.approx(near / 4.0)


def test_solar_flux_is_higher_at_perihelion_than_aphelion():
    perihelion = solar_flux_w_m2(147_000_000.0)
    aphelion = solar_flux_w_m2(152_000_000.0)
    assert perihelion > aphelion


def test_vertical_tracking_panel_at_low_sun_elevation():
    panel = PanelConfig(kind="tracking", normal_elevation_deg=0.0)
    result = panel_cosine(120.0, 1.5, panel)
    assert result == pytest.approx(np.cos(np.radians(1.5)))


def test_horizontal_panel_at_low_sun_elevation():
    panel = PanelConfig(kind="fixed", normal_elevation_deg=90.0)
    result = panel_cosine(120.0, 1.5, panel)
    assert result == pytest.approx(np.sin(np.radians(1.5)))


def test_fixed_panel_responds_to_azimuth_difference():
    panel = PanelConfig(
        kind="fixed",
        normal_elevation_deg=0.0,
        normal_azimuth_deg=0.0,
    )
    aligned = panel_cosine(0.0, 10.0, panel)
    perpendicular = panel_cosine(90.0, 10.0, panel)

    assert aligned > perpendicular
    assert perpendicular == pytest.approx(0.0, abs=1e-12)


def test_solar_power_applies_efficiency_dust_and_orientation():
    panel = PanelConfig(
        kind="tracking",
        area_m2=2.0,
        efficiency=0.25,
        dust_loss=0.10,
        degradation=0.05,
        normal_elevation_deg=0.0,
    )

    actual = solar_power_w(AU_KM, 0.0, 0.0, 1.0, panel)
    expected = 1361.0 * 2.0 * 0.25 * 0.90 * 0.95

    assert actual == pytest.approx(expected)


def test_full_sun_energy_over_24_hours():
    panel = PanelConfig(
        kind="tracking",
        area_m2=1.0,
        efficiency=0.28,
        dust_loss=0.0,
        normal_elevation_deg=0.0,
    )

    power = solar_power_w(AU_KM, 0.0, 0.0, 1.0, panel)
    energy_wh = power * 24.0

    assert energy_wh == pytest.approx(1361.0 * 0.28 * 24.0)


def test_invalid_panel_configurations_are_rejected():
    with pytest.raises(ValueError):
        PanelConfig(kind="unknown")

    with pytest.raises(ValueError):
        PanelConfig(area_m2=0.0)

    with pytest.raises(ValueError):
        PanelConfig(efficiency=1.5)

    with pytest.raises(ValueError):
        PanelConfig(dust_loss=-0.1)


# ============================================================
# TERRAIN VISIBILITY AND ECLIPSES
# ============================================================

def test_sun_disc_fully_above_flat_horizon():
    result = sun_visibility_from_samples(
        [sun_sample(elevation=2.0)],
        flat_horizon(0.0),
    )
    assert result[0]["terrain_fraction"] == pytest.approx(1.0)
    assert result[0]["sun_fraction"] == pytest.approx(1.0)
    assert result[0]["coverage_complete"]


def test_sun_disc_half_visible_at_horizon():
    result = sun_visibility_from_samples(
        [sun_sample(elevation=0.0)],
        flat_horizon(0.0),
    )
    assert result[0]["terrain_fraction"] == pytest.approx(0.5, abs=0.04)


def test_sun_disc_hidden_below_horizon():
    result = sun_visibility_from_samples(
        [sun_sample(elevation=-2.0)],
        flat_horizon(0.0),
    )
    assert result[0]["terrain_fraction"] == pytest.approx(0.0)
    assert not result[0]["sun_in_view"]


def test_total_eclipse_removes_sunlight():
    result = sun_visibility_from_samples(
        [sun_sample()],
        flat_horizon(-90.0),
        [earth_sample()],
    )
    assert result[0]["eclipse_factor"] == pytest.approx(0.0)
    assert result[0]["sun_fraction"] == pytest.approx(0.0)


def test_partial_eclipse_reduces_sunlight():
    result = sun_visibility_from_samples(
        [sun_sample()],
        flat_horizon(-90.0),
        [earth_sample(azimuth=90.25)],
    )
    assert 0.0 < result[0]["eclipse_factor"] < 1.0
    assert result[0]["sun_fraction"] == pytest.approx(
        result[0]["eclipse_factor"]
    )


def test_mismatched_earth_sample_count_is_rejected():
    with pytest.raises(ValueError):
        sun_visibility_from_samples(
            [sun_sample(), sun_sample()],
            flat_horizon(-90.0),
            [earth_sample()],
        )


# ============================================================
# BATTERY MODEL
# ============================================================

def test_battery_charging_efficiency():
    config = BatteryConfig(
        capacity_wh=1000.0,
        initial_soc=0.5,
        charge_efficiency=0.95,
    )

    result = simulate_battery(
        power_w=[100.0],
        load_w=[0.0],
        dt_s=[3600.0],
        config=config,
    )

    assert result["total_stored_wh"] == pytest.approx(95.0)
    assert result["final_soc"] == pytest.approx(0.595)


def test_battery_discharging_efficiency():
    config = BatteryConfig(
        capacity_wh=1000.0,
        initial_soc=0.5,
        discharge_efficiency=0.95,
    )

    result = simulate_battery(
        power_w=[0.0],
        load_w=[100.0],
        dt_s=[3600.0],
        config=config,
    )

    assert result["total_drawn_wh"] == pytest.approx(100.0)
    assert result["final_soc"] == pytest.approx(0.5 - 100.0 / 0.95 / 1000.0)


def test_full_battery_wastes_surplus_and_empty_battery_reports_unmet_load():
    full = simulate_battery(
        [200.0],
        [0.0],
        [3600.0],
        BatteryConfig(capacity_wh=100.0, initial_soc=1.0),
    )

    empty = simulate_battery(
        [0.0],
        [100.0],
        [3600.0],
        BatteryConfig(capacity_wh=100.0, initial_soc=0.0),
    )

    assert full["final_soc"] == pytest.approx(1.0)
    assert full["total_wasted_wh"] == pytest.approx(200.0)
    assert empty["final_soc"] == pytest.approx(0.0)
    assert empty["total_unmet_load_wh"] == pytest.approx(100.0)
    assert empty["depleted"][0]


def test_battery_soc_bounds_and_minimum_warning():
    result = simulate_battery(
        [0.0, 0.0, 0.0],
        [100.0, 100.0, 100.0],
        [3600.0, 3600.0, 3600.0],
        BatteryConfig(
            capacity_wh=1000.0,
            initial_soc=0.5,
            min_soc=0.2,
        ),
    )

    assert np.all(result["soc"] >= 0.0)
    assert np.all(result["soc"] <= 1.0)
    assert result["below_minimum"][-1]


def test_step_seconds_and_battery_config_validation():
    assert np.allclose(step_seconds([0.0, 300.0, 600.0]), [300.0, 300.0, 300.0])

    with pytest.raises(ValueError):
        step_seconds([0.0])

    with pytest.raises(ValueError):
        step_seconds([0.0, 0.0])

    with pytest.raises(ValueError):
        BatteryConfig(capacity_wh=0.0)

    with pytest.raises(ValueError):
        BatteryConfig(initial_soc=1.5)


def test_extra_loads_apply_only_inside_requested_window():
    result = load_profile(
        [0.0, 300.0, 600.0, 900.0],
        base_w=20.0,
        extra_loads=[(300.0, 900.0, 10.0)],
    )

    assert np.array_equal(result, [20.0, 30.0, 30.0, 20.0])
