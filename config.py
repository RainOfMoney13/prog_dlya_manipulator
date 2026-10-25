import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UI_FILE = os.path.join(BASE_DIR, "module_B.ui")

SAFETY_LIMITS = {
    "x_min": -0.95, "x_max": 0.95,
    "y_min": -0.95, "y_max": 0.95,
    "z_min": 0.0, "z_max": 1.0,
    "max_speed": 3.0, "max_load": 5.0
}

JOINT_PARAMS = {
    "count": 6,
    "min_angle": -3.14159,
    "max_angle": 3.14159,
    "default_speed": 0.5,
    "names": ["Base", "Shoulder", "Elbow", "Wrist1", "Wrist2", "Wrist3"]
}