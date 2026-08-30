from __future__ import annotations

import json
import re
import sys
from pathlib import Path


# ============================================================
# VALIDATE README
#
# Objetivo:
#   Comprobar que README_CANDIDATE.md no documente
#   elementos que no aparecen en la evidencia generada
#   por readme3.py.
#
# Valida principalmente:
#   - endpoints
#   - variables de entorno
#   - tecnologías
#   - tablas
#   - comandos
#   - estructura mínima
#
# Resultado:
#   PASS = no se detectaron errores críticos
#   FAIL = existen afirmaciones técnicas no verificadas
# ============================================================


# ============================================================
# CONFIGURACIÓN
# ============================================================

IGNORED_ENV_NAMES = {
    "README",
    "API",
    "URL",
    "HTTP",
    "HTTPS",
    "UTF8",
    "UTF_8",
    "ASCII",
}

GENERIC_WORDS = {
    "api",
    "http",
    "https",
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "readme",
    "json",
    "yaml",
    "html",
    "css",
    "js",
    "ts",
    "python",
    "project",
    "system",
    "software",
}


# ============================================================
# UTILIDADES
# ============================================================

def load_json(path: Path):

    try:

        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:

        print(
            f"ERROR: no se pudo leer {path}:\n{exc}"
        )

        sys.exit(2)


# ============================================================
# EVIDENCIA
# ============================================================

def get_evidence_environment_variables(
    evidence
):

    values = set()

    for item in evidence.get(
        "environment_variables",
        []
    ):

        if isinstance(item, dict):

            value = item.get(
                "value"
            )

        else:

            value = item

        if value:
            values.add(
                value
            )

    return values


def get_evidence_endpoints(
    evidence
):

    values = set()

    for item in evidence.get(
        "api",
        []
    ):

        if not isinstance(
            item,
            dict
        ):
            continue

        method = item.get(
            "method"
        )

        path = item.get(
            "path"
        )

        if method and path:

            values.add(
                f"{method.upper()} {path}"
            )

    return values


def get_evidence_technologies(
    evidence
):

    values = set()

    technologies = evidence.get(
        "technologies",
        {}
    )

    if isinstance(
        technologies,
        dict
    ):

        values.update(
            technologies.keys()
        )

    elif isinstance(
        technologies,
        list
    ):

        values.update(
            technologies
        )

    return values


def get_evidence_tables(
    evidence
):

    values = set()

    for item in evidence.get(
        "database_tables",
        []
    ):

        if isinstance(
            item,
            dict
        ):

            value = item.get(
                "value"
            )

        else:

            value = item

        if value:
            values.add(
                value
            )

    return values


def get_evidence_commands(
    evidence
):

    values = set()

    dependencies = evidence.get(
        "dependencies",
        {}
    )

    # Los scripts NPM están contenidos normalmente
    # dentro del análisis de package.json.
    analysis = evidence.get(
        "analysis",
        {}
    )

    for data in analysis.values():

        package = data.get(
            "package_json",
            {}
        )

        for script in package.get(
            "scripts",
            []
        ):

            if isinstance(
                script,
                dict
            ):

                command = script.get(
                    "command"
                )

                if command:
                    values.add(
                        command
                    )

    # Compatibilidad adicional:
    # algunas implementaciones pueden guardar
    # los comandos directamente.
    for command in evidence.get(
        "commands",
        []
    ):

        if isinstance(
            command,
            dict
        ):

            value = command.get(
                "value"
            )

        else:

            value = command

        if value:
            values.add(
                value
            )

    return values


# ============================================================
# EXTRAER DEL README
# ============================================================

def extract_env_variables(
    readme
):

    values = set()

    # Variables en backticks
    pattern_backticks = re.compile(
        r"`([A-Z][A-Z0-9_]{2,})`"
    )

    for match in pattern_backticks.finditer(
        readme
    ):

        value = match.group(1)

        if (
            "_" in value
            and value not in IGNORED_ENV_NAMES
        ):

            values.add(
                value
            )

    # Variables en texto
    pattern_plain = re.compile(
        r"\b([A-Z][A-Z0-9_]{2,})\b"
    )

    for match in pattern_plain.finditer(
        readme
    ):

        value = match.group(1)

        if (
            "_" in value
            and value not in IGNORED_ENV_NAMES
        ):

            values.add(
                value
            )

    return values


def extract_endpoints(
    readme
):

    values = set()

    pattern = re.compile(
        r"\b"
        r"(GET|POST|PUT|PATCH|DELETE)"
        r"\s+"
        r"`?("
        r"/[A-Za-z0-9_./:{}\-?=&]+"
        r")"
        r"`?",
        re.IGNORECASE,
    )

    for match in pattern.finditer(
        readme
    ):

        method = match.group(
            1
        ).upper()

        path = match.group(
            2
        )

        values.add(
            f"{method} {path}"
        )

    return values


def extract_technologies(
    readme,
    known_technologies,
):

    found = set()

    lower = readme.lower()

    aliases = {
        "postgres": "PostgreSQL",
        "postgresql": "PostgreSQL",
        "sqlite": "SQLite",
        "redis": "Redis",
        "fastapi": "FastAPI",
        "flask": "Flask",
        "django": "Django",
        "react": "React",
        "vite": "Vite",
        "express": "Express",
        "node.js": "Node.js",
        "nodejs": "Node.js",
        "leaflet": "Leaflet",
        "mapbox": "Mapbox",
        "tailwind": "Tailwind",
        "pandas": "Pandas",
        "numpy": "NumPy",
        "opencv": "OpenCV",
        "yolo": "YOLO",
        "sqlalchemy": "SQLAlchemy",
        "docker": "Docker",
        "vue": "Vue",
        "angular": "Angular",
    }

    for alias, canonical in aliases.items():

        if alias in lower:

            # Solo marcamos como problema si la tecnología
            # no aparece en la evidencia.
            if canonical not in known_technologies:

                found.add(
                    canonical
                )

    return found


def extract_table_mentions(
    readme
):

    values = set()

    # Busca nombres dentro de backticks que parezcan
    # tablas. Es deliberadamente conservador.
    pattern = re.compile(
        r"`([a-zA-Z_][a-zA-Z0-9_]*)`"
    )

    for match in pattern.finditer(
        readme
    ):

        value = match.group(1)

        lower = value.lower()

        if (
            lower not in GENERIC_WORDS
            and not lower.startswith("http")
            and not lower.endswith(".py")
            and not lower.endswith(".js")
            and not lower.endswith(".ts")
        ):

            values.add(
                value
            )

    return values


# ============================================================
# COMANDOS
# ============================================================

def extract_commands(
    readme
):

    values = set()

    patterns = [
        r"(?m)^\s*(python(?:3)?\s+[^\n]+)$",
        r"(?m)^\s*(pip(?:3)?\s+[^\n]+)$",
        r"(?m)^\s*(npm\s+[^\n]+)$",
        r"(?m)^\s*(npx\s+[^\n]+)$",
        r"(?m)^\s*(uvicorn\s+[^\n]+)$",
        r"(?m)^\s*(docker\s+[^\n]+)$",
        r"(?m)^\s*(docker-compose\s+[^\n]+)$",
    ]

    for pattern in patterns:

        for match in re.finditer(
            pattern,
            readme,
            re.IGNORECASE,
        ):

            values.add(
                match.group(1).strip()
            )

    return values


# ============================================================
# VALIDACIÓN
# ============================================================

def validate(
    readme,
    evidence,
):

    errors = []
    warnings = []

    # --------------------------------------------------------
    # Evidencia
    # --------------------------------------------------------

    evidence_env = (
        get_evidence_environment_variables(
            evidence
        )
    )

    evidence_endpoints = (
        get_evidence_endpoints(
            evidence
        )
    )

    evidence_technologies = (
        get_evidence_technologies(
            evidence
        )
    )

    evidence_tables = (
        get_evidence_tables(
            evidence
        )
    )

    evidence_commands = (
        get_evidence_commands(
            evidence
        )
    )

    # --------------------------------------------------------
    # README
    # --------------------------------------------------------

    mentioned_env = (
        extract_env_variables(
            readme
        )
    )

    mentioned_endpoints = (
        extract_endpoints(
            readme
        )
    )

    unsupported_technologies = (
        extract_technologies(
            readme,
            evidence_technologies,
        )
    )

    mentioned_tables = (
        extract_table_mentions(
            readme
        )
    )

    mentioned_commands = (
        extract_commands(
            readme
        )
    )

    # --------------------------------------------------------
    # ENV
    # --------------------------------------------------------

    for variable in sorted(
        mentioned_env
    ):

        if variable not in evidence_env:

            warnings.append(
                "Variable posiblemente no "
                f"respaldada: {variable}"
            )

    # --------------------------------------------------------
    # ENDPOINTS
    # --------------------------------------------------------

    for endpoint in sorted(
        mentioned_endpoints
    ):

        if endpoint not in evidence_endpoints:

            errors.append(
                "Endpoint no encontrado en "
                f"la evidencia: {endpoint}"
            )

    # --------------------------------------------------------
    # TECHNOLOGIES
    # --------------------------------------------------------

    for technology in sorted(
        unsupported_technologies
    ):

        warnings.append(
            "Tecnología mencionada sin "
            f"evidencia directa: {technology}"
        )

    # --------------------------------------------------------
    # TABLES
    # --------------------------------------------------------

    # Solo comprobamos tablas cuando la evidencia
    # contiene tablas reales. Esto evita falsos positivos
    # por cualquier término técnico entre backticks.

    if evidence_tables:

        for table in sorted(
            mentioned_tables
        ):

            if (
                table not in evidence_tables
            ):

                # Reducimos falsos positivos.
                lower = table.lower()

                if (
                    lower
                    not in GENERIC_WORDS
                ):

                    warnings.append(
                        "Tabla potencialmente no "
                        "verificada: "
                        f"{table}"
                    )

    # --------------------------------------------------------
    # COMMANDS
    # --------------------------------------------------------

    if evidence_commands:

        for command in sorted(
            mentioned_commands
        ):

            if command not in evidence_commands:

                warnings.append(
                    "Comando potencialmente no "
                    "verificado: "
                    f"{command}"
                )

    # --------------------------------------------------------
    # LONGITUD
    # --------------------------------------------------------

    if len(
        readme.strip()
    ) < 300:

        errors.append(
            "README demasiado corto."
        )

    # --------------------------------------------------------
    # ESTRUCTURA
    # --------------------------------------------------------

    required_concepts = [
        "descripción",
        "instalación",
        "ejecución",
    ]

    lower_readme = (
        readme.lower()
    )

    for concept in required_concepts:

        if concept not in lower_readme:

            warnings.append(
                "No se encontró una sección "
                f"relacionada con '{concept}'."
            )

    # --------------------------------------------------------
    # FRASES DE INCERTIDUMBRE
    # --------------------------------------------------------

    uncertainty_patterns = [
        "probablemente",
        "posiblemente",
        "parece utilizar",
        "podría utilizar",
        "se espera que",
        "aparentemente",
    ]

    for phrase in uncertainty_patterns:

        if phrase in lower_readme:

            warnings.append(
                "El README contiene lenguaje "
                f"incierto: '{phrase}'"
            )

    # --------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "statistics": {
            "environment_variables": len(
                mentioned_env
            ),
            "endpoints": len(
                mentioned_endpoints
            ),
            "unsupported_technologies": len(
                unsupported_technologies
            ),
            "table_mentions": len(
                mentioned_tables
            ),
            "commands": len(
                mentioned_commands
            ),
        },
    }


# ============================================================
# MAIN
# ============================================================

def main():

    if len(sys.argv) != 3:

        print("")
        print("Uso:")
        print("")
        print(
            'python validate_readme.py '
            '"README_CANDIDATE.md" '
            '"README_EVIDENCE.json"'
        )
        print("")

        sys.exit(2)

    readme_file = Path(
        sys.argv[1]
    ).resolve()

    evidence_file = Path(
        sys.argv[2]
    ).resolve()

    if not readme_file.exists():

        print(
            f"ERROR: no existe:\n{readme_file}"
        )

        sys.exit(2)

    if not evidence_file.exists():

        print(
            f"ERROR: no existe:\n{evidence_file}"
        )

        sys.exit(2)

    readme = readme_file.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    evidence = load_json(
        evidence_file
    )

    result = validate(
        readme,
        evidence,
    )

    print("")
    print("=" * 70)
    print(
        " README AUDIT"
    )
    print("=" * 70)
    print("")

    print(
        "Estado: "
        + (
            "PASS"
            if result["valid"]
            else "FAIL"
        )
    )

    print(
        f"Endpoints detectados: "
        f"{result['statistics']['endpoints']}"
    )

    print(
        f"Variables detectadas: "
        f"{result['statistics']['environment_variables']}"
    )

    print(
        f"Tecnologías no verificadas: "
        f"{result['statistics']['unsupported_technologies']}"
    )

    print(
        f"Tablas mencionadas: "
        f"{result['statistics']['table_mentions']}"
    )

    print(
        f"Comandos mencionados: "
        f"{result['statistics']['commands']}"
    )

    print("")

    # --------------------------------------------------------
    # ERRORES
    # --------------------------------------------------------

    if result["errors"]:

        print(
            "ERRORES"
        )

        print(
            "-" * 70
        )

        for item in result["errors"]:

            print(
                f"- {item}"
            )

        print("")

    # --------------------------------------------------------
    # WARNINGS
    # --------------------------------------------------------

    if result["warnings"]:

        print(
            "ADVERTENCIAS"
        )

        print(
            "-" * 70
        )

        for item in result["warnings"]:

            print(
                f"- {item}"
            )

        print("")

    # --------------------------------------------------------
    # EXIT CODE
    # --------------------------------------------------------

    if result["valid"]:

        print(
            "Validación completada."
        )

        sys.exit(0)

    print(
        "Validación fallida."
    )

    sys.exit(1)


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    main()