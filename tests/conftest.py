import pytest

from compest.company import Company
from compest.currency import Currency


@pytest.fixture
def usd() -> Currency:
    """A zero-valued USD currency useful as a symbol/factory."""
    return Currency(0, "$")


@pytest.fixture
def gbp() -> Currency:
    """A zero-valued GBP currency useful as a symbol/factory."""
    return Currency(0, "£")


@pytest.fixture
def company(usd: Currency) -> Company:
    """A simple company with a $10 share price and 10% annual growth."""
    return Company(
        name="Acme",
        valuation=usd(1_000_000),
        share_price=usd(10),
        growth_percent=10,
        vesting_period=4,
    )


@pytest.fixture
def flat_company(usd: Currency) -> Company:
    """A company with no share price growth - useful for deterministic tests."""
    return Company(
        name="Flat Co.",
        valuation=usd(1_000_000),
        share_price=usd(10),
        growth_percent=0,
        vesting_period=4,
    )
