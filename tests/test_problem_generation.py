"""Tests for problem generation - pure logic, no mocking needed. Runs
many iterations per invariant since these are randomized."""
import pytest

ITERATIONS = 200


def test_multiply_with_fixed_table_keeps_first_factor_fixed():
    from mathpractice_skill import generate_problem
    for _ in range(ITERATIONS):
        a, b, answer = generate_problem("multiply", table=7)
        assert a == 7
        assert answer == 7 * b


def test_subtract_never_produces_negative_result():
    from mathpractice_skill import generate_problem
    for _ in range(ITERATIONS):
        a, b, answer = generate_problem("subtract")
        assert answer >= 0
        assert answer == a - b


def test_add_answer_is_correct():
    from mathpractice_skill import generate_problem
    for _ in range(ITERATIONS):
        a, b, answer = generate_problem("add")
        assert answer == a + b


def test_divide_always_divides_evenly():
    from mathpractice_skill import generate_problem
    for _ in range(ITERATIONS):
        a, b, answer = generate_problem("divide")
        assert a % b == 0
        assert answer == a // b


def test_multiplication_table_rows_are_correct():
    from mathpractice_skill import multiplication_table
    rows = multiplication_table(7)
    assert rows[0] == (1, 7, 7)
    assert rows[4] == (5, 7, 35)
    assert rows[-1] == (10, 7, 70)
    assert len(rows) == 10


def test_unknown_operation_raises():
    from mathpractice_skill import generate_problem
    with pytest.raises(ValueError):
        generate_problem("exponentiate")


def test_percent_always_divides_evenly():
    from mathpractice_skill import generate_problem
    for _ in range(ITERATIONS):
        percent, base, answer = generate_problem("percent")
        assert (percent * base) % 100 == 0
        assert answer == percent * base // 100


def test_percent_within_configured_range():
    from mathpractice_skill import generate_problem, PERCENT_MIN, PERCENT_MAX
    for _ in range(ITERATIONS):
        percent, base, answer = generate_problem("percent")
        assert PERCENT_MIN <= percent <= PERCENT_MAX


def test_all_operations_includes_percent_but_operations_does_not():
    from mathpractice_skill import OPERATIONS, ALL_OPERATIONS
    assert "percent" not in OPERATIONS
    assert "percent" in ALL_OPERATIONS
    assert set(ALL_OPERATIONS) == set(OPERATIONS) | {"percent"}


def test_default_difficulty_matches_pre_difficulty_behavior():
    """generate_problem() with no explicit difficulty must produce the
    exact same ranges it always did before DIFFICULTY_RANGES existed -
    this is the whole point of building 'medium' FROM the original
    constants rather than duplicating literals."""
    from mathpractice_skill import generate_problem, ADD_SUB_MIN, ADD_SUB_MAX
    for _ in range(ITERATIONS):
        a, b, answer = generate_problem("add")
        assert ADD_SUB_MIN <= a <= ADD_SUB_MAX
        assert ADD_SUB_MIN <= b <= ADD_SUB_MAX


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
@pytest.mark.parametrize("operation", ["add", "subtract", "multiply", "divide", "percent"])
def test_every_operation_respects_its_difficulty_range(operation, difficulty):
    from mathpractice_skill import generate_problem, DIFFICULTY_RANGES
    ranges = DIFFICULTY_RANGES[difficulty]
    for _ in range(ITERATIONS):
        a, b, answer = generate_problem(operation, difficulty=difficulty)
        if operation in ("add", "subtract"):
            lo, hi = ranges[operation]
            assert lo <= a <= hi
            assert lo <= b <= hi
        elif operation == "multiply":
            factor_lo, factor_hi = ranges["multiply_factor"]
            other_lo, other_hi = ranges["multiply_other"]
            assert factor_lo <= a <= factor_hi
            assert other_lo <= b <= other_hi
        elif operation == "divide":
            lo, hi = ranges["divide"]
            assert lo <= b <= hi  # b is the divisor
            assert lo <= answer <= hi  # answer is the quotient


def test_subtract_stays_non_negative_at_every_difficulty():
    from mathpractice_skill import generate_problem
    for difficulty in ("easy", "medium", "hard"):
        for _ in range(ITERATIONS):
            a, b, answer = generate_problem("subtract", difficulty=difficulty)
            assert answer >= 0


def test_divide_still_divides_evenly_at_every_difficulty():
    from mathpractice_skill import generate_problem
    for difficulty in ("easy", "medium", "hard"):
        for _ in range(ITERATIONS):
            a, b, answer = generate_problem("divide", difficulty=difficulty)
            assert a % b == 0
            assert answer == a // b


def test_percent_still_divides_evenly_at_every_difficulty():
    from mathpractice_skill import generate_problem
    for difficulty in ("easy", "medium", "hard"):
        for _ in range(ITERATIONS):
            percent, base, answer = generate_problem("percent", difficulty=difficulty)
            assert (percent * base) % 100 == 0
            assert answer == percent * base // 100


def test_unknown_difficulty_raises():
    from mathpractice_skill import generate_problem
    with pytest.raises(ValueError):
        generate_problem("add", difficulty="impossible")


def test_multiply_with_explicit_table_ignores_factor_range_but_keeps_other_range():
    """table= overrides the varying-factor range at any difficulty -
    quiz_table.intent doesn't take a difficulty at all, so this
    confirms explicit table selection still works even though
    generate_problem() now threads difficulty through multiply too."""
    from mathpractice_skill import generate_problem
    for difficulty in ("easy", "medium", "hard"):
        for _ in range(ITERATIONS):
            a, b, answer = generate_problem("multiply", table=7, difficulty=difficulty)
            assert a == 7
            assert answer == 7 * b


def test_chain_add_answer_is_correct_and_has_right_operand_count():
    from mathpractice_skill import generate_chain_problem, NUM_CHAIN_OPERANDS
    for _ in range(ITERATIONS):
        operands, answer = generate_chain_problem("add")
        assert len(operands) == NUM_CHAIN_OPERANDS
        assert answer == sum(operands)


def test_chain_multiply_answer_is_correct():
    from mathpractice_skill import generate_chain_problem
    for _ in range(ITERATIONS):
        operands, answer = generate_chain_problem("multiply")
        expected = 1
        for o in operands:
            expected *= o
        assert answer == expected


def test_chain_subtract_never_goes_negative_at_any_intermediate_step():
    from mathpractice_skill import generate_chain_problem
    for _ in range(ITERATIONS):
        operands, answer = generate_chain_problem("subtract")
        running = operands[0]
        for delta in operands[1:]:
            running -= delta
            assert running >= 0  # every intermediate step, not just the final one
        assert running == answer


def test_chain_divide_divides_evenly_at_every_intermediate_step():
    from mathpractice_skill import generate_chain_problem
    for _ in range(ITERATIONS):
        operands, answer = generate_chain_problem("divide")
        running = operands[0]
        for divisor in operands[1:]:
            assert running % divisor == 0  # every intermediate step, not just the final one
            running //= divisor
        assert running == answer


def test_chain_unknown_operation_raises():
    from mathpractice_skill import generate_chain_problem
    with pytest.raises(ValueError):
        generate_chain_problem("exponentiate")


def test_chain_respects_custom_operand_count():
    from mathpractice_skill import generate_chain_problem
    for operation in ("add", "subtract", "multiply", "divide"):
        operands, answer = generate_chain_problem(operation, n=5)
        assert len(operands) == 5


def _evaluate_mixed(a, op1, b, op2, c):
    """Reference evaluator for generate_mixed_problem()'s output,
    independent of how the generator itself computed the answer -
    infers precedence from which operator is in the 'tight'
    (multiply/divide) tier vs 'loose' (add/subtract) tier, since
    exactly one of op1/op2 must be each (see the function it tests)."""
    ops = {
        "add": lambda x, y: x + y,
        "subtract": lambda x, y: x - y,
        "multiply": lambda x, y: x * y,
        "divide": lambda x, y: x // y,
    }
    tight = {"multiply", "divide"}
    if op1 in tight and op2 not in tight:
        return ops[op2](ops[op1](a, b), c)
    elif op2 in tight and op1 not in tight:
        return ops[op1](a, ops[op2](b, c))
    raise AssertionError(f"expected exactly one tight/loose operator, got {op1!r}, {op2!r}")


def test_mixed_problem_answer_respects_precedence():
    from mathpractice_skill import generate_mixed_problem
    for _ in range(ITERATIONS):
        a, op1, b, op2, c, answer = generate_mixed_problem()
        assert answer == _evaluate_mixed(a, op1, b, op2, c)


def test_mixed_problem_always_pairs_one_tight_and_one_loose_operator():
    from mathpractice_skill import generate_mixed_problem
    tight = {"multiply", "divide"}
    loose = {"add", "subtract"}
    for _ in range(ITERATIONS):
        a, op1, b, op2, c, answer = generate_mixed_problem()
        assert {op1, op2} & tight
        assert {op1, op2} & loose
        assert len({op1, op2} & tight) == 1
        assert len({op1, op2} & loose) == 1


def test_mixed_problem_answer_is_never_negative():
    from mathpractice_skill import generate_mixed_problem
    for _ in range(ITERATIONS):
        a, op1, b, op2, c, answer = generate_mixed_problem()
        assert answer >= 0


def test_estimate_problem_has_right_number_of_unique_choices():
    from mathpractice_skill import generate_estimate_problem, ESTIMATE_NUM_CHOICES
    for _ in range(ITERATIONS):
        a, operation, b, answer, choices, correct_index = generate_estimate_problem()
        assert len(choices) == ESTIMATE_NUM_CHOICES
        assert len(set(choices)) == ESTIMATE_NUM_CHOICES  # no duplicate options


def test_estimate_problem_correct_index_points_at_the_real_answer():
    from mathpractice_skill import generate_estimate_problem
    for _ in range(ITERATIONS):
        a, operation, b, answer, choices, correct_index = generate_estimate_problem()
        assert choices[correct_index] == answer


def test_estimate_problem_answer_matches_the_actual_arithmetic():
    from mathpractice_skill import generate_estimate_problem
    for _ in range(ITERATIONS):
        a, operation, b, answer, choices, correct_index = generate_estimate_problem()
        if operation == "multiply":
            assert answer == a * b
        else:
            assert a % b == 0
            assert answer == a // b


def test_estimate_problem_only_uses_multiply_or_divide():
    from mathpractice_skill import generate_estimate_problem
    seen = set()
    for _ in range(ITERATIONS):
        a, operation, b, answer, choices, correct_index = generate_estimate_problem()
        seen.add(operation)
    assert seen == {"multiply", "divide"}  # both should appear over enough iterations


def test_round_to_nice_never_returns_zero():
    from mathpractice_skill import _round_to_nice
    assert _round_to_nice(1, 500) != 0
    assert _round_to_nice(49, 100) != 0


def test_dedupe_candidates_produces_all_distinct_values():
    from mathpractice_skill import _dedupe_candidates
    result = _dedupe_candidates([100, 100, 100])
    assert len(set(result)) == 3
    assert result[0] == 100  # first occurrence is never touched


def test_addition_table_matches_real_arithmetic():
    from mathpractice_skill import addition_table
    for a, b, answer in addition_table(7):
        assert a + b == answer


def test_subtraction_table_matches_real_arithmetic_and_stays_non_negative():
    from mathpractice_skill import subtraction_table
    for a, b, answer in subtraction_table(7):
        assert a - b == answer
        assert answer >= 0


def test_division_table_matches_real_arithmetic():
    from mathpractice_skill import division_table
    for a, b, answer in division_table(7):
        assert a / b == answer


def test_fact_table_generators_registry_covers_all_four_operations():
    from mathpractice_skill import FACT_TABLE_GENERATORS, OPERATIONS
    assert set(FACT_TABLE_GENERATORS.keys()) == set(OPERATIONS)
