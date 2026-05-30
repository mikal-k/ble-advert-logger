def bytes_to_hex(data):
    return " ".join(f"{b:02x}" for b in data)


def decode_temperature_int16_le_centi_celsius(data):
    if len(data) < 2:
        return {}

    raw_value = int.from_bytes(data[:2], byteorder="little", signed=True)

    return {
        "decoder": "temperature_int16_le_centi_celsius",
        "temperature_c": round(raw_value / 100.0, 2),
    }


def decode_service_data(uuid, data, decoder_config):
    uuid = uuid.lower()
    configured = decoder_config.get(uuid)

    if not configured:
        return {}

    decoder_type = configured.get("type")

    if decoder_type == "temperature_int16_le_centi_celsius":
        return decode_temperature_int16_le_centi_celsius(data)

    return {
        "decoder_error": f"unknown decoder type: {decoder_type}",
    }
