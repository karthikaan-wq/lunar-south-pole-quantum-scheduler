# Phase 10 — Refined Lunar Communication Window Detection

**Project:** Lunar South Pole Quantum Scheduler
**Phase:** 10
**Status:** Implementation, API integration, real-data execution, exports, and full test-suite verification completed; final Git review and publication pending.

## 1. Objective

Phase 10 extends the Phase 9 direct-to-Earth communication link model by identifying continuous periods during which a lunar surface station satisfies the configured communication constraints.

Previous phases calculated individual geometric and communication conditions at discrete timestamps. Phase 10 converts those individual availability decisions into communication windows with estimated start and end boundaries.

The principal outputs are:

- Refined communication-window start and end times.
- Window durations and available durations.
- Bridged short gaps.
- Rejected windows that do not satisfy the minimum duration.
- Limiting communication checks.
- Per-window statistics.
- Site-level availability summaries.

The model provides geometric communication-availability decision support. It is not a complete RF link budget or flight-qualified communications system.

## 2. Architecture and implementation

### 2.1 `backend/communications/windows.py`

This module implements the Phase 10 window-detection engine.

#### WindowSettings

The configuration contains three parameters:

| Parameter | Default | Purpose |
|---|---:|---|
| `resolution_s` | 60 seconds | Maximum transition-refinement bracket width |
| `max_gap_s` | 600 seconds | Maximum unavailable gap that can be bridged |
| `min_duration_s` | 1800 seconds | Minimum accepted available duration |

Validation rejects non-positive refinement resolution and negative gap or minimum-duration values.

#### Contiguous availability detection

`find_runs(flags)` identifies consecutive `True` values in the sampled availability array.

Each detected run is represented by an inclusive pair of sample indices.

`windows_from_flags(times_s, flags)` converts those runs into coarse windows and validates matching array lengths and strictly increasing timestamps.

#### Availability-state evaluation

The engine supports either Boolean state results or dictionaries containing availability information.

For dictionary results, the engine reads:

- `up` or `available`
- `reasons`

This allows the window detector to preserve the reasons why a transition into or out of availability occurred.

#### Boundary refinement

`refine_brackets(...)` uses bisection to refine a transition between a known available timestamp and a known unavailable timestamp.

At each iteration:

1. The midpoint of the bracket is calculated.
2. The continuous state evaluator is called.
3. The available or unavailable side of the bracket is updated.
4. Iteration continues until the bracket width is no greater than the configured resolution.

The returned boundary is the last verified available-side timestamp. This conservative convention avoids treating an unverified timestamp as available.

The default refinement resolution is 60 seconds.

#### Window merging

After individual runs have been refined, the engine calculates the gap between adjacent windows.

If the gap is no greater than `max_gap_s`, the windows are merged and the gap is recorded.

The bridged gap is subtracted from the merged duration when calculating `available_s`.

This preserves the distinction between the overall window span and the time actually classified as available.

#### Minimum-duration filtering

The engine compares each window's available duration with `min_duration_s`.

Windows below the threshold are placed in the rejected collection with the reason `too_short`.

Accepted and rejected windows retain their timing and diagnostic information.

#### Window statistics

When additional sample-aligned numerical series are provided, the engine calculates:

- Mean
- Minimum
- Maximum

Phase 10 supplies Earth visible fraction, Earth clearance, and Sun-Earth angular separation.

#### Clipped-window detection

A window is marked as clipped when it touches either observation-period boundary.

The flags are:

- `starts_before_period`
- `ends_after_period`
- `clipped`

These flags prevent an observation boundary from being mistaken for a physically determined acquisition or loss time.

#### Summary calculations

`summarize_windows(...)` calculates:

- Accepted window count.
- Rejected window count.
- Total available seconds and hours.
- Longest available window.
- Number of windows touching observation boundaries.
- Availability percentage when a valid observation duration is supplied.

### 2.2 `backend/communications/site_windows.py`

This module connects the earlier scientific models with the Phase 10 window engine.

The `windows_for_site(...)` function integrates five project phases.

**Phase 6 — SPICE Earth geometry**

Earth geometry is calculated at the selected lunar site and observation timestamps.

**Phase 7 — Lunar terrain horizon**

NASA LOLA elevation data is loaded and the terrain horizon is calculated.

The resulting horizon model is retained and reused for the sampled and refined timestamp evaluations.

**Phase 8 — Earth-disc visibility**

The apparent Earth disc is evaluated against the terrain horizon.

The resulting visible fraction and terrain-clearance measurements are retained for communication evaluation.

**Phase 9 — Direct-to-Earth link constraints**

Sun geometry is calculated at the same timestamps as Earth geometry.

The Phase 9 link evaluator applies the configured conditions, including:

- Terrain coverage completeness.
- Minimum Earth visible fraction.
- Minimum Earth clearance.
- Antenna pointing limits.
- Sun-exclusion requirements.

The link evaluator produces the final availability decision for every sample.

**Phase 10 — Window construction**

The sampled link decisions are passed to `build_windows(...)`.

A continuous `state_fn(epoch_seconds)` is also defined for transition refinement. At each requested timestamp it:

1. Converts the requested epoch time into a normalized UTC timestamp.
2. Calculates Earth geometry at that timestamp.
3. Evaluates the Earth disc using the retained horizon model.
4. Calculates Sun geometry at the same timestamp.
5. Re-evaluates the Phase 9 link constraints.
6. Returns availability and failed-check reasons.

The same terrain horizon is reused rather than regenerating it for every bisection evaluation.

The resulting function returns site information, settings, terrain information, Earth-track and visibility summaries, link samples, accepted windows, rejected windows, and an overall summary.

### 2.3 `backend/communications/routes.py`

Phase 10 adds the endpoint:

`GET /api/communications/windows`

The existing Phase 9 endpoint remains available:

`GET /api/communications/direct-to-earth`

The new endpoint accepts site coordinates, ground elevation, observation start time, duration, sampling interval, antenna configuration, communication constraints, and window-detection settings.

Window-specific query parameters are:

| Parameter | Default | Validation |
|---|---:|---|
| `resolution_s` | 60 | Greater than zero |
| `max_gap_s` | 600 | Zero or greater |
| `min_duration_s` | 1800 | Zero or greater |

The endpoint constructs the antenna, link-constraint, and window-settings objects, then calls `windows_for_site(...)`.

Invalid inputs return HTTP 422. Missing SPICE kernels or required files return HTTP 503.

The communications router is registered in `backend/main.py`.

The generated OpenAPI schema confirms both communications endpoints are registered.

## 3. Real lunar terrain and site configuration

The real-data study uses the NASA LOLA 80-metre DEM:

`data/dem/LDEM_80S_80MPP_ADJ.TIF`

The terrain dataset has:

- 80 m pixel resolution.
- 7600 × 7600 raster dimensions.
- South-polar stereographic projection.
- 80 m × 80 m pixel spacing.

Two lunar South Pole sites were evaluated.

| Property | Shackleton region | Malapert reference site |
|---|---:|---:|
| Latitude | −89.90° | −85.99° |
| Longitude | 129.78° | 0.12° |
| Ground elevation | −337.984 m | 4842.282 m |
| Antenna height | 2 m | 2 m |
| DEM resolution | 80 m | 80 m |
| Complete horizon directions | 720/720 | 720/720 |

The ground elevations are site-specific DEM elevations, not the elevation at the centre of the loaded terrain raster.

## 4. Observation and simulation settings

Both sites were evaluated using the same observation configuration.

| Setting | Value |
|---|---:|
| Observation start | 2026-11-14 00:00:00 UTC |
| Observation duration | 1 day |
| Observation end | 2026-11-15 00:00:00 UTC |
| Sampling interval | 60 minutes |
| Samples per site | 25 |
| Antenna height | 2 m |
| Maximum terrain-horizon range | 40,000 m |
| Horizon azimuth step | 0.5° |
| Earth-disc sampling points | 400 |
| Window refinement resolution | 60 seconds |
| Maximum bridgeable gap | 600 seconds |
| Minimum accepted duration | 1800 seconds |

The 25 samples include the start and end of the one-day observation interval.

## 5. Real-data results

### 5.1 Shackleton region

Results:

- 25 total samples.
- 0 available samples.
- 25 unavailable samples.
- 0% sampled link availability.
- 0 accepted windows.
- 0 rejected windows.
- 720/720 complete terrain-horizon directions.

The site produced no communication window under the tested conditions.

This is a result for the selected site, antenna configuration, constraints, and observation period. It should not be generalized to every location in the Shackleton region or every possible observation period.

### 5.2 Malapert reference site

Results:

- 25 total samples.
- 25 available samples.
- 0 unavailable samples.
- 100% sampled link availability.
- 1 accepted window.
- 0 rejected windows.
- 720/720 complete terrain-horizon directions.

The detected window is:

| Property | Result |
|---|---|
| Window ID | window_001 |
| Start | 2026-11-14 00:00:00 UTC |
| End | 2026-11-15 00:00:00 UTC |
| Duration | 86,400 seconds |
| Available duration | 86,400 seconds |
| Bridged gap | 0 seconds |
| Clipped | True |

The window statistics are:

| Measurement | Mean | Minimum | Maximum |
|---|---:|---:|---:|
| Earth visible fraction | 1.000 | 1.000 | 1.000 |
| Earth clearance | 2.932° | 2.429° | 3.460° |
| Sun-Earth separation | 122.476° | 117.099° | 127.848° |

The window has both boundary flags set:

- `starts_before_period = True`
- `ends_after_period = True`

Consequently, its start and end are clipped to the observation interval. The model establishes availability at every sampled time during this interval, but does not establish the actual acquisition or loss times.

The 24-hour result must therefore be interpreted as continuous availability across the tested observation period, not as a physically bounded 24-hour communication opportunity.

## 6. Generated outputs

All Phase 10 real-data outputs are stored in:

`docs/phase10_results/`

| File | Description |
|---|---|
| `phase10_all_sites_samples.csv` | Sample-level communication and geometry data for both sites |
| `phase10_windows.csv` | Accepted communication-window details |
| `phase10_summary.csv` | Site-level availability and terrain summary |
| `phase10_communications_timeline.png` | Visual timeline of sampled availability and detected windows |
| `phase10_technical_report.md` | Phase 10 technical documentation |

The export script is:

`scripts/phase10_communications.py`

It calculates both sites and generates the CSV and PNG outputs.

## 7. API and software verification

The Phase 10 API tests cover:

- Invalid latitude.
- Invalid timestamp.
- Invalid refinement resolution.
- Negative maximum gap.
- Negative minimum duration.
- Mocked window response.
- Real Malapert window integration.

The API schema includes:

- `/api/communications/direct-to-earth`
- `/api/communications/windows`

The full project test suite was executed using:

`python -m pytest -v`

Final result:

**208 passed, 0 failed, 1 warning.**

Execution time: 20.62 seconds.

The warning concerns the deprecation of using `httpx` with Starlette's `TestClient`. It did not cause a test failure.

The Phase 10 window-engine tests also cover contiguous runs, timestamp validation, boundary refinement, clipped windows, short-gap bridging, minimum-duration rejection, extra statistics, and summary calculations.

## 8. Scientific interpretation and limitations

### 8.1 Sampling resolution

The real-data study uses one-hour sampling intervals.

This is suitable for an initial daily availability study, but a short communication opportunity occurring entirely between adjacent samples could be missed.

A finer sampling interval should be used for more detailed operational scheduling.

### 8.2 Boundary refinement

The bisection refinement uses a 60-second stopping resolution.

This refines a detected transition within its sampled bracket. It does not guarantee that all possible transitions have been detected: the method depends on the initial samples identifying the availability runs.

### 8.3 Gap bridging

The engine can bridge gaps no longer than 600 seconds.

Bridged gaps are recorded separately and excluded from the calculated available duration.

The current real-data runs did not require gap bridging.

### 8.4 Minimum window duration

Windows shorter than 1800 seconds are rejected.

The current real-data study produced no rejected windows, but the rejection logic is covered by automated tests.

### 8.5 Terrain resolution

The terrain horizon uses an 80-metre NASA LOLA DEM.

Small-scale terrain features below the dataset's effective resolution may not be represented.

### 8.6 Communication model

The project evaluates geometric and configured link constraints. It does not yet implement a complete RF link budget covering transmitter power, antenna gain, receiver noise temperature, propagation losses, data rate, and link margin.

No claim of flight qualification or guaranteed operational connectivity is made.

### 8.7 Observation-period limitations

The Malapert window touches both observation boundaries. Longer observations are needed to identify its actual acquisition and loss transitions.

The Shackleton result is limited to the selected 24-hour interval and tested configuration.

### 8.8 Quantum optimization

Phase 10 generates classical communication-availability windows. These results can provide scheduling inputs for a future optimization phase, where quantum-inspired or QAOA-based scheduling can be evaluated against classical optimization baselines.

No quantum advantage is claimed by Phase 10.

## 9. Phase 10 completion assessment

The following implementation and verification tasks have been completed:

- Communication-window detection engine.
- Contiguous availability-run detection.
- Bisection-based transition refinement.
- Short-gap merging.
- Minimum-duration filtering.
- Window statistics and summaries.
- Site-level integration with Phases 6–9.
- Continuous state evaluation using the retained terrain horizon.
- FastAPI communications-window endpoint.
- API validation and integration tests.
- Real NASA DEM calculations for two lunar sites.
- Combined sample CSV export.
- Window CSV export.
- Site summary CSV export.
- Communication timeline PNG generation.
- Full project test suite: 208 passed.

Final Git review and publication remain pending.

## 10. Conclusion

Phase 10 introduces a complete initial communication-window detection workflow into the Lunar South Pole Quantum Scheduler.

It connects the project's Earth geometry, lunar terrain, Earth-disc visibility, antenna configuration, and Sun-exclusion models to produce time-based communication availability windows.

The Malapert reference-site experiment showed availability throughout the tested 24-hour interval, with a window clipped at both observation boundaries. The Shackleton test site produced no available samples during the same interval.

The implementation provides a foundation for longer observation studies, finer time sampling, multi-site scheduling, and future optimization work.
