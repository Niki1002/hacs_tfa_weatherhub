"""Config flow for TFA weatherhub."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WeatherhubApi, WeatherhubConnectionError, WeatherhubError, normalize_device_ids
from .const import (
    CONF_DEVICE_IDS,
    CONF_PHONE_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_DEVICE_IDS, default=defaults.get(CONF_DEVICE_IDS, "")
            ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            vol.Optional(
                CONF_PHONE_ID,
                description={"suggested_value": defaults.get(CONF_PHONE_ID)},
            ): str,
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=MAX_SCAN_INTERVAL,
                    step=1,
                    unit_of_measurement="min",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


async def _validate(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
    """Validate input. Returns (clean data, errors, placeholders)."""
    errors: dict[str, str] = {}
    placeholders: dict[str, str] = {"ids": ""}
    try:
        ids = normalize_device_ids(user_input[CONF_DEVICE_IDS])
    except ValueError as err:
        placeholders["ids"] = str(err)
        return {}, {CONF_DEVICE_IDS: "invalid_device_id"}, placeholders
    if not ids:
        return {}, {CONF_DEVICE_IDS: "no_device_ids"}, placeholders

    phone_id = (user_input.get(CONF_PHONE_ID) or "").strip() or None
    api = WeatherhubApi(async_get_clientsession(hass))
    try:
        result = await api.async_get_last_measurements(ids, phone_id)
    except WeatherhubConnectionError:
        errors["base"] = "cannot_connect"
    except WeatherhubError:
        errors["base"] = "api_error"
    else:
        missing = [dev_id for dev_id in ids if dev_id not in result]
        if missing:
            errors[CONF_DEVICE_IDS] = "device_not_found"
            placeholders["ids"] = ", ".join(missing)

    data = {
        CONF_DEVICE_IDS: ids,
        CONF_PHONE_ID: phone_id,
        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
    }
    return data, errors, placeholders


class WeatherhubConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"ids": ""}
        if user_input is not None:
            data, errors, placeholders = await _validate(self.hass, user_input)
            if not errors:
                await self.async_set_unique_id("_".join(sorted(data[CONF_DEVICE_IDS])))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="TFA weatherhub", data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input or {}),
            errors=errors,
            description_placeholders=placeholders,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> WeatherhubOptionsFlow:
        return WeatherhubOptionsFlow()


class WeatherhubOptionsFlow(OptionsFlow):
    """Change device list / interval later."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"ids": ""}
        if user_input is not None:
            data, errors, placeholders = await _validate(self.hass, user_input)
            if not errors:
                return self.async_create_entry(data=data)
            defaults = user_input
        else:
            current = {**self.config_entry.data, **self.config_entry.options}
            defaults = {
                CONF_DEVICE_IDS: "\n".join(current.get(CONF_DEVICE_IDS, [])),
                CONF_PHONE_ID: current.get(CONF_PHONE_ID),
                CONF_SCAN_INTERVAL: current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            }
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(defaults),
            errors=errors,
            description_placeholders=placeholders,
        )
