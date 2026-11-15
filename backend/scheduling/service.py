
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from backend.scheduling.candidates import (
    CandidateGenerationLimitError,
    generate_candidates,
)
from backend.scheduling.environment import prepare_environment
from backend.scheduling.exact import (
    ExactSolveError,
    ExactSolveLimitError,
    exact_schedule,
)
from backend.scheduling.models import SchedulingProblem
from backend.scheduling.selection import greedy_schedule


def _serialize_result(result) -> dict[str, Any]:
    return asdict(result)


def run_classical_scheduler(
    problem: SchedulingProblem,
) -> dict[str, Any]:
    """
    Prepare real environmental windows and run Greedy and Exact
    against the same generated candidate set.

    Exact solver failures are reported without discarding the
    successful Greedy result.
    """

    # 1. Prepare energy, Earth visibility, and surface-link windows.
    environment = prepare_environment(problem)
    prepared_problem = environment.problem

    # 2. Generate one shared candidate set.
    try:
        candidates = generate_candidates(
            prepared_problem,
            max_candidates=prepared_problem.max_exact_candidates,
        )
    except CandidateGenerationLimitError:
        raise

    task_ids = [
        task.task_id
        for task in prepared_problem.tasks
    ]

    # 3. Run Greedy.
    greedy_result = greedy_schedule(
        candidates,
        task_ids,
    )

    # 4. Run Exact using precisely the same candidates.
    exact_result = None
    exact_error = None

    try:
        exact_result = exact_schedule(
            candidates,
            task_ids,
            max_candidates=prepared_problem.max_exact_candidates,
        )

    except (
        ExactSolveLimitError,
        ExactSolveError,
        ValueError,
    ) as error:
        exact_error = str(error)

    # 5. Return compact environmental evidence.
    environment_summary = {
        "energy_sites_processed": len(environment.energy_results),
        "earth_sites_processed": len(environment.earth_results),
        "surface_links_checked": len(environment.surface_results),
        "links_with_windows": sum(
            bool(link.windows)
            for link in prepared_problem.links
        ),
        "links_without_windows": sum(
            not bool(link.windows)
            for link in prepared_problem.links
        ),
        "sunlight_windows": len(prepared_problem.sunlight_windows),
    }

    return {
        "status": "completed",
        "source": "real_environment_preparation",
        "algorithm_comparison": {
            "candidate_count": len(candidates),
            "greedy": _serialize_result(greedy_result),
            "exact": (
                _serialize_result(exact_result)
                if exact_result is not None
                else None
            ),
            "exact_error": exact_error,
        },
        "candidates": [
            asdict(candidate)
            for candidate in candidates
        ],
        "environment": environment_summary,
        "warnings": environment.warnings,
        "limitations": [
            "Battery eligibility uses baseline energy-load windows.",
            "Schedule-dependent radio transmission energy is not simulated.",
            "Surface-link geometry is treated as static during the mission.",
            "Communication windows do not constitute a complete RF link-budget validation.",
            "Exact results are returned only when optimality is proven.",
        ],
    }
