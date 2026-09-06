#!/usr/bin/env python3
"""
Selecciona que repositorios documentar en el proximo barrido.

Por que existe
--------------

El generador solo actuaba cuando alguien hacia push a main. Los
repositorios dormidos —que suelen ser justamente los peor documentados—
nunca se alcanzaban. Este modulo elige a quien despertar y en que orden.

Criterio de prioridad
---------------------

Primero los que mas lo necesitan, medido con hechos de sistema de archivos
y no con senales del detector:

    1. sin README                      deuda maxima
    2. README que es un marcador       deuda maxima
    3. README pequeno                  a menor tamano, mas prioridad
    4. sin actividad reciente          a mas antiguo, mas prioridad

Se excluyen archivados, deshabilitados y forks. Y se excluye a quien haya
cerrado un pull request del bot sin fusionarlo: eso es una respuesta, y
volver a proponerle lo mismo cada semana es acoso, no automatizacion.

Es de SOLO LECTURA. Emite la seleccion por stdout; disparar es tarea del
workflow.

    python fleet_select.py --limite 5
    python fleet_select.py --json
"""

from __future__ import annotations

import argparse
import json
import sys

from github_client import GitHubClient, Repository

STUB_PATH = ".github/workflows/readme.yml"

BOT_BRANCH = "ai-readme/update-readme"

# Por debajo de esto un README no es documentacion.
UMBRAL_PLACEHOLDER = 200


def _readme(client: GitHubClient, repo: Repository) -> tuple[int, bool]:
    """
    Devuelve (bytes, es_placeholder) del README del repositorio.
    """

    contenido, _ = client.get_file(
        repo.full_name,
        "README.md",
        repo.default_branch,
    )

    if contenido is None:
        return 0, True

    texto = contenido.strip()

    if len(texto) < UMBRAL_PLACEHOLDER:
        return len(contenido), True

    sin_titulo = texto.replace(f"# {repo.name}", "").strip()

    return len(contenido), not sin_titulo


def _rechazo_previo(client: GitHubClient, repo: Repository) -> bool:
    """
    True si alguien cerro un pull request del bot sin fusionarlo.

    Es el bucle de resultado que le faltaba al sistema: sin esto, un
    barrido semanal vuelve a proponer indefinidamente lo mismo a quien ya
    dijo que no.
    """

    respuesta = client.request(
        "GET",
        f"/repos/{repo.full_name}/pulls",
        params={
            "state": "closed",
            "head": f"{repo.full_name.split('/')[0]}:{BOT_BRANCH}",
            "per_page": 10,
        },
    )

    if respuesta.status_code != 200:
        return False

    for pull in respuesta.json():
        if not pull.get("merged_at"):
            return True

    return False


def seleccionar(
    client: GitHubClient,
    limite: int = 0,
    incluir_rechazados: bool = False,
) -> list[dict]:

    repos = [
        r
        for r in client.list_organization_repositories(only_in_scope=True)
        if not r.archived and not r.disabled and not r.fork
    ]

    filas: list[dict] = []

    for indice, repo in enumerate(repos, start=1):

        print(
            f"   [{indice}/{len(repos)}] {repo.name}",
            end="\r",
            file=sys.stderr,
            flush=True,
        )

        stub, _ = client.get_file(
            repo.full_name,
            STUB_PATH,
            repo.default_branch,
        )

        bytes_readme, placeholder = _readme(client, repo)

        rechazado = (
            False
            if incluir_rechazados
            else _rechazo_previo(client, repo)
        )

        filas.append(
            {
                "repo": repo.full_name,
                "nombre": repo.name,
                "default_branch": repo.default_branch,
                "has_stub": stub is not None,
                "readme_bytes": bytes_readme,
                "placeholder": placeholder,
                "pushed_at": repo.pushed_at,
                "privado": repo.private,
                "rechazo_previo": rechazado,
            }
        )

    print(" " * 70, end="\r", file=sys.stderr)

    elegibles = [
        f for f in filas
        if f["has_stub"] and not f["rechazo_previo"]
    ]

    # Los de mayor deuda documental primero; a igualdad, el mas dormido.
    elegibles.sort(
        key=lambda f: (
            not f["placeholder"],
            f["readme_bytes"],
            f["pushed_at"] or "",
        )
    )

    if limite:
        elegibles = elegibles[:limite]

    return {
        "seleccionados": elegibles,
        "sin_stub": [f for f in filas if not f["has_stub"]],
        "rechazados": [f for f in filas if f["rechazo_previo"]],
        "total": len(filas),
    }


def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Selecciona repositorios para el barrido. Solo lectura."
        )
    )

    parser.add_argument(
        "--limite",
        type=int,
        default=0,
        help="Cuantos repositorios seleccionar.",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Emitir JSON en vez del informe legible.",
    )

    parser.add_argument(
        "--incluir-rechazados",
        action="store_true",
        help=(
            "Incluir repositorios que cerraron un pull request del bot sin "
            "fusionarlo. Por defecto se respetan."
        ),
    )

    argumentos = parser.parse_args()

    resultado = seleccionar(
        GitHubClient(),
        limite=argumentos.limite,
        incluir_rechazados=argumentos.incluir_rechazados,
    )

    if argumentos.json:
        print(json.dumps(resultado, ensure_ascii=False))
        return 0

    print("=" * 70)
    print(" SELECCION PARA EL BARRIDO")
    print("=" * 70)
    print()
    print(f"Repositorios en alcance   : {resultado['total']}")
    print(f"Seleccionados             : {len(resultado['seleccionados'])}")
    print(f"Sin stub instalado        : {len(resultado['sin_stub'])}")
    print(f"Con rechazo previo        : {len(resultado['rechazados'])}")
    print()
    print(f"{'repo':32s} {'README':>8s}  {'ultimo push':10s}")
    print("-" * 60)

    for fila in resultado["seleccionados"]:
        marca = "placeholder" if fila["placeholder"] else ""
        print(
            f"{fila['nombre']:32s} {fila['readme_bytes']:8d}  "
            f"{(fila['pushed_at'] or '')[:10]}  {marca}"
        )

    if resultado["rechazados"]:
        print()
        print("No se vuelven a proponer (cerraron un PR del bot sin fusionar):")
        for fila in resultado["rechazados"]:
            print(f"   {fila['nombre']}")

    if resultado["sin_stub"]:
        print()
        print("Sin instrumentar:")
        for fila in resultado["sin_stub"]:
            print(f"   {fila['nombre']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
