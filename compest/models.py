from abc import ABC, abstractmethod
from typing import cast, Dict, Generator, Iterator, List, Optional, Tuple, Union
from .currency import *
from .equity import *

class NetWorth:
    def __init__(self, cash: Currency|None = None, equity: list[Equity]|None = None):
        self.cash = assert_currency(cash or Currency(0))
        self.equity: List[Equity] = equity or []


    def add(self, value: 'StoreOfValue') -> 'NetWorth':
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
        result = self.cash
        for equity in self.equity:
            result += assert_currency(equity.net_value(share_price))
        return result

    def __str__(self) -> str:
        if not self.equity:
            return f"{self.cash}"
        return f"{self.cash} + {sum([assert_number(stake.shares) for stake in self.equity]):,.0f} shares"

class ValueSource(ABC):
    def next_year(self, year: int) -> Optional['ValueSource']:
        return None

    @abstractmethod
    def payouts(self) -> Iterator[StoreOfValue]:
        pass
class OneOffStockGrant(ValueSource):
    def __init__(self, value: Currency, vesting_period: int, company: 'Company', price: Currency|None = None):
        self.price = assert_currency(price or company.share_price)
        self.value = assert_currency(value)
        self.shares = assert_number(value / self.price)
        self.vesting_period = vesting_period
        self.company = company

    def payouts(self) -> Iterator[StoreOfValue]:
        yield Equity(0)
        for _ in range(self.vesting_period):
            yield Equity(self.shares / self.vesting_period)

class PreviousStockGrant(OneOffStockGrant):
    def __init__(self, shares: float, years_vested: int, vesting_period: int, company: 'Company'):
        super().__init__(assert_currency(company.share_price * shares), vesting_period, company)
        self.shares = shares
        self.years_vested = years_vested

    def payouts(self) -> Iterator[StoreOfValue]:
        yield Equity(self.shares / self.vesting_period)
        for _ in range(self.vesting_period - self.years_vested):
            yield Equity(self.shares / self.vesting_period)
class AnnualStockGrant(OneOffStockGrant):
    def next_year(self, year: int) -> Optional[ValueSource]:
        return AnnualStockGrant(self.value, self.vesting_period, self.company, price=self.company.share_price_after(year))

class ShareRefresher(ValueSource):
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
    def __init__(self, value: Currency, vesting_period: int, preferred_price: Currency, strike_price: Currency, dilution_percent: float = 30):
        self.shares = assert_number(value / preferred_price)
        self.vesting_period = vesting_period
        self.strike_price = assert_currency(strike_price)
        self.dilution_percent = dilution_percent
    
    def payouts(self) -> Iterator[StoreOfValue]:
        yield Equity(0)
        for _ in range(self.vesting_period):
            yield Equity(self.shares / self.vesting_period * (1 - self.dilution_percent / 100),  self.strike_price * (self.shares / self.vesting_period))

class Salary(ValueSource):
    def __init__(self, annual: Currency, bonus_percent: float = 0, pension_percent: float = 0, additional_cash: Currency = Currency(0), annual_growth_percent: float = 0):
        self.annual = annual
        self.bonus_percent = bonus_percent
        self.pension_percent = pension_percent
        self.additional_cash = additional_cash
        self.annual_growth_percent = annual_growth_percent

    def payouts(self) -> Iterator[StoreOfValue]:
        multiplier = 1.0
        while True:
            salary = self.annual * multiplier
            bonus = salary * (self.bonus_percent / 100)
            pension = salary * (self.pension_percent / 100)
            yield assert_currency(salary + bonus + pension + self.additional_cash)
            multiplier *= 1 + (self.annual_growth_percent / 100)

def repeat[T: StoreOfValue](value: T) -> Iterator[T]:
    while True:
        yield value

def growth_adjusted(percent_per_annum: float, values: Iterator[Currency]) -> Generator[Currency, None, None]:
    multiplier = 1.0
    for value in values:
        yield value * multiplier
        multiplier *= 1 + (percent_per_annum / 100)

class Company:
    def __init__(self, name: str, valuation: Currency, share_price: Currency, growth_percent: float, vesting_period: int = 4):
        self.name = name
        self.share_price = share_price
        self.valuation = valuation
        self.growth_percent = growth_percent
        self.vesting_period = vesting_period

    def share_prices(self) -> Iterator[Currency]:
        return growth_adjusted(self.growth_percent, repeat(self.share_price))
    
    def share_price_after(self, year: int) -> Currency:
        return self.share_price.compound(self.growth_percent / 100, year)

    def valuations(self) -> Iterator[StoreOfValue]:
        return growth_adjusted(self.growth_percent, repeat(self.valuation))
    
    def valuation_after(self, year: int) -> Currency:
        return self.valuation.compound(self.growth_percent / 100, year)
    
    def shares(self, value: Currency) -> Equity:
        return Equity(assert_number(value / self.share_price))
    
    def options(self, value: Currency, strike_price: Currency) -> Equity:
        shares = assert_number(value / self.share_price)
        return Equity(shares, assert_currency(strike_price * shares))
    
    def options_grant(self, value: Currency, strike_price: Currency, dilution_percent: float = 30):
        return OptionGrant(value, self.vesting_period, self.share_price, strike_price, dilution_percent=dilution_percent)
    
    def one_off_stock_grant(self, value: Currency, vesting_years: int|None = None):
        return OneOffStockGrant(value, vesting_period=vesting_years or self.vesting_period, company=self)
    
    def previous_stock_grant(self, shares: float, years_vested: int, vesting_years: int|None = None):
        return PreviousStockGrant(shares, years_vested, vesting_period=vesting_years or self.vesting_period, company=self)
    
    def annual_stock_grant(self, value: Currency, vesting_years: int|None = None):
        return AnnualStockGrant(value, vesting_period=vesting_years or self.vesting_period, company=self)
    
    def stock_refresher(self, value: Currency, vesting_years: int|None = None, after_years: int = 3, vesting_after_years: int|None = None):
        return ShareRefresher(value, after_years=after_years, vesting_period=vesting_years or self.vesting_period, vesting_after_years=vesting_after_years or self.vesting_period, company=self)

class Job:
    def __init__(self, name: str, company: Company, *value_sources: ValueSource):
        self.name = name
        self.company = company
        self.value_sources = value_sources

    def payouts(self) -> Iterator[NetWorth]:
        sources: List[Tuple[ValueSource, Iterator[StoreOfValue]]] = []
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
        for payout, share_value in zip(self.payouts(), self.company.share_prices()):
            yield payout.sell_equity(share_value)

    def annual_compensation_after(self, year: int) -> Currency:
        iter = self.annual_compensation()
        for _ in range(year):
            next(iter)

        return next(iter)

    def cumulative_value(self) -> Iterator[Currency]:
        total = NetWorth()
        for payout, share_value in zip(self.payouts(), self.company.share_prices()):
            total += payout
            yield total.sell_equity(share_value)

    def cumulative_value_after(self, year: int) -> Currency:
        iter = self.cumulative_value()
        for _ in range(year):
            next(iter)

        return next(iter)
