from .currency import *
from .equity import *

from abc import ABC, abstractmethod
from typing import Iterator, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .company import Company
class NetWorth:
    """A bundle of cash and equity positions that can be summed and revalued.

    A :class:`NetWorth` is the unit of accumulation used by :class:`~compest.job.Job`
    when modelling compensation. Cash values are added directly; equity
    positions are kept as a list of :class:`~compest.equity.Equity` so they
    can be revalued at the current share price via :meth:`sell_equity`.

    Supports ``+`` with both individual :class:`~compest.currency.StoreOfValue`
    instances (cash or equity) and other :class:`NetWorth` instances. The
    ``+`` operator always returns a new instance; use :meth:`add` for
    in-place mutation.
    """

    def __init__(self, cash: Currency = Currency(0), equity: list[Equity]|None = None):
        self.cash = cash
        self.equity: List[Equity] = equity or []


    def add(self, value: 'StoreOfValue') -> 'NetWorth':
        """Mutate this :class:`NetWorth` by adding a single cash or equity contribution and return ``self``."""
        if isinstance(value, Currency):
            self.cash += value
        elif isinstance(value, Equity):
            self.equity.append(value)
        else:
            raise NotImplementedError()
        
        return self


    def __add__(self, other: Union['StoreOfValue', 'NetWorth']) -> 'NetWorth':
        if isinstance(other, StoreOfValue):
            return NetWorth(self.cash, self.equity).add(other)
        elif isinstance(other, NetWorth):
            return NetWorth(self.cash + other.cash, [*self.equity, *other.equity])
        
        raise NotImplementedError()

    def __radd__(self, other: Union['StoreOfValue', 'NetWorth']) -> 'NetWorth':
        return self.__add__(other)
    
    def sell_equity(self, share_price: Currency) -> 'Currency':
        """Return the total dollar value of this :class:`NetWorth` if all equity were sold at ``share_price``.

        Each equity position is valued via :meth:`compest.equity.Equity.net_value`
        (which subtracts any exercise cost) and the result is added to the
        cash balance. This is the operation used by
        :meth:`compest.job.Job.annual_compensation` to convert per-year equity
        contributions into dollar values at the projected share price.
        """
        result = self.cash
        for equity in self.equity:
            result += assert_currency(equity.net_value(share_price))
        return result

    def __str__(self) -> str:
        if not self.equity:
            return f"{self.cash}"
        return f"{self.cash} + {sum([assert_number(stake.shares) for stake in self.equity]):,.0f} shares"

class ValueSource(ABC):
    """Abstract base class for anything that produces compensation over time.

    A :class:`ValueSource` is consumed by a :class:`~compest.job.Job` in two
    ways each modelled year:

    1. :meth:`payouts` returns an iterator that emits one
       :class:`~compest.currency.StoreOfValue` per year (cash, equity, or a
       zero-share placeholder). Sources that run out (``StopIteration``) are
       removed from the simulation.
    2. :meth:`next_year` is called with the current year index and may return
       a brand new :class:`ValueSource` to add to the simulation - this is
       how recurring schedules (annual grants, refreshers) work.

    Most users do not need to subclass :class:`ValueSource` directly; the
    built-in implementations (:class:`Salary`, :class:`OneOffStockGrant`,
    :class:`PreviousStockGrant`, :class:`AnnualStockGrant`,
    :class:`ShareRefresher`, :class:`OptionGrant`) cover the common cases.
    """

    def next_year(self, year: int) -> Optional['ValueSource']:
        """Optionally return a new :class:`ValueSource` to be added to the simulation after year ``year``.

        Override this in subclasses that schedule follow-up grants (such as
        :class:`AnnualStockGrant` or :class:`ShareRefresher`). The default
        implementation returns ``None``, meaning the source contributes
        nothing beyond its own :meth:`payouts`.
        """
        return None

    @abstractmethod
    def payouts(self) -> Iterator[StoreOfValue]:
        """Yield one :class:`~compest.currency.StoreOfValue` per modelled year.

        Implementations may yield :class:`~compest.currency.Currency` for
        cash, :class:`~compest.equity.Equity` for share/option grants, or a
        zero-valued placeholder to represent a year in which the source
        contributes nothing while still occupying a "slot" in the simulation.
        """
        pass
class OneOffStockGrant(ValueSource):
    """A single stock grant that vests evenly over ``vesting_period`` years.

    Yields a zero-share placeholder for year 0 (so that the grant begins
    vesting in year 1 alongside the first year of salary, mirroring the
    typical "1-year cliff" timing) followed by ``vesting_period`` equal
    tranches of ``shares / vesting_period`` shares each.

    The share count is derived from ``value / price`` at construction time
    and is held constant for the lifetime of the grant; growth in the
    company's share price is reflected only when the resulting equity is
    valued (see :meth:`compest.job.Job.annual_compensation`).

    Use :meth:`compest.company.Company.one_off_stock_grant` to construct one
    of these tied to a company's share price and default vesting period.
    For grants that began before the simulation starts use
    :class:`PreviousStockGrant` instead.
    """

    def __init__(self, value: Currency, vesting_period: int, company: 'Company', price: Currency|None = None):
        self.price = assert_currency(price or company.share_price)
        self.value = assert_currency(value)
        self.shares = assert_number(value / self.price)
        self.vesting_period = vesting_period
        self.company = company

    def payouts(self) -> Iterator[StoreOfValue]:
        yield Equity(0, self.price(0))
        for _ in range(self.vesting_period):
            yield Equity(self.shares / self.vesting_period, self.price(0))
class PreviousStockGrant(OneOffStockGrant):
    """A stock grant that began vesting before the simulation started.

    Unlike :class:`OneOffStockGrant`, this skips the initial zero-share
    placeholder and instead emits ``vesting_period - years_vested`` remaining
    tranches (each of ``shares / vesting_period``). This represents equity
    that you already hold a partially vested position in - typically when
    modelling a job change where you want to account for the unvested
    portion of an existing grant.

    Prefer this over building a truncated :class:`OneOffStockGrant`: it
    expresses the original grant size in shares (which matches how grants
    are usually documented) and produces the correct number of remaining
    tranches automatically.

    Use :meth:`compest.company.Company.previous_stock_grant` to construct one.
    """

    def __init__(self, shares: float, years_vested: int, vesting_period: int, company: 'Company'):
        super().__init__(assert_currency(company.share_price * shares), vesting_period, company)
        self.shares = shares
        self.years_vested = years_vested

    def payouts(self) -> Iterator[StoreOfValue]:
        yield Equity(self.shares / self.vesting_period, self.price(0))
        for _ in range(self.vesting_period - self.years_vested):
            yield Equity(self.shares / self.vesting_period, self.price(0))
class AnnualStockGrant(OneOffStockGrant):
    """A stock grant that is re-issued every year at the then-current share price.

    Each modelled year, :meth:`next_year` returns a new
    :class:`AnnualStockGrant` priced at the projected share price for that
    year. The new grant then vests evenly over ``vesting_period`` years
    using the standard :class:`OneOffStockGrant` schedule.

    The result is overlapping vesting schedules: after ``vesting_period``
    years the employee is vesting one full grant's worth of shares per
    year. Because each annual grant is priced at the share price of its
    issue year, the dollar value of each grant stays constant but the
    share count varies inversely with share-price growth.

    Use :meth:`compest.company.Company.annual_stock_grant` to construct one.
    """

    def next_year(self, year: int) -> Optional[ValueSource]:
        return AnnualStockGrant(self.value, self.vesting_period, self.company, price=self.company.share_price_after(year))

class ShareRefresher(ValueSource):
    """A stock grant that is issued on a recurring schedule (e.g. a "refresher" every N years).

    A :class:`ShareRefresher` itself emits no payouts; instead, every
    ``vesting_after_years`` years (specifically when ``(year + 1) %
    vesting_after_years == 0`` and ``year > 0``) it spawns a new
    :class:`OneOffStockGrant` that vests over ``vesting_period`` years.

    The ``after_years`` parameter back-dates the refresher's price: the
    spawned grant is priced at the share price from ``vesting_after_years -
    after_years`` years earlier, modelling the common pattern where a
    refresher granted near the end of the previous vesting cycle is
    actually priced at an earlier review-date share price.

    Use :meth:`compest.company.Company.stock_refresher` to construct one.
    For a grant that is issued every single year, use
    :class:`AnnualStockGrant` instead.
    """

    def __init__(self, value: Currency, after_years: int, vesting_period: int, vesting_after_years: int, company: 'Company'):
        self.value = assert_currency(value)
        self.after_years = after_years
        self.vesting_period = vesting_period
        self.vesting_after_years = vesting_after_years
        self.company = company

    def payouts(self) -> Iterator[StoreOfValue]:
        return iter([])
    
    def next_year(self, year: int) -> Optional[ValueSource]:
        if year > 0 and (year + 1) % self.vesting_after_years == 0:
            return OneOffStockGrant(self.value, self.vesting_period, self.company, price=self.company.share_price_after(year - (self.vesting_after_years - self.after_years)))
        return None

class OptionGrant(ValueSource):
    """A grant of stock **options** that vests evenly over ``vesting_period`` years.

    The number of underlying shares is computed as ``value /
    preferred_price``. Each vesting tranche is then reduced by
    ``dilution_percent`` to approximate the share-count impact of future
    funding rounds, and the resulting equity carries an exercise cost equal
    to ``strike_price * tranche_shares`` (so the option's *net value* at
    sale is ``share_price * shares - exercise_cost``).

    Like :class:`OneOffStockGrant`, a zero-share placeholder is yielded for
    year 0 so vesting begins in year 1.

    Use :meth:`compest.company.Company.options_grant` to construct one tied
    to a company's preferred price and default vesting period.
    """

    def __init__(self, value: Currency, vesting_period: int, preferred_price: Currency, strike_price: Currency, dilution_percent: float = 30):
        self.shares = assert_number(value / preferred_price)
        self.vesting_period = vesting_period
        self.strike_price = assert_currency(strike_price)
        self.dilution_percent = dilution_percent
    
    def payouts(self) -> Iterator[StoreOfValue]:
        yield Equity(0, self.strike_price(0))
        for _ in range(self.vesting_period):
            yield Equity(self.shares / self.vesting_period * (1 - self.dilution_percent / 100),  self.strike_price * (self.shares / self.vesting_period))

class Salary(ValueSource):
    """A cash compensation stream with optional bonus, pension and annual growth.

    Each year the source yields a single :class:`~compest.currency.Currency`
    payout equal to::

        salary = annual * (1 + annual_growth_percent/100) ** year_index
        bonus  = salary * bonus_percent/100
        pension = salary * pension_percent/100
        payout = salary + bonus + pension + additional_cash

    ``additional_cash`` is a flat amount added every year and is **not**
    subject to ``annual_growth_percent``; use it for fixed allowances or
    sign-on amounts that do not scale with merit increases.

    Bonus and pension percentages are applied to the current (grown)
    salary, so they compound implicitly along with the base salary.

    :class:`Salary` does not implement :meth:`~ValueSource.next_year`; its
    payout iterator is infinite, so it remains active for the full
    simulation.
    """

    def __init__(self, annual: Currency, additional_cash: Currency, bonus_percent: float = 0, pension_percent: float = 0, annual_growth_percent: float = 0):
        self.annual = annual
        self.additional_cash = additional_cash
        self.bonus_percent = bonus_percent
        self.pension_percent = pension_percent
        self.annual_growth_percent = annual_growth_percent

    def payouts(self) -> Iterator[StoreOfValue]:
        multiplier = 1.0
        while True:
            salary = self.annual * multiplier
            bonus = salary * (self.bonus_percent / 100)
            pension = salary * (self.pension_percent / 100)
            yield assert_currency(salary + bonus + pension + self.additional_cash)
            multiplier *= 1 + (self.annual_growth_percent / 100)
