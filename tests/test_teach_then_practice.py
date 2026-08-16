"""Tests for the teach-then-practice pattern (README 'Shared pattern:
teach-then-practice', tracked design issue #1). get_response() and
voc_match() are mocked/patched so the teaching loop's flow and state
tracking are tested deterministically."""
from unittest.mock import MagicMock, patch

import pytest


def _msg(**data):
    m = MagicMock()
    m.data = data
    return m


def test_teach_me_speaks_every_row_and_records_taught_facts(skill):
    skill.speak = MagicMock()
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="ok")  # anything but "repeat"
    skill.voc_match = MagicMock(return_value=False)
    fake_resources = MagicMock()
    fake_resources.load_dialog_file = MagicMock(
        side_effect=lambda name, data: [f"{data['i']} times {data['n']} is {data['product']}"])
    with patch.object(type(skill), "resources", property(lambda self: fake_resources)):
        skill.handle_teach_me(_msg(number="5"))

    assert len(skill._taught_facts) == 10
    assert skill._taught_facts[0] == (1, 5, 5)
    assert skill._taught_facts[-1] == (10, 5, 50)
    # 10 rows spoken, no repeats requested
    assert skill.speak.call_count == 10
    skill.speak_dialog.assert_called_once_with("teaching_finished", {"count": 10})


def test_teach_me_repeats_a_row_when_asked(skill):
    skill.speak = MagicMock()
    skill.speak_dialog = MagicMock()
    # say "repeat" on the very first prompt, "ok" on all others
    skill.get_response = MagicMock(side_effect=["repeat"] + ["ok"] * 20)
    skill.voc_match = MagicMock(side_effect=lambda utt, voc: utt == "repeat")
    fake_resources = MagicMock()
    fake_resources.load_dialog_file = MagicMock(
        side_effect=lambda name, data: [f"{data['i']} times {data['n']} is {data['product']}"])
    with patch.object(type(skill), "resources", property(lambda self: fake_resources)):
        skill.handle_teach_me(_msg(number="3"))

    # 10 rows + 1 extra repeat of the first row = 11 speak() calls
    assert skill.speak.call_count == 11
    # still only 10 unique facts recorded (a repeat doesn't double-record)
    assert len(skill._taught_facts) == 10


def test_teach_me_no_prompt_after_last_row(skill):
    """The last row shouldn't wait for a 'repeat or continue' response
    that nobody needs to give - confirms get_response() is called
    exactly 9 times for a 10-row table (once between each pair of
    rows, not after the final one)."""
    skill.speak = MagicMock()
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="ok")
    skill.voc_match = MagicMock(return_value=False)
    fake_resources = MagicMock()
    fake_resources.load_dialog_file = MagicMock(
        side_effect=lambda name, data: [f"{data['i']} times {data['n']} is {data['product']}"])
    with patch.object(type(skill), "resources", property(lambda self: fake_resources)):
        skill.handle_teach_me(_msg(number="7"))

    assert skill.get_response.call_count == 9


def test_teach_me_unparseable_number(skill):
    skill.speak = MagicMock()
    skill.speak_dialog = MagicMock()
    skill.handle_teach_me(_msg(number="banana"))
    skill.speak_dialog.assert_called_once_with("number_not_understood")
    skill.speak.assert_not_called()


def test_quiz_taught_with_nothing_taught_yet(skill):
    skill.speak_dialog = MagicMock()
    skill.handle_quiz_taught(_msg())
    skill.speak_dialog.assert_called_once_with("nothing_taught_yet")


def test_quiz_taught_quizzes_on_exactly_the_taught_facts(skill):
    skill.play_audio = MagicMock()
    skill.speak_dialog = MagicMock()
    skill._taught_facts = [(1, 5, 5), (2, 5, 10), (3, 5, 15)]
    skill.get_response = MagicMock(return_value="wrong answer entirely")
    skill.handle_quiz_taught(_msg())
    # graded against exactly the 3 taught facts, not NUM_QUIZ_QUESTIONS(5)
    final_call = skill.speak_dialog.call_args_list[-1]
    assert final_call == (("quiz_finished", {"correct": 0, "total": 3}), {})


def test_quiz_taught_all_correct(skill):
    skill.speak_dialog = MagicMock()
    skill._taught_facts = [(1, 5, 5), (2, 5, 10)]
    skill.get_response = MagicMock(side_effect=["5", "10"])
    skill.handle_quiz_taught(_msg())
    final_call = skill.speak_dialog.call_args_list[-1]
    assert final_call == (("quiz_finished", {"correct": 2, "total": 2}), {})


def test_quiz_taught_uses_multiply_question_dialog(skill):
    skill.speak_dialog = MagicMock()
    skill._taught_facts = [(4, 6, 24)]
    skill.get_response = MagicMock(return_value="24")
    skill.handle_quiz_taught(_msg())
    dialog_name = skill.get_response.call_args_list[0][1]["dialog"]
    assert dialog_name == "quiz_question_multiply"


def _fake_resources_generic():
    """A load_dialog_file stand-in that renders BOTH the multiply
    field names (i/n/product) and the generic ones (a/b/answer),
    matching whichever the real dialog file would actually receive."""
    def _render(name, data):
        if "product" in data:
            return [f"{data['i']} times {data['n']} is {data['product']}"]
        return [f"{data['a']} {name.split('_')[-1]} {data['b']} is {data['answer']}"]
    m = MagicMock()
    m.load_dialog_file = MagicMock(side_effect=_render)
    return m


def test_teach_me_operation_addition(skill):
    skill.speak = MagicMock()
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="ok")
    skill.voc_match = MagicMock(return_value=False)
    with patch.object(type(skill), "resources", property(lambda self: _fake_resources_generic())):
        skill.handle_teach_me_operation(_msg(operation="addition", number="5"))

    assert skill._taught_operation == "add"
    assert len(skill._taught_facts) == 10
    assert skill._taught_facts[0] == (5, 1, 6)  # 5 + 1 = 6
    assert skill._taught_facts[-1] == (5, 10, 15)  # 5 + 10 = 15


def test_teach_me_operation_subtraction(skill):
    skill.speak = MagicMock()
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="ok")
    skill.voc_match = MagicMock(return_value=False)
    with patch.object(type(skill), "resources", property(lambda self: _fake_resources_generic())):
        skill.handle_teach_me_operation(_msg(operation="subtraction", number="5"))

    assert skill._taught_operation == "subtract"
    assert skill._taught_facts[0] == (6, 5, 1)  # 6 - 5 = 1
    assert skill._taught_facts[-1] == (15, 5, 10)  # 15 - 5 = 10


def test_teach_me_operation_division(skill):
    skill.speak = MagicMock()
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="ok")
    skill.voc_match = MagicMock(return_value=False)
    with patch.object(type(skill), "resources", property(lambda self: _fake_resources_generic())):
        skill.handle_teach_me_operation(_msg(operation="division", number="5"))

    assert skill._taught_operation == "divide"
    assert skill._taught_facts[0] == (5, 5, 1)  # 5 / 5 = 1
    assert skill._taught_facts[-1] == (50, 5, 10)  # 50 / 5 = 10


def test_teach_me_operation_unknown_operation(skill):
    skill.speak = MagicMock()
    skill.speak_dialog = MagicMock()
    skill.handle_teach_me_operation(_msg(operation="calculus", number="5"))
    skill.speak_dialog.assert_called_once_with(
        "operation_not_understood", {"operation": "calculus"})
    skill.speak.assert_not_called()


def test_teach_me_operation_unparseable_number(skill):
    skill.speak = MagicMock()
    skill.speak_dialog = MagicMock()
    skill.handle_teach_me_operation(_msg(operation="addition", number="banana"))
    skill.speak_dialog.assert_called_once_with("number_not_understood")
    skill.speak.assert_not_called()


def test_teach_me_times_table_still_defaults_operation_to_multiply(skill):
    """The original shorthand intent ('teach me the N times table')
    must still set _taught_operation correctly, so quiz_taught still
    asks multiplication questions afterward - a regression check for
    the refactor that generalized teach mode to all four operations."""
    skill.speak = MagicMock()
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="ok")
    skill.voc_match = MagicMock(return_value=False)
    fake_resources = MagicMock()
    fake_resources.load_dialog_file = MagicMock(
        side_effect=lambda name, data: [f"{data['i']} times {data['n']} is {data['product']}"])
    with patch.object(type(skill), "resources", property(lambda self: fake_resources)):
        skill.handle_teach_me(_msg(number="5"))
    assert skill._taught_operation == "multiply"


def test_quiz_taught_uses_the_operation_that_was_actually_taught(skill):
    """After teaching subtraction, quiz_taught must ask subtraction
    questions, not default back to multiply."""
    skill.speak_dialog = MagicMock()
    skill._taught_facts = [(6, 5, 1), (7, 5, 2)]
    skill._taught_operation = "subtract"
    skill.get_response = MagicMock(side_effect=["1", "2"])
    skill.handle_quiz_taught(_msg())
    dialog_name = skill.get_response.call_args_list[0][1]["dialog"]
    assert dialog_name == "quiz_question_subtract"
    final_call = skill.speak_dialog.call_args_list[-1]
    assert final_call == (("quiz_finished", {"correct": 2, "total": 2}), {})
