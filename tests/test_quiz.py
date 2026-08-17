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


def test_quiz_operation_percent_uses_percent_question_dialog(skill):
    """'quiz me on percentages' resolves via operation_aliases.json
    straight through the existing generic quiz_operation.intent - no
    dedicated intent needed, same as any other operation alias."""
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="30")
    with patch("mathpractice_skill.generate_problem", return_value=(20, 150, 30)):
        skill.handle_quiz_operation(_msg(operation="percentage"))
    dialog_name = skill.get_response.call_args_list[0][1]["dialog"]
    assert dialog_name == "quiz_question_percent"


def test_quiz_full_can_pick_percent(skill):
    """Doesn't assert percent specifically gets chosen (random.choice
    isn't mocked here) - just that quiz_full runs successfully against
    the broader ALL_OPERATIONS pool without erroring, and that percent
    is a legal outcome by construction (see
    test_all_operations_includes_percent_but_operations_does_not in
    test_problem_generation.py for the pool membership itself)."""
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="30")
    with patch("mathpractice_skill.generate_problem", return_value=(20, 150, 30)):
        skill.handle_quiz_full(_msg())
    assert skill.get_response.call_count == 5


def test_quiz_full_samples_from_all_operations_not_just_the_classic_four(skill):
    """Confirms handle_quiz_full actually draws from ALL_OPERATIONS
    (which includes percent), not accidentally from OPERATIONS."""
    from mathpractice_skill import ALL_OPERATIONS
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="10")
    with patch("mathpractice_skill.generate_problem", return_value=(4, 6, 10)) as gen, \
            patch("mathpractice_skill.random.choice") as choice:
        choice.return_value = "percent"
        skill.handle_quiz_full(_msg())
        choice.assert_called_once_with(ALL_OPERATIONS)
        gen.assert_called_with("percent", None, "medium")


def test_quiz_operation_difficulty_passes_difficulty_through(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="10")
    with patch("mathpractice_skill.generate_problem", return_value=(4, 6, 10)) as gen:
        skill.handle_quiz_operation_difficulty(_msg(operation="addition", difficulty="hard"))
        gen.assert_called_with("add", None, "hard")


def test_quiz_operation_difficulty_defaults_to_medium_when_no_difficulty_given(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="10")
    with patch("mathpractice_skill.generate_problem", return_value=(4, 6, 10)) as gen:
        skill.handle_quiz_operation_difficulty(_msg(operation="addition"))
        gen.assert_called_with("add", None, "medium")


def test_quiz_operation_difficulty_unknown_difficulty_speaks_error(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock()
    skill.handle_quiz_operation_difficulty(_msg(operation="addition", difficulty="impossible"))
    skill.speak_dialog.assert_called_once_with(
        "difficulty_not_understood", {"difficulty": "impossible"})
    skill.get_response.assert_not_called()


def test_quiz_operation_difficulty_unknown_operation_speaks_error(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock()
    skill.handle_quiz_operation_difficulty(_msg(operation="calculus", difficulty="hard"))
    skill.speak_dialog.assert_called_once_with(
        "operation_not_understood", {"operation": "calculus"})
    skill.get_response.assert_not_called()
