#!/usr/bin/env python3
"""
Audita el estado real de la flota: quien tiene instalado el stub del
generador de README, a que referencia apunta, y que residuos dejo el bot
en repositorios que quedaron fuera de alcance.

Es de SOLO LECTURA. No escribe, no borra, no commitea nada.

    python auditar_workflows.py
    python auditar_workflows.py --json > flota.json
    python auditar_workflows.py --fuera-de-alcance

Token (solo lectura basta):

    Windows PowerShell:
        $env:GH_FLEET_TOKEN=$(gh auth token)

    Linux/macOS:
        export GH_FLEET_TOKEN=$(gh auth token)
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from github_client import (
    ORGANIZATION,
    SCOPE_PREFIX,
    GitHubClient,
    Repository,
)


STUB_PATH = ".github/workflows/readme.yml"

BOT_BRANCH = "ai-readme/update-readme"

# Captura la referencia del `uses:` del stub para distinguir @main de un
# tag o de un SHA fijado. Un caller fijado a un SHA anterior a la guarda
# de alcance nunca vera esa guarda.
USES_PATTERN = re.compile(
    r"uses:\s*Sud-Austral/coipo_aireadme/\.github/workflows/"
    r"generate-readme\.yml@(?P<ref>\S+)"
)


def clasificar_ref(ref: str) -> str:
    if ref == "main":
        return "rama main"

    if re.fullmatch(r"[0-9a-f]{7,40}", ref):
        return "SHA fijado"

    return f"tag/rama {ref}"


def auditar(
    client: GitHubClient,
    repos: list[Repository],
) -> list[dict]:

    filas: list[dict] = []

    total = len(repos)

    for indice, repo in enumerate(repos, start=1):

        print(
            f"   [{indice}/{total}] {repo.name}",
            end="\r",
            file=sys.stderr,
            flush=True,
        )

        contenido, _ = client.get_file(
            repo.full_name,
            STUB_PATH,
            repo.default_branch,
        )

        fila = {
            "repositorio": repo.name,
            "en_alcance": repo.in_scope,
            "privado": repo.private,
            "archivado": repo.archived,
            "rama_por_defecto": repo.default_branch,
            "ultimo_push": repo.pushed_at,
            "tiene_stub": contenido is not None,
            "ref": None,
            "tipo_ref": None,
            "hereda_secretos": None,
            "pr_abierto_del_bot": None,
        }

        if contenido is not None:
            coincidencia = USES_PATTERN.search(contenido)

            if coincidencia:
                ref = coincidencia.group("ref")
                fila["ref"] = ref
                fila["tipo_ref"] = clasificar_ref(ref)

            fila["hereda_secretos"] = "secrets: inherit" in contenido

        # Solo interesa el residuo del bot donde no deberia haber corrido.
        if not repo.in_scope and fila["tiene_stub"]:
            pulls = client.list_open_pull_requests(
                repo.full_name,
                head_branch=BOT_BRANCH,
            )

            fila["pr_abierto_del_bot"] = [
                p["html_url"] for p in pulls
            ]

        filas.append(fila)

    print(" " * 70, end="\r", file=sys.stderr)

    return filas


def informe(filas: list[dict]) -> int:

    en_alcance = [f for f in filas if f["en_alcance"]]
    fuera = [f for f in filas if not f["en_alcance"]]

    con_stub_dentro = [f for f in en_alcance if f["tiene_stub"]]
    sin_stub_dentro = [f for f in en_alcance if not f["tiene_stub"]]
    con_stub_fuera = [f for f in fuera if f["tiene_stub"]]

    print("=" * 70)
    print(" AUDITORIA DE LA FLOTA")
    print("=" * 70)
    print()
    print(f"Repositorios en la organizacion : {len(filas)}")
    print(f"En alcance ({SCOPE_PREFIX}*)             : {len(en_alcance)}")
    print(f"   con stub instalado           : {len(con_stub_dentro)}")
    print(f"   SIN stub (falta propagar)    : {len(sin_stub_dentro)}")
    print(f"Fuera de alcance                : {len(fuera)}")
    print(f"   con stub instalado           : {len(con_stub_fuera)}")
    print()

    # ----------------------------------------------------------------
    # Referencias
    # ----------------------------------------------------------------

    print("-" * 70)
    print(" REFERENCIAS DEL WORKFLOW REUTILIZABLE")
    print("-" * 70)
    print()

    por_tipo: dict[str, int] = {}

    for fila in filas:
        if fila["tiene_stub"]:
            clave = fila["tipo_ref"] or "no reconocida"
            por_tipo[clave] = por_tipo.get(clave, 0) + 1

    for clave, cuenta in sorted(
        por_tipo.items(),
        key=lambda item: -item[1],
    ):
        print(f"   {cuenta:4d}  {clave}")

    fijados = [
        f for f in filas
        if f["tiene_stub"] and f["tipo_ref"] == "SHA fijado"
    ]

    if fijados:
        print()
        print(
            "   AVISO: un stub fijado a un SHA no ve los cambios "
            "posteriores del hub,"
        )
        print(
            "   incluida la guarda de alcance. Revisar uno por uno:"
        )
        for fila in fijados:
            print(f"      {fila['repositorio']}  ->  {fila['ref']}")

    heredan = [f for f in filas if f["hereda_secretos"]]

    print()
    print(f"   Stubs con 'secrets: inherit' todavia: {len(heredan)}")

    # ----------------------------------------------------------------
    # Faltantes en alcance
    # ----------------------------------------------------------------

    if sin_stub_dentro:
        print()
        print("-" * 70)
        print(" EN ALCANCE Y SIN INSTRUMENTAR")
        print("-" * 70)
        print()
        for fila in sorted(
            sin_stub_dentro,
            key=lambda f: f["repositorio"].lower(),
        ):
            visibilidad = "privado" if fila["privado"] else "publico"
            print(f"   {fila['repositorio']}  ({visibilidad})")

    # ----------------------------------------------------------------
    # Residuo del bot fuera de alcance
    # ----------------------------------------------------------------

    con_pr = [
        f for f in con_stub_fuera
        if f["pr_abierto_del_bot"]
    ]

    print()
    print("-" * 70)
    print(" RESIDUO DEL BOT FUERA DE ALCANCE")
    print("-" * 70)
    print()

    if con_pr:
        print(
            f"   {len(con_pr)} repositorios fuera de alcance tienen un "
            f"PR abierto del bot."
        )
        print(
            "   La guarda de alcance es preventiva: no cierra lo que ya "
            "se abrio."
        )
        print()
        for fila in sorted(
            con_pr,
            key=lambda f: f["repositorio"].lower(),
        ):
            print(f"   {fila['repositorio']}")
            for url in fila["pr_abierto_del_bot"]:
                print(f"      {url}")
    else:
        print("   Ninguno. Nada que limpiar.")

    print()

    return 0


def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Audita el estado de instrumentacion de la flota. "
            "Solo lectura."
        )
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Emite el resultado como JSON en vez del informe.",
    )

    parser.add_argument(
        "--fuera-de-alcance",
        action="store_true",
        help=(
            "Audita solo los repositorios fuera de alcance. "
            "Util para verificar el efecto de la guarda."
        ),
    )

    parser.add_argument(
        "--limite",
        type=int,
        default=0,
        help="Audita solo los primeros N repositorios (para pruebas).",
    )

    argumentos = parser.parse_args()

    client = GitHubClient()

    print(
        f"Consultando la organizacion {ORGANIZATION}...",
        file=sys.stderr,
    )

    repos = client.list_organization_repositories()

    if argumentos.fuera_de_alcance:
        repos = [r for r in repos if not r.in_scope]

    if argumentos.limite:
        repos = repos[: argumentos.limite]

    print(
        f"Auditando {len(repos)} repositorios...",
        file=sys.stderr,
    )

    filas = auditar(client, repos)

    if argumentos.json:
        print(json.dumps(filas, indent=2, ensure_ascii=False))
        return 0

    return informe(filas)


if __name__ == "__main__":
    sys.exit(main())
