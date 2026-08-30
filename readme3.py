import ast
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


# ============================================================
# README3 - COMPACT CONTEXT
#
# Analiza un repositorio sin LLM y genera un contexto pequeño
# para que otro LLM redacte README.md.
#
# Objetivo aproximado:
# 2.500 - 3.500 tokens
# ============================================================


# ============================================================
# CONFIGURACIÓN
# ============================================================

IGNORED_DIRS = {
    ".git", ".svn", ".hg",
    "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".venv", "venv", "env",
    "dist", "build", "coverage",
    ".next", ".nuxt", ".cache",
    "vendor", ".idea", ".vscode",
    "site-packages", "readme_context"
}

IGNORED_FILES = {
    ".DS_Store",
    "Thumbs.db"
}

TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".go", ".rs", ".php", ".rb",
    ".swift", ".kt", ".kts",
    ".html", ".htm", ".css", ".scss",
    ".sass", ".less", ".sql",
    ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg",
    ".md", ".txt", ".sh", ".bat", ".ps1"
}

MAX_FILE_SIZE = 5 * 1024 * 1024

# Límite aproximado del contexto final.
TARGET_CHARS = 13500

# Límites internos para evitar ruido.
MAX_DEPS = 45
MAX_FILES = 45
MAX_ROUTES = 35
MAX_TABLES = 60
MAX_COMPONENTS = 45
MAX_FUNCTIONS = 12
MAX_CLASSES = 8
MAX_ENV = 35


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

    return mapping.get(
        path.suffix.lower(),
        "Other"
    )


def clean(value):
    if value is None:
        return ""

    value = str(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def compact_list(values, limit):
    values = [
        clean(x)
        for x in values
        if clean(x)
    ]

    values = list(dict.fromkeys(values))

    if len(values) > limit:
        values = values[:limit] + [f"...+{len(values) - limit}"]

    return ",".join(values)


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

            ext = path.suffix.lower()

            result.append({
                "path": rel_path(path, repo),
                "name": filename,
                "ext": ext,
                "language": language(path),
                "size": size,
                "text": ext in TEXT_EXTENSIONS
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
        "routes": []
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

    # Flask / FastAPI / similares.
    route_pattern = re.compile(
        r'@\w+\.(get|post|put|delete|patch|route)'
        r'\s*\(\s*[\'"]([^\'"]+)[\'"]',
        re.IGNORECASE
    )

    for match in route_pattern.finditer(text):

        result["routes"].append({
            "method": match.group(1).upper(),
            "path": match.group(2)
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

    unique_routes = {
        (x["method"], x["path"])
        for x in result["routes"]
    }

    result["routes"] = [
        {
            "method": method,
            "path": path
        }
        for method, path in sorted(unique_routes)
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
        "routes": []
    }

    # Imports.
    result["imports"] = sorted(set(
        re.findall(
            r'import\s+(?:.*?\s+from\s+)?[\'"]([^\'"]+)[\'"]',
            text
        )
    ))

    # Exports.
    result["exports"] = sorted(set(
        x for x in re.findall(
            r'export\s+(?:default\s+)?'
            r'(?:function|class|const|let|var)?\s*'
            r'([A-Za-z_$][\w$]*)?',
            text
        )
        if x
    ))

    # Componentes React.
    result["components"] = sorted(set(
        re.findall(
            r'(?:function|const)\s+'
            r'([A-Z][A-Za-z0-9_]*)',
            text
        )
    ))

    # fetch.
    fetches = re.findall(
        r'fetch\s*\(\s*[\'"`]([^\'"`]+)',
        text
    )

    # axios.
    axios = re.findall(
        r'axios\.(?:get|post|put|delete|patch)'
        r'\s*\(\s*[\'"`]([^\'"`]+)',
        text
    )

    result["api"] = sorted(set(
        fetches + axios
    ))

    # React Router.
    result["routes"] = sorted(set(
        re.findall(
            r'(?:path|route)\s*[:=]\s*[\'"]([^\'"]+)[\'"]',
            text
        )
    ))

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
        r'["`]?(?:\w+\.)?([A-Za-z_][\w$]*)',
        text,
        re.IGNORECASE
    )

    creates = re.findall(
        r'CREATE\s+TABLE\s+'
        r'(?:IF\s+NOT\s+EXISTS\s+)?'
        r'["`]?(?:\w+\.)?([A-Za-z_][\w$]*)',
        text,
        re.IGNORECASE
    )

    return {
        "tables": sorted(set(
            tables + creates
        )),
        "creates": len(creates),
        "select": len(re.findall(
            r'\bSELECT\b',
            text,
            re.IGNORECASE
        )),
        "insert": len(re.findall(
            r'\bINSERT\b',
            text,
            re.IGNORECASE
        )),
        "update": len(re.findall(
            r'\bUPDATE\b',
            text,
            re.IGNORECASE
        )),
        "delete": len(re.findall(
            r'\bDELETE\b',
            text,
            re.IGNORECASE
        ))
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

        # No analizamos todo el archivo completo para
        # tecnologías si es excesivamente grande.
        sample = text[:200000]

        for name, pattern in TECHNOLOGIES.items():

            if re.search(
                pattern,
                sample,
                re.IGNORECASE
            ):
                found[name] += 1

    # package.json tiene mayor peso.
    package = repo / "package.json"

    if package.exists():

        text = read_text(package)

        if text:

            for name, pattern in TECHNOLOGIES.items():

                if re.search(
                    pattern,
                    text,
                    re.IGNORECASE
                ):
                    found[name] += 10

    # requirements.txt tiene mayor peso.
    requirements = repo / "requirements.txt"

    if requirements.exists():

        text = read_text(requirements)

        if text:

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

            for section in (
                "dependencies",
                "devDependencies"
            ):

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
        r'process\.env\.([A-Za-z_][A-Za-z0-9_]*)'

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
                re.findall(pattern, text)
            )

    return sorted(result)


# ============================================================
# CAPACIDADES
# ============================================================

CAPABILITIES = {

    "Auth": [
        "login",
        "logout",
        "auth",
        "jwt",
        "token",
        "password",
        "authenticate"
    ],

    "Maps": [
        "leaflet",
        "mapbox",
        "mapa",
        "cartografia",
        "map"
    ],

    "Export": [
        "export",
        "exportar",
        "csv",
        "xlsx",
        "excel",
        "pdf"
    ],

    "Upload": [
        "upload",
        "archivo",
        "file",
        "document"
    ],

    "Reports": [
        "report",
        "reporte",
        "dashboard",
        "analytics",
        "estadistica"
    ],

    "Database": [
        "postgres",
        "mysql",
        "sqlite",
        "mongodb",
        "database",
        "sqlalchemy",
        "psycopg"
    ]
}


def detect_capabilities(files):

    # Usamos rutas + nombres de archivos.
    # Es barato y reduce falsos positivos producidos
    # por comentarios/código irrelevante.
    signals = " ".join(
        file["path"].lower()
        for file in files
    )

    found = {}

    for capability, keywords in CAPABILITIES.items():

        matches = [
            keyword
            for keyword in keywords
            if keyword in signals
        ]

        if matches:
            found[capability] = matches[:5]

    return found


# ============================================================
# README EXISTENTE
# ============================================================

def existing_readme(repo):

    for name in (
        "README.md",
        "README",
        "README.txt"
    ):

        path = repo / name

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
    "config",
    "settings",
    "routes",
    "router",
    "api",
    "database",
    "db",
    "model",
    "schema",
    "service",
    "controller"
]


def important_files(files):

    scored = []

    for file in files:

        path = file["path"].lower()
        score = 0

        for keyword in IMPORTANT_KEYWORDS:

            if keyword in path:
                score += 1

        if score:
            scored.append(
                (score, file["path"])
            )

    scored.sort(
        key=lambda x: (-x[0], x[1])
    )

    return [
        path
        for _, path in scored[:MAX_FILES]
    ]


# ============================================================
# ANÁLISIS DE ARCHIVOS
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

            data["py"] = analyze_python(path)

        elif file["language"] in {
            "JavaScript",
            "React",
            "TypeScript",
            "React+TS"
        }:

            data["js"] = analyze_js(path)

        elif file["language"] == "SQL":

            data["sql"] = analyze_sql(path)

        if data:
            analysis[file["path"]] = data

    return analysis


# ============================================================
# GENERAR CONTEXTO COMPACTO
# ============================================================

def generate_context(
    repo,
    files,
    analysis,
    technologies,
    deps,
    env_vars,
    capabilities,
    readme
):

    lines = []

    # --------------------------------------------------------
    # IDENTIDAD
    # --------------------------------------------------------

    lines.append(
        f"PROJECT={repo.name}"
    )

    lines.append(
        f"FILES={len(files)}"
    )

    # --------------------------------------------------------
    # STACK
    # --------------------------------------------------------

    langs = Counter(
        file["language"]
        for file in files
        if file["language"] != "Other"
    )

    if langs:

        lines.append(
            "LANG="
            + ",".join(
                f"{name}:{count}"
                for name, count
                in langs.most_common(12)
            )
        )

    if technologies:

        lines.append(
            "TECH="
            + compact_list(
                technologies.keys(),
                20
            )
        )

    # --------------------------------------------------------
    # DEPENDENCIAS
    # --------------------------------------------------------

    if deps:

        lines.append(
            "DEPS="
            + compact_list(
                deps,
                MAX_DEPS
            )
        )

    # --------------------------------------------------------
    # ESTRUCTURA
    # --------------------------------------------------------

    roots = Counter()

    for file in files:

        parts = Path(
            file["path"]
        ).parts

        if parts:
            roots[parts[0]] += 1

    if roots:

        lines.append(
            "ROOTS="
            + ",".join(
                f"{name}({count})"
                for name, count
                in roots.most_common(20)
            )
        )

    # --------------------------------------------------------
    # ARCHIVOS CLAVE
    # --------------------------------------------------------

    key_files = important_files(files)

    if key_files:

        lines.append(
            "KEY_FILES="
            + compact_list(
                key_files,
                MAX_FILES
            )
        )

    # --------------------------------------------------------
    # API
    # --------------------------------------------------------

    routes = []

    for path, data in analysis.items():

        py = data.get("py", {})

        for route in py.get("routes", []):

            routes.append(
                f"{route['method']}:{route['path']}"
            )

        js = data.get("js", {})

        for route in js.get("routes", []):

            routes.append(
                f"ROUTE:{route}"
            )

        for api in js.get("api", []):

            routes.append(
                f"CALL:{api}"
            )

    if routes:

        lines.append(
            "API="
            + compact_list(
                sorted(set(routes)),
                MAX_ROUTES
            )
        )

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    tables = set()
    sql_stats = Counter()

    for data in analysis.values():

        sql = data.get("sql", {})

        tables.update(
            sql.get("tables", [])
        )

        for key in (
            "creates",
            "select",
            "insert",
            "update",
            "delete"
        ):
            sql_stats[key] += sql.get(
                key,
                0
            )

    if tables:

        lines.append(
            "TABLES="
            + compact_list(
                sorted(tables),
                MAX_TABLES
            )
        )

    if sql_stats:

        lines.append(
            "SQL="
            + ",".join(
                f"{key}:{value}"
                for key, value
                in sql_stats.items()
                if value
            )
        )

    # --------------------------------------------------------
    # ENV
    # --------------------------------------------------------

    if env_vars:

        lines.append(
            "ENV="
            + compact_list(
                env_vars,
                MAX_ENV
            )
        )

    # --------------------------------------------------------
    # CAPACIDADES
    # --------------------------------------------------------

    if capabilities:

        capability_lines = []

        for capability, signals in capabilities.items():

            capability_lines.append(
                f"{capability}({','.join(signals)})"
            )

        lines.append(
            "CAP="
            + ";".join(capability_lines)
        )

    # --------------------------------------------------------
    # PYTHON
    # --------------------------------------------------------

    python_modules = []

    for path, data in analysis.items():

        py = data.get("py")

        if not py:
            continue

        functions = py.get(
            "functions",
            []
        )

        classes = py.get(
            "classes",
            []
        )

        imports = py.get(
            "imports",
            []
        )

        if functions or classes or imports:

            entry = path

            if classes:
                entry += (
                    "|C="
                    + compact_list(
                        classes,
                        MAX_CLASSES
                    )
                )

            if functions:
                entry += (
                    "|F="
                    + compact_list(
                        functions,
                        MAX_FUNCTIONS
                    )
                )

            if imports:
                entry += (
                    "|I="
                    + compact_list(
                        imports,
                        10
                    )
                )

            python_modules.append(entry)

    if python_modules:

        lines.append(
            "PY="
            + ";".join(
                python_modules[:35]
            )
        )

    # --------------------------------------------------------
    # COMPONENTES
    # --------------------------------------------------------

    components = []

    for path, data in analysis.items():

        js = data.get("js")

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
                + compact_list(
                    comps,
                    12
                )
            )

    if components:

        lines.append(
            "COMP="
            + ";".join(
                components[:MAX_COMPONENTS]
            )
        )

    # --------------------------------------------------------
    # README EXISTENTE
    # --------------------------------------------------------

    if readme:

        useful = []

        for line in readme.splitlines():

            line = clean(line)

            if not line:
                continue

            # El README existente solo sirve como señal.
            # No necesitamos copiarlo completo.
            if len(line) > 180:
                line = line[:180]

            useful.append(line)

            if len(useful) >= 12:
                break

        if useful:

            lines.append(
                "OLD_README="
                + " | ".join(useful)
            )

    # --------------------------------------------------------
    # REGLAS PARA EL LLM
    # --------------------------------------------------------

    lines.append(
        "RULES=Use only evidence above;do not invent "
        "features,stack,commands,endpoints,tables,config "
        "or architecture;prefer concise accurate README."
    )

    result = "\n".join(lines)

    # --------------------------------------------------------
    # CONTROL DE TAMAÑO
    # --------------------------------------------------------

    if len(result) > TARGET_CHARS:

        result = result[:TARGET_CHARS]

        # Evitar terminar en medio de una línea.
        last_newline = result.rfind("\n")

        if last_newline > 0:
            result = result[:last_newline]

        result += (
            "\nTRUNCATED=1"
        )

    return result


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
    print(" README3 - COMPACT CONTEXT")
    print("=" * 70)
    print("")
    print(f"Repositorio: {repo}")

    # --------------------------------------------------------
    # 1. ESCANEAR
    # --------------------------------------------------------

    print("")
    print("[1/6] Escaneando...")

    files = scan(repo)

    print(
        f"      {len(files)} archivos."
    )

    # --------------------------------------------------------
    # 2. ANALIZAR
    # --------------------------------------------------------

    print(
        "[2/6] Analizando arquitectura..."
    )

    analysis = analyze_files(
        repo,
        files
    )

    # --------------------------------------------------------
    # 3. TECNOLOGÍAS
    # --------------------------------------------------------

    print(
        "[3/6] Detectando tecnologías..."
    )

    technologies = detect_technologies(
        files,
        repo
    )

    # --------------------------------------------------------
    # 4. DEPENDENCIAS
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
        files
    )

    readme = existing_readme(
        repo
    )

    # --------------------------------------------------------
    # 5. GENERAR CONTEXTO
    # --------------------------------------------------------

    print(
        "[5/6] Generando contexto compacto..."
    )

    context = generate_context(
        repo=repo,
        files=files,
        analysis=analysis,
        technologies=technologies,
        deps=deps,
        env_vars=env_vars,
        capabilities=capabilities,
        readme=readme
    )

    # --------------------------------------------------------
    # 6. GUARDAR
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

    context_file = (
        output_dir
        / "README_CONTEXT_ULTRA.md"
    )

    json_file = (
        output_dir
        / "repository_analysis.json"
    )

    context_file.write_text(
        context,
        encoding="utf-8"
    )

    json_file.write_text(
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
                    capabilities
            },
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------

    estimated_tokens = len(context) // 4

    print("")
    print("=" * 70)
    print(" CONTEXTO COMPACTO GENERADO")
    print("=" * 70)
    print("")

    print(
        f"Archivo: {context_file}"
    )

    print(
        f"Caracteres: {len(context):,}"
    )

    print(
        f"Tokens estimados: {estimated_tokens:,}"
    )

    print("")

    if estimated_tokens < 2500:

        print(
            "OK: contexto por debajo del rango objetivo."
        )

    elif estimated_tokens <= 3500:

        print(
            "OK: contexto dentro del rango objetivo."
        )

    else:

        print(
            "ADVERTENCIA: contexto supera 3.500 tokens."
        )

    print("")


if __name__ == "__main__":
    main()