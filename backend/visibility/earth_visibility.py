
import numpy as np

from .disc_visibility import HorizonModel, disc_sky_points


def visibility_from_samples(
    samples,
    horizon,
    n_points=400,
):
    """
    Calculate the terrain-visible fraction of Earth's apparent disc
    for each Earth-track sample.

    Incomplete terrain coverage is explicitly flagged. The returned
    visible fraction is provisional when coverage is incomplete.
    """

    if not isinstance(horizon, HorizonModel):
        raise TypeError("horizon must be a HorizonModel.")

    if not isinstance(n_points, (int, np.integer)) or isinstance(
        n_points, (bool, np.bool_)
    ):
        raise ValueError("n_points must be a positive integer.")

    if n_points <= 0:
        raise ValueError("n_points must be positive.")

    if not samples:
        return []

    required_fields = (
        "azimuth_deg",
        "elevation_deg",
        "angular_radius_deg",
    )

    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise TypeError(f"Sample {index} must be a dictionary.")

        missing = [
            field for field in required_fields
            if field not in sample
        ]

        if missing:
            raise ValueError(
                f"Sample {index} is missing fields: {missing}"
            )

    az = np.asarray(
        [sample["azimuth_deg"] for sample in samples],
        dtype=float,
    )

    el = np.asarray(
        [sample["elevation_deg"] for sample in samples],
        dtype=float,
    )

    radius = np.asarray(
        [sample["angular_radius_deg"] for sample in samples],
        dtype=float,
    )

    if not (
        np.all(np.isfinite(az))
        and np.all(np.isfinite(el))
        and np.all(np.isfinite(radius))
    ):
        raise ValueError("Earth-track geometry must be finite.")

    if np.any((el < -90.0) | (el > 90.0)):
        raise ValueError("Earth elevation must be between -90 and 90 degrees.")

    if np.any((radius < 0.0) | (radius > 180.0)):
        raise ValueError("Angular radius must be between 0 and 180 degrees.")

    point_az, point_el = disc_sky_points(
        az,
        el,
        radius,
        n_points=n_points,
    )

    point_horizon = horizon.horizon_at(point_az)

    point_coverage = horizon.complete_at(point_az)

    point_visible = point_el > point_horizon

    visible_fraction = np.mean(
        point_visible,
        axis=1,
    )

    coverage_complete = np.all(
        point_coverage,
        axis=1,
    )

    centre_horizon = horizon.horizon_at(az)

    centre_coverage = horizon.complete_at(az)

    results = []

    for index, sample in enumerate(samples):
        fraction = float(visible_fraction[index])

        results.append({
            "utc": sample.get("utc"),
            "azimuth_deg": float(az[index]),
            "elevation_deg": float(el[index]),
            "angular_radius_deg": float(radius[index]),
            "horizon_at_centre_deg": float(centre_horizon[index]),
            "margin_deg": float(el[index] - centre_horizon[index]),
            "centre_visible": bool(
                el[index] > centre_horizon[index]
            ),
            "visible_fraction": fraction,
            "any_part_visible": bool(fraction > 0.0),
            "fully_visible": bool(fraction == 1.0),
            "blocked": bool(fraction == 0.0),
            "coverage_complete": bool(coverage_complete[index]),
            "centre_coverage_complete": bool(centre_coverage[index]),
        })

    return results


def summarize_visibility(results):
    """
    Summarize Earth-disc visibility across a sequence of samples.

    Percentages describe the computed samples, including provisional
    estimates where terrain coverage is incomplete. The incomplete
    sample count must be considered when interpreting these values.
    """

    if not results:
        return {
            "samples": 0,
            "percent_any_part_visible": 0.0,
            "percent_centre_visible": 0.0,
            "percent_fully_visible": 0.0,
            "percent_blocked": 0.0,
            "mean_visible_fraction": 0.0,
            "samples_with_incomplete_terrain": 0,
        }

    total = len(results)

    fractions = np.asarray(
        [result["visible_fraction"] for result in results],
        dtype=float,
    )

    if not np.all(np.isfinite(fractions)):
        raise ValueError("Visibility fractions must be finite.")

    if np.any((fractions < 0.0) | (fractions > 1.0)):
        raise ValueError("Visibility fractions must be between 0 and 1.")

    return {
        "samples": total,
        "percent_any_part_visible": float(
            100.0 * np.mean([
                result["any_part_visible"] for result in results
            ])
        ),
        "percent_centre_visible": float(
            100.0 * np.mean([
                result["centre_visible"] for result in results
            ])
        ),
        "percent_fully_visible": float(
            100.0 * np.mean([
                result["fully_visible"] for result in results
            ])
        ),
        "percent_blocked": float(
            100.0 * np.mean([
                result["blocked"] for result in results
            ])
        ),
        "mean_visible_fraction": float(np.mean(fractions)),
        "samples_with_incomplete_terrain": sum(
            not result["coverage_complete"] for result in results
        ),
    }
