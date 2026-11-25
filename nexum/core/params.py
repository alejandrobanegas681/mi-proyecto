from nexum.db import models as m


def obtener(db, clave: str, defecto=None):
    p = db.get(m.Parametro, clave)
    return p.valor if p is not None and p.valor is not None else defecto


def poner(db, clave: str, valor: str):
    p = db.get(m.Parametro, clave)
    if p is None:
        db.add(m.Parametro(clave=clave, valor=valor))
    else:
        p.valor = valor
