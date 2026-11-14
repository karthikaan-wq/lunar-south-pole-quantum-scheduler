import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from backend.terrain.dem_loader import load_dem_terrain
from backend.terrain.projection import (
    MOON_RADIUS_M,
    lonlat_to_xy,
    xy_to_lonlat,
)

SHACKLETON = (-89.9, 129.78)


def destination(lat, lon, azimuth_deg, distance_m):
    d = distance_m / MOON_RADIUS_M
    az = math.radians(azimuth_deg)

    la1 = math.radians(lat)
    lo1 = math.radians(lon)

    la2 = math.asin(
        math.sin(la1) * math.cos(d)
        + math.cos(la1) * math.sin(d) * math.cos(az)
    )

    lo2 = lo1 + math.atan2(
        math.sin(az) * math.sin(d) * math.cos(la1),
        math.cos(d) - math.sin(la1) * math.sin(la2),
    )

    return math.degrees(la2), math.degrees(lo2)


terrain = load_dem_terrain(
    *SHACKLETON,
    half_size_m=25000,
)

cx, cy = lonlat_to_xy(*SHACKLETON)

xs = terrain.x0 + terrain.pixel_m * np.arange(
    terrain.heights.shape[1]
)

ys = terrain.y0 - terrain.pixel_m * np.arange(
    terrain.heights.shape[0]
)

x_grid, y_grid = np.meshgrid(xs, ys)

r = np.hypot(
    x_grid - cx,
    y_grid - cy,
)

heights = terrain.heights


def pick(mask, use_min):
    valid = mask & np.isfinite(heights)

    if not np.any(valid):
        raise ValueError(
            "No valid DEM pixels found in the requested region."
        )

    values = np.where(
        valid,
        heights,
        np.inf if use_min else -np.inf,
    )

    i = np.unravel_index(
        np.argmin(values) if use_min else np.argmax(values),
        values.shape,
    )

    lat, lon = xy_to_lonlat(
        x_grid[i],
        y_grid[i],
    )

    return (
        float(lat),
        float(lon),
        float(heights[i]),
    )


print(
    "Height at original point: %.1f m"
    % float(terrain.height_at(cx, cy))
)

print(
    "Lowest point within 8 km (floor candidate): "
    "lat %.5f, lon %.5f, height %.1f m"
    % pick(r < 8000, True)
)

print(
    "Highest point 9-12 km away (rim candidate): "
    "lat %.5f, lon %.5f, height %.1f m"
    % pick(
        (r > 9000) & (r < 12000),
        False,
    )
)

print("\nHeights (m) along 8 directions from the original point:")
print(
    "Azimuth "
    + "".join(
        f"{km:>9}km"
        for km in range(2, 16, 2)
    )
)

for az in range(0, 360, 45):
    row = []

    for km in range(2, 16, 2):
        lat, lon = destination(
            *SHACKLETON,
            az,
            km * 1000,
        )

        x, y = lonlat_to_xy(lat, lon)

        row.append(
            float(terrain.height_at(x, y))
        )

    print(
        f"{az:>7} "
        + "".join(f"{h:>10.0f}" for h in row)
    )