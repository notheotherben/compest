import math
from itertools import islice

import pytest

from compest.company import Company
from compest.currency import Currency
from compest.job import Job
from compest.models import (
    AnnualStockGrant,
    OneOffStockGrant,
    OptionGrant,
    Salary,
    ShareRefresher,
)


def isclose(a: float, b: float, rel: float = 1e-9, abs_: float = 1e-6) -> bool:
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_)


@pytest.fixture
def salary_only_job(flat_company, usd):
    return Job(
        "salary-only",
        flat_company,
        Salary(annual=usd(100_000), additional_cash=usd(0)),
    )


@pytest.fixture
def salary_with_grant_job(flat_company, usd):
    return Job(
        "salary+grant",
        flat_company,
        Salary(annual=usd(100_000), additional_cash=usd(0)),
        flat_company.one_off_stock_grant(usd(400)),
    )


class TestAnnualCompensation:
    def test_salary_only_yields_flat_compensation(self, salary_only_job):
        comp = list(islice(salary_only_job.annual_compensation(), 4))
        for c in comp:
            assert isclose(c.value, 100_000)

    def test_salary_and_grant_includes_vested_value_each_year(
        self, salary_with_grant_job
    ):
        # Flat company, $10 share price. $400 grant over 4 years = $100/yr of vesting value.
        # Year 0 emits the placeholder (no shares), so equity value is 0.
        comp = list(islice(salary_with_grant_job.annual_compensation(), 5))
        assert isclose(comp[0].value, 100_000)
        for c in comp[1:]:
            assert isclose(c.value, 100_100)

    def test_annual_compensation_after_returns_specific_year(
        self, salary_with_grant_job
    ):
        assert isclose(
            salary_with_grant_job.annual_compensation_after(0).value, 100_000
        )
        assert isclose(
            salary_with_grant_job.annual_compensation_after(2).value, 100_100
        )


class TestCumulativeValue:
    def test_salary_only_accumulates_linearly(self, salary_only_job):
        cumulative = list(islice(salary_only_job.cumulative_value(), 4))
        for n, c in enumerate(cumulative):
            assert isclose(c.value, 100_000 * (n + 1))

    def test_grant_contributes_to_cumulative_value(self, salary_with_grant_job):
        # By year 4 (index 4 -> 5 payouts), cash = 5 * 100k = 500k
        # equity = 40 shares total at $10 each = $400
        result = salary_with_grant_job.cumulative_value_after(4)
        assert isclose(result.value, 500_400)


class TestAnnualGrants:
    def test_annual_stock_grant_adds_new_grant_each_year(self, flat_company, usd):
        # Annual $400 grant in flat company => each year adds 40 shares vesting over 4 years
        # so steady state per-year vested = 4 grants * 10 shares = 40 shares = $400/yr
        job = Job(
            "annual-grants",
            flat_company,
            flat_company.annual_stock_grant(usd(400)),
        )
        # Use a couple of years of warm-up then check steady state.
        comp = list(islice(job.annual_compensation(), 6))
        # Year 0 is placeholders -> 0
        assert isclose(comp[0].value, 0)
        # By year 4 we should have 4 grants vesting concurrently (10 shares each) = $400
        assert isclose(comp[4].value, 400)
        assert isclose(comp[5].value, 400)


class TestShareGrowthEffect:
    def test_growing_share_price_increases_grant_value(self, company, usd):
        # 10% growth share price. $400 one-off grant vests $100/yr at the initial price,
        # but the equity is valued at the current share price each year.
        job = Job(
            "grant-only",
            company,
            company.one_off_stock_grant(usd(400)),
        )
        comp = list(islice(job.annual_compensation(), 5))
        # Year 0 -> placeholder, value 0
        assert isclose(comp[0].value, 0)
        # Year n >= 1 -> 10 shares vested, share price = $10 * 1.10^n
        for n in range(1, 5):
            expected = 10 * 10 * (1.10 ** n)
            assert isclose(comp[n].value, expected)
