"""Contenedor de dependencias de la aplicación (inyección simple)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from daiya.core.gestor_addons import GestorAddOns
from daiya.core.gestor_instancias import GestorInstancias
from daiya.datos.repositorio import Repositorio
from daiya.servicios.cuenta import ServicioCuenta
from daiya.servicios.lanzamiento import ServicioLanzamiento
from daiya.servicios.modrinth import ClienteModrinth
from daiya.servicios.versiones_mc import CatalogoVersiones


@dataclass
class Contexto:
    """Agrupa los servicios que usa la interfaz."""

    repo: Repositorio
    instancias: GestorInstancias
    addons: GestorAddOns
    cuenta: ServicioCuenta
    lanzamiento: ServicioLanzamiento
    modrinth: ClienteModrinth
    versiones: CatalogoVersiones

    @classmethod
    def crear(cls, base: Path, cuenta: ServicioCuenta | None = None,
              modrinth: ClienteModrinth | None = None, versiones: CatalogoVersiones | None = None) -> "Contexto":
        base.mkdir(parents=True, exist_ok=True)
        repo = Repositorio(base / "daiya.db")
        return cls(repo=repo, instancias=GestorInstancias(repo, base / "instancias"), addons=GestorAddOns(repo),
                   cuenta=cuenta or ServicioCuenta(), lanzamiento=ServicioLanzamiento(base / "juego"),
                   modrinth=modrinth or ClienteModrinth(),
                   versiones=versiones or CatalogoVersiones(base / "versiones.json"))
