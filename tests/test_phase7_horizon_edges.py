
import math

import pytest

import numpy as np

from backend.terrain.terrain_model import make_synthetic_terrain
from backend.terrain.horizon import horizon_profile


def flat_terrain(latitudes, longitudes):
    return np.zeros_like(latitudes, dtype=np.float32)


def test_horizon_samples_exact_maximum_range():
    class RecordingTerrain:
        pixel_m = 200.0

        def __init__(self):
            self.sample_distances = []

        def height_at(self, x, y):
            self.sample_distances.append(math.hypot(x, y))
            return 0.0

    terrain = RecordingTerrain()

    profile = horizon_profile(
        terrain,
        lat_deg=-90.0,
        lon_deg=0.0,
        antenna_height_m=2.0,
        azimuth_step_deg=10.0,
        max_range_m=1000.0,
        step_m=300.0,
    )

    expected_projected_radius = (
        2.0 * 1_737_400.0
        * math.tan(1000.0 / (2.0 * 1_737_400.0))
    )

    assert max(terrain.sample_distances) == pytest.approx(
        expected_projected_radius,
        abs=0.01,
    )

    assert profile["ray_reaches_end"].all()
    assert profile["ray_coverage_complete"].all()
    assert profile["horizon_is_complete"].all()


def test_missing_middle_terrain_is_detected():
    class TerrainWithMissingStrip:
        pixel_m = 100.0

        def height_at(self, x, y):
            distance = math.hypot(x, y)

            if y > 0 and abs(x) < 50 and 400 < distance < 600:
                return float("nan")

            return 0.0

    terrain = TerrainWithMissingStrip()

    profile = horizon_profile(
        terrain,
        lat_deg=-90.0,
        lon_deg=0.0,
        antenna_height_m=2.0,
        azimuth_step_deg=10.0,
        max_range_m=1000.0,
        step_m=100.0,
    )

    north_index = int(
        np.where(profile["azimuth_deg"] == 0.0)[0][0]
    )

    assert profile["ray_reaches_end"][north_index]
    assert not profile["ray_coverage_complete"][north_index]
    assert not profile["horizon_is_complete"][north_index]


def test_missing_terrain_marks_horizon_incomplete():
    class PartiallyMissingTerrain:
        pixel_m = 100.0

        def height_at(self, x, y):
            if x > 300:
                return float("nan")
            return 0.0

    terrain = PartiallyMissingTerrain()

    profile = horizon_profile(
        terrain,
        lat_deg=-90.0,
        lon_deg=0.0,
        antenna_height_m=2.0,
        azimuth_step_deg=10.0,
        max_range_m=1000.0,
        step_m=100.0,
    )

    east_index = int(
        np.where(profile["azimuth_deg"] == 90.0)[0][0]
    )

    assert not profile["ray_reaches_end"][east_index]
    assert not profile["ray_coverage_complete"][east_index]
    assert not profile["horizon_is_complete"][east_index]
    assert np.isfinite(
        profile["horizon_elevation_deg"][east_index]
    )
