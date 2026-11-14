import pytest

from backend.communications.surface_opportunities import (
    compose_surface_opportunities,
    power_eligible_windows,
)


BASE = "2026-01-01T00:00:00Z"


def make_energy(flags, step_seconds=3600):
    from datetime import datetime, timedelta, timezone

    start = datetime.fromisoformat(BASE.replace("Z", "+00:00"))
    samples = []

    for index, eligible in enumerate(flags):
        timestamp = start + timedelta(seconds=index * step_seconds)
        samples.append({
            "utc": timestamp.isoformat(),
            "battery_soc": 0.8 if eligible else 0.1,
            "below_minimum_soc": not eligible,
        })

    return {"samples": samples}


def epoch(hour):
    from datetime import datetime, timedelta, timezone

    start = datetime.fromisoformat(BASE.replace("Z", "+00:00"))
    return (start + timedelta(hours=hour)).timestamp()


def test_power_eligible_windows_extracts_sampled_runs():
    result = power_eligible_windows(
        make_energy([True, True, False, True, True])
    )

    assert len(result) == 2
    assert result[0]["start_s"] == epoch(0)
    assert result[0]["end_s"] == epoch(1)
    assert result[1]["start_s"] == epoch(3)
    assert result[1]["end_s"] == epoch(4)


def test_power_eligibility_rejects_zero_soc():
    energy = make_energy([True, True])
    energy["samples"][1]["battery_soc"] = 0.0

    result = power_eligible_windows(energy)

    assert len(result) == 1
    assert result[0]["start_s"] == epoch(0)
    assert result[0]["end_s"] == epoch(0)


def test_power_eligibility_rejects_invalid_soc():
    energy = make_energy([True, True])
    energy["samples"][1]["battery_soc"] = 1.5

    with pytest.raises(ValueError, match="outside 0..1"):
        power_eligible_windows(energy)


def test_common_power_windows_are_intersected():
    result = compose_surface_opportunities(
        link_metrics={"usable": True},
        rover_energy=make_energy([True, True, True, False, True, True]),
        lander_energy=make_energy([False, True, True, True, True, False]),
        earth_windows=[],
    )

    assert result["common_power_window_count"] == 1
    assert result["uplink_window_count"] == 1

    uplink = result["uplink_windows"][0]
    assert uplink["start_s"] == epoch(1)
    assert uplink["end_s"] == epoch(2)


def test_blocked_surface_link_prevents_all_uplinks():
    result = compose_surface_opportunities(
        link_metrics={"usable": False},
        rover_energy=make_energy([True, True, True]),
        lander_energy=make_energy([True, True, True]),
        earth_windows=[
            {"start_s": epoch(0), "end_s": epoch(5)}
        ],
    )

    assert result["common_power_window_count"] == 1
    assert result["uplink_window_count"] == 0
    assert result["forwarding_options"] == []


def test_store_and_forward_waits_for_next_earth_window():
    result = compose_surface_opportunities(
        link_metrics={"usable": True},
        rover_energy=make_energy([True, True]),
        lander_energy=make_energy([True, True]),
        earth_windows=[
            {"start_s": epoch(1.5), "end_s": epoch(3)}
        ],
    )

    assert result["uplink_window_count"] == 1

    forwarding = result["forwarding_options"][0]["options"]
    assert len(forwarding) == 1
    assert forwarding[0]["wait_s"] == pytest.approx(1800)
    assert forwarding[0]["forward_s"] == pytest.approx(5400)


def test_overlapping_earth_window_has_zero_wait():
    result = compose_surface_opportunities(
        link_metrics={"usable": True},
        rover_energy=make_energy([True, True]),
        lander_energy=make_energy([True, True]),
        earth_windows=[
            {"start_s": epoch(0.5), "end_s": epoch(2)}
        ],
    )

    option = result["forwarding_options"][0]["options"][0]
    assert option["wait_s"] == 0.0
    assert option["forward_s"] == pytest.approx(3600)


def test_earth_window_beyond_maximum_wait_is_rejected():
    result = compose_surface_opportunities(
        link_metrics={"usable": True},
        rover_energy=make_energy([True, True]),
        lander_energy=make_energy([True, True]),
        earth_windows=[
            {"start_s": epoch(14), "end_s": epoch(16)}
        ],
    )

    assert result["forwarding_options"][0]["options"] == []


def test_earth_window_shorter_than_minimum_forward_time_is_rejected():
    result = compose_surface_opportunities(
        link_metrics={"usable": True},
        rover_energy=make_energy([True, True]),
        lander_energy=make_energy([True, True]),
        earth_windows=[
            {"start_s": epoch(1), "end_s": epoch(1) + 120}
        ],
    )

    assert result["forwarding_options"][0]["options"] == []


def test_invalid_energy_samples_are_rejected():
    with pytest.raises(ValueError, match="At least two"):
        power_eligible_windows(make_energy([True]))

    energy = make_energy([True, True])
    energy["samples"][1]["utc"] = energy["samples"][0]["utc"]

    with pytest.raises(ValueError, match="strictly increasing"):
        power_eligible_windows(energy)



def test_unmet_load_breaks_power_eligible_window():
    energy = make_energy([True, True, True, True])
    energy["samples"][1]["unmet_load_wh_since_previous_sample"] = 0.5

    result = power_eligible_windows(energy)

    assert len(result) == 2
    assert result[0]["start_s"] == epoch(0)
    assert result[0]["end_s"] == epoch(0)
    assert result[1]["start_s"] == epoch(2)
    assert result[1]["end_s"] == epoch(3)


@pytest.mark.parametrize("unmet_load", [-0.1, float("nan"), float("inf")])
def test_power_eligibility_rejects_invalid_unmet_load(unmet_load):
    energy = make_energy([True, True])
    energy["samples"][1]["unmet_load_wh_since_previous_sample"] = unmet_load

    with pytest.raises(ValueError, match="invalid unmet-load energy"):
        power_eligible_windows(energy)
