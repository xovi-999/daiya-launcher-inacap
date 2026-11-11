"""Catálogo de versiones de Minecraft (RF-02): todas las que publica Mojang.

- La lista completa se descarga del manifiesto oficial de Mojang y la lista de
  versiones soportadas por Fabric, de la API oficial de Fabric. Ambas por
  HTTPS, con tiempo de espera y tamaño máximo.
- Se guarda una copia local para trabajar sin conexión (RNF-05). La copia se
  trata como dato no confiable: al leerla se vuelven a validar los ids.
- Si no hay copia ni conexión, se usa una lista de releases incluida.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

from daiya.config import USER_AGENT
from daiya.core import versiones

log = logging.getLogger("daiya.versiones")

MANIFIESTO = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
FABRIC_JUEGO = "https://meta.fabricmc.net/v2/versions/game"
TIEMPO_ESPERA = 10
TAM_MAXIMO = 5 * 1024 * 1024
TIPOS = ("release", "snapshot", "old_beta", "old_alpha")

#: Releases incluidas para el primer uso sin conexión (más reciente primero).
#: Con internet, la lista se reemplaza por la oficial de Mojang, que incluye versiones posteriores.
RESPALDO = (
    ["1.21.11", "1.21.10", "1.21.9", "1.21.8", "1.21.7", "1.21.6", "1.21.5", "1.21.4", "1.21.3", "1.21.2",
     "1.21.1", "1.21", "1.20.6", "1.20.5", "1.20.4", "1.20.3", "1.20.2", "1.20.1", "1.20",
     "1.19.4", "1.19.3", "1.19.2", "1.19.1", "1.19", "1.18.2", "1.18.1", "1.18", "1.17.1", "1.17",
     "1.16.5", "1.16.4", "1.16.3", "1.16.2", "1.16.1", "1.16", "1.15.2", "1.15.1", "1.15",
     "1.14.4", "1.14.3", "1.14.2", "1.14.1", "1.14", "1.13.2", "1.13.1", "1.13", "1.12.2", "1.12.1", "1.12",
     "1.11.2", "1.11.1", "1.11", "1.10.2", "1.10.1", "1.10", "1.9.4", "1.9.3", "1.9.2", "1.9.1", "1.9"]
    + [f"1.8.{n}" for n in range(9, 0, -1)] + ["1.8"]
)


@dataclass(frozen=True)
class VersionMC:
    """Una versión publicada por Mojang."""

    id: str
    tipo: str
    fecha: str = ""


class CatalogoVersiones:
    """Lista de versiones disponible para crear instancias."""

    def __init__(self, archivo_cache: Path, sesion: requests.Session | None = None):
        self.archivo_cache = Path(archivo_cache)
        self._http = sesion or requests.Session()
        self._http.headers.update({"User-Agent": USER_AGENT})
        self._versiones: list[VersionMC] = [VersionMC(v, "release") for v in RESPALDO]
        self._fabric: set[str] | None = None
        self.origen = "incluida"
        self._leer_cache()

    # ------------------------------------------------------------ consulta
    def listar(self, tipos: set[str] | frozenset[str] = frozenset({"release"}), solo_fabric: bool = False) -> list[str]:
        """Ids de versión de los ``tipos`` pedidos, del más reciente al más antiguo."""
        return [v.id for v in self._versiones
                if v.tipo in tipos and (not solo_fabric or self.admite_fabric(v.id))]

    def admite_fabric(self, version: str) -> bool:
        """Usa la lista oficial de Fabric si se descargó; si no, la regla local."""
        if self._fabric is not None:
            return version in self._fabric
        return versiones.admite_fabric(version)

    def cantidad(self) -> int:
        return len(self._versiones)

    # --------------------------------------------------------- actualización
    def actualizar(self) -> bool:
        """Descarga las listas oficiales. Devuelve ``False`` (sin lanzar) si no hay conexión."""
        try:
            manifiesto = self._get_json(MANIFIESTO)
            lista = self._validar(manifiesto.get("versions", []))
            if not lista:
                raise ValueError("El manifiesto no contiene versiones válidas.")
            try:
                fabric = {str(v["version"]) for v in self._get_json(FABRIC_JUEGO)
                          if isinstance(v, dict) and "version" in v}
            except Exception as exc:  # Fabric caído no impide actualizar la lista de Mojang
                log.warning("No se pudo obtener la lista de Fabric: %s", type(exc).__name__)
                fabric = self._fabric
        except Exception as exc:
            log.warning("No se pudo actualizar la lista de versiones: %s", type(exc).__name__)
            return False
        self._versiones, self._fabric, self.origen = lista, fabric, "mojang"
        self._guardar_cache()
        log.info("Lista de versiones actualizada: %d versiones", len(lista))
        return True

    def _get_json(self, url: str):
        r = self._http.get(url, timeout=TIEMPO_ESPERA)
        r.raise_for_status()
        if len(r.content) > TAM_MAXIMO:
            raise ValueError("Respuesta demasiado grande.")
        return r.json()

    @staticmethod
    def _validar(entradas) -> list[VersionMC]:
        """Conserva solo entradas con id de lista blanca y tipo conocido; ordena por fecha."""
        lista = []
        for e in entradas if isinstance(entradas, list) else []:
            if not isinstance(e, dict):
                continue
            vid, tipo = str(e.get("id", "")), str(e.get("type") or e.get("tipo") or "")
            if tipo in TIPOS and versiones.id_version_valido(vid):
                lista.append(VersionMC(vid, tipo, str(e.get("releaseTime") or e.get("fecha") or "")[:32]))
        lista.sort(key=lambda v: v.fecha, reverse=True)
        return lista

    # ----------------------------------------------------------- copia local
    def _leer_cache(self) -> None:
        try:
            datos = json.loads(self.archivo_cache.read_text(encoding="utf-8"))
            lista = self._validar(datos.get("versiones"))
        except (OSError, ValueError, AttributeError):
            return  # sin copia o copia dañada: se mantiene la lista incluida
        if lista:
            self._versiones, self.origen = lista, "guardada"
            fabric = datos.get("fabric")
            if isinstance(fabric, list):
                self._fabric = {v for v in fabric if isinstance(v, str) and versiones.id_version_valido(v)}

    def _guardar_cache(self) -> None:
        datos = {"versiones": [asdict(v) for v in self._versiones],
                 "fabric": sorted(self._fabric) if self._fabric is not None else None}
        try:
            self.archivo_cache.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.archivo_cache.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(datos, f)
            os.replace(tmp, self.archivo_cache)  # escritura atómica
        except OSError as exc:
            log.warning("No se pudo guardar la lista de versiones: %s", type(exc).__name__)
