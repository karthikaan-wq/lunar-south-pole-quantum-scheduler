import math

import numpy as np
import pytest

from backend.communications.surface_links import (
    SurfaceLinkSettings,
    forwarding_options,
    great_circle_points,
    intersect_windows,
    link_matrix,
    surface_link,
)
from backend.terrain.projection import MOON_RADIUS_M, lonlat_to_xy
from backend.terrain.terrain_model import Terrain, make_synthetic_terrain


R = MOON_RADIUS_M
SITE_A = (-89.0, 10.0)


def destination(lat, lon, azimuth_deg, distance_m):
    """Return a destination point using spherical geodesic equations."""
    angular = distance_m / R
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    bearing = math.radians(azimuth_deg)

    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular)
        + math.cos(lat1) * math.sin(angular) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(angular) * math.cos(lat1),
        math.cos(angular) - math.sin(lat1) * math.sin(lat2),
    )

    return math.degrees(lat2), math.degrees(lon2)


def flat_terrain(half_size_m=70000.0, pixel_m=100.0):
    return make_synthetic_terrain(
        lambda lat, lon: np.zeros_like(lat),
        half_size_m=half_size_m,
        pixel_m=pixel_m,
    )


def hill_terrain(site, bearing_deg, distance_m, height_m=200.0, width_m=250.0):
    centre = destination(*site, bearing_deg, distance_m)
    centre_x, centre_y = lonlat_to_xy(*centre)

    def elevations(latitudes, longitudes):
        result = np.zeros_like(latitudes, dtype=float)
        for index in np.ndindex(latitudes.shape):
            x, y = lonlat_to_xy(
                float(latitudes[index]),
                float(longitudes[index]),
            )
            radius = math.hypot(x - centre_x, y - centre_y)
            result[index] = height_m * math.exp(
                -0.5 * (radius / width_m) ** 2
            )
        return result

    return make_synthetic_terrain(
        elevations,
        half_size_m=70000.0,
        pixel_m=40.0,
    )


def test_great_circle_points_start_end_and_increase():
    site_b = destination(*SITE_A, 90.0, 3000.0)
    phi, latitudes, longitudes, delta = great_circle_points(
        *SITE_A, *site_b, 51
    )

    assert len(phi) == 51
    assert phi[0] == pytest.approx(0.0)
    assert phi[-1] == pytest.approx(delta)
    assert np.all(np.diff(phi) > 0)
    assert latitudes[0] == pytest.approx(SITE_A[0])
    assert latitudes[-1] == pytest.approx(site_b[0])
    assert longitudes[0] == pytest.approx(SITE_A[1])
    assert longitudes[-1] == pytest.approx(site_b[1])


def test_midpoint_clearance_matches_lunar_curvature():
    distance = 3000.0
    site_b = destination(*SITE_A, 90.0, distance)
    terrain = flat_terrain()

    result = surface_link(
        terrain, SITE_A, site_b, 2.0, 2.0,
        SurfaceLinkSettings(step_m=20.0),
    )

    expected = (R + 2.0) * math.cos(distance / (2.0 * R)) - R

    assert result["min_clearance_m"] == pytest.approx(expected, abs=0.05)
    assert result["min_clearance_at_m"] == pytest.approx(
        distance / 2.0, abs=100.0
    )


def test_radio_horizon_for_two_metre_antennas():
    terrain = flat_terrain()
    horizon = math.sqrt(2.0 * R * 2.0) * 2.0

    inside = destination(*SITE_A, 90.0, horizon * 0.9)
    outside = destination(*SITE_A, 90.0, horizon * 1.1)

    assert surface_link(terrain, SITE_A, inside, 2.0, 2.0)["line_of_sight"]
    assert not surface_link(terrain, SITE_A, outside, 2.0, 2.0)["line_of_sight"]


def test_taller_antennas_extend_radio_horizon():
    terrain = flat_terrain()
    site_b = destination(*SITE_A, 90.0, 8000.0)

    low = surface_link(terrain, SITE_A, site_b, 2.0, 2.0)
    high = surface_link(terrain, SITE_A, site_b, 10.0, 10.0)

    assert not low["line_of_sight"]
    assert high["line_of_sight"]


def test_elevation_angles_are_symmetric_on_flat_ground():
    distance = 3000.0
    site_b = destination(*SITE_A, 90.0, distance)

    result = surface_link(flat_terrain(), SITE_A, site_b, 2.0, 2.0)
    expected = -math.degrees(distance / (2.0 * R))

    assert result["elevation_of_b_from_a_deg"] == pytest.approx(
        expected, abs=0.02
    )
    assert result["elevation_of_a_from_b_deg"] == pytest.approx(
        expected, abs=0.02
    )


def test_surface_link_is_symmetric_when_sites_are_swapped():
    site_b = destination(*SITE_A, 90.0, 3000.0)
    terrain = hill_terrain(SITE_A, 90.0, 1500.0)

    forward = surface_link(terrain, SITE_A, site_b, 2.0, 3.0)
    reverse = surface_link(terrain, site_b, SITE_A, 3.0, 2.0)

    assert forward["distance_m"] == pytest.approx(reverse["distance_m"])
    assert forward["slant_range_m"] == pytest.approx(reverse["slant_range_m"])
    assert forward["min_clearance_m"] == pytest.approx(
        reverse["min_clearance_m"], abs=0.1
    )
    assert forward["line_of_sight"] == reverse["line_of_sight"]


def test_hill_on_path_blocks_surface_link():
    site_b = destination(*SITE_A, 90.0, 3000.0)
    terrain = hill_terrain(SITE_A, 90.0, 1500.0, height_m=200.0)

    result = surface_link(terrain, SITE_A, site_b, 2.0, 2.0)

    assert result["data_complete"]
    assert not result["line_of_sight"]
    assert result["min_clearance_m"] < -20.0
    assert abs(result["min_clearance_at_m"] - 1500.0) < 300.0


def test_hill_off_path_does_not_block_surface_link():
    site_b = destination(*SITE_A, 90.0, 3000.0)
    terrain = hill_terrain(SITE_A, 0.0, 1500.0, height_m=200.0)

    result = surface_link(terrain, SITE_A, site_b, 2.0, 2.0)

    assert result["data_complete"]
    assert result["line_of_sight"]


def test_range_and_fresnel_thresholds_are_applied():
    site_b = destination(*SITE_A, 90.0, 3000.0)
    terrain = flat_terrain()

    short_range = surface_link(
        terrain, SITE_A, site_b, 20.0, 20.0,
        SurfaceLinkSettings(max_range_m=2000.0),
    )
    sufficient_range = surface_link(
        terrain, SITE_A, site_b, 20.0, 20.0,
        SurfaceLinkSettings(max_range_m=5000.0),
    )
    low_fresnel = surface_link(
        terrain, SITE_A, site_b, 2.0, 2.0,
        SurfaceLinkSettings(min_fresnel_ratio=0.6),
    )
    high_fresnel = surface_link(
        terrain, SITE_A, site_b, 20.0, 20.0,
        SurfaceLinkSettings(min_fresnel_ratio=0.6),
    )

    assert not short_range["range_ok"]
    assert not short_range["usable"]
    assert sufficient_range["range_ok"]
    assert sufficient_range["usable"]
    assert not low_fresnel["fresnel_ok"]
    assert not low_fresnel["usable"]
    assert high_fresnel["fresnel_ok"]
    assert high_fresnel["usable"]


def test_outside_terrain_window_makes_link_unusable():
    site_b = destination(*SITE_A, 90.0, 3000.0)
    small_terrain = flat_terrain(half_size_m=1000.0, pixel_m=100.0)

    result = surface_link(small_terrain, SITE_A, site_b)

    assert not result["data_complete"]
    assert not result["line_of_sight"]
    assert not result["usable"]


def test_missing_dem_sample_makes_link_unusable():
    site_b = destination(*SITE_A, 90.0, 3000.0)
    terrain = flat_terrain(half_size_m=70000.0, pixel_m=40.0)

    midpoint = destination(*SITE_A, 90.0, 1500.0)
    x, y = lonlat_to_xy(*midpoint)
    col = int(round((x - terrain.x0) / terrain.pixel_m))
    row = int(round((terrain.y0 - y) / terrain.pixel_m))
    terrain.heights[row - 1:row + 2, col - 1:col + 2] = np.nan

    result = surface_link(
        terrain, SITE_A, site_b,
        settings=SurfaceLinkSettings(step_m=20.0),
    )

    assert not result["data_complete"]
    assert not result["line_of_sight"]
    assert not result["usable"]


def test_link_matrix_evaluates_each_unique_pair_once():
    terrain = flat_terrain()
    sites = {
        "lander": SITE_A,
        "rover_1": destination(*SITE_A, 90.0, 1000.0),
        "rover_2": destination(*SITE_A, 180.0, 1500.0),
    }
    heights = {"lander": 3.0, "rover_1": 1.5, "rover_2": 1.5}

    result = link_matrix(terrain, sites, heights)

    assert len(result) == 3
    assert set(result) == {
        ("lander", "rover_1"),
        ("lander", "rover_2"),
        ("rover_1", "rover_2"),
    }
    assert all(item["usable"] for item in result.values())


def test_invalid_surface_link_settings_raise_value_error():
    with pytest.raises(ValueError):
        SurfaceLinkSettings(frequency_hz=0)
    with pytest.raises(ValueError):
        SurfaceLinkSettings(max_range_m=-1)
    with pytest.raises(ValueError):
        SurfaceLinkSettings(min_clearance_m=-1)
    with pytest.raises(ValueError):
        SurfaceLinkSettings(min_fresnel_ratio=3)
    with pytest.raises(ValueError):
        SurfaceLinkSettings(step_m=0)


def test_intersect_windows_returns_only_overlapping_intervals():
    a = [(0.0, 100.0), (200.0, 400.0)]
    b = [(50.0, 150.0), (300.0, 500.0)]

    assert intersect_windows(a, b) == [
        (50.0, 100.0),
        (300.0, 400.0),
    ]


def test_forwarding_options_support_wait_and_overlapping_windows():
    uplinks = [(1000.0, 1600.0), (3000.0, 3600.0)]
    earth = [(1900.0, 2600.0), (3500.0, 4200.0)]

    result = forwarding_options(uplinks, earth)

    assert len(result) == 2
    assert result[0]["options"][0]["wait_s"] == pytest.approx(300.0)
    assert result[0]["options"][0]["forward_s"] == pytest.approx(700.0)
    assert result[1]["options"][0]["wait_s"] == pytest.approx(0.0)
    assert result[1]["options"][0]["forward_s"] == pytest.approx(600.0)
