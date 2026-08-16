"""Shared pytest fixtures for the math-practice skill test suite."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_INIT_PATH = Path(__file__).resolve().parents[1] / "__init__.py"
_spec = importlib.util.spec_from_file_location("mathpractice_skill", _INIT_PATH)
_module = importlib.util.module_from_spec(_spec)
sys.modules["mathpractice_skill"] = _module
_spec.loader.exec_module(_module)

MathPractice = _module.MathPractice


@pytest.fixture
def skill(monkeypatch):
    s = MathPractice.__new__(MathPractice)
    s.log = MagicMock()
    s.skill_id = "ovos-skill-math-practice.test"
    s.status = MagicMock()
    s._bus = MagicMock()
    monkeypatch.setattr(MathPractice, "lang", "en-us", raising=False)
    s.res_dir = str(Path(__file__).resolve().parents[1])
    s._lang_resources = {}
    return s
