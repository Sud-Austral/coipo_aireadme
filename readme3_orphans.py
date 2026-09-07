#!/usr/bin/env python3
"""
Candidatos a borrar: filtro determinista, con evidencia.

Por que existe
--------------

Los archivos muertos no son solo desorden. Inflan el escaneo, empujan el
contexto contra el corte de 30.000 caracteres y degradan el README que se
genera. Limpiar el repositorio mejora la documentacion, no solo el repositorio.

Medido con este filtro sobre los 24 repositorios coipo_* locales: 102
candidatos, 4,3 MB. Los peores: coipo_seguimiento_madera (47),
coipo_prensa2 (14) y COIPO_CHATBOTNORMATIVA (8).

Una medicion previa con un regex suelto daba 237 archivos y 31 MB, pero
estaba llena de falsos positivos. Y una primera version de este modulo
llegaba a proponer 586 archivos y 1 GB en COIPO_LICITACION_IA: eran los PDF
de licitaciones que el proyecto procesa, o sea su insumo. Un informe con 586
falsos positivos no es un informe, y por eso la categoria de datos se
retiro.

Este modulo NO decide
---------------------

Solo propone candidatos con la evidencia de por que lo parecen. Quien juzga
y redacta es el modelo, en una llamada aparte, y quien decide es una
persona. El generador nunca borra: ni por CI, ni con opt-in, ni con bandera.

Detectar que algo parece huerfano no es concluir que sobra. La deteccion
estatica no ve importlib, ni imports dinamicos, ni rutas en cadenas de
texto, ni archivos referenciados desde HTML, ni datos que se leen por ruta
en tiempo de ejecucion. Por eso "revisar" es una categoria de primera clase
y no una nota al pie.

PRINCIPIO: DETECCION != CONCLUSION.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from readme3_scanner import read_text


# ============================================================
# LO QUE NUNCA ES CANDIDATO
#
# Regla dura. Da igual que parezca huerfano: estos archivos no se proponen.
# ============================================================

NUNCA_CANDIDATO = re.compile(
    r"""(
          (^|/)README(\.(md|txt|rst))?$
        | (^|/)LICEN[SC]E
        | (^|/)COPYING
        | (^|/)CHANGELOG
        | (^|/)CONTRIBUTING
        | (^|/)\.git(ignore|attributes|modules)
        | (^|/)\.github/
        | (^|/)package\.json$
        | (^|/)package-lock\.json$
        | (^|/)requirements[^/]*\.txt$
        | (^|/)pyproject\.toml$
        | (^|/)Pipfile
        | (^|/)poetry\.lock$
        | (^|/)composer\.(json|lock)$
        | (^|/)go\.(mod|sum)$
        | (^|/)Cargo\.(toml|lock)$
        | (^|/)Dockerfile
        | (^|/)docker-compose
        | (^|/)Makefile$
        | (^|/)migrations?/
        | (^|/)alembic/
        | (^|/)flyway
        | (^|/)tests?/
        | (^|/)__tests__/
        | (^|/)spec/
        | (^|/)\.env
        | (^|/)CLAUDE\.md$
        # Configuracion que su herramienta carga POR CONVENCION. Nadie la
        # importa, y eso no la vuelve huerfana: medido, el detector
        # proponia borrar vite.config.js de COIPO_PDF_EXCEL.
        | (^|/)(vite|next|nuxt|astro|svelte|tailwind|postcss|webpack
              |rollup|babel|jest|vitest|playwright|cypress|eslint
              |prettier|commitlint|lint-staged|drizzle|knexfile
              |metro|capacitor|ionic|craco|jsconfig|tsconfig)
              [.\w-]*\.(js|cjs|mjs|ts|json|yaml|yml)$
        | (^|/)(setup|conftest|manage|wsgi|asgi|gunicorn|celery)\.py$
        | (^|/)(setup|tox|pytest|alembic|mypy|pyrightconfig)\.(cfg|ini|toml|json)$
    )""",
    re.IGNORECASE | re.VERBOSE,
)


# ============================================================
# CATEGORIAS
# ============================================================

ARTEFACTOS_DEL_BOT = re.compile(
    r"(^|/)(README_CANDIDATE\.md|readme_report\.md|readme_context/)",
    re.IGNORECASE,
)

RESTOS_DE_BUILD = re.compile(
    r"""(
          (^|/)__pycache__/
        | (^|/)node_modules/
        | (^|/)\.venv/
        | (^|/)venv/
        | (^|/)\.pytest_cache/
        | (^|/)\.mypy_cache/
        | \.pyc$
        | \.pyo$
        | (^|/)\.DS_Store$
        | (^|/)Thumbs\.db$
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# Se exige ademas que exista el archivo base sin el sufijo: sin esa
# comprobacion, "app_v2.py" en un proyecto que solo tiene esa version
# quedaria marcado como copia de algo que no existe.
SUFIJOS_DE_VARIANTE = re.compile(
    r"""^(?P<base>.+?)
        (?P<sufijo>
              \s*-\s*cop(y|ia)
            | \s*\(\d+\)
            | \s*-\s*copy
            | _old
            | _OLD
            | _bak
            | _backup
            | _viejo
            | _antiguo
            | _v\d+
            | ~
            | \.bak
            | \.orig
        )$""",
    re.VERBOSE,
)

# La documentacion, los datos y la configuracion no se "importan". Buscar
# huerfanos entre ellos solo produce ruido.
EXTENSIONES_NO_CODIGO = {
    ".md", ".txt", ".rst", ".adoc",
    ".csv", ".xlsx", ".xls", ".parquet", ".pdf", ".zip",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".sql",
}

PUNTO_DE_ENTRADA = re.compile(
    r"""(
          if\s+__name__\s*==\s*["']__main__["']
        | ^\#!
        | @app\.route
        | createRoot|ReactDOM\.render
    )""",
    re.MULTILINE | re.VERBOSE,
)


def es_punto_de_entrada(ruta: Path) -> bool:
    """
    Un ejecutable no lo importa nadie: eso no lo vuelve huerfano.

    Medido: sin esta comprobacion, repuntar_stubs.py —un script de operador
    perfectamente vivo— aparecia como candidato a borrar en este mismo
    repositorio.
    """

    texto = read_text(ruta)

    return bool(texto and PUNTO_DE_ENTRADA.search(texto))


# ============================================================
# REFERENCIAS
# ============================================================

def _modulos_importados(analysis: dict) -> set[str]:

    modulos = set()

    for datos in analysis.values():
        for lenguaje in ("python", "javascript"):
            for item in (datos.get(lenguaje) or {}).get("imports", []):
                valor = (
                    item.get("value") if isinstance(item, dict) else item
                )
                if valor:
                    modulos.add(str(valor).split("/")[-1].split(".")[0])

    return modulos


def _menciones_de_nombre(
    files: list[dict],
    repo: Path,
    nombres: set[str],
) -> dict[str, int]:
    """
    Cuenta en cuantos archivos aparece cada nombre base.

    Barato gracias al cache de read_text: el corpus ya esta en memoria.
    """

    cuenta = {nombre: 0 for nombre in nombres}

    if not nombres:
        return cuenta

    for archivo in files:

        if not archivo["text"] or archivo["size"] > 1_000_000:
            continue

        texto = read_text(repo / archivo["path"])

        if not texto:
            continue

        propio = Path(archivo["path"]).stem

        for nombre in nombres:

            # No cuenta que un archivo se nombre a si mismo.
            if nombre == propio:
                continue

            if nombre in texto:
                cuenta[nombre] += 1

    return cuenta


# ============================================================
# BUSQUEDA
# ============================================================

def archivos_trackeados(repo: Path) -> list[str]:
    """
    Lo que git versiona, que NO es lo mismo que lo que el analizador escanea.

    El escaner ignora node_modules, __pycache__, readme_context y demas
    justamente porque no son codigo del proyecto. Pero si estan commiteados
    siguen ocupando el repositorio, y son los candidatos a borrar mas
    seguros que existen. Sin mirar el indice de git, el informe nunca
    podria proponer borrar precisamente lo que el analizador salta.
    """

    try:
        resultado = subprocess.run(
            ["git", "-C", str(repo), "ls-files"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    except Exception:
        return []

    if resultado.returncode != 0:
        return []

    return [
        linea.strip()
        for linea in resultado.stdout.splitlines()
        if linea.strip()
    ]


def find_candidates(
    repo: Path,
    files: list[dict],
    analysis: dict,
) -> list[dict]:
    """
    Devuelve candidatos con su categoria, confianza y evidencia.
    """

    rutas = {f["path"] for f in files}

    candidatos: list[dict] = []

    # ----------------------------------------------------------
    # Lo que git versiona pero el analizador no mira
    # ----------------------------------------------------------

    vistos: set[str] = set()

    for ruta in archivos_trackeados(repo):

        es_artefacto = bool(ARTEFACTOS_DEL_BOT.search(ruta))
        es_build = bool(RESTOS_DE_BUILD.search(ruta))

        if not (es_artefacto or es_build):
            continue

        # El orden importa: la lista de intocables protege README.md, y los
        # artefactos del generador se llaman README_CANDIDATE.md y viven en
        # readme_context/. Comprobarla primero los volvia invisibles, que es
        # justo lo contrario de lo que hace falta.
        if not es_artefacto and NUNCA_CANDIDATO.search(ruta):
            continue

        try:
            tamano = (repo / ruta).stat().st_size
        except OSError:
            tamano = 0

        vistos.add(ruta)

        candidatos.append(
            {
                "path": ruta,
                "size": tamano,
                "categoria": (
                    "artefacto del generador"
                    if es_artefacto
                    else "resto de build o entorno"
                ),
                "confianza": "alta",
                "evidencia": (
                    "Lo escribe este mismo generador; no es codigo del "
                    "proyecto."
                    if es_artefacto
                    else "Artefacto de compilacion o de entorno local, "
                    "versionado por error."
                ),
            }
        )

    # ----------------------------------------------------------
    # Categorias por patron de ruta
    # ----------------------------------------------------------

    for archivo in files:

        ruta = archivo["path"]

        if ruta in vistos or NUNCA_CANDIDATO.search(ruta):
            continue

        if ARTEFACTOS_DEL_BOT.search(ruta):
            candidatos.append(
                {
                    "path": ruta,
                    "size": archivo["size"],
                    "categoria": "artefacto del generador",
                    "confianza": "alta",
                    "evidencia": (
                        "Lo escribe este mismo generador. No es codigo del "
                        "proyecto y no deberia estar versionado."
                    ),
                }
            )
            continue

        if RESTOS_DE_BUILD.search(ruta):
            candidatos.append(
                {
                    "path": ruta,
                    "size": archivo["size"],
                    "categoria": "resto de build o entorno",
                    "confianza": "alta",
                    "evidencia": (
                        "Artefacto de compilacion o de entorno local, "
                        "versionado por error."
                    ),
                }
            )
            continue

        # ------------------------------------------------------
        # Variantes: solo si existe el archivo base
        # ------------------------------------------------------

        tallo = Path(ruta).stem
        extension = Path(ruta).suffix
        carpeta = str(Path(ruta).parent).replace("\\", "/")
        carpeta = "" if carpeta == "." else carpeta + "/"

        coincidencia = SUFIJOS_DE_VARIANTE.match(tallo)

        if coincidencia:

            base = f"{carpeta}{coincidencia.group('base')}{extension}"

            if base in rutas:
                candidatos.append(
                    {
                        "path": ruta,
                        "size": archivo["size"],
                        "categoria": "variante o respaldo",
                        "confianza": "media",
                        "evidencia": (
                            f"El sufijo `{coincidencia.group('sufijo')}` "
                            f"sugiere una copia, y el archivo base existe: "
                            f"`{base}`."
                        ),
                    }
                )
                continue

    # ----------------------------------------------------------
    # Huerfanos: ni se importan ni se nombran en ninguna parte
    # ----------------------------------------------------------

    ya_propuestos = {c["path"] for c in candidatos}

    importados = _modulos_importados(analysis)

    sospechosos = {}

    for archivo in files:

        ruta = archivo["path"]

        if ruta in ya_propuestos or NUNCA_CANDIDATO.search(ruta):
            continue

        if archivo.get("third_party"):
            continue

        if not archivo["text"]:
            continue

        # La documentacion no se importa nunca. Que un .md no aparezca
        # referenciado es lo normal, no una señal de que sobre. Medido:
        # marcaba como huerfanas las guias de INSUMO/ de coipo_moodle y la
        # documentacion de COIPO_ENTREGA_PLANTA.
        if archivo["ext"] in EXTENSIONES_NO_CODIGO:
            continue

        tallo = Path(ruta).stem

        if tallo in importados:
            continue

        # Un punto de entrada no lo importa nadie, por definicion.
        if es_punto_de_entrada(repo / ruta):
            continue

        # Un punto de entrada no lo importa nadie por definicion.
        if tallo in {"main", "app", "index", "server", "manage", "setup",
                     "conftest", "__init__", "wsgi", "asgi", "run"}:
            continue

        sospechosos[tallo] = ruta

    menciones = _menciones_de_nombre(files, repo, set(sospechosos))

    for tallo, ruta in sospechosos.items():

        if menciones.get(tallo, 0) > 0:
            continue

        archivo = next(f for f in files if f["path"] == ruta)

        candidatos.append(
            {
                "path": ruta,
                "size": archivo["size"],
                "categoria": "huerfano aparente",
                "confianza": "media",
                "evidencia": (
                    f"No se importa en ningun modulo y el nombre "
                    f"`{tallo}` no aparece en ninguno de los "
                    f"{len(files)} archivos analizados."
                ),
            }
        )

    # La categoria "salida de datos sin referencia" se retiro.
    #
    # Medida sobre COIPO_LICITACION_IA: 577 candidatos y 1 GB, que eran los
    # PDF de licitaciones que el proyecto procesa. Es decir, su insumo. Un
    # informe con 577 falsos positivos no es un informe.
    #
    # Distinguir un dato de entrada de una salida olvidada no se puede hacer
    # mirando si alguien nombra el archivo: los insumos se leen por
    # directorio, no por nombre.

    candidatos.sort(
        key=lambda c: (
            {"alta": 0, "media": 1, "baja": 2}[c["confianza"]],
            -c["size"],
        )
    )

    return candidatos


def resumen(candidatos: list[dict], total_archivos: int) -> dict:
    """
    Cuantifica el ahorro, que es lo que responde a la pregunta de fondo:
    cuanto contexto se recupera al limpiar.
    """

    bytes_totales = sum(c["size"] for c in candidatos)

    por_categoria: dict[str, dict] = {}

    for candidato in candidatos:
        entrada = por_categoria.setdefault(
            candidato["categoria"],
            {"archivos": 0, "bytes": 0},
        )
        entrada["archivos"] += 1
        entrada["bytes"] += candidato["size"]

    return {
        "archivos": len(candidatos),
        "bytes": bytes_totales,
        "porcentaje_archivos": (
            round(100 * len(candidatos) / total_archivos, 1)
            if total_archivos
            else 0.0
        ),
        "por_categoria": por_categoria,
    }
