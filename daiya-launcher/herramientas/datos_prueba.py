"""Generador de archivos de prueba (mods, shaders y resource packs sintéticos).

Los archivos generados imitan la estructura real de cada tipo de add-on
(por ejemplo, un .jar con ``fabric.mod.json``), pero no contienen código
ejecutable. Se usan en las pruebas automatizadas y en las capturas.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path


def crear_mod(carpeta: Path, mod_id: str, nombre: str, version: str, minecraft: str | list | None,
              depends: dict | None = None, archivo: str | None = None) -> Path:
    """Crea un .jar de Fabric con su descriptor."""
    deps = {"fabricloader": ">=0.15.0"}
    if minecraft is not None:
        deps["minecraft"] = minecraft
    deps.update(depends or {})
    ruta = carpeta / (archivo or f"{mod_id}-{version}.jar")
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("fabric.mod.json", json.dumps({"schemaVersion": 1, "id": mod_id, "name": nombre,
                                                  "version": version, "depends": deps}))
        z.writestr(f"{mod_id}/Main.class", b"\xca\xfe\xba\xbe" + mod_id.encode() * 50)
    return ruta


def crear_forge(carpeta: Path) -> Path:
    ruta = carpeta / "jei-forge-1.20.1.jar"
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("META-INF/mods.toml", 'modLoader="javafml"\n[[mods]]\nmodId="jei"')
    return ruta


def crear_shader(carpeta: Path, nombre: str = "ComplementaryReimagined_r5.3") -> Path:
    ruta = carpeta / f"{nombre}.zip"
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("shaders/shaders.properties", f"# {nombre}\nsliders=SHADOW_QUALITY")
        z.writestr("shaders/composite.fsh", "#version 330\nvoid main(){}\n" * 20)
    return ruta


def crear_resource_pack(carpeta: Path, nombre: str = "FreshAnimations_v1.9", formato: int = 34) -> Path:
    ruta = carpeta / f"{nombre}.zip"
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("pack.mcmeta", json.dumps({"pack": {"pack_format": formato, "description": nombre}}))
        z.writestr("assets/minecraft/textures/block/stone.png", b"\x89PNG" + nombre.encode() + b"0" * 200)
    return ruta


def crear_zip_slip(carpeta: Path) -> Path:
    """Zip con una ruta interna que intenta salir de la carpeta (ataque zip slip)."""
    ruta = carpeta / "malicioso.zip"
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("pack.mcmeta", '{"pack":{"pack_format":34}}')
        z.writestr("../../../evil.txt", "pwned")
    return ruta


def crear_zip_bomb(carpeta: Path) -> Path:
    """Zip con una entrada muy comprimible (simula una zip bomb a pequeña escala)."""
    ruta = carpeta / "bomba.zip"
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("pack.mcmeta", '{"pack":{"pack_format":34}}')
        z.writestr("relleno.bin", b"\0" * (20 * 1024 * 1024))
    return ruta


def crear_corrupto(carpeta: Path) -> Path:
    ruta = carpeta / "dañado.jar"
    ruta.write_bytes(b"esto no es un zip")
    return ruta


#: Catálogo de mods de ejemplo usados en las capturas y pruebas de usuario.
CATALOGO = [
    ("fabric-api", "Fabric API", "0.102.0+1.21.1", ">=1.21 <1.21.2", {}),
    ("sodium", "Sodium", "0.6.0", "~1.21", {}),
    ("lithium", "Lithium", "0.13.0", "1.21.x", {}),
    ("iris", "Iris Shaders", "1.8.0", ">=1.21", {"sodium": "*"}),
    ("modmenu", "Mod Menu", "11.0.2", ">=1.21", {"fabric-api": "*"}),
    ("appleskin", "AppleSkin", "3.0.5", "1.21.x", {}),
]
