"""Sensor platform for Pocket Money Tracker."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
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
        ]
    )


class _PocketMoneyBaseSensor(SensorEntity):
    """Shared setup for pocket money sensors."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.MONETARY
    # Deliberately no state_class: the balance can rise or fall arbitrarily
    # through the month and is reset on close-out, so it isn't a HA
    # "total"/"measurement" series worth long-term statistics for.

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


class PocketMoneyBalanceSensor(_PocketMoneyBaseSensor):
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
    def native_unit_of_measurement(self) -> str:
        return self._account.currency

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        recent = self._account.transactions[-MAX_RECENT_TRANSACTIONS:]
        return {
            "child_name": self._account.child_name,
            "period_start": self._account.period_start.isoformat(),
            "next_credit_date": self._account.next_credit_date.isoformat(),
            "base_amount": self._account.base_amount,
            "credit_day": self._account.credit_day,
            # Net total added/removed so far this month. Since the balance
            # always starts at 0 for a new month, this equals `balance` --
            # it's exposed under its own name for dashboards/templates that
            # want to talk about "this month's change" rather than reuse
            # the balance's meaning.
            "net_change": self._account.balance,
            "month_progress": self._account.month_progress,
            "recent_transactions": list(reversed(recent)),
        }


class PocketMoneyPreviousMonthSensor(_PocketMoneyBaseSensor):
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
    def native_unit_of_measurement(self) -> str:
        return self._account.currency

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        last = self._account.last_closed_month
        history = self._account.history[-MAX_HISTORY_MONTHS:]
        transactions = self._account.last_closed_transactions[-MAX_RECENT_TRANSACTIONS:]
        return {
            "child_name": self._account.child_name,
            "period": last["period"] if last else None,
            "closed_at": last["closed_at"] if last else None,
            "net_change": last["closing_balance"] if last else None,
            "recent_transactions": list(reversed(transactions)),
            "history": list(reversed(history)),
        }
