"""Sensor platform for Pocket Money Tracker."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_HISTORY_MONTHS, MAX_RECENT_TRANSACTIONS, SIGNAL_UPDATE
from .coordinator import PocketMoneyAccount


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    account: PocketMoneyAccount = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PocketMoneyBalanceSensor(account, entry),
            PocketMoneyPreviousMonthSensor(account, entry),
            PocketMoneyMonthlyChangeSensor(account, entry),
            PocketMoneyMonthProgressSensor(account, entry),
        ]
    )


class _PocketMoneyBaseSensor(SensorEntity):
    """Shared setup for pocket money sensors."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, account: PocketMoneyAccount, entry: ConfigEntry) -> None:
        self._account = account
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=account.child_name,
            manufacturer="Pocket Money Tracker",
            model="Pocket Money Account",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE.format(entry_id=self._entry.entry_id),
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class _PocketMoneyMonetarySensor(_PocketMoneyBaseSensor):
    """Shared setup for the money-valued sensors."""

    _attr_device_class = SensorDeviceClass.MONETARY
    # Deliberately no state_class: these values can rise or fall
    # arbitrarily through the month and reset on close-out, so they
    # aren't a HA "total"/"measurement" series worth long-term statistics
    # for.

    @property
    def native_unit_of_measurement(self) -> str:
        return self._account.currency


class PocketMoneyBalanceSensor(_PocketMoneyMonetarySensor):
    """Current balance for the active month."""

    _attr_translation_key = "balance"
    _attr_icon = "mdi:piggy-bank"

    def __init__(self, account: PocketMoneyAccount, entry: ConfigEntry) -> None:
        super().__init__(account, entry)
        self._attr_unique_id = f"{entry.entry_id}_balance"

    @property
    def native_value(self) -> float:
        return self._account.balance

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        recent = self._account.transactions[-MAX_RECENT_TRANSACTIONS:]
        return {
            "child_name": self._account.child_name,
            "period_start": self._account.period_start.isoformat(),
            "next_credit_date": self._account.next_credit_date.isoformat(),
            "base_amount": self._account.base_amount,
            "credit_day": self._account.credit_day,
            "recent_transactions": list(reversed(recent)),
        }


class PocketMoneyPreviousMonthSensor(_PocketMoneyMonetarySensor):
    """Closing balance of the most recently closed month."""

    _attr_translation_key = "previous_month"
    _attr_icon = "mdi:calendar-check"

    def __init__(self, account: PocketMoneyAccount, entry: ConfigEntry) -> None:
        super().__init__(account, entry)
        self._attr_unique_id = f"{entry.entry_id}_previous_month"

    @property
    def native_value(self) -> float | None:
        last = self._account.last_closed_month
        return last["closing_balance"] if last else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        last = self._account.last_closed_month
        history = self._account.history[-MAX_HISTORY_MONTHS:]
        transactions = self._account.last_closed_transactions[-MAX_RECENT_TRANSACTIONS:]
        return {
            "child_name": self._account.child_name,
            "period": last["period"] if last else None,
            "closed_at": last["closed_at"] if last else None,
            "recent_transactions": list(reversed(transactions)),
            "history": list(reversed(history)),
        }


class PocketMoneyMonthlyChangeSensor(_PocketMoneyMonetarySensor):
    """Net total added/removed so far this month.

    A separate entity (rather than just an attribute) so it can be
    dropped straight into cards like Tile that color by state, or
    graphed in history -- even though, since the balance always starts
    at 0 for a new month, its value always matches the balance sensor.
    """

    _attr_translation_key = "monthly_change"
    _attr_icon = "mdi:swap-vertical-bold"

    def __init__(self, account: PocketMoneyAccount, entry: ConfigEntry) -> None:
        super().__init__(account, entry)
        self._attr_unique_id = f"{entry.entry_id}_monthly_change"

    @property
    def native_value(self) -> float:
        return self._account.balance


class PocketMoneyMonthProgressSensor(_PocketMoneyBaseSensor):
    """How far through the current pocket-money month we are (0-100)."""

    _attr_translation_key = "month_progress"
    _attr_icon = "mdi:progress-clock"
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, account: PocketMoneyAccount, entry: ConfigEntry) -> None:
        super().__init__(account, entry)
        self._attr_unique_id = f"{entry.entry_id}_month_progress"

    @property
    def native_value(self) -> float:
        return self._account.month_progress
