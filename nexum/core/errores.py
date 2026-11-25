"""Errores propios de NEXUM (se muestran tal cual al usuario) y chequeo de permisos."""


class NexumError(Exception):
    pass


class PermisoError(NexumError):
    pass


def exigir(sesion, codigo: str, accion: str = "ver"):
    if not sesion.puede(codigo, accion):
        raise PermisoError(f"No tenés permiso para {accion} en «{codigo}»")
