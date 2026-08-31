from __future__ import annotations

import os
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
    """Lee un archivo de texto sin hacer fallar el análisis."""

    try:
        return path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except Exception:
        return None


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

            try:
                size = path.stat().st_size
            except OSError:
                continue

            result.append(
                {
                    "path": rel_path(path, repo),
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