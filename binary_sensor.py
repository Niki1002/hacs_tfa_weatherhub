"""Binary sensor platform (battery state) for TFA weatherhub."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import WeatherhubConfigEntry
from .entity import WeatherhubEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WeatherhubConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        WeatherhubBatterySensor(coordinator, device_id)
        for device_id in coordinator.device_ids
        if device_id in (coordinator.data or {})
    )


class WeatherhubBatterySensor(WeatherhubEntity, BinarySensorEntity):
    """On when the transmitter reports a low battery."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "low_battery")

    @property
    def is_on(self) -> bool | None:
        data = self.device_data or {}
        if "lowbattery" in data:
            return bool(data["lowbattery"])
        if "lb" in self.measurement:
            return bool(self.measurement["lb"])
        return None
