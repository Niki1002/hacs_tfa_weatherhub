"""Base entity for TFA weatherhub."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_MODELS, DOMAIN, MANUFACTURER
from .coordinator import WeatherhubCoordinator


class WeatherhubEntity(CoordinatorEntity[WeatherhubCoordinator]):
    """Common base for all weatherhub entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: WeatherhubCoordinator, device_id: str, key: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer=MANUFACTURER,
            model=DEVICE_MODELS.get(device_id[:2], f"Sensor (Typ {device_id[:2]})"),
            name=f"weatherhub {DEVICE_MODELS.get(device_id[:2], 'Sensor')} {device_id}",
            serial_number=device_id,
        )

    @property
    def device_data(self) -> dict[str, Any] | None:
        """Raw API data of this device."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._device_id)

    @property
    def measurement(self) -> dict[str, Any]:
        """The latest measurement block of this device."""
        data = self.device_data or {}
        return data.get("measurement") or {}

    @property
    def available(self) -> bool:
        return super().available and self.device_data is not None
