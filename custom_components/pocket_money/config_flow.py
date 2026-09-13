"""Config flow for the Pocket Money integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    CONF_BASE_AMOUNT,
    CONF_CHILD_NAME,
    CONF_CREDIT_DAY,
    CONF_CURRENCY,
    CONF_STARTING_BALANCE,
    DEFAULT_BASE_AMOUNT,
    DEFAULT_CREDIT_DAY,
    DOMAIN,
)


def _user_schema(hass, defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_CHILD_NAME, default=defaults.get(CONF_CHILD_NAME, "")
            ): TextSelector(),
            vol.Required(
                CONF_BASE_AMOUNT,
                default=defaults.get(CONF_BASE_AMOUNT, DEFAULT_BASE_AMOUNT),
            ): NumberSelector(
                NumberSelectorConfig(min=0, step=0.01, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_CREDIT_DAY,
                default=defaults.get(CONF_CREDIT_DAY, DEFAULT_CREDIT_DAY),
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=31, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_CURRENCY,
                default=defaults.get(CONF_CURRENCY, hass.config.currency or "USD"),
            ): TextSelector(),
            vol.Optional(
                CONF_STARTING_BALANCE,
                default=defaults.get(CONF_STARTING_BALANCE, 0),
            ): NumberSelector(
                NumberSelectorConfig(min=0, step=0.01, mode=NumberSelectorMode.BOX)
            ),
        }
    )


class PocketMoneyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pocket Money Tracker."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            child_name = user_input[CONF_CHILD_NAME].strip()
            if not child_name:
                errors[CONF_CHILD_NAME] = "required"
            else:
                unique_id = child_name.lower()
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=child_name, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(self.hass, user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> PocketMoneyOptionsFlow:
        return PocketMoneyOptionsFlow(config_entry)


class PocketMoneyOptionsFlow(config_entries.OptionsFlow):
    """Let the base amount and credit day be changed after setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self._config_entry.data, **self._config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_BASE_AMOUNT,
                    default=current.get(CONF_BASE_AMOUNT, DEFAULT_BASE_AMOUNT),
                ): NumberSelector(
                    NumberSelectorConfig(min=0, step=0.01, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(
                    CONF_CREDIT_DAY,
                    default=current.get(CONF_CREDIT_DAY, DEFAULT_CREDIT_DAY),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1, max=31, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
