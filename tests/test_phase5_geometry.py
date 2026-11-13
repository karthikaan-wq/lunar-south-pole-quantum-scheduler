
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
    to_et,
)
from backend.physics.lunar_frames import (
    rotation_j2000_to_moon,
)
from backend.physics.coordinates import (
    surface_vector_moon_fixed,
)
from backend.physics.earth_geometry import (
    lander_position_j2000,
    local_axes_j2000,
    earth_from_lander_j2000,
    earth_from_lander_moon_fixed,
    lander_state,
)


pytestmark = pytest.mark.skipif(
    not kernels_present(),
    reason="NASA SPICE kernels are not available",
)


@pytest.fixture(scope="module", autouse=True)
def load_spice_kernels():
    load_kernels()


TEST_UTC = "2026-11-13T00:00:00Z"

SITES = [
    (-89.9, 129.78, 0.0),
    (-85.99, 0.12, 100.0),
    (-69.37, 32.32, 0.0),
]


def get_test_et():
    return to_et(parse_utc(TEST_UTC))


def test_lander_position_j2000_is_valid():
    et = get_test_et()

    for lat, lon, height in SITES:
        position = lander_position_j2000(
            lat,
            lon,
            height,
            et,
        )

        assert position.shape == (3,)
        assert np.all(np.isfinite(position))

        # The lander should be close to the Moon's position
        # relative to Earth's centre.
        moon_position, _ = spice.spkpos(
            "MOON",
            et,
            "J2000",
            "NONE",
            "EARTH",
        )

        moon_distance = np.linalg.norm(moon_position)
        lander_distance = np.linalg.norm(position)

        assert abs(lander_distance - moon_distance) < 2000


def test_lander_position_transforms_correctly():
    et = get_test_et()
    lat, lon, height = SITES[0]

    lander_position = lander_position_j2000(
        lat,
        lon,
        height,
        et,
    )

    moon_position, _ = spice.spkpos(
        "MOON",
        et,
        "J2000",
        "NONE",
        "EARTH",
    )

    rotation = rotation_j2000_to_moon(et)

    relative_position = lander_position - np.array(moon_position)

    recovered_site = rotation @ relative_position

    expected_site = surface_vector_moon_fixed(
        lat,
        lon,
        height,
    )

    assert np.allclose(
        recovered_site,
        expected_site,
        atol=1e-6,
    )


def test_local_axes_j2000_are_orthonormal():
    et = get_test_et()

    for lat, lon, height in SITES:
        east, north, up = local_axes_j2000(
            lat,
            lon,
            et,
        )

        axes = [east, north, up]

        for axis in axes:
            assert axis.shape == (3,)
            assert np.all(np.isfinite(axis))
            assert abs(np.linalg.norm(axis) - 1.0) < 1e-10

        assert abs(east @ north) < 1e-10
        assert abs(east @ up) < 1e-10
        assert abs(north @ up) < 1e-10

        assert np.allclose(
            np.cross(east, north),
            up,
            atol=1e-10,
        )


def test_up_axis_points_away_from_moon():
    et = get_test_et()

    for lat, lon, height in SITES:
        east, north, up = local_axes_j2000(
            lat,
            lon,
            et,
        )

        rotation = rotation_j2000_to_moon(et)

        expected_up_moon = (
            surface_vector_moon_fixed(lat, lon, height)
            / np.linalg.norm(
                surface_vector_moon_fixed(lat, lon, height)
            )
        )

        recovered_up = rotation @ up

        assert np.allclose(
            recovered_up,
            expected_up_moon,
            atol=1e-10,
        )


def test_earth_from_lander_j2000_is_valid():
    et = get_test_et()

    for lat, lon, height in SITES:
        vector, distance, unit_vector = earth_from_lander_j2000(
            lat,
            lon,
            height,
            et,
        )

        assert vector.shape == (3,)
        assert np.all(np.isfinite(vector))

        assert distance > 300000
        assert distance < 500000

        assert abs(np.linalg.norm(vector) - distance) < 1e-6
        assert abs(np.linalg.norm(unit_vector) - 1.0) < 1e-10

        assert np.allclose(
            vector / distance,
            unit_vector,
            atol=1e-12,
        )


def test_earth_from_lander_moon_fixed_is_valid():
    et = get_test_et()

    for lat, lon, height in SITES:
        vector, distance, unit_vector = (
            earth_from_lander_moon_fixed(
                lat,
                lon,
                height,
                et,
            )
        )

        assert vector.shape == (3,)
        assert np.all(np.isfinite(vector))

        assert distance > 300000
        assert distance < 500000

        assert abs(np.linalg.norm(vector) - distance) < 1e-6
        assert abs(np.linalg.norm(unit_vector) - 1.0) < 1e-10

        assert np.allclose(
            vector / distance,
            unit_vector,
            atol=1e-12,
        )


def test_earth_direction_matches_between_frames():
    et = get_test_et()
    rotation = rotation_j2000_to_moon(et)

    for lat, lon, height in SITES:
        earth_j2000, distance_j2000, unit_j2000 = (
            earth_from_lander_j2000(
                lat,
                lon,
                height,
                et,
            )
        )

        earth_moon, distance_moon, unit_moon = (
            earth_from_lander_moon_fixed(
                lat,
                lon,
                height,
                et,
            )
        )

        # Convert the J2000 Earth direction into Moon-fixed coordinates.
        converted_vector = rotation @ earth_j2000

        assert np.allclose(
            converted_vector,
            earth_moon,
            atol=1e-5,
        )

        assert abs(distance_j2000 - distance_moon) < 1e-5

        assert np.allclose(
            rotation @ unit_j2000,
            unit_moon,
            atol=1e-10,
        )


def test_lander_state_contains_expected_data():
    et = get_test_et()
    lat, lon, height = SITES[0]

    result = lander_state(
        lat,
        lon,
        height,
        et,
    )

    assert result["utc"].startswith("2026-11-13")

    assert result["latitude_deg"] == lat
    assert result["longitude_deg"] == lon
    assert result["height_m"] == height

    assert len(result["moon_fixed_position_km"]) == 3
    assert len(result["j2000_position_km"]) == 3

    assert set(result["local_axes_j2000"].keys()) == {
        "east",
        "north",
        "up",
    }

    assert set(result["earth_from_lander_j2000"].keys()) == {
        "vector_km",
        "distance_km",
        "unit_vector",
    }

    assert set(
        result["earth_from_lander_moon_fixed"].keys()
    ) == {
        "vector_km",
        "distance_km",
        "unit_vector",
    }

client = TestClient(app)


def test_lander_position_api_valid_request():
    response = client.get(
        "/api/physics/lander-position",
        params={
            "latitude_deg": -89.9,
            "longitude_deg": 129.78,
            "height_m": 0,
            "utc": "2026-11-13T00:00:00Z",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["source"] == "SPICE"
    assert data["latitude_deg"] == -89.9
    assert data["longitude_deg"] == 129.78
    assert "j2000_position_km" in data
    assert "local_axes_j2000" in data


def test_lander_position_api_rejects_invalid_latitude():
    response = client.get(
        "/api/physics/lander-position",
        params={
            "latitude_deg": -200,
            "longitude_deg": 129.78,
            "height_m": 0,
            "utc": "2026-11-13T00:00:00Z",
        },
    )

    assert response.status_code == 422