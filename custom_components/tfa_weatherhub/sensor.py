"""Sensor platform for TFA weatherhub."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.util import dt as dt_util

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
    entities: list[SensorEntity] = []
    for device_id in coordinator.device_ids:
        device = (coordinator.data or {}).get(device_id)
        if not device:
            continue
        measurement = device.get("measurement") or {}
        for desc in SENSORS:
            source = device if desc.source == "device" else measurement
            if desc.field in source:
                entities.append(WeatherhubSensor(coordinator, device_id, desc))
        if "r" in measurement:
            entities.append(WeatherhubRainTodaySensor(coordinator, device_id))
        entities.extend(
            WeatherhubHistorySensor(coordinator, device_id, desc)
            for desc in HISTORY_SENSORS
            if desc.field in measurement
        )
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


@dataclass
class RainTodayData(ExtraStoredData):
    """Persisted state of the daily rain counter."""

    baseline: float | None
    last_total: float | None
    day: str | None

    def as_dict(self) -> dict[str, Any]:
        return {"baseline": self.baseline, "last_total": self.last_total, "day": self.day}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RainTodayData:
        return cls(data.get("baseline"), data.get("last_total"), data.get("day"))


class WeatherhubRainTodaySensor(WeatherhubEntity, SensorEntity, RestoreEntity):
    """Rain since local midnight, derived from the sensor's total counter.

    The API only reports a lifetime total ("r"). We remember the total at
    midnight (baseline) and show the difference. Counter resets (e.g. battery
    change) are detected and handled.
    """

    _attr_translation_key = "rain_today"
    _attr_device_class = SensorDeviceClass.PRECIPITATION
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: WeatherhubCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "rain_today")
        self._baseline: float | None = None
        self._last_total: float | None = None
        self._day: str | None = None

    @property
    def extra_restore_state_data(self) -> RainTodayData:
        return RainTodayData(self._baseline, self._last_total, self._day)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (extra := await self.async_get_last_extra_data()) is not None:
            data = RainTodayData.from_dict(extra.as_dict())
            self._baseline, self._last_total, self._day = (
                data.baseline, data.last_total, data.day
            )
        self.async_on_remove(
            async_track_time_change(self.hass, self._midnight, hour=0, minute=0, second=0)
        )
        self._update_from_total()

    @callback
    def _midnight(self, _now: datetime) -> None:
        self._start_new_day()
        self.async_write_ha_state()

    def _start_new_day(self) -> None:
        self._day = dt_util.now().date().isoformat()
        self._baseline = self._last_total

    def _update_from_total(self) -> None:
        total = _number(0, 1_000_000)(self.measurement.get("r"))
        if total is None:
            return
        if self._day != dt_util.now().date().isoformat():
            self._start_new_day()
        if self._baseline is None:
            self._baseline = total
        elif self._last_total is not None and total < self._last_total:
            # counter was reset: keep what has been counted today so far
            self._baseline -= self._last_total
        self._last_total = total

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_from_total()
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> float | None:
        if self._baseline is None or self._last_total is None:
            return None
        return max(0.0, round(self._last_total - self._baseline, 3))


# --------------------------------------------------------------------------
# Rolling window sensors (min / max / rain sum over a time window)
# The API only reports the latest value, so the history is recorded here and
# persisted through Home Assistant's restore state mechanism.
# --------------------------------------------------------------------------

MODE_MIN = "min"
MODE_MAX = "max"
MODE_COUNTER = "counter"  # difference of a cumulative counter over the window


@dataclass(frozen=True, kw_only=True)
class WeatherhubHistoryDescription(SensorEntityDescription):
    """Describes a rolling window sensor."""

    field: str
    mode: str
    window: timedelta
    value_fn: Callable[[Any], float | None]


_H24 = timedelta(hours=24)
_rain = _number(0, 1_000_000)
_wind = _number(0, 100)
_hum = _number(0, 100)


def _rain_desc(key: str, window: timedelta) -> WeatherhubHistoryDescription:
    return WeatherhubHistoryDescription(
        key=key,
        translation_key=key,
        field="r",
        mode=MODE_COUNTER,
        window=window,
        value_fn=_rain,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        suggested_display_precision=1,
    )


def _extreme_desc(
    key: str, field: str, mode: str, value_fn: Callable[[Any], float | None], **kwargs: Any
) -> WeatherhubHistoryDescription:
    return WeatherhubHistoryDescription(
        key=key,
        translation_key=key,
        field=field,
        mode=mode,
        window=_H24,
        value_fn=value_fn,
        state_class=SensorStateClass.MEASUREMENT,
        **kwargs,
    )


_TEMP_KW = {
    "device_class": SensorDeviceClass.TEMPERATURE,
    "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
}
_HUM_KW = {
    "device_class": SensorDeviceClass.HUMIDITY,
    "native_unit_of_measurement": PERCENTAGE,
}
_WIND_KW = {
    "device_class": SensorDeviceClass.WIND_SPEED,
    "native_unit_of_measurement": UnitOfSpeed.METERS_PER_SECOND,
    "suggested_unit_of_measurement": UnitOfSpeed.KILOMETERS_PER_HOUR,
    "suggested_display_precision": 1,
}

HISTORY_SENSORS: tuple[WeatherhubHistoryDescription, ...] = (
    _rain_desc("rain_1h", timedelta(hours=1)),
    _rain_desc("rain_7d", timedelta(days=7)),
    _rain_desc("rain_30d", timedelta(days=30)),
    _extreme_desc("temperature_min_24h", "t1", MODE_MIN, _temp, **_TEMP_KW),
    _extreme_desc("temperature_max_24h", "t1", MODE_MAX, _temp, **_TEMP_KW),
    _extreme_desc("humidity_min_24h", "h", MODE_MIN, _hum, **_HUM_KW),
    _extreme_desc("humidity_max_24h", "h", MODE_MAX, _hum, **_HUM_KW),
    _extreme_desc("wind_speed_max_24h", "ws", MODE_MAX, _wind, **_WIND_KW),
    _extreme_desc("wind_gust_max_24h", "wg", MODE_MAX, _wind, **_WIND_KW),
)


@dataclass
class HistoryData(ExtraStoredData):
    """Persisted samples of a rolling window sensor."""

    samples: list[list[float]]
    offset: float
    last_raw: float | None

    def as_dict(self) -> dict[str, Any]:
        return {"samples": self.samples, "offset": self.offset, "last_raw": self.last_raw}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HistoryData:
        samples = [
            [float(ts), float(val)]
            for ts, val in (data.get("samples") or [])
        ]
        return cls(samples, float(data.get("offset") or 0.0), data.get("last_raw"))


class WeatherhubHistorySensor(WeatherhubEntity, SensorEntity, RestoreEntity):
    """Min / max / counter difference over a rolling time window."""

    entity_description: WeatherhubHistoryDescription

    def __init__(
        self,
        coordinator: WeatherhubCoordinator,
        device_id: str,
        description: WeatherhubHistoryDescription,
    ) -> None:
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description
        # samples: [unix timestamp, value]; for counters the value is the
        # reset-corrected cumulative total.
        self._samples: list[list[float]] = []
        self._offset = 0.0
        self._last_raw: float | None = None
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    @property
    def extra_restore_state_data(self) -> HistoryData:
        return HistoryData(self._samples, self._offset, self._last_raw)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (extra := await self.async_get_last_extra_data()) is not None:
            try:
                data = HistoryData.from_dict(extra.as_dict())
            except (TypeError, ValueError):
                data = None
            if data is not None:
                self._samples, self._offset, self._last_raw = (
                    data.samples, data.offset, data.last_raw
                )
        self._ingest()
        self._recalculate()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._ingest()
        self._recalculate()
        super()._handle_coordinator_update()

    def _ingest(self) -> None:
        """Add the current measurement as a sample (once per measurement)."""
        desc = self.entity_description
        measurement = self.measurement
        value = desc.value_fn(measurement.get(desc.field))
        if value is None:
            return
        try:
            ts = float(measurement.get("ts"))
        except (TypeError, ValueError):
            ts = dt_util.utcnow().timestamp()

        if self._samples and ts <= self._samples[-1][0]:
            return  # already recorded (API polled faster than sensor sends)

        if desc.mode == MODE_COUNTER:
            if self._last_raw is not None and value < self._last_raw:
                self._offset += self._last_raw  # counter reset, e.g. new battery
            self._last_raw = value
            value = value + self._offset
            if self._samples and value == self._samples[-1][1]:
                return  # counter unchanged: no need to store a sample
        self._samples.append([ts, value])

    def _recalculate(self) -> None:
        desc = self.entity_description
        now = dt_util.utcnow().timestamp()
        cutoff = now - desc.window.total_seconds()

        if desc.mode == MODE_COUNTER:
            # keep the newest sample before the cutoff: it is the counter
            # value at the start of the window
            older = [smp for smp in self._samples if smp[0] <= cutoff]
            newer = [smp for smp in self._samples if smp[0] > cutoff]
            self._samples = older[-1:] + newer
            if not self._samples:
                self._attr_native_value = None
                return
            current = self._samples[-1][1]
            base = self._samples[0][1]
            self._attr_native_value = round(max(0.0, current - base), 3)
            self._attr_extra_state_attributes = {
                "data_since": dt_util.utc_from_timestamp(
                    max(self._samples[0][0], cutoff)
                ).isoformat()
            }
            return

        self._samples = [smp for smp in self._samples if smp[0] > cutoff]
        if not self._samples:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return
        pick = min if desc.mode == MODE_MIN else max
        ts, value = pick(self._samples, key=lambda smp: smp[1])
        self._attr_native_value = value
        self._attr_extra_state_attributes = {
            "time": dt_util.utc_from_timestamp(ts).isoformat(),
            "data_since": dt_util.utc_from_timestamp(self._samples[0][0]).isoformat(),
        }
