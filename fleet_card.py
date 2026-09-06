#!/usr/bin/env python3
"""
Ficha de un repositorio: destila la evidencia a menos de 5 KB.

Por que existe
--------------

El pipeline produce un README_EVIDENCE.json por repositorio y ese activo se
usa una sola vez, para un solo archivo, y luego se tira. La ficha es lo que
permite agregarlo: 57 fichas caben en un indice que una persona puede leer.

El JSON completo son 19.197 caracteres para un repositorio de 15 archivos.
La ficha se queda con lo que describe al proyecto y tira `analysis`,
`files` y `capability_signals`.

Las dos vistas
--------------

    render(ficha, publico=False)   completa. Va al indice privado.
    render(ficha, publico=True)    para la vista publica.

La regla de publicacion, y no es negociable:

    De un repositorio PUBLICO sale todo. Su codigo ya es publico, asi que
    publicar sus endpoints, tablas y nombres de variables no revela nada
    que un `git clone` no de.

    De un repositorio PRIVADO no sale NADA: ni el nombre, ni endpoints, ni
    tablas, ni variables, ni dependencias, ni rutas. Solo el agregado.

No son secretos —nunca hay valores— pero juntos son un mapa de la
superficie de ataque de sistemas internos de un organismo publico. Y el
nombre del repositorio por si solo ya es informativo.

PRINCIPIO: DETECCION != CONCLUSION.
Las columnas que ORDENAN el inventario son hechos de sistema de archivos
verificables. Las senales del detector viajan marcadas como diagnostico.
"""

from __future__ import annotations

CLAVES_PROHIBIDAS_EN_PUBLICO = (
    "nombre",
    "descripcion",
    "url",
    "endpoints",
    "tablas",
    "variables_entorno",
    "dependencias",
    "manifiestos",
    "archivos_clave",
    "lenguajes",
    "tecnologias",
)

UMBRAL_PLACEHOLDER = 200


def _hechos_de_filesystem(evidencia: dict, repo_nombre: str) -> dict:
    """
    Lo unico con lo que se ordena el inventario.

    Son comprobables abriendo el repositorio, a diferencia de las senales
    del detector, que son inferencias.
    """

    archivos = evidencia.get("files") or []

    rutas = {f["path"] for f in archivos}
    nombres = {f["name"] for f in archivos}

    readme = next(
        (f for f in archivos if f["path"] == "README.md"),
        None,
    )

    bytes_readme = readme["size"] if readme else 0

    resumen = (
        evidencia.get("existing_readme", {}) or {}
    ).get("summary") or []

    # Un README que solo repite el nombre del repositorio no es
    # documentacion.
    solo_titulo = (
        len(resumen) <= 1
        and (
            not resumen
            or resumen[0].strip().lower().lstrip("# ")
            == repo_nombre.lower()
        )
    )

    return {
        "readme_bytes": bytes_readme,
        "readme_placeholder": (
            bytes_readme < UMBRAL_PLACEHOLDER or solo_titulo
        ),
        "tiene_license": any(
            n.upper().startswith("LICEN") or n.upper() == "COPYING"
            for n in nombres
        ),
        "tiene_tests": any(
            r.startswith(("tests/", "test/", "spec/"))
            or "/tests/" in r
            or "/__tests__/" in r
            for r in rutas
        ),
        "tiene_ci": any(
            r.startswith(".github/workflows/") for r in rutas
        ),
        "tiene_docker": any(
            n in {"Dockerfile", "docker-compose.yml", "docker-compose.yaml"}
            for n in nombres
        ),
        "tiene_gitignore": ".gitignore" in rutas,
        "archivos": len(archivos),
    }


def construir(
    repo,
    evidencia: dict,
) -> dict:
    """
    Destila la evidencia de un repositorio a su ficha.
    """

    tecnologias = evidencia.get("technologies") or {}

    concluyentes = {
        nombre: datos.get("provenance")
        for nombre, datos in tecnologias.items()
        if datos.get("provenance") in {"declared", "imported", "vendored"}
    }

    manifiestos = [
        m for m in (evidencia.get("manifests") or [])
        if not m.get("third_party")
    ]

    lenguajes: dict[str, int] = {}

    for archivo in evidencia.get("files") or []:
        idioma = archivo.get("language")
        if idioma and idioma != "Other":
            lenguajes[idioma] = lenguajes.get(idioma, 0) + 1

    return {
        "nombre": repo.name,
        "privado": repo.private,
        "url": repo.html_url,
        "descripcion": repo.description,
        "default_branch": repo.default_branch,
        "ultimo_push": repo.pushed_at,
        "topics": repo.topics,

        "salud": _hechos_de_filesystem(evidencia, repo.name),

        "lenguajes": dict(
            sorted(lenguajes.items(), key=lambda x: -x[1])[:8]
        ),

        # Marcadas como diagnostico: llevan su procedencia, y las que solo
        # estaban "mencionadas" ni siquiera llegan aqui.
        "tecnologias": concluyentes,

        "manifiestos": [m["path"] for m in manifiestos],

        "dependencias": [
            f"{d['name']}{d.get('version') or ''}"
            for m in manifiestos
            for d in m.get("dependencies", [])
        ][:80],

        "endpoints": [
            f"{a.get('method')} {a.get('path')}"
            for a in (evidencia.get("api") or [])
        ][:80],

        "tablas": [
            str(t.get("value"))
            for t in (evidencia.get("database_tables") or [])
        ][:60],

        "variables_entorno": [
            str(v.get("value"))
            for v in (evidencia.get("environment_variables") or [])
        ][:60],

        "archivos_clave": (evidencia.get("important_files") or [])[:25],
    }


def render(ficha: dict, publico: bool = False) -> dict | None:
    """
    Devuelve la ficha lista para publicar.

    De un repositorio privado en la vista publica devuelve None: no hay
    version reducida que valga, porque el nombre ya es informativo.
    """

    if not publico:
        return ficha

    if ficha.get("privado"):
        return None

    return ficha


def agregado_privados(fichas: list[dict]) -> dict:
    """
    Lo unico que se publica de los repositorios privados: un recuento.

    Sin nombres. El inventario publico dice cuanta deuda documental hay
    detrás del muro, no de quien es.
    """

    privadas = [f for f in fichas if f.get("privado")]

    if not privadas:
        return {}

    return {
        "total": len(privadas),
        "sin_readme": sum(
            1 for f in privadas if f["salud"]["readme_bytes"] == 0
        ),
        "readme_placeholder": sum(
            1 for f in privadas if f["salud"]["readme_placeholder"]
        ),
        "sin_license": sum(
            1 for f in privadas if not f["salud"]["tiene_license"]
        ),
        "sin_tests": sum(
            1 for f in privadas if not f["salud"]["tiene_tests"]
        ),
        "sin_ci": sum(
            1 for f in privadas if not f["salud"]["tiene_ci"]
        ),
    }


def deuda(ficha: dict) -> int:
    """
    Puntua la deuda documental. Solo con hechos comprobables.

    Se usa para ordenar el inventario, asi que no puede depender de
    inferencias del detector.
    """

    salud = ficha["salud"]

    puntos = 0

    if salud["readme_bytes"] == 0:
        puntos += 100
    elif salud["readme_placeholder"]:
        puntos += 80
    elif salud["readme_bytes"] < 1000:
        puntos += 40

    if not salud["tiene_license"]:
        puntos += 10

    if not salud["tiene_tests"]:
        puntos += 10

    if not salud["tiene_ci"]:
        puntos += 5

    if not salud["tiene_gitignore"]:
        puntos += 5

    return puntos


def verificar_sin_fuga(publicadas: list[dict], fichas: list[dict]) -> list[str]:
    """
    Red final: comprueba que ningun dato de repositorio privado se colo.

    Se ejecuta antes de publicar. Devuelve la lista de fugas encontradas.
    """

    nombres_privados = {
        f["nombre"].lower() for f in fichas if f.get("privado")
    }

    fugas = []

    texto = repr(publicadas).lower()

    for nombre in nombres_privados:
        if nombre in texto:
            fugas.append(f"nombre de repositorio privado: {nombre}")

    for ficha in publicadas:
        if ficha.get("privado"):
            fugas.append(f"ficha privada publicada: {ficha.get('nombre')}")

    return fugas
