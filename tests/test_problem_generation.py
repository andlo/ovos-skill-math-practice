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
