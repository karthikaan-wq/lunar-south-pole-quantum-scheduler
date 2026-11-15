from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.optimize import minimize

from backend.scheduling.candidates import ScheduleCandidate
from backend.scheduling.selection import (
    SchedulingResult,
    candidate_value,
    candidates_conflict,
    greedy_schedule,
)


class QAOASizeLimitError(RuntimeError):
    """Raised when a QAOA problem exceeds the configured qubit limit."""


@dataclass(frozen=True)
class QAOAResult:
    schedule: SchedulingResult
    backend: str
    qubit_count: int
    circuit_depth: int
    sample_count: int
    sampled_feasible_count: int
    expected_cost: float
    optimizer_success: bool
    approximation_ratio: float | None
    greedy_fallback_used: bool


def _build_conflicts(
    candidates: Sequence[ScheduleCandidate],
) -> list[tuple[int, int]]:
    """Build conflicts from shared tasks and shared resources."""
    conflicts = []

    for first in range(len(candidates)):
        for second in range(first + 1, len(candidates)):
            same_task = (
                candidates[first].task_id
                == candidates[second].task_id
            )

            resource_conflict = candidates_conflict(
                candidates[first],
                candidates[second],
            )

            if same_task or resource_conflict:
                conflicts.append((first, second))

    return conflicts


def _build_cost_function(
    candidates: Sequence[ScheduleCandidate],
    conflicts: list[tuple[int, int]],
):
    """
    Build a QUBO cost function for maximum-weight independent set.

    Minimization objective:
        - normalized candidate value
        + penalty for every conflicting selected pair.
    """
    count = len(candidates)

    weights = np.asarray(
        [candidate_value(candidate) for candidate in candidates],
        dtype=float,
    )

    if not np.all(np.isfinite(weights)) or np.any(weights < 0):
        raise ValueError(
            "QAOA candidate values must be finite and nonnegative."
        )

    maximum = float(np.max(weights)) if count else 1.0

    if maximum > 0:
        weights = weights / maximum

    # This penalty exceeds the maximum total normalized benefit.
    # Therefore, an optimal QUBO solution cannot contain a conflict.
    penalty = float(np.sum(weights) + 1.0)

    indices = np.arange(1 << count, dtype=np.uint64)

    bits = (
        (indices[:, None] >> np.arange(count, dtype=np.uint64))
        & 1
    ).astype(float)

    costs = -(bits @ weights)

    for first, second in conflicts:
        costs += penalty * bits[:, first] * bits[:, second]

    return bits, costs, penalty


def _apply_mixer(
    state: np.ndarray,
    beta: float,
    qubit_count: int,
) -> None:
    """Apply exp(-i beta X) independently to every qubit."""
    dimension = len(state)
    basis = np.arange(dimension, dtype=np.uint64)

    cosine = np.cos(beta)
    sine = -1j * np.sin(beta)

    for qubit in range(qubit_count):
        mask = np.uint64(1 << qubit)

        zero_indices = np.flatnonzero((basis & mask) == 0)
        one_indices = zero_indices | int(mask)

        zero_values = state[zero_indices].copy()
        one_values = state[one_indices].copy()

        state[zero_indices] = (
            cosine * zero_values + sine * one_values
        )

        state[one_indices] = (
            sine * zero_values + cosine * one_values
        )


def _simulate_qaoa(
    costs: np.ndarray,
    qubit_count: int,
    parameters: np.ndarray,
    depth: int,
) -> np.ndarray:
    """Simulate a standard X-mixer QAOA circuit."""
    dimension = 1 << qubit_count

    state = np.full(
        dimension,
        1.0 / np.sqrt(dimension),
        dtype=np.complex128,
    )

    gammas = parameters[:depth]
    betas = parameters[depth:]

    for gamma, beta in zip(gammas, betas):
        state *= np.exp(-1j * gamma * costs)
        _apply_mixer(state, beta, qubit_count)

    return state


def qaoa_schedule(
    candidates: list[ScheduleCandidate],
    task_ids: list[str] | tuple[str, ...],
    *,
    depth: int = 1,
    shots: int = 1024,
    max_qubits: int = 16,
    max_iterations: int = 60,
    seed: int = 42,
    reference_objective: float | None = None,
) -> QAOAResult:
    """
    Approximate transmission scheduling using simulated QAOA.

    Each candidate is represented by one qubit.

    The QUBO includes:
      - Candidate priority-weighted data volume.
      - At-most-one candidate per task.
      - Shared-resource conflict penalties.

    The implementation uses a NumPy statevector simulator,
    SciPy COBYLA parameter optimization and measurement sampling.

    It does not claim quantum-hardware execution or guaranteed
    global optimality.
    """
    if depth < 1:
        raise ValueError("QAOA depth must be at least 1.")

    if shots < 1:
        raise ValueError("QAOA shots must be at least 1.")

    if max_qubits < 1:
        raise ValueError("max_qubits must be at least 1.")

    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1.")

    qubit_count = len(candidates)

    if qubit_count > max_qubits:
        raise QAOASizeLimitError(
            f"QAOA received {qubit_count} candidates, but the "
            f"configured simulator limit is {max_qubits} qubits. "
            "Reduce the candidate set or increase the limit."
        )

    if not candidates:
        empty_schedule = SchedulingResult(
            algorithm="qaoa_simulator",
            selected_candidates=(),
            unscheduled_task_ids=tuple(task_ids),
            objective_value=0.0,
            candidate_count=0,
            optimal=False,
        )

        return QAOAResult(
            schedule=empty_schedule,
            backend="numpy_statevector_simulator",
            qubit_count=0,
            circuit_depth=depth,
            sample_count=0,
            sampled_feasible_count=0,
            expected_cost=0.0,
            optimizer_success=True,
            approximation_ratio=(
                1.0 if reference_objective == 0 else None
            ),
            greedy_fallback_used=False,
        )

    conflicts = _build_conflicts(candidates)

    bits, costs, _ = _build_cost_function(
        candidates,
        conflicts,
    )

    def expectation(parameters):
        state = _simulate_qaoa(
            costs,
            qubit_count,
            parameters,
            depth,
        )

        probabilities = np.abs(state) ** 2

        return float(np.dot(probabilities, costs))

    # Deterministic initial parameters for reproducibility.
    initial = np.concatenate(
        (
            np.full(depth, 0.4),
            np.full(depth, 0.3),
        )
    )

    optimization = minimize(
        expectation,
        initial,
        method="COBYLA",
        options={
            "maxiter": max_iterations,
            "rhobeg": 0.25,
            "tol": 1e-3,
        },
    )

    optimized_parameters = (
        optimization.x
        if optimization.x is not None
        else initial
    )

    final_state = _simulate_qaoa(
        costs,
        qubit_count,
        optimized_parameters,
        depth,
    )

    probabilities = np.abs(final_state) ** 2
    probabilities = probabilities / np.sum(probabilities)

    expected_cost = float(np.dot(probabilities, costs))

    rng = np.random.default_rng(seed)

    sampled_indices = rng.choice(
        len(probabilities),
        size=shots,
        replace=True,
        p=probabilities,
    )

    sampled_feasible_count = 0
    best_indices = None
    best_value = float("-inf")

    for state_index in sampled_indices:
        selected_indices = np.flatnonzero(bits[state_index])

        selected_set = set(selected_indices.tolist())

        feasible = all(
            first not in selected_set
            or second not in selected_set
            for first, second in conflicts
        )

        if not feasible:
            continue

        sampled_feasible_count += 1

        value = sum(
            candidate_value(candidates[index])
            for index in selected_indices
        )

        if value > best_value:
            best_value = value
            best_indices = selected_indices

    greedy_fallback_used = best_indices is None

    if greedy_fallback_used:
        # Never return an infeasible sampled schedule.
        fallback = greedy_schedule(candidates, task_ids)
        selected_candidates = fallback.selected_candidates
        objective_value = fallback.objective_value
    else:
        selected_candidates = tuple(
            candidates[index]
            for index in best_indices
        )

        selected_candidates = tuple(
            sorted(
                selected_candidates,
                key=lambda item: (
                    item.start_s,
                    item.end_s,
                    item.task_id,
                ),
            )
        )

        objective_value = sum(
            candidate_value(candidate)
            for candidate in selected_candidates
        )

    scheduled_tasks = {
        candidate.task_id
        for candidate in selected_candidates
    }

    unscheduled = tuple(
        task_id
        for task_id in task_ids
        if task_id not in scheduled_tasks
    )

    schedule = SchedulingResult(
        algorithm="qaoa_simulator",
        selected_candidates=selected_candidates,
        unscheduled_task_ids=unscheduled,
        objective_value=objective_value,
        candidate_count=len(candidates),
        optimal=False,
    )

    approximation_ratio = None

    if reference_objective is not None:
        if reference_objective > 0:
            approximation_ratio = (
                objective_value / reference_objective
            )
        elif reference_objective == 0:
            approximation_ratio = 1.0

    return QAOAResult(
        schedule=schedule,
        backend="numpy_statevector_simulator",
        qubit_count=qubit_count,
        circuit_depth=depth,
        sample_count=shots,
        sampled_feasible_count=sampled_feasible_count,
        expected_cost=expected_cost,
        optimizer_success=bool(optimization.success),
        approximation_ratio=approximation_ratio,
        greedy_fallback_used=greedy_fallback_used,
    )
