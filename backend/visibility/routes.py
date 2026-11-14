
from fastapi import APIRouter, HTTPException, Query

from backend.physics.kernels import KernelsMissing
from backend.physics.time_system import parse_utc

from .site_visibility import earth_visibility_for_site


router = APIRouter(
    prefix="/api/visibility",
    tags=["Phase 8 - Earth Visibility"],
)


@router.get("/earth-track")
def visibility_earth_track(
    latitude_deg: float = Query(..., ge=-90, le=0),
    longitude_deg: float = Query(..., ge=-180, le=180),
    height_m: float = Query(...),
    start_utc: str = Query(...),
    duration_days: float = Query(..., gt=0),
    step_minutes: float = Query(5.0, gt=0),
    antenna_height_m: float = Query(2.0, ge=0),
    max_range_m: float = Query(40000.0, gt=0, le=100000),
    azimuth_step_deg: float = Query(0.5, ge=0.25, le=10),
    disc_points: int = Query(400, ge=1, le=5000),
):
    """
    Calculate terrain-aware apparent Earth-disc visibility
    over a SPICE Earth track.

    Combines:
        Phase 6: Earth direction and time tracking.
        Phase 7: NASA LOLA terrain horizon.
        Phase 8: Visible fraction of Earth's apparent disc.
    """

    try:
        parse_utc(start_utc)

    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=(
                "start_utc must be a valid ISO timestamp, "
                "for example 2026-11-14T00:00:00Z"
            ),
        )

    try:
        return earth_visibility_for_site(
            lat_deg=latitude_deg,
            lon_deg=longitude_deg,
            height_m=height_m,
            start_utc=start_utc,
            duration_days=duration_days,
            step_minutes=step_minutes,
            antenna_height_m=antenna_height_m,
            max_range_m=max_range_m,
            azimuth_step_deg=azimuth_step_deg,
            n_disc_points=disc_points,
        )

    except KernelsMissing as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        )
