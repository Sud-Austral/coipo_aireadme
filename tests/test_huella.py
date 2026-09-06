#!/usr/bin/env python3
"""
Huella de la evidencia: no regenerar lo que no cambio.

Por que estos tests importan
----------------------------

El corte por huella es la unica pieza del sistema cuyo fallo es SILENCIOSO.
Si la huella se calcula mal y siempre coincide, el generador deja de
documentar toda la flota y en la interfaz de Actions no se ve ninguna
diferencia: `sys.exit(0)` se ve igual que un exito.

Por eso se prueban las dos direcciones: que no oscile cuando no debe, y que
si detecte los cambios que importan.

    python -m pytest tests/test_huella.py -v
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from readme3_fingerprint import (   # noqa: E402
    compute,
    leer,
    quitar,
    sellar,
)


EVIDENCIA = {
    "metadata": {
        "repository": "demo",
        "generated_at": "2026-09-06T10:00:00",
        "file_count": 42,
    },
    "technologies": {
        "React": {
            "provenance": "declared",
            "evidence": [{"file": "package.json", "line": 22}],
        },
        "Django": {
            "provenance": "mentioned",
            "evidence": [{"file": "notas.md", "line": 8}],
        },
    },
    "manifests": [
        {
            "path": "package.json",
            "kind": "npm",
            "third_party": False,
            "dependencies": [
                {"name": "react", "version": "^18.3.1", "line": 22},
            ],
            "scripts": [{"name": "build", "command": "vite build"}],
        }
    ],
    "npm_scripts": [{"name": "build", "command": "vite build"}],
    "api": [{"method": "GET", "path": "/api/x", "file": "app.py", "line": 10}],
    "database_tables": [{"value": "users", "file": "db.sql", "line": 3}],
    "environment_variables": [{"value": "DATABASE_URL", "line": 5}],
    "important_files": ["package.json", "README.md"],
    "analysis": {"app.py": {"python": {"imports": [{"value": "os"}]}}},
    "files": [{"path": "app.py"}],
}


def _con(cambios: dict) -> dict:
    copia = copy.deepcopy(EVIDENCIA)
    copia.update(cambios)
    return copia


# ============================================================
# LO QUE NO DEBE MOVER LA HUELLA
# ============================================================

def test_la_hora_de_generacion_no_mueve_la_huella():
    otra = copy.deepcopy(EVIDENCIA)
    otra["metadata"]["generated_at"] = "2027-01-01T00:00:00"

    assert compute(otra) == compute(EVIDENCIA)


def test_los_numeros_de_linea_no_mueven_la_huella():
    """Editar cualquier archivo desplaza lineas sin cambiar el software."""

    otra = copy.deepcopy(EVIDENCIA)
    otra["api"][0]["line"] = 999
    otra["database_tables"][0]["line"] = 999
    otra["environment_variables"][0]["line"] = 999
    otra["technologies"]["React"]["evidence"][0]["line"] = 999

    assert compute(otra) == compute(EVIDENCIA)


def test_el_detalle_del_ast_no_mueve_la_huella():
    otra = copy.deepcopy(EVIDENCIA)
    otra["analysis"] = {"otro.py": {"python": {"imports": []}}}
    otra["files"] = []

    assert compute(otra) == compute(EVIDENCIA)


def test_lo_solo_mencionado_no_mueve_la_huella():
    """
    `mentioned` sale de texto libre, incluido el propio README. Si entrara,
    el README generado moveria su propia huella y no convergeria nunca.
    """

    otra = copy.deepcopy(EVIDENCIA)
    otra["technologies"]["MongoDB"] = {
        "provenance": "mentioned",
        "evidence": [{"file": "README.md", "line": 1}],
    }

    assert compute(otra) == compute(EVIDENCIA)


def test_el_orden_no_mueve_la_huella():
    otra = copy.deepcopy(EVIDENCIA)
    otra["important_files"] = ["README.md", "package.json"]

    assert compute(otra) == compute(EVIDENCIA)


# ============================================================
# LO QUE SI DEBE MOVERLA
# ============================================================

def test_una_dependencia_nueva_mueve_la_huella():
    otra = copy.deepcopy(EVIDENCIA)
    otra["manifests"][0]["dependencies"].append(
        {"name": "leaflet", "version": "^1.9.4", "line": 30}
    )

    assert compute(otra) != compute(EVIDENCIA)


def test_un_cambio_de_version_mueve_la_huella():
    otra = copy.deepcopy(EVIDENCIA)
    otra["manifests"][0]["dependencies"][0]["version"] = "^19.0.0"

    assert compute(otra) != compute(EVIDENCIA)


def test_un_endpoint_nuevo_mueve_la_huella():
    otra = copy.deepcopy(EVIDENCIA)
    otra["api"].append(
        {"method": "POST", "path": "/api/y", "file": "app.py", "line": 20}
    )

    assert compute(otra) != compute(EVIDENCIA)


def test_una_tabla_nueva_mueve_la_huella():
    otra = copy.deepcopy(EVIDENCIA)
    otra["database_tables"].append(
        {"value": "audit_logs", "file": "db.sql", "line": 9}
    )

    assert compute(otra) != compute(EVIDENCIA)


def test_una_tecnologia_que_pasa_a_declarada_mueve_la_huella():
    """Que Django deje de estar solo mencionado ES un cambio real."""

    otra = copy.deepcopy(EVIDENCIA)
    otra["technologies"]["Django"]["provenance"] = "declared"

    assert compute(otra) != compute(EVIDENCIA)


def test_un_script_nuevo_mueve_la_huella():
    otra = copy.deepcopy(EVIDENCIA)
    otra["npm_scripts"].append({"name": "test", "command": "vitest"})

    assert compute(otra) != compute(EVIDENCIA)


def test_una_dependencia_de_terceros_no_mueve_la_huella():
    """Un plugin de Moodle que cambia no es un cambio del proyecto."""

    otra = copy.deepcopy(EVIDENCIA)
    otra["manifests"].append(
        {
            "path": "plugins/tema/package.json",
            "kind": "npm",
            "third_party": True,
            "dependencies": [{"name": "jquery", "version": "3", "line": 2}],
            "scripts": [],
        }
    )

    assert compute(otra) == compute(EVIDENCIA)


# ============================================================
# MARCADOR
# ============================================================

def test_sellar_y_leer_son_simetricos():
    huella = compute(EVIDENCIA)

    sellado = sellar("# Proyecto\n\nTexto.\n", huella)

    assert leer(sellado) == huella


def test_sellar_dos_veces_no_acumula_marcadores():
    primera = sellar("# Proyecto\n", compute(EVIDENCIA))
    segunda = sellar(primera, compute(EVIDENCIA))

    assert segunda.count("ai-readme-fingerprint") == 1


def test_quitar_deja_el_texto_limpio():
    """
    El marcador no puede llegar al modelo: lo copiaria o lo mutilaria, y una
    huella corrupta obliga a regenerar siempre.
    """

    sellado = sellar("# Proyecto\n\nTexto.\n", compute(EVIDENCIA))
    limpio = quitar(sellado)

    assert "ai-readme-fingerprint" not in limpio
    assert "Texto." in limpio
    assert leer(limpio) is None


def test_un_readme_sin_marcador_no_tiene_huella():
    assert leer("# Proyecto\n\nSin marcador.\n") is None
    assert leer(None) is None
    assert leer("") is None
