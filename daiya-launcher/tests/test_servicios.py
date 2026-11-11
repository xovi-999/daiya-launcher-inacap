"""Pruebas de servicios externos con dobles de prueba (sin red ni cuenta real)."""
import hashlib
import logging

import pytest

from daiya.core.modelos import TipoLoader
from daiya.servicios.cuenta import ErrorSesion, Sesion, ServicioCuenta
from daiya.servicios.lanzamiento import ServicioLanzamiento
from daiya.servicios.modrinth import ClienteModrinth, ErrorModrinth
from daiya.util.log import FiltroRedaccion


class LlaveroFalso:
    def __init__(self):
        self.datos = {}

    def get_password(self, s, k):
        return self.datos.get((s, k))

    def set_password(self, s, k, v):
        self.datos[(s, k)] = v

    def delete_password(self, s, k):
        self.datos.pop((s, k))


class ApiMicrosoftFalsa:
    def get_secure_login_data(self, cid, redirect):
        return "https://login.live.com/oauth20_authorize.srf?state=abc", "abc", "verificador"

    def parse_auth_code_url(self, url, state):
        assert state in url
        return "codigo"

    def complete_login(self, *a):
        return {"name": "Steve", "id": "uuid-1", "access_token": "AT", "refresh_token": "RT"}

    def complete_refresh(self, *a):
        return self.complete_login()


def test_flujo_login_guarda_solo_refresh_en_llavero():
    llavero = LlaveroFalso()
    s = ServicioCuenta("cid", almacen=llavero, api=ApiMicrosoftFalsa())
    assert "state=abc" in s.url_inicio_sesion()
    sesion = s.completar_inicio_sesion("http://localhost:8765/callback?code=x&state=abc")
    assert sesion.nombre_jugador == "Steve"
    assert list(llavero.datos.values()) == ["RT"]
    assert "AT" not in repr(sesion)


def test_state_distinto_es_rechazado():
    s = ServicioCuenta("cid", almacen=LlaveroFalso(), api=ApiMicrosoftFalsa())
    s.url_inicio_sesion()
    with pytest.raises(ErrorSesion, match="state"):
        s.completar_inicio_sesion("http://localhost:8765/callback?code=x&state=OTRO")


def test_sin_client_id():
    with pytest.raises(ErrorSesion):
        ServicioCuenta("", almacen=LlaveroFalso(), api=ApiMicrosoftFalsa()).url_inicio_sesion()


def test_renovar_y_cerrar_sesion():
    llavero = LlaveroFalso()
    s = ServicioCuenta("cid", almacen=llavero, api=ApiMicrosoftFalsa())
    assert s.renovar() is None
    llavero.set_password("daiya-launcher", "refresh_token", "RT")
    assert s.renovar().uuid == "uuid-1"
    s.cerrar_sesion()
    assert s.sesion is None and llavero.datos == {}


class MllFalsa:
    class command:
        @staticmethod
        def get_minecraft_command(version, carpeta, opciones):
            return ["java", f"-Xmx{opciones['jvmArguments'][0][4:]}", "--accessToken", opciones["token"],
                    "--gameDir", opciones["gameDirectory"]]


def test_comando_incluye_ram_y_carpeta_de_instancia(inst_fabric, tmp_path):
    srv = ServicioLanzamiento(tmp_path / "juego", api=MllFalsa)
    cmd = srv.construir_comando(inst_fabric, "fabric-loader-1.21.1", Sesion("Steve", "u", "AT"))
    assert "-Xmx4096M" in cmd and str(inst_fabric.ruta) in cmd


def test_iniciar_rechaza_comando_como_texto(tmp_path):
    with pytest.raises(TypeError):
        ServicioLanzamiento(tmp_path).iniciar("java -jar x; rm -rf /", tmp_path)


def test_iniciar_ejecuta_sin_shell(tmp_path):
    import sys
    proc = ServicioLanzamiento(tmp_path).iniciar([sys.executable, "-c", "print('hola; echo inyeccion')"], tmp_path)
    assert proc.stdout.read().strip() == "hola; echo inyeccion" and proc.wait() == 0


def test_diagnostico_sugiere_desactivar_ultimo_addon():
    assert "Sodium" in ServicioLanzamiento.diagnosticar(["java.lang.Exception: boom"], "Sodium")
    assert ServicioLanzamiento.diagnosticar(["todo bien"], "Sodium") is None


def test_filtro_redacta_tokens():
    registro = logging.LogRecord("daiya", logging.INFO, "", 0, "url ?code=SECRETO&state=1 --accessToken eyJabc Bearer xyz", (), None)
    FiltroRedaccion().filter(registro)
    texto = registro.getMessage()
    assert "SECRETO" not in texto and "eyJabc" not in texto and "xyz" not in texto


class RespuestaFalsa:
    def __init__(self, json_=None, contenido=b""):
        self._json, self._contenido = json_, contenido

    def raise_for_status(self):
        pass

    def json(self):
        return self._json

    def iter_content(self, n):
        yield self._contenido

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class SesionHttpFalsa:
    def __init__(self, respuesta):
        self.headers, self.respuesta, self.llamadas = {}, respuesta, []

    def get(self, url, **kw):
        self.llamadas.append((url, kw))
        return self.respuesta


def test_busqueda_modrinth_envia_facetas_y_timeout():
    http = SesionHttpFalsa(RespuestaFalsa({"hits": [{"project_id": "AANobbMI", "slug": "sodium", "title": "Sodium"}]}))
    res = ClienteModrinth(http).buscar("sodium", "1.21.1")
    url, kw = http.llamadas[0]
    assert res[0]["slug"] == "sodium" and kw["timeout"] == 10 and "versions:1.21.1" in kw["params"]["facets"]
    assert "DaiyaLauncher" in http.headers["User-Agent"]


def test_descarga_verifica_hash(tmp_path):
    contenido = b"jar-falso"
    bueno = {"url": "https://cdn.modrinth.com/data/x/iris.jar", "nombre": "iris.jar",
             "sha512": hashlib.sha512(contenido).hexdigest(), "tam": 9}
    cliente = ClienteModrinth(SesionHttpFalsa(RespuestaFalsa(contenido=contenido)))
    assert cliente.descargar(bueno, tmp_path).read_bytes() == contenido
    with pytest.raises(ErrorModrinth, match="hash"):
        cliente.descargar({**bueno, "sha512": "0" * 128}, tmp_path)
    assert not any(p.suffix == ".part" for p in tmp_path.iterdir())


def test_descarga_rechaza_hosts_no_oficiales(tmp_path):
    cliente = ClienteModrinth(SesionHttpFalsa(RespuestaFalsa()))
    for url in ("http://cdn.modrinth.com/a.jar", "https://evil.example.com/a.jar"):
        with pytest.raises(ErrorModrinth, match="Origen"):
            cliente.descargar({"url": url, "nombre": "a.jar", "sha512": "", "tam": 1}, tmp_path)


def test_id_de_proyecto_invalido():
    with pytest.raises(ErrorModrinth):
        ClienteModrinth(SesionHttpFalsa(RespuestaFalsa([]))).version_compatible("../../admin", "1.21.1")


def test_version_compatible_devuelve_archivo_principal():
    datos = [{"files": [{"url": "https://cdn.modrinth.com/x.jar", "filename": "x.jar", "primary": True,
                         "hashes": {"sha512": "ab"}, "size": 5}]}]
    archivo = ClienteModrinth(SesionHttpFalsa(RespuestaFalsa(datos))).version_compatible("sodium", "1.21.1")
    assert archivo["nombre"] == "x.jar"


class LlaveroRoto(LlaveroFalso):
    def get_password(self, s, k):
        raise RuntimeError("sin backend")

    def set_password(self, s, k, v):
        raise RuntimeError("sin backend")


def test_sin_llavero_no_falla_ni_guarda_en_texto_plano(tmp_path):
    s = ServicioCuenta("cid", almacen=LlaveroRoto(), api=ApiMicrosoftFalsa())
    assert s.renovar() is None
    s.url_inicio_sesion()
    assert s.completar_inicio_sesion("http://localhost:8765/callback?code=x&state=abc").nombre_jugador == "Steve"
