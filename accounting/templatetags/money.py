from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def thousand_id(value):
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return value

    sign = '-' if amount < 0 else ''
    amount = abs(amount)
    if amount == amount.to_integral_value():
        return f'{sign}{int(amount):,}'.replace(',', '.')

    formatted = f'{amount:,.2f}'
    integer, decimal = formatted.split('.')
    return f'{sign}{integer.replace(",", ".")},{decimal}'
