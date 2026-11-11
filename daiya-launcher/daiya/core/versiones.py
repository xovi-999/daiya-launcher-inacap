"""Comparación de versiones de Minecraft según la sintaxis de Fabric.

Fabric declara la compatibilidad en ``fabric.mod.json`` mediante el campo
``depends.minecraft``, que puede ser un texto (``">=1.20.5"``, ``"1.21.x"``,
``"~1.21"``, ``">=1.20 <1.21"``) o una lista de alternativas.
"""
from __future__ import annotations

import re

_NUM = re.compile(r"^(\d+)(?:\.(\d+|x|X|\*))?(?:\.(\d+|x|X|\*))?")

#: Identificadores que publica Mojang: "1.21.1", "24w14a", "1.21-pre1", "b1.7.3", "rd-132211"...
#: Lista blanca de caracteres (sin espacios, barras ni "..") porque el id se usa en rutas y comandos.
PATRON_ID_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")
_NUMERICA = re.compile(r"^\d+\.\d+(\.\d+)?(-[A-Za-z0-9-]+)?$")  # release, pre-release o release candidate
_SNAPSHOT_SEMANAL = re.compile(r"^(\d{2})w(\d{2})[a-z]$")
_PRIMERA_FABRIC = (1, 14, 0)  # Fabric existe desde 1.14 (snapshot 18w43b)


def id_version_valido(version: str) -> bool:
    """Indica si ``version`` tiene la forma de un identificador de versión de Mojang."""
    return bool(PATRON_ID_VERSION.fullmatch(version or "")) and ".." not in version


def es_numerica(version: str) -> bool:
    """``True`` para releases y pre-releases ("1.21.1", "1.21-pre1").

    ``False`` para snapshots semanales ("24w14a") y versiones beta o alpha.
    """
    return bool(_NUMERICA.fullmatch(version or ""))


def admite_fabric(version: str) -> bool:
    """Regla local (sin conexión) para saber si Fabric soporta ``version``."""
    m = _SNAPSHOT_SEMANAL.fullmatch(version or "")
    if m:
        return (int(m.group(1)), int(m.group(2))) >= (18, 43)
    return es_numerica(version) and a_tupla(version) >= _PRIMERA_FABRIC


def a_tupla(version: str) -> tuple[int, int, int]:
    """Convierte ``"1.21.1"`` en ``(1, 21, 1)``. Los sufijos ``-pre``/``-rc`` se ignoran.

    Raises:
        ValueError: si el texto no comienza con un número de versión.
    """
    m = _NUM.match(version.strip())
    if not m:
        raise ValueError(f"Versión no reconocida: {version!r}")
    partes = [m.group(1), m.group(2) or "0", m.group(3) or "0"]
    return tuple(int(p) if p.isdigit() else 0 for p in partes)  # type: ignore[return-value]


def _cumple_predicado(version: tuple[int, int, int], predicado: str) -> bool:
    """Evalúa un predicado simple (sin espacios) contra ``version``."""
    p = predicado.strip()
    if p in ("", "*"):
        return True
    for op in (">=", "<=", ">", "<", "=", "~", "^"):
        if p.startswith(op):
            objetivo = p[len(op):].strip()
            break
    else:
        op, objetivo = "", p
    if any(c in objetivo for c in "xX*"):
        partes = objetivo.split(".")
        fijas = [int(x) for x in partes if x.isdigit()]
        return list(version[: len(fijas)]) == fijas
    obj = a_tupla(objetivo)
    if op in ("", "="):
        largo = len(objetivo.split("."))
        return version[:largo] == obj[:largo] if largo < 3 else version == obj
    if op == ">=":
        return version >= obj
    if op == "<=":
        return version <= obj
    if op == ">":
        return version > obj
    if op == "<":
        return version < obj
    if op == "~":  # misma versión menor, igual o superior
        return version[:2] == obj[:2] and version >= obj
    if op == "^":  # misma versión mayor, igual o superior
        return version[0] == obj[0] and version >= obj
    return False  # pragma: no cover


def es_compatible(version_instancia: str, requisito: str | list[str] | None) -> bool:
    """Indica si ``version_instancia`` satisface ``requisito`` de Fabric.

    Un texto con espacios se interpreta como conjunción (AND); una lista,
    como disyunción (OR). ``None`` significa que el mod no declara requisito.
    """
    if requisito is None:
        return True
    version = a_tupla(version_instancia)
    alternativas = requisito if isinstance(requisito, list) else [requisito]
    for alt in alternativas:
        if all(_cumple_predicado(version, pred) for pred in str(alt).split()):
            return True
    return False


def describir(requisito: str | list[str] | None) -> str:
    """Texto legible del requisito, para mensajes al usuario."""
    if requisito is None:
        return "cualquier versión"
    return " o ".join(requisito) if isinstance(requisito, list) else str(requisito)
