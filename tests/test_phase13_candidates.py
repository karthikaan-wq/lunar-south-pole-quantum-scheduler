import pytest

from backend.scheduling.candidates import generate_candidates
from backend.scheduling.models import (
    LinkProfile,
    SchedulingProblem,
    TimeWindow,
    TransmissionTask,
)


def make_link(
    link_id,
    link_type,
    source,
    destination,
    rate,
    windows,
    resources=None,
):
    return LinkProfile(
        link_id=link_id,
        link_type=link_type,
        source_asset=source,
        destination_asset=destination,
        data_rate_bps=rate,
        radio_power_w=10,
        data_rate_source="test configuration",
        radio_power_source="test configuration",
        resource_ids=resources or [f"{link_id}_radio"],
        windows=[
            TimeWindow(start_s=start, end_s=end)
            for start, end in windows
        ],
    )


def make_task(
    route,
    volume=1000,
    release=0,
    deadline=100,
):
    return TransmissionTask(
        task_id="task_1",
        data_volume_bytes=volume,
        release_time_s=release,
        deadline_s=deadline,
        route_link_ids=route,
    )


def make_problem(links, task, step=10):
    return SchedulingProblem(
        horizon_start_s=0,
        horizon_end_s=100,
        candidate_step_s=step,
        links=links,
        tasks=[task],
    )


def test_direct_transmission_duration_is_calculated():
    link = make_link(
        "earth",
        "earth",
        "lander",
        "earth",
        rate=8000,
        windows=[(0, 20)],
    )
    task = make_task(["earth"], volume=1000)

    candidates = generate_candidates(
        make_problem([link], task)
    )

    assert candidates
    assert candidates[0].legs[0].end_s - candidates[0].legs[0].start_s == pytest.approx(1.0)


def test_direct_candidates_fit_inside_communication_windows():
    link = make_link(
        "earth",
        "earth",
        "lander",
        "earth",
        rate=8000,
        windows=[(0, 20)],
    )

    candidates = generate_candidates(
        make_problem([link], make_task(["earth"]))
    )

    assert candidates

    for candidate in candidates:
        leg = candidate.legs[0]
        assert leg.start_s >= 0
        assert leg.end_s <= 20


def test_direct_candidates_respect_release_time():
    link = make_link(
        "earth",
        "earth",
        "lander",
        "earth",
        rate=8000,
        windows=[(0, 50)],
    )

    candidates = generate_candidates(
        make_problem(
            [link],
            make_task(["earth"], release=20),
        )
    )

    assert candidates
    assert all(
        candidate.legs[0].start_s >= 20
        for candidate in candidates
    )


def test_direct_candidates_respect_deadline():
    link = make_link(
        "earth",
        "earth",
        "lander",
        "earth",
        rate=8000,
        windows=[(0, 50)],
    )

    candidates = generate_candidates(
        make_problem(
            [link],
            make_task(["earth"], deadline=5),
        )
    )

    assert candidates
    assert all(
        candidate.legs[0].end_s <= 5
        for candidate in candidates
    )


def test_transmission_too_long_for_window_has_no_candidate():
    link = make_link(
        "earth",
        "earth",
        "lander",
        "earth",
        rate=8000,
        windows=[(0, 0.5)],
    )

    candidates = generate_candidates(
        make_problem([link], make_task(["earth"]))
    )

    assert candidates == []


def test_direct_candidates_do_not_cross_separate_windows():
    link = make_link(
        "earth",
        "earth",
        "lander",
        "earth",
        rate=8000,
        windows=[(0, 0.6), (1, 1.9)],
    )

    candidates = generate_candidates(
        make_problem([link], make_task(["earth"]))
    )

    assert candidates == []


def test_two_hop_route_generates_surface_and_earth_legs():
    surface = make_link(
        "surface",
        "surface",
        "rover",
        "lander",
        rate=8000,
        windows=[(0, 20)],
    )
    earth = make_link(
        "earth",
        "earth",
        "lander",
        "earth",
        rate=8000,
        windows=[(0, 40)],
    )

    candidates = generate_candidates(
        make_problem(
            [surface, earth],
            make_task(["surface", "earth"]),
        )
    )

    assert candidates

    for candidate in candidates:
        assert len(candidate.legs) == 2
        assert candidate.legs[0].link_id == "surface"
        assert candidate.legs[1].link_id == "earth"


def test_store_and_forward_earth_leg_starts_after_surface_leg():
    surface = make_link(
        "surface",
        "surface",
        "rover",
        "lander",
        rate=8000,
        windows=[(0, 20)],
    )
    earth = make_link(
        "earth",
        "earth",
        "lander",
        "earth",
        rate=8000,
        windows=[(0, 40)],
    )

    candidates = generate_candidates(
        make_problem(
            [surface, earth],
            make_task(["surface", "earth"]),
        )
    )

    assert candidates

    for candidate in candidates:
        surface_leg, earth_leg = candidate.legs
        assert earth_leg.start_s >= surface_leg.end_s


def test_two_hop_earth_leg_must_fit_inside_its_window():
    surface = make_link(
        "surface",
        "surface",
        "rover",
        "lander",
        rate=8000,
        windows=[(0, 10)],
    )
    earth = make_link(
        "earth",
        "earth",
        "lander",
        "earth",
        rate=8000,
        windows=[(0, 0.5)],
    )

    candidates = generate_candidates(
        make_problem(
            [surface, earth],
            make_task(["surface", "earth"]),
        )
    )

    assert candidates == []


def test_candidate_records_required_radio_resources():
    link = make_link(
        "earth",
        "earth",
        "lander",
        "earth",
        rate=8000,
        windows=[(0, 20)],
        resources=["lander_radio", "earth_channel"],
    )

    candidates = generate_candidates(
        make_problem([link], make_task(["earth"]))
    )

    assert candidates
    assert candidates[0].legs[0].resource_ids == (
        "lander_radio",
        "earth_channel",
    )


def test_overlapping_windows_are_merged_without_losing_coverage():
    link = make_link(
        "earth",
        "earth",
        "lander",
        "earth",
        rate=8000,
        windows=[(0, 10), (5, 20)],
    )

    candidates = generate_candidates(
        make_problem([link], make_task(["earth"]))
    )

    assert candidates

    assert all(
        candidate.legs[0].end_s <= 20
        for candidate in candidates
    )


def test_candidate_generation_is_deterministic():
    link = make_link(
        "earth",
        "earth",
        "lander",
        "earth",
        rate=8000,
        windows=[(0, 30)],
    )
    problem = make_problem(
        [link],
        make_task(["earth"]),
    )

    first = generate_candidates(problem)
    second = generate_candidates(problem)

    assert first == second


