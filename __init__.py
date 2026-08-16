"""
skill OVOS Math Practice
Copyright (C) 2026  Andreas Lorensen

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

---

Math practice for kids (and anyone else) - three distinct modes,
deliberately kept separate rather than folded into one "do math"
intent:

1. COUNTING - "count to ten" - pure recitation, no interaction.
2. TABLE RECITATION - "say the 5 times table" - pure recitation of
   1x5 through 10x5, no interaction. Multiplication only - addition/
   subtraction/division don't have a traditional "table" concept the
   same way, so this mode is deliberately scoped to what "tabeller"
   (the original request) actually means in everyday usage.
3. QUIZ - "quiz me on the 3 times table" / "quiz me on addition" -
   genuinely interactive: asks NUM_QUIZ_QUESTIONS questions one at a
   time via get_response(), checks each spoken answer, and reports a
   final score. Covers all four basic operations, not just
   multiplication - this was an explicit scope correction from the
   original "times tables" framing.

ARCHITECTURE NOTE: get_response(), NOT A BACKGROUND THREAD
-----------------------------------------------------------------
Unlike ovos-skill-metronome/ovos-skill-rhythm-box/ovos-skill-white-
noise, quiz mode needs no background thread - it's a sequential,
blocking conversation (ask, wait for STT to transcribe an answer,
check it, ask the next one) using OVOSSkill.get_response(), which
already handles the listen-and-transcribe round-trip. This is
architecturally simpler than the audio-loop skills, but introduces a
different kind of failure mode: a timed-out or unparseable spoken
answer, handled explicitly per question rather than crashing the
whole quiz.

PROBLEM GENERATION DEFAULTS (state your assumptions, then build)
-----------------------------------------------------------------
- NUM_QUIZ_QUESTIONS = 5 per quiz round.
- Times tables: the traditional 1-12 range.
- Addition/subtraction: operands 1-20, subtraction always kept
  non-negative (larger number first) - a negative answer isn't
  wrong, but wasn't the kind of practice this was built for.
- Division: always divides evenly (dividend is constructed as
  divisor x quotient, both 1-10) - no fractional answers, since
  spoken fraction-checking is a much harder problem than this skill
  attempts to solve.
"""

import json
import random
from pathlib import Path

from ovos_workshop.skills import OVOSSkill
from ovos_workshop.decorators import intent_handler
from ovos_number_parser import extract_number

NUM_QUIZ_QUESTIONS = 5
COUNT_MAX = 100  # sanity cap for "count to X" - not a hard product limit, just avoids absurdly long recitations
TABLE_MIN, TABLE_MAX = 1, 12
ADD_SUB_MIN, ADD_SUB_MAX = 1, 20
DIVIDE_FACTOR_MIN, DIVIDE_FACTOR_MAX = 1, 10

OPERATIONS = ["add", "subtract", "multiply", "divide"]


def generate_problem(operation, table=None):
    """Returns (a, b, correct_answer) for the given operation.
    `table` restricts multiplication to a specific times table (the
    fixed factor); ignored for other operations."""
    if operation == "multiply":
        a = table if table else random.randint(2, TABLE_MAX)
        b = random.randint(1, 10)
        return a, b, a * b
    elif operation == "add":
        a = random.randint(ADD_SUB_MIN, ADD_SUB_MAX)
        b = random.randint(ADD_SUB_MIN, ADD_SUB_MAX)
        return a, b, a + b
    elif operation == "subtract":
        a = random.randint(ADD_SUB_MIN, ADD_SUB_MAX)
        b = random.randint(ADD_SUB_MIN, ADD_SUB_MAX)
        if b > a:
            a, b = b, a  # keep the result non-negative, see module docstring
        return a, b, a - b
    elif operation == "divide":
        divisor = random.randint(DIVIDE_FACTOR_MIN, DIVIDE_FACTOR_MAX)
        quotient = random.randint(DIVIDE_FACTOR_MIN, DIVIDE_FACTOR_MAX)
        dividend = divisor * quotient
        return dividend, divisor, quotient
    raise ValueError(f"unknown operation: {operation!r}")


def multiplication_table(n, up_to=10):
    """Returns [(1, n, 1*n), (2, n, 2*n), ..., (up_to, n, up_to*n)] -
    the actual (factor, table_number, product) rows of a times table,
    for both reciting and quizzing."""
    return [(i, n, i * n) for i in range(1, up_to + 1)]


def addition_table(n, up_to=10):
    """[(n, 1, n+1), (n, 2, n+2), ..., (n, up_to, n+up_to)] -
    'n plus i is n+i'. (a, b, answer) ordering already matches
    quiz_question_add.dialog's 'what is {a} plus {b}' directly."""
    return [(n, i, n + i) for i in range(1, up_to + 1)]


def subtraction_table(n, up_to=10):
    """[(n+1, n, 1), (n+2, n, 2), ..., (n+up_to, n, up_to)] -
    '(n+i) minus n is i'. Fixes n as the subtrahend so results always
    run 1..up_to, staying non-negative - mirrors the same rule
    generate_problem()'s subtract case already applies (larger number
    first). (a, b, answer) ordering matches
    quiz_question_subtract.dialog's 'what is {a} minus {b}'."""
    return [(n + i, n, i) for i in range(1, up_to + 1)]


def division_table(n, up_to=10):
    """[(n*1, n, 1), (n*2, n, 2), ..., (n*up_to, n, up_to)] -
    '(n*i) divided by n is i'. Mirror of multiplication_table, and
    matches generate_problem()'s divide case (dividend = divisor x
    quotient). (a, b, answer) ordering matches
    quiz_question_divide.dialog's 'what is {a} divided by {b}'."""
    return [(n * i, n, i) for i in range(1, up_to + 1)]


# operation -> its "N-facts table" generator, for teach mode. multiply's
# generator returns (varying_factor, fixed_factor, product) rather than
# strict (a, b, answer) order - harmless since multiplication is
# commutative, but the other three DO need the exact order shown above
# since add/subtract/divide are not commutative and the wrong order
# would make quiz_question_{op}.dialog speak a wrong statement.
FACT_TABLE_GENERATORS = {
    "add": addition_table,
    "subtract": subtraction_table,
    "multiply": multiplication_table,
    "divide": division_table,
}


SKILL_ROOT = Path(__file__).resolve().parent
LOCALE_DIR = SKILL_ROOT / "locale"


def _load_operation_aliases_from_disk():
    """locale/<lang>/operation_aliases.json - {spoken operation name:
    key in OPERATIONS}. Same JSON-in-locale convention as the rest of
    this project family."""
    merged = {}
    if not LOCALE_DIR.is_dir():
        return merged
    for lang_dir in sorted(LOCALE_DIR.iterdir()):
        if not lang_dir.is_dir():
            continue
        alias_file = lang_dir / "operation_aliases.json"
        if not alias_file.exists():
            continue
        with open(alias_file, encoding="utf-8") as f:
            aliases = json.load(f)
        lang = lang_dir.name.lower()
        merged[lang] = {k: v for k, v in aliases.items() if not k.startswith("_")}
    return merged


OPERATION_ALIASES = _load_operation_aliases_from_disk()


class MathPractice(OVOSSkill):

    def initialize(self):
        # Session-only, not persisted across restarts - see README
        # "Shared pattern: teach-then-practice" for why (deliberately
        # simple for v1, tracked as a possible future upgrade rather
        # than built speculatively).
        self._taught_facts = []
        self._taught_operation = "multiply"

    def _speak_number_not_understood(self):
        self.speak_dialog("number_not_understood")

    def _operation_aliases_for(self, lang):
        lang = lang.lower()
        return OPERATION_ALIASES.get(lang) or OPERATION_ALIASES.get("en-us", {})

    def _resolve_operation(self, raw, lang):
        """Exact match only, no fuzzy matching - same reasoning as
        every other alias resolver in this project family: quizzing
        someone on the wrong operation is a more confusing wrong
        answer than a slightly mis-parsed number."""
        if not raw:
            return None
        return self._operation_aliases_for(lang).get(raw.strip().lower())

    # ------------------------------------------------------------------
    # Counting
    # ------------------------------------------------------------------

    @intent_handler("count_to.intent")
    def handle_count_to(self, message):
        n_raw = message.data.get("number")
        n = extract_number(n_raw, lang=self.lang) if n_raw else None
        if n is False or n is None or n < 1:
            self._speak_number_not_understood()
            return
        n = int(n)
        if n > COUNT_MAX:
            self.speak_dialog("count_too_high", {"max": COUNT_MAX})
            return
        numbers = ", ".join(str(i) for i in range(1, n + 1))
        self.speak_dialog("counting", {"numbers": numbers})

    # ------------------------------------------------------------------
    # Table recitation
    # ------------------------------------------------------------------

    def _render_table_recitation(self, n):
        """Builds the full 'one times N is ..., two times N is ...'
        recitation by rendering table_row.dialog once per row (with
        that row's own data) rather than speaking each row as a
        separate utterance - keeps the per-row phrasing localized in
        table_row.dialog while still producing one continuous spoken
        response."""
        lines = []
        for i, table_n, product in multiplication_table(n):
            rendered = self.resources.load_dialog_file(
                "table_row", {"i": i, "n": table_n, "product": product})
            lines.append(rendered[0])
        return ". ".join(lines)

    @intent_handler("recite_table.intent")
    def handle_recite_table(self, message):
        n_raw = message.data.get("number")
        n = extract_number(n_raw, lang=self.lang) if n_raw else None
        if n is False or n is None or n < 1:
            self._speak_number_not_understood()
            return
        n = int(n)
        self.speak(self._render_table_recitation(n))

    # ------------------------------------------------------------------
    # Quiz
    # ------------------------------------------------------------------

    def _ask_question(self, operation, a, b):
        """Speaks the question and listens for a spoken answer -
        returns the transcribed text, or None on timeout/no response."""
        return self.get_response(dialog=f"quiz_question_{operation}", data={"a": a, "b": b})

    def _ask_and_grade(self, operation, a, b, answer):
        """Asks one question and speaks correct/incorrect feedback.
        Returns True if the answer was correct, False otherwise
        (including no-response). Shared by _run_quiz() (fresh random
        problems) and _run_quiz_from_facts() (a fixed, previously-
        taught set) so both go through identical grading logic."""
        response_text = self._ask_question(operation, a, b)
        if response_text is None:
            self.speak_dialog("quiz_no_answer")
            return False
        user_value = extract_number(response_text, lang=self.lang)
        if user_value is not False and user_value == answer:
            self.speak_dialog("quiz_correct")
            return True
        self.speak_dialog("quiz_incorrect", {"answer": answer})
        return False

    def _run_quiz(self, operation, table=None):
        correct_count = 0
        for _ in range(NUM_QUIZ_QUESTIONS):
            a, b, answer = generate_problem(operation, table)
            if self._ask_and_grade(operation, a, b, answer):
                correct_count += 1
        self.speak_dialog("quiz_finished", {"correct": correct_count, "total": NUM_QUIZ_QUESTIONS})

    def _run_quiz_from_facts(self, facts, operation="multiply"):
        """Quizzes on a FIXED set of previously-taught facts, rather
        than freshly generating random problems - the 'practice what
        you were taught' half of the teach-then-practice pattern (see
        README). Reuses the exact same per-question grading as
        _run_quiz() via _ask_and_grade()."""
        correct_count = 0
        total = len(facts)
        for a, b, answer in facts:
            if self._ask_and_grade(operation, a, b, answer):
                correct_count += 1
        self.speak_dialog("quiz_finished", {"correct": correct_count, "total": total})

    @intent_handler("quiz_table.intent")
    def handle_quiz_table(self, message):
        n_raw = message.data.get("number")
        n = extract_number(n_raw, lang=self.lang) if n_raw else None
        if n is False or n is None or n < 1:
            self._speak_number_not_understood()
            return
        self._run_quiz("multiply", table=int(n))

    @intent_handler("quiz_operation.intent")
    def handle_quiz_operation(self, message):
        operation_raw = message.data.get("operation")
        operation = self._resolve_operation(operation_raw, self.lang) if operation_raw else None
        if operation_raw and operation is None:
            self.speak_dialog("operation_not_understood", {"operation": operation_raw})
            return
        operation = operation or random.choice(OPERATIONS)
        self._run_quiz(operation)

    @intent_handler("quiz_general.intent")
    def handle_quiz_general(self, message):
        self._run_quiz(random.choice(OPERATIONS))

    # ------------------------------------------------------------------
    # Teach-then-practice (see README "Shared pattern: teach-then-
    # practice" and the tracked design issue for the full rationale
    # and open questions)
    # ------------------------------------------------------------------

    def _teach_facts_for_operation(self, operation, n):
        """Shared by handle_teach_me() (multiply-only, the original
        'times table' phrasing) and handle_teach_me_operation() (any
        of the four operations). Speaks each row of the operation's
        N-facts table in turn, offers a 'repeat' before moving to the
        next row, and records exactly which facts were presented -
        both the facts themselves and which operation they belong to,
        so the follow-up quiz asks about them correctly."""
        self._taught_facts = []
        self._taught_operation = operation
        generator = FACT_TABLE_GENERATORS[operation]
        rows = generator(n)
        # multiply keeps using table_row.dialog (its original field
        # names {i,n,product}) for backward compatibility with
        # recite_table, which also depends on that exact dialog -
        # add/subtract/divide are new, so they get a clean {a,b,answer}
        # dialog matching the (a, b, answer) tuples the generators
        # above already produce.
        for idx, row in enumerate(rows):
            if operation == "multiply":
                i, table_n, product = row
                rendered = self.resources.load_dialog_file(
                    "table_row", {"i": i, "n": table_n, "product": product})[0]
                fact = (i, table_n, product)
            else:
                a, b, answer = row
                rendered = self.resources.load_dialog_file(
                    f"teach_row_{operation}", {"a": a, "b": b, "answer": answer})[0]
                fact = (a, b, answer)

            self.speak(rendered, wait=True)
            self._taught_facts.append(fact)

            if idx == len(rows) - 1:
                break
            response = self.get_response(dialog="continue_teaching_prompt")
            if response and self.voc_match(response, "repeat"):
                self.speak(rendered, wait=True)

        self.speak_dialog("teaching_finished", {"count": len(self._taught_facts)})

    @intent_handler("teach_me.intent")
    def handle_teach_me(self, message):
        n_raw = message.data.get("number")
        n = extract_number(n_raw, lang=self.lang) if n_raw else None
        if n is False or n is None or n < 1:
            self._speak_number_not_understood()
            return
        self._teach_facts_for_operation("multiply", int(n))

    @intent_handler("teach_me_operation.intent")
    def handle_teach_me_operation(self, message):
        operation_raw = message.data.get("operation")
        operation = self._resolve_operation(operation_raw, self.lang) if operation_raw else None
        if operation is None:
            self.speak_dialog("operation_not_understood", {"operation": operation_raw or ""})
            return
        n_raw = message.data.get("number")
        n = extract_number(n_raw, lang=self.lang) if n_raw else None
        if n is False or n is None or n < 1:
            self._speak_number_not_understood()
            return
        self._teach_facts_for_operation(operation, int(n))

    @intent_handler("quiz_taught.intent")
    def handle_quiz_taught(self, message):
        if not self._taught_facts:
            self.speak_dialog("nothing_taught_yet")
            return
        self._run_quiz_from_facts(self._taught_facts, operation=self._taught_operation)
