
# Phase 8 — Terrain-Aware Earth Visibility Modelling

**Project:** Lunar South Pole Quantum Scheduler
**Phase:** 8
**Status:** Implementation, integration, scientific analysis, testing, documentation, and GitHub publication completed

## 1. Objective

Phase 8 extends the Phase 6 Earth-position calculations and Phase 7 lunar terrain modelling to determine how much of Earth's apparent disc is visible from a lunar surface location.

Earlier phases calculated Earth's direction and the terrain horizon independently. Phase 8 combines these outputs to estimate whether Earth's apparent disc is:

- Fully visible above the local terrain horizon.
- Partially visible, with some of the disc obstructed.
- Completely blocked by lunar terrain.

The principal output is `visible_fraction`, a value between 0 and 1:

- `0.0` means none of the sampled Earth disc is visible.
- `0.5` means approximately half is visible.
- `1.0` means the entire sampled disc is visible.

This is a geometric visibility model. It does not establish that a reliable radio communication link exists.

## 2. Architecture and implementation

### 2.1 `backend/visibility/disc_visibility.py`

This module implements the geometry used to represent Earth's apparent disc.

Main components:

- `HorizonModel`: stores terrain horizon elevations and coverage information by azimuth.
- `disc_pattern`: generates an area-distributed sampling pattern across a circular disc using a golden-angle spiral.
- `disc_sky_points`: converts Earth's centre azimuth, elevation, and angular radius into individual sky positions across the apparent disc.

The radial distribution uses:

\[
r_i=\sqrt{\frac{i+0.5}{N}}
\]

where \(N\) is the number of disc samples.

The square root distributes samples across the disc area rather than concentrating them near its centre.

The horizon model sorts azimuth samples and supports interpolation across the 360° boundary. It also handles the shorter final azimuth interval produced when the requested angular step does not divide 360 evenly.

Incomplete horizon coverage is explicitly tracked rather than silently treated as confirmed clear terrain.

### 2.2 `backend/visibility/earth_visibility.py`

This module evaluates the sampled Earth disc against the terrain horizon.

Main functions:

- `visibility_from_samples(samples, horizon, n_points=400)`
- `summarize_visibility(results)`

For each Earth-track time sample, the implementation:

1. Reads Earth's centre azimuth and elevation.
2. Reads Earth's apparent angular radius.
3. Generates points across the apparent disc.
4. Determines the terrain horizon at each point's azimuth.
5. Compares each point's elevation with the corresponding terrain horizon.
6. Calculates the visible fraction.
7. Records whether the centre, any part, or the entire disc is visible.
8. Records terrain coverage completeness.

The output preserves the UTC timestamp and relevant visibility measurements.

When terrain coverage is incomplete, missing horizon values are provisionally treated as clear for the numerical visibility estimate, but the result is explicitly marked incomplete. Such estimates must not be interpreted as confirmed visibility.

### 2.3 `backend/visibility/site_visibility.py`

This module integrates the earlier project phases.

Its `earth_visibility_for_site(...)` workflow:

1. Calls the Phase 6 Earth-track calculation.
2. Loads the NASA LOLA terrain DEM.
3. Calculates the Phase 7 horizon profile for the selected lunar location.
4. Creates a `HorizonModel`.
5. Evaluates the Earth disc at every time sample.
6. Summarizes the visibility results.
7. Returns the site, terrain, simulation settings, Earth-track summary, visibility summary, and individual samples.

#### Observer-height consistency correction

The observer height used for Earth geometry accounts for both the DEM-derived terrain elevation and the antenna height above the lunar surface.

For every study location:

- `height_m` represents the interpolated DEM terrain elevation.
- `antenna_height_m` represents the antenna height above the terrain surface.
- The Earth-track calculation uses `height_m + antenna_height_m` as the observer elevation.
- The terrain horizon calculation also accounts for the same antenna height above the DEM surface.

This ensures that the Earth geometry and terrain horizon calculations use a consistent observer position.

The DEM terrain elevation remains separately recorded as the site's ground elevation. The antenna height is not added twice.

### 2.4 `backend/visibility/routes.py` and `backend/main.py`

The new API endpoint is:

`GET /api/visibility/earth-track`

It accepts parameters for:

- `latitude_deg`
- `longitude_deg`
- `height_m`
- `start_utc`
- `duration_days`
- `step_minutes`
- `antenna_height_m`
- `max_range_m`
- `azimuth_step_deg`
- `disc_points`

Input validation is performed before the visibility calculation. Invalid coordinates and timestamps are rejected.

The new router is registered in `backend/main.py`. Existing endpoints, including the earlier Earth-visibility mock endpoint, are preserved.

## 3. Study locations and terrain validation

Three study locations were selected to compare different lunar terrain environments.

The Shackleton locations are provisional candidates identified through DEM elevation analysis. They should not be described as geologically confirmed floor or rim locations.

| Study location | Latitude | Longitude | DEM elevation |
|---|---:|---:|---:|
| Shackleton Floor Candidate | -89.73391° | 122.03549° | -2843.63 m |
| Shackleton Rim Candidate | -89.67869° | -163.05292° | +1703.42 m |
| Malapert Massif | -85.99000° | 0.12000° | +4842.28 m |

### 3.1 Horizon validation

Each location was evaluated using:

- Antenna height: 2 m
- Maximum horizon range: 40 km
- Azimuth step: 0.5°
- Number of azimuth directions: 720
- Terrain sampling step: native DEM pixel spacing of 80 m

| Measurement | Floor candidate | Rim candidate | Malapert |
|---|---:|---:|---:|
| Minimum horizon | 16.6742° | -4.5879° | -4.4504° |
| Maximum horizon | 29.0437° | +7.0451° | +4.7403° |
| Mean horizon | 22.6681° | +0.0297° | -0.2285° |
| Complete directions | 720/720 | 720/720 | 720/720 |

All three profiles had complete sampled terrain coverage over the requested range.

The floor candidate has a much higher surrounding terrain horizon than the rim candidate and Malapert. This is consistent with its position in a deep depression surrounded by elevated terrain.

## 4. Main 28-day visibility simulation

### 4.1 Simulation configuration

| Parameter | Value |
|---|---|
| Start time | 2026-11-14 00:00 UTC |
| Duration | 28 days |
| Sampling interval | 30 minutes |
| Antenna height | 2 m |
| Maximum terrain horizon range | 40 km |
| Horizon azimuth step | 0.5° |
| Horizon directions | 720 |
| Earth-disc samples | 400 |
| Terrain source | NASA LOLA 80 m DEM |
| Earth position source | Phase 6 SPICE-based calculations |

Each location produced 1,345 time samples.

Total samples across all three locations:

**4,035**

The final simulation timestamp is 2026-12-12 00:00 UTC.

### 4.2 Results

The following values represent the corrected three-site run after ensuring that Earth geometry and terrain-horizon calculations use the same observer elevation.

| Measurement | Floor candidate | Rim candidate | Malapert |
|---|---:|---:|---:|
| Mean visible fraction | 0.0000 | 0.0288 | 0.9786 |
| Any part visible | 0.00% | 13.01% | 100.00% |
| Centre visible | 0.00% | 0.00% | 100.00% |
| Fully visible | 0.00% | 0.00% | 86.10% |
| Completely blocked | 100.00% | 86.99% | 0.00% |
| Samples with incomplete terrain | 0 | 0 | 0 |

### 4.3 Interpretation

**Shackleton Floor Candidate**

The model calculated zero visible Earth-disc fraction across the simulated period. The high surrounding terrain horizon obstructed Earth's apparent disc in all evaluated samples.

This is a result for the selected candidate coordinate and 28-day period. It does not prove that the location is a permanently shadowed region or that Earth is permanently invisible there.

**Shackleton Rim Candidate**

The mean visible fraction was approximately 0.0288. Some part of Earth's disc was visible during approximately 13.01% of samples, but the disc centre was never above the terrain horizon and the entire disc was never visible.

This indicates intermittent partial visibility in the model.

**Malapert Massif**

Malapert had a mean visible fraction of approximately 0.9786. Some part of Earth was visible at every evaluated time sample, and the disc centre was visible throughout the simulation.

The entire disc was visible during approximately 86.10% of samples.

Among these three study locations, Malapert had the highest modelled Earth visibility during this particular 28-day period.

## 5. Sensitivity analysis

Sensitivity analysis was performed at both Malapert Massif and the Shackleton Rim Candidate to evaluate how the results changed when the horizon angular spacing and number of Earth-disc sample points were varied.

### 5.1 Malapert Massif sensitivity analysis

The analysis used a 28-day period with hourly sampling, producing 673 samples per configuration.

| Configuration | Horizon step | Disc points | Mean visible fraction | Any part visible | Fully visible |
|---|---:|---:|---:|---:|---:|
| A | 1.0° | 400 | 0.978585 | 100% | 86.181% |
| B — Baseline | 0.5° | 400 | 0.978652 | 100% | 86.181% |
| C | 0.25° | 400 | 0.978681 | 100% | 86.181% |
| D | 0.5° | 200 | 0.978878 | 100% | 86.181% |
| E | 0.5° | 1000 | 0.978790 | 100% | 86.181% |

#### Difference from baseline

Differences below are expressed in percentage points.

| Configuration | Mean absolute difference | Maximum difference |
|---|---:|---:|
| 1.0° / 400 | 0.006686 pp | 0.50 pp |
| 0.25° / 400 | 0.002972 pp | 0.50 pp |
| 0.5° / 200 | 0.065007 pp | 1.75 pp |
| 0.5° / 1000 | 0.039599 pp | 1.00 pp |

The tested configurations produced very similar mean visibility values and identical fully-visible percentages.

The baseline of 0.5° horizon spacing and 400 disc points provides a reasonable balance between computational cost and numerical stability for this study.

### 5.2 Shackleton Rim Candidate sensitivity analysis

A second sensitivity analysis was performed at the Shackleton Rim Candidate to verify numerical stability at a location with intermittent partial Earth visibility.

The analysis used the same 28-day period, from 2026-11-14 to 2026-12-12, with hourly sampling. Each configuration produced 673 samples. All configurations reported zero incomplete-terrain samples.

| Configuration | Horizon step | Disc points | Mean visible fraction | Any part visible | Fully visible |
|---|---:|---:|---:|---:|---:|
| A | 1.0° | 400 | 0.028826 | 13.076% | 0% |
| B — Baseline | 0.5° | 400 | 0.028819 | 13.076% | 0% |
| C | 0.25° | 400 | 0.028819 | 13.076% | 0% |
| D | 0.5° | 200 | 0.028975 | 12.779% | 0% |
| E | 0.5° | 1000 | 0.028731 | 13.076% | 0% |

The 1.0°, 0.5°, and 0.25° horizon configurations produced nearly identical mean visible fractions and identical percentages of samples with some part of Earth's disc visible. Increasing the horizon resolution beyond 0.5° did not materially change the reported results.

Changing the disc sampling from 400 to 200 points produced a small difference in the percentage of samples with partial visibility. The 1,000-point configuration remained close to the 400-point baseline.

These results support retaining **0.5° horizon spacing and 400 Earth-disc points** as the Phase 8 baseline for this study. They demonstrate numerical stability across the tested configurations, not absolute physical accuracy.

## 6. Testing and verification

### 6.1 Dedicated Phase 8 tests

The dedicated Phase 8 tests were run after adding the exact circle-segment validation and API integration tests.

| Test module | Tests passed |
|---|---:|
| `tests/test_phase8_disc.py` | 18 |
| `tests/test_phase8_earth_visibility.py` | 15 |
| `tests/test_phase8_with_terrain.py` | 4 |
| `tests/test_phase8_api.py` | 4 |
| **Total** | **41** |

The tests cover:

- Disc sampling and sky-coordinate generation.
- Horizon interpolation and azimuth wraparound.
- Non-divisor azimuth spacing.
- Visibility fraction calculations.
- An exact circle-segment formula comparison for partial-disc visibility.
- Complete and incomplete terrain coverage.
- Summary statistics.
- Synthetic terrain obstruction.
- Visibility under different Earth elevations.
- Visibility away from a terrain obstruction.
- API rejection of invalid latitude.
- API rejection of invalid timestamps.
- Successful Malapert visibility API response.
- Incomplete terrain reporting near the DEM coverage boundary.

The four API tests include two validation tests and two real-data integration tests. The real-data tests require the NASA LOLA DEM and the necessary SPICE kernels.

### 6.2 Full project regression

The earlier full-project regression result was:

**126 passed, 1 warning**

There were no failures in that earlier run.

The warning was an existing Starlette deprecation warning concerning use of `httpx` with `starlette.testclient`, recommending `httpx2`. It did not cause test failures.

**Final regression status:** A new full-project regression run is required after the latest reviewer-requested API tests and observer-height correction. The earlier 126-test result must not be treated as the final count for the updated codebase.

The final command is:

`python -m pytest -v`

The final result should be recorded after that run.

### 6.3 Additional verification

The following checks were completed during Phase 8 development:

- Python compilation of the visibility package.
- Python compilation of Phase 8 scripts.
- `git diff --check`.
- API route registration and duplicate-route checks.
- API validation checks for invalid coordinates and timestamps.
- End-to-end API smoke test.

The end-to-end API smoke test returned HTTP 200 for Malapert, with 25 samples for a one-day hourly request, 720/720 complete terrain directions, mean visible fraction 1.0, and zero incomplete-terrain samples.

The dedicated API test suite also passed all four tests.

## 7. Generated outputs

The following files were generated under `docs/phase8_results/`:

| File | Purpose |
|---|---|
| `shackleton_floor_candidate_visibility.csv` | Time-series visibility for the floor candidate |
| `shackleton_rim_candidate_visibility.csv` | Time-series visibility for the rim candidate |
| `malapert_massif_visibility.csv` | Time-series visibility for Malapert |
| `phase8_all_sites_visibility.csv` | Combined time-series dataset |
| `phase8_visibility_summary.csv` | Summary statistics for all sites |
| `phase8_visibility_timeline_corrected.png` | Corrected three-site visibility timeline |
| `phase8_sensitivity_results.csv` | Malapert numerical sensitivity analysis |
| `phase8_shackleton_rim_sensitivity_results.csv` | Shackleton Rim Candidate numerical sensitivity analysis |
| `phase8_technical_report.md` | This technical report |

Supporting scripts:

- `scripts/phase8_pick_sites.py`
- `scripts/phase8_site_horizons.py`
- `scripts/phase8_visibility.py`
- `scripts/phase8_rebuild_outputs.py`
- `scripts/phase8_sensitivity.py`

The NASA LOLA DEM is stored locally at:

`data/dem/LDEM_80S_80MPP_ADJ.TIF`

The dataset is an 80 m resolution DEM. The local `data/` directory is excluded from Git, so the large DEM file is not included in the repository.

## 8. Scientific and technical limitations

The following limitations apply to the current implementation:

1. **DEM resolution:** The terrain source is an 80 m resolution LOLA DEM. Smaller features may not be represented accurately.
2. **Horizon range:** The terrain horizon is evaluated to a maximum range of 40 km. Terrain beyond this distance is not included.
3. **Geometric model:** The model evaluates geometric line-of-sight obstruction. It does not model diffraction, atmospheric or plasma effects, or radio propagation.
4. **No communication link budget:** Visibility does not guarantee a usable communication link. Transmitter power, antenna gain, receiver sensitivity, frequency, pointing accuracy, and other link-budget parameters are outside Phase 8.
5. **Finite disc sampling:** The 400-point Earth-disc representation approximates the continuous apparent disc.
6. **Sampled terrain coverage:** Completeness refers to the terrain samples evaluated along each ray. It does not prove continuous coverage between every sampled point.
7. **Incomplete terrain:** Incomplete directions are flagged. Their provisional visibility estimates must not be interpreted as confirmed clear lines of sight.
8. **Simulation period:** The principal results cover one specific 28-day interval. They do not establish long-term or seasonal availability.
9. **Candidate locations:** The Shackleton floor and rim coordinates are provisional DEM-based candidates, not independently confirmed geological classifications.
10. **Observer height:** Earth geometry and terrain-horizon calculations use a consistent observer elevation: DEM-derived site elevation plus antenna height. The ground elevation and antenna height are retained separately in the site metadata.

## 9. Conclusion

Phase 8 successfully integrates the Phase 6 Earth-track model with the Phase 7 real lunar terrain horizon model.

The project now estimates the visible fraction of Earth's apparent disc over time, rather than relying only on whether Earth's centre is above an ideal flat horizon.

The three-site study showed substantially different visibility behaviour:

- The Shackleton Floor Candidate had zero modelled visibility during the selected period.
- The Shackleton Rim Candidate had intermittent partial visibility.
- Malapert Massif maintained some Earth-disc visibility throughout the selected period and had the highest mean visible fraction of the three sites.

The sensitivity analyses at Malapert and the Shackleton Rim Candidate support the selected baseline of 0.5° horizon spacing and 400 Earth-disc points for the tested configurations.

Phase 8 delivers:

- A reusable Earth-disc sampling model.
- Terrain-aware Earth visibility calculations.
- Integration with SPICE-based Earth tracking and NASA LOLA terrain.
- A new FastAPI visibility endpoint.
- Three-site 28-day simulation datasets.
- A corrected visibility timeline.
- Two numerical sensitivity analyses.
- Dedicated tests, including API integration and exact circle-segment validation.
- A technical report documenting the implementation and limitations.

**Phase 8 implementation, integration, scientific analysis, dedicated testing, and documentation are complete.**

## 10. Git and project finalization

The main Phase 8 implementation was previously committed and pushed to the GitHub repository.

The previously confirmed latest pushed short commit hash was:

`ede4a62`

The repository was reported clean and synchronized with `origin/main` after that push.

The reviewer-requested follow-up work includes:

- Consistent observer-height handling.
- Exact circle-segment validation.
- Phase 8 API integration tests.
- Shackleton Rim Candidate sensitivity analysis.
- Updated Phase 7 and Phase 8 documentation.

These follow-up changes require a final full-project regression run, followed by a separate Git commit and push.

The final follow-up commit hash, commit message, full regression result, and clean Git status must be recorded here after those operations are completed.

**Phase 8 is technically complete. Final follow-up verification and Git publication remain to be recorded.**
