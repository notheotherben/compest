from .company import Company
from .currency import Currency, assert_currency
from .models import *

from typing import Iterator

class Job:
    def __init__(self, name: str, company: Company, *value_sources: ValueSource):
        self.name = name
        self.company = company
        self.value_sources = value_sources

    def payouts(self) -> Iterator[NetWorth]:
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
