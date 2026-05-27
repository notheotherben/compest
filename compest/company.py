from .currency import Currency, assert_currency
from .models import *

from typing import Iterator

class Company:
    """Represents an employer and the financial assumptions about their equity.

    A :class:`Company` captures the inputs needed to value any equity-based
    compensation offered by that employer: the current share price, the
    company's total valuation, an assumed annual growth rate (applied uniformly
    to both the share price and the valuation), and the default vesting period
    that grants from this company will use.

    The class also acts as the **factory** for the :class:`~compest.models.ValueSource`
    models (stock grants, option grants, refreshers, ...). Using the factory
    methods instead of constructing the model classes directly ensures that
    each grant is correctly tied to this company's share price, growth rate
    and default vesting schedule.

    Example:
        >>> from compest import Company, Currency, Job, Salary
        >>> usd = Currency(0, "$")
        >>> acme = Company(
        ...     name="Acme",
        ...     valuation=usd(50_000_000),
        ...     share_price=usd(10),
        ...     growth_percent=10,      # 10% annual growth
        ...     vesting_period=4,        # 4-year default vest
        ... )
        >>> job = Job(
        ...     "Senior Engineer",
        ...     acme,
        ...     Salary(annual=usd(150_000), additional_cash=usd(0)),
        ...     acme.one_off_stock_grant(usd(400_000)),
        ... )

    Args:
        name: A human-readable label used for plots and summaries.
        valuation: The company's current total valuation. Used by the renderer
            to project future valuations via ``valuation_after``.
        share_price: The current per-share price. Used to convert dollar-valued
            grants into share counts and to value equity at any point in time.
        growth_percent: Assumed annual growth rate (in percent) applied to both
            the share price and the valuation. ``0`` represents a flat company.
        vesting_period: Default vesting period (in years) for grants produced
            via the factory methods. Individual grants may override this.
    """

    def __init__(self, name: str, valuation: Currency, share_price: Currency, growth_percent: float, vesting_period: int = 4):
        self.name = name
        self.share_price = share_price
        self.valuation = valuation
        self.growth_percent = growth_percent
        self.vesting_period = vesting_period

    def share_prices(self) -> Iterator[Currency]:
        """Yield the share price for year 0, 1, 2, ... compounded by ``growth_percent``.

        This is an infinite iterator. Use ``itertools.islice`` (or zip it
        against another finite iterator like the payouts from a :class:`Job`)
        to consume a bounded number of years.

        For a single year prefer :meth:`share_price_after`, which avoids
        iterating through the intermediate years.
        """
        return growth_adjusted(self.growth_percent, repeat(self.share_price))

    def share_price_after(self, year: int) -> Currency:
        """Return the projected share price ``year`` years from now.

        The growth is compounded annually: ``share_price * (1 + growth_percent/100) ** year``.
        ``year=0`` returns the current share price unchanged.
        """
        return self.share_price.compound(self.growth_percent / 100, year)

    def valuations(self) -> Iterator[StoreOfValue]:
        """Yield the company's valuation for year 0, 1, 2, ... compounded by ``growth_percent``.

        This is an infinite iterator. Prefer :meth:`valuation_after` when you
        only need the valuation at a single point in time.
        """
        return growth_adjusted(self.growth_percent, repeat(self.valuation))

    def valuation_after(self, year: int) -> Currency:
        """Return the projected company valuation ``year`` years from now.

        Computed by compounding the current valuation at the company's annual
        growth rate.
        """
        return self.valuation.compound(self.growth_percent / 100, year)

    def shares(self, value: Currency) -> Equity:
        """Convert a cash amount into an :class:`~compest.equity.Equity` position of fully-paid shares.

        This is useful for representing equity you already own at the
        ``share_price`` (e.g. shares purchased outright with no exercise cost).
        For modelling vesting schedules use :meth:`one_off_stock_grant` or one
        of the other grant factories instead.
        """
        return Equity(assert_number(value / self.share_price), self.share_price(0))

    def options(self, value: Currency, strike_price: Currency) -> Equity:
        """Convert a cash amount into an :class:`~compest.equity.Equity` position of options at ``strike_price``.

        The returned :class:`Equity` records an exercise cost equal to
        ``strike_price * shares``, which is subtracted when the position is
        valued via :meth:`compest.equity.Equity.net_value`. For modelling
        options that vest over time use :meth:`options_grant`.
        """
        shares = assert_number(value / self.share_price)
        return Equity(shares, assert_currency(strike_price * shares))

    def options_grant(self, value: Currency, strike_price: Currency, dilution_percent: float = 30):
        """Create an :class:`~compest.models.OptionGrant` that vests over the company's default vesting period.

        ``value`` is the gross value of the grant at the current preferred
        (share) price; that value is divided by the share price to determine
        the option count, which is then reduced by ``dilution_percent`` to
        approximate future dilution. Each tranche carries an exercise cost
        equal to ``strike_price * tranche_shares``.
        """
        return OptionGrant(value, self.vesting_period, self.share_price, strike_price, dilution_percent=dilution_percent)

    def one_off_stock_grant(self, value: Currency, vesting_years: int|None = None):
        """Create a single :class:`~compest.models.OneOffStockGrant` that vests evenly over ``vesting_years``.

        Use this for a signing/initial grant whose vesting begins at the start
        of the job. The grant emits a zero-share placeholder for year 0
        followed by ``vesting_years`` equal tranches.

        To model a grant you started receiving before the job begins (i.e.
        partially vested historical equity), use :meth:`previous_stock_grant`
        instead - it skips the initial placeholder and emits only the
        tranches that remain unvested, which is more accurate than truncating
        a :class:`OneOffStockGrant`.

        Args:
            value: Dollar value of the grant at the company's current share price.
            vesting_years: Number of years to vest the grant over. Defaults to
                the company's ``vesting_period``.
        """
        return OneOffStockGrant(value, vesting_period=vesting_years or self.vesting_period, company=self)

    def previous_stock_grant(self, shares: float, years_vested: int, vesting_years: int|None = None):
        """Create a :class:`~compest.models.PreviousStockGrant` for equity that began vesting before the modelling window.

        Use this to represent a grant you received before the simulated start
        date which still has tranches remaining to vest. ``years_vested``
        already-vested tranches are skipped; ``vesting_years - years_vested``
        future tranches are emitted (plus one in the first modelled year, to
        align with the placeholder slot consumed by :class:`Job`).

        Prefer this over a truncated :meth:`one_off_stock_grant` because the
        ``shares`` are expressed directly as a count (matching the original
        grant size) and the vesting schedule correctly reflects only the
        unvested tranches.

        Args:
            shares: Total share count of the original grant (not just the
                unvested portion).
            years_vested: How many years of the original grant have already
                vested before the simulation starts.
            vesting_years: Total vesting period of the original grant.
                Defaults to the company's ``vesting_period``.
        """
        return PreviousStockGrant(shares, years_vested, vesting_period=vesting_years or self.vesting_period, company=self)

    def annual_stock_grant(self, value: Currency, vesting_years: int|None = None):
        """Create an :class:`~compest.models.AnnualStockGrant` that issues a fresh grant every year.

        Each year a new tranche of grants is issued at the projected share
        price for that year, so the dollar value of the grant remains
        constant but the share count varies with the share price. Each
        individual grant then vests evenly over ``vesting_years``, producing
        an overlapping schedule. In steady state (after ``vesting_years``)
        the employee is vesting one full grant's worth of shares per year.

        For a single grant that is not repeated annually, use
        :meth:`one_off_stock_grant` instead.
        """
        return AnnualStockGrant(value, vesting_period=vesting_years or self.vesting_period, company=self)

    def stock_refresher(self, value: Currency, vesting_years: int|None = None, after_years: int = 3, vesting_after_years: int|None = None):
        """Create a :class:`~compest.models.ShareRefresher` that issues a single new grant on a schedule.

        Unlike :meth:`annual_stock_grant`, a refresher issues a grant only
        every ``vesting_after_years`` years (typically aligned with the end
        of the previous grant's vesting period) and the grant itself begins
        vesting ``after_years`` years before that point - so a refresher with
        ``after_years=3, vesting_after_years=4`` "back-dates" the grant by one
        year, modelling the common pattern of a refresher granted in year 3
        which begins vesting immediately and overlaps the tail of the
        original grant.

        Args:
            value: Dollar value of the refresher grant at the time it is issued.
            vesting_years: Vesting period of each refresher grant. Defaults to
                the company's ``vesting_period``.
            after_years: How many years into a refresh cycle the grant starts
                vesting. The grant is priced at the share price ``after_years``
                years before it is issued.
            vesting_after_years: How many years apart successive refreshers
                are issued. Defaults to the company's ``vesting_period``.
        """
        return ShareRefresher(value, after_years=after_years, vesting_period=vesting_years or self.vesting_period, vesting_after_years=vesting_after_years or self.vesting_period, company=self)
