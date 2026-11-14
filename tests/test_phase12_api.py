import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.terrain.dem_loader import DEFAULT_DEM_PATH
from backend.communications.surface_links import SurfaceLinkSettings


client = TestClient(app)

ASSETS = [
    {
        "name": "Malapert_Lander",
        "type": "lander",
        "latitude_deg": -85.99,
        "longitude_deg": 0.12,
    },
    {
        "name": "Rover_01",
        "type": "rover",
        "latitude_deg": -86.0,
        "longitude_deg": 0.12,
    },
]


def request_body():
    return {"assets": ASSETS}


def test_phase12_api_returns_mocked_surface_links(monkeypatch):
    expected = {
        ("Malapert_Lander", "Rover_01"): {
            "distance_m": 303.2,
            "slant_range_m": 305.2,
            "line_of_sight": False,
            "range_ok": True,
            "fresnel_ok": False,
            "min_clearance_m": -6.4,
            "min_clearance_at_m": 113.7,
            "fresnel_ratio_min": -0.88,
            "elevation_of_b_from_a_deg": -5.0,
            "elevation_of_a_from_b_deg": 5.0,
            "data_complete": True,
            "usable": False,
        }
    }

    captured = {}

    def fake_surface_links_for_assets(assets, settings=None, margin_m=3000.0):
        captured["assets"] = assets
        captured["settings"] = settings
        captured["margin_m"] = margin_m
        return expected

    monkeypatch.setattr(
        "backend.communications.routes.surface_links_for_assets",
        fake_surface_links_for_assets,
    )

    response = client.post(
        "/api/communications/surface-links",
        json=request_body(),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["asset_count"] == 2
    assert data["link_count"] == 1
    assert data["source"] == "NASA LOLA DEM + Phase 12 Surface Link Model"

    link = data["links"][0]

    assert link["asset_a"] == "Malapert_Lander"
    assert link["asset_b"] == "Rover_01"
    assert link["line_of_sight"] is False
    assert link["usable"] is False

    assert isinstance(captured["settings"], SurfaceLinkSettings)
    assert captured["settings"].frequency_hz == pytest.approx(401.5e6)
    assert captured["settings"].max_range_m == pytest.approx(10000.0)
    assert captured["margin_m"] == pytest.approx(3000.0)


def test_phase12_api_rejects_invalid_requests():
    invalid_requests = [
        {"assets": [ASSETS[0]]},
        {
            "assets": [
                ASSETS[0],
                {**ASSETS[1], "latitude_deg": 5.0},
            ]
        },
        {
            "assets": [
                ASSETS[0],
                {**ASSETS[1], "type": "drone"},
            ]
        },
        {
            "assets": [
                ASSETS[0],
                {**ASSETS[1], "name": "Malapert_Lander"},
            ]
        },
        {
            **request_body(),
            "frequency_hz": -1.0,
        },
        {
            **request_body(),
            "min_fresnel_ratio": 3.0,
        },
    ]

    for body in invalid_requests:
        response = client.post(
            "/api/communications/surface-links",
            json=body,
        )
        assert response.status_code == 422


def test_phase12_api_returns_503_when_dem_is_missing(monkeypatch):
    def fake_surface_links_for_assets(*args, **kwargs):
        raise FileNotFoundError("Test NASA DEM unavailable.")

    monkeypatch.setattr(
        "backend.communications.routes.surface_links_for_assets",
        fake_surface_links_for_assets,
    )

    response = client.post(
        "/api/communications/surface-links",
        json=request_body(),
    )

    assert response.status_code == 503
    assert "Test NASA DEM unavailable." in response.json()["detail"]


@pytest.mark.skipif(
    not DEFAULT_DEM_PATH.is_file(),
    reason="NASA LOLA DEM is unavailable.",
)
def test_phase12_api_returns_real_terrain_link_result():
    response = client.post(
        "/api/communications/surface-links",
        json=request_body(),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["asset_count"] == 2
    assert data["link_count"] == 1

    link = data["links"][0]

    assert link["distance_m"] > 0
    assert link["slant_range_m"] > 0
    assert isinstance(link["line_of_sight"], bool)
    assert isinstance(link["usable"], bool)
    assert link["data_complete"] is True
