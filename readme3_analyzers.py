from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from readme3_scanner import (
    MAX_FILE_SIZE,
    line_number,
    read_text,
    rel_path,
)


# ============================================================
# README3 - ANALYZERS
#
# Responsabilidad:
#   - Python
#   - JavaScript / TypeScript
#   - SQL
#   - package.json
#   - requirements.txt
#   - tecnologías
#   - dependencias
#   - variables de entorno
#   - señales funcionales
#
# Principio:
#
#   DETECCIÓN != CONCLUSIÓN
#
# Este módulo recopila señales.
# No determina qué significa el software.
# ============================================================


# ============================================================
# PYTHON
# ============================================================

def analyze_python(path: Path, repo: Path):

    text = read_text(path)

    if not text:
        return {}

    relative = rel_path(path, repo)

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

        elif isinstance(node, ast.ClassDef):

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
            r'@(\w+)\.(get|post|put|patch|delete|route)'
            r'\s*\(\s*[\'"]([^\'"]+)',
            re.IGNORECASE,
        ),
    ]

    for pattern in route_patterns:

        for match in pattern.finditer(text):

            method = match.group(2).upper()
            route = match.group(3)

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
            r'os\.getenv\s*\(\s*[\'"]([A-Z][A-Z0-9_]*)[\'"]'
        ),
        re.compile(
            r'os\.environ\.get\s*\(\s*[\'"]([A-Z][A-Z0-9_]*)[\'"]'
        ),
        re.compile(
            r'os\.environ\[\s*[\'"]([A-Z][A-Z0-9_]*)[\'"]'
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

    relative = rel_path(path, repo)

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

    import_patterns = [
        re.compile(
            r'import\s+(?:[\s\S]*?\s+from\s+)?[\'"]([^\'"]+)[\'"]'
        ),
        re.compile(
            r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
        ),
    ]

    for pattern in import_patterns:

        for match in pattern.finditer(text):

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
        r'fetch\s*\(\s*[\'"`]([^\'"`]+)'
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
        r'(?:path|route)\s*[:=]\s*[\'"]([^\'"]+)[\'"]'
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
        r'import\.meta\.env\.([A-Z][A-Z0-9_]*)'
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

    relative = rel_path(path, repo)

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

    relative = rel_path(path, repo)

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

    relative = rel_path(path, repo)

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
# VARIABLES DE ENTORNO
# ============================================================

def detect_env_vars(
    analysis,
    package_analysis=None,
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
# CAPACIDADES / SEÑALES
#
# IMPORTANTE:
#
# Esto NO declara funcionalidades.
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

    for capability, keywords in CAPABILITY_SIGNALS.items():

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