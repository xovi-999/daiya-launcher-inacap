"""Genera los gráficos de métricas del informe a partir de reportes/*.json y *.xml."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

AZUL, TEXTO, SECUNDARIO, GRILLA = "#2a78d6", "#0b0b0b", "#52514e", "#e4e3df"


def _estilo(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRILLA)
    ax.tick_params(colors=SECUNDARIO, length=0, labelsize=8)
    ax.xaxis.grid(True, color=GRILLA, linewidth=0.8)
    ax.set_axisbelow(True)


def tiempos(salida: Path) -> None:
    m = json.loads(Path("reportes/metricas.json").read_text(encoding="utf-8"))
    datos = [(k, v["media_ms"]) for k, v in m.items() if not k.startswith("_") and "ventana" not in k]
    datos.sort(key=lambda d: d[1])
    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=200)
    ys = range(len(datos))
    ax.barh(ys, [d[1] for d in datos], height=0.55, color=AZUL)
    for y, (_, val) in zip(ys, datos):
        ax.text(val + 0.8, y, f"{val:.2f} ms", va="center", fontsize=8, color=TEXTO)
    ax.set_yticks(list(ys), [d[0] for d in datos], fontsize=8, color=TEXTO)
    ax.set_xlabel("Tiempo medio por operación (ms) · meta RNF-02: < 1.000 ms", fontsize=8, color=SECUNDARIO)
    ax.set_xlim(0, max(d[1] for d in datos) * 1.25)
    _estilo(ax)
    ax.set_title("Tiempo de respuesta de las operaciones principales", fontsize=10, color=TEXTO, loc="left")
    fig.tight_layout()
    fig.savefig(salida / "grafico_tiempos.png")


def cobertura(salida: Path) -> None:
    raiz = ET.parse("reportes/cobertura.xml").getroot()
    datos = []
    for paquete in raiz.iter("package"):
        nombre = paquete.get("name").replace("daiya.", "")
        nombre = "config (raíz)" if nombre in (".", "daiya", "") else nombre
        datos.append((nombre, float(paquete.get("line-rate")) * 100))
    datos.sort(key=lambda d: d[1])
    total = float(raiz.get("line-rate")) * 100
    fig, ax = plt.subplots(figsize=(8, 2.8), dpi=200)
    ys = range(len(datos))
    ax.barh(ys, [d[1] for d in datos], height=0.55, color=AZUL)
    for y, (_, val) in zip(ys, datos):
        ax.text(val + 1, y, f"{val:.0f} %", va="center", fontsize=8, color=TEXTO)
    ax.axvline(75, color=SECUNDARIO, linestyle=(0, (4, 3)), linewidth=1)
    ax.text(75.5, len(datos) - 0.45, "umbral CI 75 %", fontsize=7, color=SECUNDARIO)
    ax.set_yticks(list(ys), [d[0] for d in datos], fontsize=8, color=TEXTO)
    ax.set_xlim(0, 110)
    ax.set_xlabel(f"Cobertura de líneas por paquete (%) · total {total:.0f} %", fontsize=8, color=SECUNDARIO)
    _estilo(ax)
    ax.set_title("Cobertura de pruebas por paquete", fontsize=10, color=TEXTO, loc="left")
    fig.tight_layout()
    fig.savefig(salida / "grafico_cobertura.png")


if __name__ == "__main__":
    out = Path("reportes")
    tiempos(out)
    cobertura(out)
