
import pytest

from fastapi.testclient import TestClient

from backend.main import app
from backend.physics.kernels import kernels_present
from backend.terrain.dem_loader import DEFAULT_DEM_PATH


client = TestClient(app)

REAL_DATA_AVAILABLE = (
    kernels_present()
    and DEFAULT_DEM_PATH.is_file()
)

requires_real_data = pytest.mark.skipif(
    not REAL_DATA_AVAILABLE,
    reason="NASA LOLA DEM or required SPICE kernels are unavailable.",
)


def test_phase8_api_rejects_invalid_latitude():
    response = client.get(
        "/api/visibility/earth-track",
        params={
            "latitude_deg": -95.0,
            "longitude_deg": 0.0,
            "height_m": 0.0,
            "start_utc": "2026-11-14T00:00:00Z",
            "duration_days": 1.0,
        },
    )

    assert response.status_code == 422


def test_phase8_api_rejects_invalid_time():
    response = client.get(
        "/api/visibility/earth-track",
        params={
            "latitude_deg": -85.99,
            "longitude_deg": 0.12,
            "height_m": 4842.28,
            "start_utc": "not-a-valid-timestamp",
            "duration_days": 1.0,
        },
    )

    assert response.status_code == 422


@requires_real_data
def test_phase8_api_returns_valid_malapert_visibility():
    response = client.get(
        "/api/visibility/earth-track",
        params={
            "latitude_deg": -85.99,
            "longitude_deg": 0.12,
            "height_m": 4842.28,
            "start_utc": "2026-11-14T00:00:00Z",
            "duration_days": 1.0,
            "step_minutes": 60.0,
            "antenna_height_m": 2.0,
            "max_range_m": 40000.0,
            "azimuth_step_deg": 0.5,
            "disc_points": 400,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["source"] == "SPICE + NASA LOLA DEM"
    assert data["site"]["latitude_deg"] == pytest.approx(-85.99)
    assert data["site"]["longitude_deg"] == pytest.approx(0.12)

    assert data["sample_count"] > 0
    assert len(data["samples"]) == data["sample_count"]

    for sample in data["samples"]:
        assert 0.0 <= sample["visible_fraction"] <= 1.0

        if sample["margin_deg"] > 0.0:
            assert sample["centre_visible"] is True

    assert data["terrain"]["all_directions_complete"] is True


@requires_real_data
def test_phase8_api_flags_incomplete_terrain_near_dem_boundary():
    response = client.get(
        "/api/visibility/earth-track",
        params={
            "latitude_deg": -80.5,
            "longitude_deg": 0.0,
            "height_m": 0.0,
            "start_utc": "2026-11-14T00:00:00Z",
            "duration_days": 1.0,
            "step_minutes": 60.0,
            "antenna_height_m": 2.0,
            "max_range_m": 40000.0,
            "azimuth_step_deg": 5.0,
            "disc_points": 100,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["terrain"]["all_directions_complete"] is False
    assert (
        data["terrain"]["complete_directions"]
        < data["terrain"]["total_directions"]
    )

    assert any(
        not sample["coverage_complete"]
        for sample in data["samples"]
    )

