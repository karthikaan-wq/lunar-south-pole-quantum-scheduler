
import pytest

from backend.communications.windows import (
    WindowSettings,
    build_windows,
    find_runs,
    parse_time,
    refine_brackets,
    summarize_windows,
    to_iso,
    windows_from_flags,
)


def test_find_runs():
    assert find_runs(
        [False, True, True, False, True, True, True, False]
    ) == [(1, 2), (4, 6)]


def test_find_runs_with_empty_and_all_true():
    assert find_runs([]) == []
    assert find_runs([True, True, True]) == [(0, 2)]
    assert find_runs([False, False]) == []


def test_parse_time_and_to_iso():
    timestamp = parse_time("2026-11-14T00:00:00Z")

    assert to_iso(timestamp) == "2026-11-14T00:00:00Z"


def test_parse_time_accepts_timezone_offset():
    utc_timestamp = parse_time("2026-11-14T05:30:00+05:30")
    z_timestamp = parse_time("2026-11-14T00:00:00Z")

    assert utc_timestamp == z_timestamp


def test_windows_from_flags():
    times = [0, 300, 600, 900, 1200]
    flags = [False, True, True, False, True]

    windows = windows_from_flags(times, flags)

    assert len(windows) == 2
    assert windows[0]["start_s"] == 300
    assert windows[0]["end_s"] == 600
    assert windows[1]["start_s"] == 1200


def test_windows_from_flags_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        windows_from_flags([0, 300], [True])


def test_windows_from_flags_requires_increasing_times():
    with pytest.raises(ValueError):
        windows_from_flags([0, 300, 200], [True, True, False])


def test_refine_brackets_returns_conservative_good_side():
    def state_fn(time_s):
        return time_s >= 250

    result = refine_brackets(
        good_times=[300],
        bad_times=[0],
        bad_reasons=[["earth_not_visible"]],
        state_fn=state_fn,
        resolution_s=10,
    )[0]

    assert result["good_s"] >= 250
    assert result["good_s"] - result["bad_s"] <= 10
    assert result["edge_s"] == result["good_s"]
    assert result["bad_reasons"] == ["earth_not_visible"]


def test_refine_brackets_can_refine_multiple_edges():
    def state_fn(time_s):
        return time_s >= 100 and time_s <= 500

    results = refine_brackets(
        good_times=[200, 400],
        bad_times=[0, 600],
        bad_reasons=[["entry"], ["exit"]],
        state_fn=state_fn,
        resolution_s=5,
    )

    assert len(results) == 2
    assert results[0]["good_s"] >= 100
    assert results[1]["good_s"] <= 500
    assert results[0]["bracket_width_s"] <= 5
    assert results[1]["bracket_width_s"] <= 5


def test_build_windows_refines_entry_and_exit_edges():
    times = [0, 300, 600, 900]
    flags = [False, True, True, False]

    def state_fn(time_s):
        return {
            "up": 250 <= time_s <= 650,
            "reasons": (
                []
                if 250 <= time_s <= 650
                else ["earth_not_visible"]
            ),
        }

    result = build_windows(
        times,
        flags,
        state_fn,
        WindowSettings(
            resolution_s=10,
            max_gap_s=0,
            min_duration_s=0,
        ),
    )

    assert len(result["windows"]) == 1

    window = result["windows"][0]

    assert 250 <= window["start_s"] <= 260
    assert 640 <= window["end_s"] <= 650
    assert window["start_s"] < window["end_s"]


def test_build_windows_marks_period_edges_as_clipped():
    times = [0, 300, 600, 900]
    flags = [True, True, True, True]

    result = build_windows(
        times,
        flags,
        lambda time_s: True,
        WindowSettings(min_duration_s=0),
    )

    assert len(result["windows"]) == 1

    window = result["windows"][0]

    assert window["starts_before_period"] is True
    assert window["ends_after_period"] is True
    assert window["clipped"] is True


def test_build_windows_records_limiting_checks():
    times = [0, 300, 600, 900]
    flags = [False, True, True, False]

    def state_fn(time_s):
        good = 250 <= time_s <= 650

        return {
            "up": good,
            "reasons": [] if good else ["earth_below_horizon"],
        }

    result = build_windows(
        times,
        flags,
        state_fn,
        WindowSettings(
            resolution_s=10,
            max_gap_s=0,
            min_duration_s=0,
        ),
    )

    window = result["windows"][0]

    assert "earth_below_horizon" in window["limiting_checks"]


def test_build_windows_bridges_short_gaps_and_records_them():
    times = [0, 300, 600, 900, 1200]
    flags = [True, True, False, True, True]

    def state_fn(time_s):
        good = time_s <= 450 or time_s >= 750
        return {
            "up": good,
            "reasons": [] if good else ["temporary_outage"],
        }

    result = build_windows(
        times,
        flags,
        state_fn,
        WindowSettings(
            resolution_s=10,
            max_gap_s=400,
            min_duration_s=0,
        ),
    )

    assert len(result["windows"]) == 1

    window = result["windows"][0]

    assert len(window["bridged_gaps"]) == 1
    assert window["bridged_gap_s"] > 0
    assert window["available_s"] < window["duration_s"]


def test_build_windows_does_not_bridge_long_gaps():
    times = [0, 300, 600, 900, 1200]
    flags = [True, True, False, True, True]

    def state_fn(time_s):
        good = time_s <= 450 or time_s >= 750
        return {"up": good, "reasons": []}

    result = build_windows(
        times,
        flags,
        state_fn,
        WindowSettings(
            resolution_s=10,
            max_gap_s=100,
            min_duration_s=0,
        ),
    )

    assert len(result["windows"]) == 2


def test_build_windows_rejects_too_short_windows():
    times = [0, 300, 600, 900]
    flags = [False, True, True, False]

    def state_fn(time_s):
        return 250 <= time_s <= 650

    result = build_windows(
        times,
        flags,
        state_fn,
        WindowSettings(
            resolution_s=10,
            max_gap_s=0,
            min_duration_s=1000,
        ),
    )

    assert len(result["windows"]) == 0
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["rejection_reason"] == "too_short"


def test_build_windows_handles_no_available_samples():
    result = build_windows(
        [0, 300, 600],
        [False, False, False],
        lambda time_s: False,
    )

    assert result["windows"] == []
    assert result["rejected"] == []


def test_build_windows_handles_empty_input():
    result = build_windows(
        [],
        [],
        lambda time_s: False,
    )

    assert result["windows"] == []
    assert result["rejected"] == []


def test_build_windows_calculates_extra_statistics():
    times = [0, 300, 600, 900]
    flags = [True, True, True, True]

    result = build_windows(
        times,
        flags,
        lambda time_s: True,
        WindowSettings(min_duration_s=0),
        extras={
            "visible_fraction": [0.4, 0.6, 0.8, 1.0],
        },
    )

    stats = result["windows"][0]["stats"]["visible_fraction"]

    assert stats["min"] == pytest.approx(0.4)
    assert stats["max"] == pytest.approx(1.0)
    assert stats["mean"] == pytest.approx(0.7)


def test_build_windows_rejects_extra_series_with_wrong_length():
    with pytest.raises(ValueError):
        build_windows(
            [0, 300, 600],
            [True, True, True],
            lambda time_s: True,
            extras={"visible_fraction": [0.5, 0.6]},
        )


def test_summarize_windows():
    windows = [
        {"available_s": 3600, "starts_before_period": True,
         "ends_after_period": False},
        {"available_s": 1800, "starts_before_period": False,
         "ends_after_period": False},
    ]

    rejected = [{"rejection_reason": "too_short"}]

    summary = summarize_windows(
        windows,
        rejected,
        period_duration_s=7200,
    )

    assert summary["window_count"] == 2
    assert summary["rejected_count"] == 1
    assert summary["total_available_s"] == 5400
    assert summary["total_available_hours"] == pytest.approx(1.5)
    assert summary["longest_window_s"] == 3600
    assert summary["windows_touching_period_edges"] == 1
    assert summary["available_percentage"] == pytest.approx(75.0)


def test_window_settings_validation():
    with pytest.raises(ValueError):
        WindowSettings(resolution_s=0)

    with pytest.raises(ValueError):
        WindowSettings(max_gap_s=-1)

    with pytest.raises(ValueError):
        WindowSettings(min_duration_s=-1)
