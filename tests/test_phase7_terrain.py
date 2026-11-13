
import math

import numpy as np
import pytest

from backend.terrain.projection import (
    MOON_RADIUS_M,
    lonlat_to_xy,
    xy_to_lonlat,
)
from backend.terrain.terrain_model import Terrain, make_synthetic_terrain
from backend.terrain.horizon import (
    horizon_profile,
    horizon_at_azimuth,
)


def flat_terrain(latitudes, longitudes):
    return np.zeros_like(latitudes, dtype=np.float32)


def test_south_pole_is_map_centre():
    x, y = lonlat_to_xy(-90.0, 0.0)

    assert x == pytest.approx(0.0)
    assert y == pytest.approx(0.0)


def test_projection_map_range_checks():
    _, y80 = lonlat_to_xy(-80.0, 0.0)
    _, y75 = lonlat_to_xy(-75.0, 0.0)
    _, y60 = lonlat_to_xy(-60.0, 0.0)

    assert y80 == pytest.approx(304005.6, abs=1.0)
    assert y75 == pytest.approx(457440.0, abs=100.0)
    assert y60 == pytest.approx(931069.85, abs=1.0)


def test_true_scale_at_south_pole():
    small_angle = 0.001
    x1, y1 = lonlat_to_xy(-90.0 + math.degrees(small_angle), 0.0)

    projected_distance = math.hypot(x1, y1)
    surface_distance = MOON_RADIUS_M * small_angle

    assert projected_distance == pytest.approx(surface_distance, rel=1e-5)


def test_projection_round_trip():
    original_lat = -85.0
    original_lon = 120.0

    x, y = lonlat_to_xy(original_lat, original_lon)
    recovered_lat, recovered_lon = xy_to_lonlat(x, y)

    assert recovered_lat == pytest.approx(original_lat, abs=1e-9)
    assert recovered_lon == pytest.approx(original_lon, abs=1e-9)


def test_projection_orientation():
    x0, y0 = lonlat_to_xy(-80.0, 0.0)
    x90, y90 = lonlat_to_xy(-80.0, 90.0)

    assert abs(x0) < 1e-6
    assert y0 > 0.0

    assert x90 > 0.0
    assert abs(y90) < 1e-6


def test_bilinear_interpolation():
    heights = np.array(
        [
            [0.0, 10.0],
            [20.0, 30.0],
        ],
        dtype=np.float32,
    )

    terrain = Terrain(
        heights=heights,
        x0=0.0,
        y0=10.0,
        pixel_m=10.0,
    )

    assert terrain.height_at(0.0, 10.0) == pytest.approx(0.0)
    assert terrain.height_at(10.0, 10.0) == pytest.approx(10.0)
    assert terrain.height_at(0.0, 0.0) == pytest.approx(20.0)
    assert terrain.height_at(10.0, 0.0) == pytest.approx(30.0)
    assert terrain.height_at(5.0, 5.0) == pytest.approx(15.0)
    assert math.isnan(terrain.height_at(20.0, 20.0))


def test_flat_terrain_horizon_is_near_zero():
    terrain = make_synthetic_terrain(
        flat_terrain,
        half_size_m=40000.0,
        pixel_m=200.0,
    )

    profile = horizon_profile(
        terrain,
        lat_deg=-89.0,
        lon_deg=10.0,
        antenna_height_m=0.0,
        azimuth_step_deg=10.0,
        max_range_m=20000.0,
        step_m=200.0,
    )

    finite = profile["horizon_elevation_deg"][
        np.isfinite(profile["horizon_elevation_deg"])
    ]

    assert finite.size > 0
    assert np.all(np.abs(finite) < 0.005)


def test_antenna_height_creates_horizon_dip():
    terrain = make_synthetic_terrain(
        flat_terrain,
        half_size_m=40000.0,
        pixel_m=200.0,
    )

    profile_ground = horizon_profile(
        terrain,
        lat_deg=-89.0,
        lon_deg=10.0,
        antenna_height_m=0.0,
        azimuth_step_deg=5.0,
        max_range_m=20000.0,
        step_m=200.0,
    )

    profile_antenna = horizon_profile(
        terrain,
        lat_deg=-89.0,
        lon_deg=10.0,
        antenna_height_m=100.0,
        azimuth_step_deg=5.0,
        max_range_m=20000.0,
        step_m=200.0,
    )

    ground = np.nanmean(profile_ground["horizon_elevation_deg"])
    antenna = np.nanmean(profile_antenna["horizon_elevation_deg"])

    assert antenna < ground
    assert antenna < -0.3



def test_eastward_terrain_obstruction():
    def hill(latitudes, longitudes):
        # Observation site.
        site_lat = math.radians(-89.0)
        site_lon = math.radians(10.0)

        # Place the hill 5 km east using a true geographic bearing.
        bearing = math.radians(90.0)
        angular_distance = 5000.0 / MOON_RADIUS_M

        target_lat = math.asin(
            math.sin(site_lat) * math.cos(angular_distance)
            + math.cos(site_lat)
            * math.sin(angular_distance)
            * math.cos(bearing)
        )

        target_lon = site_lon + math.atan2(
            math.sin(bearing)
            * math.sin(angular_distance)
            * math.cos(site_lat),
            math.cos(angular_distance)
            - math.sin(site_lat) * math.sin(target_lat),
        )

        target_x, target_y = lonlat_to_xy(
            math.degrees(target_lat),
            math.degrees(target_lon),
        )

        # Convert synthetic terrain grid to projected coordinates.
        grid_x = np.zeros_like(latitudes)
        grid_y = np.zeros_like(latitudes)

        for row in range(latitudes.shape[0]):
            for col in range(latitudes.shape[1]):
                grid_x[row, col], grid_y[row, col] = lonlat_to_xy(
                    float(latitudes[row, col]),
                    float(longitudes[row, col]),
                )

        hill_distance = np.hypot(
            grid_x - target_x,
            grid_y - target_y,
        )

        return np.where(hill_distance <= 500.0, 500.0, 0.0)

    terrain = make_synthetic_terrain(
        hill,
        half_size_m=40000.0,
        pixel_m=100.0,
    )

    profile = horizon_profile(
        terrain,
        lat_deg=-89.0,
        lon_deg=10.0,
        antenna_height_m=2.0,
        azimuth_step_deg=5.0,
        max_range_m=20000.0,
        step_m=100.0,
    )

    east_horizon = horizon_at_azimuth(profile, 90.0)
    west_horizon = horizon_at_azimuth(profile, 270.0)

    assert east_horizon > 5.0
    assert abs(west_horizon) < 0.5



def test_rays_leaving_map_are_reported():
    terrain = make_synthetic_terrain(
        flat_terrain,
        half_size_m=40000.0,
        pixel_m=200.0,
    )

    profile = horizon_profile(
        terrain,
        lat_deg=-89.0,
        lon_deg=10.0,
        antenna_height_m=2.0,
        azimuth_step_deg=10.0,
        max_range_m=40000.0,
        step_m=200.0,
    )

    assert np.any(profile["ray_reaches_end"])
    assert np.any(~profile["ray_reaches_end"])


def test_site_outside_map_is_rejected():
    terrain = make_synthetic_terrain(
        flat_terrain,
        half_size_m=10000.0,
        pixel_m=200.0,
    )

    with pytest.raises(ValueError, match="observation site"):
        horizon_profile(
            terrain,
            lat_deg=-89.0,
            lon_deg=10.0,
            antenna_height_m=2.0,
            max_range_m=5000.0,
            step_m=200.0,
        )
