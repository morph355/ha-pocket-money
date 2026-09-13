"""Constants for the Pocket Money integration."""
from __future__ import annotations

DOMAIN = "pocket_money"

# Config / options keys
CONF_CHILD_NAME = "child_name"
CONF_BASE_AMOUNT = "base_amount"
CONF_CREDIT_DAY = "credit_day"
CONF_CURRENCY = "currency"
CONF_STARTING_BALANCE = "starting_balance"

DEFAULT_CREDIT_DAY = 1
DEFAULT_BASE_AMOUNT = 0.0

# Storage
STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}_"

# Max number of closed months kept in history
MAX_HISTORY_MONTHS = 24
# Max number of transactions kept in the "recent transactions" attribute
MAX_RECENT_TRANSACTIONS = 20

# Services
SERVICE_ADD_FUNDS = "add_funds"
SERVICE_REMOVE_FUNDS = "remove_funds"
SERVICE_CLOSE_MONTH = "close_month"

ATTR_AMOUNT = "amount"
ATTR_REASON = "reason"

# Transaction types
TXN_TYPE_CREDIT = "credit"
TXN_TYPE_DEBIT = "debit"
TXN_TYPE_BASE = "base_allowance"
TXN_TYPE_ADJUSTMENT = "adjustment"

# Events fired on the HA event bus (usable as automation triggers)
EVENT_TRANSACTION = f"{DOMAIN}_transaction"
EVENT_MONTH_CLOSED = f"{DOMAIN}_month_closed"

# Signals used internally to push updates to entities
SIGNAL_UPDATE = f"{DOMAIN}_update_{{entry_id}}"

DEFAULT_REASON_ALLOWANCE = "Monthly allowance"
DEFAULT_REASON_CARRYOVER = "Carried over debt from last month"
