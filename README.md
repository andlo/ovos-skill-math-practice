# <img src='icon.png' card_color='#DB4062' width='50' height='50' style='vertical-align:bottom'/> Math Practice

Math practice for kids (and anyone else) - counting, times table
recitation, and interactive arithmetic quizzes across all four basic
operations. Fully offline.

[![Tests](https://github.com/andlo/ovos-skill-math-practice/actions/workflows/test.yml/badge.svg)](https://github.com/andlo/ovos-skill-math-practice/actions/workflows/test.yml)
[![PyPI version](https://img.shields.io/pypi/v/ovos-skill-math-practice.svg)](https://pypi.org/project/ovos-skill-math-practice/)

## Three separate modes, deliberately not one "do math" intent

1. **Counting** - `"count to ten"` - pure recitation, no interaction.
2. **Table recitation** - `"say the 5 times table"` - pure recitation
   of 1×5 through 10×5, no interaction. Multiplication only -
   addition/subtraction/division don't have a traditional "table"
   concept the same way, so this stays scoped to what "times table"
   actually means.
3. **Quiz** - `"quiz me on the 3 times table"` / `"quiz me on
   addition"` - genuinely interactive: asks 5 questions one at a
   time, listens for a spoken answer, and reports a final score.
   Covers all four basic operations, not just multiplication - this
   was an explicit scope correction from the original "times tables"
   framing during design.

## Usage
```
"count to ten"
"say the 5 times table"
"quiz me on the 3 times table"
"quiz me on addition"
"give me a math quiz"
"tæl til ti"                    (Danish)
"sig 5 tabellen"                (Danish)
"quiz mig i 3 tabellen"         (Danish)
```

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
