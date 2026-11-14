
import pytest

from backend.communications.antenna import AntennaConfig
from backend.communications.direct_to_earth import (
    LinkConstraints,
    evaluate_direct_link,
)
from backend.visibility.disc_visibility import HorizonModel


def make_horizon(complete=True, elevation=-5.0):
    return HorizonModel(
        azimuth_deg=list(range(0, 360, 10)),
        horizon_deg=[elevation] * 36,
        complete=[complete] * 36,
    )


def make_samples(
    visible_fraction=0.8,
    clearance=2.0,
    earth_azimuth=90.0,
    earth_elevation=10.0,
    earth_coverage=True,
    sun_azimuth=180.0,
    sun_elevation=-20.0,
    sun_radius=0.27,
):
    earth = {
        "utc": "2026-11-14T00:00:00Z",
        "azimuth_deg": earth_azimuth,
        "elevation_deg": earth_elevation,
        "visible_fraction": visible_fraction,
        "margin_deg": clearance,
        "coverage_complete": earth_coverage,
    }

    sun = {
        "utc": "2026-11-14T00:00:00Z",
        "azimuth_deg": sun_azimuth,
        "elevation_deg": sun_elevation,
        "angular_radius_deg": sun_radius,
    }

    return [earth], [sun]


def evaluate(earth, sun, horizon=None, antenna=None, constraints=None):
    return evaluate_direct_link(
        visibility_samples=earth,
        sun_samples=sun,
        horizon=horizon or make_horizon(),
        antenna=antenna or AntennaConfig(),
        constraints=constraints,
    )[0]


def test_all_five_checks_pass():
    earth, sun = make_samples()

    result = evaluate(earth, sun)

    assert result["link_available"] is True
    assert all(result["checks"].values())
    assert result["failed_checks"] == []
    assert result["first_failure"] is None


def test_incomplete_terrain_fails_coverage_check():
    earth, sun = make_samples(earth_coverage=False)

    result = evaluate(earth, sun)

    assert result["checks"]["terrain_coverage"] is False
    assert result["first_failure"] == "terrain_coverage"
    assert result["link_available"] is False


def test_low_visible_fraction_fails_terrain_check():
    earth, sun = make_samples(visible_fraction=0.3)

    result = evaluate(earth, sun)

    assert result["checks"]["earth_visible_fraction"] is False
    assert "earth_visible_fraction" in result["failed_checks"]


def test_minimum_visible_fraction_boundary_passes():
    earth, sun = make_samples(visible_fraction=0.5)

    result = evaluate(
        earth,
        sun,
        constraints=LinkConstraints(min_visible_fraction=0.5),
    )

    assert result["checks"]["earth_visible_fraction"] is True


def test_insufficient_clearance_fails():
    earth, sun = make_samples(clearance=0.2)

    result = evaluate(earth, sun)

    assert result["checks"]["earth_clearance"] is False
    assert "earth_clearance" in result["failed_checks"]


def test_clearance_boundary_passes():
    earth, sun = make_samples(clearance=0.5)

    result = evaluate(
        earth,
        sun,
        constraints=LinkConstraints(min_clearance_deg=0.5),
    )

    assert result["checks"]["earth_clearance"] is True


def test_antenna_pointing_failure_is_recorded():
    earth, sun = make_samples(earth_azimuth=180.0)

    antenna = AntennaConfig(
        kind="fixed",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=10.0,
        half_beamwidth_deg=5.0,
    )

    result = evaluate(earth, sun, antenna=antenna)

    assert result["checks"]["antenna_pointing"] is False
    assert "antenna_pointing" in result["failed_checks"]


def test_sun_exclusion_fails_when_sun_is_visible_and_too_close():
    earth, sun = make_samples(
        earth_azimuth=90.0,
        earth_elevation=0.0,
        sun_azimuth=90.0,
        sun_elevation=0.0,
    )

    result = evaluate(
        earth,
        sun,
        horizon=make_horizon(elevation=-5.0),
    )

    assert result["sun"]["in_view"] is True
    assert result["sun"]["separation_from_earth_deg"] == pytest.approx(0.0)
    assert result["checks"]["sun_exclusion"] is False


def test_hidden_sun_does_not_trigger_sun_exclusion():
    earth, sun = make_samples(
        earth_azimuth=90.0,
        earth_elevation=0.0,
        sun_azimuth=90.0,
        sun_elevation=-20.0,
    )

    result = evaluate(
        earth,
        sun,
        horizon=make_horizon(elevation=-5.0),
    )

    assert result["sun"]["in_view"] is False
    assert result["checks"]["sun_exclusion"] is True


def test_sun_exclusion_can_be_disabled():
    earth, sun = make_samples(
        earth_azimuth=90.0,
        earth_elevation=0.0,
        sun_azimuth=90.0,
        sun_elevation=0.0,
    )

    result = evaluate(
        earth,
        sun,
        constraints=LinkConstraints(sun_exclusion_deg=0.0),
    )

    assert result["checks"]["sun_exclusion"] is True


def test_incomplete_sun_terrain_is_handled_conservatively():
    earth, sun = make_samples(
        earth_azimuth=90.0,
        earth_elevation=0.0,
        sun_azimuth=90.0,
        sun_elevation=0.0,
    )

    result = evaluate(
        earth,
        sun,
        horizon=make_horizon(complete=False),
    )

    assert result["sun"]["in_view"] is None
    assert result["checks"]["sun_exclusion"] is False


def test_all_failed_checks_are_recorded():
    earth, sun = make_samples(
        visible_fraction=0.1,
        clearance=-2.0,
        earth_coverage=False,
        earth_azimuth=180.0,
        earth_elevation=10.0,
        sun_azimuth=180.0,
        sun_elevation=10.0,
    )

    antenna = AntennaConfig(
        kind="fixed",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=10.0,
        half_beamwidth_deg=2.0,
    )

    result = evaluate(
        earth,
        sun,
        antenna=antenna,
    )

    assert result["link_available"] is False
    assert len(result["failed_checks"]) >= 4
    assert result["first_failure"] == "terrain_coverage"


def test_mismatched_timestamps_are_rejected():
    earth, sun = make_samples()
    sun[0]["utc"] = "2026-11-14T00:30:00Z"

    with pytest.raises(ValueError, match="timestamps do not match"):
        evaluate(earth, sun)


def test_invalid_visible_fraction_is_rejected():
    earth, sun = make_samples(visible_fraction=1.5)

    with pytest.raises(ValueError, match="invalid visible fraction"):
        evaluate(earth, sun)


def test_invalid_constraints_are_rejected():
    with pytest.raises(ValueError):
        LinkConstraints(min_visible_fraction=1.5)

    with pytest.raises(ValueError):
        LinkConstraints(sun_exclusion_deg=-1.0)
