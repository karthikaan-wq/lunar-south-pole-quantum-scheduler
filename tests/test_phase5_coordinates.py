
import numpy as np

from backend.physics.coordinates import (
    MOON_REFERENCE_RADIUS_KM,
    enu_matrix,
    local_axes,
    normalize_lon,
    surface_vector_moon_fixed,
)


R = MOON_REFERENCE_RADIUS_KM

SITES = [
    (-89.9, 129.78),
    (-85.99, 0.12),
    (-69.37, 32.32),
    (0.0, 0.0),
    (-45.0, -120.0),
]


def test_equator_and_pole_positions():
    assert np.allclose(
        surface_vector_moon_fixed(0, 0),
        [R, 0, 0]
    )

    assert np.allclose(
        surface_vector_moon_fixed(0, 90),
        [0, R, 0],
        atol=1e-9
    )

    assert np.allclose(
        surface_vector_moon_fixed(-90, 0),
        [0, 0, -R],
        atol=1e-9
    )


def test_radius_is_reference_radius_plus_height():
    for lat, lon in SITES:
        position = surface_vector_moon_fixed(lat, lon)

        assert abs(np.linalg.norm(position) - R) < 1e-9

    elevated_position = surface_vector_moon_fixed(
        -89.9, 129.78, 2000
    )

    assert abs(
        np.linalg.norm(elevated_position) - (R + 2.0)
    ) < 1e-9


def test_local_axes_are_orthonormal_and_right_handed():
    for lat, lon in SITES:
        east, north, up = local_axes(lat, lon)

        for vector in (east, north, up):
            assert abs(np.linalg.norm(vector) - 1) < 1e-12

        assert abs(east @ north) < 1e-12
        assert abs(east @ up) < 1e-12
        assert abs(north @ up) < 1e-12

        assert np.allclose(
            np.cross(east, north),
            up,
            atol=1e-12
        )


def test_up_points_away_from_moon_centre():
    for lat, lon in SITES:
        up = local_axes(lat, lon)[2]

        position = surface_vector_moon_fixed(lat, lon)

        assert np.allclose(
            up,
            position / R,
            atol=1e-12
        )


def test_east_and_north_directions():
    east, north, up = local_axes(-60, 40)

    step = (
        surface_vector_moon_fixed(-60, 40.01)
        - surface_vector_moon_fixed(-60, 40)
    )

    assert step @ east > 0
    assert abs(step @ north) < 1e-3 * abs(step @ east)

    assert north[2] > 0


def test_enu_matrix_is_a_rotation():
    matrix = enu_matrix(-85.99, 0.12)

    assert np.allclose(
        matrix @ matrix.T,
        np.eye(3),
        atol=1e-12
    )

    assert abs(np.linalg.det(matrix) - 1) < 1e-12


def test_normalize_lon():
    assert abs(normalize_lon(222.4) - (222.4 - 360)) < 1e-9

    assert abs(normalize_lon(-190) - 170) < 1e-9

    assert abs(abs(normalize_lon(180)) - 180) < 1e-9
