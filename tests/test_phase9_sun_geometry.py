
import math

import pytest

from backend.physics.kernels import kernels_present
from backend.physics.sun_geometry import (
    SUN_RADIUS_KM,
    sun_at_times,
)


def test_empty_timestamp_list_returns_empty_result():
    assert sun_at_times(
        lat_deg=-89.0,
        lon_deg=0.0,
        height_m=0.0,
        time_strings=[],
    ) == []


@pytest.mark.parametrize(
    "lat, lon, height",
    [
        (float("nan"), 0.0, 0.0),
        (-89.0, float("inf"), 0.0),
        (-89.0, 0.0, float("nan")),
    ],
)
def test_non_finite_site_values_are_rejected(lat, lon, height):
    with pytest.raises(ValueError):
        sun_at_times(lat, lon, height, ["2026-11-14T00:00:00Z"])


@pytest.mark.parametrize(
    "lat, lon",
    [
        (-91.0, 0.0),
        (91.0, 0.0),
        (-89.0, 181.0),
        (-89.0, -181.0),
    ],
)
def test_out_of_range_coordinates_are_rejected(lat, lon):
    with pytest.raises(ValueError):
        sun_at_times(lat, lon, 0.0, ["2026-11-14T00:00:00Z"])


def test_timestamp_argument_must_be_a_list_or_tuple():
    with pytest.raises(TypeError):
        sun_at_times(
            -89.0,
            0.0,
            0.0,
            "2026-11-14T00:00:00Z",
        )


@pytest.mark.parametrize(
    "timestamps",
    [
        [""],
        ["   "],
        [None],
    ],
)
def test_invalid_timestamps_are_rejected(timestamps):
    with pytest.raises(ValueError):
        sun_at_times(-89.0, 0.0, 0.0, timestamps)


@pytest.mark.skipif(
    not kernels_present(),
    reason="Required SPICE kernels are not installed.",
)
def test_sun_geometry_returns_valid_spice_results():
    timestamps = [
        "2026-11-14T00:00:00Z",
        "2026-11-14T06:00:00Z",
        "2026-11-14T12:00:00Z",
    ]

    results = sun_at_times(
        lat_deg=-89.0,
        lon_deg=0.0,
        height_m=0.0,
        time_strings=timestamps,
    )

    assert len(results) == len(timestamps)

    for result, timestamp in zip(results, timestamps):
        assert result["utc"] == timestamp

        assert math.isfinite(result["azimuth_deg"])
        assert 0.0 <= result["azimuth_deg"] < 360.0

        assert math.isfinite(result["elevation_deg"])
        assert -90.0 <= result["elevation_deg"] <= 90.0

        assert math.isfinite(result["distance_km"])
        assert result["distance_km"] > SUN_RADIUS_KM

        assert math.isfinite(result["angular_radius_deg"])
        assert 0.0 < result["angular_radius_deg"] < 1.0


@pytest.mark.skipif(
    not kernels_present(),
    reason="Required SPICE kernels are not installed.",
)
def test_sun_angular_radius_matches_distance():
    result = sun_at_times(
        lat_deg=-89.0,
        lon_deg=0.0,
        height_m=0.0,
        time_strings=["2026-11-14T00:00:00Z"],
    )[0]

    expected_radius = math.degrees(
        math.asin(SUN_RADIUS_KM / result["distance_km"])
    )

    assert result["angular_radius_deg"] == pytest.approx(
        expected_radius,
        rel=1e-10,
    )
