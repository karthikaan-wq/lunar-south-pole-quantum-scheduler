
from pydantic import BaseModel, Field
from typing import Literal


class MissionConfig(BaseModel):
    landers: int = Field(ge=1, le=8)
    rovers: int = Field(ge=0, le=12)
    orbiters: int = Field(default=0, ge=0, le=0)

    start_date: str
    start_time: str

    duration_days: int = Field(ge=1, le=30)
    min_elevation_deg: float = Field(ge=0, le=90)
    region: str


class AssetPick(BaseModel):
    name: str
    type: Literal["lander", "rover"]
    location_id: str
    assigned_lander: str | None = None


class MissionRequest(BaseModel):
    config: MissionConfig
    assets: list[AssetPick]
