from dataclasses import dataclass
import math

import numpy as np


@dataclass
class BatteryConfig:
    capacity_wh: float = 2000.0
    initial_soc: float = 0.8
    min_soc: float = 0.2
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95

    def __post_init__(self):
        values = {
            "capacity_wh": self.capacity_wh,
            "initial_soc": self.initial_soc,
            "min_soc": self.min_soc,
            "charge_efficiency": self.charge_efficiency,
            "discharge_efficiency": self.discharge_efficiency,
        }

        for name, value in values.items():
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite.")

        if self.capacity_wh <= 0:
            raise ValueError("Battery capacity must be greater than zero.")

        if not 0.0 <= self.initial_soc <= 1.0:
            raise ValueError("Initial SOC must be between 0 and 1.")

        if not 0.0 <= self.min_soc <= 1.0:
            raise ValueError("Minimum SOC must be between 0 and 1.")

        if not 0.0 < self.charge_efficiency <= 1.0:
            raise ValueError("Charge efficiency must be greater than 0 and at most 1.")

        if not 0.0 < self.discharge_efficiency <= 1.0:
            raise ValueError("Discharge efficiency must be greater than 0 and at most 1.")


def step_seconds(times_s):
    """Return the duration represented by each time sample."""
    times = np.asarray(times_s, dtype=float)

    if times.ndim != 1 or len(times) < 2:
        raise ValueError("At least two one-dimensional time samples are required.")

    if not np.all(np.isfinite(times)):
        raise ValueError("Time samples must be finite.")

    differences = np.diff(times)

    if np.any(differences <= 0.0):
        raise ValueError("Time samples must be strictly increasing.")

    return np.append(differences, differences[-1])


def simulate_battery(power_w, load_w, dt_s, config):
    """Simulate battery charging and discharging over time."""
    power = np.asarray(power_w, dtype=float)
    load = np.asarray(load_w, dtype=float)
    dt = np.asarray(dt_s, dtype=float)

    if power.ndim != 1 or load.ndim != 1 or dt.ndim != 1:
        raise ValueError("Power, load and time-step arrays must be one-dimensional.")

    if not (len(power) == len(load) == len(dt)):
        raise ValueError("Power, load and time-step arrays must have equal lengths.")

    if len(power) == 0:
        raise ValueError("At least one simulation sample is required.")

    for name, values in (("power", power), ("load", load), ("dt", dt)):
        if not np.all(np.isfinite(values)):
            raise ValueError(f"{name} values must be finite.")

    if np.any(power < 0.0) or np.any(load < 0.0):
        raise ValueError("Power and load cannot be negative.")

    if np.any(dt <= 0.0):
        raise ValueError("Time steps must be greater than zero.")

    capacity = config.capacity_wh
    energy = capacity * config.initial_soc

    soc = np.empty(len(power), dtype=float)
    stored_wh = np.zeros(len(power), dtype=float)
    drawn_wh = np.zeros(len(power), dtype=float)
    wasted_wh = np.zeros(len(power), dtype=float)
    unmet_load_wh = np.zeros(len(power), dtype=float)

    for i in range(len(power)):
        duration_hours = dt[i] / 3600.0
        surplus_wh = (power[i] - load[i]) * duration_hours

        if surplus_wh >= 0.0:
            potential_stored = surplus_wh * config.charge_efficiency
            available_capacity = capacity - energy

            accepted = min(potential_stored, available_capacity)
            energy += accepted

            stored_wh[i] = accepted
            wasted_wh[i] = surplus_wh - (
                accepted / config.charge_efficiency
            )

        else:
            required_wh = -surplus_wh
            available_draw = energy * config.discharge_efficiency

            delivered = min(required_wh, available_draw)
            energy -= delivered / config.discharge_efficiency

            drawn_wh[i] = delivered
            unmet_load_wh[i] = required_wh - delivered

        energy = min(capacity, max(0.0, energy))
        soc[i] = energy / capacity

    below_minimum = soc < config.min_soc
    depleted = soc <= 1e-12

    return {
        "soc": soc,
        "stored_wh": stored_wh,
        "drawn_wh": drawn_wh,
        "wasted_wh": wasted_wh,
        "unmet_load_wh": unmet_load_wh,
        "below_minimum": below_minimum,
        "depleted": depleted,
        "total_stored_wh": float(np.sum(stored_wh)),
        "total_drawn_wh": float(np.sum(drawn_wh)),
        "total_wasted_wh": float(np.sum(wasted_wh)),
        "total_unmet_load_wh": float(np.sum(unmet_load_wh)),
        "minimum_soc": float(np.min(soc)),
        "final_soc": float(soc[-1]),
    }


def load_profile(times_s, base_w, extra_loads=()):
    """
    Build a load profile.

    Each extra load is a tuple:
        (start_s, end_s, watts)

    Extra load applies for start_s <= time < end_s.
    """
    times = np.asarray(times_s, dtype=float)

    if times.ndim != 1 or not np.all(np.isfinite(times)):
        raise ValueError("Times must be a finite one-dimensional array.")

    if not math.isfinite(base_w) or base_w < 0.0:
        raise ValueError("Base load must be finite and nonnegative.")

    result = np.full(len(times), base_w, dtype=float)

    for start_s, end_s, watts in extra_loads:
        if not all(math.isfinite(v) for v in (start_s, end_s, watts)):
            raise ValueError("Extra-load parameters must be finite.")

        if end_s <= start_s:
            raise ValueError("Extra-load end must be after its start.")

        if watts < 0.0:
            raise ValueError("Extra load cannot be negative.")

        active = (times >= start_s) & (times < end_s)
        result[active] += watts

    return result
