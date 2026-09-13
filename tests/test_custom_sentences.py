"""Verify custom_sentences/en/pocket_money.yaml matches via hassil.

This is the same matching engine Home Assistant's Assist conversation
agent uses, tested directly rather than through the full
conversation/assist_pipeline/tts stack (which pulls in optional extras
like ffmpeg that aren't needed just to validate sentence matching).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from hassil.intents import Intents
from hassil.recognize import recognize

SENTENCES_PATH = (
    Path(__file__).parent.parent
    / "custom_components"
    / "pocket_money"
    / "custom_sentences"
    / "en"
    / "pocket_money.yaml"
)


@pytest.fixture(scope="module")
def intents() -> Intents:
    return Intents.from_yaml(SENTENCES_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("text", "expected_intent", "expected_slots"),
    [
        ("add five to pocket money", "PocketMoneyAddFunds", {"amount": 5}),
        (
            "add five to pocket money for chores",
            "PocketMoneyAddFunds",
            {"amount": 5, "reason": "chores"},
        ),
        (
            "credit ten to pocket money for washing the car",
            "PocketMoneyAddFunds",
            {"amount": 10, "reason": "washing the car"},
        ),
        ("remove two from pocket money", "PocketMoneyRemoveFunds", {"amount": 2}),
        (
            "take three from pocket money for sweets",
            "PocketMoneyRemoveFunds",
            {"amount": 3, "reason": "sweets"},
        ),
        (
            "spend one from pocket money for a comic",
            "PocketMoneyRemoveFunds",
            {"amount": 1, "reason": "a comic"},
        ),
        ("what is the pocket money balance", "PocketMoneyGetBalance", {}),
        ("pocket money balance", "PocketMoneyGetBalance", {}),
        ("how much pocket money is there", "PocketMoneyGetBalance", {}),
    ],
)
def test_sentence_matches_expected_intent(intents, text, expected_intent, expected_slots):
    result = recognize(text, intents)
    assert result is not None, f"{text!r} did not match any sentence"
    assert result.intent.name == expected_intent
    slots = {key: entity.value for key, entity in result.entities.items()}
    assert slots == expected_slots
