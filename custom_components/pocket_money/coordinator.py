"""Data management for a single pocket money account."""
from __future__ import annotations

import calendar
from datetime import date, datetime
import logging
from typing import Any
import uuid

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_AMOUNT,
    ATTR_REASON,
    DEFAULT_REASON_ALLOWANCE,
    DEFAULT_REASON_CARRYOVER,
    EVENT_MONTH_CLOSED,
    EVENT_TRANSACTION,
    MAX_HISTORY_MONTHS,
    SIGNAL_UPDATE,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    TXN_TYPE_ADJUSTMENT,
    TXN_TYPE_BASE,
    TXN_TYPE_CREDIT,
    TXN_TYPE_DEBIT,
)

_LOGGER = logging.getLogger(__name__)


def _clamp_day(year: int, month: int, day: int) -> int:
    """Clamp a day-of-month to the last valid day of that month.

    Lets a credit_day of e.g. 31 fall back to the 28th/30th in shorter months
    instead of silently never firing.
    """
    last_day = calendar.monthrange(year, month)[1]
    return min(day, last_day)


class PocketMoneyAccount:
    """Represents one child's pocket money account: balance, transactions, history."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        child_name: str,
        base_amount: float,
        credit_day: int,
        currency: str,
    ) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.child_name = child_name
        self.base_amount = base_amount
        self.credit_day = credit_day
        self.currency = currency

        self._store: Store = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}{entry_id}"
        )
        self._data: dict[str, Any] = {}
        self._unsub_time = None

    # ---------------------------------------------------------------- load
    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if stored is None:
            today = dt_util.now().date()
            stored = {
                "balance": 0.0,
                "period_start": today.replace(day=1).isoformat(),
                "transactions": [],
                "history": [],
            }
        self._data = stored

    async def async_start(self) -> None:
        """Load persisted data and start the daily rollover check."""
        await self.async_load()
        self._unsub_time = async_track_time_change(
            self.hass, self._handle_time_change, hour=0, minute=5, second=0
        )

    @callback
    def async_stop(self) -> None:
        if self._unsub_time is not None:
            self._unsub_time()
            self._unsub_time = None

    # ------------------------------------------------------------- helpers
    @property
    def balance(self) -> float:
        return round(self._data.get("balance", 0.0), 2)

    @property
    def period_start(self) -> date:
        return date.fromisoformat(self._data["period_start"])

    @property
    def transactions(self) -> list[dict[str, Any]]:
        return list(self._data.get("transactions", []))

    @property
    def history(self) -> list[dict[str, Any]]:
        return list(self._data.get("history", []))

    @property
    def last_closed_month(self) -> dict[str, Any] | None:
        history = self._data.get("history", [])
        return history[-1] if history else None

    @property
    def last_closed_transactions(self) -> list[dict[str, Any]]:
        """Full transaction detail for the most recently closed month."""
        return list(self._data.get("last_closed_transactions", []))

    @property
    def next_credit_date(self) -> date:
        today = dt_util.now().date()
        year, month = today.year, today.month
        day = _clamp_day(year, month, self.credit_day)
        candidate = date(year, month, day)
        if candidate <= today:
            if month == 12:
                year, month = year + 1, 1
            else:
                month += 1
            day = _clamp_day(year, month, self.credit_day)
            candidate = date(year, month, day)
        return candidate

    @property
    def month_progress(self) -> float:
        """Percentage (0-100) of the way through the current pocket money month."""
        start = self.period_start
        end = self.next_credit_date
        total_days = (end - start).days
        if total_days <= 0:
            return 100.0
        elapsed_days = (dt_util.now().date() - start).days
        return round(max(0.0, min(100.0, elapsed_days / total_days * 100)), 1)

    # -------------------------------------------------------------- writes
    async def _async_save(self) -> None:
        await self._store.async_save(self._data)

    @callback
    def _notify_update(self) -> None:
        async_dispatcher_send(self.hass, SIGNAL_UPDATE.format(entry_id=self.entry_id))

    async def _async_record_transaction(
        self, amount: float, reason: str | None, txn_type: str
    ) -> None:
        txn = {
            "id": uuid.uuid4().hex,
            "timestamp": dt_util.now().isoformat(),
            "amount": round(amount, 2),
            "reason": reason or "",
            "type": txn_type,
        }
        self._data.setdefault("transactions", []).append(txn)
        self._data["balance"] = round(self._data.get("balance", 0.0) + amount, 2)
        await self._async_save()
        self._notify_update()

        self.hass.bus.async_fire(
            EVENT_TRANSACTION,
            {
                "entry_id": self.entry_id,
                "child_name": self.child_name,
                ATTR_AMOUNT: txn["amount"],
                ATTR_REASON: txn["reason"],
                "type": txn_type,
                "new_balance": self.balance,
            },
        )

    async def async_add_funds(self, amount: float, reason: str | None = None) -> None:
        """Credit an amount to the account (positive value)."""
        if amount <= 0:
            raise ValueError("amount must be greater than zero")
        await self._async_record_transaction(amount, reason, TXN_TYPE_CREDIT)

    async def async_remove_funds(self, amount: float, reason: str | None = None) -> None:
        """Debit an amount from the account (positive value)."""
        if amount <= 0:
            raise ValueError("amount must be greater than zero")
        await self._async_record_transaction(-amount, reason, TXN_TYPE_DEBIT)

    async def async_close_month(self, *, credit_base: bool = True) -> None:
        """Snapshot the current period to history and start a fresh one.

        The closing balance stays visible via `last_closed_month` /
        the previous-month sensor even after transactions are cleared, and
        the full transaction detail for the closed month is kept (as the
        most recently closed month only) via `last_closed_transactions`.

        A positive (or zero) closing balance does not carry forward - that
        money is assumed to be paid out/given to the child in person, so the
        new month starts clean. A negative closing balance (overspent) does
        carry forward, so the child starts the new month still owing it
        rather than getting a clean slate on money already spent.
        """
        closed_period = self.period_start
        closing_balance = self.balance
        closed_transactions = list(self._data.get("transactions", []))

        history_entry = {
            "period": closed_period.strftime("%Y-%m"),
            "closing_balance": closing_balance,
            "transaction_count": len(closed_transactions),
            "closed_at": dt_util.now().isoformat(),
        }
        history = self._data.setdefault("history", [])
        history.append(history_entry)
        del history[:-MAX_HISTORY_MONTHS]

        today = dt_util.now().date()
        self._data["period_start"] = today.replace(day=1).isoformat()
        self._data["transactions"] = []
        self._data["balance"] = 0.0
        self._data["last_closed_transactions"] = closed_transactions
        await self._async_save()
        self._notify_update()

        self.hass.bus.async_fire(
            EVENT_MONTH_CLOSED,
            {
                "entry_id": self.entry_id,
                "child_name": self.child_name,
                "period": history_entry["period"],
                "closing_balance": closing_balance,
            },
        )

        if closing_balance < 0:
            await self._async_record_transaction(
                closing_balance, DEFAULT_REASON_CARRYOVER, TXN_TYPE_ADJUSTMENT
            )

        if credit_base and self.base_amount:
            await self._async_record_transaction(
                self.base_amount, DEFAULT_REASON_ALLOWANCE, TXN_TYPE_BASE
            )

    # ------------------------------------------------------------ schedule
    async def _handle_time_change(self, now: datetime) -> None:
        # month_progress and next_credit_date are pure date calculations,
        # but sensors only re-publish their state on this dispatcher signal
        # (normally fired by a transaction) - without this, they'd silently
        # freeze at yesterday's value on any day with no add/remove activity.
        self._notify_update()

        today = now.date()
        expected_day = _clamp_day(today.year, today.month, self.credit_day)
        if today.day != expected_day:
            return
        if (
            self.period_start.year == today.year
            and self.period_start.month == today.month
        ):
            # Already rolled over for this month (e.g. HA restarted same day).
            return
        _LOGGER.debug("Closing pocket money month for %s", self.child_name)
        await self.async_close_month()
