
from fastapi import APIRouter, HTTPException, Query

from backend.physics.kernels import KernelsMissing
from backend.physics.time_system import parse_utc

from .antenna import AntennaConfig
from .direct_to_earth import LinkConstraints
from .site_link import direct_to_earth_for_site


router = APIRouter(
    prefix="/api/communications",
    tags=["Phase 9 - Direct-to-Earth Communications"],
)


@router.get("/direct-to-earth")
def direct_to_earth(
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

    min_visible_fraction: float = Query(0.5, ge=0, le=1),
    min_clearance_deg: float = Query(0.5, ge=-90, le=90),
    require_complete_terrain: bool = Query(True),

    sun_exclusion_deg: float = Query(3.0, ge=0, le=180),
    sun_exclusion_only_if_sun_in_view: bool = Query(True),

    antenna_kind: str = Query("steerable"),
    min_elevation_deg: float = Query(-10.0, ge=-90, le=90),
    max_elevation_deg: float = Query(90.0, ge=-90, le=90),
    min_azimuth_deg: float = Query(0.0),
    max_azimuth_deg: float = Query(360.0),

    boresight_azimuth_deg: float = Query(0.0),
    boresight_elevation_deg: float = Query(0.0, ge=-90, le=90),
    half_beamwidth_deg: float = Query(5.0, gt=0, le=180),
):
    """
    Evaluate direct-to-Earth communication availability
    from a lunar South Pole site.

    Integrates:
        Phase 6: SPICE Earth geometry.
        Phase 7: NASA LOLA terrain horizon.
        Phase 8: Apparent Earth-disc visibility.
        Phase 9: Sun exclusion and antenna pointing.

    Returns:
        - Terrain-aware Earth visibility.
        - Sun geometry.
        - Five communication constraint decisions.
        - Available and unavailable sample counts.
        - Failure attribution.
    """

    # Validate the requested UTC start time.
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

    # Build the antenna configuration.
    try:
        antenna = AntennaConfig(
            kind=antenna_kind,
            min_elevation_deg=min_elevation_deg,
            max_elevation_deg=max_elevation_deg,
            min_azimuth_deg=min_azimuth_deg,
            max_azimuth_deg=max_azimuth_deg,
            boresight_azimuth_deg=boresight_azimuth_deg,
            boresight_elevation_deg=boresight_elevation_deg,
            half_beamwidth_deg=half_beamwidth_deg,
        )

        constraints = LinkConstraints(
            min_visible_fraction=min_visible_fraction,
            min_clearance_deg=min_clearance_deg,
            require_complete_terrain=require_complete_terrain,
            sun_exclusion_deg=sun_exclusion_deg,
            sun_exclusion_only_if_sun_in_view=(
                sun_exclusion_only_if_sun_in_view
            ),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        )

    # Calculate the complete direct-to-Earth link model.
    try:
        return direct_to_earth_for_site(
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
            antenna=antenna,
            constraints=constraints,
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
