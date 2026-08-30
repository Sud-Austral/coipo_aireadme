import ast
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


# ============================================================
# README3 - HIGH QUALITY COMPACT CONTEXT
#
# Objetivo:
#   Analizar un repositorio SIN LLM y generar un contexto
#   compacto pero rico en evidencia para que otro LLM
#   genere un README.md de alta calidad.
#
# Diseño:
#   - Prioriza información arquitectónica útil.
#   - Elimina ruido.
#   - No incluye código fuente completo.
#   - No inventa funcionalidades.
#   - Objetivo aproximado: 2.500-3.500 tokens.
# ============================================================


IGNORED_DIRS = {
    ".git", ".svn", ".hg",
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
    ".idea",
    ".vscode",
    "site-packages",
}

IGNORED_FILES = {
    ".DS_Store",
    "Thumbs.db",
}

TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".go", ".rs", ".php", ".rb",
    ".swift", ".kt", ".kts",
    ".html", ".htm",
    ".css", ".scss", ".sass", ".less",
    ".sql",
    ".json", ".yaml", ".yml", ".toml",
    ".ini", ".cfg",
    ".md", ".txt",
    ".sh", ".bat", ".ps1",
}

MAX_FILE_SIZE = 5 * 1024 * 1024


# ============================================================
# UTILIDADES
# ============================================================

def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="latin-1")
        except Exception:
            return None
    except Exception:
        return None


def rel_path(path, repo):
    return str(path.relative_to(repo)).replace("\\", "/")


def language(path):
    mapping = {
        ".py": "Python",
        ".js": "JavaScript",
        ".jsx": "React",
        ".ts": "TypeScript",
        ".tsx": "React+TS",
        ".java": "Java",
        ".c": "C",
        ".cpp": "C++",
        ".cs": "C#",
        ".go": "Go",
        ".rs": "Rust",
        ".php": "PHP",
        ".rb": "Ruby",
        ".swift": "Swift",
        ".kt": "Kotlin",
        ".html": "HTML",
        ".htm": "HTML",
        ".css": "CSS",
        ".scss": "SCSS",
        ".sass": "SASS",
        ".sql": "SQL",
        ".json": "JSON",
        ".yaml": "YAML",
        ".yml": "YAML",
        ".toml": "TOML",
        ".md": "Markdown",
        ".sh": "Shell",
        ".bat": "Batch",
        ".ps1": "PowerShell",
    }

    return mapping.get(path.suffix.lower(), "Other")


def clean_name(value):
    value = re.sub(r"\s+", " ", value)
    return value.strip()


# ============================================================
# ESCANEO
# ============================================================

def scan(repo):

    result = []

    for root, dirs, files in os.walk(repo):

        dirs[:] = [
            d for d in dirs
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

            result.append({
                "path": rel_path(path, repo),
                "name": filename,
                "ext": path.suffix.lower(),
                "language": language(path),
                "size": size,
                "text": path.suffix.lower() in TEXT_EXTENSIONS,
            })

    return result


# ============================================================
# PYTHON
# ============================================================

def analyze_python(path):

    text = read_text(path)

    if not text:
        return {}

    result = {
        "imports": [],
        "functions": [],
        "classes": [],
        "routes": [],
    }

    try:
        tree = ast.parse(text)
    except Exception:
        return result

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            for item in node.names:
                result["imports"].append(item.name)

        elif isinstance(node, ast.ImportFrom):

            if node.module:
                result["imports"].append(node.module)

        elif isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        ):

            result["functions"].append(node.name)

        elif isinstance(node, ast.ClassDef):

            result["classes"].append(node.name)

    # Flask / FastAPI / generic decorators
    route_patterns = [
        r'@\w+\.(get|post|put|delete|patch|route)\s*\(\s*[\'"]([^\'"]+)',
        r'@app\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)',
    ]

    for pattern in route_patterns:

        for method, route in re.findall(
            pattern,
            text,
            re.IGNORECASE
        ):

            result["routes"].append({
                "method": method.upper(),
                "path": route,
            })

    result["imports"] = sorted(
        set(result["imports"])
    )

    result["functions"] = sorted(
        set(result["functions"])
    )

    result["classes"] = sorted(
        set(result["classes"])
    )

    result["routes"] = sorted(
        {
            (r["method"], r["path"])
            for r in result["routes"]
        }
    )

    result["routes"] = [
        {
            "method": method,
            "path": route,
        }
        for method, route in result["routes"]
    ]

    return result


# ============================================================
# JAVASCRIPT / TYPESCRIPT
# ============================================================

def analyze_js(path):

    text = read_text(path)

    if not text:
        return {}

    result = {
        "imports": [],
        "exports": [],
        "components": [],
        "api": [],
        "routes": [],
    }

    result["imports"] = sorted(
        set(
            re.findall(
                r'import\s+(?:.*?\s+from\s+)?[\'"]([^\'"]+)[\'"]',
                text
            )
        )
    )

    result["exports"] = sorted(
        set(
            x for x in re.findall(
                r'export\s+(?:default\s+)?'
                r'(?:function|class|const|let|var)?\s*'
                r'([A-Za-z_$][\w$]*)?',
                text
            )
            if x
        )
    )

    result["components"] = sorted(
        set(
            re.findall(
                r'(?:function|const)\s+'
                r'([A-Z][A-Za-z0-9_$]*)',
                text
            )
        )
    )

    fetches = re.findall(
        r'fetch\s*\(\s*[\'"`]([^\'"`]+)',
        text
    )

    axios = re.findall(
        r'axios\.(?:get|post|put|delete|patch)'
        r'\s*\(\s*[\'"`]([^\'"`]+)',
        text
    )

    result["api"] = sorted(
        set(fetches + axios)
    )

    result["routes"] = sorted(
        set(
            re.findall(
                r'(?:path|route)\s*[:=]\s*[\'"]([^\'"]+)',
                text
            )
        )
    )

    return result


# ============================================================
# SQL
# ============================================================

def analyze_sql(path):

    text = read_text(path)

    if not text:
        return {}

    tables = re.findall(
        r'\b(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+'
        r'["`]?([A-Za-z_][\w$]*)',
        text,
        re.IGNORECASE
    )

    creates = re.findall(
        r'CREATE\s+TABLE\s+'
        r'(?:IF\s+NOT\s+EXISTS\s+)?'
        r'["`]?([A-Za-z_][\w$]*)',
        text,
        re.IGNORECASE
    )

    return {
        "tables": sorted(
            set(tables + creates)
        ),
        "creates": len(creates),
        "select": len(
            re.findall(r'\bSELECT\b', text, re.I)
        ),
        "insert": len(
            re.findall(r'\bINSERT\b', text, re.I)
        ),
        "update": len(
            re.findall(r'\bUPDATE\b', text, re.I)
        ),
        "delete": len(
            re.findall(r'\bDELETE\b', text, re.I)
        ),
    }


# ============================================================
# TECNOLOGÍAS
# ============================================================

TECHNOLOGIES = {

    "React": r"\breact\b",
    "Vite": r"\bvite\b",
    "Vue": r"\bvue\b",
    "Angular": r"@angular/",
    "Flask": r"\bflask\b",
    "FastAPI": r"\bfastapi\b",
    "Django": r"\bdjango\b",
    "Express": r"\bexpress\b",
    "Node.js": r"\bnode\b",

    "PostgreSQL": r"postgresql|psycopg",
    "MySQL": r"\bmysql\b",
    "SQLite": r"\bsqlite\b",
    "MongoDB": r"mongodb|mongoose",
    "Redis": r"\bredis\b",

    "Docker": r"\bdocker\b",
    "Leaflet": r"\bleaflet\b",
    "Mapbox": r"\bmapbox\b",
    "Tailwind": r"\btailwind\b",

    "Pandas": r"\bpandas\b",
    "NumPy": r"\bnumpy\b",
    "OpenCV": r"\bcv2\b|opencv",
    "YOLO": r"\byolo\b",
}


def detect_technologies(files, repo):

    found = Counter()

    for file in files:

        if not file["text"]:
            continue

        if file["size"] > MAX_FILE_SIZE:
            continue

        path = repo / file["path"]

        text = read_text(path)

        if not text:
            continue

        for name, pattern in TECHNOLOGIES.items():

            if re.search(
                pattern,
                text,
                re.IGNORECASE
            ):
                found[name] += 1

    for filename in [
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "docker-compose.yml",
        "docker-compose.yaml",
    ]:

        path = repo / filename

        if not path.exists():
            continue

        text = read_text(path)

        if not text:
            continue

        for name, pattern in TECHNOLOGIES.items():

            if re.search(
                pattern,
                text,
                re.IGNORECASE
            ):
                found[name] += 10

    return found


# ============================================================
# DEPENDENCIAS
# ============================================================

def dependencies(repo):

    result = []

    package = repo / "package.json"

    if package.exists():

        try:

            data = json.loads(
                read_text(package)
            )

            for section in [
                "dependencies",
                "devDependencies"
            ]:

                for name, version in data.get(
                    section,
                    {}
                ).items():

                    result.append(
                        f"{name}@{version}"
                    )

        except Exception:
            pass

    requirements = repo / "requirements.txt"

    if requirements.exists():

        text = read_text(requirements)

        if text:

            for line in text.splitlines():

                line = line.strip()

                if (
                    line
                    and not line.startswith("#")
                ):
                    result.append(line)

    return sorted(set(result))


# ============================================================
# VARIABLES DE ENTORNO
# ============================================================

def detect_env_vars(files, repo):

    result = set()

    patterns = [

        r'os\.getenv\s*\(\s*[\'"]([^\'"]+)',
        r'os\.environ\.get\s*\(\s*[\'"]([^\'"]+)',
        r'process\.env\.([A-Za-z_][A-Za-z0-9_]*)',
    ]

    for file in files:

        if not file["text"]:
            continue

        if file["size"] > MAX_FILE_SIZE:
            continue

        path = repo / file["path"]

        text = read_text(path)

        if not text:
            continue

        for pattern in patterns:

            result.update(
                re.findall(
                    pattern,
                    text
                )
            )

    return sorted(result)


# ============================================================
# CAPACIDADES
# ============================================================

CAPABILITIES = {

    "Autenticación": [
        "login",
        "logout",
        "auth",
        "jwt",
        "token",
        "authenticate",
    ],

    "Mapas": [
        "leaflet",
        "mapbox",
        "mapa",
        "cartografia",
        "map",
    ],

    "Exportación": [
        "export",
        "exportar",
        "csv",
        "xlsx",
        "excel",
        "pdf",
    ],

    "Carga de archivos": [
        "upload",
        "archivo",
        "file",
        "document",
    ],

    "Reportes": [
        "report",
        "reporte",
        "dashboard",
        "analytics",
        "estadistica",
    ],

    "Base de datos": [
        "postgres",
        "mysql",
        "sqlite",
        "mongodb",
        "database",
        "sqlalchemy",
        "psycopg",
    ],

    "Procesamiento de datos": [
        "pandas",
        "numpy",
        "csv",
        "dataframe",
        "etl",
    ],

    "IA / Machine Learning": [
        "tensorflow",
        "pytorch",
        "torch",
        "yolo",
        "model",
        "machine learning",
    ],
}


def detect_capabilities(files, repo):

    path_text = " ".join(
        file["path"].lower()
        for file in files
    )

    content_parts = []

    for file in files:

        if not file["text"]:
            continue

        if file["size"] > 300_000:
            continue

        path = repo / file["path"]

        text = read_text(path)

        if text:
            content_parts.append(
                text[:100_000].lower()
            )

    content = path_text + " " + " ".join(
        content_parts
    )

    result = {}

    for capability, keywords in CAPABILITIES.items():

        matches = [
            keyword
            for keyword in keywords
            if keyword.lower() in content
        ]

        if matches:

            result[capability] = matches[:6]

    return result


# ============================================================
# README EXISTENTE
# ============================================================

def existing_readme(repo):

    for filename in [
        "README.md",
        "README",
        "README.txt",
    ]:

        path = repo / filename

        if path.exists():

            text = read_text(path)

            if text:
                return text

    return None


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
            score += 5

        if score:

            scored.append(
                (score, file["path"])
            )

    scored.sort(
        key=lambda x: (-x[0], x[1])
    )

    return [
        path
        for _, path in scored[:60]
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
# ANÁLISIS
# ============================================================

def analyze_files(repo, files):

    analysis = {}

    for file in files:

        if not file["text"]:
            continue

        if file["size"] > MAX_FILE_SIZE:
            continue

        path = repo / file["path"]

        data = {}

        if file["language"] == "Python":

            data["python"] = analyze_python(path)

        elif file["language"] in {
            "JavaScript",
            "React",
            "TypeScript",
            "React+TS",
        }:

            data["javascript"] = analyze_js(path)

        elif file["language"] == "SQL":

            data["sql"] = analyze_sql(path)

        if data:

            analysis[file["path"]] = data

    return analysis


# ============================================================
# README EXISTENTE - INFORMACIÓN ÚTIL
# ============================================================

def summarize_existing_readme(readme):

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
            line = line[:240]

        lines.append(line)

        if len(lines) >= 25:
            break

    return lines


# ============================================================
# GENERAR CONTEXTO
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

    lines.append("# PROJECT CONTEXT")
    lines.append(
        f"PROJECT={repo.name}"
    )
    lines.append(
        f"FILES={len(files)}"
    )

    # --------------------------------------------------------
    # STACK
    # --------------------------------------------------------

    lines.append("")
    lines.append("## STACK")

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
                for name, _ in langs.most_common(10)
            )
        )

    if technologies:

        lines.append(
            "TECH=" +
            ",".join(
                technologies.most_common(20)[i][0]
                for i in range(
                    min(20, len(technologies))
                )
            )
        )

    # --------------------------------------------------------
    # DEPENDENCIAS IMPORTANTES
    # --------------------------------------------------------

    if deps:

        lines.append("")
        lines.append("## DEPENDENCIES")

        # Priorizar dependencias conocidas.
        important_deps = []

        for dep in deps:

            name = dep.lower()

            if any(
                keyword in name
                for keyword in [
                    "react",
                    "vite",
                    "vue",
                    "angular",
                    "flask",
                    "fastapi",
                    "django",
                    "express",
                    "postgres",
                    "psycopg",
                    "sqlalchemy",
                    "pandas",
                    "numpy",
                    "torch",
                    "tensorflow",
                    "leaflet",
                    "mapbox",
                    "tailwind",
                    "axios",
                    "openai",
                    "zai",
                ]
            ):
                important_deps.append(dep)

        selected = (
            important_deps[:45]
            if important_deps
            else deps[:45]
        )

        lines.append(
            ",".join(selected)
        )

    # --------------------------------------------------------
    # ESTRUCTURA
    # --------------------------------------------------------

    lines.append("")
    lines.append("## STRUCTURE")

    roots = structure(files)

    lines.append(
        "ROOTS=" +
        ",".join(
            f"{name}({count})"
            for name, count
            in roots.most_common(25)
        )
    )

    # --------------------------------------------------------
    # ARCHIVOS CLAVE
    # --------------------------------------------------------

    important = important_files(files)

    if important:

        lines.append("")
        lines.append("## KEY_FILES")

        lines.append(
            ",".join(important)
        )

    # --------------------------------------------------------
    # API
    # --------------------------------------------------------

    api_items = []

    for path, data in analysis.items():

        py = data.get(
            "python",
            {}
        )

        for route in py.get(
            "routes",
            []
        ):

            api_items.append(
                f"{route['method']} {route['path']}"
            )

        js = data.get(
            "javascript",
            {}
        )

        for route in js.get(
            "routes",
            []
        ):

            api_items.append(
                f"ROUTE {route}"
            )

        for api in js.get(
            "api",
            []
        ):

            api_items.append(
                f"CALL {api}"
            )

    if api_items:

        lines.append("")
        lines.append("## API")

        lines.append(
            ",".join(
                sorted(set(api_items))[:100]
            )
        )

    # --------------------------------------------------------
    # BASE DE DATOS
    # --------------------------------------------------------

    tables = set()

    for data in analysis.values():

        sql = data.get(
            "sql",
            {}
        )

        tables.update(
            sql.get(
                "tables",
                []
            )
        )

    if tables:

        lines.append("")
        lines.append("## DATABASE")

        lines.append(
            "TABLES=" +
            ",".join(
                sorted(tables)[:100]
            )
        )

    # --------------------------------------------------------
    # VARIABLES DE ENTORNO
    # --------------------------------------------------------

    if env_vars:

        lines.append("")
        lines.append("## ENV")

        lines.append(
            ",".join(env_vars[:50])
        )

    # --------------------------------------------------------
    # CAPACIDADES
    # --------------------------------------------------------

    if capabilities:

        lines.append("")
        lines.append("## CAPABILITIES")

        for capability, signals in capabilities.items():

            lines.append(
                f"{capability}="
                + ",".join(signals)
            )

    # --------------------------------------------------------
    # PYTHON
    # --------------------------------------------------------

    python_modules = []

    for path, data in analysis.items():

        py = data.get("python")

        if not py:
            continue

        classes = py.get(
            "classes",
            []
        )

        functions = py.get(
            "functions",
            []
        )

        imports = py.get(
            "imports",
            []
        )

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
                + ",".join(classes[:12])
            )

        if functions:

            entry += (
                "|F="
                + ",".join(functions[:18])
            )

        if imports:

            entry += (
                "|I="
                + ",".join(imports[:12])
            )

        python_modules.append(entry)

    if python_modules:

        lines.append("")
        lines.append("## PYTHON")

        lines.extend(
            python_modules[:45]
        )

    # --------------------------------------------------------
    # COMPONENTES
    # --------------------------------------------------------

    components = []

    for path, data in analysis.items():

        js = data.get(
            "javascript"
        )

        if not js:
            continue

        comps = js.get(
            "components",
            []
        )

        if comps:

            components.append(
                path
                + ":"
                + ",".join(comps[:15])
            )

    if components:

        lines.append("")
        lines.append("## COMPONENTS")

        lines.extend(
            components[:50]
        )

    # --------------------------------------------------------
    # README EXISTENTE
    # --------------------------------------------------------

    readme_summary = summarize_existing_readme(
        readme
    )

    if readme_summary:

        lines.append("")
        lines.append("## EXISTING_README")

        lines.extend(
            readme_summary
        )

    # --------------------------------------------------------
    # CONFIGURACIÓN / DEPLOY
    # --------------------------------------------------------

    deployment_files = []

    for file in files:

        name = file["name"].lower()
        path = file["path"].lower()

        if any(
            token in name or token in path
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

        lines.append("")
        lines.append("## DEPLOYMENT")

        lines.append(
            ",".join(
                sorted(set(deployment_files))[:40]
            )
        )

    # --------------------------------------------------------
    # INSTRUCCIONES PARA EL LLM
    # --------------------------------------------------------

    lines.append("")
    lines.append("## README_RULES")

    lines.append(
        "Generate a professional README.md using only evidence in this context."
    )

    lines.append(
        "Explain the project's purpose, architecture, main capabilities, stack, structure, setup and usage when evidence exists."
    )

    lines.append(
        "Do not invent features, endpoints, commands, credentials, environment values, database tables or deployment platforms."
    )

    lines.append(
        "If an important README section lacks evidence, omit it instead of guessing."
    )

    lines.append(
        "Prefer concrete repository evidence over generic explanations."
    )

    lines.append(
        "Use the existing README only as contextual evidence; improve its structure and accuracy."
    )

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def main():

    if len(sys.argv) != 2:

        print(
            'Uso: python readme3.py "RUTA_REPOSITORIO"'
        )

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

    print("")
    print("=" * 70)
    print(
        " README3 - HIGH QUALITY COMPACT CONTEXT"
    )
    print("=" * 70)
    print("")
    print(
        f"Repositorio: {repo}"
    )

    # --------------------------------------------------------
    # 1
    # --------------------------------------------------------

    print("")
    print("[1/6] Escaneando...")

    files = scan(repo)

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
        files
    )

    # --------------------------------------------------------
    # 3
    # --------------------------------------------------------

    print(
        "[3/6] Detectando tecnologías..."
    )

    technologies = detect_technologies(
        files,
        repo
    )

    # --------------------------------------------------------
    # 4
    # --------------------------------------------------------

    print(
        "[4/6] Detectando dependencias..."
    )

    deps = dependencies(repo)

    env_vars = detect_env_vars(
        files,
        repo
    )

    capabilities = detect_capabilities(
        files,
        repo
    )

    readme = existing_readme(repo)

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

    # --------------------------------------------------------
    # 6
    # --------------------------------------------------------

    print(
        "[6/6] Guardando..."
    )

    output_dir = (
        repo / "readme_context"
    )

    output_dir.mkdir(
        exist_ok=True
    )

    output_file = (
        output_dir /
        "README_CONTEXT_ULTRA.md"
    )

    analysis_file = (
        output_dir /
        "repository_analysis.json"
    )

    output_file.write_text(
        context,
        encoding="utf-8"
    )

    analysis_file.write_text(
        json.dumps(
            {
                "repository": repo.name,
                "generated_at":
                    datetime.now().isoformat(),
                "files": files,
                "analysis": analysis,
                "technologies":
                    dict(technologies),
                "dependencies": deps,
                "environment_variables":
                    env_vars,
                "capabilities":
                    capabilities,
            },
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    chars = len(context)

    tokens = chars // 4

    print("")
    print("=" * 70)
    print(
        " CONTEXTO COMPACTO GENERADO"
    )
    print("=" * 70)
    print("")

    print(
        f"Archivo: {output_file}"
    )

    print(
        f"Caracteres: {chars:,}"
    )

    print(
        f"Tokens estimados: {tokens:,}"
    )

    print("")

    if 2500 <= tokens <= 3500:

        print(
            "OK: contexto dentro del rango objetivo."
        )

    elif tokens < 2500:

        print(
            "AVISO: contexto menor al objetivo."
        )

    else:

        print(
            "AVISO: contexto mayor al objetivo."
        )

    print("")


if __name__ == "__main__":
    main()

