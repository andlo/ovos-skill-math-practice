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

Math practice for kids (and anyone else): counting, times-table
recitation, teach-then-practice, and interactive quizzes across
addition/subtraction/multiplication/division plus percentages,
difficulty levels, chained and mixed-operator problems, an
estimation mode, and one-decimal-place arithmetic.

See README.md for the full feature list, example utterances, and
per-mode explanations, and DEVELOPMENT.md's "Architecture at a
glance" for the design rationale behind each mode (including which
GitHub issue introduced it) - kept out of this docstring so it lives
in exactly one place rather than drifting out of sync with itself.
"""

import json
import math
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
PERCENT_MIN, PERCENT_MAX = 1, 100
# mirrors DIVIDE_FACTOR's 1-10 "how many times the smallest valid base" range
PERCENT_BASE_MULTIPLIER_MIN, PERCENT_BASE_MULTIPLIER_MAX = 1, 10

DIFFICULTIES = ["easy", "medium", "hard"]

# Per-operation ranges by difficulty tier. "medium" is deliberately
# built FROM the constants above rather than duplicated as literals -
# single source of truth, and it's exactly what every operation
# already did before difficulty existed, so existing behavior at the
# default difficulty is unchanged. multiply's ranges are split into
# the varying factor (used when no explicit table is requested) and
# the "other" factor (1-10 today) - table quizzing itself
# (quiz_table.intent) doesn't take a difficulty, only the general
# multiply operation does. percent only varies its base multiplier by
# difficulty, not the percentage range itself (1-100 stays constant -
# a "hard" 97% is not meaningfully harder to compute than an "easy"
# 10%, but a bigger base number is).
DIFFICULTY_RANGES = {
    "easy": {
        "add": (1, 10),
        "subtract": (1, 10),
        "multiply_factor": (2, 5),
        "multiply_other": (1, 5),
        "divide": (1, 5),
        "percent_multiplier": (1, 5),
    },
    "medium": {
        "add": (ADD_SUB_MIN, ADD_SUB_MAX),
        "subtract": (ADD_SUB_MIN, ADD_SUB_MAX),
        "multiply_factor": (2, TABLE_MAX),
        "multiply_other": (1, 10),
        "divide": (DIVIDE_FACTOR_MIN, DIVIDE_FACTOR_MAX),
        "percent_multiplier": (PERCENT_BASE_MULTIPLIER_MIN, PERCENT_BASE_MULTIPLIER_MAX),
    },
    "hard": {
        "add": (1, 100),
        "subtract": (1, 100),
        "multiply_factor": (2, TABLE_MAX),
        "multiply_other": (1, 20),
        "divide": (1, 20),
        "percent_multiplier": (1, 30),
    },
}

# Chained (issue #3) and mixed-operator (issue #4) problems are NOT
# difficulty-aware for v1 - deliberately scoped down, same "simple
# for v1, revisit if it's a real limitation" choice as taught facts
# staying session-only. They use their own fixed ranges below rather
# than plugging into DIFFICULTY_RANGES.
NUM_CHAIN_OPERANDS = 3
CHAIN_MIN, CHAIN_MAX = 1, 20  # per-leg range for chained add/subtract, mirrors ADD_SUB's medium range
# smaller than CHAIN_MIN/MAX - keeps a 3-operand product speakable
# (20*20*20 would be an unwieldy answer to say out loud)
CHAIN_MULTIPLY_MIN, CHAIN_MULTIPLY_MAX = 2, 9
CHAIN_DIVIDE_MIN, CHAIN_DIVIDE_MAX = 1, 10  # per-divisor range, mirrors DIVIDE_FACTOR's medium range

# Estimation mode (issue #8) - large-number multiple-choice, not a
# computed spoken number. Applies to multiply/divide only (the
# pedagogical need - "is this roughly right" number sense - doesn't
# apply the same way to small add/subtract results).
ESTIMATE_NUM_CHOICES = 3
ESTIMATE_LETTERS = ["A", "B", "C"]  # length must match ESTIMATE_NUM_CHOICES
ESTIMATE_OPERATIONS = ["multiply", "divide"]
ESTIMATE_MULTIPLY_A_MIN, ESTIMATE_MULTIPLY_A_MAX = 100, 999
ESTIMATE_MULTIPLY_B_MIN, ESTIMATE_MULTIPLY_B_MAX = 1000, 9999
ESTIMATE_DIVIDE_DIVISOR_MIN, ESTIMATE_DIVIDE_DIVISOR_MAX = 10, 99
ESTIMATE_DIVIDE_QUOTIENT_MIN, ESTIMATE_DIVIDE_QUOTIENT_MAX = 100, 9999

# Decimal arithmetic (issue #5, decimals half only - fractions are a
# deliberately separate, later design pass, see the issue). Exactly
# one decimal place throughout - see generate_decimal_problem()'s
# docstring for why every decimal problem here is constructed to be
# EXACT rather than needing a genuine tolerance band.
DECIMAL_ADD_SUB_MIN, DECIMAL_ADD_SUB_MAX = 1, 20  # mirrors ADD_SUB's medium range
DECIMAL_MULTIPLY_MIN, DECIMAL_MULTIPLY_MAX = 1, 12
DECIMAL_DIVIDE_QUOTIENT_MIN, DECIMAL_DIVIDE_QUOTIENT_MAX = 1, 12
DECIMAL_DIVIDE_DIVISOR_MIN, DECIMAL_DIVIDE_DIVISOR_MAX = 1, 10
# Guards against float-representation quirks after two independent
# float() conversions (the generated answer's, and extract_number()'s
# parse of the spoken response) - NOT a pedagogical estimation
# tolerance. Every decimal problem here is exact by construction.
DECIMAL_GRADING_EPSILON = 0.01

# The classic four - what "quiz me on math" / "give me a math quiz"
# (quiz_general.intent) randomizes across. Deliberately NOT auto-grown
# by every new operation - see ALL_OPERATIONS below and issue #7's
# discussion of why percent stays out of this pool by design.
OPERATIONS = ["add", "subtract", "multiply", "divide"]

# Every operation this skill can quiz on, including ones with their own
# dedicated architecture (percent has no fact-table/teach-mode
# equivalent). "give me a full math quiz" (quiz_full.intent) samples
# from this broader pool; the classic OPERATIONS pool above is
# untouched by additions here, so new operations don't retroactively
# change what "give me a math quiz" means.
ALL_OPERATIONS = OPERATIONS + ["percent"]


def generate_problem(operation, table=None, difficulty="medium"):
    """Returns (a, b, correct_answer) for the given operation.
    `table` restricts multiplication to a specific times table (the
    fixed factor); ignored for other operations. `difficulty` selects
    the per-operation range from DIFFICULTY_RANGES - "medium" (the
    default) reproduces the exact ranges this function always used
    before difficulty existed."""
    if difficulty not in DIFFICULTY_RANGES:
        raise ValueError(f"unknown difficulty: {difficulty!r}")
    ranges = DIFFICULTY_RANGES[difficulty]
    if operation == "multiply":
        factor_min, factor_max = ranges["multiply_factor"]
        other_min, other_max = ranges["multiply_other"]
        a = table if table else random.randint(factor_min, factor_max)
        b = random.randint(other_min, other_max)
        return a, b, a * b
    elif operation == "add":
        lo, hi = ranges["add"]
        a = random.randint(lo, hi)
        b = random.randint(lo, hi)
        return a, b, a + b
    elif operation == "subtract":
        lo, hi = ranges["subtract"]
        a = random.randint(lo, hi)
        b = random.randint(lo, hi)
        if b > a:
            a, b = b, a  # keep the result non-negative, see module docstring
        return a, b, a - b
    elif operation == "divide":
        lo, hi = ranges["divide"]
        divisor = random.randint(lo, hi)
        quotient = random.randint(lo, hi)
        dividend = divisor * quotient
        return dividend, divisor, quotient
    elif operation == "percent":
        # constructed backwards, like divide: pick the percentage
        # first, then build a base that's guaranteed to make
        # percent/100*base an integer, rather than picking both
        # numbers freely and hoping - same "always divides evenly"
        # rule as divide, no rounding/tolerance needed for v1 (see
        # issue #5 for the tolerance-band discussion that decimals/
        # fractions will eventually need). Only the base multiplier
        # varies by difficulty, not the percentage range itself - see
        # DIFFICULTY_RANGES comment.
        percent = random.randint(PERCENT_MIN, PERCENT_MAX)
        smallest_valid_base = 100 // math.gcd(percent, 100)
        mult_lo, mult_hi = ranges["percent_multiplier"]
        base = smallest_valid_base * random.randint(mult_lo, mult_hi)
        answer = percent * base // 100
        return percent, base, answer
    raise ValueError(f"unknown operation: {operation!r}")


def generate_chain_problem(operation, n=NUM_CHAIN_OPERANDS):
    """Returns (operands, answer) for a same-operator chain of n
    operands evaluated left to right, e.g. operands=[7, 2, 1] ->
    answer=4 for subtract ((7-2)-1). subtract and divide are
    constructed so every INTERMEDIATE step stays valid (non-negative
    / evenly divides), not just the final result - a naive "pick n
    numbers independently" chain does NOT guarantee that (see issue
    #3). Only the classic four chain - percent has no natural chained
    form."""
    if operation == "add":
        operands = [random.randint(CHAIN_MIN, CHAIN_MAX) for _ in range(n)]
        return operands, sum(operands)
    elif operation == "multiply":
        operands = [random.randint(CHAIN_MULTIPLY_MIN, CHAIN_MULTIPLY_MAX) for _ in range(n)]
        answer = 1
        for o in operands:
            answer *= o
        return operands, answer
    elif operation == "subtract":
        # Built forward, not by picking n numbers and hoping: each
        # delta is capped by the RUNNING total (min(CHAIN_MAX,
        # running)), so subtraction can never go negative at any
        # intermediate step, not just the final one.
        first = random.randint(CHAIN_MIN, CHAIN_MAX)
        operands = [first]
        running = first
        for _ in range(n - 1):
            delta_max = max(0, min(CHAIN_MAX, running))
            delta = random.randint(1, delta_max) if delta_max > 0 else 0
            operands.append(delta)
            running -= delta
        return operands, running
    elif operation == "divide":
        # Built backward, mirroring generate_problem()'s divide case:
        # pick the final quotient first, then multiply UP by n-1
        # random divisors to construct a dividend guaranteed to
        # divide evenly at every intermediate step, not just overall.
        quotient = random.randint(CHAIN_DIVIDE_MIN, CHAIN_DIVIDE_MAX)
        divisors = [random.randint(CHAIN_DIVIDE_MIN, CHAIN_DIVIDE_MAX) for _ in range(n - 1)]
        dividend = quotient
        for d in divisors:
            dividend *= d
        return [dividend] + divisors, quotient
    raise ValueError(f"unknown chain operation: {operation!r}")


def generate_mixed_problem():
    """Returns (a, op1, b, op2, c, answer) for a 3-operand expression
    with exactly one +/- operator and one x/÷ operator (never two
    from the same precedence tier - that's just a same-operator chain,
    not an order-of-operations question, see issue #4). op1 is
    whichever operator is spoken FIRST, left to right - e.g.
    (a="add", "multiply") means "a plus b times c", evaluated as
    a + (b*c); (a="multiply", "add") means "a times b plus c",
    evaluated as (a*b) + c. Constructed, not rejection-sampled, so
    subtraction/division legs stay non-negative/exact - same
    philosophy as every other generator in this module."""
    add_op = random.choice(["add", "subtract"])
    mul_op = random.choice(["multiply", "divide"])
    mul_first = random.choice([True, False])

    if mul_first:
        # (a MUL_OP b) ADD_OP c - spoken "a mul_op b add_op c"
        if mul_op == "multiply":
            a = random.randint(CHAIN_MULTIPLY_MIN, CHAIN_MULTIPLY_MAX)
            b = random.randint(CHAIN_MULTIPLY_MIN, CHAIN_MULTIPLY_MAX)
            inner = a * b
        else:
            b = random.randint(CHAIN_DIVIDE_MIN, CHAIN_DIVIDE_MAX)
            inner = random.randint(CHAIN_DIVIDE_MIN, CHAIN_DIVIDE_MAX)
            a = b * inner
        if add_op == "add":
            c = random.randint(CHAIN_MIN, CHAIN_MAX)
            answer = inner + c
        else:
            c = random.randint(0, inner)  # keeps inner - c non-negative
            answer = inner - c
        return a, mul_op, b, add_op, c, answer
    else:
        # a ADD_OP (b MUL_OP c) - spoken "a add_op b mul_op c"
        if mul_op == "multiply":
            b = random.randint(CHAIN_MULTIPLY_MIN, CHAIN_MULTIPLY_MAX)
            c = random.randint(CHAIN_MULTIPLY_MIN, CHAIN_MULTIPLY_MAX)
            inner = b * c
        else:
            c = random.randint(CHAIN_DIVIDE_MIN, CHAIN_DIVIDE_MAX)
            inner = random.randint(CHAIN_DIVIDE_MIN, CHAIN_DIVIDE_MAX)
            b = c * inner
        if add_op == "add":
            a = random.randint(CHAIN_MIN, CHAIN_MAX)
            answer = a + inner
        else:
            a = inner + random.randint(0, CHAIN_MAX)  # keeps a - inner non-negative
            answer = a - inner
        return a, add_op, b, mul_op, c, answer


def _round_to_nice(n, base):
    """Rounds n to the nearest multiple of base, never to 0 (falls
    back to base itself) - used to build a 'rounded one factor before
    computing' estimation distractor (issue #8), not just noise. e.g.
    _round_to_nice(5273, 500) -> 5500."""
    rounded = round(n / base) * base
    return rounded if rounded != 0 else base


def _dedupe_candidates(candidates):
    """Nudges any duplicate values up by 1 until every value in the
    list is distinct - collisions between the real answer and a
    distractor are extremely unlikely given the magnitudes involved
    here, but a multiple-choice question can never present two
    identical options."""
    seen = set()
    unique = []
    for value in candidates:
        while value in seen:
            value += 1
        seen.add(value)
        unique.append(value)
    return unique


def generate_estimate_problem():
    """Returns (a, operation, b, answer, choices, correct_index) for
    a large-number multiple-choice estimation question (issue #8) -
    genuinely different from the regular quiz: the user picks a
    letter, not a computed spoken number (an 8-digit answer read
    aloud is both awkward to say and a harder STT case than a 2-digit
    one). `choices` is ESTIMATE_NUM_CHOICES candidate values (the
    real answer plus DISTRACTORS built from two plausible estimation
    mistakes, not random noise), already shuffled; `correct_index`
    says which slot holds the real answer.

    Distractor strategies (both used, not randomly chosen among many,
    so every question exercises both):
    1. A decimal-place slip - the real answer x10 or /10, the classic
       "moved the decimal/forgot a zero" mistake.
    2. A rounding-based near-miss - recompute with ONE factor rounded
       to a nearby 'nice' number instead of the exact one, a genuine
       mis-estimate rather than an arbitrary offset.
    """
    operation = random.choice(ESTIMATE_OPERATIONS)
    if operation == "multiply":
        a = random.randint(ESTIMATE_MULTIPLY_A_MIN, ESTIMATE_MULTIPLY_A_MAX)
        b = random.randint(ESTIMATE_MULTIPLY_B_MIN, ESTIMATE_MULTIPLY_B_MAX)
        answer = a * b
        distractor_1 = answer * 10 if random.choice([True, False]) else max(1, answer // 10)
        if random.choice([True, False]):
            distractor_2 = _round_to_nice(a, 100) * b
        else:
            distractor_2 = a * _round_to_nice(b, 500)
    else:  # divide - built backward so it always divides evenly, same as generate_problem()
        divisor = random.randint(ESTIMATE_DIVIDE_DIVISOR_MIN, ESTIMATE_DIVIDE_DIVISOR_MAX)
        quotient = random.randint(ESTIMATE_DIVIDE_QUOTIENT_MIN, ESTIMATE_DIVIDE_QUOTIENT_MAX)
        a = divisor * quotient
        b = divisor
        answer = quotient
        distractor_1 = quotient * 10 if random.choice([True, False]) else max(1, quotient // 10)
        distractor_2 = a // _round_to_nice(divisor, 10)

    answer, distractor_1, distractor_2 = _dedupe_candidates([answer, distractor_1, distractor_2])
    choices = [answer, distractor_1, distractor_2]
    random.shuffle(choices)
    correct_index = choices.index(answer)
    return a, operation, b, answer, choices, correct_index


def generate_decimal_problem(operation):
    """Returns (a, b, answer) for a one-decimal-place question, e.g.
    (7.3, 2.5, 9.8) for add. All arithmetic is done in integer TENTHS
    internally (7.3 -> 73) and converted to a float only once, at the
    very end - avoids floating-point accumulation error (never risks
    something like 0.1 + 0.2 = 0.30000000000000004 turning up as the
    'correct' answer). Division is built backward, like every other
    divide in this module, so it always divides evenly to exactly one
    decimal place.

    This SIDESTEPS issue #5's open tolerance-band question rather
    than answering it: every decimal problem here is exact by
    construction, so grading only needs DECIMAL_GRADING_EPSILON (a
    float-representation guard, not a real tolerance band) - not a
    general solution to genuinely irrational quantities (e.g.
    ovos-skill-unit-practice's meter-to-mile conversion, which can
    never be exact), just this skill's own resolution for arithmetic
    that CAN be constructed exact.

    Multiply uses only ONE decimal operand (the other a whole number)
    - two decimal operands multiplied would need TWO decimal places
    to stay exact, widening scope beyond what's stated here."""
    if operation == "add":
        a_tenths = random.randint(DECIMAL_ADD_SUB_MIN * 10, DECIMAL_ADD_SUB_MAX * 10)
        b_tenths = random.randint(DECIMAL_ADD_SUB_MIN * 10, DECIMAL_ADD_SUB_MAX * 10)
        return a_tenths / 10, b_tenths / 10, (a_tenths + b_tenths) / 10
    elif operation == "subtract":
        a_tenths = random.randint(DECIMAL_ADD_SUB_MIN * 10, DECIMAL_ADD_SUB_MAX * 10)
        b_tenths = random.randint(DECIMAL_ADD_SUB_MIN * 10, DECIMAL_ADD_SUB_MAX * 10)
        if b_tenths > a_tenths:
            a_tenths, b_tenths = b_tenths, a_tenths  # keep the result non-negative, see module docstring
        return a_tenths / 10, b_tenths / 10, (a_tenths - b_tenths) / 10
    elif operation == "multiply":
        a_tenths = random.randint(DECIMAL_MULTIPLY_MIN * 10, DECIMAL_MULTIPLY_MAX * 10)
        b = random.randint(DECIMAL_MULTIPLY_MIN, DECIMAL_MULTIPLY_MAX)
        return a_tenths / 10, b, (a_tenths * b) / 10
    elif operation == "divide":
        quotient_tenths = random.randint(DECIMAL_DIVIDE_QUOTIENT_MIN * 10, DECIMAL_DIVIDE_QUOTIENT_MAX * 10)
        divisor = random.randint(DECIMAL_DIVIDE_DIVISOR_MIN, DECIMAL_DIVIDE_DIVISOR_MAX)
        dividend_tenths = quotient_tenths * divisor
        return dividend_tenths / 10, divisor, quotient_tenths / 10
    raise ValueError(f"unknown decimal operation: {operation!r}")


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


def _load_difficulty_aliases_from_disk():
    """locale/<lang>/difficulty_aliases.json - {spoken difficulty
    name: key in DIFFICULTIES}. Same convention and loader shape as
    _load_operation_aliases_from_disk() - kept as a separate function
    rather than generalizing the two into one, since a shared loader
    would obscure which alias file backs which resolver for a reader
    skimming this module."""
    merged = {}
    if not LOCALE_DIR.is_dir():
        return merged
    for lang_dir in sorted(LOCALE_DIR.iterdir()):
        if not lang_dir.is_dir():
            continue
        alias_file = lang_dir / "difficulty_aliases.json"
        if not alias_file.exists():
            continue
        with open(alias_file, encoding="utf-8") as f:
            aliases = json.load(f)
        lang = lang_dir.name.lower()
        merged[lang] = {k: v for k, v in aliases.items() if not k.startswith("_")}
    return merged


DIFFICULTY_ALIASES = _load_difficulty_aliases_from_disk()


def _load_operator_words_from_disk():
    """locale/<lang>/operator_words.json - {operation: spoken word},
    the REVERSE direction of operation_aliases.json (which maps
    spoken word -> operation). Needed for chain/mixed-operator
    quizzing, which builds its question as plain text in Python (see
    _render_expression()) rather than through a fixed {a}/{b} dialog
    template, since the number of operands/operators is variable."""
    merged = {}
    if not LOCALE_DIR.is_dir():
        return merged
    for lang_dir in sorted(LOCALE_DIR.iterdir()):
        if not lang_dir.is_dir():
            continue
        words_file = lang_dir / "operator_words.json"
        if not words_file.exists():
            continue
        with open(words_file, encoding="utf-8") as f:
            words = json.load(f)
        lang = lang_dir.name.lower()
        merged[lang] = {k: v for k, v in words.items() if not k.startswith("_")}
    return merged


OPERATOR_WORDS = _load_operator_words_from_disk()


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

    def _difficulty_aliases_for(self, lang):
        lang = lang.lower()
        return DIFFICULTY_ALIASES.get(lang) or DIFFICULTY_ALIASES.get("en-us", {})

    def _resolve_difficulty(self, raw, lang):
        """Exact match only - same reasoning as _resolve_operation()."""
        if not raw:
            return None
        return self._difficulty_aliases_for(lang).get(raw.strip().lower())

    def _operator_word(self, operation, lang):
        lang = lang.lower()
        words = OPERATOR_WORDS.get(lang) or OPERATOR_WORDS.get("en-us", {})
        return words.get(operation, operation)

    def _render_expression(self, parts):
        """parts alternates [operand, operation, operand, operation,
        ..., operand] (odd length, at least 3). Builds a plain-text
        arithmetic expression using localized operator words, e.g.
        '7 minus 2 minus 1' or '4 plus 3 times 2'. Shared by chain
        and mixed-operator quizzing, both of which need a
        variable-shape spoken question rather than fixed {a}/{b}
        dialog slots."""
        words = []
        for i, part in enumerate(parts):
            words.append(str(part) if i % 2 == 0 else self._operator_word(part, self.lang))
        return " ".join(words)

    def _ask_and_grade_expression(self, parts, answer):
        """Same grading contract as _ask_and_grade() (speaks
        correct/incorrect, returns True/False), but for a
        variable-shape expression rather than a fixed (operation, a,
        b) triple - see _render_expression()."""
        expression = self._render_expression(parts)
        response_text = self.get_response(dialog="quiz_question_expression", data={"expression": expression})
        if response_text is None:
            self.speak_dialog("quiz_no_answer")
            return False
        user_value = extract_number(response_text, lang=self.lang)
        if user_value is not False and user_value == answer:
            self.speak_dialog("quiz_correct")
            return True
        self.speak_dialog("quiz_incorrect", {"answer": answer})
        return False

    def _grade_estimate_response(self, response_text, choices, correct_index):
        """Accepts either a spoken letter (voc-matched against
        choice_a/b/c.voc) or the spoken number itself (extract_number,
        matched against the presented choice values) - a user reading
        the number back out loud instead of the letter should still
        count, even though the whole point of letters is to avoid
        REQUIRING that (see issue #8)."""
        for i, letter in enumerate(ESTIMATE_LETTERS):
            if self.voc_match(response_text, f"choice_{letter.lower()}"):
                return i == correct_index
        user_value = extract_number(response_text, lang=self.lang)
        if user_value is not False and user_value in choices:
            return choices.index(user_value) == correct_index
        return False

    def _ask_and_grade_estimate(self, a, operation, b, choices, correct_index):
        expression = self._render_expression([a, operation, b])
        data = {"expression": expression}
        for letter, value in zip(ESTIMATE_LETTERS, choices):
            data[f"choice_{letter.lower()}"] = value
        response_text = self.get_response(dialog="quiz_question_estimate", data=data)
        if response_text is None:
            self.speak_dialog("quiz_no_answer")
            return False
        if self._grade_estimate_response(response_text, choices, correct_index):
            self.speak_dialog("quiz_correct")
            return True
        self.speak_dialog("estimate_incorrect", {
            "letter": ESTIMATE_LETTERS[correct_index],
            "value": choices[correct_index],
        })
        return False

    def _ask_and_grade_decimal(self, operation, a, b, answer):
        """Same grading contract as _ask_and_grade(), but compares
        with DECIMAL_GRADING_EPSILON slack instead of exact equality
        - see generate_decimal_problem()'s docstring for why that's a
        float-representation guard, not a real tolerance band.
        Reuses the SAME quiz_question_<op>.dialog files as the
        integer version - they're already number-agnostic {a}/{b}
        templates, no decimal-specific dialog needed."""
        response_text = self.get_response(dialog=f"quiz_question_{operation}", data={"a": a, "b": b})
        if response_text is None:
            self.speak_dialog("quiz_no_answer")
            return False
        user_value = extract_number(response_text, lang=self.lang)
        if user_value is not False and abs(user_value - answer) < DECIMAL_GRADING_EPSILON:
            self.speak_dialog("quiz_correct")
            return True
        self.speak_dialog("quiz_incorrect", {"answer": answer})
        return False

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

    def _run_quiz(self, operation, table=None, difficulty="medium"):
        correct_count = 0
        for _ in range(NUM_QUIZ_QUESTIONS):
            a, b, answer = generate_problem(operation, table, difficulty)
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

    def _run_chain_quiz(self, operation):
        """'quiz me on chained addition' etc (issue #3) - see
        generate_chain_problem() for how the operand list is
        constructed safely."""
        correct_count = 0
        for _ in range(NUM_QUIZ_QUESTIONS):
            operands, answer = generate_chain_problem(operation)
            parts = [operands[0]]
            for operand in operands[1:]:
                parts.append(operation)
                parts.append(operand)
            if self._ask_and_grade_expression(parts, answer):
                correct_count += 1
        self.speak_dialog("quiz_finished", {"correct": correct_count, "total": NUM_QUIZ_QUESTIONS})

    def _run_mixed_quiz(self):
        """'quiz me on mixed operators' (issue #4) - one +/- operator
        and one x/÷ operator per question, real order-of-operations
        precedence. See generate_mixed_problem() for construction."""
        correct_count = 0
        for _ in range(NUM_QUIZ_QUESTIONS):
            a, op1, b, op2, c, answer = generate_mixed_problem()
            if self._ask_and_grade_expression([a, op1, b, op2, c], answer):
                correct_count += 1
        self.speak_dialog("quiz_finished", {"correct": correct_count, "total": NUM_QUIZ_QUESTIONS})

    def _run_estimate_quiz(self):
        """'quiz me on estimation' (issue #8) - multiple choice, not a
        computed spoken number. See generate_estimate_problem()."""
        correct_count = 0
        for _ in range(NUM_QUIZ_QUESTIONS):
            a, operation, b, answer, choices, correct_index = generate_estimate_problem()
            if self._ask_and_grade_estimate(a, operation, b, choices, correct_index):
                correct_count += 1
        self.speak_dialog("quiz_finished", {"correct": correct_count, "total": NUM_QUIZ_QUESTIONS})

    def _run_decimal_quiz(self, operation):
        """'quiz me on decimal addition' etc (issue #5, decimals
        half). See generate_decimal_problem() for why every question
        here is exact by construction rather than needing a genuine
        tolerance band."""
        correct_count = 0
        for _ in range(NUM_QUIZ_QUESTIONS):
            a, b, answer = generate_decimal_problem(operation)
            if self._ask_and_grade_decimal(operation, a, b, answer):
                correct_count += 1
        self.speak_dialog("quiz_finished", {"correct": correct_count, "total": NUM_QUIZ_QUESTIONS})

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

    @intent_handler("quiz_operation_difficulty.intent")
    def handle_quiz_operation_difficulty(self, message):
        """'quiz me on hard addition' - separate intent from
        quiz_operation.intent rather than an optional slot on it,
        matching this project's existing style of one static-word
        template per phrasing rather than optional-slot syntax (see
        e.g. teach_me.intent vs teach_me_operation.intent). Difficulty
        stays a per-request slot only, not persisted to
        self.settings - see the module-level DIFFICULTIES/
        DIFFICULTY_RANGES comment and issue #2 for why."""
        operation_raw = message.data.get("operation")
        difficulty_raw = message.data.get("difficulty")
        operation = self._resolve_operation(operation_raw, self.lang) if operation_raw else None
        if operation_raw and operation is None:
            self.speak_dialog("operation_not_understood", {"operation": operation_raw})
            return
        difficulty = self._resolve_difficulty(difficulty_raw, self.lang) if difficulty_raw else None
        if difficulty_raw and difficulty is None:
            self.speak_dialog("difficulty_not_understood", {"difficulty": difficulty_raw})
            return
        operation = operation or random.choice(OPERATIONS)
        difficulty = difficulty or "medium"
        self._run_quiz(operation, difficulty=difficulty)

    @intent_handler("quiz_general.intent")
    def handle_quiz_general(self, message):
        self._run_quiz(random.choice(OPERATIONS))

    @intent_handler("quiz_full.intent")
    def handle_quiz_full(self, message):
        """Samples across ALL_OPERATIONS rather than just the classic
        four - see the ALL_OPERATIONS module comment for why this is
        a separate pool rather than growing OPERATIONS/quiz_general
        itself."""
        self._run_quiz(random.choice(ALL_OPERATIONS))

    @intent_handler("quiz_chain.intent")
    def handle_quiz_chain(self, message):
        """'quiz me on chained addition' (issue #3). Not part of
        OPERATIONS/ALL_OPERATIONS - a deliberately separate v1 mode,
        see the module docstring's chain/mixed-operator note."""
        operation_raw = message.data.get("operation")
        operation = self._resolve_operation(operation_raw, self.lang) if operation_raw else None
        if operation_raw and operation is None:
            self.speak_dialog("operation_not_understood", {"operation": operation_raw})
            return
        operation = operation or random.choice(OPERATIONS)
        self._run_chain_quiz(operation)

    @intent_handler("quiz_mixed.intent")
    def handle_quiz_mixed(self, message):
        """'quiz me on mixed operators' (issue #4) - no operation slot,
        every question mixes a +/- operator with a x/÷ operator by
        construction (see generate_mixed_problem())."""
        self._run_mixed_quiz()

    @intent_handler("quiz_estimate.intent")
    def handle_quiz_estimate(self, message):
        """'quiz me on estimation' (issue #8) - no operation slot,
        samples multiply/divide per question (see
        generate_estimate_problem()). Not part of OPERATIONS/
        ALL_OPERATIONS, same v1 scoping as chain/mixed."""
        self._run_estimate_quiz()

    @intent_handler("quiz_decimal.intent")
    def handle_quiz_decimal(self, message):
        """'quiz me on decimal addition' (issue #5, decimals half -
        fractions are a deliberately separate later pass). Not part
        of OPERATIONS/ALL_OPERATIONS, same v1 scoping as chain/mixed/
        estimate."""
        operation_raw = message.data.get("operation")
        operation = self._resolve_operation(operation_raw, self.lang) if operation_raw else None
        if operation_raw and operation is None:
            self.speak_dialog("operation_not_understood", {"operation": operation_raw})
            return
        operation = operation or random.choice(OPERATIONS)
        self._run_decimal_quiz(operation)

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
