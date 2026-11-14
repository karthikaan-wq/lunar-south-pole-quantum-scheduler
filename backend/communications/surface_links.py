import math
from dataclasses import dataclass

import numpy as np

from ..terrain.projection import MOON_RADIUS_M, lonlat_to_xy

SPEED_OF_LIGHT_M_S = 299_792_458.0


@dataclass(frozen=True)
class SurfaceLinkSettings:
    frequency_hz: float = 401.5e6
    max_range_m: float = 10_000.0
    min_clearance_m: float = 0.0
    min_fresnel_ratio: float = 0.0
    step_m: float = 40.0

    def __post_init__(self):
        values = (
            self.frequency_hz,
            self.max_range_m,
            self.min_clearance_m,
            self.min_fresnel_ratio,
            self.step_m,
        )

        if not all(math.isfinite(v) for v in values):
            raise ValueError("All surface-link settings must be finite.")

        if self.frequency_hz <= 0 or self.max_range_m <= 0 or self.step_m <= 0:
            raise ValueError(
                "frequency_hz, max_range_m and step_m must be positive."
            )

        if self.min_clearance_m < 0:
            raise ValueError("min_clearance_m must not be negative.")

        if not 0 <= self.min_fresnel_ratio <= 2:
            raise ValueError("min_fresnel_ratio must be between 0 and 2.")


def _validate_site(site):
    if len(site) != 2:
        raise ValueError("A site must contain latitude and longitude.")

    lat, lon = float(site[0]), float(site[1])

    if not math.isfinite(lat) or not -90.0 <= lat <= 0.0:
        raise ValueError("Latitude must be finite and between -90 and 0.")

    if not math.isfinite(lon):
        raise ValueError("Longitude must be finite.")

    return lat, lon


def _validate_antenna_height(height_m):
    height_m = float(height_m)

    if not math.isfinite(height_m) or height_m < 0:
        raise ValueError("Antenna height must be finite and non-negative.")

    return height_m


def _unit(lat_deg, lon_deg):
    la = math.radians(lat_deg)
    lo = math.radians(lon_deg)

    return np.array([
        math.cos(la) * math.cos(lo),
        math.cos(la) * math.sin(lo),
        math.sin(la),
    ])


def great_circle_points(lat1, lon1, lat2, lon2, count):
    """
    Return angular positions, latitudes, longitudes and total angle
    along the shortest great-circle path between two lunar sites.
    """
    lat1, lon1 = _validate_site((lat1, lon1))
    lat2, lon2 = _validate_site((lat2, lon2))

    if count < 2:
        raise ValueError("At least two great-circle points are required.")

    u1 = _unit(lat1, lon1)
    u2 = _unit(lat2, lon2)

    dot = float(np.clip(u1 @ u2, -1.0, 1.0))
    delta = math.acos(dot)

    if delta < 1e-12:
        return (
            np.zeros(count),
            np.full(count, lat1),
            np.full(count, lon1),
            0.0,
        )

    phi = np.linspace(0.0, delta, count)

    if abs(math.sin(delta)) < 1e-10:
        raise ValueError(
            "Great-circle path is numerically ambiguous for near-antipodal sites."
        )

    points = (
        np.sin(delta - phi)[:, None] * u1
        + np.sin(phi)[:, None] * u2
    ) / math.sin(delta)

    points /= np.linalg.norm(points, axis=1)[:, None]

    latitudes = np.degrees(
        np.arcsin(np.clip(points[:, 2], -1.0, 1.0))
    )

    longitudes = np.degrees(
        np.arctan2(points[:, 1], points[:, 0])
    )

    return phi, latitudes, longitudes, delta


def _terrain_heights_at(terrain, latitudes, longitudes):
    """
    Sample Terrain.height_at() point by point.

    The current Terrain API accepts scalar coordinates only.
    """
    heights = np.empty(len(latitudes), dtype=np.float64)

    for index, (lat, lon) in enumerate(zip(latitudes, longitudes)):
        x, y = lonlat_to_xy(float(lat), float(lon))
        heights[index] = terrain.height_at(x, y)

    return heights


def surface_link(
    terrain,
    site_a,
    site_b,
    antenna_a_m=2.0,
    antenna_b_m=2.0,
    settings=None,
):
    """
    Evaluate a static rover-to-lander surface radio link.

    Terrain clearance is calculated along the great-circle path.
    Radio propagation follows the straight chord between antennas.

    Missing terrain samples make the link unusable.
    """
    s = settings or SurfaceLinkSettings()

    if not isinstance(s, SurfaceLinkSettings):
        raise TypeError("settings must be SurfaceLinkSettings.")

    site_a = _validate_site(site_a)
    site_b = _validate_site(site_b)

    antenna_a_m = _validate_antenna_height(antenna_a_m)
    antenna_b_m = _validate_antenna_height(antenna_b_m)

    ground_a = float(
        terrain.height_at(*lonlat_to_xy(*site_a))
    )
    ground_b = float(
        terrain.height_at(*lonlat_to_xy(*site_b))
    )

    if not math.isfinite(ground_a) or not math.isfinite(ground_b):
        return {
            "usable": False,
            "line_of_sight": False,
            "range_ok": False,
            "fresnel_ok": False,
            "data_complete": False,
            "reason": "A site is outside the terrain model or has missing elevation data.",
        }

    radius = MOON_RADIUS_M
    r_a = radius + ground_a + antenna_a_m
    r_b = radius + ground_b + antenna_b_m

    if r_a <= 0 or r_b <= 0:
        raise ValueError("Antenna position must be above the lunar centre.")

    u1 = _unit(*site_a)
    u2 = _unit(*site_b)
    delta = math.acos(float(np.clip(u1 @ u2, -1.0, 1.0)))

    arc_m = delta * radius

    count = max(
        3,
        int(math.ceil(arc_m / s.step_m)) + 1,
    )

    phi, latitudes, longitudes, delta = great_circle_points(
        *site_a,
        *site_b,
        count,
    )

    slant_m = math.sqrt(max(
        0.0,
        r_a ** 2 + r_b ** 2 - 2.0 * r_a * r_b * math.cos(delta),
    ))

    heights = _terrain_heights_at(
        terrain,
        latitudes,
        longitudes,
    )

    data_complete = bool(np.all(np.isfinite(heights)))

    if delta < 1e-9:
        clearance = np.array([min(antenna_a_m, antenna_b_m)])
        index = 0
        fresnel_min = math.inf
    else:
        denominator = (
            np.sin(delta - phi) / r_a
            + np.sin(phi) / r_b
        )

        line_radius = np.sin(delta) / denominator

        clearance = line_radius - (radius + heights)

        d1 = phi * radius
        d2 = (delta - phi) * radius

        wavelength = SPEED_OF_LIGHT_M_S / s.frequency_hz

        first_zone = np.zeros_like(phi)
        inner = slice(1, -1)

        first_zone[inner] = np.sqrt(
            wavelength * d1[inner] * d2[inner]
            / (d1[inner] + d2[inner])
        )

        valid_inner = (
            np.isfinite(clearance[inner])
            & np.isfinite(first_zone[inner])
            & (first_zone[inner] > 0)
        )

        ratios = (
            clearance[inner][valid_inner]
            / first_zone[inner][valid_inner]
        )

        fresnel_min = (
            float(np.min(ratios))
            if len(ratios)
            else math.inf
        )

        finite_clearance = np.where(
            np.isfinite(clearance),
            clearance,
            np.inf,
        )

        index = int(np.argmin(finite_clearance))

    finite_clearance = clearance[np.isfinite(clearance)]

    if len(finite_clearance) == 0:
        min_clearance = float("nan")
        min_clearance_at_m = float("nan")
    else:
        index = int(np.nanargmin(clearance))
        min_clearance = float(clearance[index])
        min_clearance_at_m = float(phi[index] * radius)

    if delta < 1e-9:
        elevation_from_a = 90.0 if r_b > r_a else (
            -90.0 if r_b < r_a else 0.0
        )
        elevation_from_b = -elevation_from_a
    else:
        elevation_from_a = math.degrees(math.atan2(
            r_b * math.cos(delta) - r_a,
            r_b * math.sin(delta),
        ))

        elevation_from_b = math.degrees(math.atan2(
            r_a * math.cos(delta) - r_b,
            r_a * math.sin(delta),
        ))

    los = bool(
        data_complete
        and math.isfinite(min_clearance)
        and min_clearance > s.min_clearance_m
    )

    range_ok = slant_m <= s.max_range_m
    fresnel_ok = fresnel_min >= s.min_fresnel_ratio

    return {
        "distance_m": float(arc_m),
        "slant_range_m": float(slant_m),
        "line_of_sight": bool(los),
        "range_ok": bool(range_ok),
        "fresnel_ok": bool(fresnel_ok),
        "min_clearance_m": min_clearance,
        "min_clearance_at_m": min_clearance_at_m,
        "fresnel_ratio_min": float(fresnel_min),
        "elevation_of_b_from_a_deg": float(elevation_from_a),
        "elevation_of_a_from_b_deg": float(elevation_from_b),
        "data_complete": data_complete,
        "usable": bool(los and range_ok and fresnel_ok and data_complete),
    }


def link_matrix(terrain, sites, antenna_heights_m, settings=None):
    """
    Evaluate each unique unordered site pair exactly once.
    """
    names = list(sites)

    if len(names) != len(set(names)):
        raise ValueError("Site names must be unique.")

    if set(names) != set(antenna_heights_m):
        raise ValueError(
            "Every site must have exactly one antenna height."
        )

    out = {}

    for index, a in enumerate(names):
        for b in names[index + 1:]:
            out[(a, b)] = surface_link(
                terrain,
                sites[a],
                sites[b],
                antenna_heights_m[a],
                antenna_heights_m[b],
                settings,
            )

    return out


def intersect_windows(windows_a, windows_b):
    """
    Return time intervals during which both assets are available.
    """
    out = []

    for start_a, end_a in windows_a:
        for start_b, end_b in windows_b:
            start = max(start_a, start_b)
            end = min(end_a, end_b)

            if end > start:
                out.append((start, end))

    return sorted(out)


def forwarding_options(
    uplink_windows,
    earth_windows,
    max_wait_s=12 * 3600.0,
    min_forward_s=300.0,
):
    """
    Find Earth windows that can forward data after each uplink ends.

    Data is assumed to reach the lander at the end of its uplink
    window. An Earth window may already be open at that time.
    """
    if (
        not math.isfinite(max_wait_s)
        or not math.isfinite(min_forward_s)
        or max_wait_s < 0
        or min_forward_s < 0
    ):
        raise ValueError(
            "Forwarding wait and duration limits must be finite and non-negative."
        )

    options = []

    for uplink_start, uplink_end in uplink_windows:
        if uplink_end <= uplink_start:
            raise ValueError("Uplink windows must have positive duration.")

        found = []

        for earth_start, earth_end in earth_windows:
            if earth_end <= earth_start:
                continue

            wait = max(0.0, earth_start - uplink_end)

            usable = earth_end - max(earth_start, uplink_end)

            if usable >= min_forward_s and wait <= max_wait_s:
                found.append({
                    "earth_start_s": earth_start,
                    "earth_end_s": earth_end,
                    "wait_s": wait,
                    "forward_s": usable,
                })

        options.append({
            "uplink_start_s": uplink_start,
            "uplink_end_s": uplink_end,
            "options": sorted(
                found,
                key=lambda option: option["wait_s"],
            ),
        })

    return options
