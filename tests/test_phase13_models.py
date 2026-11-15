import pytest
from pydantic import ValidationError

from backend.scheduling.models import (
    LinkProfile,
    SchedulingProblem,
    TimeWindow,
    TransmissionTask,
)


@pytest.fixture
def window():
    return TimeWindow(start_s=0, end_s=3600)


@pytest.fixture
def surface_link(window):
    return LinkProfile(
        link_id="surface",
        link_type="surface",
        source_asset="rover_1",
        destination_asset="lander_1",
        data_rate_bps=50000,
        radio_power_w=15,
        data_rate_source="test configuration",
        radio_power_source="test configuration",
        resource_ids=["rover_radio", "lander_radio"],
        windows=[window],
    )


@pytest.fixture
def earth_link(window):
    return LinkProfile(
        link_id="earth",
        link_type="earth",
        source_asset="lander_1",
        destination_asset="earth",
        data_rate_bps=100000,
        radio_power_w=25,
        data_rate_source="test configuration",
        radio_power_source="test configuration",
        resource_ids=["lander_earth_radio"],
        windows=[window],
    )


def make_task(route):
    return TransmissionTask(
        task_id="task_1",
        data_volume_bytes=1000000,
        release_time_s=0,
        deadline_s=3600,
        route_link_ids=route,
    )


def make_problem(links, tasks):
    return SchedulingProblem(
        horizon_start_s=0,
        horizon_end_s=3600,
        links=links,
        tasks=tasks,
    )


def test_valid_direct_to_earth_route(earth_link):
    task = make_task(["earth"])

    problem = make_problem([earth_link], [task])

    assert problem.tasks[0].route_link_ids == ["earth"]


def test_valid_rover_lander_earth_route(surface_link, earth_link):
    task = make_task(["surface", "earth"])

    problem = make_problem(
        [surface_link, earth_link],
        [task],
    )

    assert len(problem.tasks[0].route_link_ids) == 2


def test_unknown_link_is_rejected(earth_link):
    task = make_task(["missing_link"])

    with pytest.raises(ValidationError, match="unknown link"):
        make_problem([earth_link], [task])


def test_disconnected_two_hop_route_is_rejected(
    window,
    surface_link,
):
    disconnected_earth = LinkProfile(
        link_id="earth",
        link_type="earth",
        source_asset="another_lander",
        destination_asset="earth",
        data_rate_bps=100000,
        radio_power_w=25,
        data_rate_source="test configuration",
        radio_power_source="test configuration",
        resource_ids=["earth_radio"],
        windows=[window],
    )

    task = make_task(["surface", "earth"])

    with pytest.raises(ValidationError, match="disconnected route"):
        make_problem(
            [surface_link, disconnected_earth],
            [task],
        )


def test_two_hop_route_requires_surface_then_earth(
    window,
    earth_link,
):
    another_earth_link = earth_link.model_copy(
        update={
            "link_id": "earth_2",
            "source_asset": "earth",
        }
    )

    task = make_task(["earth", "earth_2"])

    with pytest.raises(ValidationError, match="surface link"):
        make_problem(
            [earth_link, another_earth_link],
            [task],
        )


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (10, 10),
        (20, 10),
        (float("nan"), 20),
        (0, float("inf")),
    ],
)
def test_invalid_time_windows_are_rejected(start, end):
    with pytest.raises(ValidationError):
        TimeWindow(start_s=start, end_s=end)


def test_duplicate_link_identifiers_are_rejected(
    surface_link,
):
    duplicate = surface_link.model_copy()

    with pytest.raises(ValidationError, match="Link identifiers"):
        make_problem(
            [surface_link, duplicate],
            [make_task(["surface"])],
        )


def test_duplicate_task_identifiers_are_rejected(earth_link):
    with pytest.raises(ValidationError, match="Task identifiers"):
        make_problem(
            [earth_link],
            [
                make_task(["earth"]),
                make_task(["earth"]),
            ],
        )


def test_invalid_deadline_is_rejected():
    with pytest.raises(ValidationError):
        TransmissionTask(
            task_id="invalid_task",
            data_volume_bytes=1000,
            release_time_s=0,
            deadline_s=0,
            route_link_ids=["earth"],
        )
