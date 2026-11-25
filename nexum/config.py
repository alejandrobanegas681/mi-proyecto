"""Configuración general de NEXUM."""
import os

APP_NAME = "NEXUM"
APP_VERSION = "0.2.0"

# En desarrollo usa SQLite; en producción se apunta a PostgreSQL con la variable de entorno.
DB_URL = os.getenv("NEXUM_DB_URL", "sqlite:///nexum_dev.db")
