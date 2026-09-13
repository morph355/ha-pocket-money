"""End-to-end tests for Pocket Money Tracker: config entry, services, rollover."""
from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.helpers import entity_registry as er, intent

from custom_components.pocket_money.const import (
    CONF_BASE_AMOUNT,
    CONF_CHILD_NAME,
    CONF_CREDIT_DAY,
    CONF_CURRENCY,
    CONF_STARTING_BALANCE,
    DOMAIN,
)


def _entity_id(hass, entry: MockConfigEntry, suffix: str) -> str:
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_{suffix}")
    assert entity_id is not None, f"no entity registered for suffix {suffix!r}"
    return entity_id


async def _setup_entry(hass, **overrides) -> MockConfigEntry:
    data = {
        CONF_CHILD_NAME: "Emma",
        CONF_BASE_AMOUNT: 10,
        CONF_CREDIT_DAY: 1,
        CONF_CURRENCY: "GBP",
        CONF_STARTING_BALANCE: 0,
    }
    data.update(overrides)
    entry = MockConfigEntry(domain=DOMAIN, data=data, title=data[CONF_CHILD_NAME])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_creates_balance_and_previous_month_sensors(hass):
    entry = await _setup_entry(hass)

    balance_id = _entity_id(hass, entry, "balance")
    previous_id = _entity_id(hass, entry, "previous_month")

    balance = hass.states.get(balance_id)
    assert balance is not None
    assert float(balance.state) == 0.0
    assert balance.attributes["child_name"] == "Emma"

    previous = hass.states.get(previous_id)
    assert previous is not None
    assert previous.state == "unknown"


async def test_setup_creates_monthly_change_and_month_progress_sensors(hass):
    entry = await _setup_entry(hass)

    change_id = _entity_id(hass, entry, "monthly_change")
    progress_id = _entity_id(hass, entry, "month_progress")

    change = hass.states.get(change_id)
    assert change is not None
    assert float(change.state) == 0.0

    progress = hass.states.get(progress_id)
    assert progress is not None
    assert 0.0 <= float(progress.state) <= 100.0


async def test_add_and_remove_funds_via_service(hass):
    entry = await _setup_entry(hass)
    balance_id = _entity_id(hass, entry, "balance")

    await hass.services.async_call(
        DOMAIN,
        "add_funds",
        {"entity_id": balance_id, "amount": 5, "reason": "Birthday"},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(balance_id)
    assert float(state.state) == 5.0
    assert state.attributes["recent_transactions"][0]["reason"] == "Birthday"
    assert state.attributes["recent_transactions"][0]["amount"] == 5.0

    await hass.services.async_call(
        DOMAIN,
        "remove_funds",
        {"entity_id": balance_id, "amount": 2, "reason": "Sweets"},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(balance_id)
    assert float(state.state) == 3.0
    assert len(state.attributes["recent_transactions"]) == 2


async def test_service_rejects_non_positive_amount(hass):
    entry = await _setup_entry(hass)
    balance_id = _entity_id(hass, entry, "balance")

    with pytest.raises(Exception):
        await hass.services.async_call(
            DOMAIN,
            "add_funds",
            {"entity_id": balance_id, "amount": 0},
            blocking=True,
        )
    await hass.async_block_till_done()
    # balance must be unchanged by the rejected call
    assert float(hass.states.get(balance_id).state) == 0.0


async def test_close_month_snapshots_and_credits_base_amount(hass):
    entry = await _setup_entry(hass, **{CONF_BASE_AMOUNT: 10})
    balance_id = _entity_id(hass, entry, "balance")
    previous_id = _entity_id(hass, entry, "previous_month")

    await hass.services.async_call(
        DOMAIN,
        "add_funds",
        {"entity_id": balance_id, "amount": 5},
        blocking=True,
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN, "close_month", {"entity_id": balance_id}, blocking=True
    )
    await hass.async_block_till_done()

    previous = hass.states.get(previous_id)
    assert float(previous.state) == 5.0

    balance = hass.states.get(balance_id)
    assert float(balance.state) == 10.0
    transactions = balance.attributes["recent_transactions"]
    assert len(transactions) == 1
    assert transactions[0]["type"] == "base_allowance"


async def test_monthly_change_and_previous_month_transaction_detail(hass):
    entry = await _setup_entry(hass, **{CONF_BASE_AMOUNT: 10})
    balance_id = _entity_id(hass, entry, "balance")
    previous_id = _entity_id(hass, entry, "previous_month")
    change_id = _entity_id(hass, entry, "monthly_change")

    await hass.services.async_call(
        DOMAIN,
        "add_funds",
        {"entity_id": balance_id, "amount": 5, "reason": "Birthday"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "remove_funds",
        {"entity_id": balance_id, "amount": 3, "reason": "Sweets"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert float(hass.states.get(change_id).state) == 2.0  # +5 -3

    await hass.services.async_call(
        DOMAIN, "close_month", {"entity_id": balance_id}, blocking=True
    )
    await hass.async_block_till_done()

    previous = hass.states.get(previous_id)
    assert float(previous.state) == 2.0

    reasons = {t["reason"] for t in previous.attributes["recent_transactions"]}
    assert reasons == {"Birthday", "Sweets"}
    amounts = {t["amount"] for t in previous.attributes["recent_transactions"]}
    assert amounts == {5.0, -3.0}

    # new month starts fresh: only the base allowance so far
    assert float(hass.states.get(change_id).state) == 10.0
    balance = hass.states.get(balance_id)
    assert len(balance.attributes["recent_transactions"]) == 1


async def test_month_progress_between_zero_and_hundred(hass):
    entry = await _setup_entry(hass)
    progress_id = _entity_id(hass, entry, "month_progress")
    progress = float(hass.states.get(progress_id).state)
    assert 0.0 <= progress <= 100.0


async def test_service_without_target_is_rejected(hass):
    # Home Assistant's entity-targeted service schema requires an explicit
    # target (entity_id/device_id/area_id/...) on every call.
    await _setup_entry(hass)

    with pytest.raises(Exception):
        await hass.services.async_call(DOMAIN, "add_funds", {"amount": 7}, blocking=True)


async def test_starting_balance_applied_once(hass):
    entry = await _setup_entry(hass, **{CONF_STARTING_BALANCE: 20})
    balance_id = _entity_id(hass, entry, "balance")
    state = hass.states.get(balance_id)
    assert float(state.state) == 20.0
    assert state.attributes["recent_transactions"][0]["reason"] == "Starting balance"


async def test_voice_intent_add_funds(hass):
    entry = await _setup_entry(hass)
    balance_id = _entity_id(hass, entry, "balance")

    response = await intent.async_handle(
        hass,
        "test",
        "PocketMoneyAddFunds",
        {"amount": {"value": 5}, "reason": {"value": "chores"}},
    )
    await hass.async_block_till_done()

    assert response.speech["plain"]["speech"]
    state = hass.states.get(balance_id)
    assert float(state.state) == 5.0
    assert state.attributes["recent_transactions"][0]["reason"] == "chores"


async def test_voice_intent_get_balance(hass):
    entry = await _setup_entry(hass)
    balance_id = _entity_id(hass, entry, "balance")
    await hass.services.async_call(
        DOMAIN, "add_funds", {"entity_id": balance_id, "amount": 8}, blocking=True
    )
    await hass.async_block_till_done()

    response = await intent.async_handle(hass, "test", "PocketMoneyGetBalance", {})
    speech = response.speech["plain"]["speech"]
    assert "8" in speech
    assert "Emma" in speech


async def test_voice_intent_no_account_configured(hass):
    # Intents register on first entry setup; removing the only account later
    # should make the handler fall back to a "not set up" message rather
    # than erroring, since the intents themselves stay registered.
    entry = await _setup_entry(hass)
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    response = await intent.async_handle(hass, "test", "PocketMoneyGetBalance", {})
    speech = response.speech["plain"]["speech"]
    assert "haven't set up" in speech
