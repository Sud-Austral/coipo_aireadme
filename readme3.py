from __future__ import annotations

import ast
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


# ============================================================
# README3 - EVIDENCE-FIRST REPOSITORY ANALYZER
#
# Objetivo:
#   Analizar un repositorio SIN LLM y generar:
#
#   1. README_CONTEXT_ULTRA.md
#      Contexto compacto para generación.
#
#   2. README_EVIDENCE.json
#      Evidencia estructurada y trazable.
#
# Principio:
#
#   El analizador NO decide qué significa el software.
#   El analizador recopila evidencia.
#
#   El LLM posteriormente redacta.
#
# Regla:
#
#   DETECCIÓN != CONCLUSIÓN
# ============================================================


# ============================================================
# CONFIGURACIÓN
# ============================================================

IGNORED_DIRS = {
    ".git",
    ".svn",
    ".hg",
    ".idea",
    ".vscode",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    "coverage",
    ".next",
    ".nuxt",
    ".cache",
    "vendor",
    "site-packages",
}

IGNORED_FILES = {
    ".DS_Store",
    "Thumbs.db",
}

TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".php",
    ".rb",
    ".swift",
    ".kt",
    ".kts",
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".sql",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".md",
    ".txt",
    ".sh",
    ".bat",
    ".ps1",
}

MAX_FILE_SIZE = 5 * 1024 * 1024

MAX_CONTEXT_FILES = 500

MAX_API_ITEMS = 150

MAX_ENV_ITEMS = 100

MAX_TABLE_ITEMS = 150


# ============================================================
# ARCHIVOS IMPORTANTES
# ============================================================

IMPORTANT_FILES = {
    "README.md",
    "README",
    "README.txt",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Makefile",
    ".env.example",
    ".env.dev.example",
    ".env.production.example",
}


# ============================================================
# UTILIDADES
# ============================================================

def read_text(path: Path) -> str | None:
    try:
        return path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except Exception:
        return None


def rel_path(path: Path, repo: Path) -> str:
    return path.relative_to(repo).as_posix()


def language(path: Path) -> str:
    mapping = {
        ".py": "Python",
        ".js": "JavaScript",
        ".jsx": "React",
        ".ts": "TypeScript",
        ".tsx": "React+TS",
        ".java": "Java",
        ".c": "C",
        ".cpp": "C++",
        ".h": "C/C++",
        ".hpp": "C++",
        ".cs": "C#",
        ".go": "Go",
        ".rs": "Rust",
        ".php": "PHP",
        ".rb": "Ruby",
        ".swift": "Swift",
        ".kt": "Kotlin",
        ".kts": "Kotlin",
        ".html": "HTML",
        ".htm": "HTML",
        ".css": "CSS",
        ".scss": "SCSS",
        ".sass": "SASS",
        ".less": "LESS",
        ".sql": "SQL",
        ".json": "JSON",
        ".yaml": "YAML",
        ".yml": "YAML",
        ".toml": "TOML",
        ".ini": "INI",
        ".cfg": "Config",
        ".md": "Markdown",
        ".txt": "Text",
        ".sh": "Shell",
        ".bat": "Batch",
        ".ps1": "PowerShell",
    }

    return mapping.get(
        path.suffix.lower(),
        "Other",
    )


def add_unique(
    collection: list,
    value,
):
    if value not in collection:
        collection.append(value)


def evidence_item(
    value,
    file,
    line=None,
    evidence_type=None,
    confidence="high",
):
    item = {
        "value": value,
        "file": file,
        "confidence": confidence,
    }

    if line is not None:
        item["line"] = line

    if evidence_type:
        item["type"] = evidence_type

    return item


def line_number(text: str, position: int) -> int:
    return text.count(
        "\n",
        0,
        position,
    ) + 1


# ============================================================
# ESCANEO
# ============================================================

def scan(repo: Path) -> list[dict]:

    result = []

    for root, dirs, files in os.walk(repo):

        dirs[:] = [
            d
            for d in dirs
            if d not in IGNORED_DIRS
        ]

        for filename in files:

            if filename in IGNORED_FILES:
                continue

            path = Path(root) / filename

            try:
                size = path.stat().st_size
            except OSError:
                continue

            result.append(
                {
                    "path": rel_path(
                        path,
                        repo,
                    ),
                    "name": filename,
                    "ext": path.suffix.lower(),
                    "language": language(path),
                    "size": size,
                    "text": (
                        path.suffix.lower()
                        in TEXT_EXTENSIONS
                    ),
                    "important": (
                        filename in IMPORTANT_FILES
                    ),
                }
            )

    return result


# ============================================================
# PYTHON
# ============================================================

def analyze_python(path: Path, repo: Path):

    text = read_text(path)

    if not text:
        return {}

    relative = rel_path(
        path,
        repo,
    )

    result = {
        "imports": [],
        "functions": [],
        "classes": [],
        "routes": [],
        "env_vars": [],
    }

    try:
        tree = ast.parse(text)
    except Exception:
        return result

    lines = text.splitlines()

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            for item in node.names:

                result["imports"].append(
                    {
                        "value": item.name,
                        "line": node.lineno,
                    }
                )

        elif isinstance(node, ast.ImportFrom):

            if node.module:

                result["imports"].append(
                    {
                        "value": node.module,
                        "line": node.lineno,
                    }
                )

        elif isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):

            result["functions"].append(
                {
                    "name": node.name,
                    "line": node.lineno,
                }
            )

        elif isinstance(
            node,
            ast.ClassDef,
        ):

            result["classes"].append(
                {
                    "name": node.name,
                    "line": node.lineno,
                }
            )

    # --------------------------------------------------------
    # Flask / FastAPI / generic Python routes
    # --------------------------------------------------------

    route_patterns = [
        re.compile(
            r'@\w+\.(get|post|put|patch|delete|route)'
            r'\s*\(\s*[\'"]([^\'"]+)',
            re.IGNORECASE,
        ),
        re.compile(
            r'@app\.(get|post|put|patch|delete)'
            r'\s*\(\s*[\'"]([^\'"]+)',
            re.IGNORECASE,
        ),
        re.compile(
            r'@router\.(get|post|put|patch|delete)'
            r'\s*\(\s*[\'"]([^\'"]+)',
            re.IGNORECASE,
        ),
    ]

    for pattern in route_patterns:

        for match in pattern.finditer(text):

            method = match.group(1).upper()
            route = match.group(2)

            result["routes"].append(
                {
                    "method": method,
                    "path": route,
                    "line": line_number(
                        text,
                        match.start(),
                    ),
                    "file": relative,
                }
            )

    # --------------------------------------------------------
    # Environment variables
    # --------------------------------------------------------

    env_patterns = [
        re.compile(
            r'os\.getenv\s*\(\s*[\'"]([A-Z][A-Z0-9_]+)',
        ),
        re.compile(
            r'os\.environ\.get\s*\(\s*[\'"]([A-Z][A-Z0-9_]+)',
        ),
        re.compile(
            r'os\.environ\[\s*[\'"]([A-Z][A-Z0-9_]+)',
        ),
    ]

    for pattern in env_patterns:

        for match in pattern.finditer(text):

            result["env_vars"].append(
                {
                    "value": match.group(1),
                    "line": line_number(
                        text,
                        match.start(),
                    ),
                    "file": relative,
                }
            )

    return result


# ============================================================
# JAVASCRIPT / TYPESCRIPT
# ============================================================

def analyze_js(path: Path, repo: Path):

    text = read_text(path)

    if not text:
        return {}

    relative = rel_path(
        path,
        repo,
    )

    result = {
        "imports": [],
        "exports": [],
        "components": [],
        "api_calls": [],
        "routes": [],
        "env_vars": [],
    }

    # --------------------------------------------------------
    # Imports
    # --------------------------------------------------------

    import_pattern = re.compile(
        r'import\s+'
        r'(?:[\s\S]*?\s+from\s+)?'
        r'[\'"]([^\'"]+)[\'"]'
    )

    for match in import_pattern.finditer(text):

        result["imports"].append(
            {
                "value": match.group(1),
                "line": line_number(
                    text,
                    match.start(),
                ),
            }
        )

    # --------------------------------------------------------
    # Exports
    # --------------------------------------------------------

    export_pattern = re.compile(
        r'export\s+'
        r'(?:default\s+)?'
        r'(?:function|class|const|let|var)?\s*'
        r'([A-Za-z_$][\w$]*)?'
    )

    for match in export_pattern.finditer(text):

        if match.group(1):

            result["exports"].append(
                {
                    "value": match.group(1),
                    "line": line_number(
                        text,
                        match.start(),
                    ),
                }
            )

    # --------------------------------------------------------
    # React components
    # --------------------------------------------------------

    component_patterns = [
        re.compile(
            r'(?:function|const)\s+'
            r'([A-Z][A-Za-z0-9_$]*)'
        ),
    ]

    for pattern in component_patterns:

        for match in pattern.finditer(text):

            result["components"].append(
                {
                    "value": match.group(1),
                    "line": line_number(
                        text,
                        match.start(),
                    ),
                }
            )

    # --------------------------------------------------------
    # fetch()
    # --------------------------------------------------------

    fetch_pattern = re.compile(
        r'fetch\s*\(\s*'
        r'[\'"`]([^\'"`]+)'
    )

    for match in fetch_pattern.finditer(text):

        result["api_calls"].append(
            {
                "method": "FETCH",
                "target": match.group(1),
                "line": line_number(
                    text,
                    match.start(),
                ),
                "file": relative,
            }
        )

    # --------------------------------------------------------
    # axios
    # --------------------------------------------------------

    axios_pattern = re.compile(
        r'axios\.(get|post|put|patch|delete)'
        r'\s*\(\s*[\'"`]([^\'"`]+)',
        re.IGNORECASE,
    )

    for match in axios_pattern.finditer(text):

        result["api_calls"].append(
            {
                "method": match.group(1).upper(),
                "target": match.group(2),
                "line": line_number(
                    text,
                    match.start(),
                ),
                "file": relative,
            }
        )

    # --------------------------------------------------------
    # React Router / generic routes
    # --------------------------------------------------------

    route_pattern = re.compile(
        r'(?:path|route)\s*[:=]\s*'
        r'[\'"]([^\'"]+)[\'"]'
    )

    for match in route_pattern.finditer(text):

        result["routes"].append(
            {
                "path": match.group(1),
                "line": line_number(
                    text,
                    match.start(),
                ),
                "file": relative,
            }
        )

    # --------------------------------------------------------
    # VITE environment variables
    # --------------------------------------------------------

    env_pattern = re.compile(
        r'import\.meta\.env\.([A-Z][A-Z0-9_]+)'
    )

    for match in env_pattern.finditer(text):

        result["env_vars"].append(
            {
                "value": match.group(1),
                "line": line_number(
                    text,
                    match.start(),
                ),
                "file": relative,
            }
        )

    return result


# ============================================================
# SQL
# ============================================================

def analyze_sql(path: Path, repo: Path):

    text = read_text(path)

    if not text:
        return {}

    relative = rel_path(
        path,
        repo,
    )

    result = {
        "tables": [],
        "operations": {},
    }

    table_patterns = [
        re.compile(
            r'CREATE\s+TABLE\s+'
            r'(?:IF\s+NOT\s+EXISTS\s+)?'
            r'["`]?([A-Za-z_][\w$.-]*)',
            re.IGNORECASE,
        ),
        re.compile(
            r'\b(?:FROM|JOIN|INTO|UPDATE)\s+'
            r'["`]?([A-Za-z_][\w$.-]*)',
            re.IGNORECASE,
        ),
    ]

    for pattern in table_patterns:

        for match in pattern.finditer(text):

            result["tables"].append(
                {
                    "value": match.group(1),
                    "file": relative,
                    "line": line_number(
                        text,
                        match.start(),
                    ),
                }
            )

    for operation in (
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
        "CREATE",
        "ALTER",
        "DROP",
    ):
        result["operations"][operation] = len(
            re.findall(
                rf"\b{operation}\b",
                text,
                re.IGNORECASE,
            )
        )

    return result


# ============================================================
# PACKAGE.JSON
# ============================================================

def analyze_package_json(
    path: Path,
    repo: Path,
):

    text = read_text(path)

    if not text:
        return {}

    try:
        data = json.loads(text)
    except Exception:
        return {}

    relative = rel_path(
        path,
        repo,
    )

    dependencies = {}

    for section in (
        "dependencies",
        "devDependencies",
        "peerDependencies",
    ):
        for name, version in data.get(
            section,
            {},
        ).items():

            dependencies[name] = {
                "version": version,
                "section": section,
                "file": relative,
            }

    scripts = {}

    for name, command in data.get(
        "scripts",
        {},
    ).items():

        scripts[name] = {
            "command": command,
            "file": relative,
        }

    return {
        "name": data.get("name"),
        "version": data.get("version"),
        "description": data.get("description"),
        "dependencies": dependencies,
        "scripts": scripts,
    }


# ============================================================
# REQUIREMENTS
# ============================================================

def analyze_requirements(
    path: Path,
    repo: Path,
):

    text = read_text(path)

    if not text:
        return []

    relative = rel_path(
        path,
        repo,
    )

    result = []

    for index, raw in enumerate(
        text.splitlines(),
        start=1,
    ):

        line = raw.strip()

        if not line or line.startswith("#"):
            continue

        result.append(
            {
                "value": line,
                "file": relative,
                "line": index,
            }
        )

    return result


# ============================================================
# TECNOLOGÍAS
# ============================================================

TECHNOLOGIES = {
    "React": [
        r"\breact\b",
    ],
    "Vite": [
        r"\bvite\b",
    ],
    "Vue": [
        r"\bvue\b",
    ],
    "Angular": [
        r"@angular/",
    ],
    "Flask": [
        r"\bflask\b",
    ],
    "FastAPI": [
        r"\bfastapi\b",
    ],
    "Django": [
        r"\bdjango\b",
    ],
    "Express": [
        r"\bexpress\b",
    ],
    "Node.js": [
        r"\bnode\b",
    ],
    "PostgreSQL": [
        r"\bpostgresql\b",
        r"\bpsycopg\b",
    ],
    "MySQL": [
        r"\bmysql\b",
    ],
    "SQLite": [
        r"\bsqlite\b",
    ],
    "MongoDB": [
        r"\bmongodb\b",
        r"\bmongoose\b",
    ],
    "Redis": [
        r"\bredis\b",
    ],
    "Docker": [
        r"\bdocker\b",
    ],
    "Leaflet": [
        r"\bleaflet\b",
    ],
    "Mapbox": [
        r"\bmapbox\b",
    ],
    "Tailwind": [
        r"\btailwind\b",
    ],
    "Pandas": [
        r"\bpandas\b",
    ],
    "NumPy": [
        r"\bnumpy\b",
    ],
    "OpenCV": [
        r"\bcv2\b",
        r"\bopencv\b",
    ],
    "YOLO": [
        r"\byolo\b",
    ],
    "SQLAlchemy": [
        r"\bsqlalchemy\b",
    ],
}


def detect_technologies(
    files,
    repo,
):

    result = {}

    priority_files = {
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
    }

    for name, patterns in TECHNOLOGIES.items():

        matches = []

        for file in files:

            if not file["text"]:
                continue

            if file["size"] > MAX_FILE_SIZE:
                continue

            path = repo / file["path"]

            text = read_text(path)

            if not text:
                continue

            weight = (
                10
                if file["name"] in priority_files
                else 1
            )

            for pattern in patterns:

                match = re.search(
                    pattern,
                    text,
                    re.IGNORECASE,
                )

                if match:

                    matches.append(
                        {
                            "file": file["path"],
                            "line": line_number(
                                text,
                                match.start(),
                            ),
                            "weight": weight,
                            "pattern": pattern,
                        }
                    )

        if matches:

            total_weight = sum(
                item["weight"]
                for item in matches
            )

            if total_weight >= 10:
                confidence = "high"
            elif total_weight >= 3:
                confidence = "medium"
            else:
                confidence = "low"

            result[name] = {
                "confidence": confidence,
                "evidence": matches[:20],
            }

    return result


# ============================================================
# DEPENDENCIAS
# ============================================================

def dependencies(repo):

    result = {
        "npm": [],
        "python": [],
    }

    package = repo / "package.json"

    if package.exists():

        data = analyze_package_json(
            package,
            repo,
        )

        for name, info in data.get(
            "dependencies",
            {},
        ).items():

            result["npm"].append(
                {
                    "name": name,
                    "version": info["version"],
                    "section": info["section"],
                    "file": info["file"],
                }
            )

    for filename in (
        "requirements.txt",
        "requirements-dev.txt",
    ):

        path = repo / filename

        if not path.exists():
            continue

        result["python"].extend(
            analyze_requirements(
                path,
                repo,
            )
        )

    return result


# ============================================================
# VARIABLES DE ENTORNO
# ============================================================

def detect_env_vars(
    analysis,
    package_analysis,
):

    result = []

    for path, data in analysis.items():

        for item in data.get(
            "python",
            {},
        ).get(
            "env_vars",
            [],
        ):

            result.append(
                {
                    "value": item["value"],
                    "file": item["file"],
                    "line": item["line"],
                    "type": "python",
                }
            )

        for item in data.get(
            "javascript",
            {},
        ).get(
            "env_vars",
            [],
        ):

            result.append(
                {
                    "value": item["value"],
                    "file": item["file"],
                    "line": item["line"],
                    "type": "javascript",
                }
            )

    unique = {}

    for item in result:

        key = item["value"]

        if key not in unique:
            unique[key] = item

    return sorted(
        unique.values(),
        key=lambda x: x["value"],
    )


# ============================================================
# CAPACIDADES
#
# IMPORTANTE:
#
# Esto NO declara funcionalidades.
#
# Solo registra señales.
# ============================================================

CAPABILITY_SIGNALS = {

    "Autenticación": [
        "login",
        "logout",
        "auth",
        "jwt",
        "token",
        "authenticate",
    ],

    "Mapas / cartografía": [
        "leaflet",
        "mapbox",
        "cartografia",
        "mapa",
    ],

    "Exportación": [
        "export",
        "exportar",
        "csv",
        "xlsx",
        "excel",
    ],

    "Carga de archivos": [
        "upload",
        "archivo",
        "file",
        "document",
    ],

    "Reportes / analítica": [
        "report",
        "reporte",
        "dashboard",
        "analytics",
        "estadistica",
    ],

    "Procesamiento de datos": [
        "pandas",
        "numpy",
        "dataframe",
        "etl",
    ],

    "IA / Machine Learning": [
        "tensorflow",
        "pytorch",
        "torch",
        "yolo",
        "machine learning",
    ],
}


def detect_capabilities(
    files,
    repo,
):

    result = {}

    for capability, keywords in (
        CAPABILITY_SIGNALS.items()
    ):

        matches = []

        for file in files:

            if not file["text"]:
                continue

            if file["size"] > 500_000:
                continue

            path = repo / file["path"]

            text = read_text(path)

            if not text:
                continue

            lower_text = text.lower()

            for keyword in keywords:

                start = lower_text.find(
                    keyword.lower()
                )

                if start == -1:
                    continue

                matches.append(
                    {
                        "keyword": keyword,
                        "file": file["path"],
                        "line": line_number(
                            text,
                            start,
                        ),
                    }
                )

        if matches:

            unique_files = {
                item["file"]
                for item in matches
            }

            if len(unique_files) >= 3:
                confidence = "medium"
            else:
                confidence = "low"

            result[capability] = {
                "confidence": confidence,
                "signals": matches[:20],
            }

    return result


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
# ANÁLISIS DE ARCHIVOS
# ============================================================

def analyze_files(
    repo,
    files,
):

    analysis = {}

    for file in files:

        if not file["text"]:
            continue

        if file["size"] > MAX_FILE_SIZE:
            continue

        path = repo / file["path"]

        data = {}

        if file["language"] == "Python":

            data["python"] = analyze_python(
                path,
                repo,
            )

        elif file["language"] in {
            "JavaScript",
            "React",
            "TypeScript",
            "React+TS",
        }:

            data["javascript"] = analyze_js(
                path,
                repo,
            )

        elif file["language"] == "SQL":

            data["sql"] = analyze_sql(
                path,
                repo,
            )

        if data:
            analysis[file["path"]] = data

    return analysis


# ============================================================
# API RESUMEN
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

        for name, info in (
            sorted(
                technologies.items()
            )
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

    package_path = (
        repo / "package.json"
    )

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

            for name, info in (
                scripts.items()
            ):
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

    key_files = important_files(
        files
    )

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

        for capability, info in (
            capabilities.items()
        ):

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

            lines.append(
                entry
            )

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

    return "\n".join(
        lines
    )


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


# ============================================================
# MAIN
# ============================================================

def main():

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

    # --------------------------------------------------------
    # 1
    # --------------------------------------------------------

    print()
    print("[1/6] Escaneando...")

    files = scan(
        repo
    )

    print(
        f"      {len(files)} archivos."
    )

    # --------------------------------------------------------
    # 2
    # --------------------------------------------------------

    print(
        "[2/6] Analizando arquitectura..."
    )

    analysis = analyze_files(
        repo,
        files,
    )

    # --------------------------------------------------------
    # 3
    # --------------------------------------------------------

    print(
        "[3/6] Detectando tecnologías..."
    )

    technologies = detect_technologies(
        files,
        repo,
    )

    # --------------------------------------------------------
    # 4
    # --------------------------------------------------------

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

    capabilities = detect_capabilities(
        files,
        repo,
    )

    readme = existing_readme(
        repo
    )

    # --------------------------------------------------------
    # 5
    # --------------------------------------------------------

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
    )

    # --------------------------------------------------------
    # 6
    # --------------------------------------------------------

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

    context_file.write_text(
        context,
        encoding="utf-8",
    )

    evidence_file.write_text(
        json.dumps(
            evidence,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

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

    # --------------------------------------------------------
    # RESUMEN
    # --------------------------------------------------------

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
        f"Endpoints             : "
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
        f"Contexto:"
        f"\n  {context_file}"
    )

    print()

    print(
        f"Evidencia:"
        f"\n  {evidence_file}"
    )

    print()

    print(
        f"Análisis:"
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


if __name__ == "__main__":
    main()