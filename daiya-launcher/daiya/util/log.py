"""Configuración del registro de eventos (logging) con redacción de secretos.

Los tokens de acceso nunca deben quedar escritos en los archivos de log
(OWASP A09:2025 y Ley 21.719 sobre protección de datos personales).
"""
from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_PATRONES_SECRETOS = [
    (re.compile(r"(access_token|refresh_token|accessToken|code_verifier|code)=([^&\s]+)", re.I), r"\1=***"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.I), r"\1***"),
    (re.compile(r"(--accessToken\s+)\S+"), r"\1***"),
]


class FiltroRedaccion(logging.Filter):
    """Reemplaza por ``***`` cualquier token presente en los mensajes."""

    def filter(self, record: logging.LogRecord) -> bool:
        mensaje = record.getMessage()
        for patron, reemplazo in _PATRONES_SECRETOS:
            mensaje = patron.sub(reemplazo, mensaje)
        record.msg, record.args = mensaje, ()
        return True


def configurar_log(carpeta: Path, nivel: int = logging.INFO) -> logging.Logger:
    """Crea el logger ``daiya`` con salida rotativa en ``carpeta/daiya.log``."""
    carpeta.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("daiya")
    logger.setLevel(nivel)
    if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        manejador = RotatingFileHandler(carpeta / "daiya.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        manejador.addFilter(FiltroRedaccion())
        logger.addHandler(manejador)
    return logger
