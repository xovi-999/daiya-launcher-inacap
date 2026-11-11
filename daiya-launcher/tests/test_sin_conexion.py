"""Pruebas del perfil sin conexión (CU-01 alternativo, RF-01)."""
import json
import uuid

import pytest

from daiya.servicios.cuenta import ErrorSesion, ServicioCuenta, uuid_offline
from daiya.servicios.lanzamiento import ServicioLanzamiento


class LlaveroEspia:
    """Registra cualquier intento de guardar secretos."""

    def __init__(self):
        self.escrituras = []

    def get_password(self, s, k):
        return None

    def set_password(self, s, k, v):
        self.escrituras.append((s, k, v))

    def delete_password(self, s, k):
        pass


def test_uuid_igual_al_que_asigna_el_juego():
    # Valor conocido del servidor vanilla para "Notch" en modo sin conexión.
    assert uuid_offline("Notch") == "b50ad385-829d-3141-a216-7e7d7539ba7f"
    assert uuid.UUID(uuid_offline("Steve_01")).version == 3


def test_perfil_valido_no_guarda_secretos():
    llavero = LlaveroEspia()
    s = ServicioCuenta("", almacen=llavero)
    sesion = s.iniciar_sin_conexion("  Steve_01 ")
    assert sesion.nombre_jugador == "Steve_01" and sesion.sin_conexion
    assert sesion.token_acceso == "" and llavero.escrituras == []
    assert "***" in repr(sesion)


@pytest.mark.parametrize("nombre", ["", "ab", "a" * 17, "con espacio", "x;rm -rf /", "../admin", "ñandú", "--demo"])
def test_nombres_invalidos_son_rechazados(nombre):
    s = ServicioCuenta("")
    with pytest.raises(ErrorSesion):
        s.iniciar_sin_conexion(nombre)
    assert s.sesion is None


def test_cerrar_perfil_sin_conexion():
    s = ServicioCuenta("", almacen=LlaveroEspia())
    s.iniciar_sin_conexion("Alex")
    s.cerrar_sesion()
    assert s.sesion is None


def test_comando_real_sin_conexion(inst_fabric, tmp_path):
    """Integración con minecraft-launcher-lib real sobre una versión local mínima (sin red)."""
    juego = tmp_path / "juego"
    carpeta = juego / "versions" / "prueba-1.21.1"
    carpeta.mkdir(parents=True)
    (carpeta / "prueba-1.21.1.json").write_text(json.dumps({
        "id": "prueba-1.21.1", "type": "release", "mainClass": "net.minecraft.client.main.Main",
        "assets": "17", "assetIndex": {"id": "17"}, "libraries": [],
        "arguments": {"game": ["--username", "${auth_player_name}", "--gameDir", "${game_directory}",
                               "--uuid", "${auth_uuid}", "--accessToken", "${auth_access_token}"],
                      "jvm": ["-cp", "${classpath}"]}}), encoding="utf-8")
    sesion = ServicioCuenta("").iniciar_sin_conexion("Steve_01")
    cmd = ServicioLanzamiento(juego).construir_comando(inst_fabric, "prueba-1.21.1", sesion)
    assert cmd[cmd.index("--username") + 1] == "Steve_01"
    assert cmd[cmd.index("--uuid") + 1] == uuid_offline("Steve_01")
    assert cmd[cmd.index("--accessToken") + 1] == ""
    assert cmd[cmd.index("--gameDir") + 1] == str(inst_fabric.ruta) and "-Xmx4096M" in cmd
