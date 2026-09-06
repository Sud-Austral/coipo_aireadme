#!/usr/bin/env python3
"""
Censo de la flota: una ficha por repositorio, sin gastar un token.

Por que existe
--------------

Hay 57 repositorios COIPO y ningun indice. Nadie puede responder que existe,
que esta sin documentar ni donde se repite el mismo trabajo. El pipeline ya
produce toda la evidencia necesaria; lo unico que faltaba era recolectarla.

Como funciona
-------------

NO ejecuta readme3.py como subproceso ni escribe nada en el arbol analizado.
Importa las funciones del pipeline —que son puras y reciben una ruta— y las
orquesta en memoria sobre una copia temporal descargada como tarball.

Tampoco llama al modelo: el censo es puramente determinista. Cero tokens,
cero pull requests, cero ruido en los repositorios.

    python fleet_scan.py --salida ./indice
    python fleet_scan.py --limite 5 --salida ./indice

Token:

    export GH_FLEET_TOKEN=$(gh auth token)

Hacen falta permisos de lectura sobre los repositorios privados: 30 de los
57 lo son, y GITHUB_TOKEN no lee repositorios hermanos.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tarfile
import tempfile
from pathlib import Path

from fleet_card import agregado_privados, construir, deuda, render
from github_client import GITHUB_API, GitHubClient, Repository

# Repositorios por encima de esto no se descargan. Se registran como
# omitidos con su motivo: un censo que salta cosas en silencio miente.
MAX_TAMANO_KB = 300_000


def descargar(client: GitHubClient, repo: Repository, destino: Path) -> Path | None:
    """
    Descarga el repositorio como tarball y lo extrae. Solo lectura.
    """

    respuesta = client.session.get(
        f"{GITHUB_API}/repos/{repo.full_name}/tarball/{repo.default_branch}",
        timeout=180,
    )

    if respuesta.status_code != 200:
        return None

    with tarfile.open(fileobj=io.BytesIO(respuesta.content)) as tar:
        tar.extractall(destino)

    # El tarball trae una sola carpeta raiz con un sufijo de commit.
    hijos = [h for h in destino.iterdir() if h.is_dir()]

    return hijos[0] if hijos else None


def analizar(ruta: Path) -> dict:
    """
    Corre el pipeline de evidencia en memoria, sin escribir nada.
    """

    import readme3_scanner as sc
    from readme3_analyzers import (
        analyze_files,
        dependencies,
        detect_env_vars,
        detect_technologies,
    )
    from readme3_evidence import build_evidence_json, existing_readme
    from readme3_manifests import discover_manifests
    from readme3_provenance import (
        classify_capabilities,
        classify_technologies,
        concluyentes,
    )

    archivos = sc.scan(ruta)
    analisis = analyze_files(ruta, archivos)
    manifiestos = discover_manifests(ruta, archivos)

    tecnologias = classify_technologies(
        analisis,
        manifiestos,
        archivos,
        ruta,
        mentioned=detect_technologies(archivos, ruta),
    )

    capacidades = classify_capabilities(
        archivos,
        ruta,
        concluyentes(tecnologias),
        manifiestos,
    )

    # generate_context no hace falta: ese destilado es el prompt del modelo,
    # y aqui no se llama al modelo.
    return build_evidence_json(
        ruta,
        archivos,
        analisis,
        tecnologias,
        dependencies(ruta),
        detect_env_vars(analisis, {}),
        capacidades,
        existing_readme(ruta),
        manifiestos,
    )


def censar(
    client: GitHubClient,
    limite: int = 0,
) -> dict:

    repos = [
        r
        for r in client.list_organization_repositories(only_in_scope=True)
        if not r.archived and not r.disabled and not r.fork
    ]

    repos.sort(key=lambda r: r.name.lower())

    if limite:
        repos = repos[:limite]

    fichas: list[dict] = []
    omitidos: list[dict] = []

    for indice, repo in enumerate(repos, start=1):

        print(
            f"   [{indice}/{len(repos)}] {repo.name}",
            file=sys.stderr,
            flush=True,
        )

        if repo.size > MAX_TAMANO_KB:
            omitidos.append(
                {
                    "repo": repo.name,
                    "motivo": (
                        f"OMITIDO_POR_TAMANO: {repo.size / 1024:.0f} MB "
                        f"supera el limite de {MAX_TAMANO_KB / 1024:.0f} MB"
                    ),
                }
            )
            continue

        with tempfile.TemporaryDirectory() as temporal:

            try:
                ruta = descargar(client, repo, Path(temporal))

            except Exception as exc:
                omitidos.append(
                    {"repo": repo.name, "motivo": f"ERROR_DESCARGA: {exc}"}
                )
                continue

            if ruta is None:
                omitidos.append(
                    {"repo": repo.name, "motivo": "ERROR_DESCARGA: vacio"}
                )
                continue

            try:
                evidencia = analizar(ruta)

            except Exception as exc:
                omitidos.append(
                    {"repo": repo.name, "motivo": f"ERROR_ANALISIS: {exc}"}
                )
                continue

            fichas.append(construir(repo, evidencia))

    fichas.sort(key=lambda f: (-deuda(f), f["nombre"].lower()))

    return {"fichas": fichas, "omitidos": omitidos}


# ============================================================
# SALIDA
# ============================================================

def inventario_markdown(fichas: list[dict], omitidos: list[dict]) -> str:

    lineas = [
        "# Inventario COIPO",
        "",
        "Ordenado por **deuda documental**, calculada solo con hechos "
        "comprobables: bytes del README, si es un marcador de posicion, si "
        "hay LICENSE, tests, CI y .gitignore.",
        "",
        "Las tecnologias que aparecen llevan su procedencia y no ordenan "
        "nada: son diagnostico, no medida.",
        "",
        "| Repositorio | Deuda | README | Tests | CI | Licencia | Stack |",
        "| --- | ---: | ---: | :-: | :-: | :-: | --- |",
    ]

    def marca(valor):
        return "si" if valor else "-"

    for ficha in fichas:

        salud = ficha["salud"]

        readme = (
            "vacio"
            if salud["readme_bytes"] == 0
            else (
                "marcador"
                if salud["readme_placeholder"]
                else f"{salud['readme_bytes'] / 1024:.1f} KB"
            )
        )

        stack = ", ".join(sorted(ficha["tecnologias"]))[:44] or "-"

        privado = " (privado)" if ficha["privado"] else ""

        lineas.append(
            f"| `{ficha['nombre']}`{privado} | {deuda(ficha)} | {readme} "
            f"| {marca(salud['tiene_tests'])} | {marca(salud['tiene_ci'])} "
            f"| {marca(salud['tiene_license'])} | {stack} |"
        )

    if omitidos:
        lineas += [
            "",
            "## No censados",
            "",
            "Un censo que salta cosas en silencio miente.",
            "",
        ]
        for omitido in omitidos:
            lineas.append(f"- `{omitido['repo']}`: {omitido['motivo']}")

    return "\n".join(lineas) + "\n"


def catalogo_publico(fichas: list[dict]) -> str:
    """
    Vista publica: los repositorios publicos en detalle, y de los privados
    solo un recuento SIN NOMBRES.
    """

    publicas = [f for f in fichas if not f["privado"]]

    lineas = [
        "# Catalogo COIPO",
        "",
        "Que hay construido en la familia COIPO de Sud-Austral.",
        "",
        "Generado desde el codigo por "
        "[`coipo_aireadme`](https://github.com/Sud-Austral/coipo_aireadme). "
        "Cada tecnologia listada procede de un manifiesto, de un import o de "
        "un recurso cargado en el HTML; nada se infiere de nombres de "
        "archivo.",
        "",
        f"## {len(publicas)} repositorios publicos",
        "",
        "| Repositorio | Stack | Endpoints | Tablas | README |",
        "| --- | --- | ---: | ---: | ---: |",
    ]

    for ficha in sorted(publicas, key=lambda f: f["nombre"].lower()):

        salud = ficha["salud"]

        readme = (
            "-"
            if salud["readme_placeholder"]
            else f"{salud['readme_bytes'] / 1024:.1f} KB"
        )

        lineas.append(
            f"| [`{ficha['nombre']}`]({ficha['url']}) "
            f"| {', '.join(sorted(ficha['tecnologias']))[:40] or '-'} "
            f"| {len(ficha['endpoints'])} | {len(ficha['tablas'])} "
            f"| {readme} |"
        )

    agregado = agregado_privados(fichas)

    if agregado:
        lineas += [
            "",
            "## Repositorios privados",
            "",
            f"Hay **{agregado['total']}** repositorios privados en el "
            "alcance. De ellos no se publica ni el nombre ni ningun detalle "
            "tecnico: sus endpoints, tablas y variables serian un mapa de la "
            "superficie de ataque de sistemas internos.",
            "",
            "Lo unico que se publica es el recuento de deuda documental:",
            "",
            f"- {agregado['readme_placeholder']} con README que es un "
            "marcador de posicion",
            f"- {agregado['sin_license']} sin licencia",
            f"- {agregado['sin_tests']} sin pruebas",
            f"- {agregado['sin_ci']} sin integracion continua",
            "",
            "El detalle esta en el indice privado.",
        ]

    return "\n".join(lineas) + "\n"


def escribir(resultado: dict, salida: Path) -> None:

    fichas = resultado["fichas"]

    (salida / "cards").mkdir(parents=True, exist_ok=True)
    (salida / "fleet").mkdir(parents=True, exist_ok=True)

    for ficha in fichas:
        (salida / "cards" / f"{ficha['nombre']}.json").write_text(
            json.dumps(ficha, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    (salida / "fleet" / "inventory.json").write_text(
        json.dumps(resultado, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    (salida / "fleet" / "INVENTARIO.md").write_text(
        inventario_markdown(fichas, resultado["omitidos"]),
        encoding="utf-8",
    )

    # Vista publica, aparte y comprobada.
    publicas = [
        f for f in (render(x, publico=True) for x in fichas) if f
    ]

    from fleet_card import verificar_sin_fuga

    fugas = verificar_sin_fuga(publicas, fichas)

    if fugas:
        raise RuntimeError(
            "Se detectaron fugas de repositorios privados en la vista "
            f"publica: {fugas}"
        )

    (salida / "publico").mkdir(parents=True, exist_ok=True)

    (salida / "publico" / "CATALOGO.md").write_text(
        catalogo_publico(fichas),
        encoding="utf-8",
    )

    (salida / "publico" / "catalogo.json").write_text(
        json.dumps(
            {
                "publicos": publicas,
                "privados_agregado": agregado_privados(fichas),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def main() -> int:

    parser = argparse.ArgumentParser(
        description="Censo de la flota COIPO. No escribe en los repositorios."
    )

    parser.add_argument(
        "--salida",
        default="indice",
        help="Directorio donde dejar las fichas y el inventario.",
    )

    parser.add_argument(
        "--limite",
        type=int,
        default=0,
        help="Censar solo los primeros N repositorios.",
    )

    argumentos = parser.parse_args()

    resultado = censar(GitHubClient(), limite=argumentos.limite)

    salida = Path(argumentos.salida)

    escribir(resultado, salida)

    print()
    print("=" * 70)
    print(" CENSO COMPLETADO")
    print("=" * 70)
    print()
    print(f"Fichas    : {len(resultado['fichas'])}")
    print(f"Omitidos  : {len(resultado['omitidos'])}")
    print(f"Salida    : {salida.resolve()}")

    for omitido in resultado["omitidos"]:
        print(f"   {omitido['repo']}: {omitido['motivo']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
