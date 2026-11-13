
from functools import lru_cache
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds

from .projection import lonlat_to_xy
from .terrain_model import Terrain


# Default NASA LOLA DEM location.
DEFAULT_DEM_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "dem"
    / "LDEM_80S_80MPP_ADJ.TIF"
)


def _validate_inputs(
    lat_deg: float,
    lon_deg: float,
    half_size_m: float,
) -> tuple[float, float, float]:

    lat_deg = float(lat_deg)
    lon_deg = float(lon_deg)
    half_size_m = float(half_size_m)

    if not np.isfinite(lat_deg) or not -90.0 <= lat_deg <= 0.0:
        raise ValueError("Latitude must be between -90 and 0 degrees.")

    if not np.isfinite(lon_deg):
        raise ValueError("Longitude must be finite.")

    if not np.isfinite(half_size_m) or half_size_m <= 0:
        raise ValueError("Terrain half-size must be positive and finite.")

    lon_deg = ((lon_deg + 180.0) % 360.0) - 180.0

    return lat_deg, lon_deg, half_size_m


@lru_cache(maxsize=8)
def _load_dem_window(
    dem_path: str,
    lat_deg: float,
    lon_deg: float,
    half_size_m: float,
) -> Terrain:
    """
    Load a square terrain window from the NASA LOLA GeoTIFF.

    The returned Terrain uses pixel-centre coordinates,
    matching the existing Terrain.height_at() convention.
    """

    path = Path(dem_path)

    if not path.is_file():
        raise FileNotFoundError(
            f"NASA LOLA DEM was not found: {path}"
        )

    with rasterio.open(path) as dataset:

        if not dataset.crs:
            raise ValueError("NASA DEM does not contain a CRS.")

        if not dataset.crs.is_projected:
            raise ValueError("NASA DEM must use a projected CRS.")

        if dataset.count != 1:
            raise ValueError("Expected a single-band NASA DEM.")

        pixel_x, pixel_y = dataset.res

        if (
            not np.isfinite(pixel_x)
            or not np.isfinite(pixel_y)
            or pixel_x <= 0
            or pixel_y <= 0
            or not np.isclose(pixel_x, pixel_y)
        ):
            raise ValueError("NASA DEM must have square, positive pixels.")

        # Convert geographic coordinates into the actual NASA CRS.
        transformer = Transformer.from_crs(
            dataset.crs.geodetic_crs,
            dataset.crs,
            always_xy=True,
        )

        site_x, site_y = transformer.transform(
            lon_deg,
            lat_deg,
        )

        if not np.isfinite(site_x) or not np.isfinite(site_y):
            raise ValueError("Could not project the requested lunar site.")

        # Verify that the NASA CRS agrees with our existing projection.
        expected_x, expected_y = lonlat_to_xy(
            lat_deg,
            lon_deg,
        )

        if not np.allclose(
            [site_x, site_y],
            [expected_x, expected_y],
            atol=0.1,
        ):
            raise ValueError(
                "NASA DEM projection does not match the project projection."
            )

        # Calculate the requested square window.
        left = site_x - half_size_m
        right = site_x + half_size_m
        bottom = site_y - half_size_m
        top = site_y + half_size_m

        window = from_bounds(
            left,
            bottom,
            right,
            top,
            transform=dataset.transform,
        )

        # Align the window to complete raster pixels.
        window = window.round_offsets().round_lengths()

        if window.width < 2 or window.height < 2:
            raise ValueError(
                "Requested terrain window is too small."
            )

        # Read only this window, not the entire 180 MB DEM.
        heights = dataset.read(
            1,
            window=window,
            boundless=True,
            fill_value=np.nan,
            out_dtype="float32",
        )

        # Convert any invalid or missing values to NaN.
        heights = np.asarray(heights, dtype=np.float32)
        heights[~np.isfinite(heights)] = np.nan

        # Get the affine transform for this particular window.
        window_transform = dataset.window_transform(window)

        # Rasterio gives pixel-corner coordinates.
        # Terrain expects the centre of pixel [0, 0].
        x0 = window_transform.c + window_transform.a / 2.0
        y0 = window_transform.f + window_transform.e / 2.0

        return Terrain(
            heights=heights,
            x0=x0,
            y0=y0,
            pixel_m=float(pixel_x),
        )


def load_dem_terrain(
    lat_deg: float,
    lon_deg: float,
    half_size_m: float = 41000.0,
    dem_path: str | Path = DEFAULT_DEM_PATH,
) -> Terrain:
    """
    Load real lunar terrain around a requested location.

    Parameters
    ----------
    lat_deg:
        Lunar latitude in degrees, from -90 to 0.

    lon_deg:
        East-positive lunar longitude in degrees.

    half_size_m:
        Half the width and height of the requested square
        terrain window, in metres.

    dem_path:
        Path to the NASA LOLA GeoTIFF.

    Returns
    -------
    Terrain
        A Terrain object compatible with horizon_profile().
    """

    lat_deg, lon_deg, half_size_m = _validate_inputs(
        lat_deg,
        lon_deg,
        half_size_m,
    )

    return _load_dem_window(
        str(Path(dem_path).resolve()),
        lat_deg,
        lon_deg,
        half_size_m,
    )


def clear_dem_cache() -> None:
    """Clear cached terrain windows."""
    _load_dem_window.cache_clear()


def dem_cache_info():
    """Return terrain-window cache statistics."""
    return _load_dem_window.cache_info()
