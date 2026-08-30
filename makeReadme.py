import json
import os
import subprocess
import sys
from pathlib import Path

import requests


# ============================================================
# MAKE README - EVIDENCE FIRST
#
# Flujo:
#
#   readme3.py
#       ↓
#   README_EVIDENCE.json
#   README_CONTEXT_ULTRA.md
#       ↓
#   Z.ai
#       ↓
#   README_CANDIDATE.md
#       ↓
#   validate_readme.py
#       ↓
#   PASS → README.md
#   FAIL → Z.ai corrige → validación
#
# Principio:
#
#   El LLM redacta.
#   La evidencia decide.
# ============================================================


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

API_FILE = BASE_DIR / "api.json"

README3_FILE = BASE_DIR / "readme3.py"

VALIDATOR_FILE = BASE_DIR / "validate_readme.py"

ZAI_URL = (
    "https://open.bigmodel.cn/api/paas/v4/chat/completions"
)

CANDIDATE_FILE_NAME = "README_CANDIDATE.md"

MAX_REPAIR_ATTEMPTS = 2


# ============================================================
# UTILIDADES
# ============================================================

def error(message):
    print("")
    print(f"ERROR: {message}")
    print("")
    sys.exit(1)


def run_command(command, cwd):

    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            text=True,
        )
    except Exception as exc:
        error(
            "No fue posible ejecutar el comando.\n"
            f"{exc}"
        )

    if result.returncode != 0:
        error(
            "El comando terminó con errores:\n"
            + " ".join(command)
        )


# ============================================================
# LEER API
# ============================================================

def load_api():

    # --------------------------------------------------------
    # Primero intentar variables de entorno.
    # --------------------------------------------------------

    api_key = os.getenv(
        "ZAI_API_KEY"
    )

    model = os.getenv(
        "ZAI_MODEL"
    )

    if api_key:

        if not model:
            model = "glm-4.5"

        return api_key, model

    # --------------------------------------------------------
    # Compatibilidad con api.json
    # --------------------------------------------------------

    if not API_FILE.exists():

        error(
            "No se encontró ZAI_API_KEY "
            "ni api.json.\n\n"
            f"Esperado:\n{API_FILE}"
        )

    try:

        with API_FILE.open(
            "r",
            encoding="utf-8"
        ) as f:

            config = json.load(f)

    except Exception as exc:

        error(
            f"No se pudo leer api.json:\n{exc}"
        )

    api_key = config.get(
        "apikey"
    )

    model = config.get(
        "model"
    )

    if not api_key:

        error(
            "api.json no contiene "
            "'apikey'."
        )

    if not model:

        error(
            "api.json no contiene "
            "'model'."
        )

    return api_key, model


# ============================================================
# EJECUTAR README3
# ============================================================

def run_readme3(repo):

    if not README3_FILE.exists():

        error(
            f"No se encontró readme3.py:\n"
            f"{README3_FILE}"
        )

    print("")
    print("=" * 70)
    print(
        " PASO 1/4 - EXTRAyENDO EVIDENCIA"
    )
    print("=" * 70)
    print("")

    command = [
        sys.executable,
        str(README3_FILE),
        str(repo),
    ]

    run_command(
        command,
        BASE_DIR,
    )


# ============================================================
# OBTENER ARCHIVOS DE CONTEXTO
# ============================================================

def get_context_files(repo):

    context_dir = (
        repo
        / "readme_context"
    )

    compact = (
        context_dir
        / "README_CONTEXT_ULTRA.md"
    )

    evidence = (
        context_dir
        / "README_EVIDENCE.json"
    )

    if not compact.exists():

        error(
            "readme3.py terminó, pero "
            "no existe:\n"
            f"{compact}"
        )

    if not evidence.exists():

        error(
            "readme3.py terminó, pero "
            "no existe:\n"
            f"{evidence}"
        )

    return compact, evidence


# ============================================================
# README EXISTENTE
# ============================================================

def get_existing_readme(repo):

    readme = repo / "README.md"

    if not readme.exists():
        return ""

    try:

        return readme.read_text(
            encoding="utf-8",
            errors="ignore",
        )

    except Exception:

        return ""


# ============================================================
# PROMPT PRINCIPAL
# ============================================================

def create_generation_prompt(
    repo,
    context,
    evidence_json,
    existing_readme,
):

    return f"""
Eres un ingeniero de software senior especializado
en documentación técnica profesional de repositorios
reales.

Tu tarea es generar el README.md definitivo del proyecto.

============================================================
FUENTE DE VERDAD
============================================================

README_EVIDENCE.json es la fuente primaria de evidencia.

README_CONTEXT_ULTRA.md es un resumen auxiliar.

El README existente puede utilizarse como referencia
histórica, pero NO debe prevalecer sobre la evidencia
actual del repositorio.

============================================================
REGLA FUNDAMENTAL
============================================================

SOLO escribas afirmaciones que puedan sustentarse
directamente con la evidencia disponible.

NO INVENTES.

No inventes:

- funcionalidades
- tecnologías
- frameworks
- librerías
- endpoints
- métodos HTTP
- tablas
- modelos
- variables de entorno
- comandos
- scripts
- roles
- arquitectura
- servicios
- infraestructura
- proveedores cloud
- configuraciones
- credenciales
- flujos de negocio

No conviertas señales débiles en hechos.

No conviertas nombres de archivos en funcionalidades.

No conviertas nombres de carpetas en funcionalidades.

No conviertas una dependencia instalada en una capacidad
de producción.

No conviertas una palabra encontrada en el código en una
característica del producto.

============================================================
NIVELES DE EVIDENCIA
============================================================

EVIDENCIA ALTA:

- dependencia declarada
- endpoint explícito
- variable de entorno explícita
- tabla SQL explícita
- script package.json explícito
- configuración explícita
- archivo Docker explícito
- código funcional claramente identificable

EVIDENCIA MEDIA:

- múltiples archivos relacionados
- componentes y servicios coherentes
- referencias cruzadas suficientes

EVIDENCIA BAJA:

- nombres de carpetas
- nombres de funciones
- palabras clave aisladas
- archivos cuyo contenido no demuestra funcionalidad

No presentes evidencia baja como funcionalidad confirmada.

============================================================
OBJETIVO DEL README
============================================================

El README debe permitir que un desarrollador entienda:

- qué es el proyecto
- para qué sirve
- cómo está organizado
- qué tecnologías utiliza realmente
- cómo instalarlo
- cómo configurarlo
- cómo ejecutarlo
- qué API existe realmente
- qué persistencia existe realmente
- cómo se relacionan sus componentes

Solo cuando exista evidencia suficiente.

============================================================
ESTRUCTURA RECOMENDADA
============================================================

# Nombre del proyecto

## Descripción

## Objetivo

## Arquitectura

## Stack técnico

## Estructura del proyecto

## Requisitos

## Instalación

## Configuración

## Ejecución

## API

## Base de datos

## Flujo de funcionamiento

## Desarrollo

## Pruebas

## Despliegue

## Limitaciones conocidas

NO es obligatorio utilizar todas las secciones.

Omitir una sección es preferible a inventarla.

============================================================
REGLAS DE API
============================================================

Solo documenta endpoints encontrados explícitamente
en la evidencia.

No deduzcas:

- endpoints por nombres de funciones
- endpoints por frontend
- endpoints por modelos
- endpoints por nombres de archivos

Distingue:

backend routes
de
frontend API calls.

============================================================
REGLAS DE BASE DE DATOS
============================================================

Solo documenta tablas cuando exista evidencia suficiente.

No inventes:

- relaciones
- claves
- índices
- motores
- migraciones
- esquemas

si no aparecen en la evidencia.

============================================================
REGLAS DE CONFIGURACIÓN
============================================================

Documenta únicamente las variables de entorno realmente
detectadas.

No inventes valores.

No expongas secretos.

No muestres claves API reales.

============================================================
REGLAS DE INSTALACIÓN Y EJECUCIÓN
============================================================

Solo escribe comandos respaldados por:

- package.json
- requirements.txt
- pyproject.toml
- Dockerfile
- docker-compose
- scripts existentes
- documentación existente coherente

No generes comandos genéricos por conocimiento externo.

============================================================
CALIDAD
============================================================

El README debe ser:

- técnico
- preciso
- profesional
- claro
- estructurado
- útil para mantenimiento
- específico del repositorio

Evita texto promocional.

Evita frases genéricas que podrían aplicarse
a cualquier proyecto.

No describas el proceso de generación.

No menciones IA.

No menciones este prompt.

No menciones README_EVIDENCE.

No menciones README_CONTEXT.

============================================================
README EXISTENTE
============================================================

{existing_readme}

============================================================
CONTEXTO
============================================================

{context}

============================================================
EVIDENCIA ESTRUCTURADA
============================================================

{evidence_json}

============================================================
SALIDA
============================================================

Devuelve exclusivamente el contenido final de README.md.

No lo envuelvas en ```markdown.

No agregues explicaciones antes o después.
""".strip()


# ============================================================
# PROMPT DE REPARACIÓN
# ============================================================

def create_repair_prompt(
    candidate,
    audit,
    context,
    evidence_json,
):

    return f"""
Eres un auditor técnico senior.

Debes corregir el README mostrado abajo.

Tu objetivo NO es hacerlo más completo.

Tu objetivo es hacerlo MÁS VERAZ.

============================================================
AUDITORÍA
============================================================

{audit}

============================================================
REGLAS
============================================================

Elimina cualquier afirmación que no pueda demostrar:

- una funcionalidad
- una tecnología
- un endpoint
- una tabla
- una variable
- un comando
- una configuración
- una arquitectura
- un servicio
- una capacidad de negocio

No sustituyas una afirmación inventada
por otra afirmación inventada.

No agregues contenido nuevo salvo que esté
claramente respaldado por la evidencia.

No escribas explicaciones meta.

No menciones la auditoría.

No menciones IA.

No menciones README_EVIDENCE.

No menciones README_CONTEXT.

No uses frases como:

"probablemente"
"parece"
"podría"
"se espera"
"posiblemente"

Si algo no puede verificarse:

ELIMÍNALO.

============================================================
README
============================================================

{candidate}

============================================================
CONTEXTO
============================================================

{context}

============================================================
EVIDENCIA
============================================================

{evidence_json}

============================================================
SALIDA
============================================================

Devuelve exclusivamente el README corregido.
""".strip()


# ============================================================
# LLAMAR A Z.AI
# ============================================================

def call_zai(
    api_key,
    model,
    prompt,
    label="GENERANDO README",
):

    print("")
    print("=" * 70)
    print(
        f" {label}"
    )
    print("=" * 70)
    print("")

    print(
        f"Modelo: {model}"
    )

    print(
        f"Prompt: {len(prompt):,} caracteres"
    )

    headers = {
        "Authorization": (
            f"Bearer {api_key}"
        ),
        "Content-Type": (
            "application/json"
        ),
    }

    payload = {
        "model": model,

        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres un ingeniero de software "
                    "senior experto en documentación "
                    "técnica verificable."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],

        "temperature": 0.1,

        "stream": False,
    }

    try:

        response = requests.post(
            ZAI_URL,
            headers=headers,
            json=payload,
            timeout=300,
        )

    except requests.RequestException as exc:

        error(
            "No fue posible conectarse con Z.ai:\n"
            f"{exc}"
        )

    if response.status_code != 200:

        try:
            details = response.json()

        except Exception:
            details = response.text

        error(
            "Z.ai devolvió un error.\n\n"
            f"HTTP: {response.status_code}\n"
            f"Respuesta:\n{details}"
        )

    try:

        data = response.json()

    except Exception:

        error(
            "Z.ai no devolvió una respuesta JSON válida."
        )

    try:

        content = (
            data["choices"][0]
            ["message"]["content"]
        )

    except (
        KeyError,
        IndexError,
        TypeError,
    ):

        error(
            "No se pudo obtener el contenido "
            "de la respuesta de Z.ai.\n\n"
            + json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            )
        )

    return content


# ============================================================
# LIMPIAR RESPUESTA
# ============================================================

def clean_response(content):

    content = content.strip()

    wrappers = (
        "```markdown",
        "```md",
        "```",
    )

    for wrapper in wrappers:

        if content.startswith(wrapper):

            content = (
                content[
                    len(wrapper):
                ]
                .strip()
            )

            if content.endswith("```"):

                content = (
                    content[:-3]
                    .strip()
                )

            break

    return content


# ============================================================
# GUARDAR CANDIDATO
# ============================================================

def save_candidate(
    repo,
    content,
):

    output = (
        repo
        / CANDIDATE_FILE_NAME
    )

    try:

        output.write_text(
            content.strip() + "\n",
            encoding="utf-8",
        )

    except Exception as exc:

        error(
            "No se pudo guardar README_CANDIDATE.md:\n"
            f"{exc}"
        )

    return output


# ============================================================
# EJECUTAR VALIDADOR
# ============================================================

def validate_readme(
    repo,
    candidate,
    evidence,
):

    if not VALIDATOR_FILE.exists():

        error(
            f"No se encontró validate_readme.py:\n"
            f"{VALIDATOR_FILE}"
        )

    command = [
        sys.executable,
        str(VALIDATOR_FILE),
        str(candidate),
        str(evidence),
    ]

    process = subprocess.run(
        command,
        cwd=BASE_DIR,
        text=True,
        capture_output=True,
    )

    output = (
        process.stdout
        + "\n"
        + process.stderr
    ).strip()

    return (
        process.returncode,
        output,
    )


# ============================================================
# GUARDAR README FINAL
# ============================================================

def save_final(
    repo,
    content,
):

    output = (
        repo
        / "README.md"
    )

    try:

        output.write_text(
            content.strip() + "\n",
            encoding="utf-8",
        )

    except Exception as exc:

        error(
            "No se pudo guardar README.md:\n"
            f"{exc}"
        )

    return output


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # ARGUMENTOS
    # --------------------------------------------------------

    if len(sys.argv) != 2:

        print("")
        print("Uso:")
        print("")
        print(
            'python makeReadme.py '
            '"D:\\GitHub\\COIPO_ENTREGA_PLANTA"'
        )
        print("")

        sys.exit(1)

    repo = Path(
        sys.argv[1]
    ).resolve()

    if not repo.exists():

        error(
            f"No existe el repositorio:\n"
            f"{repo}"
        )

    if not repo.is_dir():

        error(
            f"La ruta no es un directorio:\n"
            f"{repo}"
        )

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    print("")
    print("=" * 70)
    print(
        " MAKE README - EVIDENCE FIRST"
    )
    print("=" * 70)
    print("")

    print(
        f"Repositorio:\n{repo}"
    )

    # --------------------------------------------------------
    # API
    # --------------------------------------------------------

    api_key, model = load_api()

    # --------------------------------------------------------
    # STEP 1
    # --------------------------------------------------------

    run_readme3(
        repo
    )

    compact_file, evidence_file = (
        get_context_files(
            repo
        )
    )

    print("")
    print(
        "Contexto:"
    )
    print(
        f"  {compact_file}"
    )

    print(
        "Evidencia:"
    )
    print(
        f"  {evidence_file}"
    )

    # --------------------------------------------------------
    # LEER CONTEXTO
    # --------------------------------------------------------

    try:

        context = compact_file.read_text(
            encoding="utf-8"
        )

        evidence_json = evidence_file.read_text(
            encoding="utf-8"
        )

    except Exception as exc:

        error(
            "No se pudo leer el contexto de README3:\n"
            f"{exc}"
        )

    # Validar que JSON sea realmente JSON.

    try:

        json.loads(
            evidence_json
        )

    except Exception as exc:

        error(
            "README_EVIDENCE.json no es válido:\n"
            f"{exc}"
        )

    existing_readme = (
        get_existing_readme(
            repo
        )
    )

    # --------------------------------------------------------
    # STEP 2
    # --------------------------------------------------------

    prompt = create_generation_prompt(
        repo,
        context,
        evidence_json,
        existing_readme,
    )

    readme = call_zai(
        api_key,
        model,
        prompt,
        label=(
            "PASO 2/4 - GENERANDO README CON Z.AI"
        ),
    )

    readme = clean_response(
        readme
    )

    candidate = save_candidate(
        repo,
        readme,
    )

    print("")
    print(
        f"README candidato:\n{candidate}"
    )

    # --------------------------------------------------------
    # STEP 3 - VALIDACIÓN
    # --------------------------------------------------------

    print("")
    print("=" * 70)
    print(
        " PASO 3/4 - VALIDANDO README"
    )
    print("=" * 70)
    print("")

    return_code, audit = validate_readme(
        repo,
        candidate,
        evidence_file,
    )

    print(audit)

    # --------------------------------------------------------
    # STEP 4 - REPARACIÓN
    # --------------------------------------------------------

    attempt = 0

    while (
        return_code != 0
        and attempt < MAX_REPAIR_ATTEMPTS
    ):

        attempt += 1

        print("")
        print("=" * 70)
        print(
            f" PASO 4/4 - REPARACIÓN "
            f"{attempt}/{MAX_REPAIR_ATTEMPTS}"
        )
        print("=" * 70)
        print("")

        repair_prompt = create_repair_prompt(
            candidate=readme,
            audit=audit,
            context=context,
            evidence_json=evidence_json,
        )

        readme = call_zai(
            api_key,
            model,
            repair_prompt,
            label=(
                f"REPARANDO README "
                f"(INTENTO {attempt})"
            ),
        )

        readme = clean_response(
            readme
        )

        candidate = save_candidate(
            repo,
            readme,
        )

        return_code, audit = validate_readme(
            repo,
            candidate,
            evidence_file,
        )

        print("")
        print(audit)

    # --------------------------------------------------------
    # RESULTADO FINAL
    # --------------------------------------------------------

    if return_code != 0:

        print("")
        print("=" * 70)
        print(
            " README RECHAZADO"
        )
        print("=" * 70)
        print("")

        print(
            "El README no superó la validación."
        )

        print(
            f"Puedes revisar:\n{candidate}"
        )

        error(
            "README.md NO fue sobrescrito porque "
            "la validación falló."
        )

    final = save_final(
        repo,
        readme,
    )

    print("")
    print("=" * 70)
    print(
        " README FINAL GENERADO"
    )
    print("=" * 70)
    print("")

    print(
        f"Archivo:\n{final}"
    )

    print(
        f"Tamaño: {len(readme):,} caracteres"
    )

    print("")
    print(
        "Validación: PASS"
    )

    print("")
    print(
        "Proceso terminado correctamente."
    )
    print("")


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    main()