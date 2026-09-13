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
        (
            "add ten to arden's pocket money",
            "PocketMoneyAddFunds",
            {"amount": 10, "name": "arden"},
        ),
        (
            "add ten to arden's pocket money for chores",
            "PocketMoneyAddFunds",
            {"amount": 10, "name": "arden", "reason": "chores"},
        ),
        (
            "remove two from arden's pocket money",
            "PocketMoneyRemoveFunds",
            {"amount": 2, "name": "arden"},
        ),
        (
            "take three from arden's pocket money for sweets",
            "PocketMoneyRemoveFunds",
            {"amount": 3, "name": "arden", "reason": "sweets"},
        ),
        (
            "what is arden's pocket money balance",
            "PocketMoneyGetBalance",
            {"name": "arden"},
        ),
        (
            "how much pocket money does arden have",
            "PocketMoneyGetBalance",
            {"name": "arden"},
        ),
        # speech-to-text often mishears "pounds" as the weight unit "lbs"
        ("add five lbs to pocket money", "PocketMoneyAddFunds", {"amount": 5}),
        ("add five pounds to pocket money", "PocketMoneyAddFunds", {"amount": 5}),
        ("add five quid to pocket money", "PocketMoneyAddFunds", {"amount": 5}),
        (
            "add two pounds fifty pence to pocket money",
            "PocketMoneyAddFunds",
            {"amount": 2, "pence": 50},
        ),
        (
            "add fifty pence to pocket money",
            "PocketMoneyAddFunds",
            {"pence": 50},
        ),
        (
            "remove three pounds from pocket money",
            "PocketMoneyRemoveFunds",
            {"amount": 3},
        ),
        (
            "take one pound fifty pence from pocket money for sweets",
            "PocketMoneyRemoveFunds",
            {"amount": 1, "pence": 50, "reason": "sweets"},
        ),
        (
            "add two pounds fifty p to pocket money",
            "PocketMoneyAddFunds",
            {"amount": 2, "pence": 50},
        ),
        ("add fifty p to pocket money", "PocketMoneyAddFunds", {"pence": 50}),
        (
            "deduct four from pocket money",
            "PocketMoneyRemoveFunds",
            {"amount": 4},
        ),
        (
            "subtract four from pocket money for a toy",
            "PocketMoneyRemoveFunds",
            {"amount": 4, "reason": "a toy"},
        ),
        (
            "deduct two pounds fifty pence from pocket money",
            "PocketMoneyRemoveFunds",
            {"amount": 2, "pence": 50},
        ),
        (
            "subtract four from arden's pocket money",
            "PocketMoneyRemoveFunds",
            {"amount": 4, "name": "arden"},
        ),
    ],
)
def test_sentence_matches_expected_intent(intents, text, expected_intent, expected_slots):
    result = recognize(text, intents)
    assert result is not None, f"{text!r} did not match any sentence"
    assert result.intent.name == expected_intent
    slots = {key: entity.value for key, entity in result.entities.items()}
    assert slots == expected_slots
