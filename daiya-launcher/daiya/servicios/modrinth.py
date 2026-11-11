"""Cliente de la API pública de Modrinth (CU-09 y descarga de Iris).

- Toda petición usa HTTPS, tiempo de espera y un User-Agent identificable.
- Las descargas solo se aceptan desde el CDN oficial y se verifican con
  el hash SHA-512 que publica la API (OWASP A08:2025, integridad).
"""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests

from daiya.config import LIMITES, USER_AGENT

API = "https://api.modrinth.com/v2"
HOSTS_DESCARGA = {"cdn.modrinth.com"}
_ID_PROYECTO = re.compile(r"^[A-Za-z0-9_-]{2,64}$")
TIEMPO_ESPERA = 10


class ErrorModrinth(RuntimeError):
    """Error al consultar o descargar desde Modrinth."""


class ClienteModrinth:
    """Consultas de búsqueda, versiones y descarga verificada."""

    def __init__(self, sesion: requests.Session | None = None):
        self._http = sesion or requests.Session()
        self._http.headers.update({"User-Agent": USER_AGENT})

    def buscar(self, texto: str, version_mc: str, loader: str = "fabric", limite: int = 10) -> list[dict]:
        """Busca mods compatibles con ``version_mc`` y ``loader``."""
        texto = (texto or "").strip()[:100]
        facetas = [["project_type:mod"], [f"versions:{version_mc}"], [f"categories:{loader}"]]
        datos = self._get("/search", {"query": texto, "facets": json.dumps(facetas), "limit": max(1, min(limite, 20))})
        return [{"id": h.get("project_id"), "slug": h.get("slug"), "nombre": h.get("title"),
                 "descripcion": h.get("description", ""), "descargas": h.get("downloads", 0)}
                for h in datos.get("hits", [])]

    def version_compatible(self, proyecto: str, version_mc: str, loader: str = "fabric") -> dict | None:
        """Devuelve el archivo principal de la versión más reciente compatible."""
        if not _ID_PROYECTO.match(proyecto or ""):
            raise ErrorModrinth("Identificador de proyecto no válido.")
        versiones = self._get(f"/project/{proyecto}/version",
                              {"loaders": json.dumps([loader]), "game_versions": json.dumps([version_mc])})
        for v in versiones:
            archivos = v.get("files", [])
            principal = next((a for a in archivos if a.get("primary")), archivos[0] if archivos else None)
            if principal:
                return {"url": principal["url"], "nombre": principal["filename"],
                        "sha512": principal["hashes"]["sha512"], "tam": principal.get("size", 0)}
        return None

    def descargar(self, archivo: dict, carpeta: Path) -> Path:
        """Descarga ``archivo`` a ``carpeta`` verificando host, tamaño y SHA-512."""
        url = urlparse(archivo["url"])
        if url.scheme != "https" or url.hostname not in HOSTS_DESCARGA:
            raise ErrorModrinth("Origen de descarga no permitido.")
        if archivo.get("tam", 0) > LIMITES.tam_max_archivo:
            raise ErrorModrinth("El archivo supera el tamaño máximo permitido.")
        h = hashlib.sha512()
        carpeta.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkstemp(dir=carpeta, suffix=".part")[1])
        try:
            with self._http.get(archivo["url"], stream=True, timeout=TIEMPO_ESPERA) as r:
                r.raise_for_status()
                total = 0
                with open(tmp, "wb") as f:
                    for bloque in r.iter_content(64 * 1024):
                        total += len(bloque)
                        if total > LIMITES.tam_max_archivo:
                            raise ErrorModrinth("La descarga supera el tamaño máximo permitido.")
                        h.update(bloque)
                        f.write(bloque)
            if h.hexdigest() != archivo["sha512"]:
                raise ErrorModrinth("El archivo descargado no coincide con su hash: se descartó.")
            destino = carpeta / Path(archivo["nombre"]).name
            tmp.replace(destino)
            return destino
        finally:
            if tmp.exists():
                tmp.unlink()

    def _get(self, ruta: str, params: dict):
        try:
            r = self._http.get(API + ruta, params=params, timeout=TIEMPO_ESPERA)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            raise ErrorModrinth("No fue posible conectar con Modrinth.") from exc
