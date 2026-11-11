"""Ventana principal de Daiya Launcher."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from daiya import APP_NAME, __version__
from daiya.core.gestor_addons import AddOnDuplicadoError
from daiya.core.gestor_instancias import DatoInvalidoError
from daiya.core.modelos import Instancia, TipoAddOn
from daiya.servicios.cuenta import ErrorSesion
from daiya.servicios.instalador import PROYECTO_IRIS, instalar_desde_modrinth
from daiya.ui.contexto import Contexto
from daiya.ui.dialogo_modrinth import DialogoModrinth
from daiya.ui.dialogos import DialogoConfiguracion, DialogoCuenta, DialogoNuevaInstancia
from daiya.ui.widgets import TablaAddOns, ZonaArrastre

log = logging.getLogger("daiya.ui")


class HiloLanzamiento(QThread):
    """Prepara e inicia el juego fuera del hilo de la interfaz (evita congelarla)."""

    linea = Signal(str)
    terminado = Signal(int)

    def __init__(self, ctx: Contexto, inst: Instancia):
        super().__init__()
        self.ctx, self.inst = ctx, inst

    def run(self) -> None:
        try:
            version = self.ctx.lanzamiento.preparar(self.inst, progreso=lambda t: self.linea.emit(f"[Daiya] {t}"))
            cmd = self.ctx.lanzamiento.construir_comando(self.inst, version, self.ctx.cuenta.sesion)
            proc = self.ctx.lanzamiento.iniciar(cmd, self.inst.ruta)
            for texto in proc.stdout:
                self.linea.emit(texto.rstrip())
            self.terminado.emit(proc.wait())
        except Exception as exc:  # se informa al usuario sin detener la aplicación
            self.linea.emit(f"[Daiya] Error al lanzar: {exc}")
            self.terminado.emit(-1)


class VentanaPrincipal(QMainWindow):
    """Lista de instancias a la izquierda y detalle de la instancia a la derecha."""

    TIPOS = [(TipoAddOn.MOD, "Mods"), (TipoAddOn.SHADER, "Shaders"), (TipoAddOn.RESOURCE_PACK, "Resource packs")]

    def __init__(self, ctx: Contexto):
        super().__init__()
        self.ctx = ctx
        self.instancia: Instancia | None = None
        self._hilo: HiloLanzamiento | None = None
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1100, 700)
        self._construir()
        self.recargar_instancias()

    # ------------------------------------------------------------- interfaz
    def _construir(self) -> None:
        raiz = QWidget(objectName="fondo")
        capa = QHBoxLayout(raiz)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)

        lateral = QWidget(objectName="lateral")
        lateral.setFixedWidth(250)
        cl = QVBoxLayout(lateral)
        cl.addWidget(QLabel("◆ Daiya Launcher", objectName="logo"))
        self.lbl_cuenta = QLabel("Sesión no iniciada", objectName="cuenta")
        self.btn_sesion = QPushButton("Iniciar sesión")
        self.btn_sesion.clicked.connect(self.iniciar_sesion)
        cl.addWidget(self.lbl_cuenta)
        cl.addWidget(self.btn_sesion)
        cl.addSpacing(10)
        cl.addWidget(QLabel("INSTANCIAS", objectName="subtitulo"))
        self.lista = QListWidget()
        self.lista.currentItemChanged.connect(self._al_elegir)
        cl.addWidget(self.lista, 1)
        nueva = QPushButton("+ Nueva instancia")
        nueva.clicked.connect(self.nueva_instancia)
        cl.addWidget(nueva)
        capa.addWidget(lateral)

        panel = QWidget()
        cp = QVBoxLayout(panel)
        cp.setContentsMargins(24, 20, 24, 20)
        cabecera = QHBoxLayout()
        textos = QVBoxLayout()
        self.lbl_titulo = QLabel("Crea tu primera instancia", objectName="titulo")
        self.lbl_detalle = QLabel("", objectName="subtitulo")
        textos.addWidget(self.lbl_titulo)
        textos.addWidget(self.lbl_detalle)
        cabecera.addLayout(textos, 1)
        self.btn_config = QPushButton("Configurar")
        self.btn_config.clicked.connect(self.configurar)
        self.btn_anadir = QPushButton("Añadir add-on…")
        self.btn_anadir.clicked.connect(self.elegir_archivos)
        self.btn_jugar = QPushButton("▶  Jugar", objectName="primario")
        self.btn_jugar.clicked.connect(self.jugar)
        for b in (self.btn_config, self.btn_anadir, self.btn_jugar):
            cabecera.addWidget(b)
        cp.addLayout(cabecera)

        self.banner = QLabel(objectName="banner")
        self.banner.setWordWrap(True)
        self.banner.hide()
        fila_banner = QHBoxLayout()
        fila_banner.addWidget(self.banner, 1)
        self.btn_iris = QPushButton("Instalar Iris desde Modrinth")
        self.btn_iris.clicked.connect(lambda: self.instalar_desde_modrinth(PROYECTO_IRIS))
        self.btn_iris.hide()
        fila_banner.addWidget(self.btn_iris)
        cp.addLayout(fila_banner)
        self.zona = ZonaArrastre()
        self.zona.archivosSoltados.connect(self.anadir_archivos)
        cp.addWidget(self.zona)

        self.pestanas = QTabWidget()
        self.tablas: dict[TipoAddOn, TablaAddOns] = {}
        for tipo, titulo in self.TIPOS:
            tabla = TablaAddOns()
            tabla.cambioEstado.connect(self._cambiar_estado)
            self.tablas[tipo] = tabla
            self.pestanas.addTab(tabla, titulo)
        self.registro = QPlainTextEdit(readOnly=True)
        self.pestanas.addTab(self.registro, "Registro")
        cp.addWidget(self.pestanas, 1)
        acciones = QHBoxLayout()
        self.btn_modrinth = QPushButton("Buscar en Modrinth…")
        self.btn_modrinth.clicked.connect(self.buscar_modrinth)
        self.btn_integridad = QPushButton("Verificar integridad")
        self.btn_integridad.clicked.connect(self.verificar_integridad)
        acciones.addWidget(self.btn_modrinth)
        acciones.addWidget(self.btn_integridad)
        acciones.addStretch(1)
        eliminar = QPushButton("Eliminar seleccionado")
        eliminar.clicked.connect(self.eliminar_seleccionado)
        acciones.addWidget(eliminar)
        cp.addLayout(acciones)
        capa.addWidget(panel, 1)
        self.setCentralWidget(raiz)
        self._habilitar(False)

    def _habilitar(self, si: bool) -> None:
        for w in (self.btn_config, self.btn_anadir, self.btn_jugar, self.zona, self.pestanas,
                  self.btn_modrinth, self.btn_integridad):
            w.setEnabled(si)

    def mostrar_mensaje(self, texto: str, nivel: str = "ok") -> None:
        """Muestra un aviso coloreado (ok, aviso o error) sobre la zona de arrastre."""
        self.banner.setText(texto)
        self.banner.setProperty("nivel", nivel)
        self.banner.style().unpolish(self.banner)
        self.banner.style().polish(self.banner)
        self.banner.show()
        self.btn_iris.setVisible("Iris no está instalado" in texto)

    # ------------------------------------------------------------ instancias
    def recargar_instancias(self, seleccionar: int | None = None) -> None:
        self.lista.clear()
        for inst in self.ctx.instancias.listar():
            item = QListWidgetItem(f"{inst.nombre}\n{inst.version_minecraft} · {inst.loader.value.capitalize()}")
            item.setData(256, inst.id)
            self.lista.addItem(item)
            if inst.id == seleccionar or (seleccionar is None and self.lista.count() == 1):
                self.lista.setCurrentItem(item)

    def _al_elegir(self, item: QListWidgetItem | None, _=None) -> None:
        self.instancia = self.ctx.repo.obtener_instancia(item.data(256)) if item else None
        self.banner.hide()
        self.btn_iris.hide()
        self.refrescar()

    def refrescar(self) -> None:
        inst = self.instancia
        self._habilitar(inst is not None)
        if not inst:
            return
        self.lbl_titulo.setText(inst.nombre)
        self.lbl_detalle.setText(f"Minecraft {inst.version_minecraft} · {inst.loader.value.capitalize()} · "
                                 f"{inst.ram_mb} MB de RAM")
        for tipo, tabla in self.tablas.items():
            regs = self.ctx.addons.listar(inst, tipo)
            tabla.cargar(regs)
            idx = [t for t, _ in self.TIPOS].index(tipo)
            self.pestanas.setTabText(idx, f"{dict(self.TIPOS)[tipo]} ({len(regs)})")

    def nueva_instancia(self) -> None:
        dlg = DialogoNuevaInstancia(self, self.ctx.versiones)
        if dlg.exec():
            try:
                inst = self.ctx.instancias.crear(*dlg.datos())
            except DatoInvalidoError as exc:
                QMessageBox.warning(self, "Datos no válidos", str(exc))
                return
            self.recargar_instancias(inst.id)
            self.mostrar_mensaje(f"Instancia «{inst.nombre}» creada. Los archivos del juego se descargarán al jugar.")

    def configurar(self) -> None:
        dlg = DialogoConfiguracion(self.instancia, self)
        if dlg.exec():
            try:
                self.ctx.instancias.configurar(self.instancia, dlg.ram.value(), dlg.java.text().strip() or None)
                self.mostrar_mensaje("Configuración guardada.")
            except DatoInvalidoError as exc:
                self.mostrar_mensaje(str(exc), "error")
            self.refrescar()

    # --------------------------------------------------------------- add-ons
    def elegir_archivos(self) -> None:
        rutas, _ = QFileDialog.getOpenFileNames(self, "Seleccionar add-ons", "", "Add-ons (*.jar *.zip)")
        if rutas:
            self.anadir_archivos([Path(r) for r in rutas])

    def anadir_archivos(self, rutas: list[Path]) -> None:
        """Procesa los archivos soltados en la zona de arrastre (CU-03, CU-04, CU-05)."""
        mensajes, nivel = [], "ok"
        for ruta in rutas:
            try:
                res = self.ctx.addons.anadir(ruta, self.instancia)
            except AddOnDuplicadoError as dup:
                resp = QMessageBox.question(self, "Add-on repetido",
                                            f"{dup}\n¿Quieres reemplazarlo por {ruta.name}?")
                if resp != QMessageBox.Yes:
                    continue
                res = self.ctx.addons.anadir(ruta, self.instancia, reemplazar=True)
            if not res.validacion.valido:
                mensajes.append(f"✖ {ruta.name}: {' '.join(res.validacion.errores)}")
                nivel = "error"
                continue
            nombre = res.registro.nombre
            mensajes.append(f"✔ {nombre} añadido a {res.registro.tipo.carpeta}.")
            for aviso in res.validacion.advertencias:
                mensajes.append(f"⚠ {nombre}: {aviso}")
                nivel = "aviso" if nivel == "ok" else nivel
        if mensajes:
            self.mostrar_mensaje("\n".join(mensajes), nivel)
        self.refrescar()

    def buscar_modrinth(self) -> None:
        """CU-09: busca mods compatibles y los instala con validación completa."""
        dlg = DialogoModrinth(self.ctx.modrinth, self.instancia, self)
        if dlg.exec() and dlg.proyecto_elegido:
            self.instalar_desde_modrinth(dlg.proyecto_elegido)

    def instalar_desde_modrinth(self, proyecto: str) -> None:
        """Descarga un mod verificado (SHA-512) y lo valida igual que un archivo arrastrado."""
        res = instalar_desde_modrinth(self.ctx.modrinth, self.ctx.addons, self.instancia, proyecto)
        if res.validacion.valido and res.registro:
            avisos = "".join(f"\n⚠ {a}" for a in res.validacion.advertencias)
            self.mostrar_mensaje(f"✔ {res.registro.nombre} {res.registro.version} instalado desde Modrinth "
                                 f"(hash verificado).{avisos}", "aviso" if avisos else "ok")
        else:
            self.mostrar_mensaje("✖ " + " ".join(res.validacion.errores), "error")
        self.refrescar()

    def verificar_integridad(self) -> None:
        """Compara el hash registrado de cada add-on con el archivo en disco."""
        r = self.ctx.addons.verificar_integridad(self.instancia)
        if not r["modificados"] and not r["faltantes"]:
            self.mostrar_mensaje(f"✔ Integridad verificada: {len(r['ok'])} add-ons sin cambios.")
            return
        lineas = [f"✖ {x.nombre}: el archivo fue modificado fuera del launcher." for x in r["modificados"]]
        lineas += [f"⚠ {x.nombre}: el archivo ya no existe en la carpeta." for x in r["faltantes"]]
        self.mostrar_mensaje("\n".join(lineas), "error" if r["modificados"] else "aviso")

    def _cambiar_estado(self, reg, activo: bool) -> None:
        self.ctx.addons.cambiar_estado(self.instancia, reg, activo)
        self.mostrar_mensaje(f"{reg.nombre} {'activado' if activo else 'desactivado'}.")
        self.refrescar()

    def eliminar_seleccionado(self) -> None:
        tabla = self.pestanas.currentWidget()
        if not isinstance(tabla, TablaAddOns) or not (reg := tabla.seleccionado()):
            return
        pregunta = f"¿Eliminar {reg.nombre}? Se moverá a la papelera de la instancia."
        if QMessageBox.question(self, "Eliminar", pregunta) == QMessageBox.Yes:
            self.ctx.addons.eliminar(self.instancia, reg)
            self.refrescar()

    # ---------------------------------------------------- sesión y juego
    def iniciar_sesion(self) -> None:
        """CU-01: cierra la sesión activa o deja elegir entre Microsoft y sin conexión."""
        if self.ctx.cuenta.sesion is not None:
            self.ctx.cuenta.cerrar_sesion()
            self.actualizar_cuenta(None)
            return
        dialogo = DialogoCuenta(self, self.ctx.repo.obtener_config("perfil_sin_conexion", "") or "")
        if dialogo.exec() != DialogoCuenta.Accepted:
            return
        if dialogo.eleccion == "sin_conexion":
            self.usar_perfil_sin_conexion(dialogo.nombre.text())
        else:
            self._iniciar_sesion_microsoft()

    def _iniciar_sesion_microsoft(self) -> None:
        """Abre la página oficial de Microsoft y completa el flujo OAuth con PKCE."""
        try:
            QDesktopServices.openUrl(QUrl(self.ctx.cuenta.url_inicio_sesion()))
            url, ok = QInputDialog.getText(
                self, "Iniciar sesión", "Después de iniciar sesión, pega aquí la dirección a la que fuiste redirigido:")
            if ok and url:
                sesion = self.ctx.cuenta.completar_inicio_sesion(url.strip())
                self.actualizar_cuenta(sesion.nombre_jugador)
        except ErrorSesion as exc:
            self.mostrar_mensaje(str(exc), "error")

    def usar_perfil_sin_conexion(self, nombre: str) -> bool:
        """Activa un perfil local validado y recuerda solo el nombre (no hay secretos que guardar)."""
        try:
            sesion = self.ctx.cuenta.iniciar_sin_conexion(nombre)
        except ErrorSesion as exc:
            self.mostrar_mensaje(str(exc), "error")
            return False
        self.ctx.repo.guardar_config("perfil_sin_conexion", sesion.nombre_jugador)
        self.actualizar_cuenta(sesion.nombre_jugador, sin_conexion=True)
        self.mostrar_mensaje(f"Perfil sin conexión «{sesion.nombre_jugador}» listo: un jugador y LAN.", "ok")
        return True

    def actualizar_cuenta(self, nombre: str | None, sin_conexion: bool = False) -> None:
        sufijo = " (sin conexión)" if sin_conexion else ""
        self.lbl_cuenta.setText(f"Jugador: {nombre}{sufijo}" if nombre else "Sesión no iniciada")
        self.btn_sesion.setText("Cerrar sesión" if nombre else "Iniciar sesión")

    def jugar(self) -> None:
        """CU-07: lanza la instancia en un hilo y muestra el registro en vivo."""
        if self.ctx.cuenta.sesion is None and self.ctx.cuenta.renovar() is None:
            self.mostrar_mensaje("Debes iniciar sesión con Microsoft o crear un perfil sin conexión antes de jugar.",
                                 "aviso")
            return
        self.pestanas.setCurrentWidget(self.registro)
        self.registro.clear()
        self._hilo = HiloLanzamiento(self.ctx, self.instancia)
        self._hilo.linea.connect(self.registro.appendPlainText)
        self._hilo.terminado.connect(self._fin_juego)
        self.btn_jugar.setEnabled(False)
        self._hilo.start()

    def _fin_juego(self, codigo: int) -> None:
        self.btn_jugar.setEnabled(True)
        if codigo != 0:
            mods = self.ctx.addons.listar(self.instancia)
            ultimo = mods[-1].nombre if mods else None
            sugerencia = self.ctx.lanzamiento.diagnosticar(self.registro.toPlainText().splitlines(), ultimo)
            self.mostrar_mensaje(sugerencia or "El juego terminó con un código de error.", "error")
