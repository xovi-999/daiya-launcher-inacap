"""Punto de entrada de la interfaz gráfica."""
from __future__ import annotations

import sys
import threading

from PySide6.QtWidgets import QApplication

from daiya.config import carpeta_base
from daiya.ui.contexto import Contexto
from daiya.ui.estilos import QSS
from daiya.ui.ventana_principal import VentanaPrincipal
from daiya.util.log import configurar_log


def main() -> int:
    """Inicia Daiya Launcher."""
    base = carpeta_base()
    configurar_log(base / "logs")
    app = QApplication(sys.argv)
    app.setApplicationName("Daiya Launcher")
    app.setStyleSheet(QSS)
    ctx = Contexto.crear(base)
    ctx.repo.respaldar(base / "respaldos")  # copia diaria de la base local (ISO 27002 8.13)
    # La lista de versiones de Mojang se actualiza sin bloquear la ventana; sin internet se usa la copia local.
    threading.Thread(target=ctx.versiones.actualizar, name="versiones", daemon=True).start()
    ventana = VentanaPrincipal(ctx)
    sesion = ctx.cuenta.renovar()
    perfil_local = ctx.repo.obtener_config("perfil_sin_conexion")
    if sesion:
        ventana.actualizar_cuenta(sesion.nombre_jugador)
    elif perfil_local:
        ventana.usar_perfil_sin_conexion(perfil_local)
    ventana.show()
    codigo = app.exec()
    ventana.deleteLater()  # libera la ventana antes que la aplicación
    app.processEvents()
    ctx.repo.cerrar()
    return codigo


if __name__ == "__main__":
    sys.exit(main())
