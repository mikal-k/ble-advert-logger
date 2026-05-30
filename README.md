# ble-advert-logger

Passive Bluetooth LE advertisement logger for Linux/BlueZ.

The app listens to BLE advertisements through the host BlueZ service over
system D-Bus, decodes known service data, and writes JSON files.

Initial decoder:

* BLE temperature service data
* UUID: `00002a6e-0000-1000-8000-00805f9b34fb`
* Format: signed little-endian int16, centi-degrees Celsius
* Example: `aa 07` -> `19.62 °C`

## Status

Early working prototype.

Confirmed working with:

* Rocky Linux
* BlueZ on the host
* rootful Podman
* host system D-Bus mounted into the container

## Supported runtimes

| Runtime                      | Status                  |
| ---------------------------- | ----------------------- |
| Rootful Podman + Quadlet     | Primary target          |
| Rootful Podman manually      | Supported               |
| Podman systemd service       | Legacy fallback         |
| Docker Engine on Linux/BlueZ | Best effort             |
| Rootless Podman              | Not supported initially |
| Docker Desktop macOS/Windows | Not supported           |

## Host requirements

This is not a self-contained Bluetooth container.

Bluetooth stays on the host:

```text
host bluetoothd + hci0
        |
        | /run/dbus/system_bus_socket
        v
ble-advert-logger container
```

The host must provide:

* working Bluetooth hardware
* running `bluetooth.service`
* `/run/dbus/system_bus_socket` mounted into the container
* config mounted as `/config/config.yml`
* writable data directory mounted as `/data`

Rootless containers may fail with D-Bus errors such as:

```text
authentication failed: REJECTED: ['EXTERNAL']
```

Use rootful Podman/Quadlet first.

## Output

Program logs go to stdout/stderr.

BLE data is written to:

```text
/data/events.jsonl
/data/latest.json
```

Suggested host paths:

```text
/etc/ble-advert-logger/config.yml
/var/lib/ble-advert-logger/events.jsonl
/var/lib/ble-advert-logger/latest.json
```

## Build

```bash
sudo podman build -t localhost/ble-advert-logger:latest .
```

## Quick test

```bash
sudo mkdir -p /etc/ble-advert-logger /var/lib/ble-advert-logger
sudo cp config.example.yml /etc/ble-advert-logger/config.yml
```

```bash
sudo podman run --rm \
  --name ble-advert-logger-test \
  --security-opt label=disable \
  -v /run/dbus/system_bus_socket:/run/dbus/system_bus_socket:ro \
  -v /etc/ble-advert-logger:/config:ro \
  -v /var/lib/ble-advert-logger:/data \
  localhost/ble-advert-logger:latest \
  --config /config/config.yml \
  --duration 60
```

```bash
sudo cat /var/lib/ble-advert-logger/latest.json
```

## Quadlet

```bash
sudo mkdir -p /etc/containers/systemd
sudo cp quadlet/ble-advert-logger.container /etc/containers/systemd/
sudo systemctl daemon-reload
sudo systemctl start ble-advert-logger.service
```

Logs:

```bash
sudo journalctl -u ble-advert-logger.service -f
```

Data:

```bash
sudo tail -f /var/lib/ble-advert-logger/events.jsonl
```

## Example config

```yaml
devices:
  C4:5E:DE:F2:10:62:
    label: hallway_temperature
    notes: "P T 800307"

log:
  jsonl_path: /data/events.jsonl
  latest_path: /data/latest.json
  stdout: false
```

Use `stdout: true` while debugging.

## Current limitations

* JSONL and latest-JSON only
* one built-in decoder so far
* no database sink yet
* no MQTT, Prometheus, or Zabbix output yet
* rootless containers are not supported initially

