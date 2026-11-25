"""Cadena de precio: costo de lista → descuento → flete → costo → coeficiente → IVA → redondeo."""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

D = Decimal


def dec(x) -> Decimal:
    return x if isinstance(x, Decimal) else D(str(x or 0))


def q2(x) -> Decimal:
    return dec(x).quantize(D("0.01"), ROUND_HALF_UP)


def redondear(valor, paso=D(1)) -> Decimal:
    paso = dec(paso) or D(1)
    return ((dec(valor) / paso).quantize(D(1), ROUND_HALF_UP) * paso).quantize(D("0.01"))


def calcular(costo_lista, desc_pct=0, flete=0, coeficiente=1, alicuota=21, redondeo=False, paso=1):
    """Devuelve (costo, precio_publico)."""
    costo = q2(dec(costo_lista) * (1 - dec(desc_pct) / 100) + dec(flete))
    publico = costo * dec(coeficiente) * (1 + dec(alicuota) / 100)
    return costo, (redondear(publico, paso) if redondeo else q2(publico))


def coeficiente_para(costo, publico, alicuota) -> Decimal:
    if dec(costo) <= 0:
        return D(0)
    return (dec(publico) / (1 + dec(alicuota) / 100) / dec(costo)).quantize(D("0.0001"), ROUND_HALF_UP)


def en_oferta(art, hoy: date | None = None) -> bool:
    hoy = hoy or date.today()
    return bool(art.oferta_precio and dec(art.oferta_precio) > 0
                and (art.oferta_desde is None or art.oferta_desde <= hoy)
                and (art.oferta_hasta is None or hoy <= art.oferta_hasta))


def precio_vigente(art, hoy: date | None = None) -> Decimal:
    return q2(art.oferta_precio) if en_oferta(art, hoy) else q2(art.precio_publico)
