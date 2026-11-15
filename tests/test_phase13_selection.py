from backend.scheduling.candidates import (
    ScheduleCandidate,
    TransmissionLeg,
)
from backend.scheduling.selection import (
    candidates_conflict,
    greedy_schedule,
    legs_conflict,
    schedule_objective,
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
    leg = TransmissionLeg(
        link_id=f"link_{candidate_id}",
        start_s=start,
        end_s=end,
        resource_ids=tuple(resources),
    )

    return ScheduleCandidate(
        candidate_id=candidate_id,
        task_id=task_id,
        priority=priority,
        data_volume_bytes=volume,
        legs=(leg,),
    )


def test_overlapping_transmissions_on_shared_radio_conflict():
    first = make_candidate(
        "a", "task_a", 0, 10, ["radio_1"]
    )
    second = make_candidate(
        "b", "task_b", 5, 15, ["radio_1"]
    )

    assert candidates_conflict(first, second)


def test_overlapping_transmissions_on_different_radios_do_not_conflict():
    first = make_candidate(
        "a", "task_a", 0, 10, ["radio_1"]
    )
    second = make_candidate(
        "b", "task_b", 5, 15, ["radio_2"]
    )

    assert not candidates_conflict(first, second)


def test_adjacent_transmissions_do_not_conflict():
    first = make_candidate(
        "a", "task_a", 0, 10, ["radio_1"]
    )
    second = make_candidate(
        "b", "task_b", 10, 20, ["radio_1"]
    )

    assert not candidates_conflict(first, second)


def test_non_overlapping_transmissions_do_not_conflict():
    first = make_candidate(
        "a", "task_a", 0, 5, ["radio_1"]
    )
    second = make_candidate(
        "b", "task_b", 6, 10, ["radio_1"]
    )

    assert not candidates_conflict(first, second)


def test_shared_channel_causes_conflict():
    first = make_candidate(
        "a", "task_a", 0, 10, ["radio_a", "channel_1"]
    )
    second = make_candidate(
        "b", "task_b", 5, 15, ["radio_b", "channel_1"]
    )

    assert candidates_conflict(first, second)


def test_greedy_selects_higher_value_candidate():
    lower = make_candidate(
        "a", "task_a", 0, 10, ["radio_1"],
        priority=1,
        volume=1000,
    )
    higher = make_candidate(
        "b", "task_b", 0, 10, ["radio_1"],
        priority=2,
        volume=1000,
    )

    result = greedy_schedule(
        [lower, higher],
        ["task_a", "task_b"],
    )

    assert len(result.selected_candidates) == 1
    assert result.selected_candidates[0].task_id == "task_b"
    assert result.objective_value == 2000


def test_greedy_selects_multiple_non_conflicting_tasks():
    first = make_candidate(
        "a", "task_a", 0, 10, ["radio_1"]
    )
    second = make_candidate(
        "b", "task_b", 0, 10, ["radio_2"]
    )

    result = greedy_schedule(
        [first, second],
        ["task_a", "task_b"],
    )

    assert len(result.selected_candidates) == 2
    assert result.unscheduled_task_ids == ()
    assert result.objective_value == 2000


def test_greedy_schedules_each_task_at_most_once():
    first = make_candidate(
        "a", "task_a", 0, 10, ["radio_1"],
        priority=1,
        volume=1000,
    )
    alternative = make_candidate(
        "b", "task_a", 20, 30, ["radio_1"],
        priority=1,
        volume=1000,
    )

    result = greedy_schedule(
        [first, alternative],
        ["task_a"],
    )

    assert len(result.selected_candidates) == 1


def test_unscheduled_tasks_are_reported():
    candidate = make_candidate(
        "a", "task_a", 0, 10, ["radio_1"]
    )

    result = greedy_schedule(
        [candidate],
        ["task_a", "task_b"],
    )

    assert result.unscheduled_task_ids == ("task_b",)


def test_weighted_objective_calculation():
    first = make_candidate(
        "a", "task_a", 0, 10, ["radio_1"],
        priority=2,
        volume=1000,
    )
    second = make_candidate(
        "b", "task_b", 10, 20, ["radio_2"],
        priority=3,
        volume=500,
    )

    assert schedule_objective([first, second]) == 3500


def test_greedy_result_is_deterministic():
    first = make_candidate(
        "a", "task_a", 0, 10, ["radio_1"]
    )
    second = make_candidate(
        "b", "task_b", 20, 30, ["radio_2"]
    )

    first_result = greedy_schedule(
        [first, second],
        ["task_a", "task_b"],
    )
    second_result = greedy_schedule(
        [first, second],
        ["task_a", "task_b"],
    )

    assert first_result == second_result


def test_multi_leg_candidate_checks_every_leg_for_conflicts():
    first = ScheduleCandidate(
        candidate_id="first",
        task_id="task_first",
        priority=1,
        data_volume_bytes=1000,
        legs=(
            TransmissionLeg(
                link_id="surface",
                start_s=0,
                end_s=10,
                resource_ids=("rover_radio",),
            ),
            TransmissionLeg(
                link_id="earth",
                start_s=20,
                end_s=30,
                resource_ids=("lander_radio",),
            ),
        ),
    )

    second = make_candidate(
        "second",
        "task_second",
        25,
        35,
        ["lander_radio"],
    )

    assert candidates_conflict(first, second)


def test_legs_conflict_helper():
    first = TransmissionLeg(
        link_id="a",
        start_s=0,
        end_s=10,
        resource_ids=("radio_1",),
    )
    second = TransmissionLeg(
        link_id="b",
        start_s=5,
        end_s=15,
        resource_ids=("radio_1",),
    )

    assert legs_conflict(first, second)
