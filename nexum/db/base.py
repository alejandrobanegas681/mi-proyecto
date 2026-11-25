"""Conexión a la base de datos. Todo el sistema pide sesiones desde acá,
así cambiar de SQLite a PostgreSQL es solo cambiar la URL."""
import warnings

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from nexum import config


# SQLite es solo para desarrollo; en PostgreSQL los importes son exactos.
warnings.filterwarnings("ignore", message=".*does not support Decimal.*")


class Base(DeclarativeBase):
    pass


_engine = None
_Session = None


def init_engine(url: str | None = None):
    global _engine, _Session
    _engine = create_engine(url or config.DB_URL, future=True)
    _Session = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_session():
    if _Session is None:
        init_engine()
    return _Session()


def crear_tablas():
    from nexum.db import comercial, maestros, models  # noqa: F401  (registra los modelos)
    Base.metadata.create_all(_engine)
