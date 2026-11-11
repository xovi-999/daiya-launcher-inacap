"""Mide tiempos de respuesta y tasa de aciertos del validador de add-ons.

Uso: ``python -m herramientas.benchmark`` (genera ``reportes/metricas.json``).
"""
from __future__ import annotations

import json
import os
import statistics
import tempfile
import time
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from daiya.core.gestor_addons import AddOnDuplicadoError, GestorAddOns  # noqa: E402
from daiya.core.gestor_instancias import GestorInstancias  # noqa: E402
from daiya.core.modelos import TipoLoader  # noqa: E402
from daiya.datos.repositorio import Repositorio  # noqa: E402
from herramientas import datos_prueba as dp  # noqa: E402

REPETICIONES = 200


def _mod_grande(carpeta: Path, mb: int) -> Path:
    ruta = carpeta / f"grande-{mb}mb.jar"
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_STORED) as z:
        z.writestr("fabric.mod.json", json.dumps({"id": f"grande{mb}", "name": "Grande", "version": "1",
                                                  "depends": {"minecraft": ">=1.21"}}))
        bloque = os.urandom(1024 * 1024)
        for i in range(mb):
            z.writestr(f"assets/a{i}.bin", bloque)
        for i in range(2000):
            z.writestr(f"clases/C{i}.class", b"\xca\xfe" * 20)
    return ruta


def medir(fn, n=REPETICIONES) -> dict:
    tiempos = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        tiempos.append((time.perf_counter() - t0) * 1000)
    tiempos.sort()
    return {"n": n, "media_ms": round(statistics.mean(tiempos), 3), "p95_ms": round(tiempos[int(n * 0.95) - 1], 3),
            "max_ms": round(tiempos[-1], 3)}


def main() -> dict:
    tmp = Path(tempfile.mkdtemp())
    repo = Repositorio(tmp / "b.db")
    gi = GestorInstancias(repo, tmp / "inst")
    ga = GestorAddOns(repo)
    org = tmp / "o"
    org.mkdir()
    metricas: dict = {}

    def anadir_y_quitar(ruta):
        inst = gi.listar()[0]
        r = ga.anadir(ruta, inst)
        if r.registro:
            ga.eliminar(inst, r.registro)

    gi.crear("Bench", "1.21.1", TipoLoader.FABRIC)
    casos = {
        "Añadir mod (.jar, 4 KB)": dp.crear_mod(org, "sodium", "Sodium", "0.6.0", "~1.21"),
        "Añadir shader (.zip)": dp.crear_shader(org),
        "Añadir resource pack (.zip)": dp.crear_resource_pack(org),
        "Rechazar mod incompatible": dp.crear_mod(org, "old", "Old", "1", "1.20.1"),
        "Añadir mod grande (20 MB, 2.000 entradas)": _mod_grande(org, 20),
    }
    for nombre, ruta in casos.items():
        n = 30 if "grande" in nombre else REPETICIONES
        metricas[nombre] = medir(lambda r=ruta: anadir_y_quitar(r), n)

    inst = gi.listar()[0]
    reg = ga.anadir(dp.crear_mod(org, "lithium", "Lithium", "1", "1.21.x"), inst).registro
    estado = [True]

    def alternar():
        estado[0] = not estado[0]
        ga.cambiar_estado(inst, reg, estado[0])

    metricas["Activar / desactivar add-on"] = medir(alternar)
    contador = [0]

    def crear_inst():
        contador[0] += 1
        gi.crear(f"Inst {contador[0]}", "1.21.1", TipoLoader.FABRIC)

    metricas["Crear instancia (carpetas + SQLite)"] = medir(crear_inst, 100)

    t0 = time.perf_counter()
    from PySide6.QtWidgets import QApplication
    from daiya.ui.contexto import Contexto
    from daiya.ui.estilos import QSS
    from daiya.ui.ventana_principal import VentanaPrincipal
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(QSS)
    v = VentanaPrincipal(Contexto.crear(tmp / "ui"))
    v.show()
    app.processEvents()
    metricas["Apertura de la ventana principal"] = {"n": 1, "media_ms": round((time.perf_counter() - t0) * 1000, 1)}
    v.close()
    v.deleteLater()
    app.processEvents()
    del v

    # Tasa de aciertos de clasificación sobre un corpus etiquetado
    corpus = []
    for i in range(20):
        corpus.append((dp.crear_mod(org, f"ok{i}", f"Ok {i}", "1", ">=1.21", archivo=f"ok{i}.jar"), True))
        corpus.append((dp.crear_mod(org, f"bad{i}", f"Bad {i}", "1", "1.19.2", archivo=f"bad{i}.jar"), False))
    for i in range(5):
        corpus.append((dp.crear_shader(org, f"shader{i}"), True))
        corpus.append((dp.crear_resource_pack(org, f"rp{i}"), True))
    especiales = tmp / "esp"
    especiales.mkdir()
    for fn in (dp.crear_forge, dp.crear_zip_slip, dp.crear_zip_bomb, dp.crear_corrupto):
        corpus.append((fn(especiales), False))
    (especiales / "virus.exe").write_bytes(b"MZ")
    corpus.append((especiales / "virus.exe", False))
    inst2 = gi.crear("Corpus", "1.21.1", TipoLoader.FABRIC)
    aciertos, falsos_pos, falsos_neg = 0, 0, 0
    for ruta, esperado in corpus:
        try:
            ok = ga.anadir(ruta, inst2).validacion.valido
        except AddOnDuplicadoError:
            ok = True
        aciertos += ok == esperado
        falsos_pos += ok and not esperado
        falsos_neg += (not ok) and esperado
    metricas["_clasificacion"] = {"archivos": len(corpus), "aciertos": aciertos,
                                  "tasa_error_pct": round(100 * (len(corpus) - aciertos) / len(corpus), 2),
                                  "falsos_positivos": falsos_pos, "falsos_negativos": falsos_neg}
    # Prueba de carga: instancia con muchos add-ons
    carga = {}
    inst3 = gi.crear("Carga", "1.21.1", TipoLoader.FABRIC)
    lote = tmp / "lote"
    lote.mkdir()
    agregados = 0
    t0 = time.perf_counter()
    for objetivo in (100, 300, 500):
        while agregados < objetivo:
            ga.anadir(dp.crear_mod(lote, f"m{agregados}", f"Mod {agregados}", "1", ">=1.21",
                                   archivo=f"m{agregados}.jar"), inst3)
            agregados += 1
        lista = medir(lambda: ga.listar(inst3), 20)
        t1 = time.perf_counter()
        integ = ga.verificar_integridad(inst3)
        carga[str(objetivo)] = {"listar_ms": lista["media_ms"],
                                "verificar_integridad_ms": round((time.perf_counter() - t1) * 1000, 1),
                                "ok": len(integ["ok"])}
    total = time.perf_counter() - t0
    carga["throughput_addons_por_s"] = round(500 / total, 1)
    metricas["_carga"] = carga
    Path("reportes").mkdir(exist_ok=True)
    Path("reportes/metricas.json").write_text(json.dumps(metricas, indent=2, ensure_ascii=False), encoding="utf-8")
    return metricas


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, ensure_ascii=False))
