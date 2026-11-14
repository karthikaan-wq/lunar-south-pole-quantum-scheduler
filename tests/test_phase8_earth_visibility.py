
import numpy as np
import pytest

from backend.visibility.disc_visibility import HorizonModel
from backend.visibility.earth_visibility import (
    visibility_from_samples,
    summarize_visibility,
)


def make_horizon(step_deg=0.5, value=0.0, complete=None):
    azimuth = np.arange(0.0, 360.0, step_deg)
    horizon = np.full(len(azimuth), value)

    return HorizonModel(
        azimuth,
        horizon,
        complete,
    )


def make_sample(
    azimuth=90.0,
    elevation=5.0,
    radius=0.9,
    utc="2026-11-10T00:00:00Z",
):
    return {
        "utc": utc,
        "azimuth_deg": azimuth,
        "elevation_deg": elevation,
        "angular_radius_deg": radius,
    }


def test_earth_disc_fully_visible_above_horizon():
    horizon = make_horizon(value=0.0)

    results = visibility_from_samples(
        [make_sample(elevation=5.0)],
        horizon,
    )

    result = results[0]

    assert result["visible_fraction"] == 1.0
    assert result["any_part_visible"] is True
    assert result["fully_visible"] is True
    assert result["blocked"] is False
    assert result["centre_visible"] is True
    assert result["coverage_complete"] is True


def test_earth_disc_fully_blocked_below_horizon():
    horizon = make_horizon(value=0.0)

    results = visibility_from_samples(
        [make_sample(elevation=-5.0)],
        horizon,
    )

    result = results[0]

    assert result["visible_fraction"] == 0.0
    assert result["any_part_visible"] is False
    assert result["fully_visible"] is False
    assert result["blocked"] is True
    assert result["centre_visible"] is False


def test_earth_disc_partially_visible_at_horizon():
    horizon = make_horizon(value=0.0)

    results = visibility_from_samples(
        [make_sample(elevation=0.0)],
        horizon,
    )

    result = results[0]

    assert 0.0 < result["visible_fraction"] < 1.0
    assert result["any_part_visible"] is True
    assert result["fully_visible"] is False
    assert result["blocked"] is False


def test_visibility_preserves_utc_timestamp():
    timestamp = "2026-11-10T12:30:00Z"

    results = visibility_from_samples(
        [make_sample(utc=timestamp)],
        make_horizon(),
    )

    assert results[0]["utc"] == timestamp


def test_visibility_calculates_centre_margin():
    results = visibility_from_samples(
        [make_sample(elevation=5.0)],
        make_horizon(value=2.0),
    )

    assert results[0]["horizon_at_centre_deg"] == pytest.approx(2.0)
    assert results[0]["margin_deg"] == pytest.approx(3.0)


def test_incomplete_terrain_is_flagged():
    complete = np.ones(720, dtype=bool)
    complete[180] = False

    horizon = make_horizon(
        step_deg=0.5,
        value=0.0,
        complete=complete,
    )

    results = visibility_from_samples(
        [make_sample(azimuth=90.0, elevation=5.0)],
        horizon,
    )

    assert results[0]["coverage_complete"] is False
    assert results[0]["visible_fraction"] == 1.0


def test_empty_samples_return_empty_results():
    assert visibility_from_samples([], make_horizon()) == []


def test_summary_of_visibility_results():
    horizon = make_horizon()

    samples = [
        make_sample(elevation=5.0),
        make_sample(elevation=-5.0),
        make_sample(elevation=0.0),
    ]

    results = visibility_from_samples(samples, horizon)
    summary = summarize_visibility(results)

    assert summary["samples"] == 3
    assert summary["percent_any_part_visible"] == pytest.approx(200.0 / 3.0)
    assert summary["percent_centre_visible"] == pytest.approx(100.0 / 3.0)
    assert summary["percent_fully_visible"] == pytest.approx(100.0 / 3.0)
    assert summary["percent_blocked"] == pytest.approx(100.0 / 3.0)
    assert 0.0 <= summary["mean_visible_fraction"] <= 1.0
    assert summary["samples_with_incomplete_terrain"] == 0


def test_summary_counts_incomplete_terrain():
    complete = np.ones(720, dtype=bool)
    complete[180] = False

    horizon = make_horizon(
        step_deg=0.5,
        complete=complete,
    )

    results = visibility_from_samples(
        [make_sample(azimuth=90.0)],
        horizon,
    )

    summary = summarize_visibility(results)

    assert summary["samples_with_incomplete_terrain"] == 1


def test_summary_handles_empty_results():
    summary = summarize_visibility([])

    assert summary["samples"] == 0
    assert summary["mean_visible_fraction"] == 0.0
    assert summary["samples_with_incomplete_terrain"] == 0


def test_invalid_sample_geometry_is_rejected():
    with pytest.raises(ValueError):
        visibility_from_samples(
            [make_sample(elevation=100.0)],
            make_horizon(),
        )


def test_missing_sample_field_is_rejected():
    sample = {
        "azimuth_deg": 90.0,
        "elevation_deg": 5.0,
    }

    with pytest.raises(ValueError):
        visibility_from_samples(
            [sample],
            make_horizon(),
        )


def test_invalid_horizon_type_is_rejected():
    with pytest.raises(TypeError):
        visibility_from_samples(
            [make_sample()],
            np.zeros(10),
        )


def test_invalid_disc_point_count_is_rejected():
    with pytest.raises(ValueError):
        visibility_from_samples(
            [make_sample()],
            make_horizon(),
            n_points=0,
        )


def test_summary_rejects_invalid_visibility_fraction():
    invalid_result = {
        "visible_fraction": 1.5,
        "any_part_visible": True,
        "centre_visible": True,
        "fully_visible": True,
        "blocked": False,
        "coverage_complete": True,
    }

    with pytest.raises(ValueError):
        summarize_visibility([invalid_result])
