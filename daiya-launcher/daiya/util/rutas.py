"""Utilidades de rutas seguras.

Evitan que un nombre de archivo o de instancia manipulado escriba fuera de
la carpeta prevista (path traversal, OWASP A01:2025).
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

_NO_PERMITIDOS = re.compile(r"[^A-Za-z0-9._ -]")
_RESERVADOS_WINDOWS = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                       *(f"LPT{i}" for i in range(1, 10))}


def nombre_seguro(nombre: str, largo_max: int = 80) -> str:
    """Normaliza un nombre para usarlo como nombre de archivo o carpeta.

    Elimina tildes, separadores de ruta y caracteres de control, y evita los
    nombres reservados de Windows.

    Raises:
        ValueError: si el resultado queda vacío.
    """
    base = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    base = _NO_PERMITIDOS.sub("_", base).strip(" ._")[:largo_max]
    if not base:
        raise ValueError("El nombre no contiene caracteres válidos.")
    if base.split(".")[0].upper() in _RESERVADOS_WINDOWS:
        base = f"_{base}"
    return base


def dentro_de(base: Path, candidata: Path) -> bool:
    """Indica si ``candidata`` (ya resuelta) está contenida en ``base``."""
    try:
        candidata.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False
