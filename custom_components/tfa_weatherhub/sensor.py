"""Sensor platform for TFA weatherhub."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    EntityCategory,
    UnitOfPrecipitationDepth,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import WIND_DIRECTIONS
from .coordinator import WeatherhubConfigEntry, WeatherhubCoordinator
from .entity import WeatherhubEntity


def _number(lo: float, hi: float) -> Callable[[Any], float | None]:
    """Return a converter that drops sensor error codes / implausible values."""

    def convert(value: Any) -> float | None:
        try:
            num = float(value)
        except (TypeError, ValueError):
            return None
        return num if lo <= num <= hi else None

    return convert


def _wind_degrees(value: Any) -> float | None:
    try:
        idx = int(value)
    except (TypeError, ValueError):
        return None
    return idx * 22.5 if 0 <= idx < 16 else None


def _wind_cardinal(value: Any) -> str | None:
    try:
        idx = int(value)
    except (TypeError, ValueError):
        return None
    return WIND_DIRECTIONS[idx] if 0 <= idx < 16 else None


def _timestamp(value: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


@dataclass(frozen=True, kw_only=True)
class WeatherhubSensorDescription(SensorEntityDescription):
    """Describes a weatherhub sensor."""

    field: str
    value_fn: Callable[[Any], Any]
    source: str = "measurement"  # "measurement" or "device"


_temp = _number(-60, 100)

SENSORS: tuple[WeatherhubSensorDescription, ...] = (
    WeatherhubSensorDescription(
        key="temperature",
        field="t1",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=_temp,
    ),
    WeatherhubSensorDescription(
        key="temperature_2",
        translation_key="temperature_2",
        field="t2",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=_temp,
    ),
    WeatherhubSensorDescription(
        key="humidity",
        field="h",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=_number(0, 100),
    ),
    WeatherhubSensorDescription(
        key="rain_total",
        translation_key="rain_total",
        field="r",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        suggested_display_precision=1,
        value_fn=_number(0, 1_000_000),
    ),
    WeatherhubSensorDescription(
        key="wind_speed",
        field="ws",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=1,
        value_fn=_number(0, 100),
    ),
    WeatherhubSensorDescription(
        key="wind_gust",
        translation_key="wind_gust",
        field="wg",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=1,
        value_fn=_number(0, 100),
    ),
    WeatherhubSensorDescription(
        key="wind_bearing",
        translation_key="wind_bearing",
        field="wd",
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
        value_fn=_wind_degrees,
    ),
    WeatherhubSensorDescription(
        key="wind_direction",
        translation_key="wind_direction",
        field="wd",
        device_class=SensorDeviceClass.ENUM,
        options=WIND_DIRECTIONS,
        icon="mdi:compass-rose",
        value_fn=_wind_cardinal,
    ),
    WeatherhubSensorDescription(
        key="last_measurement",
        translation_key="last_measurement",
        field="ts",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_timestamp,
    ),
    WeatherhubSensorDescription(
        key="last_seen",
        translation_key="last_seen",
        field="lastseen",
        source="device",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_timestamp,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WeatherhubConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create sensors for every field a device actually reports."""
    coordinator = entry.runtime_data
    entities: list[WeatherhubSensor] = []
    for device_id in coordinator.device_ids:
        device = (coordinator.data or {}).get(device_id)
        if not device:
            continue
        measurement = device.get("measurement") or {}
        for desc in SENSORS:
            source = device if desc.source == "device" else measurement
            if desc.field in source:
                entities.append(WeatherhubSensor(coordinator, device_id, desc))
    async_add_entities(entities)


class WeatherhubSensor(WeatherhubEntity, SensorEntity):
    """A single weatherhub measurement value."""

    entity_description: WeatherhubSensorDescription

    def __init__(
        self,
        coordinator: WeatherhubCoordinator,
        device_id: str,
        description: WeatherhubSensorDescription,
    ) -> None:
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        desc = self.entity_description
        source = self.device_data if desc.source == "device" else self.measurement
        return desc.value_fn((source or {}).get(desc.field))
