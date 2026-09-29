"""Stop support: a quiz ends when stop is requested for its session,
instead of asking the next question until ovos-core times it out."""
from unittest.mock import MagicMock, patch

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session


def _msg(session_id, **data):
    return Message("test", data, {"session": Session(session_id).serialize()})


def test_stop_ends_the_quiz_in_that_session(skill):
    skill.speak_dialog = MagicMock()
    asked = []

    def answer(*args, **kwargs):
        asked.append(args)
        if len(asked) == 2:
            # stop arrives while waiting for the 2nd answer
            assert skill.can_stop(_msg("s1"))
            assert skill.stop_session(Session("s1")) is True
            return None  # workshop aborts the wait
        return "42"

    skill.get_response = MagicMock(side_effect=answer)
    with patch("mathpractice_skill.generate_problem", return_value=(6, 7, 42)):
        skill.handle_quiz_table(_msg("s1", number="6"))

    assert len(asked) == 2
    said = [c[0][0] for c in skill.speak_dialog.call_args_list]
    assert "quiz_finished" not in said
    assert said.count("quiz_no_answer") == 0
    assert not skill.can_stop(_msg("s1"))  # nothing left to stop
    aborts = [c[0][0] for c in skill.bus.emit.call_args_list
              if c[0][0].msg_type == "mycroft.skills.abort_question"]
    assert len(aborts) == 1 and aborts[0].data["skill_id"] == skill.skill_id
    assert aborts[0].context["session"]["session_id"] == "s1"


def test_stop_for_another_session_does_not_touch_the_quiz(skill):
    skill.speak_dialog = MagicMock()

    def answer(*args, **kwargs):
        assert skill.can_stop(_msg("s1"))
        assert not skill.can_stop(_msg("other"))
        assert skill.stop_session(Session("other")) is False
        return "42"

    skill.get_response = MagicMock(side_effect=answer)
    with patch("mathpractice_skill.generate_problem", return_value=(6, 7, 42)):
        skill.handle_quiz_table(_msg("s1", number="6"))
    assert skill.speak_dialog.call_args_list[-1] == (("quiz_finished", {"correct": 5, "total": 5}), {})


def test_nothing_to_stop_when_idle(skill):
    assert not skill.can_stop(_msg("s1"))
    assert skill.stop_session(Session("s1")) is False
