"""Unit tests for the demo tools."""

import pytest

from app.tools.demo_tools import calculator, get_current_time


def test_calculator_multiplication() -> None:
    assert calculator.invoke({"expression": "123*456"}) == "56088"


def test_calculator_formats_integral_floats() -> None:
    assert calculator.invoke({"expression": "10/2"}) == "5"


def test_calculator_keeps_fractional_results() -> None:
    assert calculator.invoke({"expression": "1/8"}) == "0.125"


def test_calculator_precedence_and_parentheses() -> None:
    assert calculator.invoke({"expression": "(2+3)*4"}) == "20"


def test_calculator_rejects_non_arithmetic_input() -> None:
    with pytest.raises(ValueError):
        calculator.invoke({"expression": "__import__('os')"})


def test_calculator_rejects_syntax_error() -> None:
    with pytest.raises(ValueError):
        calculator.invoke({"expression": "2**"})


def test_get_current_time_returns_iso_utc() -> None:
    from datetime import datetime

    value = get_current_time.invoke({})
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0
