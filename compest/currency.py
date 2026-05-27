from abc import ABC, abstractmethod
from math import log10
from typing import Union, Iterator, Generator
from collections.abc import Callable

class StoreOfValue:
    def __init__(self, symbol: str):
        self.symbol = symbol

class Currency(StoreOfValue):
    def __init__(self, value: float, symbol: str = "$"):
        super().__init__(symbol)
        self.value = value

    def relative_currency(self, other: 'Currency') -> Callable[[float], 'Currency']:
        rate = self.value / other.value
        def converter(value: float) -> Currency:
            return Currency(value * rate, self.symbol)
        
        return converter

    def compound(self, rate: float, years: int) -> 'Currency':
        return Currency(self.value * (1 + rate) ** years, self.symbol)
    
    def assert_compatible(self, other: 'Currency'):
        if self.symbol != other.symbol and self.value != 0 and other.value != 0:
            raise ValueError(f"Cannot operate on currencies with different symbols: {self.symbol} and {other.symbol}")
    
    def __call__(self, value: float) -> 'Currency':
        return Currency(value, self.symbol)

    def __add__(self, other: 'Currency') -> 'Currency':
        if not isinstance(other, Currency):
            raise TypeError()
        
        self.assert_compatible(other)
        
        if not self.value:
            return other
        
        if not other.value:
            return self

        return Currency(self.value + other.value, self.symbol)
    
    def __sub__(self, other: 'Currency') -> 'Currency':
        if not isinstance(other, Currency):
            raise TypeError()
        
        self.assert_compatible(other)

        if not self.value:
            return -other
        
        if not other.value:
            return self
        
        return Currency(self.value - other.value, self.symbol)
    
    def __mul__(self, other: float) -> 'Currency':
        if not isinstance(other, (int, float)):
            raise TypeError()
        
        return Currency(self.value * other, self.symbol)
    
    def __truediv__(self, other: Union[float, int, 'Currency']) -> Union[float, 'Currency']:
        if isinstance(other, Currency):
            self.assert_compatible(other)
            
            return self.value / other.value
        
        if not isinstance(other, (int, float)):
            raise TypeError()
        
        return Currency(self.value / other, self.symbol)
    
    def __gt__(self, other: 'Currency') -> bool:
        if not isinstance(other, Currency):
            raise TypeError()

        self.assert_compatible(other)

        return self.value > other.value
    
    def __lt__(self, other: 'Currency') -> bool:
        if not isinstance(other, Currency):
            raise TypeError()

        self.assert_compatible(other)

        return self.value < other.value
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Currency):
            raise TypeError()
        
        if self.symbol != other.symbol:
            return False

        return self.value == other.value
    
    def __ne__(self, other: object) -> bool:
        if not isinstance(other, Currency):
            raise TypeError()
        
        if self.symbol != other.symbol:
            return True

        return self.value != other.value
    
    def __ge__(self, other: 'Currency') -> bool:
        if not isinstance(other, Currency):
            raise TypeError()
        
        self.assert_compatible(other)

        return self.value >= other.value
    
    def __le__(self, other: 'Currency') -> bool:    
        if not isinstance(other, Currency):
            raise TypeError()
        
        self.assert_compatible(other)

        return self.value <= other.value
    
    def __neg__(self) -> 'Currency':
        return Currency(-self.value, self.symbol)

    def __str__(self) -> str:
        if self.value == 0:
            return f"{self.symbol}0"

        divisor_index = log10(abs(self.value))//3
        suffix = ["", "k", "M", "B", "T"][int(divisor_index)]
        divisor = 1000**divisor_index

        return f"{self.symbol}{self.value/divisor:,.1f}{suffix}"
    
    def __repr__(self) -> str:
        return f"Currency({self.value}, '{self.symbol}')"
    
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
    if not values:
        raise ValueError("Cannot sum an empty list of currencies")
    return sum(values, values[0](0))

def avg_currency(values: list[Currency]) -> Currency:
    if not values:
        raise ValueError("Cannot average an empty list of currencies")
    return assert_currency(sum_currency(values) / len(values))

def repeat[T: StoreOfValue](value: T) -> Iterator[T]:
    while True:
        yield value

def growth_adjusted(percent_per_annum: float, values: Iterator[Currency]) -> Generator[Currency, None, None]:
    multiplier = 1.0
    for value in values:
        yield value * multiplier
        multiplier *= 1 + (percent_per_annum / 100)
