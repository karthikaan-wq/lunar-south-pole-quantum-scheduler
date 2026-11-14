# Phase 12 — Rover-to-Lander Surface Links and End-to-End Communication

**Project:** Lunar South Pole Quantum Scheduler
**Phase:** 12
**Status:** Implementation, integration, and full regression testing completed
**Simulation period:** 15 November 2026 – 29 November 2026
**Primary terrain source:** NASA LOLA 80 m Lunar DEM

---

## 1. Executive Summary

Phase 12 introduces terrain-aware radio communication between lunar surface assets, specifically a stationary rover and a stationary lander.

The phase extends the project's communication model beyond direct-to-Earth visibility. It evaluates whether a rover can transmit data to a lander over a lunar surface radio link, whether both assets have sufficient electrical power, and whether the lander can subsequently forward the data to Earth.

The implementation combines:

1. Spherical lunar geometry and great-circle surface paths.
2. Terrain-aware radio line-of-sight calculations.
3. Antenna-height and radio-horizon modelling.
4. First Fresnel-zone clearance analysis.
5. NASA LOLA DEM terrain sampling.
6. Rover and lander energy timelines.
7. Power-eligible communication windows.
8. Lander-to-Earth communication windows.
9. Store-and-forward scheduling.
10. FastAPI integration and automated tests.

The real-terrain demonstration used a rover and lander separated by approximately 303.23 m near Malapert.

The terrain model found that the radio path is obstructed. Consequently, the surface link was unusable and the scheduler correctly generated zero uplink and zero end-to-end forwarding opportunities.

This is a meaningful negative engineering result: geographical proximity alone does not guarantee a usable radio link on the lunar surface.

---

## 2. Phase Objectives

The primary objective was to implement a system capable of evaluating communication opportunities between fixed lunar surface assets.

The system needed to answer:

- Are the rover and lander within the configured radio range?
- Is there unobstructed terrain line of sight?
- Does the radio path have sufficient Fresnel clearance?
- Are the rover and lander electrically eligible to communicate?
- When can the lander communicate with Earth?
- Can the lander forward rover data during an Earth communication window?
- How long must the system wait before a suitable forwarding opportunity?
- Does the available Earth window provide sufficient forwarding time?

### Version 1 scope

Both surface assets are stationary.

The radio geometry is therefore static. Time-dependent availability comes from electrical power and lander-to-Earth communication windows, rather than rover movement.

A future phase may introduce mobile rover trajectories and dynamically changing surface links.

---

## 3. Physical and Mathematical Model

### 3.1 Lunar reference geometry

The model uses the project's lunar reference radius:

`MOON_RADIUS_M`

Geographical positions are represented using latitude and longitude and converted into three-dimensional spherical unit vectors.

The surface path between two assets follows a great-circle route.

The great-circle distance is calculated from the angular separation of their spherical position vectors.

For lunar radius R and angular separation theta:

`surface_distance = R * theta`

This provides the surface arc distance.

The radio signal, however, travels along a straight chord between antenna locations rather than following the curved lunar surface.

### 3.2 Radio path geometry

The radio path is evaluated between the actual antenna positions.

Each antenna position accounts for:

- Lunar reference radius.
- Terrain elevation at the asset location.
- Antenna height above the terrain.

The algorithm samples the great-circle surface path at the configured spatial resolution.

At each sample, it compares the radial height of the straight radio chord with the local terrain elevation.

The minimum terrain clearance determines whether the terrain obstructs the radio path.

A positive clearance means the chord passes above the sampled terrain.

A negative clearance means the terrain rises above the radio path.

The default minimum clearance requirement is 0 m.

The model uses spherical reference geometry and radial terrain heights. It does not claim to represent every local geological feature.

### 3.3 Radio horizon

The approximate flat-ground radio horizon is calculated using:

`d ≈ sqrt(2 * R * h1) + sqrt(2 * R * h2)`

Where:

- R is the lunar radius.
- h1 is the first antenna height.
- h2 is the second antenna height.

Approximate theoretical horizon distances:

| Antenna configuration | Approximate radio horizon |
|---|---:|
| Two 2 m antennas | 5.3 km |
| 1.5 m rover + 3 m lander | 5.5 km |
| Two 10 m antennas | 11.8 km |

These are idealized flat-ground horizon estimates. Actual link availability also depends on terrain obstruction, range, and Fresnel clearance.

### 3.4 First Fresnel zone

The implementation evaluates the first Fresnel-zone radius along the radio path.

For wavelength lambda and distances d1 and d2 from the two antennas:

`F1 = sqrt(lambda * d1 * d2 / (d1 + d2))`

The wavelength is calculated from:

`lambda = c / frequency`

Where c is the speed of light.

The default frequency is 401.5 MHz.

For an illustrative 3 km radio path, the midpoint first Fresnel-zone radius is approximately 23.6 m.

This is a radius, not a full width. The corresponding diameter is approximately 47.2 m.

The implementation reports a minimum Fresnel clearance ratio along the path.

A negative ratio indicates that the terrain intrudes into the Fresnel zone.

The default minimum Fresnel ratio is 0.0. This disables an additional positive-clearance requirement while retaining Fresnel measurements for reporting.

### 3.5 Link usability

A surface link is considered usable only when:

- Terrain data is sufficiently complete.
- The radio path satisfies the line-of-sight clearance condition.
- The slant range does not exceed the configured maximum.
- The configured Fresnel threshold is satisfied.

The default maximum range is 10,000 m.

Missing terrain information is handled conservatively. Incomplete terrain coverage must not be interpreted as proof of an unobstructed radio link.

---

## 4. Terrain Data and Resolution

The implementation uses the project's NASA LOLA 80 m lunar digital elevation model.

The DEM file used by the project is:

`data/dem/LDEM_80S_80MPP_ADJ.TIF`

Terrain is loaded through the existing DEM loader and the project's lunar map projection.

The adapter loads one terrain window covering the relevant assets and the path between them, with a configurable margin.

The default terrain margin is 3,000 m.

The path sampling step is 40 m.

An important limitation is that a 40 m interpolation sampling interval does not create 40 m terrain resolution. The underlying DEM has approximately 80 m resolution.

Consequently:

- Small boulders may not be represented.
- Narrow ridges may be missed.
- Sub-pixel terrain details cannot be reliably inferred.
- Interpolated elevations are not equivalent to new high-resolution measurements.

The result should therefore be interpreted as a terrain-based engineering estimate using the available DEM, not a complete reconstruction of the local radio environment.

---

## 5. Software Architecture and Implementation

### 5.1 Surface radio-link engine

File:

`backend/communications/surface_links.py`

This module contains the core geometry and scheduling primitives.

Main components include:

- `SurfaceLinkSettings`
- `great_circle_points`
- `surface_link`
- `link_matrix`
- `intersect_windows`
- `forwarding_options`

Responsibilities:

1. Validate radio settings and asset coordinates.
2. Generate great-circle path samples.
3. Calculate antenna positions.
4. Calculate radio chord geometry.
5. Sample terrain along the path.
6. Calculate minimum terrain clearance.
7. Calculate Fresnel-zone clearance.
8. Evaluate range and line of sight.
9. Produce pairwise link results.
10. Intersect time windows and calculate forwarding opportunities.

The link matrix evaluates each unique asset pair once.

### 5.2 Real DEM adapter

File:

`backend/communications/site_surface_links.py`

This module connects the surface-link engine to the existing terrain subsystem.

It:

- Validates asset definitions.
- Supports rover and lander asset types.
- Applies default antenna heights.
- Supports custom antenna heights.
- Calculates a terrain-window centre.
- Handles longitude wraparound.
- Loads the required NASA DEM terrain window.
- Passes the terrain and asset information into the link matrix.

Default antenna heights:

| Asset | Antenna height |
|---|---:|
| Lander | 3.0 m |
| Rover | 1.5 m |

### 5.3 Power and opportunity composition

File:

`backend/communications/surface_opportunities.py`

This module combines surface-link availability, electrical power availability, and Earth communication windows.

Its main functions are:

- `power_eligible_windows`
- `compose_surface_opportunities`

A surface uplink requires:

1. A usable static surface link.
2. An eligible rover power interval.
3. An eligible lander power interval.
4. A common time interval between the two power windows.

The lander must subsequently have a suitable Earth communication window.

### 5.4 Energy timeline integration

File:

`backend/energy/site_energy.py`

The existing energy timeline was extended to expose interval-level unmet electrical demand in its samples.

New field:

`unmet_load_wh_since_previous_sample`

The first sample has zero unmet load because it represents the initial battery state and has no preceding simulation interval.

For later samples, the field reports the unmet load from the preceding battery simulation interval.

This makes it possible for the communication scheduler to distinguish a battery that is temporarily unable to meet demand from one that is genuinely eligible for communication.

### 5.5 API integration

File:

`backend/communications/routes.py`

New endpoint:

`POST /communications/surface-links`

The endpoint accepts surface assets and radio-link settings.

It validates the request and returns:

- Asset count.
- Link count.
- Radio settings.
- Terrain source.
- Pairwise surface-link results.
- Range status.
- Line-of-sight status.
- Fresnel status.
- Minimum clearance.
- Link usability.

Invalid requests return HTTP 422.

Missing DEM resources return HTTP 503.

Duplicate asset names are rejected.

### 5.6 End-to-end simulation

File:

`scripts/phase12_end_to_end.py`

This script executes the complete integration workflow:

1. Evaluate the real NASA DEM surface link.
2. Simulate lander energy availability.
3. Simulate rover energy availability.
4. Calculate lander-to-Earth communication windows.
5. Intersect rover and lander power windows.
6. Apply the surface-link usability condition.
7. Calculate store-and-forward opportunities.
8. Export the complete engineering result.

Output:

`docs/phase12_results/phase12_end_to_end.json`

---

## 6. Power Eligibility and Battery Behaviour

The scheduler uses the following power-eligibility conditions:

1. Battery SOC must be greater than zero.
2. Battery SOC must not be below the configured minimum.
3. Unmet load during the preceding sample interval must equal zero.

The exported rule is:

`battery_soc > 0, below_minimum_soc is false, and preceding_interval_unmet_load_wh == 0`

This is a scheduling assumption.

It does not represent an automatic hardware shutdown controller or a load-shedding implementation.

### Conservative interval treatment

Energy is sampled every 30 minutes in the end-to-end scenario.

When an interval ends with unmet load, the scheduler conservatively excludes that interval rather than assuming communication remained possible throughout it.

This avoids claiming uninterrupted communication eligibility during an interval in which the electrical model reports unmet demand.

### Battery simulation assumptions

| Parameter | Lander | Rover |
|---|---:|---:|
| Battery capacity | 2,000 Wh | 400 Wh |
| Initial SOC | 80% | 80% |
| Minimum SOC | 20% | 20% |
| Base electrical load | 60 W | 20 W |
| Solar panel area | 3.0 m² | 0.8 m² |
| Panel efficiency | 28% | 28% |
| Dust loss | 5% | 5% |
| Panel configuration | Tracking | Tracking |

Both assets use a 95% battery charge efficiency and 95% discharge efficiency.

These are simulation assumptions, not verified specifications for actual flight hardware.

---

## 7. Store-and-Forward Scheduling

The rover transmits data to the lander when a usable surface link and common power window are available.

The lander stores the received data until an Earth communication window becomes available.

The default forwarding constraints are:

| Parameter | Default |
|---|---:|
| Maximum wait for Earth window | 12 hours |
| Minimum forwarding duration | 5 minutes |
| Maximum surface radio range | 10 km |
| Surface radio frequency | 401.5 MHz |

If an Earth window overlaps the end of an uplink, the waiting time is zero.

If the next Earth window starts after the uplink, the scheduler calculates the wait from the uplink end.

A forwarding opportunity is accepted only if:

- The Earth window starts within the configured maximum wait.
- Sufficient Earth-window time remains.
- The remaining time meets the minimum forwarding duration.

The scheduler does not create forwarding opportunities when the surface link is unusable.

---

## 8. End-to-End Simulation Configuration

The real integration scenario used the following configuration.

| Parameter | Value |
|---|---:|
| Start time | 2026-11-15 00:00 UTC |
| Duration | 14 days |
| Energy sample interval | 30 minutes |
| Earth-link sample interval | 5 minutes |
| Energy horizon range | 100 km |
| Earth horizon range | 40 km |
| Earth horizon azimuth step | 0.5 degrees |
| Earth disc samples | 400 |
| Surface radio frequency | 401.5 MHz |
| Surface maximum range | 10 km |
| Surface path sample step | 40 m |
| Minimum terrain clearance | 0 m |
| Minimum Fresnel ratio | 0.0 |
| Maximum forwarding wait | 12 hours |
| Minimum forwarding time | 5 minutes |

### Asset locations

| Asset | Latitude | Longitude | Antenna height |
|---|---:|---:|---:|
| Malapert Lander | -85.99° | 0.12° | 3.0 m |
| Rover 01 | -86.00° | 0.12° | 1.5 m |

---

## 9. Real NASA DEM Surface-Link Results

The real terrain integration produced the following result.

| Metric | Result |
|---|---:|
| Surface distance | 303.23 m |
| Slant radio range | 305.26 m |
| Range requirement | Passed |
| Terrain line of sight | Failed |
| Minimum terrain clearance | -6.43 m |
| Location of minimum clearance | 113.71 m from lander |
| Minimum Fresnel clearance ratio | -0.8833 |
| Terrain data complete | Yes |
| Surface link usable | No |

### Interpretation

The rover and lander are geographically close.

The slant range is also far below the configured 10 km maximum.

However, the terrain rises approximately 6.43 m above the radio chord at the most obstructed point.

The radio path therefore fails the line-of-sight requirement.

The negative Fresnel ratio also indicates substantial intrusion into the first Fresnel zone.

The model correctly marks the surface link unusable.

This result demonstrates why a distance-only communication model is insufficient for lunar surface planning.

The negative result is not a software test failure. It is the physical result predicted by the configured terrain model.

---

## 10. Energy Simulation Results

Both energy simulations produced 673 samples over the 14-day period.

### Lander

| Metric | Result |
|---|---:|
| Battery capacity | 2,000 Wh |
| Initial SOC | 80% |
| Final SOC | 100% |
| Minimum observed SOC | 0% |
| Total generated energy | 271,670.63 Wh |
| Total stored energy | Approximately 2,000 Wh |
| Total drawn energy | 1,520 Wh |
| Total wasted energy | 254,623.49 Wh |
| Total unmet load | 3,698.12 Wh |
| Battery depleted during simulation | Yes |
| Below minimum SOC during simulation | Yes |
| Power-eligible window count | 2 |

### Rover

| Metric | Result |
|---|---:|
| Battery capacity | 400 Wh |
| Initial SOC | 80% |
| Final SOC | 100% |
| Minimum observed SOC | 0% |
| Total generated energy | 10,815.70 Wh |
| Total stored energy | 400 Wh |
| Total drawn energy | 304 Wh |
| Total wasted energy | 9,539.89 Wh |
| Total unmet load | 5,561.24 Wh |
| Battery depleted during simulation | Yes |
| Below minimum SOC during simulation | Yes |
| Power-eligible window count | 2 |

### Interpretation

Both assets experienced battery depletion and unmet electrical demand.

Their final SOC nevertheless returned to 100% because the simulation includes later solar generation and battery recharge.

A final SOC of 100% must not be interpreted as continuous power availability throughout the simulation.

The scheduler therefore evaluates individual power-eligible intervals rather than relying only on final battery state.

---

## 11. Lander-to-Earth Communication Results

The lander-to-Earth analysis used the existing terrain-aware direct-to-Earth communication subsystem.

The integration reused:

- Existing lunar and Earth geometry.
- SPICE-based ephemeris calculations.
- Terrain horizon modelling.
- Antenna configuration.
- Direct-link constraints.
- Communication-window construction and refinement.

Simulation output:

| Metric | Result |
|---|---:|
| Earth visibility samples | 4,033 |
| Accepted Earth windows | 1 |
| Rejected windows | 0 |
| Reported availability in simulated period | 100% |
| Total simulated period | 336 hours |

The single reported window spans the entire simulated interval and is marked as clipped at both period boundaries.

This means the model reports continuous qualifying availability within the simulated 14-day interval.

It does not prove that the Earth link remains continuously available before or after that interval.

---

## 12. End-to-End Communication Result

The final scheduler output was:

| Metric | Result |
|---|---:|
| Surface link usable | No |
| Rover power windows | 2 |
| Lander power windows | 2 |
| Common power windows | 2 |
| Surface uplink windows | 0 |
| End-to-end forwarding opportunities | 0 |

The decisive constraint is the terrain-blocked rover-to-lander radio path.

Even though the energy model identifies common power-eligible windows and the Earth-link model identifies an accepted communication window, the scheduler cannot create a rover uplink without a usable surface link.

This is the intended conservative behaviour.

---

## 13. Testing and Validation

### Phase 12 test coverage

The Phase 12 test group contains 43 tests.

| Test module | Tests passed |
|---|---:|
| `test_phase12_adapter.py` | 10 |
| `test_phase12_api.py` | 4 |
| `test_phase12_surface_links.py` | 15 |
| `test_phase12_surface_opportunities.py` | 14 |
| **Total** | **43** |

Coverage includes:

- Great-circle path generation.
- Lunar curvature and radio horizon.
- Antenna-height effects.
- Symmetry of link calculations.
- Terrain obstruction.
- Fresnel and range thresholds.
- Missing and incomplete terrain.
- Asset validation.
- Longitude wraparound.
- API request validation.
- DEM error handling.
- Power-window extraction.
- Battery SOC validation.
- Unmet-load validation.
- Common power-window intersections.
- Store-and-forward timing.
- Maximum forwarding wait.
- Minimum forwarding duration.

### Full project regression test

The complete test suite was executed after Phase 12 implementation.

**Final result:**

- Total tests collected: 284
- Passed: 284
- Failed: 0
- Warnings: 1
- Runtime: approximately 170.94 seconds

The warning is an existing Starlette/httpx test-client deprecation warning. It did not cause any test failure.

All tests from the existing project phases and all 43 Phase 12 tests passed.

---

## 14. API Behaviour

The new endpoint is:

`POST /communications/surface-links`

It supports:

- Two or more surface assets.
- Rover and lander asset types.
- Asset latitude and longitude.
- Optional antenna heights.
- Radio frequency.
- Maximum radio range.
- Minimum terrain clearance.
- Minimum Fresnel ratio.
- Terrain sampling step.
- Terrain-window margin.

The request model limits the number of assets to 20.

Invalid inputs are rejected through FastAPI/Pydantic validation.

Duplicate names are rejected after whitespace normalization.

Missing DEM resources are reported as service-unavailable errors.

The API returns a structured result containing all calculated pairwise links.

---

## 15. Assumptions and Limitations

The following limitations must be considered when interpreting Phase 12 results.

### Terrain resolution

The source DEM has approximately 80 m resolution.

The 40 m path-sampling interval does not improve the source dataset's true spatial resolution.

Small geological features may be missing.

### Static assets

Rover and lander positions remain fixed in Version 1.

Rover movement, route planning, changing antenna orientation, and dynamic obstruction are not yet modelled.

### Radio propagation

The model evaluates geometric terrain obstruction and first Fresnel-zone clearance.

It does not fully simulate:

- Radio-frequency interference.
- Antenna radiation patterns.
- Polarization mismatch.
- Receiver noise figure.
- Link budget and received signal strength.
- Atmospheric or plasma propagation effects.
- Multipath propagation.
- Detailed hardware performance.

### Electrical power

The battery model calculates energy generation, storage, discharge, and unmet load.

The scheduler's power-eligibility conditions are conservative scheduling assumptions.

They do not implement actual hardware shutdown, load shedding, or communication load consumption.

### Earth communication

Earth communication availability is calculated using the existing project model and its configured antenna and link constraints.

The reported 100% availability is limited to the selected 14-day simulation interval.

### Hardware assumptions

Antenna heights, solar panel parameters, battery capacities, loads, and radio frequency are engineering simulation inputs.

They are not verified specifications for a selected flight system.

---

## 16. Future Development Opportunities

Potential improvements for subsequent phases include:

1. Dynamic rover trajectories and time-dependent surface links.
2. Terrain-aware rover route planning.
3. Higher-resolution terrain data where available.
4. Radio link-budget calculations.
5. Antenna gain and orientation modelling.
6. Communication energy consumption added to battery simulation.
7. Battery-aware transmission scheduling.
8. Data volume, transmission rate, and buffer-capacity modelling.
9. Multiple rovers and multiple landers.
10. Network-level communication routing.
11. Relay selection and fault-tolerant store-and-forward scheduling.
12. Uncertainty analysis for terrain and radio propagation.

These are future development opportunities and are not claimed as completed Phase 12 functionality.

---

## 17. Phase 12 Deliverables

| Deliverable | File |
|---|---|
| Surface-link engine | `backend/communications/surface_links.py` |
| Real DEM adapter | `backend/communications/site_surface_links.py` |
| Opportunity scheduler | `backend/communications/surface_opportunities.py` |
| Communication API | `backend/communications/routes.py` |
| Energy timeline extension | `backend/energy/site_energy.py` |
| End-to-end script | `scripts/phase12_end_to_end.py` |
| Surface-link tests | `tests/test_phase12_surface_links.py` |
| Adapter tests | `tests/test_phase12_adapter.py` |
| API tests | `tests/test_phase12_api.py` |
| Opportunity tests | `tests/test_phase12_surface_opportunities.py` |
| Machine-readable results | `docs/phase12_results/phase12_end_to_end.json` |
| Technical report | `docs/phase12_results/phase12_technical_report.md` |

---

## 18. Final Conclusion

Phase 12 successfully implements terrain-aware communication between stationary lunar surface assets and integrates it with electrical power availability and lander-to-Earth communication windows.

The implementation uses the project's spherical lunar geometry, NASA LOLA terrain data, battery simulation, SPICE-based geometry, existing communication constraints, and window-scheduling infrastructure.

The real Malapert demonstration found that the rover-to-lander radio path is obstructed despite the short separation between the assets.

The scheduler correctly rejects the link and produces no uplink or forwarding opportunities.

All 43 Phase 12 tests passed, and the complete project regression suite passed all 284 tests.

The phase therefore delivers a tested surface-link model, a real-terrain integration, an API endpoint, an end-to-end scheduling workflow, and a reproducible engineering result.

**Phase 12 implementation and validation are complete. Git commit and remote repository verification are tracked separately from this technical completion status.**
