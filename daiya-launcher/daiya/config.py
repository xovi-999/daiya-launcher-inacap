"""Configuración global y límites de seguridad del launcher.

Todos los valores se centralizan aquí para evitar "números mágicos"
repartidos por el código y facilitar su revisión (OWASP A02:2025,
Security Misconfiguration).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


def carpeta_base() -> Path:
    """Devuelve la carpeta donde Daiya guarda sus datos.

    Puede sobrescribirse con la variable de entorno ``DAIYA_HOME`` (se usa
    en las pruebas). Por defecto se usa ``%APPDATA%/Daiya`` en Windows y
    ``~/.local/share/daiya`` en Linux.
    """
    override = os.environ.get("DAIYA_HOME")
    if override:
        return Path(override)
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", Path.home())) / "Daiya"
    return Path.home() / ".local" / "share" / "daiya"


@dataclass(frozen=True)
class Limites:
    """Límites defensivos aplicados al procesar archivos del usuario."""

    #: Tamaño máximo aceptado para un add-on (bytes).
    tam_max_archivo: int = 512 * 1024 * 1024
    #: Cantidad máxima de entradas dentro de un .jar/.zip.
    max_entradas_zip: int = 50_000
    #: Tamaño máximo descomprimido total (protección contra "zip bombs").
    tam_max_descomprimido: int = 2 * 1024 * 1024 * 1024
    #: Razón máxima de compresión de una entrada individual.
    razon_max_compresion: int = 200
    #: Tamaño máximo de un descriptor (fabric.mod.json / pack.mcmeta).
    tam_max_descriptor: int = 1024 * 1024
    #: Memoria RAM mínima y máxima configurable para una instancia (MB).
    ram_min_mb: int = 1024
    ram_max_mb: int = 32768
    #: Largo máximo del nombre de una instancia.
    largo_max_nombre: int = 40


LIMITES = Limites()

#: Extensiones aceptadas por tipo de add-on.
EXT_MOD = {".jar"}
EXT_ZIP = {".zip"}

#: Identificador de servicio usado en el llavero del sistema (keyring).
KEYRING_SERVICIO = "daiya-launcher"

#: Agente de usuario identificable, requerido por la API de Modrinth.
USER_AGENT = "DaiyaLauncher/0.1.0-alpha (proyecto academico INACAP)"
