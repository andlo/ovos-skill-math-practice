"""Tests for how the skill reads numbers: _read_number() for slots and
_read_answer() for spoken quiz answers (numtag)."""
from fractions import Fraction
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.parametrize("text, lang, expected", [
    ("42", "en-us", 42),
    ("forty two", "en-us", 42),
    ("it is twelve", "en-us", 12),
    ("twelve, no, thirteen", "en-us", 13),
    ("2.5", "en-us", Fraction(5, 2)),
    ("two and a half", "en-us", Fraction(5, 2)),
    ("toogfyrre", "da-dk", 42),
    ("to og fyrre", "da-dk", 42),
    ("fire og tyve", "da-dk", 24),
    ("det er fire og tyve", "da-dk", 24),
    ("tolv nej tretten", "da-dk", 13),
    ("2,5", "da-dk", Fraction(5, 2)),
    ("en", "da-dk", 1),
    ("hundrede og tyve", "da-dk", 120),
])
def test_read_answer(text, lang, expected):
    from mathpractice_skill import _read_answer
    assert _read_answer(text, lang) == expected


def test_danish_join_needs_a_unit_and_a_ten():
    """'tyve og fire' is not one number, and nor is 'ti og tyve'."""
    from mathpractice_skill import _spoken_numbers
    assert _spoken_numbers("tyve og fire", "da-dk") == [20, 4]
    assert _spoken_numbers("ti og tyve", "da-dk") == [10, 20]


def test_join_is_danish_only():
    from mathpractice_skill import _spoken_numbers
    assert _spoken_numbers("four and twenty", "en-us") == [4, 20]


@pytest.mark.parametrize("text", [None, "", "banana", "I don't know"])
def test_no_answer(text):
    from mathpractice_skill import _read_answer
    assert _read_answer(text, "en-us") is None


def test_unsupported_language_reads_no_number():
    from mathpractice_skill import _read_answer
    assert _read_answer("5", "xx-xx") is None


def test_read_number_takes_the_first_number():
    from mathpractice_skill import _read_number
    assert _read_number("the 7 times table", "en-us") == 7


def _msg(**data):
    m = MagicMock()
    m.data = data
    return m


def test_danish_quiz_accepts_split_answer(skill, monkeypatch):
    from mathpractice_skill import MathPractice
    monkeypatch.setattr(MathPractice, "lang", "da-dk", raising=False)
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="fire og tyve")
    with patch("mathpractice_skill.generate_problem", return_value=(6, 4, 24)):
        skill.handle_quiz_table(_msg(number="seks"))
    final_call = skill.speak_dialog.call_args_list[-1]
    assert final_call == (("quiz_finished", {"correct": 5, "total": 5}), {})
