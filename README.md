# <img src='icon.png' card_color='#DB4062' width='50' height='50' style='vertical-align:bottom'/> Math Practice

Math practice for kids (and anyone else) - counting, times table
recitation, and interactive arithmetic quizzes across all four basic
operations plus percentages. Fully offline.

[![Tests](https://github.com/andlo/ovos-skill-math-practice/actions/workflows/test.yml/badge.svg)](https://github.com/andlo/ovos-skill-math-practice/actions/workflows/test.yml)
[![PyPI version](https://img.shields.io/pypi/v/ovos-skill-math-practice.svg)](https://pypi.org/project/ovos-skill-math-practice/)

## Four modes, deliberately not one "do math" intent

1. **Counting** - `"count to ten"` - pure recitation, no interaction.
2. **Table recitation** - `"say the 5 times table"` - pure recitation
   of 1×5 through 10×5, no interaction. Multiplication only -
   addition/subtraction/division don't have a traditional "table"
   concept the same way, so this stays scoped to what "times table"
   actually means.
3. **Teach, then practice** - `"teach me the 5 times table"` (or
   `"teach me addition facts for 5"` / `"teach me subtraction facts
   for 5"` / `"teach me division facts for 5"` - all four operations,
   not just multiplication) goes through the facts one row at a time
   (say "repeat" to hear a row again before moving on), then `"quiz
   me on what you taught me"` quizzes specifically on THOSE facts -
   not arbitrary random problems, and in the SAME operation that was
   taught. See "Teach-then-practice" below.
4. **Quiz** - `"quiz me on the 3 times table"` / `"quiz me on
   addition"` / `"quiz me on percentages"` - genuinely interactive:
   asks 5 questions one at a time, listens for a spoken answer, and
   reports a final score. Covers all four basic operations plus
   percentages, not just multiplication - this was an explicit scope
   correction from the original "times tables" framing during design.

`"give me a math quiz"` randomizes across the classic four operations
only, same as it always has. `"give me a full math quiz"` randomizes
across every operation this skill knows (currently the classic four
plus percentages) - a separate, broader pool so new operations don't
retroactively change what the classic phrase means. See the
`ALL_OPERATIONS` / `OPERATIONS` module comment in `__init__.py` and
[issue #7](https://github.com/andlo/ovos-skill-math-practice/issues/7)
for the reasoning.

## Difficulty

`"quiz me on hard addition"` / `"quiz mig i svær division"` selects
one of `easy` / `medium` / `hard` for that quiz round only - there's
no persisted skill-wide default (see
[issue #2](https://github.com/andlo/ovos-skill-math-practice/issues/2)).
`"quiz me on addition"` with no difficulty word still works exactly
as before - it runs at `medium`, which reproduces the original ranges
every operation always used. See `DIFFICULTY_RANGES` in `__init__.py`
for the actual per-operation, per-tier ranges. Times-table quizzing
(`"quiz me on the 5 times table"`) doesn't take a difficulty - the
table number itself already controls how hard it is.

## Chained and mixed-operator problems

`"quiz me on chained addition"` / `"quiz mig i kædet subtraktion"`
asks a 3-operand, same-operator question ("what is 7 minus 2 minus
1") instead of the usual two-operand one. Subtraction and division
chains are built so every INTERMEDIATE step stays valid (non-negative
/ evenly divides), not just the final result - see
[issue #3](https://github.com/andlo/ovos-skill-math-practice/issues/3).

`"quiz me on mixed operators"` / `"quiz mig i blandede regnearter"`
asks a 3-operand question with one +/- operator and one x/÷ operator,
testing real order-of-operations precedence ("what is 4 plus 3 times
2" = 10, not 14) - see
[issue #4](https://github.com/andlo/ovos-skill-math-practice/issues/4),
including its open question about whether a spoken question conveys
precedence as unambiguously as a written one does; worth verifying on
a live instance rather than assuming.

Neither mode is difficulty-aware or part of `OPERATIONS`/
`ALL_OPERATIONS` for v1 - a deliberate, scoped-down choice, not an
oversight.

## Estimation mode

`"quiz me on estimation"` / `"quiz mig i estimering"` asks a
large-number multiplication or division question with three lettered
choices (A/B/C) instead of a computed spoken number - avoids
requiring an unwieldy 8-digit answer to be spoken, and lets the user
answer with either the letter or the number itself. The two wrong
choices are built from specific, plausible estimation mistakes (a
decimal-place slip; recomputing with one factor rounded to a nearby
"nice" number), not random noise - see
[issue #8](https://github.com/andlo/ovos-skill-math-practice/issues/8)
and `generate_estimate_problem()` in `__init__.py`. Whether three
choices is the right number for a voice-only interaction (vs. glancing
at a screen) is flagged as an open question in the issue itself -
worth testing on a live instance.

## Usage
```
"count to ten"
"say the 5 times table"
"teach me the 5 times table"
"teach me addition facts for 5"
"teach me subtraction facts for 5"
"teach me division facts for 5"
"quiz me on what you taught me"
"quiz me on the 3 times table"
"quiz me on addition"
"quiz me on percentages"
"quiz me on hard addition"
"quiz me on chained subtraction"
"quiz me on mixed operators"
"quiz me on estimation"
"give me a math quiz"
"give me a full math quiz"
"tæl til ti"                    (Danish)
"sig 5 tabellen"                (Danish)
"lær mig 5 tabellen"            (Danish)
"lær mig plus for 5"            (Danish)
"quiz mig i det du lærte mig"   (Danish)
"quiz mig i 3 tabellen"         (Danish)
"quiz mig i procent"            (Danish)
"quiz mig i svær division"      (Danish)
"quiz mig i kædet subtraktion"  (Danish)
"quiz mig i blandede regnearter" (Danish)
"quiz mig i estimering"         (Danish)
"quiz mig i det hele"           (Danish)
```

## Teach-then-practice

The reference implementation of the pattern shared across the whole
`*-practice` family (see [issue #1](https://github.com/andlo/ovos-skill-math-practice/issues/1)
for the original design discussion, since resolved and extended to
all four operations). `"teach me the 5 times table"` speaks each row
in turn, waits for either "repeat" (says the same row again) or
anything else (moves to the next row), and records exactly which
facts were presented AND which operation they belong to. `"quiz me on
what you taught me"` then quizzes ONLY on that recorded set, in the
same operation, reusing the same grading logic as the regular quiz
mode (`_ask_and_grade()`), rather than generating fresh random
problems.

Started multiply-only (mirroring "times table" recitation), then
generalized to all four operations via a shared
`FACT_TABLE_GENERATORS` registry - addition/subtraction/division each
get their own "N-facts table" generator, mirroring multiplication's
table shape (subtraction and division specifically constructed so
results stay non-negative / evenly divide, matching the same rules
the regular quiz mode already enforces).

**Deliberately session-only for this release**: `self._taught_facts`
resets when the skill restarts - it doesn't persist across days. This
was a scoped-down choice from the original design discussion, which
also considered persisting taught facts (via `self.settings` or a
local file) so "quiz me on what you taught me" would still work in a
later session. Kept simple for v1; worth revisiting if session-only
turns out to be a real limitation in practice rather than a
theoretical one.

## How the quiz works

Unlike [ovos-skill-metronome](https://github.com/andlo/ovos-skill-metronome)/
[ovos-skill-rhythm-box](https://github.com/andlo/ovos-skill-rhythm-box)/
[ovos-skill-white-noise](https://github.com/andlo/ovos-skill-white-noise),
quiz mode needs no background thread - it's a sequential, blocking
conversation using `OVOSSkill.get_response()`, which already handles
the listen-and-transcribe round-trip. Each of the 5 questions is
asked, answered (or timed out), and scored in turn; a timed-out or
unparseable answer counts as incorrect rather than crashing the quiz.

## Problem generation defaults

- 5 questions per quiz round.
- Times tables: the traditional 1-12 range.
- Addition/subtraction: operands 1-20, subtraction always kept
  non-negative (larger number first).
- Division: always divides evenly (built as divisor × quotient, both
  1-10) - no fractional answers, since spoken fraction-checking is a
  much harder problem than this skill attempts to solve.
- Percentage: built backwards like division - the percentage (1-100)
  is picked first, then a base is constructed that's guaranteed to
  make `percent/100*base` a whole number, rather than picking both
  numbers freely and rounding. No tolerance/rounding needed for v1
  (see [issue #5](https://github.com/andlo/ovos-skill-math-practice/issues/5)
  for the tolerance-band question decimals/fractions will eventually
  raise).
- All of the above are the `medium` difficulty ranges - see
  "Difficulty" above for `easy`/`hard`.

## Install
```bash
pip install ovos-skill-math-practice
```

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md).

## Category
**Education**

## Tags
#math #education #times-tables #quiz #kids
