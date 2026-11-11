"""Pruebas unitarias de detección y validación de add-ons (RF-04, RF-05, RF-07)."""
import pytest

from daiya.core.addons import ArchivoNoSoportadoError, Mod, ResourcePack, Shader, cargar_addon
from daiya.core.archivos_zip import ArchivoInseguroError
from herramientas import datos_prueba as dp


def test_detecta_mod_fabric(origen):
    addon = cargar_addon(dp.crear_mod(origen, "sodium", "Sodium", "0.6.0", "~1.21"))
    assert isinstance(addon, Mod) and addon.id_externo == "sodium" and addon.version == "0.6.0"


def test_detecta_shader_y_resource_pack(origen):
    assert isinstance(cargar_addon(dp.crear_shader(origen)), Shader)
    rp = cargar_addon(dp.crear_resource_pack(origen, formato=34))
    assert isinstance(rp, ResourcePack) and rp.pack_format == 34


def test_rechaza_forge(origen):
    with pytest.raises(ArchivoNoSoportadoError, match="Forge"):
        cargar_addon(dp.crear_forge(origen))


def test_rechaza_extension_no_soportada(origen):
    f = origen / "virus.exe"
    f.write_bytes(b"MZ")
    with pytest.raises(ArchivoNoSoportadoError):
        cargar_addon(f)


def test_rechaza_archivo_corrupto(origen):
    with pytest.raises(ArchivoInseguroError):
        cargar_addon(dp.crear_corrupto(origen))


def test_rechaza_zip_slip(origen):
    with pytest.raises(ArchivoInseguroError, match="Ruta interna"):
        cargar_addon(dp.crear_zip_slip(origen))


def test_rechaza_zip_bomb(origen):
    with pytest.raises(ArchivoInseguroError, match="compresión"):
        cargar_addon(dp.crear_zip_bomb(origen))


def test_mod_incompatible_informa_versiones(origen, inst_fabric):
    mod = cargar_addon(dp.crear_mod(origen, "oldmod", "Old Mod", "1.0", "1.20.1"))
    r = mod.validar(inst_fabric, set())
    assert not r.valido and "1.20.1" in r.errores[0] and "1.21.1" in r.errores[0]


def test_mod_en_vanilla_es_rechazado(origen, inst_vanilla):
    mod = cargar_addon(dp.crear_mod(origen, "sodium", "Sodium", "0.6.0", "~1.21"))
    assert not mod.validar(inst_vanilla, set()).valido


def test_dependencia_faltante_genera_advertencia(origen, inst_fabric):
    mod = cargar_addon(dp.crear_mod(origen, "modmenu", "Mod Menu", "11", ">=1.21", {"fabric-api": "*"}))
    r = mod.validar(inst_fabric, set())
    assert r.valido and "fabric-api" in r.advertencias[0]
    assert mod.validar(inst_fabric, {"fabric-api"}).advertencias == []


def test_shader_sin_iris_advierte(origen, inst_fabric):
    sh = cargar_addon(dp.crear_shader(origen))
    assert "Iris" in sh.validar(inst_fabric, set()).advertencias[0]
    assert sh.validar(inst_fabric, {"iris"}).advertencias == []


def test_resource_pack_formato_distinto(origen, inst_fabric):
    rp = cargar_addon(dp.crear_resource_pack(origen, formato=15))
    r = rp.validar(inst_fabric, set())
    assert r.valido and "formato 15" in r.advertencias[0]


def test_descriptor_mal_formado(origen):
    import zipfile
    f = origen / "roto.jar"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("fabric.mod.json", "{no es json")
    with pytest.raises(ArchivoNoSoportadoError, match="mal formado"):
        cargar_addon(f)
