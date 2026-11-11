"""Acceso a datos sobre SQLite.

Todas las consultas usan parámetros enlazados (``?``); nunca se concatena
texto del usuario en SQL (OWASP A05:2025, Injection).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from daiya.core.modelos import Instancia, RegistroAddOn, TipoAddOn, TipoLoader

_ESQUEMA = Path(__file__).with_name("esquema.sql")


class Repositorio:
    """Repositorio de instancias, add-ons y configuración."""

    def __init__(self, ruta_db: Path | str):
        self._con = sqlite3.connect(str(ruta_db))
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA foreign_keys = ON")
        self._con.executescript(_ESQUEMA.read_text(encoding="utf-8"))
        self._con.commit()

    def respaldar(self, carpeta: Path, conservar: int = 5) -> Path:
        """Crea una copia consistente de la base de datos y conserva las ``conservar`` más recientes.

        Usa la API de respaldo en línea de SQLite, que es segura aunque la base esté abierta
        (control de disponibilidad, ISO/IEC 27002:2022 8.13).
        """
        carpeta = Path(carpeta)
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / f"daiya_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
        with sqlite3.connect(str(destino)) as copia:
            self._con.backup(copia)
        copia.close()
        for antiguo in sorted(carpeta.glob("daiya_*.db"))[:-conservar]:
            antiguo.unlink()
        return destino

    def cerrar(self) -> None:
        """Cierra la conexión con la base de datos."""
        self._con.close()

    # ------------------------------------------------------------ instancias
    def guardar_instancia(self, inst: Instancia) -> Instancia:
        """Inserta o actualiza ``inst`` y devuelve la instancia con su id."""
        datos = (inst.nombre, inst.version_minecraft, inst.loader.value, inst.version_loader,
                 inst.ram_mb, inst.ruta_java, str(inst.ruta),
                 inst.ultima_vez.isoformat() if inst.ultima_vez else None)
        with self._con:
            if inst.id is None:
                cur = self._con.execute(
                    "INSERT INTO instancia (nombre, version_minecraft, loader, version_loader, ram_mb,"
                    " ruta_java, ruta, ultima_vez) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", datos)
                inst.id = cur.lastrowid
            else:
                self._con.execute(
                    "UPDATE instancia SET nombre=?, version_minecraft=?, loader=?, version_loader=?,"
                    " ram_mb=?, ruta_java=?, ruta=?, ultima_vez=? WHERE id=?", (*datos, inst.id))
        return inst

    def listar_instancias(self) -> list[Instancia]:
        """Devuelve las instancias ordenadas por último uso y nombre."""
        filas = self._con.execute(
            "SELECT * FROM instancia ORDER BY ultima_vez IS NULL, ultima_vez DESC, nombre").fetchall()
        return [self._a_instancia(f) for f in filas]

    def obtener_instancia(self, instancia_id: int) -> Instancia | None:
        fila = self._con.execute("SELECT * FROM instancia WHERE id = ?", (instancia_id,)).fetchone()
        return self._a_instancia(fila) if fila else None

    def existe_nombre(self, nombre: str) -> bool:
        return self._con.execute("SELECT 1 FROM instancia WHERE nombre = ? COLLATE NOCASE",
                                 (nombre,)).fetchone() is not None

    def eliminar_instancia(self, instancia_id: int) -> None:
        with self._con:
            self._con.execute("DELETE FROM instancia WHERE id = ?", (instancia_id,))

    @staticmethod
    def _a_instancia(f: sqlite3.Row) -> Instancia:
        return Instancia(
            id=f["id"], nombre=f["nombre"], version_minecraft=f["version_minecraft"],
            loader=TipoLoader(f["loader"]), version_loader=f["version_loader"], ram_mb=f["ram_mb"],
            ruta_java=f["ruta_java"], ruta=Path(f["ruta"]),
            ultima_vez=datetime.fromisoformat(f["ultima_vez"]) if f["ultima_vez"] else None)

    # ---------------------------------------------------------------- addons
    def guardar_addon(self, reg: RegistroAddOn) -> RegistroAddOn:
        """Inserta o actualiza un add-on."""
        datos = (reg.instancia_id, reg.tipo.value, reg.nombre, reg.version, reg.id_externo,
                 reg.archivo, reg.hash_sha1, int(reg.activo))
        with self._con:
            if reg.id is None:
                cur = self._con.execute(
                    "INSERT INTO addon (instancia_id, tipo, nombre, version, id_externo, archivo,"
                    " hash_sha1, activo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", datos)
                reg.id = cur.lastrowid
            else:
                self._con.execute(
                    "UPDATE addon SET instancia_id=?, tipo=?, nombre=?, version=?, id_externo=?,"
                    " archivo=?, hash_sha1=?, activo=? WHERE id=?", (*datos, reg.id))
        return reg

    def listar_addons(self, instancia_id: int, tipo: TipoAddOn | None = None) -> list[RegistroAddOn]:
        """Lista los add-ons de una instancia, opcionalmente filtrados por tipo."""
        if tipo is None:
            filas = self._con.execute("SELECT * FROM addon WHERE instancia_id = ? ORDER BY nombre",
                                      (instancia_id,)).fetchall()
        else:
            filas = self._con.execute(
                "SELECT * FROM addon WHERE instancia_id = ? AND tipo = ? ORDER BY nombre",
                (instancia_id, tipo.value)).fetchall()
        return [self._a_addon(f) for f in filas]

    def buscar_duplicado(self, instancia_id: int, id_externo: str, hash_sha1: str) -> RegistroAddOn | None:
        """Busca un add-on con el mismo identificador externo o el mismo hash."""
        fila = self._con.execute(
            "SELECT * FROM addon WHERE instancia_id = ? AND ((id_externo <> '' AND id_externo = ?)"
            " OR hash_sha1 = ?) LIMIT 1", (instancia_id, id_externo, hash_sha1)).fetchone()
        return self._a_addon(fila) if fila else None

    def eliminar_addon(self, addon_id: int) -> None:
        with self._con:
            self._con.execute("DELETE FROM addon WHERE id = ?", (addon_id,))

    @staticmethod
    def _a_addon(f: sqlite3.Row) -> RegistroAddOn:
        return RegistroAddOn(id=f["id"], instancia_id=f["instancia_id"], tipo=TipoAddOn(f["tipo"]),
                             nombre=f["nombre"], version=f["version"], id_externo=f["id_externo"],
                             archivo=f["archivo"], hash_sha1=f["hash_sha1"], activo=bool(f["activo"]))

    # --------------------------------------------------------- configuración
    def obtener_config(self, clave: str, por_defecto: str | None = None) -> str | None:
        fila = self._con.execute("SELECT valor FROM configuracion WHERE clave = ?", (clave,)).fetchone()
        return fila["valor"] if fila else por_defecto

    def guardar_config(self, clave: str, valor: str) -> None:
        with self._con:
            self._con.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?)"
                              " ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor", (clave, valor))
