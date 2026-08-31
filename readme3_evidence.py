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

        tech_values = []

        for name, info in sorted(
            technologies.items()
        ):

            tech_values.append(
                f"{name}[{info['confidence']}]"
            )

        lines.append(
            "TECH=" +
            ",".join(
                tech_values[:25]
            )
        )

    # --------------------------------------------------------
    # DEPENDENCIAS
    # --------------------------------------------------------

    npm_deps = deps.get(
        "npm",
        []
    )

    python_deps = deps.get(
        "python",
        []
    )

    if npm_deps:

        lines.extend(
            [
                "",
                "## NPM_DEPENDENCIES",
            ]
        )

        lines.append(
            ",".join(
                f"{item['name']}@{item['version']}"
                for item in npm_deps[:50]
            )
        )

    if python_deps:

        lines.extend(
            [
                "",
                "## PYTHON_DEPENDENCIES",
            ]
        )

        lines.append(
            ",".join(
                item["value"]
                for item in python_deps[:50]
            )
        )

    # --------------------------------------------------------
    # SCRIPTS
    # --------------------------------------------------------

    package_path = repo / "package.json"

    if package_path.exists():

        package_info = analyze_package_json(
            package_path,
            repo,
        )

        scripts = package_info.get(
            "scripts",
            {},
        )

        if scripts:

            lines.extend(
                [
                    "",
                    "## NPM_SCRIPTS",
                ]
            )

            for name, info in scripts.items():

                lines.append(
                    f"{name}={info['command']}"
                )

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

    # --------------------------------------------------------
    # REGLAS LLM
    # --------------------------------------------------------

    lines.extend(
        [
            "",
            "## README_RULES",
            "",
            "Generate README.md only from repository evidence.",
            "Do not invent features.",
            "Do not invent technologies.",
            "Do not invent endpoints.",
            "Do not invent database tables.",
            "Do not invent environment variables.",
            "Do not invent commands.",
            "Do not infer production architecture from filenames alone.",
            "Treat capability signals as signals, not confirmed features.",
            "Prefer explicit source evidence.",
            "Omit unsupported sections.",
        ]
    )

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

        "existing_readme": {
            "exists": bool(readme),
            "summary": summarize_existing_readme(
                readme
            ),
        },
    }