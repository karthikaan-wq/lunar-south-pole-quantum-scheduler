
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
from backend.physics.earth_geometry import lander_state

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

    Coordinates:
        Latitude: -90 to +90 degrees
        Longitude: -180 to +180 degrees
        Height: metres above the lunar reference sphere
        UTC: ISO-format timestamp
    """

    # Validate the UTC timestamp.
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

    # Convert UTC into SPICE Ephemeris Time.
    try:
        et = to_et(moment)

        # Calculate the complete lander state.
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


# Serve the frontend after registering all API routes.
frontend_path = Path(__file__).resolve().parent.parent / "frontend"

if frontend_path.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(frontend_path), html=True),
        name="frontend",
    )
