import json
import subprocess
import sys
from pathlib import Path

import requests


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

API_FILE = BASE_DIR / "api.json"
README3_FILE = BASE_DIR / "readme3.py"

ZAI_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


# ============================================================
# UTILIDADES
# ============================================================

def error(message):
    print("")
    print(f"ERROR: {message}")
    print("")
    sys.exit(1)


# ============================================================
# LEER API.JSON
# ============================================================

def load_api():

    if not API_FILE.exists():
        error(
            f"No se encontró api.json:\n{API_FILE}"
        )

    try:
        with API_FILE.open(
            "r",
            encoding="utf-8"
        ) as f:
            config = json.load(f)

    except Exception as e:
        error(
            f"No se pudo leer api.json:\n{e}"
        )

    api_key = config.get("apikey")
    model = config.get("model")

    if not api_key:
        error(
            "api.json no contiene 'apikey'."
        )

    if not model:
        error(
            "api.json no contiene 'model'."
        )

    return api_key, model


# ============================================================
# EJECUTAR README3.PY
# ============================================================

def run_readme3(repo):

    if not README3_FILE.exists():
        error(
            f"No se encontró readme3.py:\n{README3_FILE}"
        )

    print("")
    print("=" * 70)
    print(" PASO 1/3 - ANALIZANDO REPOSITORIO")
    print("=" * 70)
    print("")

    command = [
        sys.executable,
        str(README3_FILE),
        str(repo)
    ]

    result = subprocess.run(
        command,
        cwd=BASE_DIR
    )

    if result.returncode != 0:
        error(
            "readme3.py terminó con errores."
        )


# ============================================================
# BUSCAR CONTEXTO COMPACTO
# ============================================================

def get_compact(repo):

    compact = (
        repo
        / "readme_context"
        / "README_CONTEXT_ULTRA.md"
    )

    if not compact.exists():
        error(
            "readme3.py terminó, pero no se encontró:\n"
            f"{compact}"
        )

    return compact


# ============================================================
# CREAR PROMPT
# ============================================================

def create_prompt(context):

    return f"""
Eres un ingeniero de software senior especializado
en documentación técnica.

Debes redactar el README.md profesional del software
analizado.

El contexto que recibirás fue generado automáticamente
desde el código fuente del repositorio.

REGLAS ABSOLUTAS:

- Usa el contexto como fuente de verdad.
- NO inventes funcionalidades.
- NO inventes tecnologías.
- NO inventes endpoints.
- NO inventes tablas.
- NO inventes comandos.
- NO inventes variables de entorno.
- NO inventes configuraciones.
- NO inventes características que no tengan evidencia.
- Si algo no puede determinarse, omítelo.
- No menciones que utilizaste una IA.
- No menciones este prompt.
- No menciones README_CONTEXT.
- No escribas explicaciones sobre el proceso.
- Devuelve solamente el contenido final del README.md.

El README debe ser claro, profesional y útil para
desarrolladores que necesiten entender, instalar,
configurar y ejecutar el proyecto.

Cuando exista evidencia suficiente, incluye:

# Nombre del proyecto

## Descripción

## Objetivo

## Características principales

## Tecnologías utilizadas

## Arquitectura

## Estructura del proyecto

## Requisitos

## Instalación

## Configuración

## Ejecución

## API

## Base de datos

## Variables de entorno

## Flujo de funcionamiento

## Uso

No es obligatorio incluir todas las secciones.

Es mejor omitir una sección que inventar información.

IMPORTANTE:

Si el proyecto ya posee un README, utilízalo como
referencia, pero mejora su calidad basándote en la
evidencia técnica del código.

No copies información que contradiga el código.

============================================================
CONTEXTO DEL REPOSITORIO
============================================================

{context}

============================================================
FIN DEL CONTEXTO
============================================================

Ahora genera ÚNICAMENTE el README.md final.
""".strip()


# ============================================================
# LLAMAR A Z.AI
# ============================================================

def call_zai(
    api_key,
    model,
    prompt
):

    print("")
    print("=" * 70)
    print(" PASO 2/3 - GENERANDO README CON Z.AI")
    print("=" * 70)
    print("")

    print(
        f"Modelo: {model}"
    )

    print(
        f"Contexto: {len(prompt):,} caracteres"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,

        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres un ingeniero de software senior "
                    "experto en documentación técnica."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],

        "temperature": 0.2,

        "stream": False
    }

    try:

        response = requests.post(
            ZAI_URL,
            headers=headers,
            json=payload,
            timeout=300
        )

    except requests.RequestException as e:

        error(
            f"No fue posible conectarse con Z.ai:\n{e}"
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
        TypeError
    ):

        error(
            "No se pudo obtener el contenido "
            "de la respuesta de Z.ai.\n\n"
            f"{json.dumps(data, indent=2, ensure_ascii=False)}"
        )

    return content


# ============================================================
# LIMPIAR RESPUESTA
# ============================================================

def clean_response(content):

    content = content.strip()

    # El modelo puede devolver:
    #
    # ```markdown
    # # Proyecto
    # ```
    #
    # Convertimos eso en Markdown puro.

    if content.startswith("```markdown"):

        content = content[
            len("```markdown"):
        ].strip()

        if content.endswith("```"):
            content = content[:-3].strip()

    elif content.startswith("```md"):

        content = content[
            len("```md"):
        ].strip()

        if content.endswith("```"):
            content = content[:-3].strip()

    elif content.startswith("```"):

        content = content[3:].strip()

        if content.endswith("```"):
            content = content[:-3].strip()

    return content


# ============================================================
# GUARDAR README
# ============================================================

def save_readme(
    repo,
    content
):

    output = repo / "README.md"

    output.write_text(
        content,
        encoding="utf-8"
    )

    return output


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # VALIDAR ARGUMENTOS
    # --------------------------------------------------------

    if len(sys.argv) != 2:

        print("")
        print("Uso:")
        print("")
        print(
            'python makeReadme.py "D:\\GitHub\\COIPO_ENTREGA_PLANTA"'
        )
        print("")

        sys.exit(1)

    repo = Path(
        sys.argv[1]
    ).resolve()

    if not repo.exists():

        error(
            f"No existe el repositorio:\n{repo}"
        )

    if not repo.is_dir():

        error(
            f"La ruta no es un directorio:\n{repo}"
        )

    print("")
    print("=" * 70)
    print(" MAKE README")
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
    # EJECUTAR ANALIZADOR
    # --------------------------------------------------------

    run_readme3(
        repo
    )

    # --------------------------------------------------------
    # LEER COMPACT
    # --------------------------------------------------------

    compact = get_compact(
        repo
    )

    print("")
    print(
        "Contexto compacto:"
    )
    print(
        f"  {compact}"
    )

    context = compact.read_text(
        encoding="utf-8"
    )

    print(
        f"  {len(context):,} caracteres"
    )

    # --------------------------------------------------------
    # CREAR PROMPT
    # --------------------------------------------------------

    prompt = create_prompt(
        context
    )

    # --------------------------------------------------------
    # Z.AI
    # --------------------------------------------------------

    readme = call_zai(
        api_key,
        model,
        prompt
    )

    readme = clean_response(
        readme
    )

    # --------------------------------------------------------
    # GUARDAR
    # --------------------------------------------------------

    output = save_readme(
        repo,
        readme
    )

    print("")
    print("=" * 70)
    print(" PASO 3/3 - README GENERADO")
    print("=" * 70)
    print("")

    print(
        f"Archivo:\n{output}"
    )

    print("")
    print(
        f"Tamaño: {len(readme):,} caracteres"
    )

    print("")
    print("Proceso terminado correctamente.")
    print("")


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    main()
