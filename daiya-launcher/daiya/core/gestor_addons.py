"""Gestión de add-ons de una instancia: añadir, activar, desactivar y eliminar.

Implementa los casos de uso CU-03, CU-04, CU-05 y CU-06.
"""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from daiya.config import LIMITES
from daiya.core.addons import AddOn, ArchivoInseguroError, ArchivoNoSoportadoError, cargar_addon
from daiya.core.modelos import Instancia, RegistroAddOn, ResultadoValidacion, TipoAddOn
from daiya.datos.repositorio import Repositorio
from daiya.util.hashing import hash_archivo
from daiya.util.rutas import dentro_de, nombre_seguro

log = logging.getLogger("daiya.addons")
SUFIJO_DESACTIVADO = ".disabled"


class AddOnDuplicadoError(Exception):
    """Ya existe un add-on equivalente en la instancia."""

    def __init__(self, existente: RegistroAddOn):
        super().__init__(f"Ya existe {existente.nombre} {existente.version} en la instancia.")
        self.existente = existente


@dataclass
class ResultadoAnadir:
    """Resultado de intentar añadir un archivo a una instancia."""

    validacion: ResultadoValidacion
    registro: RegistroAddOn | None = None
    addon: AddOn | None = None
    duracion_ms: float = 0.0


class GestorAddOns:
    """Coordina validación, copia y registro de add-ons."""

    def __init__(self, repo: Repositorio):
        self._repo = repo

    # ------------------------------------------------------------------ añadir
    def anadir(self, origen: Path, instancia: Instancia, reemplazar: bool = False) -> ResultadoAnadir:
        """Valida ``origen`` y, si es compatible, lo instala en ``instancia``.

        Args:
            origen: archivo arrastrado o seleccionado por el usuario.
            instancia: instancia destino (debe estar persistida).
            reemplazar: si es ``True`` sustituye una versión previa del mismo add-on.

        Raises:
            AddOnDuplicadoError: si el add-on ya existe y ``reemplazar`` es ``False``.
        """
        inicio = time.perf_counter()
        resultado = self._anadir(Path(origen), instancia, reemplazar)
        resultado.duracion_ms = (time.perf_counter() - inicio) * 1000
        log.info("Añadir %s -> %s: valido=%s (%.1f ms)", Path(origen).name, instancia.nombre,
                 resultado.validacion.valido, resultado.duracion_ms)
        return resultado

    def _anadir(self, origen: Path, instancia: Instancia, reemplazar: bool) -> ResultadoAnadir:
        if not origen.is_file():
            return ResultadoAnadir(ResultadoValidacion.error("El archivo no existe o no es un archivo regular."))
        if origen.stat().st_size > LIMITES.tam_max_archivo:
            return ResultadoAnadir(ResultadoValidacion.error("El archivo supera el tamaño máximo permitido."))
        try:
            addon = cargar_addon(origen)
        except (ArchivoNoSoportadoError, ArchivoInseguroError) as exc:
            return ResultadoAnadir(ResultadoValidacion.error(str(exc)))

        ids = {r.id_externo for r in self._repo.listar_addons(instancia.id, TipoAddOn.MOD) if r.activo}
        validacion = addon.validar(instancia, ids)
        if not validacion.valido:
            return ResultadoAnadir(validacion, addon=addon)

        sha1 = hash_archivo(origen)
        existente = self._repo.buscar_duplicado(instancia.id, addon.id_externo, sha1)
        if existente and not reemplazar:
            raise AddOnDuplicadoError(existente)
        if existente:
            self._mover_a_papelera(instancia, existente)

        destino = self._copiar(origen, instancia, addon.tipo)
        registro = self._repo.guardar_addon(RegistroAddOn(
            instancia_id=instancia.id, tipo=addon.tipo, nombre=addon.nombre, version=addon.version,
            id_externo=addon.id_externo, archivo=destino.name, hash_sha1=sha1, activo=True))
        return ResultadoAnadir(validacion, registro=registro, addon=addon)

    def _copiar(self, origen: Path, instancia: Instancia, tipo: TipoAddOn) -> Path:
        """Copia de forma atómica (archivo temporal + ``os.replace``)."""
        carpeta = instancia.carpeta(tipo)
        carpeta.mkdir(parents=True, exist_ok=True)
        nombre = nombre_seguro(origen.stem) + origen.suffix.lower()
        destino = carpeta / nombre
        if not dentro_de(carpeta, destino):  # defensa en profundidad
            raise ArchivoInseguroError("Destino fuera de la carpeta de la instancia.")
        fd, tmp = tempfile.mkstemp(dir=carpeta, suffix=".part")
        os.close(fd)
        try:
            shutil.copyfile(origen, tmp)
            os.replace(tmp, destino)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        return destino

    # -------------------------------------------------- activar / desactivar
    def ruta_archivo(self, instancia: Instancia, reg: RegistroAddOn) -> Path:
        """Ruta actual del archivo del add-on según su estado."""
        base = instancia.carpeta(reg.tipo) / reg.archivo
        return base if reg.activo else base.with_name(base.name + SUFIJO_DESACTIVADO)

    def cambiar_estado(self, instancia: Instancia, reg: RegistroAddOn, activo: bool) -> RegistroAddOn:
        """Activa o desactiva un add-on renombrando su archivo (CU-06)."""
        if reg.activo == activo:
            return reg
        actual = self.ruta_archivo(instancia, reg)
        reg.activo = activo
        nuevo = self.ruta_archivo(instancia, reg)
        if actual.exists():
            os.replace(actual, nuevo)
        return self._repo.guardar_addon(reg)

    # ---------------------------------------------------------------- eliminar
    def eliminar(self, instancia: Instancia, reg: RegistroAddOn) -> None:
        """Elimina el add-on moviéndolo a la papelera de la instancia (no se borra)."""
        self._mover_a_papelera(instancia, reg)
        self._repo.eliminar_addon(reg.id)

    def _mover_a_papelera(self, instancia: Instancia, reg: RegistroAddOn) -> None:
        archivo = self.ruta_archivo(instancia, reg)
        if archivo.exists():
            papelera = instancia.ruta / ".papelera"
            papelera.mkdir(exist_ok=True)
            os.replace(archivo, papelera / f"{int(time.time())}_{archivo.name}")
        if reg.id is not None:
            self._repo.eliminar_addon(reg.id)

    def verificar_integridad(self, instancia: Instancia) -> dict[str, list[RegistroAddOn]]:
        """Compara el hash SHA-1 registrado de cada add-on con el archivo en disco.

        Detecta archivos modificados o eliminados fuera del launcher (integridad,
        ISO/IEC 27002:2022 8.7 protección contra malware).

        Returns:
            Diccionario con las listas ``ok``, ``modificados`` y ``faltantes``.
        """
        resultado: dict[str, list[RegistroAddOn]] = {"ok": [], "modificados": [], "faltantes": []}
        for reg in self._repo.listar_addons(instancia.id):
            ruta = self.ruta_archivo(instancia, reg)
            if not ruta.exists():
                resultado["faltantes"].append(reg)
            elif hash_archivo(ruta) != reg.hash_sha1:
                resultado["modificados"].append(reg)
            else:
                resultado["ok"].append(reg)
        log.info("Integridad de %s: %d ok, %d modificados, %d faltantes", instancia.nombre,
                 len(resultado["ok"]), len(resultado["modificados"]), len(resultado["faltantes"]))
        return resultado

    def listar(self, instancia: Instancia, tipo: TipoAddOn | None = None) -> list[RegistroAddOn]:
        """Add-ons registrados en la instancia."""
        return self._repo.listar_addons(instancia.id, tipo)
