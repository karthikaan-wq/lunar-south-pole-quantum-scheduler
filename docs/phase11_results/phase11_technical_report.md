# Phase 11 — Lunar Solar Energy and Battery Survival

**Project:** Lunar South Pole Quantum Scheduler
**Phase:** 11
**Simulation period:** 14 November–12 December 2026
**Main duration:** 28 days
**Status:** Implementation, primary experiments, and full test verification completed; Git publication pending.

## 1. Overview

Phase 11 extends the lunar site-analysis system with terrain-aware solar visibility, Earth occultation, solar-panel power generation, battery simulation, sunlight-window extraction, and an energy-timeline API.

Three sites were simulated:
- Floor: -89.73391°, 122.03549°
- Rim: -89.67869°, -163.05292°
- Malapert: -85.99°, 0.12°

Each site was evaluated using two hypothetical asset profiles: a lander and a rover.

## 2. Physical and numerical model

The system samples the solar disc rather than treating the Sun as a point. The assumed solar angular diameter is approximately 0.53°. The default disc sampling uses 400 points.

A sample is classified as sunlit when at least 50% of the solar disc remains visible after terrain and eclipse calculations.

Earth occultation is calculated using apparent angular separation and exact two-circle overlap geometry.

The combined visibility calculation currently uses:

`sun_fraction = terrain_fraction * eclipse_factor`

This is an approximation. It is not an exact joint geometric calculation when terrain and Earth both partially obscure the solar disc.

Solar flux uses 1361 W/m² at 1 AU and an inverse-square distance adjustment. Panel power accounts for panel area, efficiency, orientation, dust loss, degradation, and visible sunlight fraction.

The tracking-panel model follows Sun azimuth but retains the configured panel-normal elevation. It does not model full two-axis tracking, actuator constraints, slew limits, or tracking energy consumption.

At a solar elevation of 1.5°, the incidence factor is approximately 2.62% for a horizontal panel and 99.97% for a vertical panel facing the Sun's azimuth.

## 3. Hypothetical asset assumptions

These profiles are simulation assumptions, not verified specifications of real lunar hardware.

| Parameter | Lander | Rover |
|---|---:|---:|
| Panel type | Tracking | Tracking |
| Panel area | 3.0 m² | 0.8 m² |
| Panel efficiency | 28% | 28% |
| Panel height | 3.0 m | 1.5 m |
| Dust loss | 5% | 5% |
| Battery capacity | 2,000 Wh | 400 Wh |
| Initial SOC | 80% | 80% |
| Minimum SOC warning | 20% | 20% |
| Charge efficiency | 95% | 95% |
| Discharge efficiency | 95% | 95% |
| Base load | 60 W | 20 W |

The minimum SOC is a warning threshold only. Automatic load shedding is not implemented.

## 4. Shared simulation settings

| Setting | Value |
|---|---:|
| Start | 2026-11-14 00:00 UTC |
| Main duration | 28 days |
| Sampling interval | 30 minutes |
| Horizon range | 100 km |
| Horizon azimuth step | 0.25° |
| Solar-disc points | 400 |
| Sunlit threshold | 50% |
| Lunar reference radius | 1,737.4 km |

The local `data/dem` inventory contained only `LDEM_80S_80MPP_ADJ.TIF`, an 80 m/pixel LOLA DEM. No local 20 m or 5 m DEM was found. A higher-resolution Malapert dataset was identified in NASA's archive but was not used in these runs.

The observer height is terrain elevation plus panel height. Negative terrain elevations relative to the lunar reference sphere are allowed when the resulting distance from the lunar centre remains positive.

## 5. Main 28-day results

### Lander

| Measurement | Floor | Rim | Malapert |
|---|---:|---:|---:|
| Sunlit samples | 0% | 75.02% | 67.66% |
| Sunlit hours | 0 | 504 | 455 |
| Generated energy | 0 kWh | 561.865 kWh | 505.852 kWh |
| Final SOC | 0% | 100% | 0% |
| Unmet load | 38.800 kWh | 7.873 kWh | 9.128 kWh |
| Battery depleted | Yes | Yes | Yes |

### Rover

| Measurement | Floor | Rim | Malapert |
|---|---:|---:|---:|
| Sunlit samples | 0% | 72.79% | 64.61% |
| Sunlit hours | 0 | 489 | 434.5 |
| Generated energy | 0 kWh | 145.273 kWh | 128.900 kWh |
| Final SOC | 0% | 100% | 0% |
| Unmet load | 13.136 kWh | 3.191 kWh | 3.908 kWh |
| Battery depleted | Yes | Yes | Yes |

The Floor site had no qualifying sunlight during this sampled period under the 50% visibility threshold.

Rim had the highest sunlight availability in this comparison. Nevertheless, all six simulations reported battery depletion and unmet load.

Rim's final SOC reached 100% despite earlier depletion and unmet load. This shows why final SOC alone cannot establish continuous survival. Minimum SOC, depletion status, and unmet load must also be considered.

## 6. Sunlight windows

The Floor simulations produced no qualifying sunlight windows.

Rim produced two windows for each asset. One was clipped at the simulation start and another at its end. These clipped boundaries are not exact sunrise or sunset times.

Malapert lander window:
- Start: 2026-11-18 18:11:15 UTC
- End: 2026-12-07 17:00:00 UTC
- Duration: approximately 454.8 hours

Malapert rover window:
- Start: 2026-11-18 18:32:48 UTC
- End: 2026-12-06 21:24:22 UTC
- Duration: approximately 434.9 hours

## 7. Panel-height sensitivity

Malapert was simulated for 14 days with panel heights of 1, 2, 3, 5, and 10 metres.

| Height | Sunlit samples | Sunlit hours | Generation | Unmet load |
|---:|---:|---:|---:|---:|
| 1 m | 65.825% | 221.0 | 244.505 kWh | 5,170.90 Wh |
| 2 m | 65.973% | 221.5 | 244.765 kWh | 5,156.14 Wh |
| 3 m | 65.973% | 221.5 | 245.037 kWh | 5,138.12 Wh |
| 5 m | 66.122% | 222.0 | 245.586 kWh | 5,109.51 Wh |
| 10 m | 66.568% | 223.5 | 246.973 kWh | 5,047.22 Wh |

Raising the panel from 1 m to 10 m increased generation by approximately 1.01%. All five cases still experienced battery depletion.

This is a result for the selected site and period, not proof that a 10 m panel is optimal or practical.

## 8. Horizon-resolution sensitivity

| Azimuth step | Directions | Sunlit samples | Generation | Unmet load |
|---:|---:|---:|---:|---:|
| 1.0° | 360 | 65.973% | 245.048 kWh | 5,145.05 Wh |
| 0.5° | 720 | 65.973% | 245.037 kWh | 5,138.12 Wh |
| 0.25° | 1,440 | 65.973% | 245.037 kWh | 5,138.12 Wh |

The 0.5° and 0.25° results are effectively identical for this test. This does not establish that the same resolution is sufficient at every site.

Azimuth sampling density does not increase the underlying 80 m DEM resolution.

## 9. Eclipse verification

SPICE-based tests cover:
- A five-hour interval around 2026-03-03 09:00 UTC at Malapert, detecting lunar-eclipse geometry.
- A 2026-11-14 to 2026-12-12 control interval, which does not report an eclipse.

These are targeted tests, not validation of every lunar eclipse.

## 10. API

New router: `backend/energy/routes.py`

Registered in: `backend/main.py`

Endpoint:

`GET /api/energy/site-timeline`

The endpoint accepts site coordinates, UTC start time, duration, sample interval, panel configuration, battery configuration, load, horizon settings, sunlight threshold, disc sampling count, and sample-inclusion settings.

Invalid parameters return HTTP 422. Missing SPICE kernels or required terrain data return HTTP 503. The endpoint was confirmed in the application's OpenAPI schema and exercised by an integration test.

## 11. Implementation files

- `backend/energy/__init__.py`
- `backend/energy/sun_visibility.py`
- `backend/energy/solar_power.py`
- `backend/energy/battery.py`
- `backend/energy/site_energy.py`
- `backend/energy/routes.py`
- `backend/main.py`
- `backend/physics/earth_samples.py`
- `scripts/phase11_energy.py`
- `scripts/phase11_sensitivity.py`

The Earth-sample geometry was corrected to allow valid negative terrain elevations relative to the lunar reference sphere, while rejecting an observer at or below the lunar centre.

## 12. Generated artifacts

All files are under `docs/phase11_results/`:

- `phase11_all_samples.csv` — detailed time-series data.
- `phase11_battery_survival.png` — battery-survival plot.
- `phase11_results.json` — structured results for all six simulations.
- `phase11_sensitivity.csv` — eight sensitivity runs.
- `phase11_summary.csv` — six simulation summaries.
- `phase11_sunlight_windows.csv` — extracted sunlight windows.

The files were generated and their presence and sizes were checked. The PNG was verified as a valid image. CSV summaries and representative sample rows were inspected.

## 13. Test evidence

Observed test results:

| Test group | Result |
|---|---:|
| Phase 11 energy tests | 26 passed |
| Phase 11 eclipse tests | 2 passed |
| Phase 11 API tests | 5 passed |
| Combined Phase 11 focused tests | 33 passed |
| Phase 5 geometry plus Phase 11 eclipse compatibility | 12 passed |

The combined Phase 11 focused suite passed with 33 tests and zero failures.

A Starlette/httpx deprecation warning appeared in API tests. It did not cause a test failure.

The full project test suite still needs to be run after Phase 11 changes.

## 14. Scientific limitations

1. The local DEM is 80 m/pixel and may omit smaller terrain features.
2. Terrain visibility multiplied by eclipse factor is an approximation, not exact joint partial-disc geometry.
3. Tracking follows Sun azimuth only; panel elevation remains fixed.
4. The model omits slew constraints, actuator energy, and detailed hardware mechanics.
5. Asset and battery profiles are hypothetical.
6. Temperature-dependent battery behaviour, cell-level characteristics, ageing, and detailed power electronics are not modelled.
7. Minimum SOC is a warning only; load shedding is not enforced.
8. Thirty-minute sampling can miss short events.
9. Sunlight-window boundaries are estimated and may be clipped by the simulation interval.
10. A high final SOC does not prove uninterrupted operation.
11. Published long-term illumination statistics are not directly comparable without matching coordinates, dates, terrain, panel height, and definitions.
12. These simulations do not establish flight readiness or guarantee mission survival.

## 15. Overall findings

Phase 11 connects lunar terrain and celestial geometry with a solar generation and battery energy model.

The experiments demonstrate substantial site-to-site differences in illumination, show that storage constraints can cause depletion even where total solar generation is high, and quantify the modest effect of panel height and horizon angular resolution in the tested Malapert interval.

The outputs and API provide a foundation for later work on storage sizing, dynamic load scheduling, improved terrain datasets, and mission-level energy planning.

## 16. Completion checklist

- [x] Solar-disc terrain visibility implementation.
- [x] Earth occultation and eclipse calculation.
- [x] Solar power and panel orientation model.
- [x] Battery simulation and load accounting.
- [x] Site-level energy timeline.
- [x] Phase 11 API route and registration.
- [x] Three-site, two-asset main simulation.
- [x] Panel-height sensitivity experiment.
- [x] Horizon-resolution sensitivity experiment.
- [x] Result CSV, JSON, and PNG artifacts.
- [x] Focused Phase 11 tests.
- [x] Geometry compatibility tests.
- [x] Technical report draft.
- [ ] Final syntax verification.
- [ ] Full project test suite.
- [ ] Git diff and status review.
- [ ] Commit and push.
- [ ] Remote commit verification.

**Current status:** Implementation and primary experiments completed. Final verification and publication remain pending.
