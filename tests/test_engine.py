#!/usr/bin/env python3
"""
Red de seguridad del motor de deteccion.

El conjunto NEGATIVO es la parte importante. El repositorio del propio
generador contiene un diccionario de nombres de tecnologias y listas de
palabras clave, asi que cualquier detector basado en texto se atribuye a si
mismo React, Django, MongoDB, YOLO, cartografia y machine learning. Medido
antes de la correccion: 23 tecnologias de 23 y 7 capacidades de 7, el 100%
falsas.

Sin un fixture que exija CERO, arreglar la deteccion seria un cambio de fe
aplicado de golpe a toda la flota.

    python -m pytest tests/ -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import readme3_scanner as sc                       # noqa: E402
from readme3_analyzers import (                    # noqa: E402
    analyze_files,
    detect_technologies,
)
from readme3_manifests import discover_manifests   # noqa: E402
from readme3_provenance import (                   # noqa: E402
    classify_capabilities,
    classify_technologies,
    concluyentes,
    normalize_token,
    tech_for,
)

FIXTURES = RAIZ / "tests" / "golden" / "vendor"


def analizar(repo: Path) -> dict:
    """Corre el pipeline de deteccion en memoria, sin escribir nada."""

    archivos = sc.scan(repo)
    analisis = analyze_files(repo, archivos)
    manifiestos = discover_manifests(repo, archivos)

    tecnologias = classify_technologies(
        analisis,
        manifiestos,
        archivos,
        repo,
        mentioned=detect_technologies(archivos, repo),
    )

    firmes = concluyentes(tecnologias)

    return {
        "files": archivos,
        "manifests": manifiestos,
        "technologies": firmes,
        "all_technologies": tecnologias,
        "capabilities": classify_capabilities(
            archivos,
            repo,
            firmes,
            manifiestos,
        ),
    }


# ============================================================
# CONJUNTO NEGATIVO
# ============================================================

def test_el_propio_repositorio_no_detecta_ninguna_tecnologia():
    """
    coipo_aireadme es Python plano que solo usa requests y PyYAML.

    Ninguna de las 23 tecnologias del diccionario le corresponde. Que
    aparezcan sus nombres dentro del codigo del detector no es evidencia
    de nada: es el detector leyendose a si mismo.
    """

    resultado = analizar(RAIZ)

    assert resultado["technologies"] == {}, (
        "El generador se esta atribuyendo tecnologias que no usa: "
        f"{sorted(resultado['technologies'])}"
    )


def test_el_propio_repositorio_no_detecta_ninguna_capacidad():
    """
    Las listas de palabras clave contienen "leaflet", "pandas" y "yolo"
    como literales. Sin corroboracion estructural, el detector se atribuye
    cartografia y machine learning a si mismo.
    """

    resultado = analizar(RAIZ)

    assert resultado["capabilities"] == {}, (
        "El generador se esta atribuyendo capacidades: "
        f"{sorted(resultado['capabilities'])}"
    )


def test_lo_solo_mencionado_no_pasa_como_concluyente():
    """
    El nivel `mentioned` se conserva, pero separado: sirve para avisar,
    nunca para documentar.
    """

    resultado = analizar(RAIZ)

    for nombre, datos in resultado["all_technologies"].items():
        assert datos["provenance"] == "mentioned", (
            f"{nombre} no deberia tener procedencia concluyente aqui"
        )


# ============================================================
# CONJUNTO POSITIVO
# ============================================================

def test_react_vite_declarado_en_manifiesto():
    """Lo declarado en package.json se detecta y se cita."""

    resultado = analizar(FIXTURES / "react_vite")
    tecnologias = resultado["technologies"]

    for esperada in ("React", "Vite", "Leaflet", "Tailwind", "Node.js"):
        assert esperada in tecnologias, f"falta {esperada}"
        assert tecnologias[esperada]["provenance"] == "declared"
        assert tecnologias[esperada]["evidence"][0]["file"]


def test_react_vite_no_inventa_lo_mencionado_en_comentarios():
    """
    App.jsx menciona Django y MongoDB dentro de un comentario.
    No deben aparecer como tecnologias del proyecto.
    """

    resultado = analizar(FIXTURES / "react_vite")

    assert "Django" not in resultado["technologies"]
    assert "MongoDB" not in resultado["technologies"]


def test_flask_api_normaliza_nombres_de_paquete():
    """
    psycopg2-binary tiene que resolver a PostgreSQL.
    El regex original, \\bpsycopg\\b, no casaba ese nombre.
    """

    tecnologias = analizar(FIXTURES / "flask_api")["technologies"]

    assert "Flask" in tecnologias
    assert "PostgreSQL" in tecnologias, (
        "psycopg2-binary no se resolvio a PostgreSQL"
    )
    assert "Pandas" in tecnologias


def test_flask_api_no_inventa_ml_por_un_docstring():
    """El docstring menciona yolo y tensorflow. No son dependencias."""

    tecnologias = analizar(FIXTURES / "flask_api")["technologies"]

    assert "YOLO" not in tecnologias


def test_mapa_por_cdn_no_desaparece():
    """
    Un repositorio de mapas que carga Leaflet desde un <script src> y no
    tiene package.json debe seguir detectandose.

    Es el riesgo central de arreglar los falsos positivos: cambiar un
    exceso de ruido por un exceso de silencio justo en el tipo de
    repositorio mas comun de la organizacion.
    """

    tecnologias = analizar(FIXTURES / "mapa_cdn")["technologies"]

    assert "Leaflet" in tecnologias
    assert tecnologias["Leaflet"]["provenance"] == "vendored"


# ============================================================
# DESCUBRIMIENTO DE MANIFIESTOS
# ============================================================

def test_manifiesto_en_subcarpeta_se_encuentra():
    """
    dependencies() solo miraba la raiz, asi que en los proyectos con el
    front en una subcarpeta la seccion de dependencias llegaba vacia.
    """

    manifiestos = analizar(FIXTURES / "react_vite")["manifests"]

    assert manifiestos, "no se encontro ningun manifiesto"
    assert any(
        m["path"].endswith("package.json") for m in manifiestos
    )

    declaradas = [
        d["name"]
        for m in manifiestos
        for d in m["dependencies"]
    ]

    assert "react" in declaradas
    assert "@vitejs/plugin-react" in declaradas


def test_los_scripts_npm_llegan_a_la_evidencia():
    """
    Existian en analyze_package_json pero solo se renderizaban como texto,
    asi que la validacion de comandos era codigo muerto.
    """

    manifiestos = analizar(FIXTURES / "react_vite")["manifests"]

    scripts = [
        s["name"]
        for m in manifiestos
        for s in m.get("scripts", [])
    ]

    assert "dev" in scripts
    assert "build" in scripts


# ============================================================
# NORMALIZACION
# ============================================================

@pytest.mark.parametrize(
    "nombre,esperado",
    [
        ("psycopg2-binary", "PostgreSQL"),
        ("psycopg2", "PostgreSQL"),
        ("tailwindcss", "Tailwind"),
        ("@vitejs/plugin-react", "Vite"),
        ("@angular/core", "Angular"),
        ("opencv-python-headless", "OpenCV"),
        ("ultralytics", "YOLO"),
        ("react-leaflet", "Leaflet"),
        ("mysqlclient", "MySQL"),
        ("pymongo", "MongoDB"),
        ("react", "React"),
        ("requests", None),
        ("pyyaml", None),
    ],
)
def test_traduccion_de_nombre_de_paquete_a_tecnologia(nombre, esperado):
    """
    Los regex originales fallaban en los nombres reales de los paquetes.
    Estos son los casos que se verificaron a mano.
    """

    assert tech_for(nombre) == esperado


@pytest.mark.parametrize(
    "crudo,esperado",
    [
        ("@vitejs/plugin-react", "plugin-react"),
        ("psycopg2-binary>=2.9", "psycopg2-binary"),
        ("Flask==3.0.0", "flask"),
        ("pandas[all]", "pandas"),
        ("os.path", "os"),
    ],
)
def test_normalizacion_de_token(crudo, esperado):
    assert normalize_token(crudo) == esperado


# ============================================================
# CODIGO DE TERCEROS
# ============================================================

def test_rutas_de_terceros_se_excluyen_o_se_marcan():
    """
    Medido en la flota: 98% de coipo_moodle y 81% de
    coipo_seguimiento_madera son codigo que no es del proyecto.
    """

    assert sc.is_excluded("mobile/platforms/android/app/Main.java")
    assert sc.is_excluded("backend/vendor/lib/thing.php")
    assert sc.is_excluded(".claude/skills/ingesta/_staging/work/x.txt")

    assert sc.is_third_party("plugins/theme/academi/lang/en.php")
    assert sc.is_third_party("static/js/app.min.js")

    assert not sc.is_excluded("backend/app/main.py")
    assert not sc.is_third_party("backend/app/main.py")


def test_el_escaner_no_ingiere_su_propia_evidencia():
    """
    readme_context contiene un JSON con los nombres de todas las
    tecnologias. Analizarlo equivale a detectarlas todas.
    """

    assert "readme_context" in sc.IGNORED_DIRS
    assert "README_CANDIDATE.md" in sc.IGNORED_FILES
