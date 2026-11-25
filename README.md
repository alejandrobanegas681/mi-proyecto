# NEXUM

Sistema de gestión de escritorio para comercios: stock, ventas de mostrador, precios, clientes y proveedores.
Python + PySide6 (Qt) + SQLAlchemy. SQLite para desarrollo, PostgreSQL para producción.

## Cómo correrlo
```
pip install -r requirements.txt
python -m nexum.main
```
La primera vez aparece un asistente (empresa, sucursal, usuario y clave). **El sistema arranca vacío**: no hay
artículos, clientes, ni provincias de ejemplo (las provincias son opcionales en el asistente).
Si venís de una versión anterior, borrá `nexum_dev.db` para empezar limpio.

## Base de datos
Variable `NEXUM_DB_URL` (ver `.env.example`). Por defecto crea `nexum_dev.db` (SQLite, solo desarrollo).

## Uso diario
- **F2** Mostrador · **F3** Artículos · **F4** Stock · **F5** Clientes · **Ctrl+K** ir a cualquier pantalla · **Ctrl+W** cerrar pestaña.
- Mostrador: escribí o escaneá y Enter; `3*código` agrega 3 unidades; **F12** cobra; **F9** limpia.
- Artículos: el precio se calcula en vivo (costo → descuento → flete → coeficiente → IVA → redondeo). Si tipeás el precio
  público, el coeficiente se deduce. **Ctrl+S** guarda; «Guardar y cargar otro» para cargar en tanda.
- Precios: importar la lista del proveedor (Excel/CSV) con vista previa, o subir/bajar un porcentaje. Todo queda en el historial.

## Estructura
- `nexum/core/`: lógica de negocio (sin interfaz): precios, artículos, stock, comprobantes, listas, usuarios, permisos.
- `nexum/db/`: modelos (SQLAlchemy). El stock no es un campo: es la suma de movimientos.
- `nexum/ui/`: pantallas (PySide6). `registry.py` asocia códigos de menú con pantallas; las que faltan muestran «en construcción».
- `nexum/maestros/definiciones.py`: maestros simples generados por el motor de ABM (una entrada por tabla).
- `tests/`: `PYTHONPATH=. python tests/test_core.py` (y `test_abm`, `test_comercial`, `test_ui` con `QT_QPA_PLATFORM=offscreen`).

## Pendiente (próximas versiones)
Compras y órdenes de pago, caja y cierres, cuentas corrientes y recibos, facturación electrónica ARCA (CAE),
Libro de IVA Digital, editor de roles y permisos, modo sin conexión para sucursales, migraciones (Alembic), instalador.
