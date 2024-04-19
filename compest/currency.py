from abc import ABC, abstractmethod
from math import log10
from typing import Union, Self

USD_TO_EUR = 0.86
USD_TO_GBP = 0.75


class StoreOfValue:
    def __init__(self, symbol: str):
        self.symbol = symbol

class Currency(StoreOfValue):
    def __init__(self, value: float, symbol: str = "$"):
        super().__init__(symbol)
        self.value = value

    def compound(self, rate: float, years: int) -> 'Currency':
        return Currency(self.value * (1 + rate) ** years)
    
    def to_eur(self) -> 'Currency':
        return Currency(self.value * USD_TO_EUR, "€")
    
    def to_gbp(self) -> 'Currency':
        return Currency(self.value * USD_TO_GBP, "£")

    def __add__(self, other: 'Currency') -> 'Currency':
        if not isinstance(other, Currency):
            raise TypeError()
        
        return Currency(self.value + other.value)
    
    def __sub__(self, other: 'Currency') -> 'Currency':
        if not isinstance(other, Currency):
            raise TypeError()
        
        return Currency(self.value - other.value)
    
    def __mul__(self, other: float) -> 'Currency':
        if not isinstance(other, (int, float)):
            raise TypeError()
        return Currency(self.value * other)
    
    def __truediv__(self, other: Union[float, int, 'Currency']) -> Union[float, 'Currency']:
        if isinstance(other, Currency):
            return self.value / other.value
        
        if not isinstance(other, (int, float)):
            raise TypeError()
        
        return Currency(self.value / other)
    
    def __gt__(self, other: 'Currency') -> bool:
        if not isinstance(other, Currency):
            raise TypeError()

        return self.value > other.value
    
    def __lt__(self, other: 'Currency') -> bool:
        if not isinstance(other, Currency):
            raise TypeError()

        return self.value < other.value
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Currency):
            raise TypeError()

        return self.value == other.value
    
    def __ne__(self, other: object) -> bool:
        if not isinstance(other, Currency):
            raise TypeError()

        return self.value != other.value
    
    def __ge__(self, other: 'Currency') -> bool:
        if not isinstance(other, Currency):
            raise TypeError()

        return self.value >= other.value
    
    def __le__(self, other: 'Currency') -> bool:    
        if not isinstance(other, Currency):
            raise TypeError()

        return self.value <= other.value
    
    def __neg__(self) -> 'Currency':
        return Currency(-self.value)

    def __str__(self) -> str:
        if self.value == 0:
            return f"{self.symbol}0"

        divisor_index = log10(abs(self.value))//3
        suffix = ["", "k", "M", "B", "T"][int(divisor_index)]
        divisor = 1000**divisor_index

        return f"{self.symbol}{self.value/divisor:,.1f}{suffix}"
    
    def __repr__(self) -> str:
        return f"Currency({self.value})"
    
    def _repr_pretty_(self, p, cycle: bool) -> str:
        return p.text(str(self))

def assert_currency(value) -> Currency:
    if isinstance(value, Currency):
        return value
    
    raise TypeError(f"The value {repr(value)} was expected to be a Currency")

def assert_number(value) -> float:
    if isinstance(value, (int, float)):
        return value
    
    raise TypeError(f"The value {repr(value)} was expected to be a number")

def sum_currency(values: list[Currency]) -> Currency:
    return sum(values, Currency(0))

def avg_currency(values: list[Currency]) -> Currency:
    if not values:
        return Currency(0)
    return assert_currency(sum_currency(values) / len(values))

def usd(value: float) -> Currency:
    return Currency(value)

def eur(value: float) -> Currency:
    return Currency(value / USD_TO_EUR)

def gbp(value: float) -> Currency:
    return Currency(value / USD_TO_GBP)