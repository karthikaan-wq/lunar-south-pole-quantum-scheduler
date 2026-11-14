import pytest

from fastapi.testclient import TestClient

from backend.main import app
from backend.physics.kernels import KernelsMissing, kernels_present
from backend.terrain.dem_loader import DEFAULT_DEM_PATH

from backend.energy.battery import BatteryConfig
from backend.energy.solar_power import PanelConfig


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
        "start_utc": "2026-11-14T00:00:00Z",
        "duration_days": 1.0,
        "step_minutes": 60.0,
        "panel_kind": "tracking",
        "panel_area_m2": 3.0,
        "panel_efficiency": 0.28,
        "panel_dust_loss": 0.05,
        "panel_height_m": 3.0,
        "battery_capacity_wh": 2000.0,
        "battery_initial_soc": 0.8,
        "battery_min_soc": 0.2,
        "base_load_w": 60.0,
        "max_range_m": 100000.0,
        "azimuth_step_deg": 0.25,
        "sunlit_threshold": 0.5,
        "disc_points": 400,
        "include_samples": True,
    }


def test_phase11_api_rejects_invalid_coordinates_timestamp_and_settings():
    params = malapert_params()
    params["latitude_deg"] = -95.0

    response = client.get(
        "/api/energy/site-timeline",
        params=params,
    )
    assert response.status_code == 422

    params = malapert_params()
    params["start_utc"] = "not-a-valid-timestamp"

    response = client.get(
        "/api/energy/site-timeline",
        params=params,
    )
    assert response.status_code == 422

    params = malapert_params()
    params["panel_kind"] = "invalid-panel"

    response = client.get(
        "/api/energy/site-timeline",
        params=params,
    )
    assert response.status_code == 422

    params = malapert_params()
    params["battery_capacity_wh"] = -100.0

    response = client.get(
        "/api/energy/site-timeline",
        params=params,
    )
    assert response.status_code == 422

    params = malapert_params()
    params["duration_days"] = 28.0
    params["step_minutes"] = 1.0

    response = client.get(
        "/api/energy/site-timeline",
        params=params,
    )
    assert response.status_code == 422


def test_phase11_api_returns_mocked_energy_timeline(monkeypatch):
    expected_result = {
        "source": "SPICE + NASA LOLA DEM + Phase 11 Solar Energy Model",
        "sample_count": 2,
        "site": {
            "name": "Malapert",
            "latitude_deg": -85.99,
            "longitude_deg": 0.12,
        },
        "summary": {
            "sunlit_hours": 1.0,
            "total_generated_wh": 500.0,
        },
        "sunlight_windows": [],
        "warnings": [],
        "samples": [],
    }

    captured = {}

    def fake_energy_timeline_for_site(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return expected_result

    monkeypatch.setattr(
        "backend.energy.routes.energy_timeline_for_site",
        fake_energy_timeline_for_site,
    )

    response = client.get(
        "/api/energy/site-timeline",
        params=malapert_params(),
    )

    assert response.status_code == 200
    assert response.json() == expected_result

    assert captured["args"] == ()

    kwargs = captured["kwargs"]

    assert kwargs["lat_deg"] == pytest.approx(-85.99)
    assert kwargs["lon_deg"] == pytest.approx(0.12)
    assert kwargs["start_utc"] == "2026-11-14T00:00:00Z"
    assert kwargs["duration_days"] == pytest.approx(1.0)
    assert kwargs["step_minutes"] == pytest.approx(60.0)
    assert kwargs["base_load_w"] == pytest.approx(60.0)
    assert kwargs["max_range_m"] == pytest.approx(100000.0)
    assert kwargs["azimuth_step_deg"] == pytest.approx(0.25)
    assert kwargs["sunlit_threshold"] == pytest.approx(0.5)
    assert kwargs["n_disc_points"] == 400
    assert kwargs["include_samples"] is True

    assert isinstance(kwargs["panel_config"], PanelConfig)
    assert isinstance(kwargs["battery_config"], BatteryConfig)

    panel = kwargs["panel_config"]

    assert panel.kind == "tracking"
    assert panel.area_m2 == pytest.approx(3.0)
    assert panel.efficiency == pytest.approx(0.28)
    assert panel.dust_loss == pytest.approx(0.05)
    assert panel.panel_height_m == pytest.approx(3.0)

    battery = kwargs["battery_config"]

    assert battery.capacity_wh == pytest.approx(2000.0)
    assert battery.initial_soc == pytest.approx(0.8)
    assert battery.min_soc == pytest.approx(0.2)


@pytest.mark.parametrize(
    "error",
    [
        KernelsMissing("Test missing SPICE kernels."),
        FileNotFoundError("Test missing NASA DEM."),
    ],
)
def test_phase11_api_returns_503_when_resources_are_missing(
    monkeypatch,
    error,
):
    def fake_energy_timeline_for_site(*args, **kwargs):
        raise error

    monkeypatch.setattr(
        "backend.energy.routes.energy_timeline_for_site",
        fake_energy_timeline_for_site,
    )

    response = client.get(
        "/api/energy/site-timeline",
        params=malapert_params(),
    )

    assert response.status_code == 503
    assert str(error) in response.json()["detail"]


@requires_real_data
def test_phase11_api_returns_valid_real_malapert_energy_timeline():
    params = malapert_params()

    response = client.get(
        "/api/energy/site-timeline",
        params=params,
    )

    assert response.status_code == 200

    data = response.json()
    summary = data["summary"]

    assert summary["sample_count"] > 0
    assert len(data["samples"]) == summary["sample_count"]

    assert 0.0 <= summary["sunlit_sample_percent"] <= 100.0
    assert summary["sunlit_hours"] >= 0.0
    assert summary["total_generated_wh"] >= 0.0

    assert isinstance(data["sunlight_windows"], list)
    assert isinstance(data["warnings"], list)

    for window in data["sunlight_windows"]:
        assert window["end_utc"] > window["start_utc"]
        assert window["duration_s"] >= 1800.0
