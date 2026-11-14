
import numpy as np
import pytest

from backend.terrain.terrain_model import make_synthetic_terrain
from backend.terrain.horizon import horizon_profile

from backend.visibility.disc_visibility import HorizonModel
from backend.visibility.earth_visibility import visibility_from_samples


SITE_LAT = -89.9
SITE_LON = 0.0


def block_east(latitudes, longitudes):
    """
    Create a 500 m raised terrain wall east of the observation site.

    The wall occupies:
        Distance: 4–6 km
        Azimuth: 85–95 degrees

    All other terrain is flat.
    """

    lat1 = np.radians(SITE_LAT)
    lon1 = np.radians(SITE_LON)

    lat2 = np.radians(latitudes)
    lon2 = np.radians(longitudes)

    delta_lon = lon2 - lon1

    # Great-circle distance from the observation site.
    sin_dlat = np.sin((lat2 - lat1) / 2.0)
    sin_dlon = np.sin(delta_lon / 2.0)

    a = (
        sin_dlat ** 2
        + np.cos(lat1) * np.cos(lat2) * sin_dlon ** 2
    )

    central_angle = 2.0 * np.arctan2(
        np.sqrt(a),
        np.sqrt(np.maximum(0.0, 1.0 - a)),
    )

    distance_m = 1_737_400.0 * central_angle

    # Initial bearing, measured clockwise from north.
    bearing = np.degrees(
        np.arctan2(
            np.sin(delta_lon) * np.cos(lat2),
            np.cos(lat1) * np.sin(lat2)
            - np.sin(lat1) * np.cos(lat2) * np.cos(delta_lon),
        )
    ) % 360.0

    wall = (
        (distance_m >= 4000.0)
        & (distance_m <= 6000.0)
        & (bearing >= 85.0)
        & (bearing <= 95.0)
    )

    return np.where(wall, 500.0, 0.0)


@pytest.fixture(scope="module")
def terrain_horizon():
    """
    Generate synthetic terrain and calculate its real horizon profile.
    """

    terrain = make_synthetic_terrain(
        block_east,
        half_size_m=20000.0,
        pixel_m=100.0,
    )

    profile = horizon_profile(
        terrain,
        lat_deg=SITE_LAT,
        lon_deg=SITE_LON,
        antenna_height_m=2.0,
        azimuth_step_deg=0.5,
        max_range_m=12000.0,
        step_m=100.0,
    )

    return HorizonModel.from_profile(
        profile,
        angle_key="horizon_elevation_deg",
        complete_key="horizon_is_complete",
    )


def make_sample(azimuth, elevation, radius=0.9):
    return {
        "utc": "2026-11-10T00:00:00Z",
        "azimuth_deg": azimuth,
        "elevation_deg": elevation,
        "angular_radius_deg": radius,
    }


def test_synthetic_wall_creates_elevated_east_horizon(
    terrain_horizon,
):
    east_horizon = float(
        terrain_horizon.horizon_at(90.0)
    )

    assert east_horizon > 0.0


def test_earth_disc_is_blocked_behind_east_wall(
    terrain_horizon,
):
    results = visibility_from_samples(
        [
            make_sample(
                azimuth=90.0,
                elevation=4.0,
            )
        ],
        terrain_horizon,
    )

    result = results[0]

    assert result["visible_fraction"] == 0.0
    assert result["blocked"] is True
    assert result["coverage_complete"] is True


def test_earth_disc_becomes_visible_above_east_wall(
    terrain_horizon,
):
    results = visibility_from_samples(
        [
            make_sample(
                azimuth=90.0,
                elevation=15.0,
            )
        ],
        terrain_horizon,
    )

    result = results[0]

    assert result["visible_fraction"] == 1.0
    assert result["fully_visible"] is True
    assert result["coverage_complete"] is True


def test_earth_disc_remains_visible_away_from_wall(
    terrain_horizon,
):
    results = visibility_from_samples(
        [
            make_sample(
                azimuth=30.0,
                elevation=4.0,
            )
        ],
        terrain_horizon,
    )

    result = results[0]

    assert result["visible_fraction"] > 0.0
    assert result["coverage_complete"] is True
