import math

import pytest

from compest.company import Company
from compest.currency import Currency
from compest.equity import Equity
from compest.models import (
    AnnualStockGrant,
    OneOffStockGrant,
    OptionGrant,
    PreviousStockGrant,
    ShareRefresher,
)


def isclose(a: float, b: float, rel: float = 1e-9, abs_: float = 1e-6) -> bool:
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_)


class TestSharePriceGrowth:
    @pytest.mark.parametrize("year", [0, 1, 2, 5, 10])
    def test_share_price_after_compounds_growth(self, company, year):
        expected = 10 * (1 + 0.10) ** year
        assert isclose(company.share_price_after(year).value, expected)

    @pytest.mark.parametrize("year", [0, 1, 2, 5, 10])
    def test_valuation_after_compounds_growth(self, company, year):
        expected = 1_000_000 * (1 + 0.10) ** year
        assert isclose(company.valuation_after(year).value, expected)

    def test_share_prices_iterator_matches_after(self, company):
        from itertools import islice

        prices = list(islice(company.share_prices(), 5))
        for n, price in enumerate(prices):
            assert isclose(price.value, company.share_price_after(n).value)


class TestEquityHelpers:
    def test_shares_returns_equity_with_no_exercise_cost(self, company, usd):
        equity = company.shares(usd(1000))
        assert isinstance(equity, Equity)
        # 1000 / 10 = 100 shares; exercise_cost is zero.
        assert equity.shares == 100
        assert equity.exercise_cost.value == 0

    def test_options_returns_equity_with_strike_cost(self, company, usd):
        equity = company.options(usd(1000), strike_price=usd(2))
        # 1000 / 10 = 100 shares; exercise cost = strike * shares = 200
        assert equity.shares == 100
        assert equity.exercise_cost.value == 200


class TestGrantFactories:
    def test_one_off_stock_grant_uses_default_vesting(self, company, usd):
        grant = company.one_off_stock_grant(usd(400))
        assert isinstance(grant, OneOffStockGrant)
        assert grant.vesting_period == company.vesting_period

    def test_one_off_stock_grant_accepts_custom_vesting(self, company, usd):
        grant = company.one_off_stock_grant(usd(400), vesting_years=2)
        assert grant.vesting_period == 2

    def test_previous_stock_grant_factory(self, company):
        grant = company.previous_stock_grant(shares=40, years_vested=1)
        assert isinstance(grant, PreviousStockGrant)
        assert grant.shares == 40
        assert grant.years_vested == 1

    def test_annual_stock_grant_factory(self, company, usd):
        grant = company.annual_stock_grant(usd(400))
        assert isinstance(grant, AnnualStockGrant)

    def test_stock_refresher_factory(self, company, usd):
        refresher = company.stock_refresher(usd(400), after_years=3)
        assert isinstance(refresher, ShareRefresher)
        assert refresher.after_years == 3

    def test_options_grant_factory(self, company, usd):
        grant = company.options_grant(usd(400), strike_price=usd(2))
        assert isinstance(grant, OptionGrant)
