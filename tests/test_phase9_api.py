
import pytest

from fastapi.testclient import TestClient

from backend.main import app
from backend.physics.kernels import kernels_present
from backend.terrain.dem_loader import DEFAULT_DEM_PATH
from backend.communications.antenna import AntennaConfig
from backend.communications.direct_to_earth import LinkConstraints


client = TestClient(app)

REAL_DATA_AVAILABLE = (
    kernels_present()
    and DEFAULT_DEM_PATH.is_file()
)

requires_real_data = pytest.mark.skipif(
    not REAL_DATA_AVAILABLE,
    reason="NASA LOLA DEM or required SPICE kernels are unavailable.",
)


def malapert_params():
    return {
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
    }


def test_phase9_api_rejects_invalid_latitude():
    params = malapert_params()
    params["latitude_deg"] = -95.0

    response = client.get(
        "/api/communications/direct-to-earth",
        params=params,
    )

    assert response.status_code == 422


def test_phase9_api_rejects_invalid_time():
    params = malapert_params()
    params["start_utc"] = "not-a-valid-timestamp"

    response = client.get(
        "/api/communications/direct-to-earth",
        params=params,
    )

    assert response.status_code == 422


def test_phase9_api_rejects_invalid_antenna_kind():
    params = malapert_params()
    params["antenna_kind"] = "invalid_antenna"

    response = client.get(
        "/api/communications/direct-to-earth",
        params=params,
    )

    assert response.status_code == 422


def test_phase9_api_rejects_invalid_elevation_limits():
    params = malapert_params()
    params["min_elevation_deg"] = 30.0
    params["max_elevation_deg"] = 10.0

    response = client.get(
        "/api/communications/direct-to-earth",
        params=params,
    )

    assert response.status_code == 422


def test_phase9_api_returns_mocked_link_result(monkeypatch):
    expected_result = {
        "source": "SPICE + NASA LOLA DEM + Phase 9 Link Model",
        "sample_count": 1,
        "link_summary": {
            "total_samples": 1,
            "available_samples": 1,
            "unavailable_samples": 0,
            "availability_percent": 100.0,
            "failure_counts": {
                "terrain_coverage": 0,
                "earth_visible_fraction": 0,
                "earth_clearance": 0,
                "antenna_pointing": 0,
                "sun_exclusion": 0,
            },
        },
        "samples": [
            {
                "utc": "2026-11-14T00:00:00Z",
                "link_available": True,
                "failed_checks": [],
                "first_failure": None,
            }
        ],
    }

    captured = {}

    def fake_direct_to_earth_for_site(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return expected_result

    monkeypatch.setattr(
        "backend.communications.routes.direct_to_earth_for_site",
        fake_direct_to_earth_for_site,
    )

    response = client.get(
        "/api/communications/direct-to-earth",
        params=malapert_params(),
    )

    assert response.status_code == 200
    assert response.json() == expected_result

    assert captured["args"] == ()
    assert captured["kwargs"]["lat_deg"] == pytest.approx(-85.99)
    assert captured["kwargs"]["lon_deg"] == pytest.approx(0.12)
    assert captured["kwargs"]["height_m"] == pytest.approx(4842.28)
    assert captured["kwargs"]["start_utc"] == "2026-11-14T00:00:00Z"
    assert captured["kwargs"]["duration_days"] == pytest.approx(1.0)
    assert captured["kwargs"]["step_minutes"] == pytest.approx(60.0)

    assert isinstance(
        captured["kwargs"]["antenna"],
        AntennaConfig,
    )

    assert isinstance(
        captured["kwargs"]["constraints"],
        LinkConstraints,
    )


@requires_real_data
def test_phase9_api_returns_valid_malapert_link_analysis():
    response = client.get(
        "/api/communications/direct-to-earth",
        params=malapert_params(),
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["source"]
        == "SPICE + NASA LOLA DEM + Phase 9 Link Model"
    )

    assert data["site"]["latitude_deg"] == pytest.approx(-85.99)
    assert data["site"]["longitude_deg"] == pytest.approx(0.12)

    assert data["sample_count"] > 0
    assert len(data["samples"]) == data["sample_count"]

    summary = data["link_summary"]

    assert summary["total_samples"] == data["sample_count"]

    assert (
        summary["available_samples"]
        + summary["unavailable_samples"]
        == summary["total_samples"]
    )

    assert 0.0 <= summary["availability_percent"] <= 100.0

    assert set(summary["failure_counts"]) == {
        "terrain_coverage",
        "earth_visible_fraction",
        "earth_clearance",
        "antenna_pointing",
        "sun_exclusion",
    }

    for sample in data["samples"]:
        assert isinstance(sample["link_available"], bool)

        assert isinstance(sample["checks"], dict)

        assert set(sample["checks"]) == {
            "terrain_coverage",
            "earth_visible_fraction",
            "earth_clearance",
            "antenna_pointing",
            "sun_exclusion",
        }

        if sample["link_available"]:
            assert all(sample["checks"].values())
            assert sample["failed_checks"] == []
            assert sample["first_failure"] is None

        else:
            assert sample["failed_checks"]
            assert sample["first_failure"] in sample["failed_checks"]
