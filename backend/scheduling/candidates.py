
from __future__ import annotations

from dataclasses import dataclass

from backend.scheduling.models import SchedulingProblem, TransmissionTask


class CandidateGenerationLimitError(RuntimeError):
    """Raised when candidate generation exceeds its configured limit."""


@dataclass(frozen=True)
class TransmissionLeg:
    link_id: str
    start_s: float
    end_s: float
    resource_ids: tuple[str, ...]


@dataclass(frozen=True)
class ScheduleCandidate:
    candidate_id: str
    task_id: str
    priority: float
    data_volume_bytes: int
    legs: tuple[TransmissionLeg, ...]

    @property
    def start_s(self) -> float:
        return self.legs[0].start_s

    @property
    def end_s(self) -> float:
        return self.legs[-1].end_s


def _merge_overlapping_windows(windows):
    """Merge overlapping windows without bridging positive gaps."""
    ordered = sorted(
        windows,
        key=lambda item: (item.start_s, item.end_s),
    )

    merged = []

    for window in ordered:
        if not merged or window.start_s > merged[-1][1]:
            merged.append([window.start_s, window.end_s])
        else:
            merged[-1][1] = max(
                merged[-1][1],
                window.end_s,
            )

    return [
        (start_s, end_s)
        for start_s, end_s in merged
    ]


def _candidate_starts(
    window_start_s: float,
    window_end_s: float,
    duration_s: float,
    earliest_s: float,
    latest_end_s: float,
    step_s: float,
):
    """Generate deterministic start times inside one continuous window."""
    first_start = max(window_start_s, earliest_s)

    last_start = min(
        window_end_s - duration_s,
        latest_end_s - duration_s,
    )

    if first_start > last_start + 1e-9:
        return

    index = 0

    while True:
        start_s = first_start + index * step_s

        if start_s > last_start + 1e-9:
            break

        end_s = start_s + duration_s

        if end_s <= window_end_s + 1e-9:
            yield start_s

        index += 1


def _leg_duration_s(task: TransmissionTask, link) -> float:
    """Calculate transmission duration for the complete task payload."""
    return task.data_volume_bytes * 8.0 / link.data_rate_bps


def generate_candidates(
    problem: SchedulingProblem,
    max_candidates: int | None = None,
) -> list[ScheduleCandidate]:
    """
    Generate complete feasible transmission-route candidates.

    Direct route:
        One Earth transmission.

    Two-hop route:
        1. Rover-to-lander transmission.
        2. Lander-to-Earth transmission after the first leg completes.

    Every leg must fit inside one continuous communication window.

    Windows must already exclude unavailable bridged gaps.

    Candidate generation stops with an explicit exception when
    max_candidates is exceeded. It never silently truncates results.
    """
    if max_candidates is not None and max_candidates < 1:
        raise ValueError("max_candidates must be at least 1.")

    links = {
        link.link_id: link
        for link in problem.links
    }

    candidates: list[ScheduleCandidate] = []

    def append_candidate(candidate: ScheduleCandidate) -> None:
        if (
            max_candidates is not None
            and len(candidates) >= max_candidates
        ):
            raise CandidateGenerationLimitError(
                "Candidate generation limit exceeded: "
                f"more than {max_candidates:,} candidates."
            )

        candidates.append(candidate)

    horizon_start = problem.horizon_start_s
    horizon_end = problem.horizon_end_s
    step_s = problem.candidate_step_s

    for task in problem.tasks:
        route = [
            links[link_id]
            for link_id in task.route_link_ids
        ]

        task_earliest = max(
            horizon_start,
            task.release_time_s,
        )

        task_latest_end = min(
            horizon_end,
            task.deadline_s,
        )

        if len(route) == 1:
            link = route[0]
            duration = _leg_duration_s(task, link)

            windows = _merge_overlapping_windows(link.windows)

            for window_start, window_end in windows:
                for start_s in _candidate_starts(
                    window_start,
                    window_end,
                    duration,
                    task_earliest,
                    task_latest_end,
                    step_s,
                ):
                    leg = TransmissionLeg(
                        link_id=link.link_id,
                        start_s=start_s,
                        end_s=start_s + duration,
                        resource_ids=tuple(link.resource_ids),
                    )

                    append_candidate(
                        ScheduleCandidate(
                            candidate_id=(
                                f"{task.task_id}:"
                                f"{len(candidates)}"
                            ),
                            task_id=task.task_id,
                            priority=task.priority,
                            data_volume_bytes=task.data_volume_bytes,
                            legs=(leg,),
                        )
                    )

            continue

        surface_link, earth_link = route

        surface_duration = _leg_duration_s(
            task,
            surface_link,
        )

        earth_duration = _leg_duration_s(
            task,
            earth_link,
        )

        surface_windows = _merge_overlapping_windows(
            surface_link.windows
        )

        earth_windows = _merge_overlapping_windows(
            earth_link.windows
        )

        for surface_window_start, surface_window_end in surface_windows:
            for surface_start in _candidate_starts(
                surface_window_start,
                surface_window_end,
                surface_duration,
                task_earliest,
                task_latest_end,
                step_s,
            ):
                surface_end = surface_start + surface_duration

                for earth_window_start, earth_window_end in earth_windows:
                    earth_earliest = max(
                        surface_end,
                        earth_window_start,
                    )

                    for earth_start in _candidate_starts(
                        earth_window_start,
                        earth_window_end,
                        earth_duration,
                        earth_earliest,
                        task_latest_end,
                        step_s,
                    ):
                        earth_end = earth_start + earth_duration

                        surface_leg = TransmissionLeg(
                            link_id=surface_link.link_id,
                            start_s=surface_start,
                            end_s=surface_end,
                            resource_ids=tuple(
                                surface_link.resource_ids
                            ),
                        )

                        earth_leg = TransmissionLeg(
                            link_id=earth_link.link_id,
                            start_s=earth_start,
                            end_s=earth_end,
                            resource_ids=tuple(
                                earth_link.resource_ids
                            ),
                        )

                        append_candidate(
                            ScheduleCandidate(
                                candidate_id=(
                                    f"{task.task_id}:"
                                    f"{len(candidates)}"
                                ),
                                task_id=task.task_id,
                                priority=task.priority,
                                data_volume_bytes=task.data_volume_bytes,
                                legs=(
                                    surface_leg,
                                    earth_leg,
                                ),
                            )
                        )

    return candidates
