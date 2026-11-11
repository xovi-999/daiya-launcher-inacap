"""Prepara una carpeta con archivos de demostración para la exposición.

Uso: ``python -m herramientas.preparar_demo [carpeta]`` (por defecto ``demo_addons``).
Crea mods compatibles e incompatibles, un mod de Forge, un archivo malicioso
(zip slip), shaders y un resource pack, para mostrar en vivo cada validación.
"""
from __future__ import annotations

import sys
from pathlib import Path

from herramientas import datos_prueba as dp


def main(destino: str = "demo_addons") -> Path:
    carpeta = Path(destino)
    (carpeta / "1_compatibles").mkdir(parents=True, exist_ok=True)
    (carpeta / "2_rechazados").mkdir(exist_ok=True)
    (carpeta / "3_shaders_y_packs").mkdir(exist_ok=True)
    for mod_id, nombre, version, mc, deps in dp.CATALOGO:
        dp.crear_mod(carpeta / "1_compatibles", mod_id, nombre, version, mc, deps)
    dp.crear_mod(carpeta / "2_rechazados", "create", "Create", "0.5.1", "1.20.1")
    dp.crear_forge(carpeta / "2_rechazados")
    dp.crear_zip_slip(carpeta / "2_rechazados")
    dp.crear_corrupto(carpeta / "2_rechazados")
    dp.crear_shader(carpeta / "3_shaders_y_packs")
    dp.crear_shader(carpeta / "3_shaders_y_packs", "BSL_v8.2.09")
    dp.crear_resource_pack(carpeta / "3_shaders_y_packs")
    print(f"Archivos de demostración en {carpeta.resolve()}")
    return carpeta


if __name__ == "__main__":
    main(*sys.argv[1:])
