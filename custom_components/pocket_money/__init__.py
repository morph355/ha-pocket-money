"""The Pocket Money Tracker integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er

try:
    # HA >= 2026.8: moved out of helpers.service, and now takes a
    # TargetSelection instead of the ServiceCall directly.
    from homeassistant.helpers.target import (
        TargetSelection,
        async_extract_referenced_entity_ids,
    )
except ImportError:
    from homeassistant.helpers.service import async_extract_referenced_entity_ids

    TargetSelection = None

from .const import (
    ATTR_AMOUNT,
    ATTR_REASON,
    CONF_BASE_AMOUNT,
    CONF_CHILD_NAME,
    CONF_CREDIT_DAY,
    CONF_CURRENCY,
    CONF_STARTING_BALANCE,
    DEFAULT_BASE_AMOUNT,
    DEFAULT_CREDIT_DAY,
    DOMAIN,
    SERVICE_ADD_FUNDS,
    SERVICE_CLOSE_MONTH,
    SERVICE_REMOVE_FUNDS,
)
from .coordinator import PocketMoneyAccount
from .intents import async_register_intents

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

SERVICE_AMOUNT_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Required(ATTR_AMOUNT): vol.Coerce(float),
        vol.Optional(ATTR_REASON): cv.string,
    }
)
SERVICE_TARGET_ONLY_SCHEMA = cv.make_entity_service_schema({})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pocket Money Tracker from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    data = {**entry.data, **entry.options}
    account = PocketMoneyAccount(
        hass,
        entry.entry_id,
        data[CONF_CHILD_NAME],
        float(data.get(CONF_BASE_AMOUNT, DEFAULT_BASE_AMOUNT)),
        int(data.get(CONF_CREDIT_DAY, DEFAULT_CREDIT_DAY)),
        data.get(CONF_CURRENCY) or hass.config.currency or "USD",
    )
    await account.async_start()

    starting_balance = data.get(CONF_STARTING_BALANCE)
    if (
        starting_balance
        and not account.transactions
        and not account.history
        and account.balance == 0
    ):
        await account.async_add_funds(float(starting_balance), "Starting balance")

    hass.data[DOMAIN][entry.entry_id] = account

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _async_register_services(hass)
    async_register_intents(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        account: PocketMoneyAccount = hass.data[DOMAIN].pop(entry.entry_id)
        account.async_stop()
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply changed options (base amount / credit day) to the live account."""
    account: PocketMoneyAccount = hass.data[DOMAIN][entry.entry_id]
    account.base_amount = float(
        entry.options.get(CONF_BASE_AMOUNT, account.base_amount)
    )
    account.credit_day = int(entry.options.get(CONF_CREDIT_DAY, account.credit_day))


def _accounts_for_call(hass: HomeAssistant, call: ServiceCall) -> list[PocketMoneyAccount]:
    """Resolve the accounts targeted by a service call's entity/device/area target."""
    target = TargetSelection(call.data) if TargetSelection is not None else call
    referenced = async_extract_referenced_entity_ids(hass, target)
    entity_ids = referenced.referenced | referenced.indirectly_referenced

    ent_reg = er.async_get(hass)
    accounts: list[PocketMoneyAccount] = []
    for entity_id in entity_ids:
        entity = ent_reg.async_get(entity_id)
        if entity is None or entity.config_entry_id is None:
            continue
        account = hass.data.get(DOMAIN, {}).get(entity.config_entry_id)
        if isinstance(account, PocketMoneyAccount) and account not in accounts:
            accounts.append(account)

    return accounts


@callback
def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_ADD_FUNDS):
        return

    async def _async_handle_add_funds(call: ServiceCall) -> None:
        accounts = _accounts_for_call(hass, call)
        if not accounts:
            raise ServiceValidationError(
                "No pocket money account matched the given target."
            )
        for account in accounts:
            await account.async_add_funds(
                call.data[ATTR_AMOUNT], call.data.get(ATTR_REASON)
            )

    async def _async_handle_remove_funds(call: ServiceCall) -> None:
        accounts = _accounts_for_call(hass, call)
        if not accounts:
            raise ServiceValidationError(
                "No pocket money account matched the given target."
            )
        for account in accounts:
            await account.async_remove_funds(
                call.data[ATTR_AMOUNT], call.data.get(ATTR_REASON)
            )

    async def _async_handle_close_month(call: ServiceCall) -> None:
        accounts = _accounts_for_call(hass, call)
        if not accounts:
            raise ServiceValidationError(
                "No pocket money account matched the given target."
            )
        for account in accounts:
            await account.async_close_month()

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_FUNDS, _async_handle_add_funds, schema=SERVICE_AMOUNT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_FUNDS,
        _async_handle_remove_funds,
        schema=SERVICE_AMOUNT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLOSE_MONTH,
        _async_handle_close_month,
        schema=SERVICE_TARGET_ONLY_SCHEMA,
    )
