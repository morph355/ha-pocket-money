"""Voice assistant (HA Assist) intents for Pocket Money Tracker.

These back the sentences in custom_sentences/en/pocket_money.yaml, so phrases
like "add five pounds to pocket money for chores" can be spoken to any Assist
voice satellite (or typed into the Assist chat) without needing scripts.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .const import DOMAIN
from .coordinator import PocketMoneyAccount

_LOGGER = logging.getLogger(__name__)

INTENT_ADD_FUNDS = "PocketMoneyAddFunds"
INTENT_REMOVE_FUNDS = "PocketMoneyRemoveFunds"
INTENT_GET_BALANCE = "PocketMoneyGetBalance"

_SENTENCES_FILENAME = "pocket_money.yaml"
_SENTENCES_SOURCE = Path(__file__).parent / "custom_sentences" / "en" / _SENTENCES_FILENAME


def _install_custom_sentences(hass: HomeAssistant) -> None:
    """Copy the bundled sentence file into HA's own custom_sentences dir.

    Home Assistant's default conversation agent only scans
    <config>/custom_sentences/<language>/*.yaml at startup - it does not look
    inside a custom integration's own package folder. Without this, the
    sentences bundled here would never actually be loaded by Assist no
    matter how the integration is installed or how often HA is restarted.
    """
    dest_dir = Path(hass.config.path("custom_sentences", "en"))
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_SENTENCES_SOURCE, dest_dir / _SENTENCES_FILENAME)


def _accounts(hass: HomeAssistant) -> list[PocketMoneyAccount]:
    return [
        value
        for value in hass.data.get(DOMAIN, {}).values()
        if isinstance(value, PocketMoneyAccount)
    ]


def _resolve_account(
    hass: HomeAssistant, name: str | None
) -> tuple[PocketMoneyAccount | None, str | None]:
    """Find the account a spoken command refers to.

    Returns (account, error_speech). If error_speech is set, account is None
    and the caller should speak that message back to the user.
    """
    accounts = _accounts(hass)
    if not accounts:
        return None, "You haven't set up a pocket money account yet."

    if name:
        needle = name.strip().lower()
        matches = [a for a in accounts if needle in a.child_name.lower()]
        if len(matches) == 1:
            return matches[0], None
        if not matches:
            return None, f"I couldn't find a pocket money account for {name}."
        return None, f"There's more than one pocket money account matching {name}."

    if len(accounts) == 1:
        return accounts[0], None

    return None, "Whose pocket money did you mean?"


def _slot_value(slots: dict, key: str):
    if key not in slots:
        return None
    return slots[key].get("value")


def _combined_amount(slots: dict) -> float | None:
    """Combine the {amount} (pounds) and {pence} slots into one decimal value.

    Sentences may supply either or both - "add 50 pence" has only {pence},
    "add 2 pounds 50 pence" has both, and the plain "add {amount}" sentences
    have only {amount}.
    """
    pounds = _slot_value(slots, "amount")
    pence = _slot_value(slots, "pence")
    if pounds is None and pence is None:
        return None
    total = float(pounds) if pounds is not None else 0.0
    if pence is not None:
        total += float(pence) / 100.0
    return total


class AddFundsIntentHandler(intent.IntentHandler):
    """Handle: "add {amount} to pocket money [for {reason}]"."""

    intent_type = INTENT_ADD_FUNDS

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        hass = intent_obj.hass
        slots = intent_obj.slots
        response = intent_obj.create_response()

        amount = _combined_amount(slots)
        if amount is None:
            response.async_set_speech("How much should I add?")
            return response
        reason = _slot_value(slots, "reason")
        name = _slot_value(slots, "name")

        account, error = _resolve_account(hass, name)
        if account is None:
            response.async_set_speech(error or "I couldn't find that account.")
            return response

        try:
            await account.async_add_funds(amount, reason)
        except ValueError:
            response.async_set_speech("The amount needs to be greater than zero.")
            return response

        speech = (
            f"Added {amount:g} {account.currency} to {account.child_name}'s "
            f"pocket money. New balance is {account.balance:g} {account.currency}."
        )
        response.async_set_speech(speech)
        return response


class RemoveFundsIntentHandler(intent.IntentHandler):
    """Handle: "remove {amount} from pocket money [for {reason}]"."""

    intent_type = INTENT_REMOVE_FUNDS

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        hass = intent_obj.hass
        slots = intent_obj.slots
        response = intent_obj.create_response()

        amount = _combined_amount(slots)
        if amount is None:
            response.async_set_speech("How much should I take off?")
            return response
        reason = _slot_value(slots, "reason")
        name = _slot_value(slots, "name")

        account, error = _resolve_account(hass, name)
        if account is None:
            response.async_set_speech(error or "I couldn't find that account.")
            return response

        try:
            await account.async_remove_funds(amount, reason)
        except ValueError:
            response.async_set_speech("The amount needs to be greater than zero.")
            return response

        speech = (
            f"Removed {amount:g} {account.currency} from {account.child_name}'s "
            f"pocket money. New balance is {account.balance:g} {account.currency}."
        )
        response.async_set_speech(speech)
        return response


class GetBalanceIntentHandler(intent.IntentHandler):
    """Handle: "what is [the] pocket money balance"."""

    intent_type = INTENT_GET_BALANCE

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        hass = intent_obj.hass
        slots = intent_obj.slots
        response = intent_obj.create_response()

        name = _slot_value(slots, "name")
        account, error = _resolve_account(hass, name)
        if account is None:
            response.async_set_speech(error or "I couldn't find that account.")
            return response

        speech = (
            f"{account.child_name} has {account.balance:g} {account.currency} "
            "in pocket money."
        )
        response.async_set_speech(speech)
        return response


async def async_register_intents(hass: HomeAssistant) -> None:
    """Register the pocket money intents once per Home Assistant instance."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("_intents_registered"):
        return
    domain_data["_intents_registered"] = True

    await hass.async_add_executor_job(_install_custom_sentences, hass)

    intent.async_register(hass, AddFundsIntentHandler())
    intent.async_register(hass, RemoveFundsIntentHandler())
    intent.async_register(hass, GetBalanceIntentHandler())
