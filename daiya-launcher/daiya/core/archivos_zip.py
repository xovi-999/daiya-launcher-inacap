"""Lectura defensiva de archivos .jar y .zip aportados por el usuario.

Un archivo malicioso puede intentar agotar memoria o disco ("zip bomb") o
incluir rutas como ``../../`` ("zip slip"). Este módulo valida la
estructura del archivo antes de leer su contenido (OWASP A10:2025,
Mishandling of Exceptional Conditions, y A01:2025).
"""
from __future__ import annotations

import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Iterator

from daiya.config import LIMITES


class ArchivoInseguroError(ValueError):
    """El archivo comprimido no supera las validaciones de seguridad."""


def _ruta_entrada_segura(nombre: str) -> bool:
    ruta = PurePosixPath(nombre.replace("\\", "/"))
    return not ruta.is_absolute() and ".." not in ruta.parts and ":" not in nombre


@contextmanager
def abrir_zip_seguro(ruta: Path) -> Iterator[zipfile.ZipFile]:
    """Abre ``ruta`` como zip tras validar su estructura.

    Raises:
        ArchivoInseguroError: si el archivo no es un zip válido o excede límites.
    """
    if ruta.stat().st_size > LIMITES.tam_max_archivo:
        raise ArchivoInseguroError("El archivo supera el tamaño máximo permitido (512 MB).")
    try:
        zf = zipfile.ZipFile(ruta)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ArchivoInseguroError("El archivo está dañado o no es un archivo comprimido válido.") from exc
    try:
        entradas = zf.infolist()
        if len(entradas) > LIMITES.max_entradas_zip:
            raise ArchivoInseguroError("El archivo contiene demasiadas entradas.")
        total = 0
        for e in entradas:
            if not _ruta_entrada_segura(e.filename):
                raise ArchivoInseguroError(f"Ruta interna no permitida: {e.filename!r}")
            total += e.file_size
            if (e.file_size > 1024 * 1024 and e.compress_size
                    and e.file_size / e.compress_size > LIMITES.razon_max_compresion):
                raise ArchivoInseguroError("Razón de compresión sospechosa (posible zip bomb).")
        if total > LIMITES.tam_max_descomprimido:
            raise ArchivoInseguroError("El contenido descomprimido supera el límite permitido.")
        yield zf
    finally:
        zf.close()


def leer_entrada(zf: zipfile.ZipFile, nombre: str, limite: int = LIMITES.tam_max_descriptor) -> bytes | None:
    """Lee una entrada del zip respetando ``limite`` bytes. Devuelve ``None`` si no existe."""
    try:
        info = zf.getinfo(nombre)
    except KeyError:
        return None
    if info.file_size > limite:
        raise ArchivoInseguroError(f"{nombre} supera el tamaño máximo esperado.")
    with zf.open(info) as f:
        return f.read(limite + 1)[:limite]


def tiene_prefijo(zf: zipfile.ZipFile, prefijo: str) -> bool:
    """Indica si alguna entrada del zip comienza con ``prefijo``."""
    return any(n.startswith(prefijo) for n in zf.namelist())
