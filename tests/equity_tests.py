import math

import pytest
from hypothesis import assume, given, strategies as st

from compest.currency import Currency
from compest.equity import Equity


share_counts = st.floats(min_value=1, max_value=1e6, allow_nan=False, allow_infinity=False)
prices = st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False)


def isclose(a: float, b: float, rel: float = 1e-9, abs_: float = 1e-6) -> bool:
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_)


class TestNetValue:
    @given(shares=share_counts, price=prices, cost=prices)
    def test_net_value_is_price_times_shares_minus_cost(self, shares, price, cost):
        equity = Equity(shares, Currency(cost, "$"))
        result = equity.net_value(Currency(price, "$"))
        assert isinstance(result, Currency)
        assert isclose(result.value, price * shares - cost)

    def test_net_value_can_be_negative(self):
        equity = Equity(10, Currency(200, "$"))
        # Price below break-even => negative net value (loss on exercise).
        assert equity.net_value(Currency(5, "$")).value == 5 * 10 - 200


class TestArithmetic:
    def test_addition_sums_shares(self):
        a = Equity(10, Currency(100, "$"))
        b = Equity(5, Currency(50, "$"))
        result = a + b
        assert result.shares == 15

    def test_subtraction_subtracts_shares_and_costs(self):
        a = Equity(10, Currency(100, "$"))
        b = Equity(4, Currency(40, "$"))
        result = a - b
        assert result.shares == 6
        assert result.exercise_cost.value == 60

    def test_multiplication_by_currency_returns_total_value(self):
        equity = Equity(10, Currency(50, "$"))
        total = equity * Currency(7, "$")
        assert isinstance(total, Currency)
        assert total.value == 70

    @pytest.mark.parametrize("other", [1, 1.0, "string", None])
    def test_addition_with_non_equity_raises(self, other):
        with pytest.raises(TypeError):
            Equity(1, Currency(1, "$")) + other  # type: ignore[operator]

    @pytest.mark.parametrize("other", [1, 1.0, "string", None])
    def test_multiplication_by_non_currency_raises(self, other):
        with pytest.raises(TypeError):
            Equity(1, Currency(1, "$")) * other  # type: ignore[operator]


class TestStringFormatting:
    @pytest.mark.parametrize(
        "shares,expected",
        [
            (0, "0 shares"),
            (1, "1 shares"),
            (1234, "1,234 shares"),
        ],
    )
    def test_str_formats_share_count(self, shares, expected):
        assert str(Equity(shares, Currency(0, "$"))) == expected
