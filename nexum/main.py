import sys

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

import nexum.ui.maestros_ui  # noqa: F401  (registra las pantallas)
from nexum.core import auth, setup
from nexum.db import base
from nexum.ui import tema
from nexum.ui.login import LoginDialog
from nexum.ui.main_window import MainWindow
from nexum.ui.setup_dialog import SetupDialog


def main():
    base.init_engine()
    base.crear_tablas()
    app = QApplication(sys.argv)
    tema.aplicar(app, QSettings("NEXUM", "NEXUM").value("oscuro", "false") == "true")

    with base.get_session() as db:
        primera_vez = setup.necesita_configuracion(db)
    sesion = None
    if primera_vez:
        asistente = SetupDialog()
        if asistente.exec() != SetupDialog.Accepted:
            return 0
        with base.get_session() as db:
            sesion = auth.iniciar_sesion(db, *asistente.datos)
    else:
        login = LoginDialog()
        if login.exec() != LoginDialog.Accepted:
            return 0
        sesion = login.sesion
    ventana = MainWindow(sesion)
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
