"""Tests for the two pure-recitation intents (no interaction)."""
from unittest.mock import MagicMock

import pytest


def _msg(**data):
    m = MagicMock()
    m.data = data
    return m


def test_count_to_speaks_comma_joined_numbers(skill):
    skill.speak_dialog = MagicMock()
    skill.handle_count_to(_msg(number="5"))
    skill.speak_dialog.assert_called_once_with(
        "counting", {"numbers": "1, 2, 3, 4, 5"})


def test_count_to_rejects_too_high(skill):
    skill.speak_dialog = MagicMock()
    skill.handle_count_to(_msg(number="500"))
    skill.speak_dialog.assert_called_once_with("count_too_high", {"max": 100})


def test_count_to_unparseable_number(skill):
    skill.speak_dialog = MagicMock()
    skill.handle_count_to(_msg(number="banana"))
    skill.speak_dialog.assert_called_once_with("number_not_understood")


def test_recite_table_renders_and_speaks_full_recitation(skill, monkeypatch):
    skill.speak = MagicMock()
    fake_resources = MagicMock()
    fake_resources.load_dialog_file = MagicMock(
        side_effect=lambda name, data: [f"{data['i']} times {data['n']} is {data['product']}"])
    monkeypatch.setattr(
        type(skill), "resources", property(lambda self: fake_resources), raising=False)
    skill.handle_recite_table(_msg(number="5"))
    skill.speak.assert_called_once()
    spoken_text = skill.speak.call_args[0][0]
    assert "1 times 5 is 5" in spoken_text
    assert "10 times 5 is 50" in spoken_text
    assert fake_resources.load_dialog_file.call_count == 10


def test_recite_table_unparseable_number(skill):
    skill.speak = MagicMock()
    skill.speak_dialog = MagicMock()
    skill.handle_recite_table(_msg(number="banana"))
    skill.speak_dialog.assert_called_once_with("number_not_understood")
    skill.speak.assert_not_called()
