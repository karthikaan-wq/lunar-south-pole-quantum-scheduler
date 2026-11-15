import pytest

from backend.scheduling.candidates import (
    ScheduleCandidate,
    TransmissionLeg,
)
from backend.scheduling.exact import (
    ExactSolveLimitError,
    exact_schedule,
)
from backend.scheduling.selection import (
    greedy_schedule,
)


def make_candidate(
    candidate_id,
    task_id,
    start,
    end,
    resources,
    priority=1.0,
    volume=1000,
):
    return ScheduleCandidate(
        candidate_id=candidate_id,
        task_id=task_id,
        priority=priority,
        data_volume_bytes=volume,
        legs=(
            TransmissionLeg(
                link_id=f"link_{candidate_id}",
                start_s=start,
                end_s=end,
                resource_ids=tuple(resources),
            ),
        ),
    )


def test_exact_selects_higher_value_conflicting_candidate():
    low = make_candidate(
        "low",
        "task_low",
        0,
        10,
        ["radio_1"],
        priority=1,
        volume=1000,
    )
    high = make_candidate(
        "high",
        "task_high",
        0,
        10,
        ["radio_1"],
        priority=3,
        volume=1000,
    )

    result = exact_schedule(
        [low, high],
        ["task_low", "task_high"],
    )

    assert result.optimal is True
    assert result.objective_value == 3000
    assert [
        item.task_id for item in result.selected_candidates
    ] == ["task_high"]
    assert result.unscheduled_task_ids == ("task_low",)


def test_exact_selects_both_non_conflicting_candidates():
    first = make_candidate(
        "first",
        "task_first",
        0,
        10,
        ["radio_1"],
    )
    second = make_candidate(
        "second",
        "task_second",
        0,
        10,
        ["radio_2"],
    )

    result = exact_schedule(
        [first, second],
        ["task_first", "task_second"],
    )

    assert len(result.selected_candidates) == 2
    assert result.objective_value == 2000
    assert result.unscheduled_task_ids == ()


def test_exact_finds_global_optimum_not_greedy_choice():
    # The highest-value task occupies the entire interval.
    # Two smaller tasks can run consecutively and yield more value.
    large = make_candidate(
        "large",
        "task_large",
        0,
        20,
        ["radio_1"],
        priority=1,
        volume=100,
    )
    small_a = make_candidate(
        "small_a",
        "task_small_a",
        0,
        10,
        ["radio_1"],
        priority=1,
        volume=60,
    )
    small_b = make_candidate(
        "small_b",
        "task_small_b",
        10,
        20,
        ["radio_1"],
        priority=1,
        volume=60,
    )

    candidates = [large, small_a, small_b]
    task_ids = [
        "task_large",
        "task_small_a",
        "task_small_b",
    ]

    greedy = greedy_schedule(candidates, task_ids)
    exact = exact_schedule(candidates, task_ids)

    assert greedy.objective_value == 100
    assert exact.objective_value == 120

    assert {
        candidate.task_id
        for candidate in exact.selected_candidates
    } == {"task_small_a", "task_small_b"}

    assert exact.optimal is True


def test_exact_respects_shared_channel_conflicts():
    first = make_candidate(
        "first",
        "task_first",
        0,
        10,
        ["radio_a", "channel_1"],
    )
    second = make_candidate(
        "second",
        "task_second",
        0,
        10,
        ["radio_b", "channel_1"],
    )

    result = exact_schedule(
        [first, second],
        ["task_first", "task_second"],
    )

    assert len(result.selected_candidates) == 1
    assert result.objective_value == 1000


def test_exact_allows_adjacent_transmissions():
    first = make_candidate(
        "first",
        "task_first",
        0,
        10,
        ["radio_1"],
    )
    second = make_candidate(
        "second",
        "task_second",
        10,
        20,
        ["radio_1"],
    )

    result = exact_schedule(
        [first, second],
        ["task_first", "task_second"],
    )

    assert len(result.selected_candidates) == 2
    assert result.objective_value == 2000


def test_exact_schedules_each_task_at_most_once():
    first = make_candidate(
        "first",
        "task_a",
        0,
        10,
        ["radio_1"],
    )
    alternative = make_candidate(
        "alternative",
        "task_a",
        20,
        30,
        ["radio_1"],
    )

    result = exact_schedule(
        [first, alternative],
        ["task_a"],
    )

    assert len(result.selected_candidates) == 1


def test_exact_reports_unscheduled_tasks():
    candidate = make_candidate(
        "candidate",
        "task_a",
        0,
        10,
        ["radio_1"],
    )

    result = exact_schedule(
        [candidate],
        ["task_a", "task_b"],
    )

    assert result.unscheduled_task_ids == ("task_b",)


def test_exact_empty_candidate_set_is_optimal():
    result = exact_schedule(
        [],
        ["task_a", "task_b"],
    )

    assert result.optimal is True
    assert result.objective_value == 0
    assert result.selected_candidates == ()
    assert result.unscheduled_task_ids == (
        "task_a",
        "task_b",
    )


def test_exact_candidate_limit_is_enforced():
    candidate = make_candidate(
        "candidate",
        "task_a",
        0,
        10,
        ["radio_1"],
    )

    with pytest.raises(ValueError, match="max_candidates"):
        exact_schedule(
            [candidate],
            ["task_a"],
            max_candidates=0,
        )


def test_exact_candidate_count_limit_is_enforced():
    first = make_candidate(
        "first",
        "task_a",
        0,
        10,
        ["radio_1"],
    )
    second = make_candidate(
        "second",
        "task_b",
        20,
        30,
        ["radio_1"],
    )

    with pytest.raises(ExactSolveLimitError, match="candidate limit"):
        exact_schedule(
            [first, second],
            ["task_a", "task_b"],
            max_candidates=1,
        )


def test_exact_conflict_pair_limit_is_enforced():
    first = make_candidate(
        "first",
        "task_a",
        0,
        10,
        ["radio_1"],
    )
    second = make_candidate(
        "second",
        "task_b",
        5,
        15,
        ["radio_1"],
    )

    with pytest.raises(ExactSolveLimitError, match="conflict-pair limit"):
        exact_schedule(
            [first, second],
            ["task_a", "task_b"],
            max_conflict_pairs=0,
        )


def test_exact_result_is_deterministic():
    first = make_candidate(
        "first",
        "task_a",
        0,
        10,
        ["radio_1"],
    )
    second = make_candidate(
        "second",
        "task_b",
        20,
        30,
        ["radio_2"],
    )

    result_a = exact_schedule(
        [first, second],
        ["task_a", "task_b"],
    )
    result_b = exact_schedule(
        [first, second],
        ["task_a", "task_b"],
    )

    assert result_a == result_b
