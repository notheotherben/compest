from .currency import *
from .equity import *

from abc import ABC, abstractmethod
from typing import Iterator, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .company import Company
class NetWorth:
    def __init__(self, cash: Currency = Currency(0), equity: list[Equity]|None = None):
        self.cash = cash
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
        yield Equity(0, self.price(0))
        for _ in range(self.vesting_period):
            yield Equity(self.shares / self.vesting_period, self.price(0))
class PreviousStockGrant(OneOffStockGrant):
    def __init__(self, shares: float, years_vested: int, vesting_period: int, company: 'Company'):
        super().__init__(assert_currency(company.share_price * shares), vesting_period, company)
        self.shares = shares
        self.years_vested = years_vested

    def payouts(self) -> Iterator[StoreOfValue]:
        yield Equity(self.shares / self.vesting_period, self.price(0))
        for _ in range(self.vesting_period - self.years_vested):
            yield Equity(self.shares / self.vesting_period, self.price(0))
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
        yield Equity(0, self.strike_price(0))
        for _ in range(self.vesting_period):
            yield Equity(self.shares / self.vesting_period * (1 - self.dilution_percent / 100),  self.strike_price * (self.shares / self.vesting_period))

class Salary(ValueSource):
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
