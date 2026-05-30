# ble-advert-logger
Bluetooth LE advertisements logger

## Supported:
  Podman Quadlet on Linux/BlueZ       primary
  Podman + systemd service            legacy fallback
  Docker Engine on Linux/BlueZ        best-effort
  Docker Compose on Linux/BlueZ       best-effort

## Not supported initially:
  Docker Desktop macOS/Windows
  Raw HCI passthrough
  Running bluetoothd inside container
