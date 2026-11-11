"""Diálogo de búsqueda e instalación de mods desde Modrinth (CU-09)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from daiya.core.modelos import Instancia
from daiya.servicios.modrinth import ClienteModrinth, ErrorModrinth


class DialogoModrinth(QDialog):
    """Busca mods compatibles con la instancia y devuelve el proyecto elegido."""

    def __init__(self, cliente: ClienteModrinth, inst: Instancia, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"Buscar mods para {inst.nombre} ({inst.version_minecraft})")
        self.resize(640, 420)
        self._cliente, self._inst = cliente, inst
        self.resultados: list[dict] = []
        self.proyecto_elegido: str | None = None
        capa = QVBoxLayout(self)
        fila = QHBoxLayout()
        self.texto = QLineEdit(placeholderText="Ej.: sodium, minimap, shaders")
        self.texto.setMaxLength(100)
        self.texto.returnPressed.connect(self.buscar)
        boton = QPushButton("Buscar")
        boton.clicked.connect(self.buscar)
        fila.addWidget(self.texto, 1)
        fila.addWidget(boton)
        capa.addLayout(fila)
        self.estado = QLabel(f"Solo se muestran mods para Fabric y Minecraft {inst.version_minecraft}.",
                             objectName="subtitulo")
        capa.addWidget(self.estado)
        self.tabla = QTableWidget(0, 3)
        self.tabla.setHorizontalHeaderLabels(["Mod", "Descripción", "Descargas"])
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        capa.addWidget(self.tabla, 1)
        instalar = QPushButton("Instalar seleccionado", objectName="primario")
        instalar.clicked.connect(self._instalar)
        capa.addWidget(instalar)

    def buscar(self) -> None:
        try:
            self.mostrar(self._cliente.buscar(self.texto.text(), self._inst.version_minecraft))
        except ErrorModrinth as exc:
            self.estado.setText(str(exc))

    def mostrar(self, resultados: list[dict]) -> None:
        self.resultados = resultados
        self.tabla.setRowCount(len(resultados))
        for fila, r in enumerate(resultados):
            for col, valor in enumerate([r["nombre"], r["descripcion"], f"{r['descargas']:,}".replace(",", ".")]):
                self.tabla.setItem(fila, col, QTableWidgetItem(str(valor)))
        self.estado.setText(f"{len(resultados)} resultados compatibles.")

    def _instalar(self) -> None:
        fila = self.tabla.currentRow()
        if 0 <= fila < len(self.resultados):
            self.proyecto_elegido = self.resultados[fila]["slug"] or self.resultados[fila]["id"]
            self.accept()
