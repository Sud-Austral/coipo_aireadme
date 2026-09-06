#!/usr/bin/env python3
"""
Clasificacion de tecnologias por PROCEDENCIA de la evidencia.

El problema que resuelve
------------------------

`detect_technologies` buscaba cada tecnologia por regex sobre el texto de
todos los archivos. Medido sobre este mismo repositorio, que es Python plano
con `requests`: devolvia 23 de 23 tecnologias, el 100% falsas. La primera
"evidencia" de Node.js era el regex \\bnode\\b casando con
`for node in ast.walk(tree)`.

Aqui la pregunta cambia. Ya no es "aparece esta palabra", sino "de donde sale
la evidencia", y la respuesta se etiqueta:

    declared    el nombre aparece como dependencia en un manifiesto.
                Es la evidencia mas fuerte que existe.
    imported    el modulo se importa en el codigo.
    vendored    se carga por CDN o esta vendorizado en un HTML.
                Imprescindible: hay repos de mapas que cargan Leaflet
                desde un <script src> y no tienen package.json. Sin este
                nivel, arreglar el ruido produciria silencio justo en el
                tipo de repositorio mas comun de la organizacion.
    mentioned   solo aparece el nombre en algun texto. NO es concluyente.

PRINCIPIO: DETECCION != CONCLUSION.
Este modulo dice de donde sale cada senal. No decide que significa.
"""

from __future__ import annotations

import re
from pathlib import Path

from readme3_scanner import line_number, read_text


# ============================================================
# NORMALIZACION DE NOMBRES
# ============================================================

def normalize_token(nombre: str) -> str:
    """
    Reduce un nombre de paquete o modulo a una forma comparable.

    Los regex originales fallaban en los casos mas frecuentes:
    \\bpsycopg\\b no casa "psycopg2-binary", \\btailwind\\b no casa
    "tailwindcss" y \\bvite\\b no casa "@vitejs/plugin-react".
    """

    token = nombre.strip().lower()

    # Scope de npm: @org/paquete -> paquete
    if token.startswith("@"):
        partes = token.split("/", 1)
        token = partes[1] if len(partes) > 1 else partes[0][1:]

    # Especificador de version pegado al nombre
    token = re.split(r"[<>=!~\^\[; ]", token, maxsplit=1)[0]

    # Submodulo de python: paquete.sub -> paquete
    token = token.split(".")[0]

    return token.strip()


# ============================================================
# MAPA MODULO -> TECNOLOGIA
#
# El nombre del paquete casi nunca es el nombre de la tecnologia. Sin este
# mapa, el arreglo empeoraria la deteccion en vez de mejorarla.
# ============================================================

MODULE_TO_TECH = {
    # Frontend
    "react": "React",
    "react-dom": "React",
    "react-router": "React",
    "react-router-dom": "React",
    "vite": "Vite",
    "vitejs": "Vite",
    "plugin-react": "Vite",
    "vue": "Vue",
    "core": None,          # @angular/core se resuelve por prefijo, abajo
    "tailwindcss": "Tailwind",
    "tailwind": "Tailwind",

    # Backend
    "flask": "Flask",
    "fastapi": "FastAPI",
    "uvicorn": "FastAPI",
    "django": "Django",
    "express": "Express",

    # Bases de datos
    "psycopg2": "PostgreSQL",
    "psycopg2-binary": "PostgreSQL",
    "psycopg": "PostgreSQL",
    "asyncpg": "PostgreSQL",
    "pg": "PostgreSQL",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysqlclient": "MySQL",
    "pymysql": "MySQL",
    "mysql": "MySQL",
    "mysql2": "MySQL",
    "mysql-connector-python": "MySQL",
    "sqlite3": "SQLite",
    "aiosqlite": "SQLite",
    "better-sqlite3": "SQLite",
    "pymongo": "MongoDB",
    "motor": "MongoDB",
    "mongoose": "MongoDB",
    "redis": "Redis",
    "ioredis": "Redis",
    "sqlalchemy": "SQLAlchemy",
    "flask-sqlalchemy": "SQLAlchemy",

    # Mapas
    "leaflet": "Leaflet",
    "react-leaflet": "Leaflet",
    "folium": "Leaflet",
    "mapbox-gl": "Mapbox",
    "react-map-gl": "Mapbox",

    # Datos y vision
    "pandas": "Pandas",
    "geopandas": "Pandas",
    "numpy": "NumPy",
    "opencv-python": "OpenCV",
    "opencv-python-headless": "OpenCV",
    "cv2": "OpenCV",
    "ultralytics": "YOLO",
    "yolov5": "YOLO",
    "yolov8": "YOLO",
}

# Prefijos de paquete que resuelven a una tecnologia.
PREFIX_TO_TECH = (
    ("@angular/", "Angular"),
    ("angular", "Angular"),
    ("@vitejs/", "Vite"),
    ("@tailwindcss/", "Tailwind"),
)


def tech_for(nombre: str) -> str | None:
    """Traduce un nombre de dependencia o modulo a una tecnologia."""

    crudo = nombre.strip().lower()

    for prefijo, tecnologia in PREFIX_TO_TECH:
        if crudo.startswith(prefijo):
            return tecnologia

    return MODULE_TO_TECH.get(normalize_token(nombre))


# ============================================================
# CARGA POR CDN O VENDORIZADA EN HTML
# ============================================================

ASSET_RE = re.compile(
    r"""<(?:script|link)[^>]*?(?:src|href)\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)

ASSET_TO_TECH = (
    ("leaflet", "Leaflet"),
    ("mapbox", "Mapbox"),
    ("openlayers", "Leaflet"),
    ("react", "React"),
    ("vue", "Vue"),
    ("tailwind", "Tailwind"),
    ("bootstrap", None),
)


def detect_vendored_assets(files, repo: Path) -> dict[str, list[dict]]:
    """
    Busca tecnologias cargadas desde un <script src> o <link href>.

    Solo mira archivos HTML: en cualquier otro sitio la cadena "leaflet"
    no prueba que se cargue Leaflet.
    """

    hallazgos: dict[str, list[dict]] = {}

    for archivo in files:

        if archivo["language"] != "HTML":
            continue

        texto = read_text(repo / archivo["path"])

        if not texto:
            continue

        for coincidencia in ASSET_RE.finditer(texto):

            url = coincidencia.group(1).lower()

            for aguja, tecnologia in ASSET_TO_TECH:

                if tecnologia is None:
                    continue

                if aguja not in url:
                    continue

                hallazgos.setdefault(tecnologia, []).append(
                    {
                        "file": archivo["path"],
                        "line": line_number(
                            texto,
                            coincidencia.start(),
                        ),
                        "asset": coincidencia.group(1),
                        "third_party": archivo.get("third_party", False),
                    }
                )

    return hallazgos


# ============================================================
# CLASIFICACION
# ============================================================

ORDEN_PROCEDENCIA = ["declared", "imported", "vendored", "mentioned"]

CONFIANZA = {
    "declared": "high",
    "imported": "high",
    "vendored": "medium",
    "mentioned": "low",
}


def classify_technologies(
    analysis: dict,
    manifests: list[dict],
    files: list[dict],
    repo: Path,
    mentioned: dict | None = None,
) -> dict:
    """
    Devuelve {tecnologia: {provenance, confidence, evidence[]}}.

    Mantiene la forma del dict que ya consumia validate_readme.py, y agrega
    el campo `provenance`.
    """

    resultado: dict[str, dict] = {}

    def registrar(tecnologia, procedencia, item):

        if tecnologia is None:
            return

        entrada = resultado.setdefault(
            tecnologia,
            {"provenance": procedencia, "evidence": []},
        )

        # Se conserva la procedencia mas fuerte encontrada.
        if ORDEN_PROCEDENCIA.index(procedencia) < ORDEN_PROCEDENCIA.index(
            entrada["provenance"]
        ):
            entrada["provenance"] = procedencia

        if len(entrada["evidence"]) < 20:
            item = dict(item)
            item["provenance"] = procedencia
            entrada["evidence"].append(item)

    # ----------------------------------------------------------
    # declared: manifiestos
    # ----------------------------------------------------------

    hay_package_json = False
    hay_docker = False

    for manifiesto in manifests:

        if manifiesto["third_party"]:
            continue

        if manifiesto["kind"] == "npm":
            hay_package_json = True

        if manifiesto["kind"] in {"docker", "compose"}:
            hay_docker = True

        for dependencia in manifiesto["dependencies"]:

            registrar(
                tech_for(dependencia["name"]),
                "declared",
                {
                    "file": dependencia["file"],
                    "line": dependencia.get("line"),
                    "declared_as": dependencia["name"],
                },
            )

    # La presencia de un package.json es evidencia de Node.js mucho mas
    # solida que el regex \\bnode\\b, que casaba con `for node in ...`.
    if hay_package_json:
        for manifiesto in manifests:
            if manifiesto["kind"] == "npm" and not manifiesto["third_party"]:
                registrar(
                    "Node.js",
                    "declared",
                    {"file": manifiesto["path"], "line": 1,
                     "declared_as": "package.json"},
                )
                break

    if hay_docker:
        for manifiesto in manifests:
            if (
                manifiesto["kind"] in {"docker", "compose"}
                and not manifiesto["third_party"]
            ):
                registrar(
                    "Docker",
                    "declared",
                    {"file": manifiesto["path"], "line": 1,
                     "declared_as": manifiesto["path"]},
                )
                break

    # ----------------------------------------------------------
    # imported: codigo fuente
    # ----------------------------------------------------------

    for ruta, datos in analysis.items():

        for lenguaje in ("python", "javascript"):

            bloque = datos.get(lenguaje) or {}

            for importado in bloque.get("imports", []):

                nombre = (
                    importado.get("value")
                    if isinstance(importado, dict)
                    else importado
                )

                if not nombre:
                    continue

                registrar(
                    tech_for(str(nombre)),
                    "imported",
                    {
                        "file": ruta,
                        "line": (
                            importado.get("line")
                            if isinstance(importado, dict)
                            else None
                        ),
                        "imported_as": str(nombre),
                    },
                )

    # ----------------------------------------------------------
    # vendored: CDN o asset en HTML
    # ----------------------------------------------------------

    for tecnologia, hallazgos in detect_vendored_assets(files, repo).items():
        for hallazgo in hallazgos:
            registrar(tecnologia, "vendored", hallazgo)

    # ----------------------------------------------------------
    # mentioned: se conserva, degradado y aparte
    # ----------------------------------------------------------

    if mentioned:
        for tecnologia, datos in mentioned.items():
            if tecnologia in resultado:
                continue
            registrar(
                tecnologia,
                "mentioned",
                (datos.get("evidence") or [{}])[0],
            )

    for entrada in resultado.values():
        entrada["confidence"] = CONFIANZA[entrada["provenance"]]

    return resultado


# ============================================================
# SENALES DE CAPACIDAD
# ============================================================

# Se conservan las mismas categorias, con las palabras clave depuradas.
#
# La version anterior usaba find() por substring, sin limite de palabra:
# "auth" casaba dentro de "author" y "file" dentro de "profile", asi que
# cualquier repositorio con un archivo de licencia y un componente de perfil
# aparecia con autenticacion y carga de archivos.
#
# Se quitan ademas las palabras que no discriminan nada: "archivo", "file",
# "document" y "token" aparecen en practicamente cualquier codigo.
CAPABILITY_KEYWORDS = {
    "Autenticación": [
        "login", "logout", "signin", "jwt", "oauth",
        "authenticate", "authorization", "credentials",
    ],
    "Mapas / cartografía": [
        "leaflet", "mapbox", "openlayers", "geojson",
        "cartografia", "latitud", "longitude", "latitude",
    ],
    "Exportación": [
        "export", "exportar", "xlsx", "openpyxl",
        "to_csv", "to_excel", "download",
    ],
    "Carga de archivos": [
        "upload", "multipart", "formdata", "filereader",
        "uploadfile",
    ],
    "Reportes / analítica": [
        "reporte", "dashboard", "analytics", "estadistica",
    ],
    "Procesamiento de datos": [
        "pandas", "numpy", "dataframe", "etl", "geopandas",
    ],
    "IA / Machine Learning": [
        "tensorflow", "pytorch", "yolo", "sklearn",
        "scikit-learn", "openai", "anthropic",
    ],
}

# Archivos que no son evidencia de nada: son listas de dependencias o
# configuracion de herramientas.
CORPUS_EXCLUIDO = re.compile(
    r"(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|"
    r"\.eslintrc|eslint\.config\.|\.prettierrc|tsconfig\.json)",
    re.IGNORECASE,
)


# ============================================================
# CORROBORACION
#
# Una palabra en un texto no es evidencia de una capacidad. Este mismo
# repositorio lo demuestra: sus listas de palabras clave contienen
# "leaflet", "pandas" y "yolo" como literales, asi que un detector basado
# solo en texto se atribuye cartografia y machine learning a si mismo.
#
# Por eso cada categoria exige que algo ESTRUCTURAL la respalde: una
# tecnologia con procedencia, o una dependencia declarada. La palabra sola
# no basta.
# ============================================================

CAPABILITY_CORROBORATION = {
    "Autenticación": {
        "deps": {
            "pyjwt", "python-jose", "passlib", "bcrypt", "authlib",
            "jsonwebtoken", "passport", "next-auth", "flask-login",
            "django-allauth", "argon2-cffi", "oauthlib",
        },
    },
    "Mapas / cartografía": {
        "tech": {"Leaflet", "Mapbox"},
        "deps": {"geopandas", "shapely", "pyproj", "folium", "gdal", "rtree",
                 "pyogrio", "geoalchemy2"},
    },
    "Exportación": {
        "deps": {"openpyxl", "xlsxwriter", "xlsx", "exceljs", "reportlab",
                 "weasyprint", "python-docx", "papaparse", "csv-writer",
                 "pandas"},
    },
    "Carga de archivos": {
        "deps": {"python-multipart", "multer", "formidable", "busboy",
                 "aiofiles", "django-storages"},
    },
    "Reportes / analítica": {
        "deps": {"recharts", "chart.js", "chartjs", "plotly", "d3",
                 "apexcharts", "matplotlib", "seaborn", "reportlab"},
    },
    "Procesamiento de datos": {
        "tech": {"Pandas", "NumPy"},
        "deps": {"polars", "pyarrow", "dask", "duckdb"},
    },
    "IA / Machine Learning": {
        "tech": {"YOLO", "OpenCV"},
        "deps": {"tensorflow", "torch", "pytorch", "scikit-learn", "sklearn",
                 "ultralytics", "openai", "anthropic", "transformers",
                 "langchain"},
    },
}


def _corrobora(
    categoria: str,
    technologies: dict,
    nombres_dependencias: set[str],
) -> str | None:
    """
    Devuelve la evidencia estructural que respalda la categoría, o None.
    """

    regla = CAPABILITY_CORROBORATION.get(categoria)

    if not regla:
        return None

    for tecnologia in regla.get("tech", set()):
        if tecnologia in technologies:
            return f"tecnología {tecnologia}"

    for dependencia in regla.get("deps", set()):
        if dependencia in nombres_dependencias:
            return f"dependencia {dependencia}"

    return None


def classify_capabilities(
    files,
    repo: Path,
    technologies: dict | None = None,
    manifests: list[dict] | None = None,
) -> dict:
    """
    Registra señales de capacidad con límite de palabra y corroboración.

    IMPORTANTE: son SEÑALES, no funcionalidades confirmadas. Que aparezca
    la palabra "upload" no prueba que el sistema permita subir archivos.
    Por eso, además de la palabra, se exige una dependencia o tecnología
    que la respalde.
    """

    technologies = technologies or {}

    nombres_dependencias = set()

    for manifiesto in (manifests or []):

        if manifiesto.get("third_party"):
            continue

        for dependencia in manifiesto.get("dependencies", []):
            nombres_dependencias.add(
                normalize_token(dependencia["name"])
            )
            nombres_dependencias.add(dependencia["name"].strip().lower())

    patrones = {
        categoria: re.compile(
            "|".join(
                r"\b" + re.escape(palabra) + r"\b"
                for palabra in palabras
            ),
            re.IGNORECASE,
        )
        for categoria, palabras in CAPABILITY_KEYWORDS.items()
    }

    resultado: dict[str, dict] = {}

    for categoria, patron in patrones.items():

        señales = []
        archivos_propios = set()

        for archivo in files:

            if not archivo["text"]:
                continue

            if archivo["size"] > 500_000:
                continue

            if CORPUS_EXCLUIDO.search(archivo["path"]):
                continue

            texto = read_text(repo / archivo["path"])

            if not texto:
                continue

            coincidencia = patron.search(texto)

            if not coincidencia:
                continue

            es_terceros = archivo.get("third_party", False)

            if not es_terceros:
                archivos_propios.add(archivo["path"])

            if len(señales) < 20:
                señales.append(
                    {
                        "keyword": coincidencia.group(0).lower(),
                        "file": archivo["path"],
                        "line": line_number(
                            texto,
                            coincidencia.start(),
                        ),
                        "third_party": es_terceros,
                    }
                )

        if not archivos_propios:
            # Solo aparecia en codigo de terceros: no dice nada del proyecto.
            continue

        respaldo = _corrobora(
            categoria,
            technologies,
            nombres_dependencias,
        )

        if respaldo is None:
            # La palabra esta, pero nada estructural la sostiene.
            # Se descarta: es exactamente el caso que hacia que este
            # repositorio se atribuyera cartografia por tener la cadena
            # "leaflet" dentro de una lista de palabras clave.
            continue

        resultado[categoria] = {
            "confidence": (
                "medium" if len(archivos_propios) >= 3 else "low"
            ),
            "own_files": len(archivos_propios),
            "corroborated_by": respaldo,
            "signals": señales,
        }

    return resultado


def concluyentes(technologies: dict) -> dict:
    """
    Solo las tecnologias con procedencia concluyente.

    `mentioned` queda fuera: que el nombre aparezca en un texto no prueba
    que el proyecto use la tecnologia.
    """

    return {
        nombre: datos
        for nombre, datos in technologies.items()
        if datos.get("provenance") in {"declared", "imported", "vendored"}
    }
