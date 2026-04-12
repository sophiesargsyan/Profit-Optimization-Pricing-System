from __future__ import annotations

EMPTY_DISPLAY = "—"

_CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "AMD": "AMD",
}


def normalize_currency_code(currency_code):
    return str(currency_code or "USD").upper()


def build_financial_format_config(currency_code):
    code = normalize_currency_code(currency_code)
    symbol = _CURRENCY_SYMBOLS.get(code, code)
    uses_spacing = symbol.isalpha() or len(symbol) > 1
    return {
        "currencyCode": code,
        "currencySymbol": symbol,
        "currencySpaceBetween": uses_spacing,
        "emptyDisplay": EMPTY_DISPLAY,
        "defaultCurrencyDigits": 2,
        "defaultPercentDigits": 1,
        "groupSeparator": ",",
        "decimalSeparator": ".",
    }


def _coerce_numeric(value):
    if value in (None, ""):
        return None
    return float(value)


def format_number_value(value, digits=0):
    amount = _coerce_numeric(value)
    if amount is None:
        return EMPTY_DISPLAY
    return f"{amount:,.{digits}f}"


def format_percent_value(value, digits=1):
    amount = _coerce_numeric(value)
    if amount is None:
        return EMPTY_DISPLAY
    return f"{amount:,.{digits}f}%"


def format_currency_value(value, currency_code, digits=2):
    amount = _coerce_numeric(value)
    if amount is None:
        return EMPTY_DISPLAY

    config = build_financial_format_config(currency_code)
    formatted_amount = f"{abs(amount):,.{digits}f}"
    symbol = config["currencySymbol"]
    body = f"{symbol} {formatted_amount}" if config["currencySpaceBetween"] else f"{symbol}{formatted_amount}"
    return f"-{body}" if amount < 0 else body


def format_signed_currency_value(value, currency_code, digits=2):
    amount = _coerce_numeric(value)
    if amount is None:
        return EMPTY_DISPLAY
    if amount > 0:
        return f"+{format_currency_value(amount, currency_code, digits)}"
    if amount < 0:
        return f"-{format_currency_value(abs(amount), currency_code, digits)}"
    return format_currency_value(0, currency_code, digits)
