from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Expense:
    day: int
    month: str
    description: str
    category: str
    amount: str
