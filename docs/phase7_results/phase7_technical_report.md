

# Phase 7 — Real Lunar Terrain Horizon Modelling



**Project:** Lunar South Pole Quantum Scheduler

**Phase:** 7

**Status:** Implementation and automated testing completed; Git verification and publication pending

**Date:** 13 November 2026



---



## 1. Phase 7 Objective



The objective of Phase 7 is to introduce real lunar terrain into the project's geometric environment model.



Earlier phases calculated the direction, elevation, azimuth, distance, and apparent angular size of Earth as viewed from lunar surface locations.



However, those calculations did not determine whether local lunar mountains, crater rims, ridges, or other terrain features obstruct the line of sight.



Phase 7 introduces a terrain-based horizon model.



It calculates the maximum terrain elevation angle along different azimuth directions around a selected lunar site.



This creates the terrain visibility information required by a future phase that will combine Earth's apparent position with local terrain obstruction.



### Main objectives



1. Build a reusable lunar terrain representation.

2. Implement a South Polar Stereographic projection.

3. Generate synthetic terrain for mathematical testing.

4. Integrate a real NASA LOLA Digital Elevation Model.

5. Load local terrain windows efficiently.

6. Calculate horizon profiles across multiple azimuth directions.

7. Detect incomplete terrain coverage.

8. Expose horizon calculations through a FastAPI endpoint.

9. Test the implementation with synthetic and real terrain data.



---



## 2. Project Structure



Phase 7 introduced the following files:



### Terrain implementation



- `backend/terrain/__init__.py`

- `backend/terrain/projection.py`

- `backend/terrain/terrain_model.py`

- `backend/terrain/horizon.py`

- `backend/terrain/dem_loader.py`



### Tests



- `tests/test_phase7_terrain.py`

- `tests/test_phase7_real_dem.py`

- `tests/test_phase7_horizon_edges.py`

- `tests/test_phase7_api.py`



### NASA data



- `data/dem/LDEM_80S_80MPP_ADJ.TIF`



### Documentation



- `docs/phase7_results/phase7_technical_report.md`



The NASA DEM is stored locally and excluded from Git through the project's `data/` ignore rule.



---



## 3. South Polar Stereographic Projection



The terrain model uses a South Polar Stereographic projection.



This allows lunar latitude and longitude coordinates to be represented as planar X and Y coordinates around the South Pole.



The lunar radius used is:



`MOON_RADIUS_M = 1,737,400 metres`



The projection equations are:



`rho = 2R × tan((90° + latitude) / 2)`



`x = rho × sin(longitude)`



`y = rho × cos(longitude)`



Here, latitude and longitude are expressed in radians when used in trigonometric calculations.



### Coordinate convention



- Longitude 0° points along positive Y.

- Longitude 90° east points along positive X.

- The South Pole maps to (0, 0).



The inverse projection is implemented through:



`xy_to_lonlat(x, y)`



### Projection validation



The project's projection was compared with the projection defined by the NASA DEM using PyProj.



| Latitude | Longitude | Result |

|---|---:|---|

| -90° | 0° | Exact match |

| -80° | 0° | Match |

| -80° | 90°E | Match |

| -85° | 120°E | Match |



The tested coordinates matched with no measurable difference in the comparison.



This verifies agreement at the tested points, not every possible coordinate in the projection.



---



## 4. Synthetic Terrain Model



Before integrating NASA data, a synthetic terrain system was developed.



This provides controlled elevation surfaces for testing the mathematical behaviour of the horizon algorithm.



### Terrain representation



The `Terrain` class stores:



- A two-dimensional elevation array.

- The X coordinate of the first pixel centre.

- The Y coordinate of the first pixel centre.

- The terrain pixel resolution in metres.



Elevation data is stored as NumPy float32 values.



### Bilinear interpolation



The method:



`height_at(x, y)`



returns an interpolated terrain elevation at a requested projected coordinate.



Bilinear interpolation uses the surrounding four pixels to estimate an elevation between pixel centres.



Coordinates outside the available terrain and missing elevation samples return NaN.



### Synthetic terrain generator



`make_synthetic_terrain()`



creates terrain around the South Pole using a supplied height function.



It supports:



- Flat terrain.

- Artificial ridges.

- Directional terrain obstructions.

- Controlled elevation variations.



This made it possible to test horizon behaviour without relying on NASA files.



---



## 5. NASA LOLA Real Elevation Data



Phase 7 integrates a real lunar Digital Elevation Model from NASA.



### Dataset



**Source:** NASA Planetary Geodesy and Geophysics Archive

**Dataset:** LOLA 80 m South Polar elevation product

**File:** `LDEM_80S_80MPP_ADJ.TIF`



Original source:



https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF



The filename contains `80MPP`, indicating the 80 metres per pixel product.



### Dataset characteristics



| Property | Value |

|---|---|

| Format | GeoTIFF |

| Dimensions | 7600 × 7600 |

| Bands | 1 |

| Data type | Float32 |

| Pixel resolution | 80 m |

| NoData | NaN |

| Projected coverage | 608 km × 608 km |

| CRS | IAU 30135 |

| Elevation values | Approximately -7295.5 m to +7026.3 m |



The dataset uses a lunar South Polar Stereographic projection.



The DEM does not cover the entire Moon. Its coverage is concentrated south of approximately 80°S.



Consequently, the Chandrayaan-3 landing site at approximately 69.37°S is outside this dataset's intended coverage.



### Local storage



The dataset is stored at:



`data/dem/LDEM_80S_80MPP_ADJ.TIF`



Its downloaded file size is approximately 180.4 MB.



It is excluded from Git to avoid committing a large binary dataset.



---



## 6. Real DEM Loader



The file:



`backend/terrain/dem_loader.py`



implements the real terrain loading pipeline.



### Main function



`load_dem_terrain()`



Inputs:



- Lunar latitude.

- Lunar longitude.

- Terrain half-size.

- Optional DEM file path.



### Loading process



1. Validate latitude, longitude, and requested terrain size.

2. Open the GeoTIFF through Rasterio.

3. Verify the dataset CRS and projected coordinate system.

4. Convert the lunar site coordinates into the DEM's projected coordinate system using PyProj.

5. Compare the projected coordinates with the project's own projection.

6. Calculate a local terrain window around the requested site.

7. Read only that window rather than loading the entire 7600 × 7600 dataset.

8. Convert missing and non-finite values into NaN.

9. Calculate the projected coordinate of the first pixel centre.

10. Return a reusable `Terrain` object.



### Memory and performance



The loader uses Rasterio windowed reading.



This avoids repeatedly loading the complete DEM when only a local region is required.



It also uses an LRU cache:



`@lru_cache(maxsize=8)`



Repeated requests for the same DEM path and site parameters can reuse the previously loaded terrain window.



Supporting functions:



- `clear_dem_cache()`

- `dem_cache_info()`



---



## 7. Real DEM Site Validation



Three important locations were checked against the NASA DEM.



| Location | Latitude | Longitude | Sampled elevation |

|---|---:|---:|---:|

| Shackleton crater centre | -89.9° | 129.78°E | -361.33 m |

| Malapert Massif | -85.99° | 0.12°E | +4844.85 m |

| South Pole | -90° | 0° | +1282.30 m |



These are nearest-pixel samples, not bilinearly interpolated site elevations.



### Shackleton local terrain window



A 5 km half-size terrain window was loaded.



| Property | Result |

|---|---:|

| Array dimensions | 125 × 125 |

| Pixel resolution | 80 m |

| Valid pixels | 15,625 |

| Missing pixels | 0 |

| Minimum elevation | -2843.63 m |

| Maximum elevation | +1736.76 m |

| Interpolated site elevation | Approximately -337.98 m |



The interpolated elevation differs from the nearest-pixel sample because it uses surrounding raster pixels.



---



## 8. Terrain-Based Horizon Algorithm



The main implementation is:



`backend/terrain/horizon.py`



Function:



`horizon_profile()`



The algorithm calculates a horizon elevation profile around a selected lunar site.



### Input parameters



- `terrain`

- `lat_deg`

- `lon_deg`

- `antenna_height_m`

- `azimuth_step_deg`

- `max_range_m`

- `step_m`



### Calculation process



For each azimuth direction:



1. Generate the requested azimuth.

2. Calculate points along the ray from the selected site.

3. Convert the ray positions into lunar geographic coordinates.

4. Project the positions into the terrain coordinate system.

5. Sample the terrain elevations.

6. Calculate the apparent elevation angle of each sampled terrain point relative to the observer.

7. Find the maximum valid elevation angle along that direction.

8. Record the distance associated with that maximum.

9. Track whether the ray reaches the requested maximum distance.

10. Track whether the sampled terrain coverage is complete.



The lunar surface is treated geometrically using the lunar radius.



The calculation accounts for the spherical shape of the Moon rather than assuming a perfectly flat planetary surface.



### Sampling strategy



The real NASA DEM has a native resolution of 80 metres.



For real terrain calculations, the API uses:



`step_m = terrain.pixel_m`



This means the ray sampling interval is 80 metres for this dataset.



The algorithm also includes the exact requested maximum range as a sample, even when the range is not an exact multiple of the sampling interval.



### Horizon interpretation



The horizon elevation represents the highest sampled terrain elevation angle in a particular azimuth direction.



A larger positive value indicates terrain rising above the local horizontal direction.



A negative value indicates that the highest sampled terrain remains below the local horizontal direction.



The associated `blocking_distance_m` is the distance to the sample producing the maximum elevation angle. It should not automatically be interpreted as a unique physical obstacle.



---



## 9. Terrain Coverage Validation



A major improvement in Phase 7 is explicit coverage reporting.



The algorithm distinguishes three different conditions.



### `ray_reaches_end`



Indicates whether the ray has a valid terrain sample at the exact requested maximum range.



### `ray_coverage_complete`



Indicates whether all sampled points along the ray have valid terrain values.



### `horizon_is_complete`



Indicates whether the calculated horizon has complete sampled coverage.



Missing terrain is not silently treated as zero elevation.



Where valid samples exist, the algorithm can calculate a provisional horizon while marking the coverage as incomplete.



Where no valid samples exist, the horizon value is NaN.



This prevents incomplete DEM coverage from being mistaken for a fully verified horizon.



---



## 10. Real Terrain Horizon Results



### Shackleton crater centre



Parameters:



- Latitude: -89.9°

- Longitude: 129.78°E

- Antenna height: 2 m

- Maximum range: 4,000 m

- Azimuth interval: 5°

- Terrain resolution: 80 m



Results:



| Measurement | Result |

|---|---:|

| Azimuth directions | 72 |

| Rays reaching endpoint | 72 |

| Complete ray coverage | 72 |

| Complete horizon directions | 72 |

| Minimum horizon elevation | Approximately -30.00° |

| Maximum horizon elevation | Approximately +32.85° |



All 72 sampled directions had complete terrain coverage for this calculation.



### Malapert Massif



Parameters:



- Latitude: -85.99°

- Longitude: 0.12°E

- Maximum range: 40,000 m

- Azimuth interval: 5°

- Terrain resolution: 80 m



Results:



| Measurement | Result |

|---|---:|

| Azimuth directions | 72 |

| Rays reaching endpoint | 72 |

| Complete ray coverage | 72 |

| Complete horizon directions | 72 |

| Minimum horizon elevation | Approximately -4.39° |

| Maximum horizon elevation | Approximately +4.73° |



These results demonstrate that the implementation can calculate horizon profiles over substantially different terrain environments.



They are geometric model outputs, not measurements of radio communication performance.



---



## 11. Sampling Resolution Comparison



The Shackleton terrain horizon was also compared using 80 m and 160 m sampling intervals.



| Measurement | Result |

|---|---:|

| Maximum absolute horizon difference | Approximately 0.0743° |

| Mean absolute horizon difference | Approximately 0.00438° |

| Directions differing by more than 1° | 0 |



The 80 m interval was selected for the real DEM integration because it matches the dataset's native pixel resolution.



This comparison does not establish that all terrain features smaller than 80 m are represented accurately.



---



## 12. FastAPI Integration



The new endpoint is:



`GET /api/terrain/horizon`



It is implemented in:



`backend/main.py`



### Query parameters



| Parameter | Default | Validation |

|---|---:|---|

| `latitude_deg` | Required | -90 to 0 |

| `longitude_deg` | Required | -180 to 180 |

| `antenna_height_m` | 2.0 | Non-negative |

| `max_range_m` | 40,000 | Greater than 0, maximum 100,000 |

| `azimuth_step_deg` | 1.0 | 0.25 to 10 |



### Endpoint workflow



1. Receive and validate query parameters.

2. Load a local NASA DEM terrain window.

3. Use the DEM's native pixel resolution for ray sampling.

4. Calculate the horizon profile.

5. Summarize complete and incomplete directions.

6. Return the terrain source, site information, settings, coverage, and horizon arrays.



### Response information



The endpoint returns:



- DEM source.

- Dataset resolution.

- Site latitude and longitude.

- Interpolated site elevation.

- Antenna height.

- Maximum range.

- Azimuth interval.

- Sampling interval.

- Complete direction count.

- Total direction count.

- All-directions-complete status.

- Azimuth array.

- Horizon elevation array.

- Blocking-distance array.

- Ray endpoint flags.

- Ray coverage flags.

- Horizon completeness flags.



### Error handling



| Condition | HTTP status |

|---|---:|

| Missing NASA DEM | 503 |

| Invalid terrain request | 422 |

| Invalid FastAPI query parameter | 422 |

| Successful calculation | 200 |



---



## 13. API Validation



The endpoint was manually tested using FastAPI TestClient.



### Shackleton request



Parameters:



- Latitude: -89.9

- Longitude: 129.78

- Antenna height: 2 m

- Maximum range: 4,000 m

- Azimuth interval: 5°



Result:



- HTTP 200

- NASA LOLA DEM returned as source.

- Resolution: 80 m.

- Interpolated elevation: approximately -337.98 m.

- Complete directions: 72/72.



### DEM coverage boundary request



A second request was made near the northern edge of the DEM coverage:



- Latitude: -80.5

- Longitude: 0°

- Maximum range: 40,000 m

- Azimuth interval: 5°



Result:



- HTTP 200

- Complete directions: 45/72.

- Incomplete directions: 27.



This confirms that incomplete coverage is reported instead of being falsely represented as complete.



---



## 14. Automated Test Coverage



Phase 7 has four test modules.



### `test_phase7_terrain.py`



Tests synthetic terrain, projection, interpolation, horizon behaviour, obstruction, and map coverage.



### `test_phase7_real_dem.py`



Tests missing DEM files, invalid inputs, real NASA DEM loading, pixel-centre consistency, and caching.



### `test_phase7_horizon_edges.py`



Tests exact maximum-range sampling and incomplete terrain detection.



### `test_phase7_api.py`



Tests successful API responses and error handling.



The four API tests cover:



1. Valid terrain horizon response.

2. Missing DEM response.

3. Invalid terrain response.

4. Invalid latitude response.



### Latest test results



The four new API tests passed:



`4 passed, 1 warning`



The final complete regression suite, including all Phase 7 API tests, passed:



`90 passed, 1 warning`



All 90 tests passed. No test failures or skips were reported.



The existing warning is:



`StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.`



This warning did not cause a test failure.



---



## 15. Dependencies



The real DEM integration uses:



- NumPy

- Rasterio

- GDAL

- PyProj



Installed environment versions during implementation:



| Package | Version |

|---|---:|

| Python | 3.15.2 |

| Rasterio | 1.5.2 |

| GDAL | 3.12.2 |

| PyProj | 3.8.0 |

| PROJ | 9.8.1 |

| NumPy | 2.5.4 |



---



## 16. Known Limitations



Phase 7 provides geometric terrain horizon calculations. It does not yet model every factor affecting real communications or visibility.



### Terrain resolution



The DEM has an 80 m pixel resolution.



Smaller terrain features may not be represented accurately.



### Dataset coverage



The NASA DEM does not cover all lunar latitudes.



Locations outside its coverage require another suitable lunar elevation dataset.



### Ray sampling



Coverage completeness refers to sampled points, not every continuous point between samples.



### Horizon approximation



The maximum sampled elevation angle is a geometric terrain horizon estimate.



It does not include diffraction, atmospheric refraction, or radio propagation effects.



### Communication reliability



The model does not yet calculate:



- Signal strength.

- Antenna gain.

- Link budget.

- Signal-to-noise ratio.

- Data rate.

- Interference.

- Actual communication reliability.



### Earth visibility



Phase 7 calculates terrain horizon profiles independently of Earth's apparent direction.



Combining Earth azimuth and elevation with terrain obstruction is a later integration task.



---



## 17. Phase 7 Deliverables



The following capabilities have been implemented:



- [x] South Polar Stereographic projection.

- [x] Inverse projection.

- [x] Synthetic terrain generation.

- [x] Bilinear terrain interpolation.

- [x] Horizon profile calculation.

- [x] Spherical lunar geometry in horizon calculations.

- [x] Exact maximum-range sampling.

- [x] Missing terrain detection.

- [x] Coverage completeness reporting.

- [x] NASA LOLA DEM integration.

- [x] Windowed raster loading.

- [x] DEM caching.

- [x] Real Shackleton terrain validation.

- [x] Real Malapert terrain validation.

- [x] FastAPI horizon endpoint.

- [x] Automated API tests.



### Remaining project verification



- [x] Run the complete regression suite after adding API tests (90 passed, 1 warning).

- [x] Review final documentation and generated outputs, including Markdown formatting and UTF-8 encoding.

- [ ] Verify Git status and intended tracked files.

- [ ] Confirm the NASA DEM and local backup files are not committed.

- [ ] Verify the final commit and push.



---



## 18. Conclusion



Phase 7 introduces real lunar terrain into the Lunar South Pole Quantum Scheduler.



The project has progressed from purely geometric lunar and Earth-direction calculations to a terrain-aware geometric environment model.



The implementation combines a South Polar Stereographic projection, synthetic terrain testing, NASA LOLA elevation data, local raster loading, spherical horizon calculations, coverage validation, and a FastAPI endpoint.



Real terrain tests at Shackleton crater centre and Malapert Massif demonstrate that the system can calculate horizon profiles from actual lunar elevation data.



The API tests also verify successful responses and expected error handling.



The regression suite and documentation review are complete. Final Git verification, commit, and push remain before Phase 7 can be formally declared complete.



**Phase 7 status: Implementation and testing complete; final Git verification and publication pending.**
