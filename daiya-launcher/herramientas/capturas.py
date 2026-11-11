"""Genera capturas de la interfaz con datos de prueba (``python -m herramientas.capturas``)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from daiya.core.modelos import TipoAddOn, TipoLoader  # noqa: E402
from daiya.ui.contexto import Contexto  # noqa: E402
from daiya.ui.dialogos import DialogoConfiguracion, DialogoCuenta, DialogoNuevaInstancia  # noqa: E402
from daiya.ui.estilos import QSS  # noqa: E402
from daiya.ui.ventana_principal import VentanaPrincipal  # noqa: E402
from herramientas import datos_prueba as dp  # noqa: E402

SALIDA = Path("reportes/capturas")


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(QSS)
    base = Path(tempfile.mkdtemp())
    org = base / "Descargas"
    org.mkdir()
    ctx = Contexto.crear(base / "daiya")
    survival = ctx.instancias.crear("Survival con shaders", "1.21.1", TipoLoader.FABRIC, 6144)
    tecnico = ctx.instancias.crear("Técnico 1.20.1", "1.20.1", TipoLoader.FABRIC, 4096)
    ctx.instancias.crear("Vanilla pura", "1.21.4", TipoLoader.VANILLA, 2048)

    v = VentanaPrincipal(ctx)
    v.resize(1180, 720)
    v.show()

    def foto(nombre: str, widget=None) -> None:
        app.processEvents()
        (widget or v).grab().save(str(SALIDA / f"{nombre}.png"))

    v.recargar_instancias(survival.id)
    archivos = [dp.crear_mod(org, *m[:4], depends=m[4]) for m in dp.CATALOGO]
    v.anadir_archivos(archivos)
    foto("01_anadir_mods")

    reg = next(r for r in ctx.addons.listar(survival, TipoAddOn.MOD) if r.id_externo == "appleskin")
    v._cambiar_estado(reg, False)
    v.anadir_archivos([dp.crear_shader(org), dp.crear_shader(org, "BSL_v8.2.09"),
                       dp.crear_resource_pack(org)])
    v.pestanas.setCurrentIndex(1)
    foto("02_shaders")

    v.pestanas.setCurrentIndex(0)
    v.anadir_archivos([dp.crear_mod(org, "create", "Create", "0.5.1", "1.20.1"), dp.crear_forge(org),
                       dp.crear_zip_slip(org)])
    foto("03_rechazos")

    v.recargar_instancias(tecnico.id)
    v.anadir_archivos([dp.crear_shader(org, "Sildurs_Vibrant_1.54")])
    v.pestanas.setCurrentIndex(1)
    foto("04_shader_sin_iris")

    foto("04b_boton_instalar_iris")

    v.recargar_instancias(survival.id)
    v.pestanas.setCurrentIndex(0)
    regs = ctx.addons.listar(survival, TipoAddOn.MOD)
    sodium = next(r for r in regs if r.id_externo == "sodium")
    (survival.carpeta(TipoAddOn.MOD) / sodium.archivo).write_bytes(b"archivo alterado fuera del launcher")
    v.verificar_integridad()
    foto("08_integridad")

    from daiya.ui.dialogo_modrinth import DialogoModrinth
    dm = DialogoModrinth(ctx.modrinth, survival, v)
    dm.texto.setText("minimap")
    dm.mostrar([{"id": "1", "slug": "xaeros-minimap", "nombre": "Xaero's Minimap", "descripcion": "Minimapa con waypoints", "descargas": 100},
                {"id": "2", "slug": "journeymap", "nombre": "JourneyMap", "descripcion": "Mapa en tiempo real", "descargas": 50},
                {"id": "3", "slug": "voxelmap-updated", "nombre": "VoxelMap", "descripcion": "Minimapa clásico", "descargas": 20}])
    dm.estado.setText("3 resultados compatibles (datos de ejemplo: captura generada sin conexión).")
    dm.show()
    foto("09_modrinth", dm)
    dm.close()

    v.recargar_instancias(survival.id)
    v.pestanas.setCurrentIndex(0)
    v.jugar()
    foto("05_jugar_sin_sesion")

    dlg = DialogoNuevaInstancia(v, ctx.versiones)
    dlg.nombre.setText("Skyblock con amigos")
    dlg.show()
    foto("06_nueva_instancia", dlg)
    dlg.close()
    cfg = DialogoConfiguracion(survival, v)
    cfg.show()
    foto("07_configuracion", cfg)
    cfg.close()
    dc = DialogoCuenta(v, "Steve_01")
    dc.show()
    foto("10_cuenta", dc)
    dc.close()
    v.usar_perfil_sin_conexion("Steve_01")
    foto("11_perfil_sin_conexion")
    v.close()
    v.deleteLater()
    app.processEvents()
    print("Capturas en", SALIDA.resolve())


if __name__ == "__main__":
    main()
