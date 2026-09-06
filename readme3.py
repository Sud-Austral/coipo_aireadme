from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


# ============================================================
# README3 - EVIDENCE-FIRST REPOSITORY ANALYZER
#
# ORQUESTADOR PRINCIPAL
#
# Este archivo mantiene la referencia del flujo completo.
#
# Lógica separada en:
#
#   readme3_scanner.py
#       - configuración
#       - utilidades
#       - escaneo
#
#   readme3_analyzers.py
#       - análisis Python
#       - análisis JS/TS
#       - análisis SQL
#       - dependencias
#       - tecnologías
#       - variables de entorno
#       - señales funcionales
#
#   readme3_evidence.py
#       - consolidación
#       - API
#       - tablas
#       - estructura
#       - contexto compacto
#       - JSON de evidencia
#
#
# PRINCIPIO:
#
#   DETECCIÓN != CONCLUSIÓN
#
# El analizador NO decide qué significa el software.
# El analizador recopila evidencia.
#
# El LLM posteriormente redacta el README.
# ============================================================


# ============================================================
# IMPORTS DE LOS MÓDULOS
# ============================================================

from readme3_scanner import scan

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


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # VALIDACIÓN DE ARGUMENTOS
    # --------------------------------------------------------

    if len(sys.argv) != 2:

        print()

        print(
            'Uso: python readme3.py "RUTA_REPOSITORIO"'
        )

        print()

        sys.exit(1)

    repo = Path(
        sys.argv[1]
    ).resolve()

    # --------------------------------------------------------
    # VALIDACIÓN DEL REPOSITORIO
    # --------------------------------------------------------

    if not repo.exists():

        print(
            f"ERROR: no existe:\n{repo}"
        )

        sys.exit(1)

    if not repo.is_dir():

        print(
            f"ERROR: no es un directorio:\n{repo}"
        )

        sys.exit(1)

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    print()

    print("=" * 70)

    print(
        " README3 - EVIDENCE-FIRST REPOSITORY ANALYZER"
    )

    print("=" * 70)

    print()

    print(
        f"Repositorio: {repo}"
    )

    # ========================================================
    # 1. SCAN
    # ========================================================

    print()

    print("[1/6] Escaneando...")

    files = scan(repo)

    print(
        f"      {len(files)} archivos."
    )

    # ========================================================
    # 2. ANALYSIS
    # ========================================================

    print(
        "[2/6] Analizando arquitectura..."
    )

    analysis = analyze_files(
        repo,
        files,
    )

    # ========================================================
    # 3. TECHNOLOGIES
    # ========================================================

    print(
        "[3/6] Detectando tecnologías..."
    )

    # Manifiestos a cualquier profundidad. En los proyectos con el front en
    # una subcarpeta, esto es la diferencia entre entregar la lista real de
    # dependencias o entregar una seccion vacia.
    manifests = discover_manifests(
        repo,
        files,
    )

    # El detector por regex se conserva, pero degradado: alimenta el nivel
    # "mentioned", que se emite marcado como no concluyente.
    mentioned = detect_technologies(
        files,
        repo,
    )

    technologies = classify_technologies(
        analysis,
        manifests,
        files,
        repo,
        mentioned=mentioned,
    )

    print(
        f"      {len(manifests)} manifiestos, "
        f"{len(concluyentes(technologies))} tecnologías con procedencia."
    )

    # ========================================================
    # 4. DEPENDENCIES / CONFIGURATION
    # ========================================================

    print(
        "[4/6] Detectando dependencias y configuración..."
    )

    deps = dependencies(
        repo
    )

    env_vars = detect_env_vars(
        analysis,
        {},
    )

    # Las señales de capacidad exigen corroboración estructural: una
    # tecnología con procedencia o una dependencia declarada. Sin eso, una
    # palabra suelta en un comentario bastaba para atribuir cartografía o
    # machine learning a cualquier repositorio.
    capabilities = classify_capabilities(
        files,
        repo,
        concluyentes(technologies),
        manifests,
    )

    readme = existing_readme(
        repo
    )

    # ========================================================
    # 5. GENERATE EVIDENCE
    # ========================================================

    print(
        "[5/6] Generando contexto compacto..."
    )

    context = generate_context(
        repo,
        files,
        analysis,
        technologies,
        deps,
        env_vars,
        capabilities,
        readme,
        manifests,
    )

    evidence = build_evidence_json(
        repo,
        files,
        analysis,
        technologies,
        deps,
        env_vars,
        capabilities,
        readme,
        manifests,
    )

    # ========================================================
    # 6. SAVE
    # ========================================================

    print(
        "[6/6] Guardando evidencia..."
    )

    output_dir = (
        repo / "readme_context"
    )

    output_dir.mkdir(
        exist_ok=True
    )

    context_file = (
        output_dir
        / "README_CONTEXT_ULTRA.md"
    )

    evidence_file = (
        output_dir
        / "README_EVIDENCE.json"
    )

    analysis_file = (
        output_dir
        / "repository_analysis.json"
    )

    # --------------------------------------------------------
    # CONTEXTO
    # --------------------------------------------------------

    context_file.write_text(
        context,
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # EVIDENCIA
    # --------------------------------------------------------

    evidence_file.write_text(
        json.dumps(
            evidence,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # ANÁLISIS
    # --------------------------------------------------------

    analysis_file.write_text(
        json.dumps(
            {
                "repository": repo.name,
                "generated_at": (
                    datetime.now().isoformat()
                ),
                "analysis": analysis,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    chars = len(context)

    # ========================================================
    # RESUMEN
    # ========================================================

    print()

    print("=" * 70)

    print(
        " EVIDENCIA GENERADA"
    )

    print("=" * 70)

    print()

    print(
        f"Archivos             : {len(files):,}"
    )

    print(
        f"Tecnologías          : {len(technologies):,}"
    )

    print(
        f"Variables entorno    : {len(env_vars):,}"
    )

    print(
        f"Endpoints            : "
        f"{len(evidence['api']):,}"
    )

    print(
        f"Tablas detectadas    : "
        f"{len(evidence['database_tables']):,}"
    )

    print(
        f"Señales funcionales  : "
        f"{len(capabilities):,}"
    )

    print()

    print(
        "Contexto:"
        f"\n  {context_file}"
    )

    print()

    print(
        "Evidencia:"
        f"\n  {evidence_file}"
    )

    print()

    print(
        "Análisis:"
        f"\n  {analysis_file}"
    )

    print()

    print(
        f"Contexto: {chars:,} caracteres"
    )

    print(
        f"Tokens estimados: {chars // 4:,}"
    )

    print()

    print(
        "README3 terminado correctamente."
    )

    print()


# ============================================================
# ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    main()