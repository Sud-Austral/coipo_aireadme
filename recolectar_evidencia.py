#!/usr/bin/env python3
"""
Recolecta la evidencia completa de cada repositorio en un solo directorio.

Para que sirve
--------------

fleet_scan.py produce fichas destiladas de menos de 5 KB, pensadas para el
inventario. Los insumos inversos necesitan mas: cada afirmacion suya lleva
una cita [archivo:linea], asi que hace falta la evidencia COMPLETA, con las
lineas.

Esto la deja en disco, un JSON por repositorio, para que se puedan redactar
los documentos sin volver a descargar nada.

No llama a ningun modelo y no escribe en los repositorios analizados.

    python recolectar_evidencia.py --salida ./evidencia
    python recolectar_evidencia.py --salida ./evidencia --local d:/GitHub
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tarfile
import tempfile
from pathlib import Path

from github_client import GITHUB_API, GitHubClient

MAX_TAMANO_KB = 300_000

NO_RECOLECTAR = {"coipo_index"}


def analizar(ruta: Path) -> dict:

    import readme3_scanner as sc
    from readme3_analyzers import (
        analyze_files,
        dependencies,
        detect_env_vars,
        detect_technologies,
    )
    from readme3_evidence import (
        build_evidence_json,
        existing_readme,
        generate_context,
    )
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
        analisis, manifiestos, archivos, ruta,
        mentioned=detect_technologies(archivos, ruta),
    )

    capacidades = classify_capabilities(
        archivos, ruta, concluyentes(tecnologias), manifiestos,
    )

    deps = dependencies(ruta)
    envs = detect_env_vars(analisis, {})
    readme = existing_readme(ruta)

    evidencia = build_evidence_json(
        ruta, archivos, analisis, tecnologias, deps, envs,
        capacidades, readme, manifiestos,
    )

    # El contexto destilado, que es lo que se le da a un redactor.
    evidencia["_contexto"] = generate_context(
        ruta, archivos, analisis, tecnologias, deps, envs,
        capacidades, readme, manifiestos,
    )

    # La evidencia completa pesa demasiado para leerla entera: se recorta
    # lo que no aporta a la redaccion.
    evidencia.pop("analysis", None)

    evidencia["files"] = [
        {k: f[k] for k in ("path", "language", "size", "third_party")}
        for f in archivos
    ]

    return evidencia


def main() -> int:

    parser = argparse.ArgumentParser()
    parser.add_argument("--salida", default="evidencia")
    parser.add_argument(
        "--local",
        default="",
        help=(
            "Directorio con clones locales. Se usan cuando existen, para "
            "no descargar de nuevo."
        ),
    )
    parser.add_argument("--limite", type=int, default=0)

    argumentos = parser.parse_args()

    salida = Path(argumentos.salida)
    salida.mkdir(parents=True, exist_ok=True)

    local = Path(argumentos.local) if argumentos.local else None

    client = GitHubClient()

    repos = [
        r
        for r in client.list_organization_repositories(only_in_scope=True)
        if not r.archived and not r.disabled and not r.fork
        and r.name not in NO_RECOLECTAR
    ]

    repos.sort(key=lambda r: r.name.lower())

    if argumentos.limite:
        repos = repos[: argumentos.limite]

    hechos, omitidos = [], []

    for indice, repo in enumerate(repos, start=1):

        destino = salida / f"{repo.name}.json"

        if destino.exists():
            print(f"   [{indice}/{len(repos)}] {repo.name} (ya estaba)")
            hechos.append(repo.name)
            continue

        print(f"   [{indice}/{len(repos)}] {repo.name}", flush=True)

        ruta_local = None

        if local:
            for candidato in (local / repo.name, local / repo.name.upper()):
                if candidato.is_dir():
                    ruta_local = candidato
                    break

        try:

            if ruta_local:
                evidencia = analizar(ruta_local)
                evidencia["_origen"] = f"local: {ruta_local}"

            else:

                if repo.size > MAX_TAMANO_KB:
                    omitidos.append(
                        f"{repo.name}: {repo.size / 1024:.0f} MB, "
                        f"supera el limite"
                    )
                    continue

                with tempfile.TemporaryDirectory() as temporal:

                    respuesta = client.session.get(
                        f"{GITHUB_API}/repos/{repo.full_name}/tarball/"
                        f"{repo.default_branch}",
                        timeout=300,
                    )

                    if respuesta.status_code != 200:
                        omitidos.append(
                            f"{repo.name}: HTTP {respuesta.status_code}"
                        )
                        continue

                    with tarfile.open(
                        fileobj=io.BytesIO(respuesta.content)
                    ) as tar:
                        tar.extractall(temporal)

                    hijos = [
                        h for h in Path(temporal).iterdir() if h.is_dir()
                    ]

                    if not hijos:
                        omitidos.append(f"{repo.name}: tarball vacio")
                        continue

                    evidencia = analizar(hijos[0])
                    evidencia["_origen"] = "tarball"

        except Exception as exc:
            omitidos.append(f"{repo.name}: {type(exc).__name__}: {exc}")
            continue

        evidencia["_repo"] = {
            "nombre": repo.name,
            "full_name": repo.full_name,
            "privado": repo.private,
            "default_branch": repo.default_branch,
            "descripcion": repo.description,
            "url": repo.html_url,
        }

        destino.write_text(
            json.dumps(evidencia, indent=1, ensure_ascii=False),
            encoding="utf-8",
        )

        hechos.append(repo.name)

    print()
    print(f"Evidencia recolectada: {len(hechos)}")
    print(f"Omitidos            : {len(omitidos)}")

    for omitido in omitidos:
        print(f"   {omitido}")

    (salida / "_omitidos.json").write_text(
        json.dumps(omitidos, indent=1, ensure_ascii=False),
        encoding="utf-8",
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
