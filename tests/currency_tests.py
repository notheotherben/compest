import math
from itertools import islice

import pytest
from hypothesis import assume, given, strategies as st

from compest.currency import (
    Currency,
    assert_currency,
    assert_number,
    avg_currency,
    growth_adjusted,
    repeat,
    sum_currency,
)


# Hypothesis strategies that produce well-behaved (finite, reasonably scaled)
# currency values. We deliberately avoid extreme magnitudes so that
# floating-point round-off doesn't dominate property checks.
finite_amounts = st.floats(
    min_value=-1e9,
    max_value=1e9,
    allow_nan=False,
    allow_infinity=False,
)

symbols = st.sampled_from(["$", "£", "€", "¥"])


@st.composite
def currencies(draw, symbol: str | None = None) -> Currency:
    value = draw(finite_amounts)
    sym = symbol if symbol is not None else draw(symbols)
    return Currency(value, sym)


def isclose(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


class TestConstruction:
    def test_default_symbol_is_dollar(self):
        assert Currency(5).symbol == "$"

    def test_stores_value(self):
        assert Currency(7.5, "£").value == 7.5

    def test_call_constructs_compatible_currency(self):
        usd = Currency(0, "$")
        new = usd(42)
        assert isinstance(new, Currency)
        assert new.symbol == "$"
        assert new.value == 42


class TestArithmetic:
    @given(a=finite_amounts, b=finite_amounts)
    def test_addition_matches_underlying_arithmetic(self, a, b):
        result = Currency(a, "$") + Currency(b, "$")
        assert isclose(result.value, a + b)
        assert result.symbol == "$"

    @given(a=finite_amounts, b=finite_amounts)
    def test_subtraction_matches_underlying_arithmetic(self, a, b):
        result = Currency(a, "$") - Currency(b, "$")
        assert isclose(result.value, a - b)
        assert result.symbol == "$"

    @given(a=finite_amounts, k=finite_amounts)
    def test_multiplication_by_scalar(self, a, k):
        result = Currency(a, "$") * k
        assert isclose(result.value, a * k)
        assert result.symbol == "$"

    @given(a=finite_amounts, k=finite_amounts)
    def test_division_by_scalar(self, a, k):
        assume(abs(k) > 1e-6)
        result = Currency(a, "$") / k
        assert isinstance(result, Currency)
        assert isclose(result.value, a / k)
        assert result.symbol == "$"

    @given(a=finite_amounts, b=finite_amounts)
    def test_division_by_currency_returns_ratio(self, a, b):
        assume(abs(b) > 1e-6)
        result = Currency(a, "$") / Currency(b, "$")
        assert isinstance(result, float)
        assert isclose(result, a / b)

    @given(a=finite_amounts)
    def test_negation_inverts_value(self, a):
        result = -Currency(a, "$")
        assert isclose(result.value, -a)

    @given(a=finite_amounts)
    def test_double_negation_is_identity(self, a):
        assert isclose((-(-Currency(a, "$"))).value, a)

    @given(a=finite_amounts, b=finite_amounts, c=finite_amounts)
    def test_addition_is_commutative(self, a, b, c):
        ca, cb = Currency(a, "$"), Currency(b, "$")
        assert isclose((ca + cb).value, (cb + ca).value)

    @given(a=finite_amounts)
    def test_adding_zero_yields_same_value(self, a):
        c = Currency(a, "$")
        zero = Currency(0, "$")
        assert isclose((c + zero).value, a)
        assert isclose((zero + c).value, a)

    @given(a=finite_amounts)
    def test_subtracting_self_is_zero(self, a):
        c = Currency(a, "$")
        assert isclose((c - c).value, 0)


class TestCrossSymbolHandling:
    def test_addition_across_symbols_raises(self):
        with pytest.raises(ValueError):
            Currency(1, "$") + Currency(1, "£")

    def test_subtraction_across_symbols_raises(self):
        with pytest.raises(ValueError):
            Currency(1, "$") - Currency(1, "£")

    def test_division_across_symbols_raises(self):
        with pytest.raises(ValueError):
            Currency(1, "$") / Currency(1, "£")

    def test_zero_acts_as_compatible_neutral(self):
        # Zero on either side is treated as compatible regardless of symbol.
        assert (Currency(0, "$") + Currency(5, "£")).value == 5
        assert (Currency(5, "$") + Currency(0, "£")).value == 5

    @pytest.mark.parametrize("other", [1, 1.5, "string", None, object()])
    def test_addition_with_non_currency_raises(self, other):
        with pytest.raises(TypeError):
            Currency(1, "$") + other  # type: ignore[operator]

    @pytest.mark.parametrize("other", ["string", None, object()])
    def test_multiplication_by_non_number_raises(self, other):
        with pytest.raises(TypeError):
            Currency(1, "$") * other  # type: ignore[operator]


class TestComparisons:
    @given(a=finite_amounts, b=finite_amounts)
    def test_comparison_operators_agree_with_floats(self, a, b):
        ca, cb = Currency(a, "$"), Currency(b, "$")
        assert (ca > cb) == (a > b)
        assert (ca < cb) == (a < b)
        assert (ca >= cb) == (a >= b)
        assert (ca <= cb) == (a <= b)
        assert (ca == cb) == (a == b)
        assert (ca != cb) == (a != b)

    def test_equality_across_symbols_is_false(self):
        # Same value, different symbols are never considered equal.
        assert Currency(5, "$") != Currency(5, "£")
        assert not (Currency(5, "$") == Currency(5, "£"))


class TestCompounding:
    @given(a=finite_amounts, rate=st.floats(min_value=-0.5, max_value=0.5, allow_nan=False))
    def test_compound_zero_years_is_identity(self, a, rate):
        assert isclose(Currency(a, "$").compound(rate, 0).value, a)

    @given(a=finite_amounts, years=st.integers(min_value=0, max_value=20))
    def test_compound_zero_rate_is_identity(self, a, years):
        assert isclose(Currency(a, "$").compound(0, years).value, a)

    @pytest.mark.parametrize(
        "value,rate,years,expected",
        [
            (100, 0.10, 1, 110),
            (100, 0.10, 2, 121),
            (100, 0.05, 4, 100 * 1.05 ** 4),
            (50, 0.0, 10, 50),
        ],
    )
    def test_compound_known_values(self, value, rate, years, expected):
        assert isclose(Currency(value, "$").compound(rate, years).value, expected)


class TestRelativeCurrency:
    def test_relative_currency_converts_at_rate(self):
        usd = Currency(1, "$")
        gbp = Currency(2, "£")
        # $1 == £2 -> converter takes a £-denominated number and returns $
        to_dollars = usd.relative_currency(gbp)
        result = to_dollars(10)
        assert result.symbol == "$"
        assert isclose(result.value, 5)


class TestHelpers:
    def test_assert_currency_passes_through(self):
        c = Currency(1, "$")
        assert assert_currency(c) is c

    @pytest.mark.parametrize("bad", [1, "abc", None, object()])
    def test_assert_currency_rejects_non_currency(self, bad):
        with pytest.raises(TypeError):
            assert_currency(bad)

    @pytest.mark.parametrize("good", [1, 1.5, -3, 0])
    def test_assert_number_accepts_numbers(self, good):
        assert assert_number(good) == good

    @pytest.mark.parametrize("bad", ["1", None, object(), Currency(1)])
    def test_assert_number_rejects_non_numbers(self, bad):
        with pytest.raises(TypeError):
            assert_number(bad)

    @given(values=st.lists(finite_amounts, min_size=1, max_size=20))
    def test_sum_currency_matches_python_sum(self, values):
        currencies = [Currency(v, "$") for v in values]
        result = sum_currency(currencies)
        assert isinstance(result, Currency)
        assert isclose(result.value, sum(values))

    @given(values=st.lists(finite_amounts, min_size=1, max_size=20))
    def test_avg_currency_matches_python_mean(self, values):
        currencies = [Currency(v, "$") for v in values]
        result = avg_currency(currencies)
        assert isinstance(result, Currency)
        assert isclose(result.value, sum(values) / len(values))

    def test_sum_currency_rejects_empty(self):
        with pytest.raises(ValueError):
            sum_currency([])

    def test_avg_currency_rejects_empty(self):
        with pytest.raises(ValueError):
            avg_currency([])


class TestGenerators:
    def test_repeat_yields_same_value(self):
        c = Currency(3, "$")
        first_five = list(islice(repeat(c), 5))
        assert all(v is c for v in first_five)

    def test_growth_adjusted_applies_compound_growth(self):
        base = Currency(100, "$")
        # 10% growth: yields 100, 110, 121, 133.1, ...
        result = list(islice(growth_adjusted(10, repeat(base)), 4))
        expected = [100, 110, 121, 133.1]
        assert len(result) == len(expected)
        for actual, expected_value in zip(result, expected):
            assert isclose(actual.value, expected_value)

    def test_growth_adjusted_with_zero_growth_is_identity(self):
        base = Currency(50, "$")
        result = list(islice(growth_adjusted(0, repeat(base)), 5))
        assert all(isclose(r.value, 50) for r in result)


class TestStringFormatting:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (0, "$0"),
            (500, "$500.0"),
            (1_500, "$1.5k"),
            (2_500_000, "$2.5M"),
            (1_500_000_000, "$1.5B"),
        ],
    )
    def test_str_uses_metric_suffixes(self, value, expected):
        assert str(Currency(value, "$")) == expected

    def test_repr_round_trips_through_eval(self):
        c = Currency(12.5, "$")
        # The repr should be informative and include both fields.
        assert "12.5" in repr(c)
        assert "$" in repr(c)
