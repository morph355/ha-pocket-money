# Pocket Money Tracker for Home Assistant

A custom integration that tracks a child's pocket money: a monthly base
amount credited automatically on a chosen day, plus ad-hoc top-ups and
deductions (each with an optional reason) through the month. At month end
the balance is archived and a fresh month starts, so you can always see
last month's final total.

## What it gives you

- **Config flow setup** — add an account from Settings → Devices & Services,
  no YAML required.
- **Two sensors** per account:
  - `sensor.<child>_balance` — current balance, with a `recent_transactions`
    attribute listing amount/reason/timestamp for the running month.
  - `sensor.<child>_previous_month` — the closing balance of the last closed
    month, with a `history` attribute going back up to 24 months.
- **Services** for automations, scripts, or voice: `pocket_money.add_funds`,
  `pocket_money.remove_funds`, `pocket_money.close_month`.
- **Automatic month rollover** on a configurable day (default the 1st):
  snapshots the closing balance to history, clears the transaction list, and
  credits the base amount — all without you doing anything.
- **Events** fired on every change (`pocket_money_transaction`,
  `pocket_money_month_closed`) so you can build your own automations on top
  (e.g. a notification whenever money is added or removed).
- **Built-in Assist voice commands** — "add five to pocket money for
  chores", "take two from pocket money for sweets", "what's the pocket
  money balance" work out of the box with Home Assistant's Assist voice
  pipeline, no extra scripting needed.

## Installation

### Via HACS (custom repository)
1. HACS → Integrations → ⋮ → Custom repositories.
2. Add this repo's URL, category "Integration".
3. Install "Pocket Money Tracker", then restart Home Assistant.

### Manual
Copy `custom_components/pocket_money` into your Home Assistant
`config/custom_components/` directory and restart.

## Setup

Settings → Devices & Services → Add Integration → "Pocket Money Tracker".
You'll be asked for:

- **Child's name** — used as the account/device name.
- **Monthly base amount** — credited automatically on the credit day.
- **Credit day** — day of month (1–31; clamped to the last day in shorter
  months, e.g. 31 becomes the 28th/30th where needed).
- **Currency** — defaults to your Home Assistant instance's currency.
- **Starting balance** (optional) — a one-off opening balance, applied only
  the first time the account is set up.

The base amount and credit day can be changed later from the integration's
"Configure" option; the account keeps its history.

## Services

```yaml
# Add money, with an optional reason
service: pocket_money.add_funds
target:
  entity_id: sensor.emma_balance
data:
  amount: 5
  reason: "Birthday money from Gran"

# Remove money, with an optional reason
service: pocket_money.remove_funds
target:
  entity_id: sensor.emma_balance
data:
  amount: 2.50
  reason: "Bought sweets"

# Manually close the month early (normally automatic)
service: pocket_money.close_month
target:
  entity_id: sensor.emma_balance
```

`target` is required on every call (Home Assistant rejects entity-targeted
service calls with no target) — always pass at least an `entity_id`.

## Building automations

Every add/remove fires a `pocket_money_transaction` event; every rollover
fires `pocket_money_month_closed`. Example: notify you whenever money moves.

```yaml
automation:
  - alias: "Notify on pocket money change"
    trigger:
      - platform: event
        event_type: pocket_money_transaction
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: >-
            {{ trigger.event.data.child_name }}: {{ trigger.event.data.amount }}
            {{ 'added' if trigger.event.data.type in ['credit', 'base_allowance']
               else 'removed' }} ({{ trigger.event.data.reason or 'no reason given' }}).
            New balance: {{ trigger.event.data.new_balance }}.
```

## Voice assistants

### Home Assistant Assist (built in, works today)
No setup needed — just talk or type to Assist:
- "Add ten to pocket money for chores"
- "Take three from pocket money for a snack"
- "What's the pocket money balance"

### Siri (recommended path: Companion App shortcuts, not HomeKit)
The most reliable way to reach Siri is Home Assistant's iOS Companion App,
which can donate any script as a Siri Shortcut:

1. Create a script per common action, e.g. `script.pocket_money_add_pound`
   calling `pocket_money.add_funds` with a fixed amount/reason.
2. In the Home Assistant iOS app, add that script to a Siri Shortcut
   (Settings → Shortcuts, or via the iOS Shortcuts app's Home Assistant
   actions).
3. Say "Hey Siri, add a pound to pocket money."

This avoids exposing the integration through HomeKit (where voice commands
are limited to on/off-style device semantics and don't fit money amounts
well).

### Alexa
Expose the same kind of fixed-amount scripts as scenes via Home Assistant's
Alexa Smart Home integration (Nabu Casa, or a manual Alexa Skill), then:

- "Alexa, turn on Add A Pound To Pocket Money."

Example script + automation glue:

```yaml
script:
  pocket_money_add_pound:
    alias: "Add a pound to pocket money"
    sequence:
      - service: pocket_money.add_funds
        target:
          entity_id: sensor.emma_balance
        data:
          amount: 1
          reason: "Voice command"
```

## Development

### Interactive testing (devcontainer)
Open this repo in VS Code with the Dev Containers extension ("Reopen in
Container"), then run `scripts/develop` to launch a real Home Assistant
instance at http://localhost:8123 with this repo's `custom_components`
mounted — useful for clicking through the config flow or trying Assist
voice commands by hand.

### Automated tests
```
python -m venv .venv
.venv/Scripts/activate  # or source .venv/bin/activate on Linux/macOS
pip install -r requirements_test.txt
pytest tests/
```
On Windows, use Python 3.12 (not 3.13) for this venv: `homeassistant`
pins `lru-dict==1.3.0`, which has no prebuilt wheel for Python 3.13 on
Windows and would otherwise require a C++ compiler to build from source.

## Notes / limitations (v1)

- One account per config entry, but you can add multiple config entries for
  more than one child — each gets its own device, sensors, and services
  target.
- Amounts are stored to 2 decimal places; this isn't built for anything
  beyond simple pocket-money-scale bookkeeping.
- Fixed-amount scripts (used for Siri/Alexa) log whatever reason you hard-code
  into the script; only Assist captures a spoken reason dynamically.
