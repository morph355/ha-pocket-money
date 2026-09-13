"""Tests for the config flow and options flow."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.pocket_money.const import (
    CONF_BASE_AMOUNT,
    CONF_CHILD_NAME,
    CONF_CREDIT_DAY,
    CONF_CURRENCY,
    CONF_STARTING_BALANCE,
    DOMAIN,
)


async def test_user_flow_creates_entry(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CHILD_NAME: "Emma",
            CONF_BASE_AMOUNT: 10,
            CONF_CREDIT_DAY: 1,
            CONF_CURRENCY: "GBP",
            CONF_STARTING_BALANCE: 0,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Emma"
    assert result["data"][CONF_BASE_AMOUNT] == 10


async def test_user_flow_rejects_duplicate_name(hass):
    data = {
        CONF_CHILD_NAME: "Emma",
        CONF_BASE_AMOUNT: 10,
        CONF_CREDIT_DAY: 1,
        CONF_CURRENCY: "GBP",
        CONF_STARTING_BALANCE: 0,
    }
    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(first["flow_id"], data)
    await hass.async_block_till_done()

    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(second["flow_id"], data)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_updates_base_amount_and_credit_day(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CHILD_NAME: "Emma",
            CONF_BASE_AMOUNT: 10,
            CONF_CREDIT_DAY: 1,
            CONF_CURRENCY: "GBP",
            CONF_STARTING_BALANCE: 0,
        },
    )
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    options_result = await hass.config_entries.options.async_init(entry.entry_id)
    assert options_result["type"] == FlowResultType.FORM

    options_result = await hass.config_entries.options.async_configure(
        options_result["flow_id"],
        {CONF_BASE_AMOUNT: 25, CONF_CREDIT_DAY: 15},
    )
    await hass.async_block_till_done()

    assert options_result["type"] == FlowResultType.CREATE_ENTRY

    account = hass.data[DOMAIN][entry.entry_id]
    assert account.base_amount == 25
    assert account.credit_day == 15
