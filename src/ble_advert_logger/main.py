import argparse
import asyncio
import time
from datetime import datetime, timezone

from bleak.exc import BleakDBusError
from bleak import BleakScanner

from .config import get_device_info, load_config, normalize_mac
from .decoders import bytes_to_hex, decode_service_data
from .sinks import append_jsonl, atomic_write_json


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def manufacturer_data_to_json(manufacturer_data):
    result = {}

    for key, value in (manufacturer_data or {}).items():
        result[str(key)] = bytes_to_hex(value)

    return result


def make_base_row(device, adv, config):
    mac = normalize_mac(device.address)
    device_info = get_device_info(config, mac)

    return {
        "ts": utc_now(),
        "seen_epoch": time.time(),
        "mac": mac,
        "label": device_info.get("label", ""),
        "name": adv.local_name or device.name or "",
        "rssi": getattr(adv, "rssi", None),
        "service_uuids": list(adv.service_uuids or []),
        "manufacturer_data": manufacturer_data_to_json(adv.manufacturer_data),
    }


def should_log_plain_advert(mac, service_data, config):
    policy = config.get("logging_policy") or {}

    if policy.get("log_all_adverts", False):
        return True

    if service_data:
        return False

    device_info = get_device_info(config, mac)

    if device_info and policy.get("log_known_devices_without_service_data", True):
        return True

    return False


def handle_advert(device, adv, config, latest):
    log_config = config.get("log") or {}
    policy = config.get("logging_policy") or {}
    decoder_config = ((config.get("decoders") or {}).get("service_data")) or {}

    jsonl_path = log_config.get("jsonl_path", "/data/events.jsonl")
    latest_path = log_config.get("latest_path", "/data/latest.json")
    write_stdout = bool(log_config.get("stdout", True))

    mac = normalize_mac(device.address)
    service_data = adv.service_data or {}

    rows = []

    for uuid, raw in service_data.items():
        uuid = uuid.lower()

        decoded = decode_service_data(uuid, raw, decoder_config)

        if not decoded and not policy.get("log_unknown_service_data", True):
            continue

        row = make_base_row(device, adv, config)
        row.update({
            "event_type": "service_data",
            "service_uuid": uuid,
            "raw_hex": bytes_to_hex(raw),
        })
        row.update(decoded)

        rows.append(row)

    if not rows and should_log_plain_advert(mac, service_data, config):
        row = make_base_row(device, adv, config)
        row.update({
            "event_type": "advertisement",
        })
        rows.append(row)

    for row in rows:
        latest_key = row["mac"]

        if row.get("service_uuid"):
            latest_key = f"{row['mac']} {row['service_uuid']}"

        latest[latest_key] = row

        append_jsonl(jsonl_path, row)
        atomic_write_json(latest_path, latest)

        if write_stdout:
            print(row, flush=True)


async def run(args):
    config = load_config(args.config)
    latest = {}

    adapter = config.get("adapter") or "hci0"

    def callback(device, adv):
        handle_advert(device, adv, config, latest)

    scanner = BleakScanner(
        callback,
        adapter=adapter,
    )

    print(f"Starting BLE scan on adapter {adapter}", flush=True)

    scanner_started = False

    try:
        await scanner.start()
        scanner_started = True

        if args.duration > 0:
            await asyncio.sleep(args.duration)
        else:
            while True:
                await asyncio.sleep(3600)

    except KeyboardInterrupt:
        print("Interrupted", flush=True)

    finally:
        if scanner_started:
            try:
                await scanner.stop()
            except BleakDBusError as e:
                print(f"Warning: scanner.stop failed: {e}", flush=True)

        print("Stopped BLE scan", flush=True)

def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="/config/config.yml",
        help="Path to YAML config file",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=0,
        help="Scan duration in seconds. 0 means forever.",
    )

    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    cli()
