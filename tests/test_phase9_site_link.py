
from unittest.mock import patch

import pytest

from backend.communications.antenna import AntennaConfig
from backend.communications.direct_to_earth import LinkConstraints
from backend.communications.site_link import (
    direct_to_earth_for_site,
    summarize_link_availability,
)
from backend.visibility.disc_visibility import HorizonModel


TEST_UTC = "2026-11-14T00:00:00Z"


def make_horizon():
    return HorizonModel(
        azimuth_deg=list(range(0, 360, 10)),
        horizon_deg=[-5.0] * 36,
        complete=[True] * 36,
    )


def make_visibility_result():
    earth_samples = [
        {
            "utc": TEST_UTC,
            "azimuth_deg": 90.0,
            "elevation_deg": 10.0,
            "visible_fraction": 0.8,
            "margin_deg": 2.0,
            "coverage_complete": True,
        },
        {
            "utc": "2026-11-14T00:05:00Z",
            "azimuth_deg": 90.0,
            "elevation_deg": 10.0,
            "visible_fraction": 0.3,
            "margin_deg": 2.0,
            "coverage_complete": True,
        },
    ]

    return {
        "source": "SPICE + NASA LOLA DEM",
        "site": {
            "latitude_deg": -85.99,
            "longitude_deg": 0.12,
            "height_m": 4842.28,
            "terrain_elevation_m": 4842.28,
            "antenna_height_m": 2.0,
        },
        "settings": {
            "start_utc": TEST_UTC,
            "step_minutes": 5.0,
        },
        "terrain": {
            "all_directions_complete": True,
        },
        "earth_track_summary": {},
        "visibility_summary": {},
        "sample_count": len(earth_samples),
        "samples": earth_samples,
    }


def make_sun_samples():
    return [
        {
            "utc": TEST_UTC,
            "azimuth_deg": 180.0,
            "elevation_deg": -20.0,
            "distance_km": 149000000.0,
            "angular_radius_deg": 0.27,
        },
        {
            "utc": "2026-11-14T00:05:00Z",
            "azimuth_deg": 180.0,
            "elevation_deg": -20.0,
            "distance_km": 149000000.0,
            "angular_radius_deg": 0.27,
        },
    ]


@patch("backend.communications.site_link.sun_at_times")
@patch("backend.communications.site_link.earth_visibility_for_site")
def test_site_integration_connects_earth_sun_and_link_models(
    mock_visibility,
    mock_sun,
):
    visibility = make_visibility_result()
    horizon = make_horizon()

    mock_visibility.return_value = (visibility, horizon)
    mock_sun.return_value = make_sun_samples()

    result = direct_to_earth_for_site(
        lat_deg=-85.99,
        lon_deg=0.12,
        height_m=4842.28,
        start_utc=TEST_UTC,
        duration_days=1.0,
    )

    assert result["source"] == (
        "SPICE + NASA LOLA DEM + Phase 9 Link Model"
    )

    assert result["sample_count"] == 2
    assert len(result["samples"]) == 2

    assert result["samples"][0]["link_available"] is True

    assert result["samples"][1]["link_available"] is False
    assert "earth_visible_fraction" in (
        result["samples"][1]["failed_checks"]
    )

    assert result["link_summary"]["total_samples"] == 2
    assert result["link_summary"]["available_samples"] == 1
    assert result["link_summary"]["unavailable_samples"] == 1
    assert result["link_summary"]["availability_percent"] == 50.0

    mock_visibility.assert_called_once()

    mock_sun.assert_called_once_with(
        lat_deg=-85.99,
        lon_deg=0.12,
        height_m=4844.28,
        time_strings=[
            TEST_UTC,
            "2026-11-14T00:05:00Z",
        ],
    )


@patch("backend.communications.site_link.sun_at_times")
@patch("backend.communications.site_link.earth_visibility_for_site")
def test_site_integration_preserves_custom_constraints_and_antenna(
    mock_visibility,
    mock_sun,
):
    mock_visibility.return_value = (
        make_visibility_result(),
        make_horizon(),
    )
    mock_sun.return_value = make_sun_samples()

    antenna = AntennaConfig(
        kind="fixed",
        boresight_azimuth_deg=90.0,
        boresight_elevation_deg=10.0,
        half_beamwidth_deg=5.0,
    )

    constraints = LinkConstraints(
        min_visible_fraction=0.7,
        min_clearance_deg=1.0,
        sun_exclusion_deg=0.0,
    )

    result = direct_to_earth_for_site(
        lat_deg=-85.99,
        lon_deg=0.12,
        height_m=4842.28,
        start_utc=TEST_UTC,
        duration_days=1.0,
        antenna=antenna,
        constraints=constraints,
    )

    assert result["antenna"]["kind"] == "fixed"
    assert result["antenna"]["half_beamwidth_deg"] == 5.0

    assert result["link_constraints"]["min_visible_fraction"] == 0.7
    assert result["link_constraints"]["sun_exclusion_deg"] == 0.0

    assert result["samples"][0]["link_available"] is True


def test_summary_handles_empty_samples():
    result = summarize_link_availability([])

    assert result["total_samples"] == 0
    assert result["available_samples"] == 0
    assert result["unavailable_samples"] == 0
    assert result["availability_percent"] == 0.0

    assert all(
        count == 0
        for count in result["failure_counts"].values()
    )


def test_summary_counts_multiple_failures_in_one_sample():
    samples = [
        {
            "link_available": False,
            "failed_checks": [
                "terrain_coverage",
                "earth_clearance",
            ],
        },
        {
            "link_available": True,
            "failed_checks": [],
        },
    ]

    result = summarize_link_availability(samples)

    assert result["total_samples"] == 2
    assert result["available_samples"] == 1
    assert result["unavailable_samples"] == 1
    assert result["availability_percent"] == 50.0

    assert result["failure_counts"]["terrain_coverage"] == 1
    assert result["failure_counts"]["earth_clearance"] == 1
    assert result["failure_counts"]["sun_exclusion"] == 0
