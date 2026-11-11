"""Pruebas de los controles de integridad, disponibilidad e instalación desde Modrinth."""
import hashlib

from daiya.core.modelos import TipoAddOn
from daiya.servicios.instalador import instalar_desde_modrinth
from daiya.servicios.modrinth import ErrorModrinth
from herramientas import datos_prueba as dp


def test_respaldo_crea_copia_y_rota(repo, inst_fabric, tmp_path):
    for _ in range(7):
        repo.respaldar(tmp_path / "respaldos", conservar=5)
    copias = sorted((tmp_path / "respaldos").glob("daiya_*.db"))
    assert len(copias) == 5
    import sqlite3
    from contextlib import closing
    with closing(sqlite3.connect(copias[-1])) as c:
        assert c.execute("SELECT nombre FROM instancia").fetchone()[0] == inst_fabric.nombre


def test_integridad_detecta_modificados_y_faltantes(gestor, inst_fabric, origen):
    a = gestor.anadir(dp.crear_mod(origen, "sodium", "Sodium", "1", "~1.21"), inst_fabric).registro
    b = gestor.anadir(dp.crear_mod(origen, "lithium", "Lithium", "1", "1.21.x"), inst_fabric).registro
    gestor.anadir(dp.crear_shader(origen), inst_fabric)
    carpeta = inst_fabric.carpeta(TipoAddOn.MOD)
    (carpeta / a.archivo).write_bytes(b"manipulado")
    (carpeta / b.archivo).unlink()
    r = gestor.verificar_integridad(inst_fabric)
    assert [x.id_externo for x in r["modificados"]] == ["sodium"]
    assert [x.id_externo for x in r["faltantes"]] == ["lithium"]
    assert len(r["ok"]) == 1


class ClienteFalso:
    """Doble de ClienteModrinth que entrega un .jar generado localmente."""

    def __init__(self, ruta_jar, compatible=True, falla=False):
        self.ruta, self.compatible, self.falla = ruta_jar, compatible, falla

    def version_compatible(self, proyecto, version, loader):
        if self.falla:
            raise ErrorModrinth("No fue posible conectar con Modrinth.")
        if not self.compatible:
            return None
        datos = self.ruta.read_bytes()
        return {"url": "https://cdn.modrinth.com/x.jar", "nombre": self.ruta.name,
                "sha512": hashlib.sha512(datos).hexdigest(), "tam": len(datos)}

    def descargar(self, archivo, carpeta):
        destino = carpeta / archivo["nombre"]
        destino.write_bytes(self.ruta.read_bytes())
        return destino


def test_instalar_iris_desde_modrinth_quita_advertencia(gestor, inst_fabric, origen):
    iris = dp.crear_mod(origen, "iris", "Iris Shaders", "1.8.0", ">=1.21")
    res = instalar_desde_modrinth(ClienteFalso(iris), gestor, inst_fabric, "iris")
    assert res.validacion.valido and res.registro.id_externo == "iris"
    assert gestor.anadir(dp.crear_shader(origen), inst_fabric).validacion.advertencias == []


def test_lo_descargado_tambien_se_valida(gestor, inst_fabric, origen):
    viejo = dp.crear_mod(origen, "oldmod", "Old", "1", "1.19.2")
    res = instalar_desde_modrinth(ClienteFalso(viejo), gestor, inst_fabric, "oldmod")
    assert not res.validacion.valido


def test_sin_version_compatible_o_sin_red(gestor, inst_fabric, origen):
    jar = dp.crear_mod(origen, "x", "X", "1", "*")
    assert "No hay una versión" in instalar_desde_modrinth(ClienteFalso(jar, compatible=False), gestor, inst_fabric, "x").validacion.errores[0]
    assert "conectar" in instalar_desde_modrinth(ClienteFalso(jar, falla=True), gestor, inst_fabric, "x").validacion.errores[0]
