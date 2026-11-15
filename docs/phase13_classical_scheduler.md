# Phase 13 — Classical Scheduler

## Status
Implementation integrated; final regression verification pending.

## API
`POST /api/scheduling/run`

Accepts a `SchedulingProblem` and performs environmental preparation followed by classical scheduling.

## Scheduling pipeline
1. Calculate baseline site energy and battery-eligible intervals.
2. Calculate terrain-aware Earth communication windows.
3. Evaluate static rover–lander surface-link feasibility.
4. Intersect communication opportunities with baseline power-eligible intervals.
5. Generate complete direct-to-Earth and rover–lander–Earth transmission candidates.
6. Run Greedy and Exact scheduling against the same candidate set.
7. Return selected candidates, unscheduled tasks, objective values, environmental summary, and warnings.

## Optimization objective
Maximize the sum of:

`task priority × completed data volume`

Each task can be selected at most once. Overlapping transmissions cannot share a resource. Transmission intervals are half-open, so a transmission may start when another finishes.

## Algorithms
### Greedy
Deterministic heuristic prioritizing higher weighted data volume, earlier completion, earlier start, and stable identifiers. It does not guarantee global optimality.

### Exact
Binary mixed-integer linear optimization using SciPy MILP. It enforces one candidate per task and shared-resource conflict constraints. An exact result is reported only when the solver proves optimality. Candidate and conflict-pair limits prevent uncontrolled problem growth.

Both algorithms receive the same generated candidate set.

## Environmental assumptions and limitations
- Energy windows use baseline site loads and battery eligibility.
- Radio transmission energy is not dynamically simulated for each selected schedule. Therefore, this phase does not claim complete schedule-dependent battery feasibility.
- Surface-link geometry is treated as static over the mission interval.
- Earth communication windows use SPICE geometry and terrain horizon constraints; they are not a complete RF link-budget guarantee.
- Data rates and radio power values must be supplied by the problem configuration and are not inferred from geometry.
- Missing communication windows are represented as empty windows; they do not cause false availability.
- Environmental coverage and data-quality warnings must be reviewed when interpreting results.

## Response interpretation
The API returns Greedy results even when the Exact solver cannot complete or prove optimality. In that case, `exact` is null and `exact_error` explains the reason. A missing Exact result must not be interpreted as an optimal schedule.

## Verification
Final status depends on Phase 13 tests and the full project regression suite.
