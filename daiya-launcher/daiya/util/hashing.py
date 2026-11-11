"""Cálculo de hashes de archivos por bloques (no carga el archivo completo)."""
from __future__ import annotations

import hashlib
from pathlib import Path

_BLOQUE = 1024 * 1024


def hash_archivo(ruta: Path, algoritmo: str = "sha1") -> str:
    """Calcula el hash hexadecimal de ``ruta`` leyendo en bloques de 1 MB.

    Args:
        ruta: archivo a procesar.
        algoritmo: nombre aceptado por :mod:`hashlib` (``sha1``, ``sha512``...).

    Returns:
        El hash en formato hexadecimal en minúsculas.
    """
    h = hashlib.new(algoritmo)
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(_BLOQUE), b""):
            h.update(bloque)
    return h.hexdigest()
