"""Data update coordinator for TFA weatherhub."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WeatherhubApi, WeatherhubError
from .const import CONF_DEVICE_IDS, CONF_PHONE_ID, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type WeatherhubConfigEntry = ConfigEntry[WeatherhubCoordinator]


class WeatherhubCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Fetch all configured devices with a single API call."""

    config_entry: WeatherhubConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: WeatherhubConfigEntry, api: WeatherhubApi
    ) -> None:
        options = {**entry.data, **entry.options}
        minutes = int(options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=minutes),
        )
        self.api = api
        self.device_ids: list[str] = list(options[CONF_DEVICE_IDS])
        self.phone_id: str | None = options.get(CONF_PHONE_ID) or None

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            return await self.api.async_get_last_measurements(
                self.device_ids, self.phone_id
            )
        except WeatherhubError as err:
            raise UpdateFailed(f"Error fetching weatherhub data: {err}") from err
