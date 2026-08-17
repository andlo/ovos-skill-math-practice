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


def test_quiz_chain_uses_expression_dialog_and_grades_final_answer(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="4")
    with patch("mathpractice_skill.generate_chain_problem", return_value=([7, 2, 1], 4)):
        skill.handle_quiz_chain(_msg(operation="subtraction"))
    dialog_name = skill.get_response.call_args_list[0][1]["dialog"]
    assert dialog_name == "quiz_question_expression"
    expression = skill.get_response.call_args_list[0][1]["data"]["expression"]
    assert expression == "7 minus 2 minus 1"
    correct_calls = [c for c in skill.speak_dialog.call_args_list if c[0][0] == "quiz_correct"]
    assert len(correct_calls) == 5  # NUM_QUIZ_QUESTIONS, answered correctly every time


def test_quiz_chain_unknown_operation_speaks_error(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock()
    skill.handle_quiz_chain(_msg(operation="calculus"))
    skill.speak_dialog.assert_called_once_with(
        "operation_not_understood", {"operation": "calculus"})
    skill.get_response.assert_not_called()


def test_quiz_chain_defaults_to_a_random_operation_when_none_given(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="10")
    with patch("mathpractice_skill.generate_chain_problem", return_value=([4, 3, 2], 9)):
        skill.handle_quiz_chain(_msg())
    assert skill.get_response.call_count == 5


def test_quiz_mixed_uses_expression_dialog_and_grades_final_answer(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="10")
    with patch("mathpractice_skill.generate_mixed_problem", return_value=(4, "add", 3, "multiply", 2, 10)):
        skill.handle_quiz_mixed(_msg())
    dialog_name = skill.get_response.call_args_list[0][1]["dialog"]
    assert dialog_name == "quiz_question_expression"
    expression = skill.get_response.call_args_list[0][1]["data"]["expression"]
    assert expression == "4 plus 3 times 2"
    correct_calls = [c for c in skill.speak_dialog.call_args_list if c[0][0] == "quiz_correct"]
    assert len(correct_calls) == 5


def _fixed_estimate_problem():
    """a=350, operation=multiply, b=5500, answer=1925000, with two
    fixed distractors at indices 0 and 2, correct answer at index 1 -
    a deterministic stand-in for generate_estimate_problem()."""
    choices = [999999, 1925000, 3850000]
    return 350, "multiply", 5500, 1925000, choices, 1


def test_quiz_estimate_speaks_expression_and_all_three_lettered_choices(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="B")
    skill.voc_match = MagicMock(side_effect=lambda utt, voc: voc == "choice_b" and utt == "B")
    with patch("mathpractice_skill.generate_estimate_problem", return_value=_fixed_estimate_problem()):
        skill.handle_quiz_estimate(_msg())
    dialog_name = skill.get_response.call_args_list[0][1]["dialog"]
    data = skill.get_response.call_args_list[0][1]["data"]
    assert dialog_name == "quiz_question_estimate"
    assert data["expression"] == "350 times 5500"
    assert data["choice_a"] == 999999
    assert data["choice_b"] == 1925000
    assert data["choice_c"] == 3850000


def test_quiz_estimate_correct_letter_answer_is_graded_correct(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="B")
    skill.voc_match = MagicMock(side_effect=lambda utt, voc: voc == "choice_b" and utt == "B")
    with patch("mathpractice_skill.generate_estimate_problem", return_value=_fixed_estimate_problem()):
        skill.handle_quiz_estimate(_msg())
    correct_calls = [c for c in skill.speak_dialog.call_args_list if c[0][0] == "quiz_correct"]
    assert len(correct_calls) == 5


def test_quiz_estimate_correct_number_spoken_instead_of_letter_still_counts(skill):
    """Saying the number itself ('1925000') instead of the letter
    should still be graded correct, per issue #8's fallback."""
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="1925000")
    skill.voc_match = MagicMock(return_value=False)  # doesn't match any letter voc
    with patch("mathpractice_skill.generate_estimate_problem", return_value=_fixed_estimate_problem()):
        skill.handle_quiz_estimate(_msg())
    correct_calls = [c for c in skill.speak_dialog.call_args_list if c[0][0] == "quiz_correct"]
    assert len(correct_calls) == 5


def test_quiz_estimate_wrong_letter_speaks_estimate_incorrect_with_correct_choice(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="A")
    skill.voc_match = MagicMock(side_effect=lambda utt, voc: voc == "choice_a" and utt == "A")
    with patch("mathpractice_skill.generate_estimate_problem", return_value=_fixed_estimate_problem()):
        skill.handle_quiz_estimate(_msg())
    incorrect_calls = [c for c in skill.speak_dialog.call_args_list if c[0][0] == "estimate_incorrect"]
    assert len(incorrect_calls) == 5
    assert incorrect_calls[0] == (("estimate_incorrect", {"letter": "B", "value": 1925000}), {})


def test_quiz_estimate_no_response_counts_as_wrong_but_does_not_crash(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value=None)
    with patch("mathpractice_skill.generate_estimate_problem", return_value=_fixed_estimate_problem()):
        skill.handle_quiz_estimate(_msg())
    no_answer_calls = [c for c in skill.speak_dialog.call_args_list if c[0][0] == "quiz_no_answer"]
    assert len(no_answer_calls) == 5
    final_call = skill.speak_dialog.call_args_list[-1]
    assert final_call == (("quiz_finished", {"correct": 0, "total": 5}), {})


def test_quiz_decimal_uses_existing_question_dialog_and_grades_with_epsilon(skill):
    """Reuses quiz_question_add.dialog directly (no decimal-specific
    dialog file), and treats a closely-matching float as correct even
    if it's not bit-for-bit equal, per DECIMAL_GRADING_EPSILON."""
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="9.8")
    with patch("mathpractice_skill.generate_decimal_problem", return_value=(7.3, 2.5, 9.8)):
        skill.handle_quiz_decimal(_msg(operation="addition"))
    dialog_name = skill.get_response.call_args_list[0][1]["dialog"]
    assert dialog_name == "quiz_question_add"
    data = skill.get_response.call_args_list[0][1]["data"]
    assert data == {"a": 7.3, "b": 2.5}
    correct_calls = [c for c in skill.speak_dialog.call_args_list if c[0][0] == "quiz_correct"]
    assert len(correct_calls) == 5


def test_quiz_decimal_wrong_answer_speaks_quiz_incorrect(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="0")
    with patch("mathpractice_skill.generate_decimal_problem", return_value=(7.3, 2.5, 9.8)):
        skill.handle_quiz_decimal(_msg(operation="addition"))
    final_call = skill.speak_dialog.call_args_list[-1]
    assert final_call == (("quiz_finished", {"correct": 0, "total": 5}), {})


def test_quiz_decimal_unknown_operation_speaks_error(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock()
    skill.handle_quiz_decimal(_msg(operation="calculus"))
    skill.speak_dialog.assert_called_once_with(
        "operation_not_understood", {"operation": "calculus"})
    skill.get_response.assert_not_called()


def test_quiz_decimal_defaults_to_a_random_operation_when_none_given(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value="9.8")
    with patch("mathpractice_skill.generate_decimal_problem", return_value=(7.3, 2.5, 9.8)):
        skill.handle_quiz_decimal(_msg())
    assert skill.get_response.call_count == 5
