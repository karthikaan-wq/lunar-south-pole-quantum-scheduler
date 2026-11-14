
import math
import pytest

from backend.communications.antenna import (
    AntennaConfig,
    angular_separation_deg,
    azimuth_in_range,
    pointing_ok,
)


def test_identical_directions_have_zero_separation():
    result = angular_separation_deg(45, 30, 45, 30)

    assert result == pytest.approx(0.0, abs=1e-10)


def test_opposite_directions_have_180_degree_separation():
    result = angular_separation_deg(0, 0, 180, 0)

    assert result == pytest.approx(180.0)


def test_azimuth_range_crossing_north():
    assert azimuth_in_range(350, 300, 60)
    assert azimuth_in_range(20, 300, 60)
    assert azimuth_in_range(60, 300, 60)
    assert not azimuth_in_range(180, 300, 60)


def test_full_circle_azimuth_range():
    assert azimuth_in_range(200, 0, 360)
    assert azimuth_in_range(350, 10, 370)


def test_steerable_antenna_respects_mechanical_limits():
    config = AntennaConfig(
        kind="steerable",
        min_elevation_deg=-10,
        max_elevation_deg=90,
        min_azimuth_deg=0,
        max_azimuth_deg=360,
    )

    assert pointing_ok(120, 30, config)
    assert pointing_ok(120, -10, config)
    assert pointing_ok(120, 90, config)

    assert not pointing_ok(120, -10.1, config)
    with pytest.raises(ValueError):pointing_ok(120, 90.1, config)


def test_steerable_antenna_respects_azimuth_limits():
    config = AntennaConfig(
        kind="steerable",
        min_azimuth_deg=300,
        max_azimuth_deg=60,
    )

    assert pointing_ok(350, 20, config)
    assert pointing_ok(30, 20, config)
    assert not pointing_ok(180, 20, config)


def test_fixed_antenna_accepts_target_inside_beam():
    config = AntennaConfig(
        kind="fixed",
        boresight_azimuth_deg=90,
        boresight_elevation_deg=30,
        half_beamwidth_deg=5,
    )

    assert pointing_ok(90, 30, config)
    assert pointing_ok(92, 32, config)


def test_fixed_antenna_rejects_target_outside_beam():
    config = AntennaConfig(
        kind="fixed",
        boresight_azimuth_deg=90,
        boresight_elevation_deg=30,
        half_beamwidth_deg=5,
    )

    assert not pointing_ok(110, 30, config)
    assert not pointing_ok(90, 40, config)


def test_invalid_antenna_configuration_is_rejected():
    with pytest.raises(ValueError):
        AntennaConfig(kind="dish")

    with pytest.raises(ValueError):
        AntennaConfig(min_elevation_deg=20, max_elevation_deg=10)

    with pytest.raises(ValueError):
        AntennaConfig(half_beamwidth_deg=0)


def test_non_finite_angles_are_rejected():
    with pytest.raises(ValueError):
        angular_separation_deg(math.nan, 0, 0, 0)

    with pytest.raises(ValueError):
        pointing_ok(0, math.inf, AntennaConfig())
