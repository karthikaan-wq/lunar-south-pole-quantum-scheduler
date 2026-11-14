import pytest

from fastapi.testclient import TestClient

from backend.main import app
from backend.physics.kernels import kernels_present
from backend.terrain.dem_loader import DEFAULT_DEM_PATH
from backend.communications.antenna import AntennaConfig
from backend.communications.direct_to_earth import LinkConstraints
from backend.communications.windows import WindowSettings


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
        "resolution_s": 60.0,
        "max_gap_s": 600.0,
        "min_duration_s": 1800.0,
    }


def test_phase10_api_rejects_invalid_latitude():
    params = malapert_params()
    params["latitude_deg"] = -95.0

    response = client.get(
        "/api/communications/windows",
        params=params,
    )

    assert response.status_code == 422


def test_phase10_api_rejects_invalid_timestamp():
    params = malapert_params()
    params["start_utc"] = "not-a-valid-timestamp"

    response = client.get(
        "/api/communications/windows",
        params=params,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("resolution_s", 0),
        ("max_gap_s", -1),
        ("min_duration_s", -1),
    ],
)
def test_phase10_api_rejects_invalid_window_settings(setting, value):
    params = malapert_params()
    params[setting] = value

    response = client.get(
        "/api/communications/windows",
        params=params,
    )

    assert response.status_code == 422


def test_phase10_api_returns_mocked_windows(monkeypatch):
    expected_result = {
        "source": (
            "SPICE + NASA LOLA DEM + Phase 9 Direct-to-Earth "
            "Link Model + Phase 10 Refined Windows"
        ),
        "sample_count": 2,
        "windows": [
            {
                "start_utc": "2026-11-14T01:00:00Z",
                "end_utc": "2026-11-14T03:00:00Z",
                "duration_s": 7200.0,
            }
        ],
    }

    captured = {}

    def fake_windows_for_site(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return expected_result

    monkeypatch.setattr(
        "backend.communications.routes.windows_for_site",
        fake_windows_for_site,
    )

    response = client.get(
        "/api/communications/windows",
        params=malapert_params(),
    )

    assert response.status_code == 200
    assert response.json() == expected_result

    assert captured["args"] == ()

    kwargs = captured["kwargs"]

    assert kwargs["lat_deg"] == pytest.approx(-85.99)
    assert kwargs["lon_deg"] == pytest.approx(0.12)
    assert kwargs["height_m"] == pytest.approx(4842.28)
    assert kwargs["start_utc"] == "2026-11-14T00:00:00Z"
    assert kwargs["duration_days"] == pytest.approx(1.0)
    assert kwargs["step_minutes"] == pytest.approx(60.0)
    assert kwargs["n_disc_points"] == 400

    assert isinstance(kwargs["antenna"], AntennaConfig)
    assert isinstance(kwargs["constraints"], LinkConstraints)
    assert isinstance(kwargs["window_settings"], WindowSettings)

    settings = kwargs["window_settings"]

    assert settings.resolution_s == pytest.approx(60.0)
    assert settings.max_gap_s == pytest.approx(600.0)
    assert settings.min_duration_s == pytest.approx(1800.0)


@requires_real_data
def test_phase10_api_returns_valid_real_malapert_windows():
    response = client.get(
        "/api/communications/windows",
        params=malapert_params(),
    )

    assert response.status_code == 200

    data = response.json()

    assert "Phase 10 Refined Windows" in data["source"]

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

    assert isinstance(data["windows"], list)
    assert isinstance(data["rejected"], list)

    for window in data["windows"]:
        assert window["duration_s"] >= 1800.0
        assert window["end_utc"] > window["start_utc"]
