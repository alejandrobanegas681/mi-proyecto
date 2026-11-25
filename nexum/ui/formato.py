"""Formato argentino de números: 1.234,56"""
from decimal import Decimal


def money(v) -> str:
    if v is None:
        return ""
    return f"{Decimal(str(v)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def cant(v) -> str:
    if v is None:
        return ""
    d = Decimal(str(v)).normalize()
    s = f"{d:f}"
    return s.rstrip("0").rstrip(".") if "." in s else s
