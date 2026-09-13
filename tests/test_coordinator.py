"""Pure-logic tests for coordinator helpers."""
from __future__ import annotations

from custom_components.pocket_money.coordinator import _clamp_day


def test_clamp_day_within_month_unchanged():
    assert _clamp_day(2026, 1, 15) == 15


def test_clamp_day_31_clamps_to_28_in_february():
    assert _clamp_day(2026, 2, 31) == 28


def test_clamp_day_31_clamps_to_29_in_leap_february():
    assert _clamp_day(2024, 2, 31) == 29


def test_clamp_day_31_clamps_to_30_in_april():
    assert _clamp_day(2026, 4, 31) == 30
