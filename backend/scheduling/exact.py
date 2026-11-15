from __future__ import annotations

import math

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from backend.scheduling.candidates import ScheduleCandidate
from backend.scheduling.selection import (
    SchedulingResult,
    candidate_value,
)


class ExactSolveLimitError(RuntimeError):
    """Raised when the exact problem exceeds configured limits."""


class ExactSolveError(RuntimeError):
    """Raised when optimality cannot be established."""


def _conflict_pairs(
    candidates: list[ScheduleCandidate],
    max_conflict_pairs: int,
) -> list[tuple[int, int]]:
    """
    Build candidate conflict pairs using resource-indexed time intervals.

    Intervals are half-open: [start_s, end_s).
    Only overlapping legs sharing a resource create a conflict.
    """
    resource_events = {}

    for candidate_index, candidate in enumerate(candidates):
        for leg in candidate.legs:
            for resource_id in leg.resource_ids:
                resource_events.setdefault(resource_id, []).append(
                    (
                        leg.start_s,
                        leg.end_s,
                        candidate_index,
                    )
                )

    conflicts = set()

    for events in resource_events.values():
        events.sort()

        active = []

        for start_s, end_s, candidate_index in events:
            active = [
                item
                for item in active
                if item[0] > start_s
            ]

            for active_end, other_index in active:
                if other_index == candidate_index:
                    continue

                pair = (
                    min(candidate_index, other_index),
                    max(candidate_index, other_index),
                )

                conflicts.add(pair)

                if len(conflicts) > max_conflict_pairs:
                    raise ExactSolveLimitError(
                        "Exact solver conflict-pair limit exceeded: "
                        f"more than {max_conflict_pairs:,} conflicts."
                    )

            active.append((end_s, candidate_index))

    return sorted(conflicts)


def exact_schedule(
    candidates: list[ScheduleCandidate],
    task_ids: list[str] | tuple[str, ...],
    max_candidates: int = 5000,
    max_conflict_pairs: int = 100000,
) -> SchedulingResult:
    """
    Find an optimal feasible candidate selection using binary MILP.

    Objective:
        Maximize sum(priority * completed_data_volume).

    Constraints:
        - At most one candidate per task.
        - No overlapping transmissions on shared resources.

    A candidate represents a complete task route, including every
    required leg. Selecting it therefore selects the complete route.

    The function only returns an exact result when the solver reports
    a proven optimum. Limits and unsuccessful solver outcomes raise
    explicit exceptions.
    """
    if max_candidates < 1:
        raise ValueError("max_candidates must be at least 1.")

    if max_conflict_pairs < 0:
        raise ValueError("max_conflict_pairs cannot be negative.")

    if len(candidates) > max_candidates:
        raise ExactSolveLimitError(
            "Exact solver candidate limit exceeded: "
            f"{len(candidates):,} candidates; "
            f"configured limit is {max_candidates:,}."
        )

    if not candidates:
        return SchedulingResult(
            algorithm="exact",
            selected_candidates=(),
            unscheduled_task_ids=tuple(task_ids),
            objective_value=0.0,
            candidate_count=0,
            optimal=True,
        )

    for candidate in candidates:
        value = candidate_value(candidate)

        if not math.isfinite(value) or value < 0:
            raise ValueError(
                "Candidate objective values must be finite "
                "and nonnegative."
            )

    task_rows = {}
    for candidate_index, candidate in enumerate(candidates):
        task_rows.setdefault(candidate.task_id, []).append(
            candidate_index
        )

    conflicts = _conflict_pairs(
        candidates,
        max_conflict_pairs,
    )

    candidate_count = len(candidates)
    task_count = len(task_rows)
    conflict_count = len(conflicts)
    constraint_count = task_count + conflict_count

    matrix_rows = []
    matrix_columns = []
    matrix_values = []

    row_index = 0

    # At most one candidate can be selected for each task.
    for indices in task_rows.values():
        for candidate_index in indices:
            matrix_rows.append(row_index)
            matrix_columns.append(candidate_index)
            matrix_values.append(1.0)

        row_index += 1

    # Conflicting candidates cannot both be selected.
    for first_index, second_index in conflicts:
        matrix_rows.extend((row_index, row_index))
        matrix_columns.extend((first_index, second_index))
        matrix_values.extend((1.0, 1.0))
        row_index += 1

    matrix = coo_matrix(
        (
            np.asarray(matrix_values, dtype=float),
            (
                np.asarray(matrix_rows, dtype=np.int32),
                np.asarray(matrix_columns, dtype=np.int32),
            ),
        ),
        shape=(constraint_count, candidate_count),
    ).tocsr()

    objective = np.asarray(
        [
            -candidate_value(candidate)
            for candidate in candidates
        ],
        dtype=float,
    )

    constraints = LinearConstraint(
        matrix,
        lb=np.full(constraint_count, -np.inf),
        ub=np.ones(constraint_count),
    )

    result = milp(
        c=objective,
        integrality=np.ones(candidate_count, dtype=np.int32),
        bounds=Bounds(
            lb=np.zeros(candidate_count),
            ub=np.ones(candidate_count),
        ),
        constraints=constraints,
        options={"presolve": True},
    )

    if result.status != 0 or not result.success or result.x is None:
        raise ExactSolveError(
            "Exact solver did not prove optimality. "
            f"Solver status={result.status}; "
            f"message={result.message}"
        )

    selected = [
        candidates[index]
        for index, value in enumerate(result.x)
        if value > 0.5
    ]

    selected.sort(
        key=lambda candidate: (
            candidate.start_s,
            candidate.end_s,
            candidate.task_id,
        )
    )

    scheduled_tasks = {
        candidate.task_id
        for candidate in selected
    }

    unscheduled = tuple(
        task_id
        for task_id in task_ids
        if task_id not in scheduled_tasks
    )

    objective_value = sum(
        candidate_value(candidate)
        for candidate in selected
    )

    return SchedulingResult(
        algorithm="exact",
        selected_candidates=tuple(selected),
        unscheduled_task_ids=unscheduled,
        objective_value=objective_value,
        candidate_count=candidate_count,
        optimal=True,
    )
