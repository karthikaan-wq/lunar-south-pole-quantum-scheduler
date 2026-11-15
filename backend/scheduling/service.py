from __future__ import annotations

from dataclasses import asdict
from typing import Any

from backend.scheduling.candidates import (
    CandidateGenerationLimitError,
    ScheduleCandidate,
    generate_candidates,
)
from backend.scheduling.environment import prepare_environment
from backend.scheduling.exact import (
    ExactSolveError,
    ExactSolveLimitError,
    exact_schedule,
)
from backend.scheduling.models import SchedulingProblem
from backend.scheduling.qaoa import (
    QAOASizeLimitError,
    qaoa_schedule,
)
from backend.scheduling.selection import greedy_schedule


QAOA_MAX_QUBITS = 16


def _serialize_result(result) -> dict[str, Any]:
    return asdict(result)


def _select_qaoa_candidates(
    candidates: list[ScheduleCandidate],
    task_ids: list[str],
    limit: int = QAOA_MAX_QUBITS,
) -> list[ScheduleCandidate]:
    """
    Select a deterministic, task-balanced subset for QAOA.

    Candidates are ranked by priority-weighted data volume
    within each task. Selection proceeds round-robin so that
    multiple tasks are represented where possible.
    """
    grouped: dict[str, list[ScheduleCandidate]] = {
        task_id: [] for task_id in task_ids
    }

    for candidate in candidates:
        grouped.setdefault(candidate.task_id, []).append(candidate)

    for task_candidates in grouped.values():
        task_candidates.sort(
            key=lambda item: (
                -(item.priority * item.data_volume_bytes),
                item.start_s,
                item.end_s,
                item.candidate_id,
            )
        )

    selected = []
    depth = 0

    while len(selected) < limit:
        added = False

        for task_id in task_ids:
            options = grouped.get(task_id, [])

            if depth < len(options):
                selected.append(options[depth])
                added = True

                if len(selected) >= limit:
                    break

        if not added:
            break

        depth += 1

    return selected


def run_classical_scheduler(
    problem: SchedulingProblem,
) -> dict[str, Any]:
    """
    Prepare real environmental windows and compare Greedy,
    Exact, and simulated QAOA scheduling.

    Greedy and Exact use the complete generated candidate set.
    QAOA uses a bounded, task-balanced candidate subset.
    """

    # 1. Prepare energy, Earth visibility, and surface-link windows.
    environment = prepare_environment(problem)
    prepared_problem = environment.problem

    # 2. Generate the shared candidate set.
    candidates = generate_candidates(
        prepared_problem,
        max_candidates=prepared_problem.max_exact_candidates,
    )

    task_ids = [
        task.task_id
        for task in prepared_problem.tasks
    ]

    # 3. Run Greedy on all candidates.
    greedy_result = greedy_schedule(
        candidates,
        task_ids,
    )

    # 4. Run Exact on all candidates.
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

    # 5. Prepare a bounded candidate subset for QAOA.
    qaoa_candidates = _select_qaoa_candidates(
        candidates,
        task_ids,
        QAOA_MAX_QUBITS,
    )

    qaoa_result = None
    qaoa_error = None
    qaoa_reference = None
    qaoa_reference_algorithm = None

    # 6. Establish a reference objective on exactly the same subset.
    qaoa_greedy_reference = greedy_schedule(
        qaoa_candidates,
        task_ids,
    )

    try:
        qaoa_exact_reference = exact_schedule(
            qaoa_candidates,
            task_ids,
            max_candidates=QAOA_MAX_QUBITS,
        )

        qaoa_reference = qaoa_exact_reference.objective_value
        qaoa_reference_algorithm = "exact_on_qaoa_subset"

    except (
        ExactSolveLimitError,
        ExactSolveError,
        ValueError,
    ):
        qaoa_reference = qaoa_greedy_reference.objective_value
        qaoa_reference_algorithm = "greedy_on_qaoa_subset"

    # 7. Run simulated QAOA.
    try:
        qaoa_result = qaoa_schedule(
            qaoa_candidates,
            task_ids,
            depth=1,
            shots=1024,
            max_qubits=QAOA_MAX_QUBITS,
            max_iterations=60,
            seed=42,
            reference_objective=qaoa_reference,
        )

    except (
        QAOASizeLimitError,
        ValueError,
        RuntimeError,
    ) as error:
        qaoa_error = str(error)

    # 8. Environmental evidence.
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
            "qaoa": (
                _serialize_result(qaoa_result.schedule)
                if qaoa_result is not None
                else None
            ),
            "qaoa_error": qaoa_error,
            "qaoa_metadata": (
                {
                    "backend": qaoa_result.backend,
                    "qubit_count": qaoa_result.qubit_count,
                    "circuit_depth": qaoa_result.circuit_depth,
                    "shots": qaoa_result.sample_count,
                    "sampled_feasible_count": (
                        qaoa_result.sampled_feasible_count
                    ),
                    "expected_cost": qaoa_result.expected_cost,
                    "optimizer_success": (
                        qaoa_result.optimizer_success
                    ),
                    "approximation_ratio": (
                        qaoa_result.approximation_ratio
                    ),
                    "greedy_fallback_used": (
                        qaoa_result.greedy_fallback_used
                    ),
                    "reference_algorithm": (
                        qaoa_reference_algorithm
                    ),
                    "reference_objective": qaoa_reference,
                    "original_candidate_count": len(candidates),
                    "candidates_used": len(qaoa_candidates),
                    "candidate_reduction": (
                        len(candidates) - len(qaoa_candidates)
                    ),
                    "is_hardware_execution": False,
                }
                if qaoa_result is not None
                else None
            ),
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
            "QAOA is a NumPy statevector simulation, not quantum-hardware execution.",
            "QAOA uses a task-balanced subset of at most 16 candidates.",
            "QAOA results are approximate and are not guaranteed globally optimal.",
        ],
    }
