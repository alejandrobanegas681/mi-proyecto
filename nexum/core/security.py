"""Hash de claves con PBKDF2 (biblioteca estándar, sin dependencias extra)."""
import hashlib
import hmac
import os

_ITER = 200_000


def hashear(clave: str) -> str:
    sal = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", clave.encode(), sal, _ITER)
    return f"{_ITER}${sal.hex()}${h.hex()}"


def verificar(clave: str, guardado: str) -> bool:
    try:
        it, sal, h = guardado.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(sal), int(it))
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False
