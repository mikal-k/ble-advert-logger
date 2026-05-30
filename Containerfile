FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends dbus \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN pip install --no-cache-dir --root-user-action=ignore .

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["ble-advert-logger"]
CMD ["--config", "/config/config.yml"]
