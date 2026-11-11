"""Pruebas de la interfaz en modo sin pantalla (offscreen)."""
import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402

from daiya.core.modelos import TipoAddOn, TipoLoader  # noqa: E402
from daiya.ui.contexto import Contexto  # noqa: E402
from daiya.ui.ventana_principal import VentanaPrincipal  # noqa: E402
from herramientas import datos_prueba as dp  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _cerrar_bases_de_datos(monkeypatch):
    """Cierra la conexión SQLite de cada contexto creado en la prueba."""
    creados, original = [], Contexto.crear

    def crear(*args, **kwargs):
        ctx = original(*args, **kwargs)
        creados.append(ctx)
        return ctx

    monkeypatch.setattr(Contexto, "crear", staticmethod(crear))
    yield
    for ctx in creados:
        ctx.repo.cerrar()


def test_soltar_archivos_actualiza_tablas(app, tmp_path):
    ctx = Contexto.crear(tmp_path / "home")
    inst = ctx.instancias.crear("UI", "1.21.1", TipoLoader.FABRIC)
    v = VentanaPrincipal(ctx)
    v.recargar_instancias(inst.id)
    origen = tmp_path / "o"
    origen.mkdir()
    v.anadir_archivos([dp.crear_mod(origen, "sodium", "Sodium", "0.6.0", "~1.21"), dp.crear_shader(origen),
                       dp.crear_mod(origen, "old", "Old", "1", "1.20.1")])
    assert v.tablas[TipoAddOn.MOD].rowCount() == 1
    assert v.tablas[TipoAddOn.SHADER].rowCount() == 1
    assert v.banner.property("nivel") == "error" and "Old" not in v.tablas[TipoAddOn.MOD].item(0, 1).text()


def test_jugar_sin_sesion_muestra_aviso(app, tmp_path):
    ctx = Contexto.crear(tmp_path / "home2")
    inst = ctx.instancias.crear("UI2", "1.21.1", TipoLoader.FABRIC)
    v = VentanaPrincipal(ctx)
    v.recargar_instancias(inst.id)
    v.jugar()
    assert "iniciar sesión" in v.banner.text()


def test_boton_instalar_iris_aparece_con_la_advertencia(app, tmp_path):
    ctx = Contexto.crear(tmp_path / "home3")
    inst = ctx.instancias.crear("UI3", "1.21.1", TipoLoader.FABRIC)
    v = VentanaPrincipal(ctx)
    v.show()
    v.recargar_instancias(inst.id)
    origen = tmp_path / "o3"
    origen.mkdir()
    v.anadir_archivos([dp.crear_shader(origen)])
    assert v.btn_iris.isVisible()


def test_dialogo_modrinth_muestra_resultados(app, tmp_path):
    from daiya.ui.dialogo_modrinth import DialogoModrinth
    ctx = Contexto.crear(tmp_path / "home4")
    inst = ctx.instancias.crear("UI4", "1.21.1", TipoLoader.FABRIC)
    dlg = DialogoModrinth(ctx.modrinth, inst)
    dlg.mostrar([{"id": "AANobbMI", "slug": "sodium", "nombre": "Sodium", "descripcion": "Rendimiento", "descargas": 1000}])
    dlg.tabla.selectRow(0)
    dlg._instalar()
    assert dlg.proyecto_elegido == "sodium"


def test_perfil_sin_conexion_permite_jugar_y_se_recuerda(app, tmp_path):
    ctx = Contexto.crear(tmp_path / "home5")
    v = VentanaPrincipal(ctx)
    assert not v.usar_perfil_sin_conexion("mal nombre")
    assert v.banner.property("nivel") == "error" and ctx.cuenta.sesion is None
    assert v.usar_perfil_sin_conexion("Steve_01")
    assert "sin conexión" in v.lbl_cuenta.text() and v.btn_sesion.text() == "Cerrar sesión"
    assert ctx.repo.obtener_config("perfil_sin_conexion") == "Steve_01"


def test_dialogo_cuenta_ofrece_ambas_opciones(app):
    from daiya.ui.dialogos import DialogoCuenta
    dlg = DialogoCuenta(nombre_guardado="Alex")
    assert dlg.nombre.text() == "Alex" and "sin fines de lucro" in dlg.AVISO
    estado, _, _ = dlg.nombre.validator().validate("x;rm", 0)
    assert estado.name != "Acceptable"  # el campo no acepta caracteres fuera de la lista blanca
    dlg.btn_offline.click()
    assert dlg.eleccion == "sin_conexion" and dlg.result() == DialogoCuenta.Accepted
    dlg2 = DialogoCuenta()
    dlg2.btn_microsoft.click()
    assert dlg2.eleccion == "microsoft"


def test_dialogo_nueva_instancia_muestra_todas_las_versiones(app, tmp_path):
    from daiya.core.modelos import TipoLoader as TL
    from daiya.servicios.versiones_mc import CatalogoVersiones
    from daiya.ui.dialogos import DialogoNuevaInstancia
    from tests.test_versiones_mc import _online
    cat = CatalogoVersiones(tmp_path / "v.json", _online())
    dlg = DialogoNuevaInstancia(catalogo=cat)
    dlg.actualizar_lista()
    items = lambda: [dlg.version.itemText(i) for i in range(dlg.version.count())]  # noqa: E731
    assert items() == ["1.21.1"] and "lista oficial de Mojang" in dlg.lbl_versiones.text()  # Fabric por defecto
    dlg.chk_snapshots.setChecked(True)
    assert items() == ["24w33a", "1.21.1", "1.21-pre1"]
    dlg.loader.setCurrentIndex(dlg.loader.findData(TL.VANILLA))
    dlg.chk_antiguas.setChecked(True)
    assert items()[-2:] == ["b1.7.3", "rd-132211"] and len(items()) == 6
    dlg.version.setCurrentText("b1.7.3")
    dlg.nombre.setText("Beta")
    assert dlg.datos() == ("Beta", "b1.7.3", TL.VANILLA, 4096)
