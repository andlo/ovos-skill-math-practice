# <img src='icon.png' card_color='#DB4062' width='50' height='50' style='vertical-align:bottom'/> Math Practice

Math practice for kids (and anyone else) - counting, times table
recitation, and interactive arithmetic quizzes across all four basic
operations. Fully offline.

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
   addition"` - genuinely interactive: asks 5 questions one at a
   time, listens for a spoken answer, and reports a final score.
   Covers all four basic operations, not just multiplication - this
   was an explicit scope correction from the original "times tables"
   framing during design.

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
"give me a math quiz"
"tæl til ti"                    (Danish)
"sig 5 tabellen"                (Danish)
"lær mig 5 tabellen"            (Danish)
"lær mig plus for 5"            (Danish)
"quiz mig i det du lærte mig"   (Danish)
"quiz mig i 3 tabellen"         (Danish)
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
