"""Tests for persistent user preferences and configuration."""

from __future__ import annotations

import json
from pathlib import Path
from src.config import UserPreferences, load_preferences, save_preferences


def test_preferences_save_and_load(tmp_path: Path) -> None:
    pref_file = tmp_path / "test_prefs.json"

    prefs = UserPreferences(
        last_city="Tokyo",
        temperature_unit="F",
        enable_regional_news=True,
        auto_locate_on_startup=False,
    )
    ok = save_preferences(prefs, pref_file)
    assert ok is True
    assert pref_file.exists()

    loaded = load_preferences(pref_file)
    assert loaded.last_city == "Tokyo"
    assert loaded.temperature_unit == "F"
    assert loaded.enable_regional_news is True


def test_preferences_corrupt_file_recovery(tmp_path: Path) -> None:
    corrupt_file = tmp_path / "corrupt_prefs.json"
    corrupt_file.write_text("{invalid json garbage", encoding="utf-8")

    loaded = load_preferences(corrupt_file)
    # Should fall back cleanly to defaults without crashing
    assert loaded.last_city == "London"
    assert loaded.temperature_unit == "C"


def test_preferences_sanitization() -> None:
    prefs = UserPreferences(last_city="   Sydney   ", temperature_unit="kelvin")
    prefs.sanitize()
    assert prefs.last_city == "Sydney"
    assert prefs.temperature_unit == "C"
