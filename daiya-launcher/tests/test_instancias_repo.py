"""Pruebas de gestión de instancias y del repositorio (CU-02, CU-08, RNF-04)."""
import pytest

from daiya.core.gestor_instancias import DatoInvalidoError
from daiya.core.modelos import RegistroAddOn, TipoAddOn, TipoLoader


def test_crear_instancia_crea_carpetas(instancias):
    inst = instancias.crear("Creativo", "1.20.1", TipoLoader.FABRIC)
    assert all((inst.ruta / c).is_dir() for c in ("mods", "shaderpacks", "resourcepacks"))
    assert inst.id is not None


@pytest.mark.parametrize("nombre,version,ram", [
    ("", "1.21.1", 4096), ("x" * 41, "1.21.1", 4096), ("../../etc", "1.21.1", 4096),
    ("Ok", "1.21.1; rm -rf /", 4096), ("Ok", "1.21.1", 512), ("Ok", "1.21.1", 999999),
    ("Nombre<script>", "1.21.1", 4096),
])
def test_validaciones_de_entrada(instancias, nombre, version, ram):
    with pytest.raises(DatoInvalidoError):
        instancias.crear(nombre, version, TipoLoader.FABRIC, ram)


def test_nombre_duplicado(instancias):
    instancias.crear("Mundo", "1.21.1", TipoLoader.FABRIC)
    with pytest.raises(DatoInvalidoError, match="Ya existe"):
        instancias.crear("mundo", "1.21.1", TipoLoader.FABRIC)


def test_configurar_ram_y_java_invalido(instancias, tmp_path):
    inst = instancias.crear("Cfg", "1.21.1", TipoLoader.FABRIC)
    assert instancias.configurar(inst, 6144, None).ram_mb == 6144
    falso = tmp_path / "notepad.exe"
    falso.write_text("x")
    with pytest.raises(DatoInvalidoError):
        instancias.configurar(inst, 6144, str(falso))


def test_inyeccion_sql_se_trata_como_texto(repo, instancias):
    inst = instancias.crear("Prueba (SQL)", "1.21.1", TipoLoader.FABRIC)
    repo.guardar_addon(RegistroAddOn(inst.id, TipoAddOn.MOD, "x'); DROP TABLE addon;--", "a.jar", "h"))
    assert repo.listar_addons(inst.id)[0].nombre.startswith("x');")
    assert repo.listar_instancias()


def test_config_clave_valor(repo):
    repo.guardar_config("idioma", "es")
    repo.guardar_config("idioma", "en")
    assert repo.obtener_config("idioma") == "en" and repo.obtener_config("nada", "-") == "-"


def test_borrado_en_cascada(repo, instancias):
    inst = instancias.crear("Temporal", "1.21.1", TipoLoader.FABRIC)
    repo.guardar_addon(RegistroAddOn(inst.id, TipoAddOn.MOD, "m", "m.jar", "h"))
    repo.eliminar_instancia(inst.id)
    assert repo.listar_addons(inst.id) == []
