import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from .settings import get_settings

# Values the converter expects but that the essential config.json may omit
DEFAULTS = {
    "loop_limit": 10,
    "debug": False,
    "show_stats": False,
    "convert_cs": True,
    "perform_alt_classes": False,
    "alt_classes_folder": None,
    "new_mm_file": "_new-data.xlsx",
    "frame_map": {},
    "radi_map": {"R": "Rearranging", "A": "Augmenting", "D": "Decreasing", "I": "Identifying"},
    "error_reporting": {"meanings": True, "microroles": True, "frames": True},
    "sets": {},
    "languages": [],
}


def load_app_config(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    base_folder = data.get("base_folder", "")
    for key, value in data.items():
        if isinstance(value, str):
            data[key] = value.replace("$BASE", base_folder)

    config = deepcopy(DEFAULTS)
    config.update(data)
    config["rename_columns"] = {"a": {}, "e": {}, "mr": {}, **data.get("rename_columns", {})}

    for key in ("input_folder", "excel_folder"):
        if not config.get(key):
            raise ValueError(f"'{key}' is missing from {path}")
    return config


@lru_cache
def get_app_config():
    return load_app_config(Path(get_settings().config_file).expanduser())
