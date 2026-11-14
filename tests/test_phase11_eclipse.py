from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from backend.physics.kernels import kernels_present
from backend.physics.earth_samples import earth_samples_at
from backend.physics.sun_geometry import sun_at_times
from backend.energy.sun_visibility import occulted_fraction
from backend.communications.antenna import angular_separation_deg


pytestmark = pytest.mark.skipif(
    not kernels_present(),
    reason="SPICE kernels are not available",
)


SITE = (-85.99, 0.12, 0.0)


def make_times(start, duration_hours, step_minutes):
    count = int(duration_hours * 60 / step_minutes) + 1
    return [
        (
            start + timedelta(minutes=step_minutes * i)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        for i in range(count)
    ]


def eclipse_factors(times):
    lat, lon, height = SITE

    sun = sun_at_times(lat, lon, height, times)
    earth = earth_samples_at(lat, lon, height, times)

    factors = []

    for s, e in zip(sun, earth):
        separation = angular_separation_deg(
            s["azimuth_deg"],
            s["elevation_deg"],
            e["azimuth_deg"],
            e["elevation_deg"],
        )

        hidden = occulted_fraction(
            separation,
            s["angular_radius_deg"],
            e["angular_radius_deg"],
        )

        factors.append(1.0 - float(hidden))

    return np.asarray(factors)


def test_march_2026_lunar_eclipse_is_detected_from_moon():
    start = datetime(2026, 3, 3, 9, 0, tzinfo=timezone.utc)
    times = make_times(start, duration_hours=5, step_minutes=10)

    factors = eclipse_factors(times)

    assert len(factors) == 31
    assert np.min(factors) < 0.999
    assert np.min(factors) >= 0.0
    assert np.max(factors) <= 1.0


def test_november_2026_control_period_has_no_lunar_eclipse():
    start = datetime(2026, 11, 14, 0, 0, tzinfo=timezone.utc)
    times = make_times(start, duration_hours=28 * 24, step_minutes=120)

    factors = eclipse_factors(times)

    assert len(factors) == 337
    assert np.min(factors) > 0.999
    assert np.max(factors) <= 1.0
