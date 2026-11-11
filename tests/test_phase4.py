
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
import spiceypy as spice
from fastapi.testclient import TestClient
from backend.main import app

from backend.physics.kernels import (
    kernels_present,
    load_kernels,
)

from backend.physics.time_system import (
    parse_utc,
    utc_string,
    to_et,
    et_to_utc,
)

from backend.physics.lunar_frames import (
    ME_FRAME,
    frame_is_known,
    rotation_j2000_to_moon,
)

from backend.physics.ephemeris import (
    earth_moon_state,
    earth_angular_radius_deg,
    SPEED_OF_LIGHT_KM_S,
)


pytestmark = pytest.mark.skipif(
    not kernels_present(),
    reason="NASA SPICE kernels are not available",
)
client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def load_spice_kernels():
    load_kernels()


def test_j2000_epoch_conversion():
    moment = datetime(
        2000, 1, 1, 12, 0, 0,
        tzinfo=timezone.utc
    )

    et = to_et(moment)

    assert abs(et - 64.184) < 0.01


def test_utc_roundtrip():
    moment = datetime(
        2026, 11, 10, 0, 0, 0,
        tzinfo=timezone.utc
    )

    et = to_et(moment)
    result = et_to_utc(et)

    assert result.startswith("2026-11-10T00:00:00")


def test_parse_utc_accepts_z():
    moment = parse_utc("2026-11-10T00:00:00Z")

    assert moment.tzinfo == timezone.utc
    assert moment.year == 2026
    assert moment.month == 11
    assert moment.day == 10


def test_parse_utc_accepts_plain_timestamp():
    moment = parse_utc("2026-11-10T00:00:00")

    assert moment.tzinfo == timezone.utc


def test_lunar_frame_is_known():
    assert frame_is_known(ME_FRAME)


def test_earth_moon_distance_is_realistic():
    moment = datetime(
        2026, 11, 10, 0, 0, 0,
        tzinfo=timezone.utc
    )

    result = earth_moon_state(moment)

    assert 356000 < result["distance_km"] < 407000


def test_light_time_matches_distance():
    moment = datetime(
        2026, 11, 10, 0, 0, 0,
        tzinfo=timezone.utc
    )

    result = earth_moon_state(moment)

    expected = (
        result["distance_km"] / SPEED_OF_LIGHT_KM_S
    )

    assert abs(result["light_time_s"] - expected) < 0.01


def test_rotation_matrix_is_orthogonal():
    moment = datetime(
        2026, 11, 10, 0, 0, 0,
        tzinfo=timezone.utc
    )

    et = to_et(moment)

    matrix = rotation_j2000_to_moon(et)

    identity = np.eye(3)

    assert np.allclose(
        matrix @ matrix.T,
        identity,
        atol=1e-10
    )

    assert abs(np.linalg.det(matrix) - 1.0) < 1e-10


def test_rotation_matches_spice_direct_lookup():
    moment = datetime(
        2026, 11, 10, 0, 0, 0,
        tzinfo=timezone.utc
    )

    et = to_et(moment)

    actual = rotation_j2000_to_moon(et)

    expected = spice.pxform(
        "J2000",
        ME_FRAME,
        et
    )

    assert np.allclose(actual, expected)


def test_sub_earth_libration_ranges():
    start = datetime(
        2026, 11, 10, 0, 0, 0,
        tzinfo=timezone.utc
    )

    longitudes = []
    latitudes = []

    for sample in range(56):
        moment = start + timedelta(hours=12 * sample)

        result = earth_moon_state(moment)

        longitudes.append(result["sub_earth_lon_deg"])
        latitudes.append(result["sub_earth_lat_deg"])

    assert max(abs(value) for value in longitudes) < 10
    assert max(abs(value) for value in latitudes) < 8

    assert max(longitudes) - min(longitudes) > 8
    assert max(latitudes) - min(latitudes) > 8


def test_earth_angular_radius():
    radius = earth_angular_radius_deg(399769.95)

    assert 0.89 < radius < 1.03


    
def test_earth_moon_api_returns_real_spice_data():
    response = client.get(
        "/api/physics/earth-moon",
        params={"utc": "2026-11-10T00:00:00Z"}
    )

    assert response.status_code == 200

    data = response.json()

    assert data["source"] == "SPICE"
    assert 350000 < data["distance_km"] < 410000
    assert "apparent_distance_km" in data
    assert "light_time_s" in data
    assert "earth_angular_radius_deg" in data
    assert data["moon_frame"] == ME_FRAME


def test_earth_moon_api_rejects_invalid_utc():
    response = client.get(
        "/api/physics/earth-moon",
        params={"utc": "not-a-date"}
    )

    assert response.status_code == 422