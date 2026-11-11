"""Fixtures compartidas por las pruebas."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from daiya.core.gestor_addons import GestorAddOns  # noqa: E402
from daiya.core.gestor_instancias import GestorInstancias  # noqa: E402
from daiya.core.modelos import TipoLoader  # noqa: E402
from daiya.datos.repositorio import Repositorio  # noqa: E402


@pytest.fixture
def repo(tmp_path):
    r = Repositorio(tmp_path / "daiya.db")
    yield r
    r.cerrar()


@pytest.fixture
def instancias(repo, tmp_path):
    return GestorInstancias(repo, tmp_path / "instancias")


@pytest.fixture
def gestor(repo):
    return GestorAddOns(repo)


@pytest.fixture
def inst_fabric(instancias):
    return instancias.crear("Survival 1.21.1", "1.21.1", TipoLoader.FABRIC, 4096)


@pytest.fixture
def inst_vanilla(instancias):
    return instancias.crear("Vanilla pura", "1.21.1", TipoLoader.VANILLA, 2048)


@pytest.fixture
def origen(tmp_path):
    carpeta = tmp_path / "descargas"
    carpeta.mkdir()
    return carpeta
