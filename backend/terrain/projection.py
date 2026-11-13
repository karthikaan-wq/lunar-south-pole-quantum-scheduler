
import math

MOON_RADIUS_M = 1_737_400.0


def lonlat_to_xy(lat_deg: float, lon_deg: float) -> tuple[float, float]:
    """
    Convert lunar latitude/longitude into south-polar stereographic
    map coordinates in metres.
    """
    lat = float(lat_deg)
    lon = float(lon_deg)

    if not math.isfinite(lat) or not math.isfinite(lon):
        raise ValueError("Latitude and longitude must be finite numbers.")

    if not -90.0 <= lat <= 0.0:
        raise ValueError("Latitude must be between -90 and 0 degrees.")

    colat_rad = math.radians(90.0 + lat)
    lon_rad = math.radians(lon)

    rho = 2.0 * MOON_RADIUS_M * math.tan(colat_rad / 2.0)

    x = rho * math.sin(lon_rad)
    y = rho * math.cos(lon_rad)

    return float(x), float(y)


def xy_to_lonlat(x: float, y: float) -> tuple[float, float]:
    """
    Convert south-polar stereographic map coordinates into
    lunar latitude/longitude.
    """
    x = float(x)
    y = float(y)

    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("Map coordinates must be finite numbers.")

    rho = math.hypot(x, y)

    if rho == 0.0:
        return -90.0, 0.0

    colat_rad = 2.0 * math.atan(rho / (2.0 * MOON_RADIUS_M))
    lat_deg = math.degrees(colat_rad) - 90.0

    lon_deg = math.degrees(math.atan2(x, y))
    lon_deg = (lon_deg + 180.0) % 360.0 - 180.0

    return float(lat_deg), float(lon_deg)
