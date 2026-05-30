docker run -d \
  --name ble-advert-logger \
  --restart unless-stopped \
  --security-opt label=disable \
  -v /run/dbus/system_bus_socket:/run/dbus/system_bus_socket:ro \
  -v "$PWD/config:/config:ro" \
  -v "$PWD/data:/data" \
  ble-advert-logger:latest
