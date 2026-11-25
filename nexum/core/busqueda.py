"""Búsqueda rápida: varias palabras en cualquier orden sobre código, nombre, código del proveedor y barras."""
from sqlalchemy import or_, select

from nexum.db import comercial as c


def buscar_articulos(db, texto: str, limite: int = 100, solo_activos: bool = True) -> list:
    q = select(c.Articulo)
    if solo_activos:
        q = q.where(c.Articulo.activo.is_(True))
    for t in texto.split():
        like = f"%{t}%"
        q = q.where(or_(
            c.Articulo.codigo.ilike(like), c.Articulo.nombre.ilike(like), c.Articulo.codigo_proveedor.ilike(like),
            c.Articulo.id.in_(select(c.ArticuloBarras.articulo_id).where(c.ArticuloBarras.barras.ilike(like)))))
    return list(db.scalars(q.order_by(c.Articulo.nombre).limit(limite)))


def buscar_exacto(db, texto: str):
    """Código de barras, código o código del proveedor exactos (para el lector de barras)."""
    t = (texto or "").strip()
    if not t:
        return None
    b = db.scalar(select(c.ArticuloBarras).where(c.ArticuloBarras.barras == t))
    if b:
        return db.get(c.Articulo, b.articulo_id)
    return db.scalar(select(c.Articulo).where(c.Articulo.activo.is_(True),
                                              or_(c.Articulo.codigo == t, c.Articulo.codigo_proveedor == t)).limit(1))
