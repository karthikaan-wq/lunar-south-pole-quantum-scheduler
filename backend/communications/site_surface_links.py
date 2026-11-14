import math

import numpy as np

from ..terrain.dem_loader import load_dem_terrain
from ..terrain.projection import MOON_RADIUS_M
from .surface_links import SurfaceLinkSettings, link_matrix


DEFAULT_ANTENNA_HEIGHT_M = {
    "lander": 3.0,
    "rover": 1.5,
}


def load_terrain_window(
    lat_deg,
    lon_deg,
    half_size_m,
):
    """Load a square NASA LOLA terrain window around a surface location."""
    if not math.isfinite(half_size_m) or half_size_m <= 0:
        raise ValueError("Terrain window half-size must be positive and finite.")

    return load_dem_terrain(
        lat_deg,
        lon_deg,
        half_size_m=half_size_m,
    )


def _site_unit(lat_deg, lon_deg):
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)

    return np.array([
        math.cos(lat) * math.cos(lon),
        math.cos(lat) * math.sin(lon),
        math.sin(lat),
    ])


def surface_links_for_assets(
    assets,
    settings=None,
    margin_m=3000.0,
):
    """
    Load terrain and evaluate all unique links between fixed surface assets.

    Each asset must provide name, type, latitude_deg and longitude_deg.
    An optional antenna_height_m overrides the type-based default.
    """
    if not math.isfinite(margin_m) or margin_m < 0:
        raise ValueError("margin_m must be finite and non-negative.")

    assets = list(assets)

    if len(assets) < 2:
        raise ValueError("At least two surface assets are required.")

    names = [asset["name"] for asset in assets]

    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError("Every asset must have a non-empty name.")

    if len(names) != len(set(names)):
        raise ValueError("Asset names must be unique.")

    sites = {}
    antenna_heights = {}
    unit_vectors = []

    for asset in assets:
        asset_type = asset["type"]

        if asset_type not in DEFAULT_ANTENNA_HEIGHT_M:
            raise ValueError(
                f"Unsupported surface asset type: {asset_type!r}."
            )

        lat = float(asset["latitude_deg"])
        lon = float(asset["longitude_deg"])

        if not math.isfinite(lat) or not -90.0 <= lat <= 0.0:
            raise ValueError("Asset latitude must be between -90 and 0 degrees.")

        if not math.isfinite(lon):
            raise ValueError("Asset longitude must be finite.")

        height = asset.get(
            "antenna_height_m",
            DEFAULT_ANTENNA_HEIGHT_M[asset_type],
        )
        height = float(height)

        if not math.isfinite(height) or height < 0:
            raise ValueError("Antenna height must be finite and non-negative.")

        name = asset["name"]
        sites[name] = (lat, lon)
        antenna_heights[name] = height
        unit_vectors.append(_site_unit(lat, lon))

    centre_vector = np.sum(unit_vectors, axis=0)
    centre_norm = float(np.linalg.norm(centre_vector))

    if centre_norm < 1e-10:
        raise ValueError("Cannot determine a stable centre for these assets.")

    centre_vector /= centre_norm

    centre_lat = math.degrees(
        math.asin(float(np.clip(centre_vector[2], -1.0, 1.0)))
    )
    centre_lon = math.degrees(
        math.atan2(centre_vector[1], centre_vector[0])
    )

    farthest_distance_m = max(
        math.acos(
            float(np.clip(
                np.dot(centre_vector, vector),
                -1.0,
                1.0,
            ))
        ) * MOON_RADIUS_M
        for vector in unit_vectors
    )

    terrain_half_size_m = max(1000.0, farthest_distance_m + margin_m)

    terrain = load_terrain_window(
        centre_lat,
        centre_lon,
        terrain_half_size_m,
    )

    return link_matrix(
        terrain,
        sites,
        antenna_heights,
        settings=settings or SurfaceLinkSettings(),
    )
