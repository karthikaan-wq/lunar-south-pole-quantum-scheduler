
from uuid import uuid4

missions = {}
results = {}


def new_id():
    return str(uuid4())


def save_mission(mission_id, mission_data):
    missions[mission_id] = mission_data


def get_mission(mission_id):
    return missions.get(mission_id)


def save_result(result_id, result_data):
    results[result_id] = result_data


def get_result(result_id):
    return results.get(result_id)
