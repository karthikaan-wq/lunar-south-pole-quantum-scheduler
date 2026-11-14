import math

from fastapi import APIRouter, HTTPException, Query

from backend.physics.kernels import KernelsMissing
from backend.physics.time_system import parse_utc

from .battery import BatteryConfig
from .site_energy import energy_timeline_for_site
from .solar_power import PanelConfig


router = APIRouter(
    prefix="/api/energy",
    tags=["Phase 11 - Solar Energy and Battery Survival"],
)


@router.get("/site-timeline")
def site_energy_timeline(
    latitude_deg: float = Query(..., ge=-90, le=0),
    longitude_deg: float = Query(..., ge=-180, le=180),
    start_utc: str = Query(...),

    duration_days: float = Query(14.0, gt=0, le=28),
    step_minutes: float = Query(30.0, gt=0, le=1440),

    panel_kind: str = Query("tracking"),
    panel_normal_elevation_deg: float = Query(0.0, ge=-90, le=90),
    panel_normal_azimuth_deg: float = Query(0.0),
    panel_area_m2: float = Query(3.0, gt=0),
    panel_efficiency: float = Query(0.28, ge=0, le=1),
    panel_dust_loss: float = Query(0.05, ge=0, le=1),
    panel_degradation: float = Query(0.0, ge=0, le=1),
    panel_height_m: float = Query(3.0, ge=0),

    battery_capacity_wh: float = Query(2000.0, gt=0),
    battery_initial_soc: float = Query(0.8, ge=0, le=1),
    battery_min_soc: float = Query(0.2, ge=0, le=1),
    battery_charge_efficiency: float = Query(0.95, gt=0, le=1),
    battery_discharge_efficiency: float = Query(0.95, gt=0, le=1),

    base_load_w: float = Query(60.0, ge=0),

    max_range_m: float = Query(100000.0, gt=0, le=100000),
    azimuth_step_deg: float = Query(0.25, ge=0.25, le=10),
    sunlit_threshold: float = Query(0.5, ge=0, le=1),
    disc_points: int = Query(400, ge=20, le=5000),
    include_samples: bool = Query(True),
):
    """
    Simulate terrain-aware solar generation and battery survival.

    Integrates:
        Phase 6: SPICE Sun and Earth geometry.
        Phase 7: NASA LOLA terrain horizon.
        Phase 11: Solar-disc visibility, panel generation,
                  eclipse attenuation and battery simulation.

    The terrain visibility fraction and eclipse factor are
    multiplied as an approximation, not an exact joint
    geometric intersection.

    Tracking panels follow solar azimuth but retain their
    configured normal elevation. Full two-axis tracking,
    actuator limits and slew constraints are not modelled.

    Battery minimum SOC is a warning threshold; automatic
    load shedding is not enforced.
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

    if not math.isfinite(duration_days):
        raise HTTPException(
            status_code=422,
            detail="duration_days must be finite.",
        )

    if not math.isfinite(step_minutes):
        raise HTTPException(
            status_code=422,
            detail="step_minutes must be finite.",
        )

    sample_count = (
        math.ceil(duration_days * 86400.0 / (step_minutes * 60.0))
        + 1
    )

    if sample_count > 20000:
        raise HTTPException(
            status_code=422,
            detail=(
                "The requested timeline exceeds 20,000 samples. "
                "Increase step_minutes or reduce duration_days."
            ),
        )

    try:
        panel = PanelConfig(
            kind=panel_kind,
            normal_elevation_deg=panel_normal_elevation_deg,
            normal_azimuth_deg=panel_normal_azimuth_deg,
            area_m2=panel_area_m2,
            efficiency=panel_efficiency,
            dust_loss=panel_dust_loss,
            degradation=panel_degradation,
            panel_height_m=panel_height_m,
        )

        battery = BatteryConfig(
            capacity_wh=battery_capacity_wh,
            initial_soc=battery_initial_soc,
            min_soc=battery_min_soc,
            charge_efficiency=battery_charge_efficiency,
            discharge_efficiency=battery_discharge_efficiency,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        )

    try:
        return energy_timeline_for_site(
            lat_deg=latitude_deg,
            lon_deg=longitude_deg,
            start_utc=start_utc,
            duration_days=duration_days,
            step_minutes=step_minutes,
            panel_config=panel,
            battery_config=battery,
            base_load_w=base_load_w,
            max_range_m=max_range_m,
            azimuth_step_deg=azimuth_step_deg,
            sunlit_threshold=sunlit_threshold,
            n_disc_points=disc_points,
            include_samples=include_samples,
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
