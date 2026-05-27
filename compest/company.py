from .currency import Currency, assert_currency
from .models import *

from typing import Iterator

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
        return Equity(assert_number(value / self.share_price), self.share_price(0))
    
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
