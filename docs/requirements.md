
# Lunar South Pole Quantum Scheduler
# Project Requirements and Technical Decisions

## Phase 5 - Lunar Coordinate and Geometry Decisions

### Reference geometry
- Moon reference model: spherical Moon.
- Reference sphere radius: 1737.4 km.
- Reference frame: MOON_ME_DE440_ME421.
- Lander height is measured in metres above the reference sphere.
- Latitude is expressed in degrees.
- Southern latitudes are negative.
- Longitude is positive eastward.

### Coordinate systems
- Moon-fixed coordinates are used for lunar surface geometry.
- J2000 coordinates are used for inertial space positions.
- Local directions use East-North-Up (ENU) axes.
- ENU directions are calculated at the lander's surface location.

### Earth geometry
- Earth direction and distance are calculated geometrically.
- SPICE aberration correction: abcorr = NONE.
- Earth direction vectors are evaluated in Moon-fixed and J2000 frames.
- Phase 5 does not calculate Earth elevation or azimuth.
- Phase 5 does not calculate terrain obstruction or communication visibility.

### Phase 5 API
Endpoint:
GET /api/physics/lander-position

Parameters:
- latitude_deg
- longitude_deg
- height_m
- utc

Latitude validation range: -90 to +90 degrees.
Longitude validation range: -180 to +180 degrees.

### Phase 5 validation baseline
- Coordinate tests: 7 passed.
- Geometry and API tests: 10 passed.
- Multi-site validation checks: 12 passed.
- Full project test suite at Phase 5 completion: 30 passed.
- Phase 5 commit: e437a6a.

Validation sites:
1. Shackleton Rim: -89.9, 129.78
2. Malapert Massif: -85.99, 0.12
3. Chandrayaan-3 Landing Site: -69.37, 32.32

Validation dates:
- 2026-11-13
- 2026-11-20
- 2026-11-27
- 2026-12-04

Detailed numerical results:
See docs/phase5_test_results.txt.

## Phase 6 - Earth Direction and Apparent Size

### Implemented calculations
- Earth azimuth from the local East-North-Up (ENU) frame.
- Earth elevation above a flat local horizon.
- Lander-to-Earth distance.
- Earth's apparent angular radius.
- Upper and lower limb elevations.
- Earth direction and apparent elevation over a specified time interval.
- Summary statistics for Earth elevation and horizon intersection.

### Technical assumptions
- Geometric SPICE calculations without light-time correction.
- SPICE aberration correction: abcorr = NONE.
- Flat local horizon; terrain obstruction is not included.
- Earth equatorial radius: 6378.137 km.
- Default time sampling interval: 5 minutes.
- Maximum samples per API request: 20,000.
- Earth angular radius is calculated using the Earth equatorial radius and lander-to-Earth distance.

### Phase 6 API

#### Earth direction
Endpoint:
GET /api/physics/earth-direction

Parameters:
- latitude_deg
- longitude_deg
- height_m
- utc

Returns:
- Earth azimuth and elevation.
- Earth distance.
- Angular radius.
- Upper and lower limb elevations.
- Earth direction vector in Moon-fixed coordinates.
- Aberration correction and horizon model metadata.

#### Earth track
Endpoint:
GET /api/physics/earth-track

Parameters:
- latitude_deg
- longitude_deg
- height_m
- start_utc
- duration_days
- step_minutes

Returns:
- Time-series Earth azimuth and elevation.
- Earth distance and apparent angular radius.
- Upper and lower limb elevations.
- Track start and end times.
- Sample count and summary statistics.
- Counts of Earth-centre-above-horizon, Earth-disc-intersecting-horizon, and Earth-disc-entirely-above-horizon samples.

### Phase 6 automated test results
- Azimuth and elevation tests: 9 passed.
- Earth geometry, tracking and API tests: 24 passed.
- Phase 6 tests combined: 33 passed.
- Full project test suite: 63 passed.
- One non-blocking Starlette deprecation warning remains.

### Phase 6 numerical validation

Validation configuration:
- Start UTC: 2026-11-13T00:00:00Z.
- Duration: 1 day per site.
- Sampling interval: 5 minutes.
- Expected samples per site: 289.
- Total observations: 867.
- SPICE aberration correction: NONE.
- Horizon model: flat.

Validation sites and results:

1. Shackleton Rim
   - Latitude: -89.9 degrees.
   - Longitude: 129.78 degrees.
   - Height: 0 metres.
   - Samples: 289.
   - Earth distance: approximately 405,506.384 km.
   - Angular radius: approximately 0.901232 degrees.
   - Elevation range: -5.621102 to -4.713839 degrees.
   - Earth centre above horizon: 0 samples.
   - Earth disc intersects horizon: 0 samples.
   - Earth disc entirely above horizon: 0 samples.

2. Malapert Massif
   - Latitude: -85.99 degrees.
   - Longitude: 0.12 degrees.
   - Height: 100 metres.
   - Samples: 289.
   - Earth distance: approximately 405,383.123 km.
   - Angular radius: approximately 0.901506 degrees.
   - Elevation range: -1.548397 to -0.640161 degrees.
   - Earth centre above horizon: 0 samples.
   - Earth disc intersects horizon: 77 samples.
   - Earth disc entirely above horizon: 0 samples.

3. Chandrayaan-3 Landing Site
   - Latitude: -69.37 degrees.
   - Longitude: 32.32 degrees.
   - Height: 0 metres.
   - Samples: 289.
   - Earth distance: approximately 404,978.219 km.
   - Angular radius: approximately 0.902408 degrees.
   - Elevation range: 11.894971 to 12.523416 degrees.
   - Earth centre above horizon: 289 samples.
   - Earth disc intersects horizon: 0 samples.
   - Earth disc entirely above horizon: 289 samples.

### Phase 6 generated validation artifacts

Directory:
docs/phase6_results/

Generated files:
- shackleton_rim_earth_track.csv
- shackleton_rim_earth_elevation.png
- malapert_massif_earth_track.csv
- malapert_massif_earth_elevation.png
- chandrayaan_3_landing_site_earth_track.csv
- chandrayaan_3_landing_site_earth_elevation.png
- phase6_validation_results.txt

Numerical, time-series and plotting checks passed for all three sites.

Important limitation:
Flat-horizon elevation and Earth-disc intersection are geometric results. They do not establish terrain visibility, actual radio-link availability, or communication reliability.

## Known development warning

The full test suite passed with one non-blocking warning:

StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.

This warning did not cause any test failures.
