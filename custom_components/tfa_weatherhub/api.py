"""Minimal async client for the Mobile Alerts / weatherhub REST API."""

from __future__ import annotations

import asyncio
import re
from typing import Any

import aiohttp

from .const import API_URL

DEVICE_ID_RE = re.compile(r"^[0-9A-F]{12}$")
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)


class WeatherhubError(Exception):
    """Generic API error."""


class WeatherhubConnectionError(WeatherhubError):
    """Cloud not reachable."""


class WeatherhubApiError(WeatherhubError):
    """The API answered with an error."""


def normalize_device_ids(raw: str | list[str]) -> list[str]:
    """Turn user input into a list of upper case device IDs.

    Raises ValueError for IDs that are not 12 hex digits.
    """
    if isinstance(raw, str):
        parts = re.split(r"[\s,;]+", raw)
    else:
        parts = list(raw)
    ids: list[str] = []
    for part in parts:
        dev_id = part.strip().replace("-", "").replace(" ", "").upper()
        if not dev_id:
            continue
        if not DEVICE_ID_RE.match(dev_id):
            raise ValueError(dev_id)
        if dev_id not in ids:
            ids.append(dev_id)
    return ids


class WeatherhubApi:
    """Client for https://www.data199.com/api/pv1/device/lastmeasurement."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def async_get_last_measurements(
        self, device_ids: list[str], phone_id: str | None = None
    ) -> dict[str, dict[str, Any]]:
        """Return the latest measurement per device ID."""
        if not device_ids:
            return {}
        payload = {"deviceids": ",".join(device_ids)}
        if phone_id:
            payload["phoneid"] = phone_id

        try:
            async with self._session.post(
                API_URL, data=payload, timeout=REQUEST_TIMEOUT
            ) as resp:
                if resp.status == 429:
                    raise WeatherhubApiError("Rate limit exceeded (HTTP 429)")
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise WeatherhubConnectionError(str(err)) from err
        except ValueError as err:  # invalid JSON
            raise WeatherhubApiError(f"Invalid response: {err}") from err

        if not isinstance(data, dict) or not data.get("success", False):
            code = data.get("errorcode") if isinstance(data, dict) else None
            msg = data.get("errormessage") if isinstance(data, dict) else None
            raise WeatherhubApiError(f"API error {code}: {msg}")

        result: dict[str, dict[str, Any]] = {}
        for device in data.get("devices") or []:
            dev_id = str(device.get("deviceid", "")).upper()
            if dev_id:
                result[dev_id] = device
        return result
