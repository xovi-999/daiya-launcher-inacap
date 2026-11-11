"""Creación y configuración de instancias (CU-02 y CU-08)."""
from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path

from daiya.config import LIMITES
from daiya.core import versiones
from daiya.core.modelos import Instancia, TipoAddOn, TipoLoader
from daiya.datos.repositorio import Repositorio
from daiya.util.rutas import nombre_seguro

log = logging.getLogger("daiya.instancias")
_NOMBRE = re.compile(r"^[\w áéíóúñÁÉÍÓÚÑ.\-()]+$")
_JAVA_VALIDOS = {"java", "java.exe", "javaw", "javaw.exe"}


class DatoInvalidoError(ValueError):
    """Un dato ingresado por el usuario no supera la validación."""


class GestorInstancias:
    """Crea, configura y elimina instancias."""

    def __init__(self, repo: Repositorio, carpeta_instancias: Path):
        self._repo = repo
        self._base = Path(carpeta_instancias)
        self._base.mkdir(parents=True, exist_ok=True)

    def crear(self, nombre: str, version_mc: str, loader: TipoLoader, ram_mb: int = 4096) -> Instancia:
        """Valida los datos y crea la instancia con sus carpetas.

        Raises:
            DatoInvalidoError: si algún dato no es válido o el nombre ya existe.
        """
        nombre = (nombre or "").strip()
        if not nombre or len(nombre) > LIMITES.largo_max_nombre or not _NOMBRE.match(nombre):
            raise DatoInvalidoError(
                f"El nombre debe tener entre 1 y {LIMITES.largo_max_nombre} caracteres "
                "(letras, números, espacios, . - ( )).")
        if self._repo.existe_nombre(nombre):
            raise DatoInvalidoError("Ya existe una instancia con ese nombre.")
        if not versiones.id_version_valido(version_mc):
            raise DatoInvalidoError("Versión de Minecraft no válida (ejemplo: 1.21.1).")
        if TipoLoader(loader) is TipoLoader.FABRIC and not versiones.admite_fabric(version_mc):
            raise DatoInvalidoError(f"Fabric no está disponible para Minecraft {version_mc}: "
                                    "elige 1.14 o superior, o crea la instancia como vanilla.")
        self._validar_ram(ram_mb)
        ruta = self._base / nombre_seguro(nombre)
        if ruta.exists():
            ruta = self._base / f"{nombre_seguro(nombre)}_{int(time.time())}"
        for tipo in TipoAddOn:
            (ruta / tipo.carpeta).mkdir(parents=True, exist_ok=True)
        inst = Instancia(nombre=nombre, version_minecraft=version_mc, loader=TipoLoader(loader),
                         ruta=ruta, ram_mb=ram_mb)
        self._repo.guardar_instancia(inst)
        log.info("Instancia creada: %s (%s, %s)", nombre, version_mc, inst.loader.value)
        return inst

    def configurar(self, inst: Instancia, ram_mb: int, ruta_java: str | None) -> Instancia:
        """Actualiza la memoria y la ruta de Java de la instancia (CU-08)."""
        self._validar_ram(ram_mb)
        if ruta_java:
            java = Path(ruta_java)
            if java.name.lower() not in _JAVA_VALIDOS or not java.is_file() or not os.access(java, os.X_OK):
                raise DatoInvalidoError("La ruta indicada no corresponde a un ejecutable de Java.")
        inst.ram_mb, inst.ruta_java = ram_mb, (ruta_java or None)
        return self._repo.guardar_instancia(inst)

    def listar(self) -> list[Instancia]:
        return self._repo.listar_instancias()

    @staticmethod
    def _validar_ram(ram_mb: int) -> None:
        if not isinstance(ram_mb, int) or not LIMITES.ram_min_mb <= ram_mb <= LIMITES.ram_max_mb:
            raise DatoInvalidoError(
                f"La memoria debe estar entre {LIMITES.ram_min_mb} y {LIMITES.ram_max_mb} MB.")
