"""Tests for the interactive quiz flow - get_response() and
generate_problem() are both mocked/patched so the quiz's SCORING and
FLOW logic is tested deterministically, independent of randomness or
actual speech I/O."""
from unittest.mock import MagicMock, patch

import pytest


def _msg(**data):
    m = MagicMock()
    m.data = data
    return m


def test_quiz_table_all_correct_answers(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="42")
    with patch("mathpractice_skill.generate_problem", return_value=(6, 7, 42)):
        skill.handle_quiz_table(_msg(number="6"))
    # every question answered "42" and every generated answer is 42 -> all correct
    correct_calls = [c for c in skill.speak_dialog.call_args_list if c[0][0] == "quiz_correct"]
    assert len(correct_calls) == 5  # NUM_QUIZ_QUESTIONS
    final_call = skill.speak_dialog.call_args_list[-1]
    assert final_call == (("quiz_finished", {"correct": 5, "total": 5}), {})


def test_quiz_table_all_wrong_answers(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="0")
    with patch("mathpractice_skill.generate_problem", return_value=(6, 7, 42)):
        skill.handle_quiz_table(_msg(number="6"))
    final_call = skill.speak_dialog.call_args_list[-1]
    assert final_call == (("quiz_finished", {"correct": 0, "total": 5}), {})


def test_quiz_no_response_counts_as_wrong_but_does_not_crash(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value=None)  # simulates STT timeout
    with patch("mathpractice_skill.generate_problem", return_value=(6, 7, 42)):
        skill.handle_quiz_table(_msg(number="6"))
    no_answer_calls = [c for c in skill.speak_dialog.call_args_list if c[0][0] == "quiz_no_answer"]
    assert len(no_answer_calls) == 5
    final_call = skill.speak_dialog.call_args_list[-1]
    assert final_call == (("quiz_finished", {"correct": 0, "total": 5}), {})


def test_quiz_question_uses_correct_dialog_name_per_operation(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="10")
    with patch("mathpractice_skill.generate_problem", return_value=(4, 6, 10)):
        skill._run_quiz("add")
    dialog_name = skill.get_response.call_args_list[0][1]["dialog"]
    assert dialog_name == "quiz_question_add"


def test_quiz_operation_unknown_operation_speaks_error(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock()
    message = _msg(operation="calculus")
    skill.handle_quiz_operation(message)
    skill.speak_dialog.assert_called_once_with(
        "operation_not_understood", {"operation": "calculus"})
    skill.get_response.assert_not_called()


def test_quiz_operation_known_operation_runs_quiz(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="10")
    with patch("mathpractice_skill.generate_problem", return_value=(4, 6, 10)):
        skill.handle_quiz_operation(_msg(operation="addition"))
    assert skill.get_response.call_count == 5


def test_quiz_general_picks_a_random_operation_and_runs(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="10")
    with patch("mathpractice_skill.generate_problem", return_value=(4, 6, 10)):
        skill.handle_quiz_general(_msg())
    assert skill.get_response.call_count == 5
