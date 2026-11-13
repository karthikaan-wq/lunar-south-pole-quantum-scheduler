
import math

import numpy as np
import pytest

from backend.physics.coordinates import azimuth_elevation


def test_north_direction():
    azimuth, elevation, distance = azimuth_elevation(
        [0, 0, 1], 0, 0
    )

    assert azimuth == pytest.approx(0.0)
    assert elevation == pytest.approx(0.0)
    assert distance == pytest.approx(1.0)


def test_east_direction():
    azimuth, elevation, distance = azimuth_elevation(
        [0, 1, 0], 0, 0
    )

    assert azimuth == pytest.approx(90.0)
    assert elevation == pytest.approx(0.0)
    assert distance == pytest.approx(1.0)


def test_south_direction():
    azimuth, elevation, distance = azimuth_elevation(
        [0, 0, -1], 0, 0
    )

    assert azimuth == pytest.approx(180.0)
    assert elevation == pytest.approx(0.0)
    assert distance == pytest.approx(1.0)


def test_west_direction():
    azimuth, elevation, distance = azimuth_elevation(
        [0, -1, 0], 0, 0
    )

    assert azimuth == pytest.approx(270.0)
    assert elevation == pytest.approx(0.0)
    assert distance == pytest.approx(1.0)


def test_diagonal_direction():
    vector = np.array([1.0, 1.0, 1.0])

    azimuth, elevation, distance = azimuth_elevation(
        vector, 0, 0
    )

    assert azimuth == pytest.approx(45.0)
    assert elevation == pytest.approx(
        math.degrees(math.asin(1 / math.sqrt(3)))
    )
    assert distance == pytest.approx(math.sqrt(3))


def test_non_equatorial_observer():
    lat = 45.0
    lon = 0.0

    north = np.array([
        -math.sin(math.radians(lat)),
        0.0,
        math.cos(math.radians(lat))
    ])

    azimuth, elevation, distance = azimuth_elevation(
        north, lat, lon
    )

    assert azimuth == pytest.approx(0.0)
    assert elevation == pytest.approx(0.0)
    assert distance == pytest.approx(1.0)


def test_zero_vector_rejected():
    with pytest.raises(ValueError):
        azimuth_elevation([0, 0, 0], 0, 0)


def test_invalid_vector_shape_rejected():
    with pytest.raises(ValueError):
        azimuth_elevation([1, 2], 0, 0)


def test_non_finite_vector_rejected():
    with pytest.raises(ValueError):
        azimuth_elevation([1, float("nan"), 0], 0, 0)
