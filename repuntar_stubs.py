#!/usr/bin/env python3
"""
Repunta el stub de los repositorios en alcance a una referencia fija del
workflow reutilizable.

Por que existe
--------------

Hasta ahora los stubs apuntaban a `@main`, asi que cualquier commit al hub
entraba en produccion en toda la flota al instante, sin revision. Al fijarlos
a un tag, `main` pasa a ser rama de trabajo y publicar es mover el tag
deliberadamente.

El stub nuevo incorpora `paths-ignore` sobre si mismo. Sin eso, el commit que
repunta el stub disparia el propio stub y se generarian tantas ejecuciones y
tantos pull requests como repositorios se toquen de una vez.

Solo actua sobre repositorios en alcance (nombre que empieza con "coipo").
Nunca borra nada.

Uso
---

    python repuntar_stubs.py --dry-run
    python repuntar_stubs.py --limite 1
    python repuntar_stubs.py --repo coipo_canciones
    python repuntar_stubs.py --lote 10

Token:

    $env:GH_FLEET_TOKEN=$(gh auth token)      # PowerShell
    export GH_FLEET_TOKEN=$(gh auth token)    # bash
"""

from __future__ import annotations

import argparse
import sys
import time

from github_client import (
    GitHubClient,
    Repository,
    normalize_content,
)


STUB_PATH = ".github/workflows/readme.yml"

CENTRAL_REPOSITORY = "Sud-Austral/coipo_aireadme"

COMMIT_MESSAGE = (
    "ci: fijar el generador de README a una version publicada\n"
    "\n"
    "El stub apuntaba a la rama main del hub, de modo que cualquier cambio\n"
    "alli entraba en produccion aqui sin revision. Ahora apunta a un tag.\n"
    "\n"
    "Se agrega paths-ignore sobre el propio stub para que editarlo no\n"
    "dispare una regeneracion del README."
)


def construir_stub(ref: str) -> str:
    return f"""name: Run README Maintainer

on:
  push:
    branches:
      - main

    paths-ignore:
      # Editar este archivo no debe disparar una regeneracion del README.
      # Sin esta linea, repuntar el stub en la flota generaria una ejecucion
      # y un pull request por cada repositorio tocado.
      - '.github/workflows/readme.yml'

  workflow_dispatch:

jobs:
  call-readme-generator:
    # Referencia fija: main es rama de trabajo del hub, no produccion.
    uses: {CENTRAL_REPOSITORY}/.github/workflows/generate-readme.yml@{ref}
"""


def procesar(
    client: GitHubClient,
    repo: Repository,
    ref: str,
    dry_run: bool,
    crear_faltantes: bool = False,
) -> str:

    deseado = construir_stub(ref)

    actual, sha = client.get_file(
        repo.full_name,
        STUB_PATH,
        repo.default_branch,
    )

    if actual is None:

        if not crear_faltantes:
            return "sin stub"

        if dry_run:
            return "se instalaria"

        respuesta = client.put_file(
            repository=repo.full_name,
            path=STUB_PATH,
            branch=repo.default_branch,
            content=deseado,
            sha=None,
            message=(
                "ci: instalar el generador de README\n"
                "\n"
                "Llama al workflow reutilizable del hub, fijado a un tag.\n"
                "No genera nada hasta que haya un push o un dispatch."
            ),
        )

        if respuesta.status_code not in (200, 201):
            return (
                f"ERROR {respuesta.status_code}: "
                f"{respuesta.text[:120]}"
            )

        return "instalado"

    if normalize_content(actual) == normalize_content(deseado):
        return "ya al dia"

    if dry_run:
        return "se actualizaria"

    respuesta = client.put_file(
        repository=repo.full_name,
        path=STUB_PATH,
        branch=repo.default_branch,
        content=deseado,
        sha=sha,
        message=COMMIT_MESSAGE,
    )

    if respuesta.status_code not in (200, 201):
        return f"ERROR {respuesta.status_code}: {respuesta.text[:120]}"

    return "actualizado"


def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Repunta el stub de los repositorios en alcance a una "
            "referencia fija."
        )
    )

    parser.add_argument(
        "--ref",
        default="v1",
        help="Referencia del workflow reutilizable (por defecto v1).",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No escribe nada. Solo dice que haria.",
    )

    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        help="Actuar solo sobre estos repositorios. Repetible.",
    )

    parser.add_argument(
        "--limite",
        type=int,
        default=0,
        help="Procesar como maximo N repositorios.",
    )

    parser.add_argument(
        "--crear-faltantes",
        action="store_true",
        help=(
            "Instalar el stub tambien donde no exista. Sin esta bandera "
            "solo se actualizan los que ya lo tienen."
        ),
    )

    parser.add_argument(
        "--lote",
        type=int,
        default=0,
        help=(
            "Pausa de 5 segundos cada N repositorios, para no golpear la "
            "API de una sola vez."
        ),
    )

    argumentos = parser.parse_args()

    client = GitHubClient()

    repos = client.list_organization_repositories(only_in_scope=True)

    repos = [
        r for r in repos
        if not r.archived and not r.disabled and not r.fork
    ]

    if argumentos.repo:
        pedidos = {n.lower() for n in argumentos.repo}
        repos = [r for r in repos if r.name.lower() in pedidos]

    repos.sort(key=lambda r: r.name.lower())

    if argumentos.limite:
        repos = repos[: argumentos.limite]

    print("=" * 70)
    print(
        f" REPUNTE DE STUBS  ->  @{argumentos.ref}"
        f"{'   (SIMULACION)' if argumentos.dry_run else ''}"
    )
    print("=" * 70)
    print()
    print(f"Repositorios en alcance a procesar: {len(repos)}")
    print()

    conteo: dict[str, int] = {}

    for indice, repo in enumerate(repos, start=1):

        estado = procesar(
            client,
            repo,
            argumentos.ref,
            argumentos.dry_run,
            argumentos.crear_faltantes,
        )

        conteo[estado] = conteo.get(estado, 0) + 1

        print(f"   [{indice:3d}/{len(repos)}] {repo.name:34s} {estado}")

        if (
            argumentos.lote
            and indice % argumentos.lote == 0
            and indice < len(repos)
        ):
            print(f"        pausa de lote ({argumentos.lote})...")
            time.sleep(5)

    print()
    print("-" * 70)

    for estado, cuenta in sorted(
        conteo.items(),
        key=lambda item: -item[1],
    ):
        print(f"   {cuenta:4d}  {estado}")

    errores = sum(
        cuenta for estado, cuenta in conteo.items()
        if estado.startswith("ERROR")
    )

    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
