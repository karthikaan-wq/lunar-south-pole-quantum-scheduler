import math

import numpy as np
import pytest

from backend.communications import site_surface_links as adapter
from backend.communications.surface_links import SurfaceLinkSettings


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


def test_adapter_uses_defaults_and_loads_one_terrain_window(monkeypatch):
    calls = []

    def fake_load(lat, lon, half_size):
        calls.append((lat, lon, half_size))
        return "synthetic-terrain"

    def fake_link_matrix(terrain, sites, heights, settings):
        assert terrain == "synthetic-terrain"
        assert sites == {
            "Malapert_Lander": (-85.99, 0.12),
            "Rover_01": (-86.0, 0.12),
        }
        assert heights == {
            "Malapert_Lander": 3.0,
            "Rover_01": 1.5,
        }
        assert isinstance(settings, SurfaceLinkSettings)
        return {"test": "success"}

    monkeypatch.setattr(adapter, "load_terrain_window", fake_load)
    monkeypatch.setattr(adapter, "link_matrix", fake_link_matrix)

    result = adapter.surface_links_for_assets(ASSETS)

    assert result == {"test": "success"}
    assert len(calls) == 1
    assert calls[0][2] >= 3000.0


def test_adapter_respects_custom_antenna_heights_and_settings(monkeypatch):
    captured = {}

    def fake_load(lat, lon, half_size):
        return "terrain"

    def fake_link_matrix(terrain, sites, heights, settings):
        captured["heights"] = heights
        captured["settings"] = settings
        return {}

    custom_assets = [
        {**ASSETS[0], "antenna_height_m": 5.0},
        {**ASSETS[1], "antenna_height_m": 2.5},
    ]
    settings = SurfaceLinkSettings(max_range_m=8000.0)

    monkeypatch.setattr(adapter, "load_terrain_window", fake_load)
    monkeypatch.setattr(adapter, "link_matrix", fake_link_matrix)

    adapter.surface_links_for_assets(custom_assets, settings=settings)

    assert captured["heights"] == {
        "Malapert_Lander": 5.0,
        "Rover_01": 2.5,
    }
    assert captured["settings"] is settings


def test_adapter_handles_longitude_wraparound(monkeypatch):
    captured = {}

    def fake_load(lat, lon, half_size):
        captured["centre_lon"] = lon
        captured["half_size"] = half_size
        return "terrain"

    monkeypatch.setattr(adapter, "load_terrain_window", fake_load)
    monkeypatch.setattr(
        adapter,
        "link_matrix",
        lambda *args, **kwargs: {},
    )

    assets = [
        {
            "name": "Lander",
            "type": "lander",
            "latitude_deg": -89.0,
            "longitude_deg": 179.9,
        },
        {
            "name": "Rover",
            "type": "rover",
            "latitude_deg": -89.0,
            "longitude_deg": -179.9,
        },
    ]

    adapter.surface_links_for_assets(assets)

    assert abs(abs(captured["centre_lon"]) - 180.0) < 0.01
    assert captured["half_size"] >= 3000.0


@pytest.mark.parametrize(
    "assets, message",
    [
        ([ASSETS[0]], "At least two"),
        ([ASSETS[0], ASSETS[0]], "unique"),
        (
            [
                ASSETS[0],
                {**ASSETS[1], "type": "drone"},
            ],
            "Unsupported",
        ),
        (
            [
                ASSETS[0],
                {**ASSETS[1], "latitude_deg": 5.0},
            ],
            "latitude",
        ),
        (
            [
                ASSETS[0],
                {**ASSETS[1], "antenna_height_m": -1.0},
            ],
            "Antenna height",
        ),
    ],
)
def test_adapter_rejects_invalid_assets(monkeypatch, assets, message):
    monkeypatch.setattr(
        adapter,
        "load_terrain_window",
        lambda *args: pytest.fail("Terrain must not load for invalid assets"),
    )

    with pytest.raises(ValueError, match=message):
        adapter.surface_links_for_assets(assets)


def test_adapter_rejects_invalid_terrain_margin():
    with pytest.raises(ValueError, match="margin_m"):
        adapter.surface_links_for_assets(ASSETS, margin_m=-1.0)


def test_load_terrain_window_rejects_invalid_half_size(monkeypatch):
    monkeypatch.setattr(
        adapter,
        "load_dem_terrain",
        lambda *args, **kwargs: pytest.fail("DEM loader must not be called"),
    )

    with pytest.raises(ValueError, match="half-size"):
        adapter.load_terrain_window(-86.0, 0.0, 0.0)
