
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.schemas import AssetPick
from backend.energy.solar_power import PanelConfig
from backend.energy.battery import BatteryConfig


class SchedulingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SchedulingAsset(AssetPick):
    """Physical and energy configuration for a lunar surface asset."""

    model_config = ConfigDict(extra="forbid")

    latitude_deg: float = Field(ge=-90, le=90)
    longitude_deg: float = Field(ge=-180, le=180)
    height_m: float

    antenna_height_m: float = Field(default=2.0, ge=0)

    panel_config: PanelConfig
    battery_config: BatteryConfig

    base_load_w: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_asset(self):
        values = (
            self.height_m,
            self.latitude_deg,
            self.longitude_deg,
            self.antenna_height_m,
            self.base_load_w,
        )

        if not all(math.isfinite(value) for value in values):
            raise ValueError("Asset physical parameters must be finite.")

        if not self.name.strip() or not self.location_id.strip():
            raise ValueError("Asset name and location ID cannot be empty.")

        return self


class TimeWindow(SchedulingModel):
    start_s: float
    end_s: float

    @model_validator(mode="after")
    def validate_interval(self):
        if not math.isfinite(self.start_s) or not math.isfinite(self.end_s):
            raise ValueError("Window times must be finite.")

        if self.end_s <= self.start_s:
            raise ValueError("Window end must be after its start.")

        return self


class LinkProfile(SchedulingModel):
    link_id: str = Field(min_length=1, max_length=100)
    link_type: Literal["surface", "earth"]

    source_asset: str = Field(min_length=1, max_length=100)
    destination_asset: str = Field(min_length=1, max_length=100)

    data_rate_bps: float = Field(gt=0)
    radio_power_w: float = Field(ge=0)

    data_rate_source: str = Field(min_length=1)
    radio_power_source: str = Field(min_length=1)

    # Endpoint-specific power for real battery calculations.
    # Both values and their provenance must be supplied together.
    source_radio_power_w: float | None = Field(default=None, ge=0)
    destination_radio_power_w: float | None = Field(default=None, ge=0)

    source_radio_power_source: str | None = None
    destination_radio_power_source: str | None = None

    resource_ids: list[str] = Field(min_length=1)
    windows: list[TimeWindow] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_link(self):
        if not math.isfinite(self.data_rate_bps):
            raise ValueError("Data rate must be finite.")

        if not math.isfinite(self.radio_power_w):
            raise ValueError("Radio power must be finite.")

        endpoint_values = (
            self.source_radio_power_w,
            self.destination_radio_power_w,
            self.source_radio_power_source,
            self.destination_radio_power_source,
        )

        if any(value is not None for value in endpoint_values):
            if any(value is None for value in endpoint_values):
                raise ValueError(
                    "Both endpoint radio powers and their provenance "
                    "must be supplied together."
                )

            if not self.source_radio_power_source.strip():
                raise ValueError("Source radio power provenance is empty.")

            if not self.destination_radio_power_source.strip():
                raise ValueError(
                    "Destination radio power provenance is empty."
                )

            if not math.isfinite(self.source_radio_power_w):
                raise ValueError("Source radio power must be finite.")

            if not math.isfinite(self.destination_radio_power_w):
                raise ValueError("Destination radio power must be finite.")

        if any(not item.strip() for item in self.resource_ids):
            raise ValueError("Resource identifiers cannot be empty.")

        if len(self.resource_ids) != len(set(self.resource_ids)):
            raise ValueError("Resource identifiers must be unique per link.")

        return self


class TransmissionTask(SchedulingModel):
    task_id: str = Field(min_length=1, max_length=100)

    data_volume_bytes: int = Field(gt=0)

    release_time_s: float
    deadline_s: float

    priority: float = Field(default=1.0, gt=0)

    # One link: direct Earth transmission.
    # Two links: rover -> lander -> Earth.
    route_link_ids: list[str] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def validate_task(self):
        if not math.isfinite(self.release_time_s):
            raise ValueError("Release time must be finite.")

        if not math.isfinite(self.deadline_s):
            raise ValueError("Deadline must be finite.")

        if self.deadline_s <= self.release_time_s:
            raise ValueError("Deadline must be after release time.")

        if len(self.route_link_ids) != len(set(self.route_link_ids)):
            raise ValueError("A task route cannot repeat a link.")

        return self


class SchedulingProblem(SchedulingModel):
    horizon_start_s: float
    horizon_end_s: float

    candidate_step_s: float = Field(default=60.0, gt=0)

    assets: list[SchedulingAsset] = Field(default_factory=list)

    links: list[LinkProfile] = Field(min_length=1)
    tasks: list[TransmissionTask] = Field(min_length=1)

    # Environmental sunlight information is kept separate from
    # battery-safe transmission availability.
    sunlight_windows: list[TimeWindow] = Field(default_factory=list)

    max_exact_candidates: int = Field(default=5000, ge=1)

    @model_validator(mode="after")
    def validate_problem(self):
        if not math.isfinite(self.horizon_start_s):
            raise ValueError("Scheduling horizon start must be finite.")

        if not math.isfinite(self.horizon_end_s):
            raise ValueError("Scheduling horizon end must be finite.")

        if self.horizon_end_s <= self.horizon_start_s:
            raise ValueError("Scheduling horizon end must be after start.")

        if not math.isfinite(self.candidate_step_s):
            raise ValueError("Candidate step must be finite.")

        asset_names = [asset.name for asset in self.assets]

        if len(asset_names) != len(set(asset_names)):
            raise ValueError("Asset names must be unique.")

        link_ids = [link.link_id for link in self.links]
        task_ids = [task.task_id for task in self.tasks]

        if len(link_ids) != len(set(link_ids)):
            raise ValueError("Link identifiers must be unique.")

        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Task identifiers must be unique.")

        link_lookup = {link.link_id: link for link in self.links}

        asset_lookup = {
            asset.name: asset
            for asset in self.assets
        }

        for link in self.links:
            if self.assets:
                if link.source_asset not in asset_lookup:
                    raise ValueError(
                        f"Unknown source asset: {link.source_asset}."
                    )

                if (
                    link.destination_asset != "Earth"
                    and link.destination_asset not in asset_lookup
                ):
                    raise ValueError(
                        "Unknown destination asset: "
                        f"{link.destination_asset}."
                    )

        for task in self.tasks:
            current_asset = None

            for index, link_id in enumerate(task.route_link_ids):
                if link_id not in link_lookup:
                    raise ValueError(
                        f"Task {task.task_id} references unknown link {link_id}."
                    )

                link = link_lookup[link_id]

                if index == 0:
                    current_asset = link.source_asset
                elif link.source_asset != current_asset:
                    raise ValueError(
                        f"Task {task.task_id} has a disconnected route."
                    )

                current_asset = link.destination_asset

            if len(task.route_link_ids) == 2:
                first = link_lookup[task.route_link_ids[0]]
                second = link_lookup[task.route_link_ids[1]]

                if first.link_type != "surface" or second.link_type != "earth":
                    raise ValueError(
                        "Two-hop routes must use a surface link followed "
                        "by an Earth link."
                    )

        return self
