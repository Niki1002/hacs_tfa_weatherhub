"""The TFA weatherhub integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WeatherhubApi
from .coordinator import WeatherhubConfigEntry, WeatherhubCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: WeatherhubConfigEntry) -> bool:
    """Set up TFA weatherhub from a config entry."""
    api = WeatherhubApi(async_get_clientsession(hass))
    coordinator = WeatherhubCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WeatherhubConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: WeatherhubConfigEntry) -> None:
    """Reload when the options change."""
    await hass.config_entries.async_reload(entry.entry_id)
