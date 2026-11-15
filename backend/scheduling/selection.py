from __future__ import annotations

from dataclasses import dataclass

from backend.scheduling.candidates import (
    ScheduleCandidate,
    TransmissionLeg,
)


@dataclass(frozen=True)
class SchedulingResult:
    algorithm: str
    selected_candidates: tuple[ScheduleCandidate, ...]
    unscheduled_task_ids: tuple[str, ...]
    objective_value: float
    candidate_count: int
    optimal: bool


def candidate_value(candidate: ScheduleCandidate) -> float:
    """
    Weighted completed data volume.

    A task contributes its priority multiplied by its complete
    data volume when all transmission legs are scheduled.
    """
    return candidate.priority * candidate.data_volume_bytes


def legs_conflict(
    first: TransmissionLeg,
    second: TransmissionLeg,
) -> bool:
    """
    Return True when two legs overlap in time and share a resource.

    Intervals are half-open: [start_s, end_s).
    Therefore, one transmission may start exactly when another ends.
    """
    shared_resources = set(first.resource_ids).intersection(
        second.resource_ids
    )

    if not shared_resources:
        return False

    return (
        first.start_s < second.end_s
        and second.start_s < first.end_s
    )


def candidates_conflict(
    first: ScheduleCandidate,
    second: ScheduleCandidate,
) -> bool:
    """
    Check all transmission legs for shared-resource conflicts.
    """
    return any(
        legs_conflict(first_leg, second_leg)
        for first_leg in first.legs
        for second_leg in second.legs
    )


def schedule_objective(
    candidates: list[ScheduleCandidate] | tuple[ScheduleCandidate, ...],
) -> float:
    """
    Calculate the total weighted data volume of selected tasks.
    """
    return sum(
        candidate_value(candidate)
        for candidate in candidates
    )


def greedy_schedule(
    candidates: list[ScheduleCandidate],
    task_ids: list[str] | tuple[str, ...],
) -> SchedulingResult:
    """
    Select a feasible set of complete transmission candidates.

    Prioritization:
      1. Higher priority-weighted data volume.
      2. Earlier completion.
      3. Earlier start.
      4. Stable task and candidate identifiers.

    Each task may be selected at most once.
    Shared resources cannot be used by overlapping transmissions.
    """
    ordered = sorted(
        candidates,
        key=lambda candidate: (
            -candidate_value(candidate),
            candidate.end_s,
            candidate.start_s,
            candidate.task_id,
            candidate.candidate_id,
        ),
    )

    selected = []
    scheduled_tasks = set()

    for candidate in ordered:
        if candidate.task_id in scheduled_tasks:
            continue

        if any(
            candidates_conflict(candidate, existing)
            for existing in selected
        ):
            continue

        selected.append(candidate)
        scheduled_tasks.add(candidate.task_id)

    selected.sort(
        key=lambda candidate: (
            candidate.start_s,
            candidate.end_s,
            candidate.task_id,
        )
    )

    unscheduled = tuple(
        task_id
        for task_id in task_ids
        if task_id not in scheduled_tasks
    )

    return SchedulingResult(
        algorithm="greedy",
        selected_candidates=tuple(selected),
        unscheduled_task_ids=unscheduled,
        objective_value=schedule_objective(selected),
        candidate_count=len(candidates),
        optimal=False,
    )
