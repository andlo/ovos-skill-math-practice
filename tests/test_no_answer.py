"""A question nobody answers ends the quiz (issue: a quiz nobody
answers never ends). On ovos-workshop 7.x get_response() re-prompts
forever by default and holds one of ovos-core's bus threads, so _ask()
bounds the retries and a None answer ends the quiz instead of asking
the next question."""
from unittest.mock import MagicMock

import mathpractice_skill as skill_module


def _msg(**data):
    m = MagicMock()
    m.data = data
    return m


def _said(skill):
    return [c[0][0] for c in skill.speak_dialog.call_args_list]


def test_no_answer_ends_the_quiz_after_the_first_question(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value=None)
    skill.handle_quiz_table(_msg(number="6"))
    assert skill.get_response.call_count == 1
    said = _said(skill)
    assert said.count("quiz_no_answer") == 1
    assert "quiz_finished" not in said
    assert not skill.can_stop(_msg())


def test_no_answer_mid_quiz_ends_it_there(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(side_effect=['0', None, "unused"])
    skill.handle_quiz_table(_msg(number="6"))
    assert skill.get_response.call_count == 2
    said = _said(skill)
    assert said.count("quiz_no_answer") == 1
    assert "quiz_finished" not in said


def test_questions_are_repeated_a_bounded_number_of_times(skill):
    skill.speak_dialog = MagicMock()
    skill.get_response = MagicMock(return_value=None)
    skill.handle_quiz_table(_msg(number="6"))
    kwargs = skill.get_response.call_args[1]
    assert kwargs["num_retries"] == skill_module.ASK_RETRIES >= 1


def test_silence_can_mean_continue(skill):
    """continue_teaching_prompt: silence means 'go on', not 'end'."""
    skill.get_response = MagicMock(return_value=None)
    assert skill._ask(dialog="continue_teaching_prompt", end_on_no_answer=False) is None
