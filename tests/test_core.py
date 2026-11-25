"""Núcleo: arranque limpio, configuración inicial, login, permisos, módulos y menú."""
from nexum.core import auth, menu, setup, validadores
from nexum.core.errores import NexumError
from nexum.db import base, comercial as c, maestros as t, models as m
from sqlalchemy import select, func
from tests.util import sistema_nuevo


def test_todo():
    base.init_engine("sqlite:///:memory:")
    base.crear_tablas()
    with base.get_session() as db:
        # arranca VACÍO
        assert setup.necesita_configuracion(db)
        for modelo in (m.Usuario, t.Provincia, c.Articulo, c.Cliente, t.CondicionPago):
            assert db.scalar(select(func.count()).select_from(modelo)) == 0
        # validaciones de la configuración
        for kw, msg in [({"clave": "123"}, "6 caracteres"), ({"cuit": "20-12345678-0"}, "CUIT")]:
            args = dict(empresa="X", cuit=None, condicion_iva="RI", sucursal="S", usuario="a", nombre="A", clave="secreto1")
            args.update(kw)
            try:
                setup.configurar_inicial(db, **args); assert False
            except NexumError as e:
                assert msg in str(e)
        assert setup.necesita_configuracion(db)

    s = sistema_nuevo()
    with base.get_session() as db:
        assert not setup.necesita_configuracion(db)
        assert db.scalar(select(func.count()).select_from(t.Provincia)) == 0      # sin provincias salvo que se pidan
        assert db.scalar(select(func.count()).select_from(c.Articulo)) == 0
        assert s.es_admin and s.puede("stock.archivos.articulos")
        try:
            auth.iniciar_sesion(db, "admin", "mala"); assert False
        except auth.LoginError:
            pass
        # roles iniciales
        db.add(m.Usuario(usuario="ven", nombre="Vendedor", clave_hash=__import__("nexum.core.security", fromlist=["x"]).hashear("clave123"),
                         rol_id=db.scalar(select(m.Rol).where(m.Rol.nombre == "Vendedor")).id))
        db.commit()
        v = auth.iniciar_sesion(db, "ven", "clave123")
        assert v.puede("ventas.facturacion.facturacion_mostrador", "crear")
        assert not v.puede("ventas.facturacion.facturacion_mostrador", "anular")
        assert v.puede("stock.archivos.articulos") and not v.puede("stock.archivos.articulos", "crear")
        assert not v.puede("tesoreria.caja.movimientos_de_caja")
        # módulo desactivado bloquea incluso al admin
        db.get(m.ModuloActivo, "contabilidad").activo = False
        db.commit()
        assert not auth.iniciar_sesion(db, "admin", "secreto1").puede("contabilidad.archivos.plan_de_cuentas")

    arbol = menu.parsear()
    assert [n.codigo for n in arbol] == ["ventas", "tesoreria", "stock", "compras_y_bancos", "administracion", "contabilidad"]
    assert validadores.validar_cuit("20-12345678-6") is None and validadores.validar_cuit("20123456781")
    print("OK: núcleo funcionando (arranque limpio, roles, módulos, CUIT)")


if __name__ == "__main__":
    test_todo()
