"""Pruebas del catálogo con todas las versiones de Mojang (RF-02) y de su validación."""
import json

import pytest

from daiya.core import versiones
from daiya.core.addons import Mod
from daiya.core.gestor_instancias import DatoInvalidoError
from daiya.core.modelos import Instancia, TipoLoader
from daiya.servicios.versiones_mc import RESPALDO, TAM_MAXIMO, CatalogoVersiones

MANIFIESTO = {"latest": {"release": "1.21.1", "snapshot": "24w33a"}, "versions": [
    {"id": "24w33a", "type": "snapshot", "releaseTime": "2024-08-15T12:00:00+00:00"},
    {"id": "1.21.1", "type": "release", "releaseTime": "2024-08-08T12:00:00+00:00"},
    {"id": "1.21-pre1", "type": "snapshot", "releaseTime": "2024-05-29T12:00:00+00:00"},
    {"id": "1.12.2", "type": "release", "releaseTime": "2017-09-18T08:39:46+00:00"},
    {"id": "b1.7.3", "type": "old_beta", "releaseTime": "2011-07-07T22:00:00+00:00"},
    {"id": "rd-132211", "type": "old_alpha", "releaseTime": "2009-05-13T20:11:00+00:00"},
    {"id": "../../evil", "type": "release", "releaseTime": "2030-01-01T00:00:00+00:00"},
    {"id": "3D Shareware v1.34", "type": "snapshot", "releaseTime": "2019-04-01T11:00:00+00:00"},
    {"id": "1.99", "type": "desconocido", "releaseTime": "2031-01-01T00:00:00+00:00"},
]}
FABRIC = [{"version": "24w33a", "stable": False}, {"version": "1.21.1", "stable": True},
          {"version": "1.21-pre1", "stable": False}]


class Respuesta:
    def __init__(self, datos, tam=None):
        self._datos = datos
        self.content = b"x" * (tam if tam is not None else len(json.dumps(datos)))

    def raise_for_status(self):
        pass

    def json(self):
        return self._datos


class SesionFalsa:
    def __init__(self, respuestas=None, error=None):
        self.headers, self.urls = {}, []
        self.respuestas, self.error = respuestas or {}, error

    def get(self, url, timeout):
        assert url.startswith("https://") and timeout > 0
        self.urls.append(url)
        if self.error:
            raise self.error
        return self.respuestas[url.split("/")[2]]


def _online(tam=None):
    return SesionFalsa({"piston-meta.mojang.com": Respuesta(MANIFIESTO, tam), "meta.fabricmc.net": Respuesta(FABRIC)})


def test_sin_conexion_usa_la_lista_incluida(tmp_path):
    cat = CatalogoVersiones(tmp_path / "v.json", SesionFalsa(error=ConnectionError("sin red")))
    assert cat.actualizar() is False
    assert cat.origen == "incluida" and cat.listar() == RESPALDO and "1.8.9" in cat.listar()


def test_actualiza_desde_mojang_filtra_y_ordena(tmp_path):
    cat = CatalogoVersiones(tmp_path / "v.json", _online())
    assert cat.actualizar() and cat.origen == "mojang"
    assert cat.listar() == ["1.21.1", "1.12.2"]
    todas = cat.listar({"release", "snapshot", "old_beta", "old_alpha"})
    assert todas == ["24w33a", "1.21.1", "1.21-pre1", "1.12.2", "b1.7.3", "rd-132211"]
    assert "../../evil" not in todas and "3D Shareware v1.34" not in todas


def test_fabric_usa_la_lista_oficial(tmp_path):
    cat = CatalogoVersiones(tmp_path / "v.json", _online())
    cat.actualizar()
    assert cat.listar({"release", "snapshot", "old_beta"}, solo_fabric=True) == ["24w33a", "1.21.1", "1.21-pre1"]


def test_copia_local_se_reutiliza_sin_conexion(tmp_path):
    CatalogoVersiones(tmp_path / "v.json", _online()).actualizar()
    cat = CatalogoVersiones(tmp_path / "v.json", SesionFalsa(error=ConnectionError()))
    assert cat.origen == "guardada" and cat.listar({"old_beta"}) == ["b1.7.3"]
    assert not cat.admite_fabric("1.12.2")


@pytest.mark.parametrize("contenido", ["{no es json", json.dumps({"versiones": [{"id": "../x", "tipo": "release"}]}),
                                       json.dumps([1, 2, 3])])
def test_copia_local_danada_no_rompe_la_app(tmp_path, contenido):
    (tmp_path / "v.json").write_text(contenido, encoding="utf-8")
    cat = CatalogoVersiones(tmp_path / "v.json", SesionFalsa(error=ConnectionError()))
    assert cat.origen == "incluida" and cat.listar() == RESPALDO


def test_respuesta_demasiado_grande_se_rechaza(tmp_path):
    cat = CatalogoVersiones(tmp_path / "v.json", _online(tam=TAM_MAXIMO + 1))
    assert cat.actualizar() is False and cat.origen == "incluida"


@pytest.mark.parametrize("version,esperado", [
    ("1.21.1", True), ("1.14", True), ("1.13.2", False), ("26.1", True), ("1.21-pre1", True),
    ("24w14a", True), ("18w43b", True), ("18w40a", False), ("b1.7.3", False), ("rd-132211", False)])
def test_regla_local_de_fabric(version, esperado):
    assert versiones.admite_fabric(version) is esperado


@pytest.mark.parametrize("version", ["", "../1.21", "1.21/..", "1.21 1", "1.21;rm", "-v", "a" * 41])
def test_ids_de_version_invalidos(version):
    assert not versiones.id_version_valido(version)


def test_crear_instancias_de_cualquier_version(instancias):
    assert instancias.crear("Beta clásica", "b1.7.3", TipoLoader.VANILLA).version_minecraft == "b1.7.3"
    assert instancias.crear("Snapshot", "24w14a", TipoLoader.FABRIC).version_minecraft == "24w14a"
    assert instancias.crear("Antigua", "1.8.9", TipoLoader.VANILLA).id is not None
    with pytest.raises(DatoInvalidoError, match="Fabric no está disponible"):
        instancias.crear("Fabric viejo", "1.12.2", TipoLoader.FABRIC)


def test_mod_en_snapshot_se_instala_con_advertencia(tmp_path):
    inst = Instancia(nombre="S", version_minecraft="24w14a", loader=TipoLoader.FABRIC, ruta=tmp_path)
    mod = Mod(ruta=tmp_path / "m.jar", nombre="Sodium", id_externo="sodium", requisito_mc="~1.21")
    r = mod.validar(inst, set())
    assert r.valido and "snapshot" in r.advertencias[0]
