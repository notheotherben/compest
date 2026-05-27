from .currency import *


class Equity(StoreOfValue):
    def __init__(self, shares: float, exercise_cost: Currency):
        super().__init__("shares")
        self.shares = shares
        self.exercise_cost = exercise_cost

    def net_value(self, price: Currency) -> Currency:
        return price * self.shares - self.exercise_cost

    def __add__(self, other: 'Equity') -> 'Equity':
        if not isinstance(other, Equity):
            raise TypeError()
        
        total_shares = self.shares + other.shares
        return Equity(total_shares, assert_currency((self.exercise_cost * self.shares + other.exercise_cost * other.shares) / total_shares))
    
    def __sub__(self, other: 'Equity') -> 'Equity':
        if not isinstance(other, Equity):
            raise TypeError()
        
        return Equity(self.shares - other.shares, exercise_cost=self.exercise_cost - other.exercise_cost)
    
    def __mul__(self, other: Currency) -> Currency:
        if not isinstance(other, Currency):
            raise TypeError()
        return other * self.shares
    
    def __div__(self, other: int) -> 'Equity':
        if not isinstance(other, (int, float)):
            raise TypeError()
        return Equity(self.shares / other, exercise_cost=self.exercise_cost)
    
    def __str__(self) -> str:
        return f"{self.shares:,.0f} shares"

