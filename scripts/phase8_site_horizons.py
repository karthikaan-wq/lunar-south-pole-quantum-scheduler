import numpy as np

from backend.terrain.dem_loader import load_dem_terrain
from backend.terrain.horizon import horizon_profile


SITES = {
    "Shackleton Floor Candidate": (-89.73391, 122.03549),
    "Shackleton Rim Candidate": (-89.67869, -163.05292),
    "Malapert Massif": (-85.99000, 0.12000),
}

ANTENNA_HEIGHT_M = 2.0
MAX_RANGE_M = 40000.0
AZIMUTH_STEP_DEG = 0.5


def main():
    print("=" * 65)
    print("PHASE 8 - THREE-SITE TERRAIN HORIZON VALIDATION")
    print("=" * 65)

    for site_name, (lat, lon) in SITES.items():
        print(f"\nSITE: {site_name}")
        print(f"Coordinates: {lat:.5f}, {lon:.5f}")

        terrain = load_dem_terrain(
            lat,
            lon,
            half_size_m=45000,
        )

        profile = horizon_profile(
            terrain,
            lat_deg=lat,
            lon_deg=lon,
            antenna_height_m=ANTENNA_HEIGHT_M,
            azimuth_step_deg=AZIMUTH_STEP_DEG,
            max_range_m=MAX_RANGE_M,
            step_m=terrain.pixel_m,
        )

        horizon = np.asarray(
            profile["horizon_elevation_deg"],
            dtype=float,
        )

        complete = np.asarray(
            profile["ray_coverage_complete"],
            dtype=bool,
        )

        reaches_end = np.asarray(
            profile["ray_reaches_end"],
            dtype=bool,
        )

        valid = np.isfinite(horizon)

        print(f"DEM dimensions: {terrain.heights.shape}")
        print(f"DEM pixel size: {terrain.pixel_m:.1f} m")
        print(f"Site elevation: {profile['site_height_m']:.2f} m")
        print(f"Azimuth samples: {len(horizon)}")
        print(f"Valid horizon samples: {np.count_nonzero(valid)}")
        print(f"Complete rays: {np.count_nonzero(complete)}")
        print(f"Rays reaching 40 km: {np.count_nonzero(reaches_end)}")

        if np.any(valid):
            print(f"Minimum horizon: {np.nanmin(horizon):.4f}°")
            print(f"Maximum horizon: {np.nanmax(horizon):.4f}°")
            print(f"Mean horizon: {np.nanmean(horizon):.4f}°")
        else:
            print("WARNING: No valid horizon samples.")

        print(
            "Overall horizon coverage: "
            + ("COMPLETE" if np.all(complete) else "INCOMPLETE")
        )

    print("\n" + "=" * 65)
    print("THREE-SITE VALIDATION FINISHED")
    print("=" * 65)


if __name__ == "__main__":
    main()