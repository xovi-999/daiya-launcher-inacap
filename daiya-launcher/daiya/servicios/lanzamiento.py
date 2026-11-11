"""Preparación y ejecución del juego (CU-07).

La instalación de versiones y de Fabric, y la construcción del comando, se
delegan en ``minecraft-launcher-lib``. El proceso se inicia con una lista de
argumentos y ``shell=False`` para impedir la inyección de comandos
(OWASP A05:2025).
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Callable

import minecraft_launcher_lib as mll

from daiya.core.modelos import Instancia, TipoLoader
from daiya.servicios.cuenta import Sesion

log = logging.getLogger("daiya.lanzamiento")


class ServicioLanzamiento:
    """Instala lo necesario y lanza una instancia."""

    def __init__(self, carpeta_juego: Path, api=mll):
        self.carpeta_juego = Path(carpeta_juego)
        self._api = api

    def preparar(self, inst: Instancia, progreso: Callable[[str], None] | None = None) -> str:
        """Instala (o verifica) la versión y el loader. Devuelve el id de versión a lanzar."""
        cb = {"setStatus": progreso} if progreso else None
        if inst.loader is TipoLoader.FABRIC:
            cargador = self._api.mod_loader.get_mod_loader("fabric")
            return cargador.install(inst.version_minecraft, self.carpeta_juego,
                                    loader_version=inst.version_loader, callback=cb, java=inst.ruta_java)
        self._api.install.install_minecraft_version(inst.version_minecraft, self.carpeta_juego, callback=cb)
        return inst.version_minecraft

    def construir_comando(self, inst: Instancia, version_id: str, sesion: Sesion) -> list[str]:
        """Arma el comando de ejecución con la RAM, Java y carpeta de la instancia.

        Con un perfil sin conexión el token va vacío: el juego abre en modo un
        jugador/LAN y los servidores oficiales rechazan la conexión.
        """
        opciones = {
            "username": sesion.nombre_jugador,
            "uuid": sesion.uuid,
            "token": sesion.token_acceso,  # vacío en modo sin conexión
            "jvmArguments": [f"-Xmx{inst.ram_mb}M", f"-Xms{min(inst.ram_mb, 1024)}M"],
            "gameDirectory": str(inst.ruta),
            "launcherName": "DaiyaLauncher",
            "launcherVersion": "0.1.0",
        }
        if inst.ruta_java:
            opciones["executablePath"] = inst.ruta_java
        return self._api.command.get_minecraft_command(version_id, self.carpeta_juego, opciones)

    def iniciar(self, comando: list[str], directorio: Path) -> subprocess.Popen:
        """Inicia el juego sin shell y con salida unificada para el visor de log."""
        if not isinstance(comando, list) or not all(isinstance(a, str) for a in comando):
            raise TypeError("El comando debe ser una lista de argumentos de texto.")
        log.info("Iniciando Minecraft (%d argumentos)", len(comando))  # el token no se registra
        return subprocess.Popen(comando, cwd=directorio, shell=False, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")

    @staticmethod
    def diagnosticar(lineas_log: list[str], ultimo_addon: str | None) -> str | None:
        """Sugerencia para el usuario si el juego terminó con error."""
        if not any("Exception" in linea or "Error" in linea for linea in lineas_log[-50:]):
            return None
        sugerencia = "El juego se cerró con un error."
        if ultimo_addon:
            sugerencia += f" Prueba desactivar el último add-on agregado ({ultimo_addon})."
        return sugerencia
