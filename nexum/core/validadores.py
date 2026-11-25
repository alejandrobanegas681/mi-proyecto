import re


def validar_cuit(valor: str):
    """Devuelve None si el CUIT/CUIL es válido (dígito verificador), o un mensaje de error."""
    d = re.sub(r"\D", "", valor or "")
    if len(d) != 11:
        return "El CUIT debe tener 11 dígitos"
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(x) * p for x, p in zip(d[:10], pesos))
    v = 11 - suma % 11
    v = 0 if v == 11 else v
    if v == 10 or v != int(d[10]):
        return "El CUIT no es válido (dígito verificador incorrecto)"
    return None
