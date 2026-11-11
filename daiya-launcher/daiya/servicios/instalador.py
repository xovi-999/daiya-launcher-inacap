"""Instalación de mods desde Modrinth reutilizando la validación local (RF-07 y RF-11).

Lo descargado se trata igual que un archivo arrastrado por el usuario: pasa por
la verificación SHA-512 del cliente y luego por la validación completa del
gestor de add-ons (defensa en profundidad).
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from daiya.core.gestor_addons import GestorAddOns, ResultadoAnadir
from daiya.core.modelos import Instancia, ResultadoValidacion
from daiya.servicios.modrinth import ClienteModrinth, ErrorModrinth

#: Identificador del mod Iris en Modrinth, requerido por los shaders.
PROYECTO_IRIS = "iris"


def instalar_desde_modrinth(cliente: ClienteModrinth, gestor: GestorAddOns, instancia: Instancia,
                            proyecto: str) -> ResultadoAnadir:
    """Descarga la versión compatible de ``proyecto`` y la instala en ``instancia``."""
    try:
        archivo = cliente.version_compatible(proyecto, instancia.version_minecraft, instancia.loader.value)
        if archivo is None:
            return ResultadoAnadir(ResultadoValidacion.error(
                f"No hay una versión de {proyecto} para Minecraft {instancia.version_minecraft} con Fabric."))
        temporal = Path(tempfile.mkdtemp(prefix="daiya_"))
        try:
            ruta = cliente.descargar(archivo, temporal)
            return gestor.anadir(ruta, instancia)
        finally:
            shutil.rmtree(temporal, ignore_errors=True)
    except ErrorModrinth as exc:
        return ResultadoAnadir(ResultadoValidacion.error(str(exc)))
