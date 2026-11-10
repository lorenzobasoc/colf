from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from .http import json_client


@dataclass(frozen=True)
class Rate:
    currency: str
    requested_date: date
    effective_date: date
    eur_per_unit: Decimal


def get_rate(currency: str, day: date, *, request=None) -> Rate:
    if currency == 'EUR':
        return Rate(currency, day, day, Decimal('1'))
    request = request or json_client('https://api.frankfurter.dev')
    for offset in range(8):
        target = day - timedelta(days=offset)
        data = request('GET', f'/v2/providers/ecb/rate/{currency}/EUR?date={target.isoformat()}')
        if not data:
            continue
        actual = date.fromisoformat(data['date'])
        value = Decimal(str(data['rate']))
        if data['base'].upper() != currency or data['quote'].upper() != 'EUR':
            raise ValueError('Direzione cambio inattesa')
        if not day - timedelta(days=7) <= actual <= day or not value.is_finite() or value <= 0:
            raise ValueError('Cambio storico non valido')
        return Rate(currency, day, actual, value)
    raise ValueError(f'Nessun cambio {currency}/EUR disponibile per {day}')


def round_eur(value: Decimal) -> Decimal:
    """Round once to the nearest five euro cents; ties round up."""
    return ((value / Decimal('0.05')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            * Decimal('0.05'))


def split_eur(amount: Decimal, rate: Rate, shared: bool) -> tuple[Decimal, Decimal]:
    converted = amount * rate.eur_per_unit
    if shared:
        quota = round_eur(converted / 2)
        return quota, quota
    return round_eur(converted), Decimal('0')
