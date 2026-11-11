"""Pruebas unitarias de la compatibilidad de versiones (RF-05)."""
import pytest

from daiya.core.versiones import a_tupla, describir, es_compatible


@pytest.mark.parametrize("version,req,esperado", [
    ("1.21.1", None, True),
    ("1.21.1", "*", True),
    ("1.21.1", "1.21.1", True),
    ("1.21.1", "1.20.1", False),
    ("1.21.1", ">=1.21", True),
    ("1.20.6", ">=1.21", False),
    ("1.21.1", "1.21.x", True),
    ("1.20.1", "1.21.x", False),
    ("1.21.1", "~1.21", True),
    ("1.22", "~1.21", False),
    ("1.21.1", ">=1.20 <1.21", False),
    ("1.20.4", ">=1.20 <1.21", True),
    ("1.21.1", ["1.20.1", "1.21.1"], True),
    ("1.21.4", ["1.20.1", "1.21.1"], False),
    ("1.21.1", "^1.20", True),
    ("1.21", "1.21", True),
    ("1.21.1", "<=1.21.1", True),
    ("1.21.1", ">1.21.1", False),
])
def test_es_compatible(version, req, esperado):
    assert es_compatible(version, req) is esperado


def test_a_tupla_ignora_sufijos():
    assert a_tupla("1.21.2-pre1") == (1, 21, 2)


def test_a_tupla_invalida():
    with pytest.raises(ValueError):
        a_tupla("abc")


def test_describir():
    assert describir(None) == "cualquier versión"
    assert describir(["1.20.1", "1.21"]) == "1.20.1 o 1.21"
