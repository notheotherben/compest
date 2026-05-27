from .company import Company
from .currency import Currency, assert_currency
from .models import *

from typing import Iterator

class Job:
    """A job offer modelled as a collection of :class:`~compest.models.ValueSource` payouts.

    A :class:`Job` ties together a :class:`~compest.company.Company` (which
    provides the share-price model) with one or more value sources -
    typically a :class:`~compest.models.Salary` plus some combination of
    stock or option grants. Each modelled year, every value source emits
    a payout (cash or equity) and any grant that schedules follow-up grants
    (for example :class:`~compest.models.AnnualStockGrant` or
    :class:`~compest.models.ShareRefresher`) is given the opportunity to add
    a new active grant to the simulation.

    The class exposes the simulation through four iterators/accessors:

    - :meth:`payouts` - the raw per-year :class:`~compest.models.NetWorth`
      contributions.
    - :meth:`annual_compensation` / :meth:`annual_compensation_after` - the
      dollar-valued compensation **earned in a single year**, evaluating any
      equity at that year's projected share price.
    - :meth:`cumulative_value` / :meth:`cumulative_value_after` - the total
      compensation accumulated **up to and including** a given year, again
      with equity revalued at that year's projected share price.

    Example:
        >>> from compest import Company, Currency, Job, Salary
        >>> usd = Currency(0, "$")
        >>> acme = Company("Acme", usd(50_000_000), usd(10), 10, vesting_period=4)
        >>> job = Job(
        ...     "Senior Engineer",
        ...     acme,
        ...     Salary(annual=usd(150_000), additional_cash=usd(0), annual_growth_percent=5),
        ...     acme.one_off_stock_grant(usd(400_000)),
        ...     acme.annual_stock_grant(usd(100_000)),
        ... )
        >>> # Total comp accumulated by the end of year 4
        >>> job.cumulative_value_after(4)
        >>> # Comp earned in year 4 alone
        >>> job.annual_compensation_after(4)

    Args:
        name: A label for the offer (used by the rendering helpers).
        company: The :class:`~compest.company.Company` whose share-price model
            is used to value any equity emitted by the value sources.
        value_sources: Any number of :class:`~compest.models.ValueSource`
            instances. Order is not significant.
    """

    def __init__(self, name: str, company: Company, *value_sources: ValueSource):
        self.name = name
        self.company = company
        self.value_sources = value_sources

    def payouts(self) -> Iterator[NetWorth]:
        """Yield the raw :class:`~compest.models.NetWorth` produced each year.

        Each iteration represents one simulated year and sums the contributions
        from every currently-active value source. Sources that have exhausted
        their payout iterator (e.g. a :class:`~compest.models.OneOffStockGrant`
        after it has finished vesting) are removed automatically, and any new
        grants scheduled by ``next_year`` (e.g. additional grants from a
        :class:`~compest.models.AnnualStockGrant` or
        :class:`~compest.models.ShareRefresher`) are added to the simulation.

        The returned :class:`NetWorth` contains the **delta** for that year,
        not a running total - see :meth:`cumulative_value` for a running total.

        This is an infinite iterator; consume it with ``islice`` or a bounded
        zip.
        """
        sources: list[tuple[ValueSource, Iterator[StoreOfValue]]] = []
        for source in self.value_sources:
            sources.append((source, source.payouts()))

        year = 0
        while True:
            total = NetWorth()
            
            for (source, payouts) in list(sources):
                value = next(payouts, None)
                if value is None:
                    sources.remove((source, payouts))
                    continue
                else:
                    total += value

            for source in self.value_sources:
                granted = source.next_year(year)
                if granted is not None:
                    sources.append((granted, granted.payouts()))

            yield total
            year += 1
    
    def annual_compensation(self) -> Iterator[Currency]:
        """Yield the dollar-value compensation **earned in each year** of the simulation.

        For year ``n`` the value of any equity emitted that year is computed
        at the company's projected share price for year ``n`` (i.e. with
        ``growth_percent`` years of compounding applied). Cash payouts pass
        through unchanged.

        Use :meth:`annual_compensation_after` if you only need a single year.
        Use :meth:`cumulative_value` if you want a running total instead of
        a per-year value.
        """
        for payout, share_value in zip(self.payouts(), self.company.share_prices()):
            yield payout.sell_equity(share_value)

    def annual_compensation_after(self, year: int) -> Currency:
        """Return the compensation earned in the single year ``year`` (0-indexed).

        ``year=0`` is the first modelled year. Internally this iterates
        :meth:`annual_compensation`, discarding earlier years.
        """
        iter = self.annual_compensation()
        for _ in range(year):
            next(iter)

        return next(iter)

    def cumulative_value(self) -> Iterator[Currency]:
        """Yield the total dollar value accumulated **up to and including** each year.

        Equity accumulated across years is held in the running
        :class:`~compest.models.NetWorth` and revalued at each year's
        projected share price - so growth in the share price retroactively
        increases the value of previously-vested equity. Cash compensation
        simply accumulates without growth.

        Use :meth:`cumulative_value_after` if you only need a single year.
        Use :meth:`annual_compensation` for per-year (non-cumulative) values.
        """
        total = NetWorth()
        for payout, share_value in zip(self.payouts(), self.company.share_prices()):
            total += payout
            yield total.sell_equity(share_value)

    def cumulative_value_after(self, year: int) -> Currency:
        """Return the cumulative compensation accumulated by the end of year ``year`` (0-indexed)."""
        iter = self.cumulative_value()
        for _ in range(year):
            next(iter)

        return next(iter)
