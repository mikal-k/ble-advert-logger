import argparse
import asyncio
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

from bleak.exc import BleakBluetoothNotAvailableError, BleakDBusError
from bleak import BleakScanner

from .config import get_device_info, load_config, normalize_mac
from .decoders import bytes_to_hex, decode_service_data
from .sinks import append_jsonl, atomic_write_json


class BlueZAccessError(RuntimeError):
    pass


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
    check_output_paths(config)
    latest = {}

    adapter = config.get("adapter") or "hci0"

    def callback(device, adv):
        handle_advert(device, adv, config, latest)

    scanner = BleakScanner(
        callback,
        adapter=adapter,
    )

    dbus_socket = Path("/run/dbus/system_bus_socket")
    if not dbus_socket.exists():
        raise BlueZAccessError(
            "BlueZ system D-Bus socket not found: "
            "/run/dbus/system_bus_socket"
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

def check_output_paths(config):
    log_config = config.get("log") or {}

    for key in ("jsonl_path", "latest_path"):
        path = Path(log_config.get(key, ""))
        parent = path.parent

        if not parent.exists():
            raise FileNotFoundError(
                f"Output directory does not exist: {parent}. "
                "Mount or create the data directory first."
            )

        if not parent.is_dir():
            raise NotADirectoryError(
                f"Output parent is not a directory: {parent}"
            )

        test_file = parent / ".ble-advert-logger-write-test"

        try:
            test_file.write_text("ok\n", encoding="utf-8")
            test_file.unlink()
        except PermissionError:
            raise PermissionError(
                f"Output directory is not writable: {parent}"
            )


def print_startup_error(message):
    print(f"ERROR: {message}", file=sys.stderr)


def print_bluez_help(exc):
    print_startup_error("Could not access BlueZ over system D-Bus.")
    print("", file=sys.stderr)
    print("Common causes:", file=sys.stderr)
    print("- bluetooth.service is not running on the host", file=sys.stderr)
    print("- /run/dbus/system_bus_socket is not mounted into the container",
          file=sys.stderr)
    print("- the container is running rootless and D-Bus rejected auth",
          file=sys.stderr)
    print("- the Bluetooth adapter is blocked or unavailable", file=sys.stderr)
    print("", file=sys.stderr)
    print("Try rootful Podman/Quadlet first.", file=sys.stderr)
    print(f"Details: {exc}", file=sys.stderr)

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

    try:
        asyncio.run(run(args))
    except FileNotFoundError as exc:
        print_startup_error(exc)
        print("Hint: mount config as /config/config.yml and data as /data.",
              file=sys.stderr)
        return 2
    except NotADirectoryError as exc:
        print_startup_error(exc)
        return 2
    except PermissionError as exc:
        print_startup_error(exc)
        print("Hint: check ownership/permissions on the mounted data directory.",
              file=sys.stderr)
        return 2
    except BlueZAccessError as exc:
        print_bluez_help(exc)
        return 2
    except BleakBluetoothNotAvailableError as exc:
        print_bluez_help(exc)
        return 2
    except BleakDBusError as exc:
        print_bluez_help(exc)
        return 2
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130

    return 0



if __name__ == "__main__":
    cli()
