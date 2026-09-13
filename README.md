# Pocket Money Tracker for Home Assistant

A custom integration that tracks a child's pocket money: a monthly base
amount credited automatically on a chosen day, plus ad-hoc top-ups and
deductions (each with an optional reason) through the month. At month end
the balance is archived and a fresh month starts, so you can always see
last month's final total.

## What it gives you

- **Config flow setup** — add an account from Settings → Devices & Services,
  no YAML required.
- **Four sensors** per account (all under one device, so they group
  together in Settings → Devices & Services → the account's device page):
  - `sensor.<child>_balance` — current balance for the running month.
    Attributes: `recent_transactions` (amount/reason/timestamp for every
    change so far this month), `period_start`, `next_credit_date`,
    `base_amount`, `credit_day`.
  - `sensor.<child>_previous_month` — the closing balance of the last
    closed month. Attributes: `recent_transactions` (the full amount/
    reason/timestamp detail for that closed month), `period`, `closed_at`,
    and `history` — lightweight summaries (period + closing balance, no
    per-transaction detail) going back up to 24 months.
  - `sensor.<child>_monthly_change` — net total added/removed so far this
    month. Its own entity (not just an attribute) so it drops straight
    into cards like Tile that color by state — its value always matches
    `balance` since the month starts at 0.
  - `sensor.<child>_month_progress` — 0–100, how far through the current
    pocket-money month you are (from the last credit date to the next).
- **Services** for automations, scripts, or voice: `pocket_money.add_funds`,
  `pocket_money.remove_funds`, `pocket_money.close_month`.
- **Automatic month rollover** on a configurable day (default the 1st):
  snapshots the closing balance to history, clears the transaction list, and
  credits the base amount — all without you doing anything. A positive (or
  zero) closing balance does *not* carry forward — that's assumed to be
  paid out in person, so the new month starts clean. A negative balance
  (overspent) *does* carry forward, netted against the new month's base
  amount, so the child starts the new month still owing it rather than
  getting a clean slate on money already spent.
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

## Dashboard

The integration only exposes numbers (via the four sensors above) —
coloring and shapes are a Lovelace card concern.

Home Assistant's Markdown card sanitizes its rendered HTML and doesn't
allow SVG elements, so a hand-drawn rainbow arc (`<svg>`/`<path>`/
`<linearGradient>`) won't render — those tags get stripped and their raw
text leaks through instead. The reliable way to get a progress-arc shape
is the built-in **Gauge card**, combined with a Markdown card for the
balance and colored monthly change, merged into one bordered card with
the small HACS frontend card **`stack-in-card`**.

### Install `stack-in-card`
1. HACS → **Frontend** → search **"stack-in-card"** → install → restart
   Home Assistant.
2. It should auto-register as a Lovelace resource (Settings → Dashboards
   → ⋮ → Resources — look for `stack-in-card.js`). If a card using it
   claims the dependency is missing right after installing, a hard
   refresh of the frontend usually fixes it (desktop: Ctrl/Cmd+Shift+R;
   mobile app: fully close and reopen).

### Adding the card
1. Open the dashboard you want, then the **⋮ menu (top right) → Edit
   Dashboard**.
2. **+ Add Card** → search **"Manual"** (this is how you paste raw YAML
   instead of using a visual form).
3. Delete the placeholder and paste the YAML below, then **Save**.

```yaml
type: custom:stack-in-card
cards:
  - type: gauge
    entity: sensor.emma_month_progress
    name: Month progress
    min: 0
    max: 100
  - type: markdown
    content: >
      {% set bal = states('sensor.emma_balance') | float(0) %}
      {% set change = states('sensor.emma_monthly_change') | float(0) %}
      {% set currency = state_attr('sensor.emma_balance', 'unit_of_measurement') %}
      <div style="text-align:center;">
        <h1 style="margin:0;">{{ bal }} {{ currency }}</h1>
        <div style="font-size:1.1em; font-weight:bold; color: {{ '#2e7d32' if change >= 0 else '#c62828' }};">
          {{ '+' if change >= 0 else '' }}{{ change }} {{ currency }} this month
        </div>
      </div>
```

Swap `sensor.emma_...` for your account's actual entity IDs throughout.
The gauge shows the month-progress % in its own center (that's a Home
Assistant Gauge card limitation — it always displays its own bound
entity's value, so it can't be swapped for the balance); the balance and
colored change sit directly below it in the same merged card.

### Using it inside Dwains Dashboard

If you use [Dwains Dashboard](https://github.com/dwainscheeren/dwains-lovelace-dashboard),
its auto-generated area/device pages have their own per-entity card
configurator rather than a plain YAML editor, so pasting the card above
into one of those directly can fail oddly. Dwains supports custom cards
via its own **card blueprint** format instead — this one takes three
entity pickers (balance, monthly change, month progress) so you choose
the right sensors when adding it:

```yaml
blueprint:
  custom_cards:
    - stack-in-card
  description: Pocket Money balance, this month's change, and a month-progress gauge, all in one card.
  input:
    balance_entity:
      name: Balance entity
      description: The pocket money balance sensor
      type: entity-picker
    change_entity:
      name: Monthly change entity
      description: The pocket money monthly change sensor
      type: entity-picker
    progress_entity:
      name: Month progress entity
      description: The pocket money month progress sensor
      type: entity-picker
  name: Pocket Money Card
  type: card
  version: '1.0'
card:
  type: custom:stack-in-card
  cards:
    - type: gauge
      entity: $progress_entity$
      name: Month progress
      min: 0
      max: 100
    - type: markdown
      content: >
        {% set bal = states('$balance_entity$') | float(0) %}
        {% set change = states('$change_entity$') | float(0) %}
        {% set currency = state_attr('$balance_entity$', 'unit_of_measurement') %}
        <div style="text-align:center;">
          <h1 style="margin:0;">{{ bal }} {{ currency }}</h1>
          <div style="font-size:1.1em; font-weight:bold; color: {{ '#2e7d32' if change >= 0 else '#c62828' }};">
            {{ '+' if change >= 0 else '' }}{{ change }} {{ currency }} this month
          </div>
        </div>
```

## Adding and removing money from the dashboard

The services can be called straight from a card's `tap_action`, but routing
them through **scripts** first is worth it: the same scripts double as
Siri Shortcuts / Alexa scenes (see [Voice assistants](#voice-assistants)
below), so you're not maintaining two separate setups.

### Quick preset buttons
Adjust the amounts/reasons/entity_id to taste, then add these as four
separate scripts.

**If you manage scripts through the UI** (Settings → Automations & Scenes
→ Scripts → **+ Add Script** → ⋮ → **Edit in YAML**): that editor is scoped
to *one script at a time* and its schema doesn't accept a `script:` wrapper
or a script-ID key — pasting one produces `Message malformed: not a valid
option, did you mean 'description'? at 'script'`. Paste only the script's
own fields, then repeat "+ Add Script" for each preset:

```yaml
alias: "Add £1 pocket money"
icon: mdi:cash-plus
sequence:
  - action: pocket_money.add_funds
    target:
      entity_id: sensor.emma_balance
    data:
      amount: 1
      reason: "Top-up"
```

```yaml
alias: "Add £5 pocket money"
icon: mdi:cash-plus
sequence:
  - action: pocket_money.add_funds
    target:
      entity_id: sensor.emma_balance
    data:
      amount: 5
      reason: "Top-up"
```

```yaml
alias: "Remove £1 pocket money"
icon: mdi:cash-minus
sequence:
  - action: pocket_money.remove_funds
    target:
      entity_id: sensor.emma_balance
    data:
      amount: 1
      reason: "Spent"
```

```yaml
alias: "Remove £2 pocket money"
icon: mdi:cash-minus
sequence:
  - action: pocket_money.remove_funds
    target:
      entity_id: sensor.emma_balance
    data:
      amount: 2
      reason: "Spent"
```

**If you manage scripts as YAML files** (`configuration.yaml`, or a
`scripts.yaml` `!include`d under a top-level `script:` key there), keep the
`script:` wrapper and give each one its own ID:

```yaml
script:
  pocket_money_add_pound:
    alias: "Add £1 pocket money"
    icon: mdi:cash-plus
    sequence:
      - action: pocket_money.add_funds
        target:
          entity_id: sensor.emma_balance
        data:
          amount: 1
          reason: "Top-up"

  pocket_money_add_fiver:
    alias: "Add £5 pocket money"
    icon: mdi:cash-plus
    sequence:
      - action: pocket_money.add_funds
        target:
          entity_id: sensor.emma_balance
        data:
          amount: 5
          reason: "Top-up"

  pocket_money_remove_pound:
    alias: "Remove £1 pocket money"
    icon: mdi:cash-minus
    sequence:
      - action: pocket_money.remove_funds
        target:
          entity_id: sensor.emma_balance
        data:
          amount: 1
          reason: "Spent"

  pocket_money_remove_two_pounds:
    alias: "Remove £2 pocket money"
    icon: mdi:cash-minus
    sequence:
      - action: pocket_money.remove_funds
        target:
          entity_id: sensor.emma_balance
        data:
          amount: 2
          reason: "Spent"
```

(If `scripts.yaml` is already the file `script:` points to via `!include
scripts.yaml`, drop the `script:` wrapper there too — its top-level keys
are just the script IDs directly.)

Then a button grid card (Add Card → Manual). Some Home Assistant versions
default a script entity's tap action to opening its more-info dialog
instead of running it, so set `tap_action` explicitly to be sure:

```yaml
type: grid
columns: 2
cards:
  - type: button
    entity: script.pocket_money_add_pound
    name: +£1
    icon: mdi:cash-plus
    tap_action:
      action: perform-action
      perform_action: script.turn_on
      target:
        entity_id: script.pocket_money_add_pound
  - type: button
    entity: script.pocket_money_add_fiver
    name: +£5
    icon: mdi:cash-plus
    tap_action:
      action: perform-action
      perform_action: script.turn_on
      target:
        entity_id: script.pocket_money_add_fiver
  - type: button
    entity: script.pocket_money_remove_pound
    name: -£1
    icon: mdi:cash-minus
    tap_action:
      action: perform-action
      perform_action: script.turn_on
      target:
        entity_id: script.pocket_money_remove_pound
  - type: button
    entity: script.pocket_money_remove_two_pounds
    name: -£2
    icon: mdi:cash-minus
    tap_action:
      action: perform-action
      perform_action: script.turn_on
      target:
        entity_id: script.pocket_money_remove_two_pounds
```

(On older Home Assistant versions that don't recognize `perform-action`,
use `action: call-service` and `service: script.turn_on` instead.)

#### Dwains Dashboard blueprint for the buttons
Same reasoning as the [balance card blueprint](#using-it-inside-dwains-dashboard):
Dwains' auto-generated pages want a card blueprint rather than raw
Lovelace YAML. This one takes four script pickers so you can wire up
whichever scripts you created above:

```yaml
blueprint:
  description: Pocket Money quick add/remove buttons (+£1, +£5, -£1, -£2) — pick your four scripts.
  input:
    add_pound_script:
      name: Add £1 script
      description: Script that adds £1
      type: entity-picker
    add_fiver_script:
      name: Add £5 script
      description: Script that adds £5
      type: entity-picker
    remove_pound_script:
      name: Remove £1 script
      description: Script that removes £1
      type: entity-picker
    remove_two_pounds_script:
      name: Remove £2 script
      description: Script that removes £2
      type: entity-picker
  name: Pocket Money Buttons
  type: card
  version: '1.0'
card:
  type: grid
  columns: 2
  cards:
    - type: button
      entity: $add_pound_script$
      name: +£1
      icon: mdi:cash-plus
      tap_action:
        action: perform-action
        perform_action: script.turn_on
        target:
          entity_id: $add_pound_script$
    - type: button
      entity: $add_fiver_script$
      name: +£5
      icon: mdi:cash-plus
      tap_action:
        action: perform-action
        perform_action: script.turn_on
        target:
          entity_id: $add_fiver_script$
    - type: button
      entity: $remove_pound_script$
      name: -£1
      icon: mdi:cash-minus
      tap_action:
        action: perform-action
        perform_action: script.turn_on
        target:
          entity_id: $remove_pound_script$
    - type: button
      entity: $remove_two_pounds_script$
      name: -£2
      icon: mdi:cash-minus
      tap_action:
        action: perform-action
        perform_action: script.turn_on
        target:
          entity_id: $remove_two_pounds_script$
```

No `custom_cards` entry is needed here — `grid` and `button` are built-in
Lovelace card types, unlike the balance card's `stack-in-card`. The
`tap_action` on each button forces it to run the script directly rather
than opening its more-info dialog (some Home Assistant versions default
script buttons to more-info instead of running).

### Flexible amount + reason form
For anything that doesn't fit a preset. First create two helpers:
Settings → Devices & Services → **Helpers** tab → **+ Create Helper**:
- **Number** — name it "Pocket Money Amount" (min `0.01`, step `0.01`,
  **Display Mode: Box** so it's a typed number field rather than a slider).
  Note its entity ID (likely `input_number.pocket_money_amount`).
- **Text** — name it "Pocket Money Reason". Note its entity ID (likely
  `input_text.pocket_money_reason`).

Then two more scripts that read those helpers. As above, if you're using
the UI's "Edit in YAML" (per-script), paste just one script's fields at a
time with no `script:` wrapper:

```yaml
alias: "Add custom amount to pocket money"
icon: mdi:cash-plus
sequence:
  - action: pocket_money.add_funds
    target:
      entity_id: sensor.emma_balance
    data:
      amount: "{{ states('input_number.pocket_money_amount') | float(0) }}"
      reason: "{{ states('input_text.pocket_money_reason') }}"
```

```yaml
alias: "Remove custom amount from pocket money"
icon: mdi:cash-minus
sequence:
  - action: pocket_money.remove_funds
    target:
      entity_id: sensor.emma_balance
    data:
      amount: "{{ states('input_number.pocket_money_amount') | float(0) }}"
      reason: "{{ states('input_text.pocket_money_reason') }}"
```

If you manage scripts as YAML files instead, keep the `script:` wrapper
with an ID for each, same as the preset scripts above:

```yaml
script:
  pocket_money_add_custom:
    alias: "Add custom amount to pocket money"
    icon: mdi:cash-plus
    sequence:
      - action: pocket_money.add_funds
        target:
          entity_id: sensor.emma_balance
        data:
          amount: "{{ states('input_number.pocket_money_amount') | float(0) }}"
          reason: "{{ states('input_text.pocket_money_reason') }}"

  pocket_money_remove_custom:
    alias: "Remove custom amount from pocket money"
    icon: mdi:cash-minus
    sequence:
      - action: pocket_money.remove_funds
        target:
          entity_id: sensor.emma_balance
        data:
          amount: "{{ states('input_number.pocket_money_amount') | float(0) }}"
          reason: "{{ states('input_text.pocket_money_reason') }}"
```

And a card with the two inputs plus Add/Remove buttons. As with the preset
buttons, set `tap_action` explicitly so tapping runs the script instead of
opening its more-info dialog:

```yaml
type: vertical-stack
cards:
  - type: entities
    entities:
      - entity: input_number.pocket_money_amount
        name: Amount
      - entity: input_text.pocket_money_reason
        name: Reason
  - type: horizontal-stack
    cards:
      - type: button
        entity: script.pocket_money_add_custom
        name: Add
        icon: mdi:cash-plus
        tap_action:
          action: perform-action
          perform_action: script.turn_on
          target:
            entity_id: script.pocket_money_add_custom
      - type: button
        entity: script.pocket_money_remove_custom
        name: Remove
        icon: mdi:cash-minus
        tap_action:
          action: perform-action
          perform_action: script.turn_on
          target:
            entity_id: script.pocket_money_remove_custom
```

The amount/reason fields stay filled in after tapping Add/Remove. To clear
them automatically, add reset steps to the end of each script's
`sequence`:

```yaml
alias: "Add custom amount to pocket money"
icon: mdi:cash-plus
sequence:
  - action: pocket_money.add_funds
    target:
      entity_id: sensor.emma_balance
    data:
      amount: "{{ states('input_number.pocket_money_amount') | float(0) }}"
      reason: "{{ states('input_text.pocket_money_reason') }}"
  - action: input_number.set_value
    target:
      entity_id: input_number.pocket_money_amount
    data:
      value: 0
  - action: input_text.set_value
    target:
      entity_id: input_text.pocket_money_reason
    data:
      value: ""
```

(Same two steps at the end of the "Remove custom amount" script.)

#### Dwains Dashboard blueprint for the custom amount form
Same idea as the other two blueprints above — four pickers (the amount
helper, the reason helper, and the two scripts) so you can wire up
whichever entities you created:

```yaml
blueprint:
  description: Pocket Money custom amount + reason form, with Add/Remove buttons.
  input:
    amount_entity:
      name: Amount helper
      description: The input_number helper holding the amount
      type: entity-picker
    reason_entity:
      name: Reason helper
      description: The input_text helper holding the reason
      type: entity-picker
    add_script:
      name: Add script
      description: Script that adds the custom amount
      type: entity-picker
    remove_script:
      name: Remove script
      description: Script that removes the custom amount
      type: entity-picker
  name: Pocket Money Custom Amount
  type: card
  version: '1.0'
card:
  type: vertical-stack
  cards:
    - type: entities
      entities:
        - entity: $amount_entity$
          name: Amount
        - entity: $reason_entity$
          name: Reason
    - type: horizontal-stack
      cards:
        - type: button
          entity: $add_script$
          name: Add
          icon: mdi:cash-plus
          tap_action:
            action: perform-action
            perform_action: script.turn_on
            target:
              entity_id: $add_script$
        - type: button
          entity: $remove_script$
          name: Remove
          icon: mdi:cash-minus
          tap_action:
            action: perform-action
            perform_action: script.turn_on
            target:
              entity_id: $remove_script$
```

## Voice assistants

### Home Assistant Assist (built in, works today)
No setup needed — just talk or type to Assist:
- "Add ten to pocket money for chores"
- "Take three from pocket money for a snack"
- "What's the pocket money balance"

To have Assist trigger one of your own [preset scripts](#quick-preset-buttons)
by a fixed phrase instead (e.g. so "add a pound to pocket money" runs the
exact £1 top-up script, no amount/reason to speak), add a **Sentence
trigger** automation per script — this is native Home Assistant, not part
of this integration. Settings → Automations & Scenes → **+ Create
Automation** → **Create new automation**, then ⋮ → **Edit in YAML** (this
editor is scoped to one automation, same caveat as the per-script editor —
paste the fields directly, no wrapping list or `automation:` key):

```yaml
alias: "Voice: add a pound to pocket money"
trigger:
  - trigger: conversation
    command:
      - "add a pound to pocket money"
      - "add one pound to pocket money"
condition: []
action:
  - action: script.turn_on
    target:
      entity_id: script.pocket_money_add_pound
mode: single
```

Repeat with the matching phrases and `entity_id` for the other three
preset scripts. These sentence triggers are shortcuts on top of the
built-in phrases above, which still work unchanged for arbitrary amounts.

### Siri (recommended path: Companion App shortcuts, not HomeKit)
The most reliable way to reach Siri is Home Assistant's iOS Companion App,
which can donate any script as a Siri Shortcut:

1. Use the same preset scripts from the
   [dashboard section above](#quick-preset-buttons) (e.g.
   `script.pocket_money_add_pound`) — no separate setup needed.
2. In the Home Assistant iOS app, add that script to a Siri Shortcut
   (Settings → Shortcuts, or via the iOS Shortcuts app's Home Assistant
   actions).
3. Say "Hey Siri, add a pound to pocket money."

This avoids exposing the integration through HomeKit (where voice commands
are limited to on/off-style device semantics and don't fit money amounts
well).

### Alexa
Expose the same preset scripts as scenes via Home Assistant's Alexa Smart
Home integration (Nabu Casa, or a manual Alexa Skill), then:

- "Alexa, turn on Add A Pound To Pocket Money."

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
