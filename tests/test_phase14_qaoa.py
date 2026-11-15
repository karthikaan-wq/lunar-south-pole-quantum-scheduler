import pytest

from backend.scheduling.candidates import (
    ScheduleCandidate,
    TransmissionLeg,
)
from backend.scheduling.qaoa import (
    QAOASizeLimitError,
    qaoa_schedule,
)
from backend.scheduling.selection import candidates_conflict


def make_candidate(
    candidate_id,
    task_id,
    value,
    start,
    end,
    resources,
):
    return ScheduleCandidate(
        candidate_id=candidate_id,
        task_id=task_id,
        priority=1.0,
        data_volume_bytes=value,
        legs=(
            TransmissionLeg(
                link_id=f"link-{candidate_id}",
                start_s=start,
                end_s=end,
                resource_ids=tuple(resources),
            ),
        ),
    )


@pytest.fixture
def candidates():
    return [
        make_candidate("c1", "task-1", 100, 0, 10, ["radio-A"]),
        make_candidate("c2", "task-2", 80, 5, 15, ["radio-A"]),
        make_candidate("c3", "task-3", 50, 0, 10, ["radio-B"]),
    ]


def test_qaoa_returns_valid_result(candidates):
    result = qaoa_schedule(
        candidates,
        ["task-1", "task-2", "task-3"],
        depth=1,
        shots=256,
        max_iterations=30,
        seed=42,
    )

    assert result.backend == "numpy_statevector_simulator"
    assert result.qubit_count == 3
    assert result.circuit_depth == 1
    assert result.sample_count == 256
    assert result.schedule.algorithm == "qaoa_simulator"
    assert result.schedule.optimal is False
    assert result.schedule.objective_value >= 0


def test_qaoa_never_returns_resource_conflicts(candidates):
    result = qaoa_schedule(
        candidates,
        ["task-1", "task-2", "task-3"],
        shots=256,
        max_iterations=30,
        seed=7,
    )

    selected = result.schedule.selected_candidates

    for index, first in enumerate(selected):
        for second in selected[index + 1:]:
            assert first.task_id != second.task_id
            assert not candidates_conflict(first, second)


def test_qaoa_reports_qubit_limit(candidates):
    with pytest.raises(QAOASizeLimitError):
        qaoa_schedule(
            candidates,
            ["task-1", "task-2", "task-3"],
            max_qubits=2,
        )


def test_qaoa_handles_empty_candidates():
    result = qaoa_schedule(
        [],
        ["task-1", "task-2"],
    )

    assert result.qubit_count == 0
    assert result.schedule.objective_value == 0
    assert result.schedule.unscheduled_task_ids == (
        "task-1",
        "task-2",
    )


def test_qaoa_is_reproducible(candidates):
    first = qaoa_schedule(
        candidates,
        ["task-1", "task-2", "task-3"],
        shots=256,
        max_iterations=30,
        seed=123,
    )

    second = qaoa_schedule(
        candidates,
        ["task-1", "task-2", "task-3"],
        shots=256,
        max_iterations=30,
        seed=123,
    )

    assert first.schedule.objective_value == second.schedule.objective_value

    assert [
        item.candidate_id
        for item in first.schedule.selected_candidates
    ] == [
        item.candidate_id
        for item in second.schedule.selected_candidates
    ]


def test_qaoa_approximation_ratio_uses_reference(candidates):
    result = qaoa_schedule(
        candidates,
        ["task-1", "task-2", "task-3"],
        shots=256,
        max_iterations=30,
        seed=42,
        reference_objective=150.0,
    )

    assert result.approximation_ratio is not None
    assert result.approximation_ratio == pytest.approx(
        result.schedule.objective_value / 150.0
    )


def test_qaoa_does_not_claim_optimality(candidates):
    result = qaoa_schedule(
        candidates,
        ["task-1", "task-2", "task-3"],
        shots=256,
        max_iterations=30,
    )

    assert result.schedule.optimal is False
