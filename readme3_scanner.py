from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path


# ============================================================
# README3 - SCANNER
#
# Responsabilidad:
#   - Configuración de exclusiones
#   - Extensiones de texto
#   - Archivos importantes
#   - Utilidades comunes
#   - Escaneo del repositorio
#
# NO analiza semánticamente el software.
# Solo recopila información básica de archivos.
# ============================================================


# ============================================================
# CONFIGURACIÓN
# ============================================================

IGNORED_DIRS = {
    # Artefactos del propio generador. Sin esta linea, en la segunda corrida
    # el escaner analiza la evidencia que el mismo dejo en la primera —un JSON
    # que contiene literalmente los nombres de todas las tecnologias— como si
    # fuera codigo del proyecto.
    "readme_context",
    # Los insumos derivados son .md y .yaml: sin excluirlos, el analizador
    # los leeria como codigo del proyecto en la corrida siguiente. Quinta
    # vez que aparece esta clase de bug.
    "insumos",
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
    # Todo lo que escribe el generador queda fuera del analisis, por el mismo
    # motivo que readme_context: su extension esta en TEXT_EXTENSIONS y se
    # leeria a si mismo en la corrida siguiente.
    "README_CANDIDATE.md",
    "readme_report.md",
    "delete_files.md",
    # La prosa que un humano escribe aqui volveria como falsos positivos de
    # tecnologia citados en [.aireadme.yml:N]. Es el mismo bug de
    # auto-deteccion que ya aparecio con readme_context y con las listas de
    # palabras clave del propio detector.
    ".aireadme.yml",
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

# ============================================================
# CODIGO DE TERCEROS
#
# Muchos repositorios versionan codigo que no es suyo: los plugins de
# Moodle, el directorio platforms/ de Cordova, material ingerido. Medido
# sobre la flota: 98% de coipo_moodle, 81% de coipo_seguimiento_madera y
# 77% de COIPO_CHATBOTNORMATIVA.
#
# Analizarlo sin distinguirlo produce un README que describe Moodle en vez
# del proyecto, y ademas consume el presupuesto de contexto con codigo ajeno.
#
# Se distinguen dos niveles:
#
#   EXCLUDED_PATH_PATTERNS   no se analiza. Es inequivocamente de terceros.
#   THIRD_PARTY_PATTERNS     se analiza, pero marcado. Puede ser propio.
#
# Se usan patrones de RUTA y no nombres de directorio: "platforms/android"
# es Cordova, pero un directorio llamado "platforms" a secas podria ser
# codigo propio.
# ============================================================

EXCLUDED_PATH_PATTERNS = (
    r"(^|/)vendor/",
    r"(^|/)bower_components/",
    r"(^|/)third_party/",
    r"(^|/)site-packages/",
    # Cordova / Capacitor: codigo generado por la herramienta.
    r"(^|/)platforms/(android|ios|browser|electron|windows)/",
    # Material ingerido por herramientas de agente, no codigo del proyecto.
    r"(^|/)_staging/",
)

THIRD_PARTY_PATTERNS = (
    # En Moodle son de Moodle; en otros proyectos pueden ser propios.
    r"(^|/)plugins?/",
    r"(^|/)lib/external/",
    r"(^|/)assets/vendor/",
    # Artefactos construidos o minificados: no son fuente.
    r"\.min\.(js|css)$",
    r"(^|/)dist/",
)

EXCLUDED_PATH_RE = re.compile(
    "|".join(EXCLUDED_PATH_PATTERNS),
    re.IGNORECASE,
)

THIRD_PARTY_RE = re.compile(
    "|".join(THIRD_PARTY_PATTERNS),
    re.IGNORECASE,
)


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

@lru_cache(maxsize=4096)
def read_text(path: Path) -> str | None:
    """
    Lee un archivo de texto sin hacer fallar el análisis.

    Cacheado: los detectores recorrían el repositorio una vez por cada
    tecnología y una vez por cada categoría de capacidad, releyendo cada
    archivo del disco 30 veces por ejecución. Medido sobre
    COIPO_CHATBOTNORMATIVA: 158.125 lecturas.
    """

    try:
        return path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except Exception:
        return None


def rutas_extra_ignoradas() -> list[str]:
    """
    Rutas que el repositorio declaro en .aireadme.yml.

    Se pasan por entorno y no por argumento porque readme3.py se invoca
    como subproceso desde makeReadme.py, que es quien lee la configuracion.
    """

    crudo = os.environ.get("AIREADME_IGNORE_PATHS", "")

    return [p.strip().strip("/") for p in crudo.split(",") if p.strip()]


def is_excluded(relative_path: str) -> bool:
    """Ruta de terceros que no debe analizarse en absoluto."""

    if EXCLUDED_PATH_RE.search(relative_path):
        return True

    for extra in rutas_extra_ignoradas():
        if relative_path == extra or relative_path.startswith(extra + "/"):
            return True

    return False


def is_third_party(relative_path: str) -> bool:
    """
    Ruta que probablemente no es código del proyecto.

    Se analiza igual, pero marcada: quien lea la evidencia tiene que poder
    distinguir "el proyecto usa Leaflet" de "un plugin de terceros que el
    repositorio versiona usa Leaflet".
    """

    return bool(THIRD_PARTY_RE.search(relative_path))


def rel_path(path: Path, repo: Path) -> str:
    """Devuelve la ruta relativa POSIX respecto al repositorio."""

    return path.relative_to(repo).as_posix()


def language(path: Path) -> str:
    """Determina el lenguaje a partir de la extensión."""

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


def add_unique(collection: list, value):
    """Agrega un valor solamente si todavía no existe."""

    if value not in collection:
        collection.append(value)


def evidence_item(
    value,
    file,
    line=None,
    evidence_type=None,
    confidence="high",
):
    """Construye un elemento estándar de evidencia."""

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
    """Obtiene el número de línea correspondiente a una posición."""

    return text.count(
        "\n",
        0,
        position,
    ) + 1


# ============================================================
# ESCANEO
# ============================================================

def scan(repo: Path) -> list[dict]:
    """
    Escanea el repositorio y genera un inventario de archivos.

    Importante:
        Este método NO interpreta el significado del software.
        Solo registra evidencia estructural.
    """

    result = []

    for root, dirs, files in os.walk(repo):

        dirs[:] = [
            directory
            for directory in dirs
            if directory not in IGNORED_DIRS
        ]

        for filename in files:

            if filename in IGNORED_FILES:
                continue

            path = Path(root) / filename

            relative = rel_path(path, repo)

            # Codigo inequivocamente de terceros: no entra al inventario.
            if is_excluded(relative):
                continue

            try:
                size = path.stat().st_size
            except OSError:
                continue

            result.append(
                {
                    "path": relative,
                    "name": filename,
                    "ext": path.suffix.lower(),
                    "language": language(path),
                    "size": size,
                    "text": (
                        path.suffix.lower()
                        in TEXT_EXTENSIONS
                        # Dockerfile, Makefile y .env.example no tienen
                        # extension reconocible, pero son de las fuentes de
                        # evidencia mas fiables que existen.
                        or filename in IMPORTANT_FILES
                    ),
                    "important": (
                        filename in IMPORTANT_FILES
                    ),
                    "third_party": is_third_party(relative),
                }
            )

    return result