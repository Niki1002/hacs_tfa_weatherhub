"""Constants for the TFA weatherhub integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "tfa_weatherhub"
MANUFACTURER: Final = "TFA Dostmann"

API_URL: Final = "https://www.data199.com/api/pv1/device/lastmeasurement"

CONF_DEVICE_IDS: Final = "device_ids"
CONF_PHONE_ID: Final = "phone_id"

DEFAULT_SCAN_INTERVAL: Final = 5  # minutes
MIN_SCAN_INTERVAL: Final = 1
MAX_SCAN_INTERVAL: Final = 60
DEFAULT_SCAN_TIMEDELTA: Final = timedelta(minutes=DEFAULT_SCAN_INTERVAL)

# The sensor type is encoded in the first byte of the 12 digit device ID.
DEVICE_MODELS: Final[dict[str, str]] = {
    "01": "Temperatursender",
    "02": "Temperatursender",
    "03": "Thermo-Hygro-Sender",
    "04": "Thermo-Hygro-Sender mit Wassermelder",
    "06": "Thermo-Hygro-Sender mit Pool-Sensor",
    "07": "Wetterstation",
    "08": "Regensender",
    "09": "Thermosender mit Kabelfühler",
    "0B": "Windsender",
    "0E": "Thermo-Hygro-Sender",
    "0F": "Thermosender mit Kabelfühler",
    "11": "Thermo-Hygro-Sender (4 Kanäle)",
    "12": "Thermo-Hygro-Sender",
}

WIND_DIRECTIONS: Final[list[str]] = [
    "n", "nne", "ne", "ene", "e", "ese", "se", "sse",
    "s", "ssw", "sw", "wsw", "w", "wnw", "nw", "nnw",
]
