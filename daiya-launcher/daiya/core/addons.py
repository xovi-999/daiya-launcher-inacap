"""Jerarquía de complementos (add-ons) y detección de su tipo.

``AddOn`` es una clase abstracta; ``Mod``, ``Shader`` y ``ResourcePack``
implementan cada una su propia validación (polimorfismo), de modo que el
gestor de add-ons no necesita conocer el tipo concreto.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from daiya.config import EXT_MOD, EXT_ZIP
from daiya.core import versiones
from daiya.core.archivos_zip import ArchivoInseguroError, abrir_zip_seguro, leer_entrada, tiene_prefijo
from daiya.core.modelos import Instancia, ResultadoValidacion, TipoAddOn, TipoLoader

#: Dependencias de Fabric que no son mods instalables por el usuario.
_DEPENDENCIAS_IMPLICITAS = {"minecraft", "fabricloader", "java", "fabric-loader"}

#: pack_format de resource packs por versión de Minecraft (referencia: Minecraft Wiki).
PACK_FORMAT = {"1.20.1": 15, "1.20.2": 18, "1.20.4": 22, "1.20.6": 32, "1.21": 34, "1.21.1": 34,
               "1.21.3": 42, "1.21.4": 46}


class ArchivoNoSoportadoError(ValueError):
    """El archivo no corresponde a ningún tipo de add-on soportado."""


@dataclass
class AddOn(ABC):
    """Complemento aportado por el usuario."""

    ruta: Path
    nombre: str
    version: str = ""
    id_externo: str = ""
    advertencias: list[str] = field(default_factory=list)

    tipo: TipoAddOn = field(init=False)

    @abstractmethod
    def validar(self, instancia: Instancia, ids_instalados: set[str]) -> ResultadoValidacion:
        """Valida el add-on contra ``instancia``.

        Args:
            instancia: instancia destino.
            ids_instalados: identificadores de los mods ya instalados en la instancia.
        """


@dataclass
class Mod(AddOn):
    """Mod de Fabric (.jar con ``fabric.mod.json``)."""

    requisito_mc: str | list[str] | None = None
    dependencias: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.tipo = TipoAddOn.MOD

    @classmethod
    def desde_descriptor(cls, ruta: Path, datos: dict) -> "Mod":
        """Construye el mod a partir del contenido de ``fabric.mod.json``."""
        if not isinstance(datos, dict) or not isinstance(datos.get("id"), str):
            raise ArchivoNoSoportadoError("fabric.mod.json no tiene un identificador válido.")
        depends = datos.get("depends") or {}
        if not isinstance(depends, dict):
            depends = {}
        deps = [d for d in depends if isinstance(d, str) and d not in _DEPENDENCIAS_IMPLICITAS]
        return cls(ruta=ruta, nombre=str(datos.get("name") or datos["id"])[:80],
                   version=str(datos.get("version", ""))[:40], id_externo=datos["id"][:64],
                   requisito_mc=depends.get("minecraft"), dependencias=deps)

    def validar(self, instancia: Instancia, ids_instalados: set[str]) -> ResultadoValidacion:
        if instancia.loader is not TipoLoader.FABRIC:
            return ResultadoValidacion.error(
                "La instancia es vanilla: los mods requieren una instancia con Fabric.")
        if not versiones.es_numerica(instancia.version_minecraft):
            # Los snapshots semanales no tienen número comparable: se instala, pero se advierte.
            faltantes = [d for d in self.dependencias if d not in ids_instalados]
            return ResultadoValidacion.ok(
                [f"No se puede comprobar la compatibilidad con {instancia.version_minecraft} (snapshot); "
                 "el mod podría no funcionar."]
                + [f"Requiere {d}: agrégalo para que el mod funcione." for d in faltantes])
        try:
            compatible = versiones.es_compatible(instancia.version_minecraft, self.requisito_mc)
        except ValueError:
            compatible = False
        if not compatible:
            return ResultadoValidacion.error(
                f"Este mod es para Minecraft {versiones.describir(self.requisito_mc)} "
                f"y tu instancia es {instancia.version_minecraft}.")
        faltantes = [d for d in self.dependencias if d not in ids_instalados]
        avisos = [f"Requiere {d}: agrégalo para que el mod funcione." for d in faltantes]
        return ResultadoValidacion.ok(avisos)


@dataclass
class Shader(AddOn):
    """Shaderpack (.zip con carpeta ``shaders/``); requiere Iris."""

    def __post_init__(self) -> None:
        self.tipo = TipoAddOn.SHADER

    def validar(self, instancia: Instancia, ids_instalados: set[str]) -> ResultadoValidacion:
        if instancia.loader is not TipoLoader.FABRIC:
            return ResultadoValidacion.error(
                "Los shaders necesitan Iris, que funciona sobre Fabric. Crea una instancia con Fabric.")
        if "iris" not in ids_instalados:
            return ResultadoValidacion.ok(["Iris no está instalado: los shaders no se verán hasta agregarlo."])
        return ResultadoValidacion.ok()


@dataclass
class ResourcePack(AddOn):
    """Paquete de recursos (.zip con ``pack.mcmeta``)."""

    pack_format: int | None = None

    def __post_init__(self) -> None:
        self.tipo = TipoAddOn.RESOURCE_PACK

    def validar(self, instancia: Instancia, ids_instalados: set[str]) -> ResultadoValidacion:
        esperado = PACK_FORMAT.get(instancia.version_minecraft)
        if esperado and self.pack_format and self.pack_format != esperado:
            return ResultadoValidacion.ok(
                [f"El pack usa el formato {self.pack_format} y la versión {instancia.version_minecraft} "
                 f"espera el {esperado}; podría verse incompleto."])
        return ResultadoValidacion.ok()


def _json(datos: bytes | None) -> dict | None:
    if datos is None:
        return None
    try:
        return json.loads(datos.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArchivoNoSoportadoError("El descriptor del archivo está mal formado.") from exc


def cargar_addon(ruta: Path) -> AddOn:
    """Detecta el tipo de ``ruta`` y devuelve el add-on correspondiente.

    Raises:
        ArchivoNoSoportadoError: si el archivo no es un add-on reconocido.
        ArchivoInseguroError: si el archivo no supera las validaciones de seguridad.
    """
    ext = ruta.suffix.lower()
    if ext not in EXT_MOD | EXT_ZIP:
        raise ArchivoNoSoportadoError("Archivo no soportado: usa .jar para mods o .zip para shaders y resource packs.")
    with abrir_zip_seguro(ruta) as zf:
        if ext in EXT_MOD:
            descriptor = _json(leer_entrada(zf, "fabric.mod.json"))
            if descriptor is not None:
                return Mod.desde_descriptor(ruta, descriptor)
            forge = ("META-INF/mods.toml", "META-INF/neoforge.mods.toml")
            if any(leer_entrada(zf, n) is not None for n in forge):
                raise ArchivoNoSoportadoError("Este mod es para Forge/NeoForge; la versión Alpha solo soporta Fabric.")
            raise ArchivoNoSoportadoError("El .jar no contiene fabric.mod.json: no es un mod de Fabric.")
        if tiene_prefijo(zf, "shaders/"):
            return Shader(ruta=ruta, nombre=ruta.stem[:80])
        mcmeta = _json(leer_entrada(zf, "pack.mcmeta"))
        if mcmeta is not None:
            pack = mcmeta.get("pack", {}) if isinstance(mcmeta, dict) else {}
            fmt = pack.get("pack_format") if isinstance(pack, dict) else None
            return ResourcePack(ruta=ruta, nombre=ruta.stem[:80], pack_format=fmt if isinstance(fmt, int) else None)
    raise ArchivoNoSoportadoError("El .zip no es un shader (falta shaders/) ni un resource pack (falta pack.mcmeta).")


__all__ = ["AddOn", "Mod", "Shader", "ResourcePack", "cargar_addon", "ArchivoNoSoportadoError",
           "ArchivoInseguroError", "PACK_FORMAT"]
