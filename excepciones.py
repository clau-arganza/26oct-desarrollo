"""Excepciones propias para distinguir autenticación y acceso al contenido."""


class AccesoNoPermitidoError(Exception):
    """Clase común para las restricciones del contenido."""


class MenorDeEdadError(AccesoNoPermitidoError):
    """El usuario está identificado, pero todavía no tiene 18 años."""


class UsuarioBloqueadoError(AccesoNoPermitidoError):
    """El usuario está identificado, pero su cuenta está bloqueada."""


class UsuarioExistenteError(Exception):
    """No pueden registrarse dos usuarios con el mismo nickname."""


class CredencialesIncorrectasError(Exception):
    """El usuario no existe o la contraseña no coincide."""
