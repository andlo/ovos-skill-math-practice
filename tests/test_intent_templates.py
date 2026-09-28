"""ovos-workshop 9.x (the OVOS alpha channel) rejects intent templates
with two slots next to each other ('{difficulty} {operation}'), which
dropped quiz_operation_difficulty.intent entirely there. The difficulty
is now a fixed word list in the template, picked out of the utterance."""
import json
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

LOCALE = Path(__file__).resolve().parents[1] / "locale"


@pytest.mark.parametrize("path", sorted(LOCALE.glob("*/*.intent")), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_no_intent_line_has_two_slots_next_to_each_other(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        assert not re.search(r"\}\s*\{", line), f"adjacent slots in {path}: {line!r}"


@pytest.mark.parametrize("lang_dir", sorted(p for p in LOCALE.iterdir() if (p / "quiz_operation_difficulty.intent").exists()),
                         ids=lambda p: p.name)
def test_difficulty_words_in_the_template_match_difficulty_aliases(lang_dir):
    aliases = {k for k in json.loads((lang_dir / "difficulty_aliases.json").read_text(encoding="utf-8")) if not k.startswith("_")}
    for line in (lang_dir / "quiz_operation_difficulty.intent").read_text(encoding="utf-8").splitlines():
        words = set(re.search(r"\(([^)]*)\)", line).group(1).split("|"))
        assert words == aliases, f"{lang_dir.name}: {line!r} - update it from difficulty_aliases.json"


@pytest.mark.parametrize("utterance,lang,expected", [
    ("quiz me on hard addition", "en-us", "hard"),
    ("test me on easy multiplication", "en-us", "easy"),
    ("quiz mig i svær addition", "da-dk", "svær"),
    ("quiz me on addition", "en-us", None),
])
def test_difficulty_is_picked_out_of_the_utterance(skill, utterance, lang, expected):
    assert skill._difficulty_in(utterance, lang) == expected


def test_handler_uses_the_difficulty_from_the_utterance(skill, monkeypatch):
    runs = []
    monkeypatch.setattr(skill, "_run_quiz", lambda op, difficulty=None: runs.append((op, difficulty)), raising=False)
    monkeypatch.setattr(skill, "speak_dialog", MagicMock(), raising=False)
    op_alias = next(k for k in skill._operation_aliases_for("en-us"))
    skill.handle_quiz_operation_difficulty(MagicMock(data={"operation": op_alias, "utterance": f"quiz me on hard {op_alias}"}))
    assert runs == [(skill._resolve_operation(op_alias, "en-us"), "hard")]
