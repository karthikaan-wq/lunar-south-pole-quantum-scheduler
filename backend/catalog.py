
LANDERS = [
    {"id": f"L-{i:02d}", "name": f"Lander-{i}", "type": "lander"}
    for i in range(1, 9)
]

ROVERS = [
    {"id": f"R-{i:02d}", "name": f"Rover-{i}", "type": "rover"}
    for i in range(1, 13)
]

def get_catalog():
    return {
        "landers": LANDERS,
        "rovers": ROVERS
    }
