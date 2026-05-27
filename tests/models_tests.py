import math
from itertools import islice

import pytest

from compest.company import Company
from compest.currency import Currency
from compest.equity import Equity
from compest.models import (
    AnnualStockGrant,
    NetWorth,
    OneOffStockGrant,
    OptionGrant,
    PreviousStockGrant,
    Salary,
    ShareRefresher,
)


def isclose(a: float, b: float, rel: float = 1e-9, abs_: float = 1e-6) -> bool:
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_)


class TestNetWorth:
    def test_default_construction_is_empty(self, usd):
        net = NetWorth()
        assert net.cash.value == 0
        assert net.equity == []

    def test_add_currency_accumulates_cash(self, usd):
        net = NetWorth(cash=usd(10))
        net.add(usd(5))
        assert net.cash.value == 15

    def test_add_equity_appends_to_equity_list(self, usd):
        equity = Equity(10, usd(100))
        net = NetWorth()
        net.add(equity)
        assert net.equity == [equity]

    def test_add_unknown_type_raises(self):
        net = NetWorth()
        with pytest.raises(NotImplementedError):
            net.add(object())  # type: ignore[arg-type]

    def test_add_operator_with_currency_returns_new_networth(self, usd):
        original = NetWorth(cash=usd(10))
        result = original + usd(5)
        assert result.cash.value == 15
        # Operator returns a new instance and does not mutate the original.
        assert original.cash.value == 10

    def test_add_operator_combines_two_networths(self, usd):
        a = NetWorth(cash=usd(10), equity=[Equity(1, usd(1))])
        b = NetWorth(cash=usd(20), equity=[Equity(2, usd(2))])
        combined = a + b
        assert combined.cash.value == 30
        assert len(combined.equity) == 2

    def test_sell_equity_combines_cash_and_equity_value(self, usd):
        net = NetWorth(cash=usd(50), equity=[Equity(10, usd(20))])
        # Selling at $5 => 5*10 - 20 + 50 = 80
        result = net.sell_equity(usd(5))
        assert result.value == 80

    def test_sell_equity_with_no_equity_returns_cash(self, usd):
        net = NetWorth(cash=usd(50))
        assert net.sell_equity(usd(10)).value == 50


class TestOneOffStockGrant:
    def test_yields_initial_empty_grant_then_vests_evenly(self, company, usd):
        grant = OneOffStockGrant(usd(400), vesting_period=4, company=company)
        payouts = list(grant.payouts())

        # 1 initial empty + 4 vesting yields
        assert len(payouts) == 5
        # First payout has zero shares (placeholder for year 0).
        assert payouts[0].shares == 0
        # Each subsequent payout vests 1/4 of the total shares.
        expected_shares = 400 / 10 / 4  # value / share_price / vesting_period = 10
        for payout in payouts[1:]:
            assert isclose(payout.shares, expected_shares)

    def test_total_vested_shares_equal_initial_grant(self, company, usd):
        grant = OneOffStockGrant(usd(1000), vesting_period=4, company=company)
        total_shares = sum(p.shares for p in grant.payouts())
        assert isclose(total_shares, 100)  # 1000 / 10

    def test_next_year_returns_none(self, company, usd):
        grant = OneOffStockGrant(usd(400), vesting_period=4, company=company)
        assert grant.next_year(0) is None
        assert grant.next_year(5) is None


class TestPreviousStockGrant:
    def test_remaining_vesting_yields_correct_count(self, company, usd):
        # 4-year vest with 1 year already vested -> 3 remaining years of vesting
        # plus the initial yield used by Job() to consume the placeholder slot.
        grant = PreviousStockGrant(
            shares=40, years_vested=1, vesting_period=4, company=company
        )
        payouts = list(grant.payouts())
        # The implementation yields: one initial (matching the standard
        # OneOffStockGrant placeholder) and then `vesting_period - years_vested`
        # subsequent vesting yields.
        assert len(payouts) == 1 + (4 - 1)

    def test_each_payout_is_one_period_of_total_shares(self, company, usd):
        grant = PreviousStockGrant(
            shares=40, years_vested=2, vesting_period=4, company=company
        )
        payouts = list(grant.payouts())
        for payout in payouts:
            assert isclose(payout.shares, 40 / 4)


class TestAnnualStockGrant:
    def test_next_year_produces_grant_at_new_price(self, company, usd):
        grant = AnnualStockGrant(usd(400), vesting_period=4, company=company)
        new_grant = grant.next_year(1)
        assert isinstance(new_grant, AnnualStockGrant)
        # Price after 1 year of 10% growth
        assert isclose(new_grant.price.value, 10 * 1.10)


class TestShareRefresher:
    def test_no_payouts_directly(self, company, usd):
        refresher = ShareRefresher(
            usd(400),
            after_years=3,
            vesting_period=4,
            vesting_after_years=4,
            company=company,
        )
        assert list(refresher.payouts()) == []

    def test_grants_new_one_off_grant_on_schedule(self, company, usd):
        refresher = ShareRefresher(
            usd(400),
            after_years=3,
            vesting_period=4,
            vesting_after_years=4,
            company=company,
        )
        # Triggers when (year + 1) % vesting_after_years == 0 and year > 0
        # i.e. year = 3
        assert refresher.next_year(0) is None
        assert refresher.next_year(1) is None
        assert refresher.next_year(2) is None
        granted = refresher.next_year(3)
        assert isinstance(granted, OneOffStockGrant)


class TestOptionGrant:
    def test_yields_initial_empty_grant_then_vests_evenly(self, usd):
        preferred = usd(10)
        strike = usd(2)
        grant = OptionGrant(
            usd(400), vesting_period=4, preferred_price=preferred, strike_price=strike
        )
        payouts = list(grant.payouts())
        # 1 initial placeholder + 4 vesting payouts.
        assert len(payouts) == 5
        assert payouts[0].shares == 0

        # Each vested payout: shares/vesting_period * (1 - dilution/100)
        # = 40 / 4 * (1 - 0.3) = 7
        for payout in payouts[1:]:
            assert isclose(payout.shares, 7)
            # Exercise cost is strike_price * (shares/vesting_period)
            # = 2 * 10 = 20
            assert isclose(payout.exercise_cost.value, 20)

    @pytest.mark.parametrize("dilution", [0, 10, 50, 75])
    def test_dilution_reduces_share_count(self, usd, dilution):
        grant = OptionGrant(
            usd(400),
            vesting_period=4,
            preferred_price=usd(10),
            strike_price=usd(2),
            dilution_percent=dilution,
        )
        payouts = list(grant.payouts())
        vested = payouts[1]
        assert isclose(vested.shares, 10 * (1 - dilution / 100))


class TestSalary:
    def test_flat_salary_yields_constant_total(self, usd):
        salary = Salary(annual=usd(100_000), additional_cash=usd(0))
        first_three = list(islice(salary.payouts(), 3))
        for payout in first_three:
            assert isclose(payout.value, 100_000)

    def test_bonus_and_pension_are_added(self, usd):
        salary = Salary(
            annual=usd(100_000),
            additional_cash=usd(5_000),
            bonus_percent=10,
            pension_percent=5,
        )
        first = next(iter(salary.payouts()))
        # 100k + 10k bonus + 5k pension + 5k additional cash
        assert isclose(first.value, 120_000)

    def test_annual_growth_compounds(self, usd):
        salary = Salary(
            annual=usd(100_000), additional_cash=usd(0), annual_growth_percent=5
        )
        payouts = list(islice(salary.payouts(), 4))
        for n, payout in enumerate(payouts):
            assert isclose(payout.value, 100_000 * 1.05 ** n)

    def test_additional_cash_does_not_grow(self, usd):
        salary = Salary(
            annual=usd(100_000),
            additional_cash=usd(10_000),
            annual_growth_percent=10,
        )
        payouts = list(islice(salary.payouts(), 3))
        for n, payout in enumerate(payouts):
            assert isclose(payout.value, 100_000 * 1.10 ** n + 10_000)
