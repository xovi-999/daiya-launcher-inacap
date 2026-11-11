"""Modelos de dominio del launcher (clases de la vista lógica 4+1)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class TipoLoader(str, Enum):
    """Cargador de mods de una instancia."""

    VANILLA = "vanilla"
    FABRIC = "fabric"


class TipoAddOn(str, Enum):
    """Tipos de complemento soportados en la versión Alpha."""

    MOD = "mod"
    SHADER = "shader"
    RESOURCE_PACK = "resourcepack"

    @property
    def carpeta(self) -> str:
        """Subcarpeta de la instancia donde se guarda este tipo."""
        return {"mod": "mods", "shader": "shaderpacks", "resourcepack": "resourcepacks"}[self.value]


@dataclass
class ResultadoValidacion:
    """Resultado de validar un add-on contra una instancia."""

    valido: bool
    errores: list[str] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)

    @classmethod
    def ok(cls, advertencias: list[str] | None = None) -> "ResultadoValidacion":
        return cls(True, [], advertencias or [])

    @classmethod
    def error(cls, mensaje: str) -> "ResultadoValidacion":
        return cls(False, [mensaje], [])


@dataclass
class Instancia:
    """Perfil de juego independiente con su versión, loader y add-ons."""

    nombre: str
    version_minecraft: str
    loader: TipoLoader
    ruta: Path
    ram_mb: int = 4096
    ruta_java: str | None = None
    version_loader: str | None = None
    id: int | None = None
    ultima_vez: datetime | None = None

    def carpeta(self, tipo: TipoAddOn) -> Path:
        """Ruta de la subcarpeta de la instancia para ``tipo``."""
        return self.ruta / tipo.carpeta


@dataclass
class RegistroAddOn:
    """Fila persistida de un add-on instalado."""

    instancia_id: int
    tipo: TipoAddOn
    nombre: str
    archivo: str
    hash_sha1: str
    version: str = ""
    id_externo: str = ""
    activo: bool = True
    id: int | None = None
