
from datetime import datetime, timedelta
import math


def generate_mock_environment(config):
    start = datetime.strptime(
        f"{config.start_date} {config.start_time}",
        "%Y-%m-%d %H:%M"
    )

    earth_series = []
    comm_windows = []
    sun_windows = []

    total_hours = config.duration_days * 24

    for hour in range(total_hours):
        current_time = start + timedelta(hours=hour)

        # DEMONSTRATION VALUES ONLY — NOT REAL LUNAR GEOMETRY
        earth_elevation = (
            25 + 20 * math.sin(hour * 2 * math.pi / 24)
        )

        sun_elevation = (
            10 + 15 * math.sin(hour * 2 * math.pi / 24)
        )

        earth_visible = earth_elevation >= config.min_elevation_deg

        earth_series.append({
            "time": current_time.isoformat(),
            "elevation_deg": round(earth_elevation, 2),
            "visible": earth_visible
        })

        if earth_visible:
            comm_windows.append({
                "start": current_time.isoformat(),
                "duration_hours": 1
            })

        if sun_elevation > 0:
            sun_windows.append({
                "start": current_time.isoformat(),
                "duration_hours": 1
            })

    return {
        "earth_series": earth_series,
        "comm_windows": comm_windows,
        "sun_windows": sun_windows,
        "source": "mock",
        "warning": (
            "Demonstration data only. "
            "Not calculated from real lunar positions or terrain."
        )
    }
