#!/usr/bin/env python3
"""
Artefactos deterministas: `.env.example` y `docs/API.md`.

La objecion, escrita antes que el codigo
----------------------------------------

Este es el unico componente del sistema que produce archivos que otra
persona EJECUTA. Y se presenta como seguro justamente por lo que lo hace
peligroso: "cero coste de tokens, sin modelo".

Invierte el principio del repositorio. El README es una AFIRMACION que el
modelo hace y validate_readme.py audita. Un `.env.example` es una
INSTRUCCION que un colega copia a su `.env`. Publicar "usa Django" en prosa
es vergonzoso; publicar `HTTP_USER_AGENT` como variable de configuracion es
un defecto que se propaga al runtime ajeno.

Por eso, tres rieles:

  1. Solo fuentes `declared` e `imported`. Nada que venga de `mentioned`.
  2. NUNCA se escribe al arbol. Va en el cuerpo del pull request como
     propuesta, para que una persona decida.
  3. Desactivado por defecto. Se activa por repositorio con
     `artifacts: true` en .aireadme.yml.

Lo que queda fuera, y por que
-----------------------------

  Diagrama ER          analyze_sql cuenta como "tabla" lo que sigue a FROM,
                       JOIN, INTO o UPDATE, incluidos alias y subconsultas,
                       y no extrae ni una columna ni una clave foranea.
                       Seria ficcion con apariencia de rigor.

  requirements.txt     el nombre de import no es el del paquete: cv2 es
  autogenerado         opencv-python, sklearn es scikit-learn. Escribirlo
                       seria exactamente la conclusion que el principio
                       prohibe.

  CHANGELOG            en repositorios cuyos mensajes de commit dicen
                       "update" produce paginas de ruido.

PRINCIPIO: DETECCION != CONCLUSION.
Estos artefactos son propuestas, no verdades.
"""

from __future__ import annotations

# Variables que expone el entorno y que nadie configura en un .env.
# Sin esta lista, un `.env.example` sugiere copiar cosas como SCRIPT_NAME o
# HTTP_USER_AGENT, que las pone el servidor.
NO_SON_CONFIGURACION = {
    "PATH", "HOME", "USER", "USERNAME", "SHELL", "PWD", "LANG", "LC_ALL",
    "TERM", "TMPDIR", "TEMP", "TMP", "OS", "HOSTNAME",
    "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX",
    "NODE_ENV", "npm_lifecycle_event",
    "CI", "GITHUB_ACTIONS", "GITHUB_TOKEN", "GITHUB_REPOSITORY",
    "RUNNER_OS", "RUNNER_TEMP",
    "SCRIPT_NAME", "HTTP_USER_AGENT", "REQUEST_METHOD", "QUERY_STRING",
    "REMOTE_ADDR", "SERVER_NAME", "SERVER_PORT", "CONTENT_TYPE",
}

# Pistas para el comentario de cada variable. No inventan el valor: dicen
# que clase de cosa es, que es lo que un .env.example tiene que decir.
PISTAS = (
    ("PASSWORD", "secreto: no lo escribas aqui, ponlo en el .env real"),
    ("SECRET", "secreto: no lo escribas aqui, ponlo en el .env real"),
    ("TOKEN", "secreto: no lo escribas aqui, ponlo en el .env real"),
    ("KEY", "secreto: no lo escribas aqui, ponlo en el .env real"),
    ("_URL", "URL completa"),
    ("_HOST", "nombre de host"),
    ("_PORT", "puerto"),
    ("_USER", "nombre de usuario"),
    ("_NAME", "nombre"),
    ("_PATH", "ruta en el sistema de archivos"),
    ("DATABASE", "conexion a la base de datos"),
)


def _pista(nombre: str) -> str:

    mayus = nombre.upper()

    for aguja, texto in PISTAS:
        if aguja in mayus:
            return texto

    return "sin valor por defecto conocido"


def env_example(evidencia: dict) -> tuple[str, list[str]]:
    """
    Propone un `.env.example` desde las variables detectadas en el codigo.

    Devuelve (contenido, variables). Contenido vacio si no hay nada que
    proponer.
    """

    variables: dict[str, dict] = {}

    for item in evidencia.get("environment_variables") or []:

        nombre = str(item.get("value") or "").strip()

        if not nombre or nombre in NO_SON_CONFIGURACION:
            continue

        # Se conserva la primera cita: es la que sirve para verificar.
        variables.setdefault(nombre, item)

    if not variables:
        return "", []

    lineas = [
        "# Variables de entorno detectadas en el codigo.",
        "#",
        "# PROPUESTA generada por Sud-Austral/coipo_aireadme. No se escribio",
        "# ningun archivo: revisa esta lista y quedate con lo que aplique.",
        "#",
        "# Cada variable lleva el archivo y la linea donde se usa. Los",
        "# valores NO se deducen del codigo: los tienes que poner tu.",
        "",
    ]

    for nombre in sorted(variables):

        item = variables[nombre]

        cita = item.get("file", "")
        linea = item.get("line")

        referencia = f"{cita}:{linea}" if cita and linea else cita

        lineas.append(f"# {_pista(nombre)}  [{referencia}]")
        lineas.append(f"{nombre}=")
        lineas.append("")

    return "\n".join(lineas), sorted(variables)


def api_markdown(evidencia: dict) -> tuple[str, int]:
    """
    Propone un `docs/API.md` desde los endpoints detectados.
    """

    endpoints = evidencia.get("api") or []

    if not endpoints:
        return "", 0

    # Las llamadas del frontend no son la API que el proyecto EXPONE.
    backend = [
        e for e in endpoints
        if e.get("type") != "frontend_api_call"
    ]

    consumo = [
        e for e in endpoints
        if e.get("type") == "frontend_api_call"
    ]

    lineas = [
        "# API",
        "",
        "PROPUESTA generada por "
        "[`coipo_aireadme`](https://github.com/Sud-Austral/coipo_aireadme) "
        "a partir de las rutas declaradas en el codigo.",
        "",
        "Cada fila lleva el archivo y la linea donde se declara. Lo que no "
        "aparece aqui es porque el analizador no lo encontro, no porque no "
        "exista.",
        "",
    ]

    if backend:
        lineas += [
            "## Rutas expuestas",
            "",
            "| Metodo | Ruta | Declarada en |",
            "| --- | --- | --- |",
        ]

        vistas = set()

        for endpoint in backend:

            clave = (endpoint.get("method"), endpoint.get("path"))

            if clave in vistas:
                continue

            vistas.add(clave)

            lineas.append(
                f"| `{endpoint.get('method')}` "
                f"| `{endpoint.get('path')}` "
                f"| `{endpoint.get('file')}:{endpoint.get('line')}` |"
            )

        lineas.append("")

    if consumo:
        lineas += [
            "## Rutas que el frontend consume",
            "",
            "Detectadas en llamadas del cliente. Pueden apuntar a esta misma "
            "API o a un servicio externo: el analizador no puede "
            "distinguirlo.",
            "",
            "| Metodo | Ruta | Llamada desde |",
            "| --- | --- | --- |",
        ]

        vistas = set()

        for endpoint in consumo:

            clave = (endpoint.get("method"), endpoint.get("path"))

            if clave in vistas:
                continue

            vistas.add(clave)

            lineas.append(
                f"| `{endpoint.get('method')}` "
                f"| `{endpoint.get('path')}` "
                f"| `{endpoint.get('file')}:{endpoint.get('line')}` |"
            )

        lineas.append("")

    return "\n".join(lineas), len(backend) + len(consumo)


def proponer(evidencia: dict) -> list[dict]:
    """
    Devuelve las propuestas que tengan respaldo suficiente.

    Nunca escribe. El que decide es quien lee el pull request.
    """

    propuestas = []

    contenido, variables = env_example(evidencia)

    if contenido:
        propuestas.append(
            {
                "ruta": ".env.example",
                "contenido": contenido,
                "resumen": (
                    f"{len(variables)} variables de entorno detectadas en "
                    "el codigo y no declaradas en ningun archivo de ejemplo."
                ),
                "lenguaje": "bash",
            }
        )

    contenido, cuantos = api_markdown(evidencia)

    if contenido:
        propuestas.append(
            {
                "ruta": "docs/API.md",
                "contenido": contenido,
                "resumen": f"{cuantos} rutas detectadas con su cita.",
                "lenguaje": "markdown",
            }
        )

    return propuestas


def bloque_para_el_informe(propuestas: list[dict]) -> list[str]:
    """
    Las propuestas, plegadas, para el cuerpo del pull request.
    """

    if not propuestas:
        return []

    lineas = [
        "### Artefactos propuestos",
        "",
        "Generados de forma determinista desde la evidencia, **sin modelo**. "
        "No se escribio ningun archivo: son propuestas para que decidas.",
        "",
    ]

    for propuesta in propuestas:
        lineas += [
            "<details>",
            f"<summary><code>{propuesta['ruta']}</code> — "
            f"{propuesta['resumen']}</summary>",
            "",
            f"```{propuesta['lenguaje']}",
            propuesta["contenido"].strip(),
            "```",
            "",
            "</details>",
            "",
        ]

    return lineas
