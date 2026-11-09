
from backend.catalog import LANDERS, ROVERS
from backend.schemas import MissionRequest


def validate_mission(request: MissionRequest):
    errors = []

    config = request.config
    assets = request.assets

    lander_assets = [a for a in assets if a.type == "lander"]
    rover_assets = [a for a in assets if a.type == "rover"]

    if len(lander_assets) != config.landers:
        errors.append("Selected lander count does not match configuration.")

    if len(rover_assets) != config.rovers:
        errors.append("Selected rover count does not match configuration.")

    if len(assets) != len({a.name for a in assets}):
        errors.append("Asset names must be unique.")

    if len(assets) != len({a.location_id for a in assets}):
        errors.append("Asset locations must be unique.")

    valid_lander_ids = {item["id"] for item in LANDERS}
    valid_rover_ids = {item["id"] for item in ROVERS}

    for asset in lander_assets:
        if asset.location_id not in valid_lander_ids:
            errors.append(f"Invalid lander location: {asset.location_id}")

        if asset.assigned_lander is not None:
            errors.append("Landers cannot be assigned to another lander.")

    lander_names = {a.name for a in lander_assets}

    for asset in rover_assets:
        if asset.location_id not in valid_rover_ids:
            errors.append(f"Invalid rover location: {asset.location_id}")

        if asset.assigned_lander not in lander_names:
            errors.append(
                f"Rover {asset.name} must be assigned to a selected lander."
            )

    return {
        "valid": len(errors) == 0,
        "errors": errors
    }
