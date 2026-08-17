# Development

## Architecture at a glance

Four modes, deliberately kept separate rather than folded into one
"do math" intent:

1. **Counting** - pure recitation, no interaction.
2. **Table recitation** - multiplication only; addition/subtraction/
   division don't have a traditional "table" concept the same way.
3. **Teach-then-practice** - teach a fact table row by row, then quiz
   on exactly what was taught (see README "Teach-then-practice" and
   [issue #1](https://github.com/andlo/ovos-skill-math-practice/issues/1)).
4. **Quiz** - the interactive core: `OVOSSkill.get_response()` for a
   sequential, blocking conversation rather than a background thread
   (unlike `ovos-skill-metronome`/`rhythm-box`/`white-noise`) - a
   timed-out or unparseable answer is handled explicitly per question
   rather than crashing the quiz. Covers the classic four operations
   plus percentages, difficulty levels, chained and mixed-operator
   problems, an estimation mode, and decimal arithmetic - each added
   by a tracked GitHub issue (#2 difficulty, #3 chained, #4
   mixed-operator, #5 decimals, #7 percent, #8 estimation).

**Two operation pools, not one**: `OPERATIONS` (the classic four -
what `"give me a math quiz"` samples) and `ALL_OPERATIONS` (also
includes percent - what `"give me a full math quiz"` samples). New
operations don't automatically join both - see "Adding a new quiz
mode or operation" below.

**Every generator follows the same rule**: construct problems so the
answer is exact/valid BY CONSTRUCTION (division as divisor x
quotient, subtraction with the larger operand first, chain
subtraction capped by the running total, decimal arithmetic in
integer tenths, multiple-choice distractors built from named
mistakes rather than random noise) rather than generating freely and
rejecting or rounding. See each `generate_*` function's own docstring
for the specific constraint it enforces, and "Decimals, tolerance
bands, and when NOT to use one" below for the one place this rule
runs into a genuine limit.

Chained/mixed-operator/estimation/decimal modes are all deliberately
NOT difficulty-aware and NOT part of `OPERATIONS`/`ALL_OPERATIONS`
for v1 - a scoped-down choice repeated across issues #3/#4/#5/#8, not
an oversight in any one of them.

## Setup
```bash
git clone https://github.com/andlo/ovos-skill-math-practice.git
cd ovos-skill-math-practice
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -r requirements-test.txt
```

## Running tests
```bash
pytest tests/ -v
```
`tests/test_problem_generation.py` runs each generator 200 times to
check its invariants hold across the randomization (subtraction never
negative, division always exact, etc), not just a single lucky case.
`tests/test_counting_and_recitation.py` covers the two pure-recitation
intents, including monkeypatching the (read-only) `resources`
property to verify `table_row.dialog` is rendered once per row rather
than actually speaking each row separately.
`tests/test_quiz.py` covers the interactive quiz flow with
`get_response()` and `generate_problem()` both mocked/patched, so the
scoring and flow logic (all-correct, all-wrong, no-response-doesn't-
crash) is tested deterministically rather than depending on real
randomness or actual speech I/O.
`tests/test_teach_then_practice.py` covers the teach-then-practice
loop similarly: `get_response()` and `voc_match()` mocked to verify
the row-by-row teaching flow, the "repeat" branch, that no prompt is
asked after the final row, and that the follow-up quiz grades against
exactly the recorded taught facts rather than fresh random ones.

## Adding a new quiz mode or operation

1. Add the generation logic to `generate_problem()` in `__init__.py`,
   following the same "state the constraint, then generate within it"
   approach as the existing four (e.g. division's "always divides
   evenly" constraint).
2. Add `locale/en-us/quiz_question_<op>.dialog` and the Danish
   equivalent.
3. Add the operation name to both languages' `operation_aliases.json`
   so `"quiz me on <op>"` (`quiz_operation.intent`) works directly -
   this alone is enough for the operation to be quizzable.
4. Decide which pool(s) it joins:
   - `ALL_OPERATIONS` always - this is what `"give me a full math
     quiz"` (`quiz_full.intent`) samples from, and should include
     every operation the skill knows.
   - `OPERATIONS` only if it belongs in the *classic* random pool
     that `"give me a math quiz"` (`quiz_general.intent`) has always
     meant - adding here changes existing behavior for anyone using
     that phrase, so treat it as a deliberate decision, not a
     default. Percent (issue #7) is the precedent for staying out of
     `OPERATIONS` while still being in `ALL_OPERATIONS`.
5. Add `test_problem_generation.py` invariant tests (run many
   iterations, not just one), a `test_quiz.py` case confirming the
   right question dialog gets used, and a case confirming which
   pool(s) the operation ended up in.
6. Add a per-difficulty entry for the operation in `DIFFICULTY_RANGES`
   (`easy`/`medium`/`hard`) - see "Adding difficulty support to a new
   operation" below if it needs anything beyond a simple `(lo, hi)`
   tuple (multiply and percent both need more than one).

## Adding difficulty support to a new operation

`DIFFICULTY_RANGES[difficulty][operation]` is usually a simple
`(lo, hi)` tuple `generate_problem()` calls `random.randint()` on
directly. If the operation needs more than one range (multiply's
factor vs. the "other" number, percent's base multiplier), use
multiple keys instead (see `multiply_factor`/`multiply_other` or
`percent_multiplier`) rather than overloading a single tuple's
meaning per-operation - keeps `generate_problem()` legible without
having to remember which operation's tuple means what.

`"medium"` must always reproduce whatever the operation's original,
pre-difficulty behavior was - build it FROM existing constants rather
than a fresh literal, the same way every entry already does, so
`"quiz me on <op>"` with no difficulty word never changes behavior
just because difficulty support exists.

Difficulty is per-request only (see `DIFFICULTY_RANGES` module
comment and issue #2) - don't add a `self.settings`-persisted default
without a real, demonstrated need for one; that's a deliberate
scoped-down v1 choice, not an oversight.

## Variable-shape questions (chained, mixed-operator)

`generate_chain_problem()` (issue #3) and `generate_mixed_problem()`
(issue #4) don't fit the fixed `(operation, a, b)` shape every other
generator uses, so they don't go through `_ask_and_grade()` or a
per-op `quiz_question_<op>.dialog`. Instead:

- `_render_expression(parts)` builds the spoken question as plain
  text in Python from an alternating `[operand, operation, operand,
  ...]` list, using `operator_words.json` (the reverse of
  `operation_aliases.json` - operation -> spoken word, not word ->
  operation) for localized operator words.
- `quiz_question_expression.dialog` (just `"what is {expression}"`)
  is the one shared dialog both use.
- `_ask_and_grade_expression(parts, answer)` is the equivalent of
  `_ask_and_grade()` for this shape.

If a future variable-shape mode needs different final-answer grading
(not "does the spoken number match"), it'll need its own grading
function - `_ask_and_grade_expression()` assumes a single numeric
answer, same as everything else in this skill so far.

## Multiple-choice questions (estimation)

`generate_estimate_problem()` (issue #8) is the one mode so far that
doesn't grade a free-form spoken number at all - the user answers
with a letter (or, as a fallback, the number itself). If a future
mode needs multiple choice again:

- Build distractors from SPECIFIC, named wrong-answer strategies
  (see `_round_to_nice()`'s docstring), not `answer ± random%`- a
  plausible mistake teaches something, arbitrary noise doesn't.
- Run every candidate through `_dedupe_candidates()` before
  presenting - a multiple-choice question can never show two
  identical options, however unlikely a collision is at your
  magnitudes.
- Add one `choice_<letter>.voc` per option (see `choice_a.voc`
  /`choice_b.voc`/`choice_c.voc`) so `voc_match()` can resolve a
  spoken letter the same way `repeat.voc` already does for
  teach-then-practice.

## Decimals, tolerance bands, and when NOT to use one

`generate_decimal_problem()` (issue #5) does its arithmetic in
integer TENTHS internally and converts to a float only once, so every
decimal problem here is exact - grading uses
`DECIMAL_GRADING_EPSILON` purely as a float-representation guard
(two independent `float()` conversions occasionally disagree in the
last bit), not a real tolerance band.

**This is not a general answer to the tolerance-band question** - it
works here because every operation in this skill CAN be constructed
to have an exact answer (same "construct it clean" philosophy as
everything else in this module). A genuinely irrational quantity
(e.g. `ovos-skill-unit-practice`'s meter-to-mile conversion, or a
non-Pythagorean-triple hypotenuse in the planned
`ovos-skill-geometry-practice`) can't be constructed exact and will
need real tolerance-band grading (e.g. "within 1-2% counts"). Before
reaching for a real tolerance band anywhere in this project family,
ask first whether the problem can instead be constructed exact - it
usually can, and exact grading is simpler and less surprising to a
user than "correct-ish."

## Versioning

`version.py` follows `VERSION_MAJOR.VERSION_MINOR.VERSION_BUILD[aVERSION_ALPHA]`.

## Releasing

Releases are tag-triggered (`v*`):
```bash
git add version.py
git commit -m "chore: bump version to 0.0.X"
git tag vX.Y.Z
git push && git push --tags
```
Triggers `.github/workflows/test.yml` then `.github/workflows/publish.yml`
(PyPI via trusted publishing - see `ovos-skill-convert`'s
DEVELOPMENT.md for the one-time PyPI setup needed before the first
tagged release).

## Style / conventions

- License: GPL-3.0-or-later (matches the other `andlo` skill repos).
- `locale/<lang-code>/` layout, `skill.json` inside each locale folder.
- Alias JSON in locale (`operation_aliases.json`) - same JSON-in-locale
  convention as the rest of this project family.
- Present design changes for review before implementing.
