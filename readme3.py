import ast
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


# ============================================================
# README3 - ULTRA COMPRESSED CONTEXT
#
# Objetivo:
#   Analizar un repositorio SIN LLM y generar un contexto
#   extremadamente compacto para que otro LLM redacte
#   README.md.
#
# Salida:
#
#   readme_context/
#       README_CONTEXT_ULTRA.md
#       repository_analysis.json
#
# El contexto ULTRA NO contiene código completo.
# Solo contiene señales arquitectónicas y funcionales.
# ============================================================


# ============================================================
# CONFIGURACIÓN
# ============================================================

IGNORED_DIRS = {
    ".git",
    ".svn",
    ".hg",

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

    "target",
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


# ============================================================
# UTILIDADES
# ============================================================

def read_text(path):

    try:

        return path.read_text(
            encoding="utf-8"
        )

    except UnicodeDecodeError:

        try:

            return path.read_text(
                encoding="latin-1"
            )

        except Exception:
            return None

    except Exception:

        return None


def rel_path(
    path,
    repo
):

    return str(
        path.relative_to(repo)
    ).replace(
        "\\",
        "/"
    )


def language(path):

    mapping = {

        ".py":
            "Python",

        ".js":
            "JavaScript",

        ".jsx":
            "React",

        ".ts":
            "TypeScript",

        ".tsx":
            "React+TS",

        ".java":
            "Java",

        ".c":
            "C",

        ".cpp":
            "C++",

        ".cs":
            "C#",

        ".go":
            "Go",

        ".rs":
            "Rust",

        ".php":
            "PHP",

        ".rb":
            "Ruby",

        ".swift":
            "Swift",

        ".kt":
            "Kotlin",

        ".html":
            "HTML",

        ".css":
            "CSS",

        ".scss":
            "SCSS",

        ".sql":
            "SQL",

        ".json":
            "JSON",

        ".yaml":
            "YAML",

        ".yml":
            "YAML",

        ".toml":
            "TOML",

        ".md":
            "Markdown",

        ".sh":
            "Shell",

        ".ps1":
            "PowerShell",
    }

    return mapping.get(
        path.suffix.lower(),
        "Other"
    )


# ============================================================
# ESCANEO
# ============================================================

def scan(repo):

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

            path = (
                Path(root)
                / filename
            )

            try:

                size = path.stat().st_size

            except OSError:

                continue

            result.append({

                "path":
                    rel_path(
                        path,
                        repo
                    ),

                "name":
                    filename,

                "ext":
                    path.suffix.lower(),

                "language":
                    language(path),

                "size":
                    size,

                "text":
                    path.suffix.lower()
                    in TEXT_EXTENSIONS,

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

        tree = ast.parse(
            text
        )

    except Exception:

        return result

    for node in ast.walk(tree):

        # Imports
        if isinstance(
            node,
            ast.Import
        ):

            for item in node.names:

                result[
                    "imports"
                ].append(
                    item.name
                )

        elif isinstance(
            node,
            ast.ImportFrom
        ):

            if node.module:

                result[
                    "imports"
                ].append(
                    node.module
                )

        # Funciones
        elif isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef
            )
        ):

            result[
                "functions"
            ].append(
                node.name
            )

        # Clases
        elif isinstance(
            node,
            ast.ClassDef
        ):

            result[
                "classes"
            ].append(
                node.name
            )

    # Flask / FastAPI / similares
    route_patterns = [

        r'@\w+\.(get|post|put|delete|patch|route)'
        r'\s*\(\s*[\'"]([^\'"]+)',

        r'@app\.(get|post|put|delete|patch)'
        r'\s*\(\s*[\'"]([^\'"]+)',
    ]

    for pattern in route_patterns:

        for match in re.findall(
            pattern,
            text,
            re.IGNORECASE
        ):

            result[
                "routes"
            ].append(
                {
                    "method":
                        match[0].upper(),

                    "path":
                        match[1],
                }
            )

    result[
        "imports"
    ] = sorted(
        set(
            result["imports"]
        )
    )

    result[
        "functions"
    ] = sorted(
        set(
            result["functions"]
        )
    )

    result[
        "classes"
    ] = sorted(
        set(
            result["classes"]
        )
    )

    result[
        "routes"
    ] = sorted(
        {
            (
                r["method"],
                r["path"]
            )
            for r in result["routes"]
        }
    )

    result[
        "routes"
    ] = [
        {
            "method":
                item[0],

            "path":
                item[1],
        }

        for item in result[
            "routes"
        ]
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

    # Imports
    result[
        "imports"
    ] = sorted(
        set(
            re.findall(
                r'import\s+'
                r'(?:.*?\s+from\s+)?'
                r'[\'"]([^\'"]+)[\'"]',
                text
            )
        )
    )

    # Exports
    result[
        "exports"
    ] = sorted(
        set(
            x
            for x in re.findall(
                r'export\s+'
                r'(?:default\s+)?'
                r'(?:function|class|const|let|var)?'
                r'\s*([A-Za-z_$][\w$]*)?',
                text
            )
            if x
        )
    )

    # Componentes React
    result[
        "components"
    ] = sorted(
        set(
            re.findall(
                r'(?:function|const)\s+'
                r'([A-Z][A-Za-z0-9_]*)',
                text
            )
        )
    )

    # fetch
    fetches = re.findall(
        r'fetch\s*\(\s*[\'"`]([^\'"`]+)',
        text
    )

    # axios
    axios = re.findall(
        r'axios\.'
        r'(?:get|post|put|delete|patch)'
        r'\s*\(\s*[\'"`]([^\'"`]+)',
        text
    )

    result[
        "api"
    ] = sorted(
        set(
            fetches + axios
        )
    )

    # React Router
    result[
        "routes"
    ] = sorted(
        set(
            re.findall(
                r'(?:path|route)\s*[:=]\s*'
                r'[\'"]([^\'"]+)[\'"]',
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
        r'\b(?:FROM|JOIN|INTO|UPDATE|TABLE)'
        r'\s+["`]?'
        r'([A-Za-z_][\w$]*)',
        text,
        re.IGNORECASE
    )

    creates = re.findall(
        r'CREATE\s+TABLE\s+'
        r'(?:IF\s+NOT\s+EXISTS\s+)?'
        r'["`]?'
        r'([A-Za-z_][\w$]*)',
        text,
        re.IGNORECASE
    )

    return {

        "tables":
            sorted(
                set(
                    tables + creates
                )
            ),

        "creates":
            len(
                creates
            ),

        "select":
            len(
                re.findall(
                    r'\bSELECT\b',
                    text,
                    re.IGNORECASE
                )
            ),

        "insert":
            len(
                re.findall(
                    r'\bINSERT\b',
                    text,
                    re.IGNORECASE
                )
            ),

        "update":
            len(
                re.findall(
                    r'\bUPDATE\b',
                    text,
                    re.IGNORECASE
                )
            ),

        "delete":
            len(
                re.findall(
                    r'\bDELETE\b',
                    text,
                    re.IGNORECASE
                )
            ),
    }


# ============================================================
# TECNOLOGÍAS
# ============================================================

TECHNOLOGIES = {

    "React":
        r'\breact\b',

    "Vite":
        r'\bvite\b',

    "Vue":
        r'\bvue\b',

    "Angular":
        r'@angular/',

    "Flask":
        r'\bflask\b',

    "FastAPI":
        r'\bfastapi\b',

    "Django":
        r'\bdjango\b',

    "Express":
        r'\bexpress\b',

    "Node.js":
        r'\bnode\b',

    "PostgreSQL":
        r'postgresql|psycopg',

    "MySQL":
        r'\bmysql\b',

    "SQLite":
        r'\bsqlite\b',

    "MongoDB":
        r'mongodb|mongoose',

    "Redis":
        r'\bredis\b',

    "Docker":
        r'docker',

    "Leaflet":
        r'\bleaflet\b',

    "Mapbox":
        r'\bmapbox\b',

    "Tailwind":
        r'\btailwind\b',

    "Pandas":
        r'\bpandas\b',

    "NumPy":
        r'\bnumpy\b',

    "OpenCV":
        r'\bcv2\b|opencv',

    "YOLO":
        r'\byolo\b',

}


def detect_technologies(
    files,
    repo
):

    found = Counter()

    # Primero por contenido
    for file in files:

        if not file["text"]:
            continue

        path = (
            repo /
            file["path"]
        )

        if (
            file["size"]
            > MAX_FILE_SIZE
        ):
            continue

        text = read_text(
            path
        )

        if not text:
            continue

        for name, pattern in (
            TECHNOLOGIES.items()
        ):

            if re.search(
                pattern,
                text,
                re.IGNORECASE
            ):

                found[name] += 1

    # También por nombres de dependencias
    package = repo / "package.json"

    if package.exists():

        text = read_text(
            package
        )

        if text:

            for name, pattern in (
                TECHNOLOGIES.items()
            ):

                if re.search(
                    pattern,
                    text,
                    re.IGNORECASE
                ):

                    found[name] += 10

    requirements = (
        repo /
        "requirements.txt"
    )

    if requirements.exists():

        text = read_text(
            requirements
        )

        if text:

            for name, pattern in (
                TECHNOLOGIES.items()
            ):

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

                for name in data.get(
                    section,
                    {}
                ):

                    result.append(
                        f"{name}"
                        f"@"
                        f"{data[section][name]}"
                    )

        except Exception:
            pass

    requirements = (
        repo /
        "requirements.txt"
    )

    if requirements.exists():

        text = read_text(
            requirements
        )

        if text:

            for line in text.splitlines():

                line = line.strip()

                if (
                    line
                    and not line.startswith("#")
                ):

                    result.append(
                        line
                    )

    return sorted(
        set(result)
    )


# ============================================================
# VARIABLES DE ENTORNO
# ============================================================

def detect_env_vars(
    files,
    repo
):

    result = set()

    patterns = [

        r'os\.getenv\s*\(\s*[\'"]([^\'"]+)',

        r'os\.environ\.get\s*\(\s*[\'"]([^\'"]+)',

        r'process\.env\.([A-Za-z_][A-Za-z0-9_]*)',

    ]

    for file in files:

        if not file["text"]:
            continue

        path = (
            repo /
            file["path"]
        )

        if (
            file["size"]
            > MAX_FILE_SIZE
        ):
            continue

        text = read_text(
            path
        )

        if not text:
            continue

        for pattern in patterns:

            result.update(
                re.findall(
                    pattern,
                    text
                )
            )

    return sorted(
        result
    )


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
        "password",
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

}


def detect_capabilities(
    files,
    repo
):

    # Construimos un índice textual pequeño.
    signals = []

    for file in files:

        signals.append(
            file["path"].lower()
        )

    content = " ".join(
        signals
    )

    found = {}

    for capability, keywords in (
        CAPABILITIES.items()
    ):

        matches = [
            keyword
            for keyword in keywords
            if keyword in content
        ]

        if matches:

            found[
                capability
            ] = matches[:5]

    return found


# ============================================================
# README EXISTENTE
# ============================================================

def existing_readme(repo):

    candidates = [
        repo / "README.md",
        repo / "README",
        repo / "README.txt",
    ]

    for path in candidates:

        if path.exists():

            text = read_text(
                path
            )

            if text:

                return text

    return None


# ============================================================
# ARCHIVOS IMPORTANTES
# ============================================================

def important_files(files):

    keywords = [

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

        "controller",

    ]

    result = []

    for file in files:

        path = file[
            "path"
        ].lower()

        score = 0

        for keyword in keywords:

            if keyword in path:

                score += 1

        if score:

            result.append(
                (
                    score,
                    file["path"]
                )
            )

    result.sort(
        reverse=True
    )

    return [
        path
        for _, path
        in result[:80]
    ]


# ============================================================
# ESTRUCTURA COMPACTA
# ============================================================

def structure(files):

    roots = Counter()

    for file in files:

        parts = Path(
            file["path"]
        ).parts

        if not parts:
            continue

        roots[
            parts[0]
        ] += 1

    return roots


# ============================================================
# ANÁLISIS PRINCIPAL
# ============================================================

def analyze_files(
    repo,
    files
):

    analysis = {}

    for file in files:

        if not file["text"]:
            continue

        if (
            file["size"]
            > MAX_FILE_SIZE
        ):
            continue

        path = (
            repo /
            file["path"]
        )

        data = {}

        if file["language"] == "Python":

            data[
                "python"
            ] = analyze_python(
                path
            )

        elif file["language"] in {
            "JavaScript",
            "React",
            "TypeScript",
            "React+TS",
        }:

            data[
                "javascript"
            ] = analyze_js(
                path
            )

        elif file["language"] == "SQL":

            data[
                "sql"
            ] = analyze_sql(
                path
            )

        if data:

            analysis[
                file["path"]
            ] = data

    return analysis


# ============================================================
# GENERAR ULTRA CONTEXT
# ============================================================

def generate_ultra(
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

    lines.append(
        "# README GENERATION CONTEXT"
    )

    lines.append(
        f"PROJECT={repo.name}"
    )

    lines.append(
        f"FILES={len(files)}"
    )

    lines.append(
        f"GENERATED={datetime.now().strftime('%Y-%m-%d')}"
    )

    lines.append("")

    # --------------------------------------------------------
    # STACK
    # --------------------------------------------------------

    lines.append(
        "## STACK"
    )

    langs = Counter(
        file["language"]
        for file in files
        if file["language"] != "Other"
    )

    if langs:

        lines.append(
            "LANGUAGES="
            + ", ".join(
                f"{name}:{count}"
                for name, count
                in langs.most_common()
            )
        )

    if technologies:

        lines.append(
            "TECH="
            + ", ".join(
                technologies.keys()
            )
        )

    lines.append("")

    # --------------------------------------------------------
    # DEPENDENCIAS
    # --------------------------------------------------------

    if deps:

        lines.append(
            "## DEPENDENCIES"
        )

        # Muy agresivo:
        # máximo 80 dependencias.
        lines.append(
            ", ".join(
                deps[:80]
            )
        )

        lines.append("")

    # --------------------------------------------------------
    # ESTRUCTURA
    # --------------------------------------------------------

    lines.append(
        "## STRUCTURE"
    )

    roots = structure(
        files
    )

    lines.append(
        "ROOTS="
        + ", ".join(
            f"{name}/:{count}"
            for name, count
            in roots.most_common(40)
        )
    )

    lines.append("")

    # --------------------------------------------------------
    # ARCHIVOS IMPORTANTES
    # --------------------------------------------------------

    important = important_files(
        files
    )

    if important:

        lines.append(
            "## KEY_FILES"
        )

        lines.append(
            ", ".join(
                important
            )
        )

        lines.append("")

    # --------------------------------------------------------
    # API
    # --------------------------------------------------------

    routes = []

    for path, data in analysis.items():

        py = data.get(
            "python",
            {}
        )

        for route in py.get(
            "routes",
            []
        ):

            routes.append(
                f"{route['method']} "
                f"{route['path']}"
            )

        js = data.get(
            "javascript",
            {}
        )

        for route in js.get(
            "routes",
            []
        ):

            routes.append(
                f"ROUTE {route}"
            )

        for api in js.get(
            "api",
            []
        ):

            routes.append(
                f"CALL {api}"
            )

    if routes:

        lines.append(
            "## API"
        )

        lines.append(
            ", ".join(
                sorted(
                    set(routes)
                )[:120]
            )
        )

        lines.append("")

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

        lines.append(
            "## DATABASE"
        )

        lines.append(
            "TABLES="
            + ", ".join(
                sorted(tables)[:150]
            )
        )

        lines.append("")

    # --------------------------------------------------------
    # CONFIGURACIÓN
    # --------------------------------------------------------

    if env_vars:

        lines.append(
            "## ENV"
        )

        lines.append(
            ", ".join(
                env_vars[:80]
            )
        )

        lines.append("")

    # --------------------------------------------------------
    # CAPACIDADES
    # --------------------------------------------------------

    if capabilities:

        lines.append(
            "## CAPABILITIES"
        )

        for capability, signals in (
            capabilities.items()
        ):

            lines.append(
                f"{capability}: "
                f"{', '.join(signals)}"
            )

        lines.append("")

    # --------------------------------------------------------
    # PYTHON PRINCIPAL
    # --------------------------------------------------------

    python_summary = []

    for path, data in analysis.items():

        py = data.get(
            "python"
        )

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

        if functions or classes:

            entry = path

            if classes:

                entry += (
                    " | classes="
                    + ",".join(
                        classes[:20]
                    )
                )

            if functions:

                entry += (
                    " | functions="
                    + ",".join(
                        functions[:30]
                    )
                )

            python_summary.append(
                entry
            )

    if python_summary:

        lines.append(
            "## PYTHON_MODULES"
        )

        lines.extend(
            python_summary[:60]
        )

        lines.append("")

    # --------------------------------------------------------
    # COMPONENTES JS
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
                f"{path}:"
                + ",".join(
                    comps[:20]
                )
            )

    if components:

        lines.append(
            "## COMPONENTS"
        )

        lines.extend(
            components[:80]
        )

        lines.append("")

    # --------------------------------------------------------
    # README EXISTENTE
    # --------------------------------------------------------

    if readme:

        # Solo extraer las primeras partes.
        # No queremos duplicar un README gigante.

        readme_lines = (
            readme
            .splitlines()
        )

        useful = []

        for line in readme_lines:

            line = line.strip()

            if not line:
                continue

            if len(line) > 300:
                line = line[:300]

            useful.append(
                line
            )

            if len(useful) >= 35:
                break

        if useful:

            lines.append(
                "## EXISTING_README"
            )

            lines.extend(
                useful
            )

            lines.append("")

    # --------------------------------------------------------
    # INSTRUCCIÓN FINAL
    # --------------------------------------------------------

    lines.append(
        "## INSTRUCTION"
    )

    lines.append(
        "Generate README.md using only supported evidence."
    )

    lines.append(
        "Do not invent features, technologies, commands, "
        "endpoints, database tables or configuration."
    )

    lines.append(
        "Prefer concise accurate documentation over speculation."
    )

    return "\n".join(
        lines
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if len(sys.argv) != 2:

        print("")
        print(
            "Uso:"
        )
        print(
            'python readme3.py "D:\\GitHub\\PROYECTO"'
        )
        print("")

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
        " README3 - ULTRA COMPRESSED CONTEXT"
    )
    print("=" * 70)
    print("")

    print(
        f"Repositorio: {repo}"
    )

    # --------------------------------------------------------
    # ESCANEAR
    # --------------------------------------------------------

    print("")
    print(
        "[1/6] Escaneando..."
    )

    files = scan(
        repo
    )

    print(
        f"      {len(files)} archivos."
    )

    # --------------------------------------------------------
    # ANALIZAR
    # --------------------------------------------------------

    print(
        "[2/6] Analizando arquitectura..."
    )

    analysis = analyze_files(
        repo,
        files
    )

    # --------------------------------------------------------
    # TECNOLOGÍAS
    # --------------------------------------------------------

    print(
        "[3/6] Detectando tecnologías..."
    )

    technologies = detect_technologies(
        files,
        repo
    )

    # --------------------------------------------------------
    # DEPENDENCIAS
    # --------------------------------------------------------

    print(
        "[4/6] Detectando dependencias..."
    )

    deps = dependencies(
        repo
    )

    env_vars = detect_env_vars(
        files,
        repo
    )

    capabilities = detect_capabilities(
        files,
        repo
    )

    readme = existing_readme(
        repo
    )

    # --------------------------------------------------------
    # GENERAR
    # --------------------------------------------------------

    print(
        "[5/6] Generando contexto ULTRA..."
    )

    ultra = generate_ultra(
        repo,
        files,
        analysis,
        technologies,
        deps,
        env_vars,
        capabilities,
        readme
    )

    # --------------------------------------------------------
    # GUARDAR
    # --------------------------------------------------------

    output_dir = (
        repo /
        "readme_context"
    )

    output_dir.mkdir(
        exist_ok=True
    )

    ultra_file = (
        output_dir /
        "README_CONTEXT_ULTRA.md"
    )

    json_file = (
        output_dir /
        "repository_analysis.json"
    )

    ultra_file.write_text(
        ultra,
        encoding="utf-8"
    )

    json_file.write_text(
        json.dumps(
            {
                "repository":
                    repo.name,

                "generated_at":
                    datetime.now().isoformat(),

                "files":
                    files,

                "analysis":
                    analysis,

                "technologies":
                    dict(
                        technologies
                    ),

                "dependencies":
                    deps,

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

    # --------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------

    print(
        "[6/6] Terminado."
    )

    print("")
    print("=" * 70)
    print(
        " CONTEXTO ULTRA GENERADO"
    )
    print("=" * 70)
    print("")

    print(
        f"Archivo:"
    )

    print(
        f"  {ultra_file}"
    )

    print("")

    print(
        f"Caracteres:"
    )

    print(
        f"  {len(ultra):,}"
    )

    print("")

    print(
        f"Tokens estimados:"
    )

    print(
        f"  {len(ultra) // 4:,}"
    )

    print("")

    print(
        "Este es el archivo recomendado "
        "para enviar a Z.ai."
    )

    print("")


if __name__ == "__main__":
    main()

