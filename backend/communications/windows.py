
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence


def parse_time(text: str) -> float:
    """Convert an ISO-8601 timestamp to Unix seconds."""
    value = text.strip()

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.timestamp()


def to_iso(seconds: float) -> str:
    """Convert Unix seconds to an ISO-8601 UTC timestamp."""
    return (
        datetime.fromtimestamp(seconds, tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


@dataclass
class WindowSettings:
    """Configuration for communication-window detection."""

    resolution_s: float = 60.0
    max_gap_s: float = 600.0
    min_duration_s: float = 1800.0

    def __post_init__(self) -> None:
        if self.resolution_s <= 0:
            raise ValueError("resolution_s must be greater than zero")

        if self.max_gap_s < 0:
            raise ValueError("max_gap_s cannot be negative")

        if self.min_duration_s < 0:
            raise ValueError("min_duration_s cannot be negative")


def find_runs(flags: Sequence[bool]) -> list[tuple[int, int]]:
    """
    Find contiguous True runs.

    Returned index pairs are inclusive:
    (start_index, end_index).
    """
    runs: list[tuple[int, int]] = []
    start: int | None = None

    for index, flag in enumerate(flags):
        if flag and start is None:
            start = index

        elif not flag and start is not None:
            runs.append((start, index - 1))
            start = None

    if start is not None:
        runs.append((start, len(flags) - 1))

    return runs


def windows_from_flags(
    times_s: Sequence[float],
    flags: Sequence[bool],
) -> list[dict[str, Any]]:
    """Create coarse windows directly from sampled availability flags."""
    if len(times_s) != len(flags):
        raise ValueError("times_s and flags must have equal lengths")

    if not times_s:
        return []

    if any(times_s[i] >= times_s[i + 1] for i in range(len(times_s) - 1)):
        raise ValueError("times_s must be strictly increasing")

    windows = []

    for start_index, end_index in find_runs(flags):
        windows.append(
            {
                "start_index": start_index,
                "end_index": end_index,
                "start_s": float(times_s[start_index]),
                "end_s": float(times_s[end_index]),
                "duration_s": float(
                    times_s[end_index] - times_s[start_index]
                ),
            }
        )

    return windows


def _state_is_good(state: Any) -> bool:
    """Read availability from either a bool or a state dictionary."""
    if isinstance(state, bool):
        return state

    if isinstance(state, Mapping):
        return bool(state.get("up", state.get("available", False)))

    raise TypeError("state_fn must return a bool or a state dictionary")


def _state_reasons(state: Any) -> list[str]:
    """Extract limiting-check reasons from a state result."""
    if not isinstance(state, Mapping):
        return []

    reasons = state.get("reasons", [])

    if isinstance(reasons, str):
        return [reasons]

    return [str(reason) for reason in reasons]


def refine_brackets(
    good_times: Sequence[float],
    bad_times: Sequence[float],
    bad_reasons: Sequence[Sequence[str]],
    state_fn: Callable[[float], Any],
    resolution_s: float,
) -> list[dict[str, Any]]:
    """
    Refine transition brackets using bisection.

    Each bracket must contain one known-good time and one known-bad time.
    The returned edge is always the last verified good-side time.

    This is conservative:
      - For an entry edge, it returns the earliest verified good time.
      - For an exit edge, it returns the latest verified good time.
    """
    if resolution_s <= 0:
        raise ValueError("resolution_s must be greater than zero")

    if not (
        len(good_times) == len(bad_times) == len(bad_reasons)
    ):
        raise ValueError("Bracket input lists must have equal lengths")

    results = []

    for original_good, original_bad, reasons in zip(
        good_times, bad_times, bad_reasons
    ):
        good = float(original_good)
        bad = float(original_bad)

        if good == bad:
            raise ValueError("A bracket must have two different times")

        if _state_is_good(state_fn(good)) is False:
            raise ValueError("The supplied good-side time is not available")

        if _state_is_good(state_fn(bad)) is True:
            raise ValueError("The supplied bad-side time is available")

        while abs(bad - good) > resolution_s:
            midpoint = (good + bad) / 2.0

            if _state_is_good(state_fn(midpoint)):
                good = midpoint
            else:
                bad = midpoint

        results.append(
            {
                "edge_s": good,
                "good_s": good,
                "bad_s": bad,
                "bad_reasons": list(reasons),
                "bracket_width_s": abs(bad - good),
            }
        )

    return results


def _stats(
    times_s: Sequence[float],
    values: Sequence[float],
    start_s: float,
    end_s: float,
) -> dict[str, float] | None:
    """Calculate mean, minimum and maximum for values in a time interval."""
    selected = [
        float(value)
        for time_value, value in zip(times_s, values)
        if start_s <= time_value <= end_s and value is not None
    ]

    if not selected:
        return None

    return {
        "mean": sum(selected) / len(selected),
        "min": min(selected),
        "max": max(selected),
    }


def build_windows(
    times_s: Sequence[float],
    flags: Sequence[bool],
    state_fn: Callable[[float], Any],
    settings: WindowSettings | None = None,
    extras: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, Any]:
    """
    Build refined communication windows from sampled availability.

    state_fn(epoch_seconds) must return either:
        bool
    or:
        {"up": bool, "reasons": [...], ...}

    extras may contain additional sample-aligned numeric series, such as
    visible_fraction or Earth clearance margin.
    """
    settings = settings or WindowSettings()

    times = [float(value) for value in times_s]
    availability = [bool(value) for value in flags]

    if len(times) != len(availability):
        raise ValueError("times_s and flags must have equal lengths")

    if not times:
        return {
            "windows": [],
            "rejected": [],
            "settings": {
                "resolution_s": settings.resolution_s,
                "max_gap_s": settings.max_gap_s,
                "min_duration_s": settings.min_duration_s,
            },
        }

    if any(times[i] >= times[i + 1] for i in range(len(times) - 1)):
        raise ValueError("times_s must be strictly increasing")

    if extras:
        for name, values in extras.items():
            if len(values) != len(times):
                raise ValueError(
                    f"Extra series '{name}' must match the sample count"
                )

    runs = find_runs(availability)
    raw_windows: list[dict[str, Any]] = []

    for start_index, end_index in runs:
        start_s = times[start_index]
        end_s = times[end_index]

        starts_before_period = start_index == 0
        ends_after_period = end_index == len(times) - 1

        limiting_checks: set[str] = set()

        # Refine the entry boundary.
        if not starts_before_period:
            bad_index = start_index - 1
            reasons = _state_reasons(state_fn(times[bad_index]))
            limiting_checks.update(reasons)

            result = refine_brackets(
                [times[start_index]],
                [times[bad_index]],
                [reasons],
                state_fn,
                settings.resolution_s,
            )[0]

            start_s = result["edge_s"]

        # Refine the exit boundary.
        if not ends_after_period:
            bad_index = end_index + 1
            reasons = _state_reasons(state_fn(times[bad_index]))
            limiting_checks.update(reasons)

            result = refine_brackets(
                [times[end_index]],
                [times[bad_index]],
                [reasons],
                state_fn,
                settings.resolution_s,
            )[0]

            end_s = result["edge_s"]

        raw_windows.append(
            {
                "start_s": start_s,
                "end_s": end_s,
                "starts_before_period": starts_before_period,
                "ends_after_period": ends_after_period,
                "limiting_checks": sorted(limiting_checks),
                "bridged_gaps": [],
            }
        )

    # Merge nearby windows when their gap is within max_gap_s.
    merged: list[dict[str, Any]] = []

    for current in raw_windows:
        if not merged:
            merged.append(current.copy())
            continue

        previous = merged[-1]
        gap_s = current["start_s"] - previous["end_s"]

        if gap_s <= settings.max_gap_s:
            previous["bridged_gaps"].append(
                {
                    "start_s": previous["end_s"],
                    "end_s": current["start_s"],
                    "duration_s": max(0.0, gap_s),
                }
            )

            previous["end_s"] = current["end_s"]
            previous["ends_after_period"] = current[
                "ends_after_period"
            ]
            previous["limiting_checks"] = sorted(
                set(previous["limiting_checks"])
                | set(current["limiting_checks"])
            )
        else:
            merged.append(current.copy())

    windows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for index, item in enumerate(merged, start=1):
        duration_s = max(0.0, item["end_s"] - item["start_s"])

        bridged_gap_s = sum(
            gap["duration_s"] for gap in item["bridged_gaps"]
        )

        available_s = max(0.0, duration_s - bridged_gap_s)

        window = {
            "window_id": f"window_{index:03d}",
            "start_s": item["start_s"],
            "end_s": item["end_s"],
            "start_utc": to_iso(item["start_s"]),
            "end_utc": to_iso(item["end_s"]),
            "duration_s": duration_s,
            "available_s": available_s,
            "bridged_gap_s": bridged_gap_s,
            "bridged_gaps": item["bridged_gaps"],
            "starts_before_period": item["starts_before_period"],
            "ends_after_period": item["ends_after_period"],
            "clipped": (
                item["starts_before_period"]
                or item["ends_after_period"]
            ),
            "limiting_checks": item["limiting_checks"],
            "stats": {},
        }

        if extras:
            for name, values in extras.items():
                statistics = _stats(
                    times,
                    values,
                    item["start_s"],
                    item["end_s"],
                )
                if statistics is not None:
                    window["stats"][name] = statistics

        if available_s < settings.min_duration_s:
            rejected.append(
                {
                    **window,
                    "rejection_reason": "too_short",
                }
            )
        else:
            windows.append(window)

    return {
        "windows": windows,
        "rejected": rejected,
        "settings": {
            "resolution_s": settings.resolution_s,
            "max_gap_s": settings.max_gap_s,
            "min_duration_s": settings.min_duration_s,
        },
    }


def summarize_windows(
    windows: Sequence[Mapping[str, Any]],
    rejected: Sequence[Mapping[str, Any]] | None = None,
    period_duration_s: float | None = None,
) -> dict[str, Any]:
    """Summarize accepted communication windows."""
    rejected = rejected or []

    total_available_s = sum(
        float(window.get("available_s", 0.0))
        for window in windows
    )

    durations = [
        float(window.get("available_s", 0.0))
        for window in windows
    ]

    total_period_s = (
        float(period_duration_s)
        if period_duration_s is not None
        else None
    )

    percentage = None
    if total_period_s is not None and total_period_s > 0:
        percentage = 100.0 * total_available_s / total_period_s

    return {
        "window_count": len(windows),
        "rejected_count": len(rejected),
        "total_available_s": total_available_s,
        "total_available_hours": total_available_s / 3600.0,
        "longest_window_s": max(durations, default=0.0),
        "windows_touching_period_edges": sum(
            bool(window.get("starts_before_period"))
            or bool(window.get("ends_after_period"))
            for window in windows
        ),
        "available_percentage": percentage,
    }
