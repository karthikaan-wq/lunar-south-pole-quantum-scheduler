
import math
from datetime import timedelta

import numpy as np
import pytest

from fastapi.testclient import TestClient

from backend.main import app
from backend.physics.earth_geometry import (
    EARTH_EQUATORIAL_RADIUS_KM,
    DEFAULT_TRACK_STEP_MINUTES,
    MAX_TRACK_SAMPLES,
    earth_angular_radius_deg,
    sample_from_vector,
    summarize_track,
    earth_direction,
    earth_track,
)
from backend.physics.kernels import (
    kernels_present,
    load_kernels,
)
from backend.physics.time_system import parse_utc


TEST_UTC = "2026-11-13T00:00:00Z"

LATITUDE = -89.9
LONGITUDE = 129.78
HEIGHT = 0.0

client = TestClient(app)


@pytest.fixture(scope="module")
def spice_ready():
    if not kernels_present():
        pytest.skip("NASA SPICE kernels are not available")

    load_kernels()


# ============================================================
# PURE GEOMETRY TESTS
# ============================================================

def test_earth_angular_radius_is_correct():
    distance = 400000.0

    result = earth_angular_radius_deg(distance)

    expected = math.degrees(
        math.asin(EARTH_EQUATORIAL_RADIUS_KM / distance)
    )

    assert result == pytest.approx(expected)
    assert result > 0.0
    assert result < 2.0


def test_earth_angular_radius_rejects_invalid_distance():
    with pytest.raises(ValueError):
        earth_angular_radius_deg(0)

    with pytest.raises(ValueError):
        earth_angular_radius_deg(EARTH_EQUATORIAL_RADIUS_KM)

    with pytest.raises(ValueError):
        earth_angular_radius_deg(float("inf"))

    with pytest.raises(ValueError):
        earth_angular_radius_deg(float("nan"))

def test_sample_from_vertical_vector():
    distance = 400000.0

    result = sample_from_vector(
        [distance, 0.0, 0.0],
        0.0,
        0.0,
    )

    assert result["azimuth_deg"] == pytest.approx(0.0)
    assert result["elevation_deg"] == pytest.approx(90.0)
    assert result["distance_km"] == pytest.approx(distance)

    assert result["upper_limb_elevation_deg"] > 90.0
    assert result["lower_limb_elevation_deg"] < 90.0

def test_sample_from_vector_contains_all_geometry_fields():
    distance = 400000.0

    result = sample_from_vector(
        [distance, 0.0, 0.0],
        0.0,
        0.0,
    )

    expected_radius = earth_angular_radius_deg(distance)

    assert set(result.keys()) == {
        "azimuth_deg",
        "elevation_deg",
        "distance_km",
        "angular_radius_deg",
        "lower_limb_elevation_deg",
        "upper_limb_elevation_deg",
    }

    assert result["distance_km"] == pytest.approx(distance)
    assert result["angular_radius_deg"] == pytest.approx(
        expected_radius
    )

    assert result["lower_limb_elevation_deg"] == pytest.approx(
        90.0 - expected_radius
    )

    assert result["upper_limb_elevation_deg"] == pytest.approx(
        90.0 + expected_radius
    )


def test_summarize_track_returns_correct_counts():
    samples = [
        {
            "elevation_deg": 10.0,
            "upper_limb_elevation_deg": 11.0,
            "lower_limb_elevation_deg": 9.0,
        },
        {
            "elevation_deg": 0.0,
            "upper_limb_elevation_deg": 1.0,
            "lower_limb_elevation_deg": -1.0,
        },
        {
            "elevation_deg": -10.0,
            "upper_limb_elevation_deg": -9.0,
            "lower_limb_elevation_deg": -11.0,
        },
    ]

    result = summarize_track(samples)

    assert result["sample_count"] == 3

    assert result["minimum_elevation_deg"] == -10.0
    assert result["maximum_elevation_deg"] == 10.0

    assert result["earth_centre_above_flat_horizon_samples"] == 1
    assert result["earth_disc_intersects_flat_horizon_samples"] == 1
    assert result["earth_disc_entirely_above_flat_horizon_samples"] == 1


def test_summarize_track_rejects_empty_samples():
    with pytest.raises(ValueError):
        summarize_track([])


def test_track_rejects_invalid_duration():
    with pytest.raises(ValueError):
        earth_track(
            LATITUDE,
            LONGITUDE,
            HEIGHT,
            TEST_UTC,
            0,
        )

    with pytest.raises(ValueError):
        earth_track(
            LATITUDE,
            LONGITUDE,
            HEIGHT,
            TEST_UTC,
            -1,
        )

    with pytest.raises(ValueError):
        earth_track(
            LATITUDE,
            LONGITUDE,
            HEIGHT,
            TEST_UTC,
            float("nan"),
        )


def test_track_rejects_invalid_step():
    with pytest.raises(ValueError):
        earth_track(
            LATITUDE,
            LONGITUDE,
            HEIGHT,
            TEST_UTC,
            1,
            0,
        )

    with pytest.raises(ValueError):
        earth_track(
            LATITUDE,
            LONGITUDE,
            HEIGHT,
            TEST_UTC,
            1,
            -5,
        )


def test_track_rejects_more_than_maximum_samples():
    with pytest.raises(ValueError, match="maximum allowed"):
        earth_track(
            LATITUDE,
            LONGITUDE,
            HEIGHT,
            TEST_UTC,
            100,
            5,
        )


def test_default_track_step_is_five_minutes():
    assert DEFAULT_TRACK_STEP_MINUTES == 5


def test_maximum_track_samples_is_20000():
    assert MAX_TRACK_SAMPLES == 20000


# ============================================================
# SPICE GEOMETRY TESTS
# ============================================================

def test_earth_direction_returns_valid_geometry(spice_ready):
    result = earth_direction(
        LATITUDE,
        LONGITUDE,
        HEIGHT,
        TEST_UTC,
    )

    assert result["utc"].startswith("2026-11-13")

    assert result["latitude_deg"] == LATITUDE
    assert result["longitude_deg"] == LONGITUDE
    assert result["height_m"] == HEIGHT

    assert 300000 < result["distance_km"] < 500000

    assert 0 <= result["azimuth_deg"] < 360
    assert -90 <= result["elevation_deg"] <= 90

    assert result["angular_radius_deg"] > 0

    assert (
        result["upper_limb_elevation_deg"]
        > result["lower_limb_elevation_deg"]
    )

    assert len(result["earth_vector_moon_fixed_km"]) == 3
    assert len(result["earth_unit_vector_moon_fixed"]) == 3

    assert result["correction"] == "NONE"
    assert result["horizon_model"] == "flat"


def test_earth_direction_unit_vector_is_normalized(spice_ready):
    result = earth_direction(
        LATITUDE,
        LONGITUDE,
        HEIGHT,
        TEST_UTC,
    )

    unit_vector = np.array(
        result["earth_unit_vector_moon_fixed"]
    )

    assert np.linalg.norm(unit_vector) == pytest.approx(
        1.0,
        abs=1e-10,
    )


def test_earth_track_includes_exact_end_time(spice_ready):
    result = earth_track(
        LATITUDE,
        LONGITUDE,
        HEIGHT,
        TEST_UTC,
        duration_days=10 / 1440,
        step_minutes=5,
    )

    samples = result["samples"]

    assert len(samples) == 3
    assert result["sample_count"] == 3

    start = parse_utc(TEST_UTC)
    end = start + timedelta(minutes=10)

    assert parse_utc(samples[0]["utc"]) == start
    assert parse_utc(samples[-1]["utc"]) == end

    assert result["correction"] == "NONE"
    assert result["horizon_model"] == "flat"


def test_earth_track_includes_non_aligned_end_time(spice_ready):
    result = earth_track(
        LATITUDE,
        LONGITUDE,
        HEIGHT,
        TEST_UTC,
        duration_days=12 / 1440,
        step_minutes=5,
    )

    samples = result["samples"]

    assert len(samples) == 4
    assert result["sample_count"] == 4

    start = parse_utc(TEST_UTC)
    expected_end = start + timedelta(minutes=12)

    assert parse_utc(samples[-1]["utc"]) == expected_end

    timestamps = [
        parse_utc(sample["utc"])
        for sample in samples
    ]

    assert len(timestamps) == len(set(timestamps))


def test_earth_track_has_valid_sample_structure(spice_ready):
    result = earth_track(
        LATITUDE,
        LONGITUDE,
        HEIGHT,
        TEST_UTC,
        duration_days=10 / 1440,
        step_minutes=5,
    )

    assert result["latitude_deg"] == LATITUDE
    assert result["longitude_deg"] == LONGITUDE
    assert result["height_m"] == HEIGHT

    assert result["duration_days"] == pytest.approx(10 / 1440)
    assert result["step_minutes"] == 5

    assert result["sample_count"] == len(result["samples"])

    assert result["summary"]["sample_count"] == len(
        result["samples"]
    )

    for sample in result["samples"]:
        assert 0 <= sample["azimuth_deg"] < 360
        assert -90 <= sample["elevation_deg"] <= 90

        assert sample["distance_km"] > 300000
        assert sample["angular_radius_deg"] > 0

        assert (
            sample["upper_limb_elevation_deg"]
            > sample["lower_limb_elevation_deg"]
        )


# ============================================================
# FASTAPI TESTS
# ============================================================

def test_earth_direction_api_valid_request(spice_ready):
    response = client.get(
        "/api/physics/earth-direction",
        params={
            "latitude_deg": LATITUDE,
            "longitude_deg": LONGITUDE,
            "height_m": HEIGHT,
            "utc": TEST_UTC,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["source"] == "SPICE"
    assert data["correction"] == "NONE"
    assert data["horizon_model"] == "flat"

    assert "azimuth_deg" in data
    assert "elevation_deg" in data
    assert "distance_km" in data
    assert "angular_radius_deg" in data
    assert "upper_limb_elevation_deg" in data
    assert "lower_limb_elevation_deg" in data


def test_earth_direction_api_rejects_invalid_latitude():
    response = client.get(
        "/api/physics/earth-direction",
        params={
            "latitude_deg": -200,
            "longitude_deg": LONGITUDE,
            "height_m": HEIGHT,
            "utc": TEST_UTC,
        },
    )

    assert response.status_code == 422


def test_earth_direction_api_rejects_invalid_utc():
    response = client.get(
        "/api/physics/earth-direction",
        params={
            "latitude_deg": LATITUDE,
            "longitude_deg": LONGITUDE,
            "height_m": HEIGHT,
            "utc": "not-a-valid-date",
        },
    )

    assert response.status_code == 422


def test_earth_track_api_valid_request(spice_ready):
    response = client.get(
        "/api/physics/earth-track",
        params={
            "latitude_deg": LATITUDE,
            "longitude_deg": LONGITUDE,
            "height_m": HEIGHT,
            "start_utc": TEST_UTC,
            "duration_days": 10 / 1440,
            "step_minutes": 5,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["source"] == "SPICE"
    assert data["correction"] == "NONE"
    assert data["horizon_model"] == "flat"

    assert data["sample_count"] == 3
    assert len(data["samples"]) == 3

    assert "summary" in data


def test_earth_track_api_rejects_invalid_latitude():
    response = client.get(
        "/api/physics/earth-track",
        params={
            "latitude_deg": -200,
            "longitude_deg": LONGITUDE,
            "height_m": HEIGHT,
            "start_utc": TEST_UTC,
            "duration_days": 1,
        },
    )

    assert response.status_code == 422


def test_earth_track_api_rejects_invalid_duration():
    response = client.get(
        "/api/physics/earth-track",
        params={
            "latitude_deg": LATITUDE,
            "longitude_deg": LONGITUDE,
            "height_m": HEIGHT,
            "start_utc": TEST_UTC,
            "duration_days": 0,
        },
    )

    assert response.status_code == 422


def test_earth_track_api_rejects_invalid_start_utc():
    response = client.get(
        "/api/physics/earth-track",
        params={
            "latitude_deg": LATITUDE,
            "longitude_deg": LONGITUDE,
            "height_m": HEIGHT,
            "start_utc": "invalid-date",
            "duration_days": 1,
        },
    )

    assert response.status_code == 422


def test_earth_track_api_rejects_excessive_sample_count():
    response = client.get(
        "/api/physics/earth-track",
        params={
            "latitude_deg": LATITUDE,
            "longitude_deg": LONGITUDE,
            "height_m": HEIGHT,
            "start_utc": TEST_UTC,
            "duration_days": 100,
            "step_minutes": 5,
        },
    )

    assert response.status_code == 422
