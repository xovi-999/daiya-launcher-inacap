"""Componentes reutilizables de la interfaz."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from daiya.core.modelos import RegistroAddOn


class ZonaArrastre(QFrame):
    """Zona que acepta archivos arrastrados desde el explorador (RNF-01)."""

    archivosSoltados = Signal(list)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("zona")
        self.setAcceptDrops(True)
        self.setMinimumHeight(96)
        capa = QVBoxLayout(self)
        texto = QLabel("⬇  Arrastra aquí tus mods (.jar), shaders o resource packs (.zip)")
        texto.setObjectName("zonaTexto")
        texto.setAlignment(Qt.AlignCenter)
        capa.addWidget(texto)

    def _marcar(self, activa: bool) -> None:
        self.setProperty("activa", "true" if activa else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, e):  # noqa: N802 (nombre impuesto por Qt)
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._marcar(True)

    def dragLeaveEvent(self, e):  # noqa: N802
        self._marcar(False)

    def dropEvent(self, e):  # noqa: N802
        self._marcar(False)
        rutas = [Path(u.toLocalFile()) for u in e.mimeData().urls() if u.isLocalFile()]
        if rutas:
            self.archivosSoltados.emit(rutas)


class TablaAddOns(QTableWidget):
    """Tabla con los add-ons de un tipo, con interruptor de activación."""

    cambioEstado = Signal(object, bool)

    COLUMNAS = ["Activo", "Nombre", "Versión", "Archivo"]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(0, len(self.COLUMNAS), parent)
        self.setHorizontalHeaderLabels(self.COLUMNAS)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        cab = self.horizontalHeader()
        cab.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        cab.setSectionResizeMode(1, QHeaderView.Stretch)
        cab.setSectionResizeMode(3, QHeaderView.Stretch)
        self.registros: list[RegistroAddOn] = []

    def cargar(self, registros: list[RegistroAddOn]) -> None:
        """Muestra ``registros`` en la tabla."""
        self.registros = registros
        self.clearContents()
        self.setRowCount(0)
        self.setRowCount(len(registros))
        for fila, reg in enumerate(registros):
            celda = QWidget(self)
            caja = QCheckBox()
            caja.setChecked(reg.activo)
            caja.toggled.connect(lambda v, r=reg: self.cambioEstado.emit(r, v))
            capa = QHBoxLayout(celda)
            capa.addWidget(caja)
            capa.setAlignment(Qt.AlignCenter)
            capa.setContentsMargins(0, 0, 0, 0)
            self.setCellWidget(fila, 0, celda)
            archivo = reg.archivo + ("" if reg.activo else ".disabled")
            for col, valor in enumerate([reg.nombre, reg.version or "—", archivo], 1):
                item = QTableWidgetItem(valor)
                if not reg.activo:
                    item.setForeground(Qt.gray)
                self.setItem(fila, col, item)

    def seleccionado(self) -> RegistroAddOn | None:
        fila = self.currentRow()
        return self.registros[fila] if 0 <= fila < len(self.registros) else None
