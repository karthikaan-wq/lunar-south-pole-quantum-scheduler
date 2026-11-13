
import math

import numpy as np
import pytest
import rasterio

from backend.terrain.dem_loader import (
    DEFAULT_DEM_PATH,
    clear_dem_cache,
    dem_cache_info,
    load_dem_terrain,
)


NASA_DEM_AVAILABLE = DEFAULT_DEM_PATH.is_file()


@pytest.fixture(autouse=True)
def clear_cache_before_and_after():
    clear_dem_cache()
    yield
    clear_dem_cache()


def test_missing_dem_file_is_reported(tmp_path):
    missing_path = tmp_path / "missing_dem.tif"

    with pytest.raises(FileNotFoundError, match="NASA LOLA DEM"):
        load_dem_terrain(
            -89.9,
            129.78,
            half_size_m=1000,
            dem_path=missing_path,
        )


@pytest.mark.parametrize(
    "latitude,longitude,half_size",
    [
        (1.0, 0.0, 1000.0),
        (-91.0, 0.0, 1000.0),
        (-89.0, float("nan"), 1000.0),
        (-89.0, 0.0, 0.0),
        (-89.0, 0.0, -1000.0),
    ],
)
def test_invalid_loader_inputs_are_rejected(
    latitude,
    longitude,
    half_size,
):
    with pytest.raises(ValueError):
        load_dem_terrain(
            latitude,
            longitude,
            half_size_m=half_size,
        )


@pytest.mark.skipif(
    not NASA_DEM_AVAILABLE,
    reason="NASA LOLA DEM is not installed.",
)
def test_nasa_dem_loads_real_shackleton_terrain():
    terrain = load_dem_terrain(
        lat_deg=-89.9,
        lon_deg=129.78,
        half_size_m=5000.0,
    )

    assert terrain.heights.ndim == 2
    assert terrain.heights.shape[0] >= 2
    assert terrain.heights.shape[1] >= 2

    assert terrain.pixel_m == pytest.approx(80.0)

    assert np.isfinite(terrain.heights).any()

    site_height = terrain.height_at(
        2330.37,
        -1940.21,
    )

    assert math.isfinite(site_height)
    assert -1000.0 < site_height < 1000.0


@pytest.mark.skipif(
    not NASA_DEM_AVAILABLE,
    reason="NASA LOLA DEM is not installed.",
)
def test_loaded_pixel_centre_matches_original_dem():
    terrain = load_dem_terrain(
        lat_deg=-89.9,
        lon_deg=129.78,
        half_size_m=5000.0,
    )

    # The first Terrain pixel coordinate must represent
    # the centre of the first loaded raster pixel.
    expected_height = float(terrain.heights[0, 0])

    with rasterio.open(DEFAULT_DEM_PATH) as dataset:
        original_height = float(
            next(
                dataset.sample(
                    [(terrain.x0, terrain.y0)]
                )
            )[0]
        )

    assert math.isfinite(original_height)

    assert terrain.height_at(
        terrain.x0,
        terrain.y0,
    ) == pytest.approx(expected_height, abs=1e-4)

    assert expected_height == pytest.approx(
        original_height,
        abs=1e-3,
    )


@pytest.mark.skipif(
    not NASA_DEM_AVAILABLE,
    reason="NASA LOLA DEM is not installed.",
)
def test_dem_window_cache_reuses_loaded_terrain():
    first = load_dem_terrain(
        -89.9,
        129.78,
        half_size_m=5000.0,
    )

    second = load_dem_terrain(
        -89.9,
        129.78,
        half_size_m=5000.0,
    )

    cache = dem_cache_info()

    assert first is second
    assert cache.hits == 1
    assert cache.currsize == 1
