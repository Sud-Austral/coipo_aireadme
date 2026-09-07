#!/usr/bin/env python3
"""
Que haria el generador en este repositorio, sin llamar al modelo.

Por que existe
--------------

Antes, la unica forma de saber que iba a hacer el bot era dejarlo correr y
mirar el pull request. Eso cuesta una llamada al modelo, deja artefactos y,
en un repositorio con README escrito a mano, daba miedo.

Esto responde las mismas preguntas sin gastar nada:

    - Que evidencia ve, y con que procedencia.
    - Que decidiria el contrato con el humano: crear, fusionar o respetar.
    - Si la evidencia cambio desde la ultima generacion.
    - Que archivos propondria borrar.
    - Que artefactos propondria.
    - Que lee de .aireadme.yml.

    python preview.py "D:/GitHub/COIPO_ENTREGA_PLANTA"

No escribe nada en el repositorio.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import readme3_scanner as sc                              # noqa: E402
from readme3_analyzers import (                           # noqa: E402
    analyze_files,
    dependencies,
    detect_env_vars,
    detect_technologies,
)
from readme3_artifacts import proponer                    # noqa: E402
from readme3_evidence import (                            # noqa: E402
    build_evidence_json,
    existing_readme,
)
from readme3_fingerprint import compute, leer             # noqa: E402
from readme3_manifests import discover_manifests          # noqa: E402
from readme3_orphans import find_candidates, resumen      # noqa: E402
from readme3_provenance import (                          # noqa: E402
    classify_capabilities,
    classify_technologies,
    concluyentes,
)
from readme_config import ARCHIVO, cargar                 # noqa: E402
from readme_merge import decidir_accion                   # noqa: E402


ACCIONES = {
    "creado": (
        "Escribiria el README completo. No hay documentacion todavia: solo "
        "un marcador de posicion."
    ),
    "fusionado": (
        "Actualizaria solo el interior de los bloques AI:BEGIN cuyo "
        "contenido no haya cambiado a mano."
    ),
    "respetado": (
        "NO tocaria el README. Esta escrito a mano y no declara ningun "
        "bloque gestionado."
    ),
    "bloqueado": (
        "NO haria nada. El README declara <!-- ai-readme:lock -->."
    ),
}


def main() -> int:

    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if len(sys.argv) != 2:
        print('Uso: python preview.py "RUTA_REPOSITORIO"')
        return 1

    repo = Path(sys.argv[1]).resolve()

    if not repo.is_dir():
        print(f"No es un directorio: {repo}")
        return 1

    config = cargar(repo)

    print("=" * 70)
    print(f" PREVISUALIZACION: {repo.name}")
    print("=" * 70)
    print()
    print("Nada de esto llama al modelo ni escribe en el repositorio.")
    print()

    # ----------------------------------------------------------
    # Configuracion
    # ----------------------------------------------------------

    print("-" * 70)
    print(f" {ARCHIVO}")
    print("-" * 70)
    print()

    if not config.presente:
        print("   No existe. Se usarian los valores por defecto.")
    else:
        print(f"   enabled      : {config.enabled}")
        print(f"   lang         : {config.lang}")
        print(f"   ignore_paths : {config.ignore_paths or '-'}")
        print(f"   artifacts    : {config.artifacts}")
        print(f"   cleanup      : {config.cleanup}")
        print(f"   insumos      : {config.insumos}")
        print(
            f"   declared     : "
            f"{'si, ' + str(len(config.declared)) + ' caracteres' if config.declared else 'no'}"
        )

    for aviso in config.avisos:
        print(f"   AVISO: {aviso}")

    if not config.enabled:
        print()
        print("   El repositorio esta desactivado. No se haria nada mas.")
        return 0

    if config.ignore_paths:
        os.environ["AIREADME_IGNORE_PATHS"] = ",".join(config.ignore_paths)

    # ----------------------------------------------------------
    # Evidencia
    # ----------------------------------------------------------

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

    capacidades = classify_capabilities(
        archivos, repo, firmes, manifiestos
    )

    evidencia = build_evidence_json(
        repo,
        archivos,
        analisis,
        tecnologias,
        dependencies(repo),
        detect_env_vars(analisis, {}),
        capacidades,
        existing_readme(repo),
        manifiestos,
    )

    terceros = sum(1 for a in archivos if a.get("third_party"))

    print()
    print("-" * 70)
    print(" EVIDENCIA")
    print("-" * 70)
    print()
    print(f"   archivos analizados  : {len(archivos)}")
    print(f"      de terceros       : {terceros}")
    print(f"   manifiestos propios  : "
          f"{sum(1 for m in manifiestos if not m['third_party'])}")
    print(f"   dependencias         : "
          f"{sum(len(m['dependencies']) for m in manifiestos if not m['third_party'])}")
    print(f"   endpoints            : {len(evidencia['api'])}")
    print(f"   tablas               : {len(evidencia['database_tables'])}")
    print(f"   variables de entorno : "
          f"{len(evidencia['environment_variables'])}")
    print()

    if firmes:
        print("   Stack, con la procedencia de cada senal:")
        for nombre, datos in sorted(firmes.items()):
            ev = (datos.get("evidence") or [{}])[0]
            cita = ev.get("file", "")
            linea = ev.get("line")
            print(
                f"      {nombre:14s} {datos['provenance']:9s} "
                f"{cita}{':' + str(linea) if linea else ''}"
            )
    else:
        print("   Stack: ninguna tecnologia con procedencia concluyente.")

    solo_mencionadas = [
        n for n, d in tecnologias.items()
        if d.get("provenance") == "mentioned"
    ]

    if solo_mencionadas:
        print()
        print(
            "   Solo mencionadas, NO se documentarian: "
            + ", ".join(sorted(solo_mencionadas))
        )

    # ----------------------------------------------------------
    # Que haria
    # ----------------------------------------------------------

    readme_actual = existing_readme(repo)

    accion = decidir_accion(readme_actual, repo.name)

    print()
    print("-" * 70)
    print(" QUE HARIA CON EL README")
    print("-" * 70)
    print()
    print(f"   {accion.upper()}")
    print()
    print(f"   {ACCIONES.get(accion, '')}")

    huella_nueva = compute(evidencia)
    huella_previa = leer(readme_actual)

    print()

    if huella_previa and huella_previa == huella_nueva:
        print(
            "   Y ni siquiera llegaria a eso: la evidencia no ha cambiado "
            "desde"
        )
        print(
            f"   la ultima generacion (huella {huella_nueva[:12]}). No "
            "llamaria al modelo."
        )
    elif huella_previa:
        print(
            f"   La evidencia CAMBIO desde la ultima generacion: "
            f"{huella_previa[:12]} -> {huella_nueva[:12]}."
        )
    else:
        print(
            f"   El README no lleva huella todavia. La sellaria con "
            f"{huella_nueva[:12]}."
        )

    # ----------------------------------------------------------
    # Limpieza
    # ----------------------------------------------------------

    if config.cleanup:

        candidatos = find_candidates(repo, archivos, analisis)

        print()
        print("-" * 70)
        print(" CANDIDATOS A BORRAR")
        print("-" * 70)
        print()

        if not candidatos:
            print("   Ninguno.")
        else:
            datos = resumen(candidatos, len(archivos))
            print(
                f"   {datos['archivos']} archivos, "
                f"{datos['bytes'] / 1024:.0f} KB "
                f"({datos['porcentaje_archivos']}% de lo analizado)"
            )
            print()
            for candidato in candidatos[:10]:
                print(
                    f"      [{candidato['confianza']:5s}] "
                    f"{candidato['path'][:56]}"
                )
            if len(candidatos) > 10:
                print(f"      ... y {len(candidatos) - 10} mas")
            print()
            print("   Se propondrian en delete_files.md. Nada se borra.")

    # ----------------------------------------------------------
    # Artefactos
    # ----------------------------------------------------------

    propuestas = proponer(evidencia)

    print()
    print("-" * 70)
    print(" ARTEFACTOS")
    print("-" * 70)
    print()

    if not propuestas:
        print("   Ninguno: no hay evidencia suficiente.")
    elif not config.artifacts:
        print(
            f"   Habria {len(propuestas)} propuesta(s), pero "
            f"artifacts esta en false."
        )
        for propuesta in propuestas:
            print(f"      {propuesta['ruta']}: {propuesta['resumen']}")
        print()
        print(
            f"   Para verlas en el pull request, pon artifacts: true en "
            f"{ARCHIVO}."
        )
    else:
        for propuesta in propuestas:
            print(f"   {propuesta['ruta']}: {propuesta['resumen']}")

    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
