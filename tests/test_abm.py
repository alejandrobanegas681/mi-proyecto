"""Motor de ABM: alta, edición, validaciones, únicos, FK, baja lógica, permisos y auditoría."""
from sqlalchemy import select

from nexum.core import abm
from nexum.core.auth import Sesion
from nexum.core.errores import NexumError, PermisoError
from nexum.db import base, maestros as t, models as m
from nexum.maestros.definiciones import DEFINICIONES
from tests.util import sistema_nuevo

D = {d.modelo.__name__: d for d in DEFINICIONES}


def test_abm():
    admin = sistema_nuevo()
    with base.get_session() as db:
        fam = D["Familia"]
        abm.guardar(db, admin, fam, {"codigo": "FR", "nombre": "Frenos"})
        abm.guardar(db, admin, fam, {"codigo": "LU", "nombre": "Lubricantes"})
        assert [f.nombre for f in abm.listar(db, fam)] == ["Frenos", "Lubricantes"]
        assert [f.nombre for f in abm.listar(db, fam, "lubri")] == ["Lubricantes"]
        for datos, msg in [({"codigo": "", "nombre": "X"}, "obligatorio"), ({"codigo": "FR", "nombre": "O"}, "Ya existe"),
                           ({"codigo": "A" * 11, "nombre": "X"}, "hasta 10")]:
            try:
                abm.guardar(db, admin, fam, datos); assert False
            except NexumError as e:
                assert msg in str(e), e
        f = abm.listar(db, fam, "frenos")[0]
        abm.guardar(db, admin, fam, {"codigo": "FR", "nombre": "Frenos y embragues"}, f.id)
        assert db.get(t.Familia, f.id).nombre == "Frenos y embragues"

        # FK localidad → provincia
        prov = abm.guardar(db, admin, D["Provincia"], {"codigo": "A", "nombre": "Salta"})
        o = abm.guardar(db, admin, D["Localidad"], {"provincia_id": prov.id, "nombre": "Salta Capital", "codigo_postal": "4400"})
        loc = D["Localidad"]
        assert [abm.texto_celda(db, c, o) for c in loc.campos if c.en_lista] == ["Salta", "Salta Capital", "4400"]

        # clientes: CUIT validado, decimales
        cli = D["Cliente"]
        try:
            abm.guardar(db, admin, cli, {"codigo": "C1", "razon_social": "Juan", "cuit": "20-12345678-0", "condicion_iva": "RI"}); assert False
        except NexumError as e:
            assert "CUIT" in str(e)
        o = abm.guardar(db, admin, cli, {"codigo": "C1", "razon_social": "Juan", "cuit": "20-12345678-6",
                                         "condicion_iva": "RI", "descuento_pct": 5.5})
        assert float(o.descuento_pct) == 5.5

        # baja lógica y permisos
        abm.eliminar(db, admin, fam, f.id)
        assert [x.nombre for x in abm.listar(db, fam)] == ["Lubricantes"] and len(abm.listar(db, fam, inactivos=True)) == 2
        solo_ver = Sesion(99, "x", "X", None, False, {"stock": {"ver": True}}, {"stock"})
        for fn in (lambda: abm.guardar(db, solo_ver, fam, {"codigo": "ZZ", "nombre": "Z"}), lambda: abm.eliminar(db, solo_ver, fam, 1)):
            try:
                fn(); assert False
            except PermisoError:
                pass
        assert {"crear", "modificar", "baja"} <= {a.accion for a in db.scalars(select(m.Auditoria))}
    print("OK: motor de ABM funcionando")


if __name__ == "__main__":
    test_abm()
