
import numpy as np
import pytest

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def make_test_profile():
    """Create a deterministic horizon profile for API tests."""

    return {
        "azimuth_deg": np.array([0.0, 90.0, 180.0, 270.0]),
        "horizon_elevation_deg": np.array([1.0, 2.0, 3.0, 4.0]),
        "blocking_distance_m": np.array(
            [1000.0, 1200.0, 1400.0, 1600.0]
        ),
        "ray_reaches_end": np.array(
            [True, True, True, True]
        ),
        "ray_coverage_complete": np.array(
            [True, True, True, True]
        ),
        "horizon_is_complete": np.array(
            [True, True, True, True]
        ),
        "site_height_m": 1250.0,
        "antenna_height_m": 2.0,
        "max_range_m": 4000.0,
        "azimuth_step_deg": 90.0,
        "sample_step_m": 80.0,
    }


def test_terrain_horizon_endpoint_returns_valid_profile(monkeypatch):
    """Verify the endpoint returns terrain and horizon information."""

    captured = {}

    class FakeTerrain:
        pixel_m = 80.0

    def fake_load_dem_terrain(**kwargs):
        captured["loader"] = kwargs
        return FakeTerrain()

    def fake_horizon_profile(**kwargs):
        captured["horizon"] = kwargs
        return make_test_profile()

    monkeypatch.setattr(
        "backend.main.load_dem_terrain",
        fake_load_dem_terrain,
    )

    monkeypatch.setattr(
        "backend.main.horizon_profile",
        fake_horizon_profile,
    )

    response = client.get(
        "/api/terrain/horizon",
        params={
            "latitude_deg": -89.9,
            "longitude_deg": 129.78,
            "antenna_height_m": 2.0,
            "max_range_m": 4000.0,
            "azimuth_step_deg": 5.0,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["source"] == "NASA LOLA DEM"
    assert data["dataset_resolution_m"] == 80.0

    assert data["site"]["latitude_deg"] == -89.9
    assert data["site"]["longitude_deg"] == 129.78
    assert data["site"]["elevation_m"] == 1250.0

    assert data["coverage_summary"] == {
        "complete_directions": 4,
        "total_directions": 4,
        "all_directions_complete": True,
    }

    assert data["horizon"]["azimuth_deg"] == [
        0.0, 90.0, 180.0, 270.0
    ]

    assert len(data["horizon"]["elevation_deg"]) == 4

    assert captured["loader"]["lat_deg"] == -89.9
    assert captured["loader"]["lon_deg"] == 129.78

    assert captured["horizon"]["step_m"] == 80.0


def test_terrain_horizon_returns_503_when_dem_is_missing(monkeypatch):
    """A missing NASA DEM should produce HTTP 503."""

    def fake_load_dem_terrain(**kwargs):
        raise FileNotFoundError("NASA LOLA DEM was not found.")

    monkeypatch.setattr(
        "backend.main.load_dem_terrain",
        fake_load_dem_terrain,
    )

    response = client.get(
        "/api/terrain/horizon",
        params={
            "latitude_deg": -89.9,
            "longitude_deg": 129.78,
        },
    )

    assert response.status_code == 503
    assert "NASA LOLA DEM" in response.json()["detail"]


def test_terrain_horizon_returns_422_for_invalid_terrain(monkeypatch):
    """Invalid terrain input should produce HTTP 422."""

    def fake_load_dem_terrain(**kwargs):
        raise ValueError("Invalid terrain request.")

    monkeypatch.setattr(
        "backend.main.load_dem_terrain",
        fake_load_dem_terrain,
    )

    response = client.get(
        "/api/terrain/horizon",
        params={
            "latitude_deg": -89.9,
            "longitude_deg": 129.78,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid terrain request."


def test_terrain_horizon_rejects_invalid_latitude():
    """FastAPI should reject latitude outside the supported range."""

    response = client.get(
        "/api/terrain/horizon",
        params={
            "latitude_deg": -95.0,
            "longitude_deg": 0.0,
        },
    )

    assert response.status_code == 422
