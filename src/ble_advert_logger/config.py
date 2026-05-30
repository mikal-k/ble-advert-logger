from pathlib import Path

import yaml


DEFAULT_CONFIG = {
    "adapter": "hci0",
    "log": {
        "jsonl_path": "/data/events.jsonl",
        "latest_path": "/data/latest.json",
        "stdout": True,
    },
    "logging_policy": {
        "log_all_adverts": False,
        "log_unknown_service_data": True,
        "log_known_devices_without_service_data": True,
    },
    "devices": {},
    "decoders": {
        "service_data": {
            "00002a6e-0000-1000-8000-00805f9b34fb": {
                "type": "temperature_int16_le_centi_celsius",
            },
        },
    },
}


def merge_dicts(base, override):
    result = dict(base)

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value

    return result


def load_config(path):
    path = Path(path)

    with path.open("r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}

    return merge_dicts(DEFAULT_CONFIG, loaded)


def normalize_mac(mac):
    return mac.upper()


def get_device_info(config, mac):
    devices = config.get("devices") or {}
    return devices.get(normalize_mac(mac), {})
