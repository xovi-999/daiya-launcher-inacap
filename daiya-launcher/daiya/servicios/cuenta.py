"""Inicio de sesión con cuenta Microsoft mediante OAuth 2.0 con PKCE (CU-01).

- El launcher nunca recibe la contraseña: el usuario se autentica en la
  página oficial de Microsoft.
- Se usa PKCE y un parámetro ``state`` aleatorio para evitar la
  interceptación del código de autorización (OWASP A07:2025).
- Solo el token de renovación se persiste, cifrado por el llavero del
  sistema operativo mediante ``keyring`` (OWASP A04:2025). El token de
  acceso vive únicamente en memoria.

Modo sin conexión (decisión académica, ver informe): mientras Microsoft no
aprueba la aplicación para la API de Minecraft, el launcher permite crear un
perfil local con solo un nombre de jugador. Ese perfil no tiene token, no
puede entrar a servidores oficiales (exigen cuenta verificada) y su nombre
se valida con una lista blanca de caracteres antes de usarse.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid
from dataclasses import dataclass

import keyring
import minecraft_launcher_lib as mll

from daiya.config import KEYRING_SERVICIO

log = logging.getLogger("daiya.cuenta")
REDIRECT_URI = "http://localhost:8765/callback"
_CLAVE_REFRESH = "refresh_token"


#: Nombres de Minecraft válidos: 3 a 16 letras, dígitos o guion bajo (lista blanca).
PATRON_NOMBRE = re.compile(r"^[A-Za-z0-9_]{3,16}$")


def uuid_offline(nombre: str) -> str:
    """UUID que el propio juego asigna a un jugador sin conexión.

    Equivale a ``UUID.nameUUIDFromBytes("OfflinePlayer:" + nombre)`` de Java
    (MD5, versión 3), por lo que los mundos guardados reconocen al jugador.
    """
    digest = bytearray(hashlib.md5(f"OfflinePlayer:{nombre}".encode()).digest())  # noqa: S324 (no es uso criptográfico)
    digest[6] = (digest[6] & 0x0F) | 0x30
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


class ErrorSesion(RuntimeError):
    """No fue posible iniciar o renovar la sesión."""


@dataclass
class Sesion:
    """Datos mínimos de la sesión necesarios para lanzar el juego."""

    nombre_jugador: str
    uuid: str
    token_acceso: str
    sin_conexion: bool = False

    def __repr__(self) -> str:  # evita filtrar el token en logs o depuración
        return (f"Sesion(nombre_jugador={self.nombre_jugador!r}, uuid={self.uuid!r}, token_acceso='***', "
                f"sin_conexion={self.sin_conexion})")


class ServicioCuenta:
    """Gestiona el flujo OAuth de Microsoft y el almacenamiento seguro del token."""

    def __init__(self, client_id: str | None = None, almacen=keyring, api=mll.microsoft_account):
        self.client_id = client_id or os.environ.get("DAIYA_AZURE_CLIENT_ID", "")
        self._almacen = almacen
        self._api = api
        self._state: str | None = None
        self._verifier: str | None = None
        self.sesion: Sesion | None = None

    def url_inicio_sesion(self) -> str:
        """Genera la URL oficial de inicio de sesión con PKCE y ``state``."""
        if not self.client_id:
            raise ErrorSesion("Falta configurar el Client ID de Azure (variable DAIYA_AZURE_CLIENT_ID).")
        url, self._state, self._verifier = self._api.get_secure_login_data(self.client_id, REDIRECT_URI)
        return url

    def completar_inicio_sesion(self, url_redireccion: str) -> Sesion:
        """Valida el ``state``, canjea el código y guarda el token de renovación."""
        if not self._state:
            raise ErrorSesion("No hay un inicio de sesión en curso.")
        try:
            codigo = self._api.parse_auth_code_url(url_redireccion, self._state)
            datos = self._api.complete_login(self.client_id, None, REDIRECT_URI, codigo, self._verifier)
        except AssertionError as exc:
            raise ErrorSesion("La respuesta de Microsoft no coincide con la solicitud (state inválido).") from exc
        except Exception as exc:  # errores de red o cuenta sin juego
            raise ErrorSesion(self._mensaje_error(exc)) from exc
        finally:
            self._state = self._verifier = None
        return self._guardar(datos)

    def iniciar_sin_conexion(self, nombre: str) -> Sesion:
        """Crea un perfil local sin cuenta Microsoft (solo un jugador o LAN).

        No se guarda ningún secreto: el perfil no tiene token. El nombre se
        valida contra :data:`PATRON_NOMBRE` (OWASP A05:2025, validación de entradas).
        """
        nombre = (nombre or "").strip()
        if not PATRON_NOMBRE.fullmatch(nombre):
            raise ErrorSesion("El nombre debe tener entre 3 y 16 caracteres: letras, números o guion bajo.")
        self.sesion = Sesion(nombre, uuid_offline(nombre), "", sin_conexion=True)
        log.info("Perfil sin conexión activo para %s", nombre)
        return self.sesion

    def renovar(self) -> Sesion | None:
        """Renueva la sesión con el token guardado; devuelve ``None`` si no hay."""
        try:
            refresh = self._almacen.get_password(KEYRING_SERVICIO, _CLAVE_REFRESH)
        except Exception as exc:  # sin llavero disponible en el sistema operativo
            log.warning("Llavero del sistema no disponible: %s", type(exc).__name__)
            return None
        if not refresh or not self.client_id:
            return None
        try:
            datos = self._api.complete_refresh(self.client_id, None, REDIRECT_URI, refresh)
        except Exception as exc:
            log.warning("No se pudo renovar la sesión: %s", type(exc).__name__)
            self.cerrar_sesion()
            return None
        return self._guardar(datos)

    def cerrar_sesion(self) -> None:
        """Elimina el token guardado y la sesión en memoria."""
        self.sesion = None
        try:
            self._almacen.delete_password(KEYRING_SERVICIO, _CLAVE_REFRESH)
        except Exception as exc:  # el token no existía o no hay llavero
            log.debug("Sin token que eliminar: %s", type(exc).__name__)

    def _guardar(self, datos: dict) -> Sesion:
        try:
            self._almacen.set_password(KEYRING_SERVICIO, _CLAVE_REFRESH, datos["refresh_token"])
        except Exception as exc:
            # Nunca se guarda el token en texto plano: la sesión queda solo en memoria.
            log.warning("No se pudo guardar el token en el llavero (%s); la sesión no se recordará.",
                        type(exc).__name__)
        self.sesion = Sesion(datos["name"], datos["id"], datos["access_token"])
        log.info("Sesión iniciada para %s", self.sesion.nombre_jugador)
        return self.sesion

    @staticmethod
    def _mensaje_error(exc: Exception) -> str:
        nombre = type(exc).__name__
        if nombre == "AzureAppNotPermitted":
            return "La aplicación aún no tiene permiso de Microsoft para usar la API de Minecraft."
        if nombre == "AccountNotOwnMinecraft":
            return "Esta cuenta no tiene Minecraft Java Edition."
        return "No fue posible iniciar sesión. Revisa tu conexión e inténtalo nuevamente."
