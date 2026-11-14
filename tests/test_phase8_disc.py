import numpy as np
import pytest

from backend.terrain import horizon
from backend.visibility.disc_visibility import (
    HorizonModel,
    disc_pattern,
    disc_sky_points,
)


def make_horizon(step_deg=45.0, value=0.0, complete=None):
    azimuth = np.arange(0.0, 360.0, step_deg)
    horizon = np.full(len(azimuth), value)

    return HorizonModel(
        azimuth,
        horizon,
        complete,
    )


def angular_separation_deg(az1, el1, az2, el2):
    az1 = np.radians(az1)
    el1 = np.radians(el1)
    az2 = np.radians(az2)
    el2 = np.radians(el2)

    cosine = (
        np.sin(el1) * np.sin(el2)
        + np.cos(el1) * np.cos(el2) * np.cos(az1 - az2)
    )

    return np.degrees(
        np.arccos(np.clip(cosine, -1.0, 1.0))
    )


# ============================================================
# DISC DISTRIBUTION TESTS
# ============================================================

def test_disc_pattern_has_correct_number_of_points():
    radius, phi = disc_pattern(400)

    assert len(radius) == 400
    assert len(phi) == 400


def test_disc_pattern_is_inside_unit_circle():
    radius, _ = disc_pattern(400)

    assert np.all(radius > 0.0)
    assert np.all(radius < 1.0)


def test_disc_pattern_is_area_uniform():
    radius, _ = disc_pattern(400)

    mean_squared_radius = np.mean(radius ** 2)

    assert mean_squared_radius == pytest.approx(
        0.5,
        abs=0.002,
    )


def test_disc_pattern_uses_golden_angle():
    _, phi = disc_pattern(400)

    differences = np.diff(phi)

    assert np.allclose(
        differences,
        differences[0],
    )


def test_disc_pattern_rejects_invalid_point_count():
    with pytest.raises(ValueError):
        disc_pattern(0)

    with pytest.raises(ValueError):
        disc_pattern(-10)


# ============================================================
# EARTH DISC SKY GEOMETRY TESTS
# ============================================================

def test_disc_sky_points_stay_inside_angular_radius():
    centre_az = 120.0
    centre_el = 25.0
    radius = 0.9

    point_az, point_el = disc_sky_points(
        centre_az,
        centre_el,
        radius,
        n_points=400,
    )

    separation = angular_separation_deg(
        centre_az,
        centre_el,
        point_az[0],
        point_el[0],
    )

    assert np.all(separation <= radius + 1e-7)


def test_disc_sky_points_have_expected_shape():
    az, el = disc_sky_points(
        [10.0, 20.0],
        [5.0, 15.0],
        [0.9, 0.8],
        n_points=400,
    )

    assert az.shape == (2, 400)
    assert el.shape == (2, 400)


def test_disc_sky_points_support_north_azimuth_wrap():
    az, el = disc_sky_points(
        0.0,
        0.0,
        0.9,
        n_points=400,
    )

    assert np.all(az >= 0.0)
    assert np.all(az < 360.0)

    assert np.any(az > 350.0)
    assert np.any(az < 10.0)


def test_disc_sky_points_reject_mismatched_inputs():
    with pytest.raises(ValueError):
        disc_sky_points(
            [10.0, 20.0],
            [5.0],
            [0.9, 0.8],
        )


# ============================================================
# HORIZON MODEL TESTS
# ============================================================

def test_constant_horizon_interpolation():
    horizon = make_horizon(
        step_deg=45.0,
        value=5.0,
    )

    values = horizon.horizon_at(
        [0.0, 45.0, 90.0, 180.0, 359.0]
    )

    assert np.allclose(values, 5.0)


def test_horizon_interpolates_across_north():
    azimuth = np.arange(0.0, 360.0, 45.0)

    elevations = np.array([
        0.0,
        10.0,
        20.0,
        30.0,
        40.0,
        50.0,
        60.0,
        70.0,
    ])

    horizon = HorizonModel(
        azimuth,
        elevations,
    )

    result = horizon.horizon_at(337.5)

    assert result == pytest.approx(35.0)


def test_horizon_supports_non_divisor_azimuth_spacing():
    azimuth = np.arange(0.0, 360.0, 7.0)
    elevations = np.full(len(azimuth), 5.0)

    horizon = HorizonModel(
        azimuth,
        elevations,
    )

    assert len(azimuth) == 52
    assert azimuth[-1] == pytest.approx(357.0)

    assert horizon.horizon_at(358.5) == pytest.approx(5.0)
    assert horizon.horizon_at(359.5) == pytest.approx(5.0)

    assert horizon.complete_at(358.5)
    assert horizon.complete_at(359.5)


def test_horizon_accepts_unsorted_azimuths():
    azimuth = np.array([
        180.0,
        0.0,
        270.0,
        90.0,
    ])

    elevations = np.array([
        4.0,
        1.0,
        5.0,
        2.0,
    ])

    # Four samples are intentionally insufficient.
    with pytest.raises(ValueError):
        HorizonModel(
            azimuth,
            elevations,
        )

    azimuth = np.arange(0.0, 360.0, 45.0)
    elevations = np.arange(8.0, dtype=float)

    order = np.array([3, 0, 6, 1, 7, 2, 5, 4])

    horizon = HorizonModel(
        azimuth[order],
        elevations[order],
    )

    assert horizon.horizon_at(0.0) == pytest.approx(0.0)

def test_incomplete_terrain_is_detected():
    complete = np.ones(8, dtype=bool)
    complete[0] = False

    horizon = make_horizon(
        step_deg=45.0,
        complete=complete,
    )

    result = horizon.complete_at(
        [0.0, 90.0, 180.0]
    )

    assert not result[0]
    assert result[1]
    assert result[2]


def test_nan_horizon_is_marked_incomplete():
    azimuth = np.arange(0.0, 360.0, 45.0)

    elevations = np.zeros(8)
    elevations[2] = np.nan

    horizon = HorizonModel(
        azimuth,
        elevations,
    )

    assert not horizon.complete_at(90.0)
    assert np.isfinite(horizon.horizon_at(90.0))


def test_horizon_rejects_irregular_spacing():
    azimuth = np.array([
        0.0,
        45.0,
        90.0,
        135.0,
        180.0,
        225.0,
        270.0,
        320.0,
    ])

    elevations = np.zeros(8)

    with pytest.raises(ValueError):
        HorizonModel(
            azimuth,
            elevations,
        )


def test_horizon_rejects_mismatched_arrays():
    with pytest.raises(ValueError):
        HorizonModel(
            np.arange(0.0, 360.0, 45.0),
            np.zeros(7),
        )