from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.catalog import get_catalog
from backend.schemas import MissionRequest
from backend.validation import validate_mission
from backend.mock_engine import generate_mock_environment

from backend.physics.ephemeris import earth_moon_state
from backend.physics.kernels import KernelsMissing
from backend.physics.time_system import parse_utc, to_et
from backend.physics.earth_geometry import (
    lander_state,
    earth_direction,
    earth_track,
)

from backend.terrain.dem_loader import load_dem_terrain
from backend.terrain.horizon import horizon_profile


from backend.store import (
    new_id,
    save_mission,
    get_mission,
    save_result,
    get_result,
)


app = FastAPI(
    title="Lunar South Pole Quantum Scheduler API",
    description="Backend API for lunar mission scheduling.",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "message": "Lunar Scheduler backend is running",
        "source": "mock",
    }


@app.get("/api/catalog")
def catalog():
    return get_catalog()


@app.post("/api/mission/validate")
def validate(request: MissionRequest):
    result = validate_mission(request)

    if not result["valid"]:
        raise HTTPException(
            status_code=422,
            detail=result["errors"],
        )

    return result


@app.post("/api/mission/create")
def create_mission(request: MissionRequest):
    validation = validate_mission(request)

    if not validation["valid"]:
        raise HTTPException(
            status_code=422,
            detail=validation["errors"],
        )

    mission_id = new_id()

    mission_data = request.model_dump()
    mission_data["mission_id"] = mission_id

    save_mission(mission_id, mission_data)

    return {
        "mission_id": mission_id,
        "status": "created",
        "source": "mock",
    }


@app.get("/api/environment")
def environment():
    return {
        "sun_windows": [],
        "source": "mock",
        "message": "Submit a mission to generate environment data.",
    }


@app.get("/api/earth-visibility")
def earth_visibility():
    return {
        "earth_series": [],
        "comm_windows": [],
        "source": "mock",
        "message": "Submit a mission to generate visibility data.",
    }


@app.post("/api/generate")
def generate(request: MissionRequest):
    validation = validate_mission(request)

    if not validation["valid"]:
        raise HTTPException(
            status_code=422,
            detail=validation["errors"],
        )

    mission_id = new_id()
    result_id = new_id()

    mission_data = request.model_dump()
    mission_data["mission_id"] = mission_id

    environment_data = generate_mock_environment(request.config)

    result_data = {
        "result_id": result_id,
        "mission_id": mission_id,
        "config": request.config.model_dump(),
        "assets": [
            asset.model_dump()
            for asset in request.assets
        ],
        **environment_data,
    }

    save_mission(mission_id, mission_data)
    save_result(result_id, result_data)

    return result_data


@app.get("/api/results/{result_id}")
def retrieve_result(result_id: str):
    result = get_result(result_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Result not found",
        )

    return result


@app.get("/api/physics/earth-moon")
def physics_earth_moon(utc: str):
    """
    Return real SPICE Earth-Moon astronomical data
    for the requested UTC timestamp.
    """

    try:
        moment = parse_utc(utc)

    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=(
                "utc must be a valid ISO timestamp, "
                "for example 2026-11-10T00:00:00Z"
            ),
        )

    try:
        return earth_moon_state(moment)

    except KernelsMissing as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        )


@app.get("/api/physics/lander-position")
def physics_lander_position(
    latitude_deg: float = Query(..., ge=-90, le=90),
    longitude_deg: float = Query(..., ge=-180, le=180),
    height_m: float = Query(...),
    utc: str = Query(...),
):
    """
    Return the real SPICE position and Earth direction
    for a lunar lander at a specified location and time.
    """

    try:
        moment = parse_utc(utc)

    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=(
                "utc must be a valid ISO timestamp, "
                "for example 2026-11-13T00:00:00Z"
            ),
        )

    try:
        et = to_et(moment)

        result = lander_state(
            lat_deg=latitude_deg,
            lon_deg=longitude_deg,
            height_m=height_m,
            et=et,
        )

        result["source"] = "SPICE"
        result["reference_frame"] = "J2000 and MOON_ME_DE440_ME421"

        return result

    except KernelsMissing as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        )


# ============================================================
# PHASE 6: EARTH DIRECTION
# ============================================================

@app.get("/api/physics/earth-direction")
def physics_earth_direction(
    latitude_deg: float = Query(..., ge=-90, le=90),
    longitude_deg: float = Query(..., ge=-180, le=180),
    height_m: float = Query(...),
    utc: str = Query(...),
):
    """
    Calculate Earth's apparent direction from a lunar lander.

    Returns:
        - Azimuth
        - Centre elevation
        - Distance to Earth's centre
        - Angular radius
        - Upper and lower limb elevations

    Elevation is relative to a flat local horizon.
    Terrain obstruction is not included.
    """

    try:
        parse_utc(utc)

    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=(
                "utc must be a valid ISO timestamp, "
                "for example 2026-11-13T00:00:00Z"
            ),
        )

    try:
        result = earth_direction(
            lat_deg=latitude_deg,
            lon_deg=longitude_deg,
            height_m=height_m,
            utc=utc,
        )

        result["source"] = "SPICE"

        return result

    except KernelsMissing as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        )


# ============================================================
# PHASE 6: EARTH ELEVATION TRACK
# ============================================================

@app.get("/api/physics/earth-track")
def physics_earth_track(
    latitude_deg: float = Query(..., ge=-90, le=90),
    longitude_deg: float = Query(..., ge=-180, le=180),
    height_m: float = Query(...),
    start_utc: str = Query(...),
    duration_days: float = Query(..., gt=0),
    step_minutes: float = Query(5.0, gt=0),
):
    """
    Calculate Earth's apparent direction over a time interval.

    Returns:
        - Time-series samples
        - Azimuth and elevation at each sample
        - Earth distance and angular radius
        - Upper and lower limb elevations
        - Track summary

    The maximum number of samples is 20,000.
    Elevation is relative to a flat local horizon.
    Terrain obstruction is not included.
    """

    try:
        parse_utc(start_utc)

    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=(
                "start_utc must be a valid ISO timestamp, "
                "for example 2026-11-13T00:00:00Z"
            ),
        )

    try:
        result = earth_track(
            lat_deg=latitude_deg,
            lon_deg=longitude_deg,
            height_m=height_m,
            start_utc=start_utc,
            duration_days=duration_days,
            step_minutes=step_minutes,
        )

        result["source"] = "SPICE"

        return result

    except KernelsMissing as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        )


# ============================================================
# PHASE 7: REAL TERRAIN HORIZON
# ============================================================

@app.get("/api/terrain/horizon")
def terrain_horizon(
    latitude_deg: float = Query(..., ge=-90, le=0),
    longitude_deg: float = Query(..., ge=-180, le=180),
    antenna_height_m: float = Query(2.0, ge=0),
    max_range_m: float = Query(40000.0, gt=0, le=100000),
    azimuth_step_deg: float = Query(1.0, ge=0.25, le=10),
):
    """
    Calculate a real terrain-based lunar horizon profile.

    Uses the NASA LOLA 80 m elevation dataset.
    """

    try:
        # Load a terrain window with a safety margin.
        terrain = load_dem_terrain(
            lat_deg=latitude_deg,
            lon_deg=longitude_deg,
            half_size_m=max_range_m * 1.1 + 1000.0,
        )

        # Calculate the horizon using the DEM's native resolution.
        profile = horizon_profile(
            terrain=terrain,
            lat_deg=latitude_deg,
            lon_deg=longitude_deg,
            antenna_height_m=antenna_height_m,
            azimuth_step_deg=azimuth_step_deg,
            max_range_m=max_range_m,
            step_m=terrain.pixel_m,
        )

        complete_count = int(
            profile["horizon_is_complete"].sum()
        )

        total_count = int(
            len(profile["azimuth_deg"])
        )

        return {
            "source": "NASA LOLA DEM",
            "dataset_resolution_m": float(terrain.pixel_m),
            "site": {
                "latitude_deg": latitude_deg,
                "longitude_deg": longitude_deg,
                "elevation_m": profile["site_height_m"],
                "antenna_height_m": profile["antenna_height_m"],
            },
            "settings": {
                "max_range_m": profile["max_range_m"],
                "azimuth_step_deg": profile["azimuth_step_deg"],
                "sample_step_m": profile["sample_step_m"],
            },
            "coverage_summary": {
                "complete_directions": complete_count,
                "total_directions": total_count,
                "all_directions_complete": (
                    complete_count == total_count
                ),
            },
            "horizon": {
                "azimuth_deg": profile["azimuth_deg"].tolist(),
                "elevation_deg": (
                    profile["horizon_elevation_deg"].tolist()
                ),
                "blocking_distance_m": (
                    profile["blocking_distance_m"].tolist()
                ),
                "ray_reaches_end": (
                    profile["ray_reaches_end"].tolist()
                ),
                "ray_coverage_complete": (
                    profile["ray_coverage_complete"].tolist()
                ),
                "horizon_is_complete": (
                    profile["horizon_is_complete"].tolist()
                ),
            },
        }

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



# Serve the frontend after registering all API routes.
frontend_path = Path(__file__).resolve().parent.parent / "frontend"

if frontend_path.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(frontend_path), html=True),
        name="frontend",
    )
