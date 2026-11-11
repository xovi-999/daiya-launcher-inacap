"""Pruebas de integración: gestor de add-ons + SQLite + sistema de archivos (CU-03 a CU-06)."""
import pytest

from daiya.core.gestor_addons import AddOnDuplicadoError
from daiya.core.modelos import TipoAddOn
from herramientas import datos_prueba as dp


def test_anadir_mod_copia_y_registra(gestor, inst_fabric, origen):
    res = gestor.anadir(dp.crear_mod(origen, "sodium", "Sodium", "0.6.0", "~1.21"), inst_fabric)
    assert res.validacion.valido
    assert (inst_fabric.carpeta(TipoAddOn.MOD) / res.registro.archivo).is_file()
    assert [r.id_externo for r in gestor.listar(inst_fabric, TipoAddOn.MOD)] == ["sodium"]


def test_mod_incompatible_no_se_copia(gestor, inst_fabric, origen):
    res = gestor.anadir(dp.crear_mod(origen, "oldmod", "Old", "1", "1.20.1"), inst_fabric)
    assert not res.validacion.valido
    assert list(inst_fabric.carpeta(TipoAddOn.MOD).iterdir()) == []


def test_duplicado_lanza_excepcion_y_permite_reemplazar(gestor, inst_fabric, origen):
    gestor.anadir(dp.crear_mod(origen, "sodium", "Sodium", "0.5.0", "~1.21"), inst_fabric)
    nuevo = dp.crear_mod(origen, "sodium", "Sodium", "0.6.0", "~1.21")
    with pytest.raises(AddOnDuplicadoError):
        gestor.anadir(nuevo, inst_fabric)
    res = gestor.anadir(nuevo, inst_fabric, reemplazar=True)
    regs = gestor.listar(inst_fabric, TipoAddOn.MOD)
    assert len(regs) == 1 and regs[0].version == "0.6.0" and res.validacion.valido
    assert any((inst_fabric.ruta / ".papelera").iterdir())


def test_desactivar_y_activar_renombra(gestor, inst_fabric, origen):
    res = gestor.anadir(dp.crear_mod(origen, "lithium", "Lithium", "0.13", "1.21.x"), inst_fabric)
    reg = gestor.cambiar_estado(inst_fabric, res.registro, False)
    carpeta = inst_fabric.carpeta(TipoAddOn.MOD)
    assert (carpeta / (reg.archivo + ".disabled")).exists() and not (carpeta / reg.archivo).exists()
    gestor.cambiar_estado(inst_fabric, reg, True)
    assert (carpeta / reg.archivo).exists()


def test_eliminar_mueve_a_papelera(gestor, inst_fabric, origen):
    res = gestor.anadir(dp.crear_shader(origen), inst_fabric)
    gestor.eliminar(inst_fabric, res.registro)
    assert gestor.listar(inst_fabric) == []
    assert len(list((inst_fabric.ruta / ".papelera").iterdir())) == 1


def test_iris_instalado_elimina_advertencia_de_shader(gestor, inst_fabric, origen):
    gestor.anadir(dp.crear_mod(origen, "iris", "Iris", "1.8", ">=1.21"), inst_fabric)
    res = gestor.anadir(dp.crear_shader(origen), inst_fabric)
    assert res.validacion.advertencias == []


def test_nombre_de_archivo_se_sanea(gestor, inst_fabric, origen):
    ruta = dp.crear_mod(origen, "appleskin", "AppleSkin", "3", "1.21.x", archivo="Apple Skin (copia) ñ.jar")
    res = gestor.anadir(ruta, inst_fabric)
    assert res.registro.archivo == "Apple Skin _copia_ n.jar"


def test_archivo_inexistente(gestor, inst_fabric, tmp_path):
    assert not gestor.anadir(tmp_path / "no.jar", inst_fabric).validacion.valido


def test_tiempo_de_validacion_bajo_un_segundo(gestor, inst_fabric, origen):
    res = gestor.anadir(dp.crear_mod(origen, "sodium", "Sodium", "0.6.0", "~1.21"), inst_fabric)
    assert res.duracion_ms < 1000  # RNF-02
