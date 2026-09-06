from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

from readme3_scanner import (
    IMPORTANT_FILES,
    MAX_API_ITEMS,
    MAX_ENV_ITEMS,
    MAX_TABLE_ITEMS,
    rel_path,
    read_text,
)

from readme3_analyzers import (
    analyze_package_json,
)


# ============================================================
# README3 - EVIDENCE
#
# Responsabilidad:
#   - README existente
#   - archivos importantes
#   - estructura
#   - API
#   - tablas
#   - contexto compacto
#   - JSON de evidencia
#
# Este módulo NO genera README.md.
#
# Genera evidencia para que posteriormente otro proceso
# pueda utilizar un LLM para redactar el README.
# ============================================================


# ============================================================
# README EXISTENTE
# ============================================================

def existing_readme(repo):

    for filename in (
        "README.md",
        "README",
        "README.txt",
    ):

        path = repo / filename

        if path.exists():

            text = read_text(path)

            if text:
                return text

    return None


def summarize_existing_readme(
    readme,
):

    if not readme:
        return []

    lines = []

    for line in readme.splitlines():

        line = line.strip()

        if not line:
            continue

        if line.startswith("!["):
            continue

        if line.startswith("[!["):
            continue

        if len(line) > 240:
            line = line[:240] + "..."

        lines.append(line)

        if len(lines) >= 35:
            break

    return lines


# ============================================================
# ARCHIVOS IMPORTANTES
# ============================================================

IMPORTANT_KEYWORDS = [
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "dockerfile",
    "docker-compose",
    "main.py",
    "app.py",
    "server.py",
    "index.js",
    "index.ts",
    "vite.config",
    "next.config",
    "angular.json",
    "manage.py",
    "routes",
    "router",
    "api",
    "database",
    "db",
    "model",
    "schema",
    "service",
    "controller",
    "config",
    "settings",
    "auth",
    "login",
    "deploy",
    "docker",
    "workflow",
]


def important_files(files):

    scored = []

    for file in files:

        path = file["path"].lower()

        score = 0

        for keyword in IMPORTANT_KEYWORDS:

            if keyword in path:
                score += 1

        if file["name"].lower() in {
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "dockerfile",
            "docker-compose.yml",
            "docker-compose.yaml",
        }:

            score += 10

        if file["name"] in IMPORTANT_FILES:
            score += 5

        if score:

            scored.append(
                (
                    score,
                    file["path"],
                )
            )

    scored.sort(
        key=lambda x: (
            -x[0],
            x[1],
        )
    )

    return [
        path
        for _, path in scored[:80]
    ]


# ============================================================
# ESTRUCTURA
# ============================================================

def structure(files):

    roots = Counter()

    for file in files:

        parts = Path(
            file["path"]
        ).parts

        if not parts:
            continue

        roots[parts[0]] += 1

    return roots


# ============================================================
# API
# ============================================================

def collect_api(analysis):

    items = []

    for path, data in analysis.items():

        python_data = data.get(
            "python",
            {},
        )

        for route in python_data.get(
            "routes",
            [],
        ):

            items.append(
                {
                    "method": route["method"],
                    "path": route["path"],
                    "file": route["file"],
                    "line": route["line"],
                    "type": "backend_route",
                }
            )

        js_data = data.get(
            "javascript",
            {},
        )

        for call in js_data.get(
            "api_calls",
            [],
        ):

            items.append(
                {
                    "method": call["method"],
                    "path": call["target"],
                    "file": call["file"],
                    "line": call["line"],
                    "type": "frontend_api_call",
                }
            )

    unique = {}

    for item in items:

        key = (
            item["method"],
            item["path"],
            item["file"],
            item["line"],
        )

        unique[key] = item

    return list(
        unique.values()
    )[:MAX_API_ITEMS]


# ============================================================
# DATABASE
# ============================================================

def collect_tables(analysis):

    items = []

    for path, data in analysis.items():

        sql = data.get(
            "sql",
            {},
        )

        items.extend(
            sql.get(
                "tables",
                [],
            )
        )

    unique = {}

    for item in items:

        key = (
            item["value"],
            item["file"],
            item["line"],
        )

        unique[key] = item

    return list(
        unique.values()
    )[:MAX_TABLE_ITEMS]


# ============================================================
# CONTEXTO COMPACTO
# ============================================================

def generate_context(
    repo,
    files,
    analysis,
    technologies,
    deps,
    env_vars,
    capabilities,
    readme,
    manifests=None,
):

    lines = []

    lines.append(
        "# PROJECT EVIDENCE CONTEXT"
    )

    lines.append(
        f"PROJECT={repo.name}"
    )

    lines.append(
        f"FILES={len(files)}"
    )

    lines.append(
        f"GENERATED={datetime.now().isoformat()}"
    )

    # --------------------------------------------------------
    # PRINCIPIOS
    # --------------------------------------------------------

    lines.extend(
        [
            "",
            "## EVIDENCE_POLICY",
            "",
            "This context contains repository evidence.",
            "Signals are not guaranteed business features.",
            "Do not infer unsupported functionality.",
            "Prefer explicit files, dependencies and source evidence.",
            "If evidence is insufficient, omit the claim.",
            "",
            "## README_RULES",
            "",
            "Generate README.md only from repository evidence.",
            "Do not invent features.",
            "Do not invent technologies.",
            "Only document technologies listed under TECH=. Each one carries",
            "its provenance and its citation. Anything under",
            "TECH_ONLY_MENTIONED is NOT evidence: do not document it.",
            "Do not invent endpoints.",
            "Do not invent database tables.",
            "Do not invent environment variables.",
            "Do not invent commands.",
            "Do not infer production architecture from filenames alone.",
            "Treat capability signals as signals, not confirmed features.",
            "Files or manifests marked [TERCEROS] are third-party code that",
            "the repository vendors. They are not what this project does.",
            "Prefer explicit source evidence.",
            "Omit unsupported sections.",
        ]
    )

    # --------------------------------------------------------
    # STACK
    # --------------------------------------------------------

    lines.extend(
        [
            "",
            "## STACK",
        ]
    )

    langs = Counter(
        file["language"]
        for file in files
        if file["language"] != "Other"
    )

    if langs:

        lines.append(
            "LANG=" +
            ",".join(
                name
                for name, _ in
                langs.most_common(15)
            )
        )

    if technologies:

        # Las tecnologias se separan por PROCEDENCIA de la evidencia.
        #
        # declared / imported / vendored son concluyentes y llevan su cita.
        # mentioned significa que el nombre aparece en algun texto y nada
        # mas: se emite aparte y marcado, para que no se documente como si
        # el proyecto usara esa tecnologia.

        firmes = []
        solo_mencionadas = []

        for name, info in sorted(technologies.items()):

            procedencia = info.get("provenance", "mentioned")

            if procedencia == "mentioned":
                solo_mencionadas.append(name)
                continue

            evidencia = (info.get("evidence") or [{}])[0]

            cita = evidencia.get("file", "")
            linea = evidencia.get("line")

            if cita and linea:
                cita = f"{cita}:{linea}"

            firmes.append(
                f"{name}[{procedencia}"
                + (f":{cita}" if cita else "")
                + "]"
            )

        if firmes:
            lines.append("TECH=" + ",".join(firmes[:25]))

        if solo_mencionadas:
            lines.extend(
                [
                    "",
                    "## TECH_ONLY_MENTIONED",
                    "",
                    "El nombre aparece en algun texto del repositorio, pero "
                    "no esta declarado en ningun manifiesto, no se importa "
                    "en el codigo y no se carga como recurso.",
                    "NO es evidencia de que el proyecto use esta tecnologia. "
                    "No la documentes.",
                    "",
                    ",".join(sorted(solo_mencionadas)[:25]),
                ]
            )

    # --------------------------------------------------------
    # DEPENDENCIAS
    # --------------------------------------------------------

    # Las dependencias se leen de los manifiestos descubiertos a cualquier
    # profundidad. Antes solo se miraba la raiz, asi que en los proyectos
    # con el front en una subcarpeta esta seccion llegaba VACIA al modelo
    # mientras se le entregaban tecnologias detectadas por regex.

    if manifests:

        lines.extend(
            [
                "",
                "## MANIFESTS",
                "",
                "Manifiestos encontrados. Son la evidencia mas fiable que",
                "existe sobre el stack: lo que el proyecto DECLARA usar.",
            ]
        )

        for manifiesto in manifests[:20]:

            marca = " [TERCEROS]" if manifiesto["third_party"] else ""

            lines.append(
                f"{manifiesto['path']} ({manifiesto['kind']}, "
                f"{len(manifiesto['dependencies'])} deps){marca}"
            )

        propios = [
            m for m in manifests if not m["third_party"]
        ]

        npm_items = [
            (d, m["path"])
            for m in propios if m["kind"] == "npm"
            for d in m["dependencies"]
        ]

        py_items = [
            (d, m["path"])
            for m in propios if m["kind"] == "python"
            for d in m["dependencies"]
        ]

        if npm_items:

            lines.extend(["", "## NPM_DEPENDENCIES"])

            lines.extend(
                f"{d['name']}@{d['version']} [{ruta}"
                + (f":{d['line']}" if d.get("line") else "")
                + "]"
                for d, ruta in npm_items[:60]
            )

        if py_items:

            lines.extend(["", "## PYTHON_DEPENDENCIES"])

            lines.extend(
                f"{d['name']}{d['version'] or ''} [{ruta}"
                + (f":{d['line']}" if d.get("line") else "")
                + "]"
                for d, ruta in py_items[:60]
            )

        scripts_items = [
            (s, m["path"])
            for m in propios
            for s in m.get("scripts", [])
        ]

        if scripts_items:

            lines.extend(["", "## NPM_SCRIPTS"])

            lines.extend(
                f"{s['name']}={s['command']} [{ruta}]"
                for s, ruta in scripts_items[:40]
            )

    else:

        # Camino anterior, por compatibilidad si se llama sin manifiestos.
        npm_deps = deps.get("npm", [])
        python_deps = deps.get("python", [])

        if npm_deps:

            lines.extend(["", "## NPM_DEPENDENCIES"])

            lines.append(
                ",".join(
                    f"{item['name']}@{item['version']}"
                    for item in npm_deps[:50]
                )
            )

        if python_deps:

            lines.extend(["", "## PYTHON_DEPENDENCIES"])

            lines.append(
                ",".join(
                    item["value"]
                    for item in python_deps[:50]
                )
            )

        package_path = repo / "package.json"

        if package_path.exists():

            package_info = analyze_package_json(
                package_path,
                repo,
            )

            scripts = package_info.get("scripts", {})

            if scripts:

                lines.extend(["", "## NPM_SCRIPTS"])

                for name, info in scripts.items():
                    lines.append(f"{name}={info['command']}")

    # --------------------------------------------------------
    # ESTRUCTURA
    # --------------------------------------------------------

    lines.extend(
        [
            "",
            "## STRUCTURE",
        ]
    )

    roots = structure(files)

    lines.append(
        "ROOTS=" +
        ",".join(
            f"{name}({count})"
            for name, count
            in roots.most_common(30)
        )
    )

    # --------------------------------------------------------
    # ARCHIVOS CLAVE
    # --------------------------------------------------------

    key_files = important_files(files)

    if key_files:

        lines.extend(
            [
                "",
                "## KEY_FILES",
                ",".join(key_files),
            ]
        )

    # --------------------------------------------------------
    # API
    # --------------------------------------------------------

    api_items = collect_api(
        analysis
    )

    if api_items:

        lines.extend(
            [
                "",
                "## API_EVIDENCE",
            ]
        )

        for item in api_items:

            lines.append(
                f"{item['method']} "
                f"{item['path']} "
                f"[{item['file']}:{item['line']}]"
            )

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    tables = collect_tables(
        analysis
    )

    if tables:

        lines.extend(
            [
                "",
                "## DATABASE_EVIDENCE",
            ]
        )

        for item in tables:

            lines.append(
                f"{item['value']} "
                f"[{item['file']}:{item['line']}]"
            )

    # --------------------------------------------------------
    # ENV
    # --------------------------------------------------------

    if env_vars:

        lines.extend(
            [
                "",
                "## ENV_EVIDENCE",
            ]
        )

        for item in env_vars[:MAX_ENV_ITEMS]:

            lines.append(
                f"{item['value']} "
                f"[{item['file']}:{item['line']}]"
            )

    # --------------------------------------------------------
    # CAPACIDADES / SEÑALES
    # --------------------------------------------------------

    if capabilities:

        lines.extend(
            [
                "",
                "## CAPABILITY_SIGNALS",
            ]
        )

        for capability, info in capabilities.items():

            lines.append(
                f"{capability} "
                f"[confidence={info['confidence']}]"
            )

            for signal in info["signals"][:8]:

                lines.append(
                    "  "
                    f"{signal['keyword']} "
                    f"[{signal['file']}:{signal['line']}]"
                )

    # --------------------------------------------------------
    # PYTHON
    # --------------------------------------------------------

    python_count = 0

    for path, data in analysis.items():

        py = data.get(
            "python"
        )

        if not py:
            continue

        classes = [
            item["name"]
            for item in py.get(
                "classes",
                []
            )
        ]

        functions = [
            item["name"]
            for item in py.get(
                "functions",
                []
            )
        ]

        imports = [
            item["value"]
            for item in py.get(
                "imports",
                []
            )
        ]

        if not (
            classes
            or functions
            or imports
        ):
            continue

        entry = path

        if classes:

            entry += (
                "|C="
                + ",".join(
                    classes[:12]
                )
            )

        if functions:

            entry += (
                "|F="
                + ",".join(
                    functions[:18]
                )
            )

        if imports:

            entry += (
                "|I="
                + ",".join(
                    imports[:12]
                )
            )

        python_count += 1

        if python_count <= 60:

            if python_count == 1:

                lines.extend(
                    [
                        "",
                        "## PYTHON",
                    ]
                )

            lines.append(entry)

    # --------------------------------------------------------
    # COMPONENTES
    # --------------------------------------------------------

    component_count = 0

    for path, data in analysis.items():

        js = data.get(
            "javascript"
        )

        if not js:
            continue

        components = [
            item["value"]
            for item in js.get(
                "components",
                []
            )
        ]

        if not components:
            continue

        component_count += 1

        if component_count == 1:

            lines.extend(
                [
                    "",
                    "## COMPONENTS",
                ]
            )

        if component_count <= 60:

            lines.append(
                path
                + ":"
                + ",".join(
                    components[:15]
                )
            )

    # --------------------------------------------------------
    # README EXISTENTE
    # --------------------------------------------------------

    readme_summary = summarize_existing_readme(
        readme
    )

    if readme_summary:

        lines.extend(
            [
                "",
                "## EXISTING_README",
            ]
        )

        lines.extend(
            readme_summary
        )

    # --------------------------------------------------------
    # DEPLOYMENT / CONFIG
    # --------------------------------------------------------

    deployment_files = []

    for file in files:

        name = file["name"].lower()
        path = file["path"].lower()

        if any(
            token in name
            or token in path
            for token in [
                "docker",
                "compose",
                "workflow",
                "deploy",
                "vercel",
                "railway",
                "render",
                "netlify",
            ]
        ):

            deployment_files.append(
                file["path"]
            )

    if deployment_files:

        lines.extend(
            [
                "",
                "## DEPLOYMENT_FILES",
            ]
        )

        lines.append(
            ",".join(
                sorted(
                    set(
                        deployment_files
                    )
                )[:50]
            )
        )

    # Las reglas ya no van aqui: se emiten al PRINCIPIO del contexto.
    #
    # Estaban al final, y el truncado a 30.000 caracteres las borraba en los
    # repositorios grandes. Medido: en COIPO_ENTREGA_PLANTA y en
    # coipo_seguimiento_madera el contexto supera ese limite, asi que
    # justamente los repositorios mas dificiles de documentar eran los que
    # llegaban al modelo SIN las reglas anti-invencion.

    return "\n".join(lines)


# ============================================================
# JSON EVIDENCE
# ============================================================

def build_evidence_json(
    repo,
    files,
    analysis,
    technologies,
    deps,
    env_vars,
    capabilities,
    readme,
    manifests=None,
):

    return {
        "metadata": {
            "repository": repo.name,
            "generated_at": datetime.now().isoformat(),
            "analyzer": "readme3",
            "version": "2.0-evidence-first",
            "file_count": len(files),
        },

        "policy": {
            "purpose": (
                "Repository evidence extraction for "
                "documentation generation."
            ),
            "important_rule": (
                "Signals do not automatically represent "
                "confirmed product capabilities."
            ),
        },

        "files": files,

        "structure": dict(
            structure(files)
        ),

        "important_files": important_files(
            files
        ),

        "technologies": technologies,

        "dependencies": deps,

        "environment_variables": env_vars,

        "api": collect_api(
            analysis
        ),

        "database_tables": collect_tables(
            analysis
        ),

        "capability_signals": capabilities,

        "analysis": analysis,

        "manifests": manifests or [],

        # Los scripts npm existian dentro de analyze_package_json pero solo
        # se renderizaban como texto y nunca entraban al JSON. Por eso
        # get_evidence_commands en validate_readme.py buscaba una clave que
        # nadie escribia y la validacion de comandos era codigo muerto.
        "npm_scripts": [
            dict(script, manifest=manifiesto["path"])
            for manifiesto in (manifests or [])
            if not manifiesto.get("third_party")
            for script in manifiesto.get("scripts", [])
        ],

        "existing_readme": {
            "exists": bool(readme),
            "summary": summarize_existing_readme(
                readme
            ),
        },
    }