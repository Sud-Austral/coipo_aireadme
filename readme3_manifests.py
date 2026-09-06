#!/usr/bin/env python3
"""
Descubrimiento de manifiestos de dependencias a cualquier profundidad.

Por que existe
--------------

`dependencies()` en readme3_analyzers.py solo miraba la RAIZ del repositorio.
En los proyectos con el front en una subcarpeta —COIPO_PDF_EXCEL,
COIPO_CHATBOTNORMATIVA, coipo_cabania y varios mas— eso significa que el
package.json es invisible: al modelo le llegaba la seccion de dependencias
VACIA mientras le llegaban tecnologias falsas detectadas por regex.

Las dependencias declaradas son la evidencia mas fiable que existe sobre el
stack de un proyecto. Perderlas y quedarse con el regex es exactamente al
reves de lo que el principio del repositorio pide.

PRINCIPIO: DETECCION != CONCLUSION.
Este modulo recopila lo que los manifiestos DECLARAN. No concluye nada.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from readme3_scanner import read_text, rel_path


# ============================================================
# QUE ES UN MANIFIESTO
# ============================================================

MANIFEST_NAMES = {
    "package.json": "npm",
    "requirements.txt": "python",
    "requirements-dev.txt": "python",
    "requirements-prod.txt": "python",
    "pyproject.toml": "python",
    "Pipfile": "python",
    "composer.json": "php",
    "Gemfile": "ruby",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "Dockerfile": "docker",
    "docker-compose.yml": "compose",
    "docker-compose.yaml": "compose",
    "Makefile": "make",
}

# Un package.json dentro de estas rutas no describe el proyecto.
MANIFEST_IGNORED = re.compile(
    r"(^|/)(node_modules|vendor|bower_components|dist|build|\.venv|venv)/",
    re.IGNORECASE,
)


# ============================================================
# PARSERS MINIMOS
# ============================================================

def parse_package_json(path: Path, repo: Path) -> dict:

    text = read_text(path)

    if not text:
        return {}

    try:
        data = json.loads(text)
    except Exception:
        return {}

    relative = rel_path(path, repo)

    dependencias = []

    for seccion in (
        "dependencies",
        "devDependencies",
        "peerDependencies",
    ):
        for nombre, version in (data.get(seccion) or {}).items():
            dependencias.append(
                {
                    "name": nombre,
                    "version": version,
                    "section": seccion,
                    "file": relative,
                    "line": _linea_de(text, f'"{nombre}"'),
                }
            )

    scripts = [
        {
            "name": nombre,
            "command": comando,
            "file": relative,
            "line": _linea_de(text, f'"{nombre}"'),
        }
        for nombre, comando in (data.get("scripts") or {}).items()
    ]

    return {
        "project_name": data.get("name"),
        "dependencies": dependencias,
        "scripts": scripts,
    }


def parse_requirements(path: Path, repo: Path) -> dict:

    text = read_text(path)

    if not text:
        return {}

    relative = rel_path(path, repo)

    dependencias = []

    for indice, cruda in enumerate(text.splitlines(), start=1):

        linea = cruda.strip()

        if not linea or linea.startswith(("#", "-r", "--")):
            continue

        # "psycopg2-binary>=2.9" -> nombre "psycopg2-binary"
        nombre = re.split(r"[<>=!~\[; ]", linea, maxsplit=1)[0].strip()

        if not nombre:
            continue

        dependencias.append(
            {
                "name": nombre,
                "version": linea[len(nombre):].strip() or None,
                "section": "requirements",
                "file": relative,
                "line": indice,
            }
        )

    return {"dependencies": dependencias, "scripts": []}


def parse_pyproject(path: Path, repo: Path) -> dict:

    text = read_text(path)

    if not text:
        return {}

    relative = rel_path(path, repo)

    dependencias = []

    # Sin dependencia de un parser TOML: se buscan las entradas de las
    # tablas de dependencias mas comunes. Es deliberadamente conservador —
    # si no se reconoce, no se inventa.
    for indice, cruda in enumerate(text.splitlines(), start=1):

        linea = cruda.strip()

        coincidencia = re.match(
            r'^["\']?([A-Za-z0-9._-]+)["\']?\s*[>=<~^]*\s*["\']',
            linea,
        )

        if not coincidencia:
            continue

        nombre = coincidencia.group(1)

        if nombre.lower() in {
            "name", "version", "description", "readme",
            "requires-python", "license", "authors", "homepage",
        }:
            continue

        dependencias.append(
            {
                "name": nombre,
                "version": None,
                "section": "pyproject",
                "file": relative,
                "line": indice,
            }
        )

    return {"dependencies": dependencias, "scripts": []}


def parse_dockerfile(path: Path, repo: Path) -> dict:

    text = read_text(path)

    if not text:
        return {}

    relative = rel_path(path, repo)

    imagenes = []

    for indice, cruda in enumerate(text.splitlines(), start=1):

        coincidencia = re.match(
            r"^\s*FROM\s+(\S+)",
            cruda,
            re.IGNORECASE,
        )

        if coincidencia:
            imagenes.append(
                {
                    "name": coincidencia.group(1),
                    "version": None,
                    "section": "docker-image",
                    "file": relative,
                    "line": indice,
                }
            )

    return {"dependencies": imagenes, "scripts": []}


def parse_compose(path: Path, repo: Path) -> dict:

    text = read_text(path)

    if not text:
        return {}

    relative = rel_path(path, repo)

    imagenes = []

    for indice, cruda in enumerate(text.splitlines(), start=1):

        coincidencia = re.match(
            r"^\s*image:\s*[\"']?([^\"'\s]+)",
            cruda,
        )

        if coincidencia:
            imagenes.append(
                {
                    "name": coincidencia.group(1),
                    "version": None,
                    "section": "compose-image",
                    "file": relative,
                    "line": indice,
                }
            )

    return {"dependencies": imagenes, "scripts": []}


PARSERS = {
    "package.json": parse_package_json,
    "requirements.txt": parse_requirements,
    "requirements-dev.txt": parse_requirements,
    "requirements-prod.txt": parse_requirements,
    "pyproject.toml": parse_pyproject,
    "Dockerfile": parse_dockerfile,
    "docker-compose.yml": parse_compose,
    "docker-compose.yaml": parse_compose,
}


# ============================================================
# UTILIDAD
# ============================================================

def _linea_de(texto: str, aguja: str) -> int | None:

    posicion = texto.find(aguja)

    if posicion == -1:
        return None

    return texto.count("\n", 0, posicion) + 1


# ============================================================
# DESCUBRIMIENTO
# ============================================================

def discover_manifests(repo: Path, files: list[dict]) -> list[dict]:
    """
    Localiza los manifiestos a cualquier profundidad y los parsea.

    Devuelve una lista de manifiestos, cada uno con su ruta, su tipo, si
    esta en codigo de terceros, y las dependencias y scripts que declara,
    todos con cita [archivo:linea].
    """

    manifiestos = []

    for archivo in files:

        nombre = archivo["name"]

        if nombre not in MANIFEST_NAMES:
            continue

        if MANIFEST_IGNORED.search(archivo["path"]):
            continue

        parser = PARSERS.get(nombre)

        if parser is None:
            # Reconocido como manifiesto, pero sin parser propio.
            # Se registra igual: su sola presencia es evidencia.
            manifiestos.append(
                {
                    "path": archivo["path"],
                    "kind": MANIFEST_NAMES[nombre],
                    "third_party": archivo.get("third_party", False),
                    "dependencies": [],
                    "scripts": [],
                }
            )
            continue

        datos = parser(repo / archivo["path"], repo)

        manifiestos.append(
            {
                "path": archivo["path"],
                "kind": MANIFEST_NAMES[nombre],
                "third_party": archivo.get("third_party", False),
                "project_name": datos.get("project_name"),
                "dependencies": datos.get("dependencies", []),
                "scripts": datos.get("scripts", []),
            }
        )

    # La raiz primero, luego por profundidad: el manifiesto mas cercano a la
    # raiz es el que mejor describe el proyecto.
    manifiestos.sort(key=lambda m: (m["third_party"], m["path"].count("/")))

    return manifiestos


def declared_dependencies(
    manifiestos: list[dict],
    incluir_terceros: bool = False,
) -> list[dict]:
    """
    Aplana las dependencias declaradas de todos los manifiestos.
    """

    resultado = []

    for manifiesto in manifiestos:

        if manifiesto["third_party"] and not incluir_terceros:
            continue

        for dependencia in manifiesto["dependencies"]:
            item = dict(dependencia)
            item["kind"] = manifiesto["kind"]
            resultado.append(item)

    return resultado
