"""Diálogos de cuenta, creación y configuración de instancias."""
from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from daiya.config import LIMITES
from daiya.core.modelos import Instancia, TipoLoader
from daiya.servicios.versiones_mc import CatalogoVersiones

ORIGEN = {"mojang": "lista oficial de Mojang", "guardada": "lista guardada (sin conexión)",
          "incluida": "lista incluida (sin conexión)"}


class DialogoNuevaInstancia(QDialog):
    """Formulario del CU-02 Crear instancia, con todas las versiones de Mojang."""

    def __init__(self, parent: QWidget | None = None, catalogo: CatalogoVersiones | None = None):
        super().__init__(parent)
        self.catalogo = catalogo or CatalogoVersiones(Path(tempfile.gettempdir()) / "daiya_sin_cache.json")
        self.setWindowTitle("Nueva instancia")
        self.setMinimumWidth(420)
        form = QFormLayout(self)
        self.nombre = QLineEdit()
        self.nombre.setMaxLength(LIMITES.largo_max_nombre)
        self.nombre.setPlaceholderText("Ej.: Survival con shaders")
        self.loader = QComboBox()
        self.loader.addItem("Fabric (permite mods y shaders)", TipoLoader.FABRIC)
        self.loader.addItem("Vanilla (sin mods)", TipoLoader.VANILLA)
        self.version = QComboBox()
        self.version.setMaxVisibleItems(15)
        self.chk_snapshots = QCheckBox("Incluir snapshots y pre-releases")
        self.chk_antiguas = QCheckBox("Incluir versiones antiguas (beta y alpha)")
        self.lbl_versiones = QLabel(objectName="subtitulo")
        self.lbl_versiones.setWordWrap(True)
        self.btn_actualizar = QPushButton("Actualizar lista")
        self.btn_actualizar.clicked.connect(self.actualizar_lista)
        for senal in (self.loader.currentIndexChanged, self.chk_snapshots.toggled, self.chk_antiguas.toggled):
            senal.connect(self.cargar_versiones)
        self.ram = QSpinBox()
        self.ram.setRange(LIMITES.ram_min_mb, LIMITES.ram_max_mb)
        self.ram.setSingleStep(512)
        self.ram.setValue(4096)
        self.ram.setSuffix(" MB")
        fila = QHBoxLayout()
        fila.addWidget(self.lbl_versiones, 1)
        fila.addWidget(self.btn_actualizar)
        form.addRow("Nombre", self.nombre)
        form.addRow("Loader", self.loader)
        form.addRow("Versión de Minecraft", self.version)
        form.addRow("", self.chk_snapshots)
        form.addRow("", self.chk_antiguas)
        form.addRow("", fila)
        form.addRow("Memoria RAM", self.ram)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.button(QDialogButtonBox.Ok).setText("Crear")
        botones.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        form.addRow(botones)
        self.cargar_versiones()

    def tipos_elegidos(self) -> set[str]:
        tipos = {"release"}
        if self.chk_snapshots.isChecked():
            tipos.add("snapshot")
        if self.chk_antiguas.isChecked():
            tipos |= {"old_beta", "old_alpha"}
        return tipos

    def cargar_versiones(self) -> None:
        """Rellena la lista según el loader y los filtros (Fabric solo muestra versiones que soporta)."""
        anterior = self.version.currentText()
        fabric = TipoLoader(self.loader.currentData()) is TipoLoader.FABRIC  # Qt devuelve el valor como texto
        ids = self.catalogo.listar(self.tipos_elegidos(), solo_fabric=fabric)
        self.version.blockSignals(True)
        self.version.clear()
        self.version.addItems(ids)
        if anterior in ids:
            self.version.setCurrentText(anterior)
        self.version.blockSignals(False)
        nota = " Fabric requiere 1.14 o superior." if fabric and self.chk_antiguas.isChecked() else ""
        self.lbl_versiones.setText(f"{len(ids)} versiones · {ORIGEN.get(self.catalogo.origen, '')}.{nota}")

    def actualizar_lista(self) -> None:
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ok = self.catalogo.actualizar()
        finally:
            QApplication.restoreOverrideCursor()
        self.cargar_versiones()
        if not ok:
            self.lbl_versiones.setText(self.lbl_versiones.text() + " No se pudo conectar con Mojang.")

    def datos(self) -> tuple[str, str, TipoLoader, int]:
        return self.nombre.text(), self.version.currentText(), self.loader.currentData(), self.ram.value()


class DialogoConfiguracion(QDialog):
    """Formulario del CU-08 Configurar memoria y Java."""

    def __init__(self, inst: Instancia, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"Configurar {inst.nombre}")
        form = QFormLayout(self)
        self.ram = QSpinBox()
        self.ram.setRange(LIMITES.ram_min_mb, LIMITES.ram_max_mb)
        self.ram.setSingleStep(512)
        self.ram.setSuffix(" MB")
        self.ram.setValue(inst.ram_mb)
        self.java = QLineEdit(inst.ruta_java or "")
        self.java.setPlaceholderText("Automático (Java incluido por Mojang)")
        elegir = QPushButton("Buscar…")
        elegir.clicked.connect(self._elegir_java)
        fila = QHBoxLayout()
        fila.addWidget(self.java)
        fila.addWidget(elegir)
        form.addRow("Memoria RAM", self.ram)
        form.addRow("Ruta de Java", fila)
        form.addRow(QLabel("Se recomienda entre 4096 y 8192 MB para instancias con shaders."))
        botones = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botones.button(QDialogButtonBox.Save).setText("Guardar")
        botones.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        form.addRow(botones)

    def _elegir_java(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(self, "Seleccionar ejecutable de Java")
        if ruta:
            self.java.setText(ruta)


class DialogoCuenta(QDialog):
    """CU-01: elegir entre la cuenta Microsoft y un perfil sin conexión."""

    AVISO = ("Perfil local para jugar en un jugador o en LAN. No entra a servidores oficiales ni a Realms. "
             "Daiya Launcher es un proyecto académico sin fines de lucro: si juegas habitualmente, "
             "compra Minecraft Java Edition para apoyar a sus creadores.")

    def __init__(self, parent: QWidget | None = None, nombre_guardado: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Cuenta")
        self.setMinimumWidth(440)
        self.eleccion: str | None = None
        capa = QVBoxLayout(self)
        capa.addWidget(QLabel("¿Cómo quieres jugar?", objectName="titulo"))
        self.btn_microsoft = QPushButton("Iniciar sesión con Microsoft (recomendado)", objectName="primario")
        self.btn_microsoft.clicked.connect(lambda: self._elegir("microsoft"))
        capa.addWidget(self.btn_microsoft)
        capa.addSpacing(12)
        capa.addWidget(QLabel("Jugar sin conexión", objectName="subtitulo"))
        self.nombre = QLineEdit(nombre_guardado)
        self.nombre.setPlaceholderText("Nombre de jugador (3 a 16 caracteres)")
        self.nombre.setMaxLength(16)
        # Solo letras, números y guion bajo: la validación también se repite en el servicio.
        self.nombre.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[A-Za-z0-9_]{0,16}$"), self))
        capa.addWidget(self.nombre)
        aviso = QLabel(self.AVISO)
        aviso.setWordWrap(True)
        aviso.setObjectName("subtitulo")
        capa.addWidget(aviso)
        self.btn_offline = QPushButton("Jugar sin conexión")
        self.btn_offline.clicked.connect(lambda: self._elegir("sin_conexion"))
        capa.addWidget(self.btn_offline)

    def _elegir(self, opcion: str) -> None:
        self.eleccion = opcion
        self.accept()
