import json
import random
import subprocess
import sys
import time
from pathlib import Path

import requests

from delete_files import (
    construir as construir_delete_files,
    crear_prompt as crear_prompt_limpieza,
    parsear_respuesta as parsear_limpieza,
)
from pr_body import (
    cargar_evidencia,
    construir as construir_informe,
    escribir as escribir_informe,
)
from insumos_inversos import (
    crear_prompt as crear_prompt_insumos,
    escribir as escribir_insumos,
    hay_insumos_humanos,
    parsear as parsear_insumos,
    preparar as preparar_insumos,
)
from readme3_orphans import find_candidates, resumen as resumen_orphans
from readme3_fingerprint import (
    compute as calcular_huella,
    leer as leer_huella,
    quitar as quitar_huella,
    sellar as sellar_huella,
)
from readme_merge import decidir_accion, merge


# ============================================================
# SALIDA TEMPRANA
# ============================================================

class _ResultadoSimple:
    """Forma minima que espera el informe cuando no hubo fusion."""

    def __init__(self, accion, motivo):
        self.accion = accion
        self.motivo = motivo
        self.conflictos = []
        self.escribe = False


def generar_insumos(repo, evidencia, contexto, api_key, model):
    """
    Reconstruye insumos/ desde el codigo, con su propia llamada al modelo.

    Nunca sobrescribe un insumos/ levantado con personas: en ese caso lo
    derivado va a un archivo aparte para contrastar.
    """

    try:

        hallazgos, ignorados = preparar_insumos(
            repo,
            evidencia.get("files") or [],
        )

        prompt = crear_prompt_insumos(
            contexto=contexto,
            hallazgos_pii=hallazgos,
            ignorados=ignorados,
            nombre_repo=repo.name,
            insumos_existentes=hay_insumos_humanos(repo),
        )

        respuesta = call_zai(
            api_key,
            model,
            prompt,
            "INSUMOS INVERSOS - RECONSTRUYENDO DESDE EL CODIGO",
        )

        partes = parsear_insumos(respuesta)

        if not partes:
            print("")
            print(
                "AVISO: la respuesta no traia los separadores esperados. "
                "No se escribio ningun insumo."
            )
            return None

        resultado = escribir_insumos(repo, partes, hallazgos)

        print("")
        print("=" * 70)
        print(" INSUMOS INVERSOS")
        print("=" * 70)
        print("")
        print(resultado["motivo"])
        print("")
        print("Escritos: " + ", ".join(resultado["escritos"]))

        if "INFORME" in partes:
            print("")
            print(partes["INFORME"][:2000])

        return resultado

    except SystemExit:
        print("")
        print(
            "AVISO: no se pudieron generar los insumos. La corrida sigue."
        )
        return None

    except Exception as exc:
        print("")
        print(f"AVISO: no se pudieron generar los insumos: {exc}")
        return None


def generar_delete_files(repo, evidencia, veredicto=None):
    """
    Escribe delete_files.md.

    La deteccion de candidatos es determinista y no necesita al modelo, asi
    que el archivo se genera tambien cuando la corrida termina temprano. El
    modelo, cuando se le llama, solo aporta el juicio y la justificacion.
    """

    try:

        candidatos = find_candidates(
            repo,
            evidencia.get("files") or [],
            evidencia.get("analysis") or {},
        )

        if not candidatos:
            return None, []

        contenido = construir_delete_files(
            nombre_repo=repo.name,
            candidatos=candidatos,
            veredicto=veredicto or {"borrar": [], "revisar": []},
            resumen_detector=resumen_orphans(
                candidatos,
                len(evidencia.get("files") or []),
            ),
            total_archivos=len(evidencia.get("files") or []),
        )

        destino = repo / DELETE_FILE_NAME

        destino.write_text(contenido, encoding="utf-8")

        print("")
        print(
            f"Candidatos a borrar: {len(candidatos)} -> {destino}"
        )

        return destino, candidatos

    except Exception as exc:

        # Util, pero nunca puede tumbar la corrida.
        print("")
        print(f"AVISO: no se pudo generar {DELETE_FILE_NAME}: {exc}")

        return None, []


def detener(repo, titulo, mensaje, evidencia, accion):
    """
    Termina la corrida sin llamar al modelo, dejando el informe escrito.

    Es una salida con exito, no un fallo: no haber cambiado nada es el
    resultado correcto cuando no hay nada que cambiar.
    """

    print("")
    print("=" * 70)
    print(f" {titulo}")
    print("=" * 70)
    print("")
    print(mensaje)

    try:
        escribir_informe(
            repo / REPORT_FILE_NAME,
            construir_informe(
                nombre_repo=repo.name,
                resultado_merge=_ResultadoSimple(accion, mensaje),
                evidencia=evidencia,
            ),
        )

        print("")
        print(f"Informe: {repo / REPORT_FILE_NAME}")

    except Exception as exc:
        print("")
        print(f"AVISO: no se pudo generar el informe: {exc}")

    # La lista de candidatos a borrar es determinista: se genera igual,
    # aunque no se haya llamado al modelo. Sin juicio, todo cae en
    # "Revisar", que es el lado seguro.
    generar_delete_files(repo, evidencia)

    sys.exit(0)


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

# Informe de la corrida. Va al cuerpo del pull request y al resumen de la
# ejecucion, para que la evidencia y la propuesta se vean incluso cuando el
# contrato con el humano decide no modificar nada.
REPORT_FILE_NAME = "readme_report.md"

# Propuesta de limpieza. El generador NUNCA borra: este archivo es una lista
# para que decida una persona.
DELETE_FILE_NAME = "delete_files.md"

MAX_REPAIR_ATTEMPTS = 2

# Reintentos de la llamada al modelo.
#
# Sin esto, un solo 429 o 5xx aborta el workflow completo. En un barrido por
# lotes eso significa que los repositorios afectados desaparecen de la corrida
# sin dejar ninguna señal.
MAX_LLM_ATTEMPTS = 4
LLM_BACKOFF_BASE = 2.0
LLM_BACKOFF_MAX = 60.0

# Límites para evitar prompts gigantes.
MAX_CONTEXT_CHARS = 30_000
MAX_EXISTING_README_CHARS = 12_000
MAX_AUDIT_CHARS = 12_000


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
# API.JSON
# ============================================================

def load_api():

    if not API_FILE.exists():

        error(
            "No se encontró api.json:\n"
            f"{API_FILE}"
        )

    try:

        with API_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:

            config = json.load(file)

    except Exception as exc:

        error(
            "No se pudo leer api.json:\n"
            f"{exc}"
        )

    api_key = config.get(
        "apikey"
    )

    model = config.get(
        "model"
    )

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
# README3
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
        " PASO 1/4 - ANALIZANDO REPOSITORIO"
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
# CONTEXTO
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
            "readme3.py terminó, pero no existe:\n"
            f"{compact}"
        )

    if not evidence.exists():

        error(
            "readme3.py terminó, pero no existe:\n"
            f"{evidence}"
        )

    return compact, evidence


# ============================================================
# README EXISTENTE
# ============================================================

def leer_readme_crudo(repo):
    """
    Lee el README tal cual esta en disco, con su marcador de huella.

    get_existing_readme lo quita a proposito antes de enviarlo al modelo.
    Para comparar huellas hace falta el texto sin tocar.
    """

    archivo = repo / "README.md"

    if not archivo.exists():
        return None

    try:
        return archivo.read_text(encoding="utf-8", errors="ignore")

    except Exception:
        return None


def get_existing_readme(repo):

    readme_file = repo / "README.md"

    if not readme_file.exists():
        return ""

    try:

        text = readme_file.read_text(
            encoding="utf-8",
            errors="ignore",
        )

    except Exception:

        return ""

    # El marcador de huella no se envia al modelo: si lo viera, lo copiaria
    # o lo mutilaria, y una huella corrupta obliga a regenerar siempre.
    text = quitar_huella(text)

    # No necesitamos enviar README gigantesco.
    if len(text) > MAX_EXISTING_README_CHARS:

        return (
            text[
                :MAX_EXISTING_README_CHARS
            ]
            + "\n\n"
            "[README EXISTENTE TRUNCADO]\n"
        )

    return text


# ============================================================
# TRUNCAR CONTEXTO DE SEGURIDAD
# ============================================================

def limit_context(context):

    if len(context) <= MAX_CONTEXT_CHARS:
        return context

    return (
        context[:MAX_CONTEXT_CHARS]
        + "\n\n"
        "[CONTEXTO TRUNCADO POR LÍMITE DE PROMPT]\n"
    )


# ============================================================
# PROMPT DE GENERACIÓN
# ============================================================

def create_generation_prompt(
    context,
    existing_readme,
):

    context = limit_context(
        context
    )

    return f"""
Eres un ingeniero de software senior especializado
en documentación técnica profesional.

Debes generar el README.md del repositorio analizado.

============================================================
REGLA PRINCIPAL
============================================================

La información del contexto proviene del código del
repositorio.

SOLO documenta información respaldada por evidencia.

NO INVENTES:

- funcionalidades
- tecnologías
- frameworks
- endpoints
- tablas
- variables de entorno
- comandos
- configuraciones
- servicios
- infraestructura
- roles
- arquitectura
- proveedores
- capacidades de negocio

No conviertas nombres de archivos en funcionalidades.

No conviertas nombres de carpetas en funcionalidades.

No conviertas una dependencia en una funcionalidad.

No conviertas una palabra clave en una funcionalidad.

Cuando no exista evidencia suficiente:

OMITE LA INFORMACIÓN.

============================================================
API
============================================================

Documenta solamente endpoints explícitamente detectados
en el contexto.

No inventes endpoints.

============================================================
BASE DE DATOS
============================================================

Documenta solamente tablas explícitamente detectadas.

No inventes relaciones, índices o modelos.

============================================================
VARIABLES DE ENTORNO
============================================================

Documenta solamente variables explícitamente detectadas.

Nunca inventes valores.

Nunca escribas secretos.

============================================================
COMANDOS
============================================================

Documenta solamente comandos respaldados por evidencia.

============================================================
ESTRUCTURA
============================================================

Usa las secciones que tengan evidencia suficiente:

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

No es obligatorio incluir todas.

Es mejor omitir una sección que inventarla.

============================================================
ESTILO
============================================================

El README debe ser:

- profesional
- técnico
- concreto
- específico del repositorio
- útil para desarrolladores

Evita lenguaje promocional.

No menciones IA.

No menciones este prompt.

No menciones README_CONTEXT.

No expliques el proceso de generación.

============================================================
README EXISTENTE
============================================================

{existing_readme}

============================================================
CONTEXTO TÉCNICO
============================================================

{context}

============================================================
SALIDA
============================================================

Devuelve únicamente el README.md.

No uses ```markdown alrededor de todo el documento.

No escribas explicaciones antes o después.
""".strip()


# ============================================================
# Z.AI
# ============================================================

def call_zai(
    api_key,
    model,
    prompt,
    title,
):

    print("")
    print("=" * 70)
    print(
        f" {title}"
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
                    "senior especializado en documentación "
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

    response = None

    last_error = ""

    for attempt in range(1, MAX_LLM_ATTEMPTS + 1):

        try:

            response = requests.post(
                ZAI_URL,
                headers=headers,
                json=payload,
                timeout=300,
            )

        except requests.RequestException as exc:

            response = None

            last_error = (
                "No fue posible conectarse con Z.ai:\n"
                f"{exc}"
            )

        else:

            if response.status_code == 200:
                break

            try:
                details = response.json()

            except Exception:
                details = response.text

            last_error = (
                f"HTTP: {response.status_code}\n"
                f"Respuesta:\n{details}"
            )

            # Un 4xx que no sea 429 es un problema del prompt o de la
            # credencial. Reintentarlo solo gasta tiempo.
            if (
                400 <= response.status_code < 500
                and response.status_code != 429
            ):
                error(
                    "Z.ai devolvió un error no recuperable.\n\n"
                    f"{last_error}"
                )

        if attempt == MAX_LLM_ATTEMPTS:
            break

        # Si el servidor dice cuánto esperar, se respeta.
        wait = None

        if response is not None:

            retry_after = response.headers.get("Retry-After")

            if retry_after:

                try:
                    wait = float(retry_after)

                except ValueError:
                    wait = None

        if wait is None:

            wait = min(
                LLM_BACKOFF_BASE ** attempt,
                LLM_BACKOFF_MAX,
            )

            # Jitter: en un barrido por lotes, varios repositorios chocan
            # con el mismo límite y reintentarían todos a la vez.
            wait += random.uniform(0, wait / 2)

        print("")
        print(
            f"Intento {attempt}/{MAX_LLM_ATTEMPTS} falló. "
            f"Reintentando en {wait:.1f}s."
        )
        print(last_error)

        time.sleep(wait)

    if response is None or response.status_code != 200:

        error(
            "Z.ai no respondió correctamente tras "
            f"{MAX_LLM_ATTEMPTS} intentos.\n\n"
            f"{last_error}"
        )

    try:

        data = response.json()

    except Exception:

        error(
            "Z.ai no devolvió JSON válido."
        )

    try:

        return (
            data["choices"][0]
            ["message"]["content"]
        )

    except (
        KeyError,
        IndexError,
        TypeError,
    ):

        error(
            "Respuesta inválida de Z.ai:\n"
            + json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            )
        )


# ============================================================
# LIMPIAR
# ============================================================

def clean_response(content):

    content = content.strip()

    wrappers = (
        "```markdown",
        "```md",
        "```",
    )

    for wrapper in wrappers:

        if content.startswith(
            wrapper
        ):

            content = (
                content[
                    len(wrapper):
                ]
                .strip()
            )

            if content.endswith(
                "```"
            ):

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
            "No se pudo guardar "
            "README_CANDIDATE.md:\n"
            f"{exc}"
        )

    return output


# ============================================================
# VALIDAR README
# ============================================================

def validate_readme(
    repo,
    candidate,
    evidence,
):

    if not VALIDATOR_FILE.exists():

        error(
            "No se encontró validate_readme.py:\n"
            f"{VALIDATOR_FILE}"
        )

    process = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR_FILE),
            str(candidate),
            str(evidence),
        ],
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
# PROMPT DE REPARACIÓN
# ============================================================

def create_repair_prompt(
    candidate,
    audit,
    context,
):

    if len(audit) > MAX_AUDIT_CHARS:

        audit = (
            audit[:MAX_AUDIT_CHARS]
            + "\n\n[AUDITORÍA TRUNCADA]"
        )

    context = limit_context(
        context
    )

    return f"""
Eres un auditor técnico senior.

Debes corregir el README mostrado abajo.

NO debes hacerlo más completo.

Debes hacerlo más VERIFICABLE.

============================================================
ERRORES DETECTADOS
============================================================

{audit}

============================================================
REGLAS
============================================================

Elimina cualquier afirmación que no pueda demostrarse
con el contexto proporcionado.

No inventes reemplazos.

No agregues funcionalidades.

No agregues tecnologías.

No agregues endpoints.

No agregues tablas.

No agregues variables.

No agregues comandos.

No agregues arquitectura.

No agregues infraestructura.

No menciones este proceso.

No menciones IA.

Si una afirmación no puede verificarse:

ELIMÍNALA.

============================================================
README ACTUAL
============================================================

{candidate}

============================================================
CONTEXTO
============================================================

{context}

============================================================
SALIDA
============================================================

Devuelve exclusivamente el README corregido.
""".strip()


# ============================================================
# README FINAL
# ============================================================

def save_final(
    repo,
    content,
    huella=None,
):
    """
    Guarda el README aplicando el contrato con el humano.

    NUNCA sobrescribe documentacion escrita a mano. Medido sobre la flota:
    de 14 README sustanciales, 12 los escribio una persona. Antes esto era
    un write_text() directo, asi que el siguiente push los destruia.
    """

    output = repo / "README.md"

    actual = get_existing_readme(repo) or None

    resultado = merge(
        actual,
        content,
        repo.name,
    )

    print("")
    print("=" * 70)
    print(
        f" CONTRATO CON EL HUMANO: {resultado.accion.upper()}"
    )
    print("=" * 70)
    print("")
    print(resultado.motivo)

    if resultado.conflictos:
        print("")
        print(
            "Bloques congelados por edicion humana: "
            + ", ".join(resultado.conflictos)
        )

    if not resultado.escribe:

        print("")
        print(
            "README.md NO fue modificado. La propuesta queda en "
            f"{CANDIDATE_FILE_NAME}."
        )

        return None, resultado

    final = resultado.contenido.strip() + "\n"

    # Se sella la huella de la evidencia con la que se genero. La proxima
    # corrida la compara y, si nada cambio, no llama al modelo.
    if huella:
        final = sellar_huella(final, huella)

    try:

        output.write_text(
            final,
            encoding="utf-8",
        )

    except Exception as exc:

        error(
            "No se pudo guardar README.md:\n"
            f"{exc}"
        )

    return output, resultado


# ============================================================
# MAIN
# ============================================================

def main():

    # La consola de Windows usa cp1252 y el mensaje de error de un servicio
    # externo puede traer cualquier caracter. Sin esto, un fallo al imprimir
    # el error mata el proceso con un traceback en vez de dar el mensaje.
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]

    banderas = {a for a in sys.argv[1:] if a.startswith("--")}

    forzar = "--force" in banderas
    proponer = "--proponer" in banderas

    # Los insumos inversos son un artefacto pesado y de vida larga: se
    # generan una vez y se corrigen a mano. No tiene sentido rehacerlos en
    # cada push, asi que van por peticion explicita.
    con_insumos = "--insumos" in banderas

    if len(argumentos) != 1:

        print("")
        print("Uso:")
        print("")
        print(
            'python makeReadme.py "D:\\GitHub\\COIPO_ENTREGA_PLANTA"'
        )
        print("")
        print("Opciones:")
        print(
            "  --force      Regenerar aunque la evidencia no haya cambiado."
        )
        print(
            "  --proponer   Generar la propuesta aunque el contrato con el"
        )
        print(
            "               humano vaya a dejar el README intacto."
        )
        print(
            "  --insumos    Reconstruir insumos/ desde el codigo:"
        )
        print(
            "               00-PROBLEMA.md, 01-SOLUCION.md y MANIFIESTO.yaml."
        )
        print("")

        sys.exit(1)

    repo = Path(
        argumentos[0]
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
    # PASO 1
    # --------------------------------------------------------

    run_readme3(
        repo
    )

    compact_file, evidence_file = (
        get_context_files(
            repo
        )
    )

    try:

        context = compact_file.read_text(
            encoding="utf-8"
        )

    except Exception as exc:

        error(
            "No se pudo leer README_CONTEXT_ULTRA.md:\n"
            f"{exc}"
        )

    # --------------------------------------------------------
    # PASO 2
    # --------------------------------------------------------

    existing_readme = (
        get_existing_readme(
            repo
        )
    )

    evidencia = cargar_evidencia(evidence_file)

    huella_nueva = calcular_huella(evidencia)

    # --------------------------------------------------------
    # CORTES ANTES DE GASTAR UNA LLAMADA AL MODELO
    # --------------------------------------------------------

    # Los insumos son independientes del README: un repositorio con README
    # escrito a mano igual se beneficia de tener 00-PROBLEMA y 01-SOLUCION.
    # Por eso este paso va ANTES de los cortes.
    if con_insumos:

        generar_insumos(
            repo=repo,
            evidencia=evidencia,
            contexto=context,
            api_key=api_key,
            model=model,
        )

    accion_prevista = decidir_accion(existing_readme, repo.name)

    if accion_prevista in {"respetado", "bloqueado"} and not proponer:

        motivo = (
            "El README esta escrito a mano y no declara ningun bloque "
            "gestionado."
            if accion_prevista == "respetado"
            else "El README declara <!-- ai-readme:lock -->."
        )

        detener(
            repo=repo,
            titulo=f"CONTRATO CON EL HUMANO: {accion_prevista.upper()}",
            mensaje=(
                f"{motivo}\n"
                "\n"
                "El contrato ya garantiza que no se va a modificar nada, asi "
                "que no se llama al modelo: seria trabajo tirado.\n"
                "\n"
                "Para ver que propondria el generador, ejecuta con "
                "--proponer, o lanza el workflow a mano con esa opcion."
            ),
            evidencia=evidencia,
            accion=accion_prevista,
        )

    # La huella se lee del README EN DISCO, no de `existing_readme`:
    # get_existing_readme quita el marcador a proposito para que no llegue
    # al modelo, asi que leerla de ahi devolvia siempre None y el corte no
    # se activaba nunca.
    huella_previa = leer_huella(leer_readme_crudo(repo))

    if huella_previa and huella_previa == huella_nueva and not forzar:

        detener(
            repo=repo,
            titulo="SIN CAMBIOS EN LA EVIDENCIA",
            mensaje=(
                f"La huella de la evidencia sigue siendo {huella_nueva[:12]}.\n"
                "\n"
                "Ni las dependencias, ni los endpoints, ni las tablas, ni las "
                "variables de entorno cambiaron desde la ultima generacion.\n"
                "\n"
                "No se llama al modelo. Usa --force para regenerar igualmente."
            ),
            evidencia=evidencia,
            accion="sin_cambios",
        )

    prompt = create_generation_prompt(
        context=context,
        existing_readme=existing_readme,
    )

    print("")
    print(
        f"Contexto utilizado: "
        f"{len(context):,} caracteres"
    )

    print(
        f"README previo: "
        f"{len(existing_readme):,} caracteres"
    )

    readme = call_zai(
        api_key,
        model,
        prompt,
        "PASO 2/4 - GENERANDO README CON Z.AI",
    )

    readme = clean_response(
        readme
    )

    candidate = save_candidate(
        repo,
        readme,
    )

    # --------------------------------------------------------
    # PASO 3
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
    # PASO 4
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
            f" REPARACIÓN {attempt}/"
            f"{MAX_REPAIR_ATTEMPTS}"
        )
        print("=" * 70)
        print("")

        repair_prompt = create_repair_prompt(
            candidate=readme,
            audit=audit,
            context=context,
        )

        readme = call_zai(
            api_key,
            model,
            repair_prompt,
            f"REPARANDO README "
            f"(INTENTO {attempt})",
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
    # RESULTADO
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
            "README.md existente NO fue sobrescrito."
        )

        print(
            f"README candidato:\n{candidate}"
        )

        error(
            "La validación no fue superada."
        )

    final, resultado_merge = save_final(
        repo,
        readme,
        huella_nueva,
    )

    # --------------------------------------------------------
    # INFORME DE LA CORRIDA
    #
    # Va siempre, incluso cuando no se modifica nada. Si el contrato
    # decide respetar un README escrito a mano no hay diff, y sin diff no
    # hay pull request: la propuesta y la evidencia se perderian.
    # --------------------------------------------------------

    try:

        informe = construir_informe(
            nombre_repo=repo.name,
            resultado_merge=resultado_merge,
            evidencia=cargar_evidencia(evidence_file),
            auditoria=audit,
            propuesta=readme,
        )

        escribir_informe(
            repo / REPORT_FILE_NAME,
            informe,
        )

        print("")
        print(
            f"Informe de la corrida: {repo / REPORT_FILE_NAME}"
        )

    except Exception as exc:

        # El informe es util, pero nunca puede tumbar la corrida.
        print("")
        print(f"AVISO: no se pudo generar el informe: {exc}")

    # --------------------------------------------------------
    # PROPUESTA DE LIMPIEZA
    #
    # Segunda llamada al modelo, con prompt propio. No descubre candidatos
    # —eso es determinista y ya esta hecho—: solo los juzga y explica.
    # --------------------------------------------------------

    candidatos = find_candidates(
        repo,
        evidencia.get("files") or [],
        evidencia.get("analysis") or {},
    )

    veredicto = None

    if candidatos:

        try:

            respuesta = call_zai(
                api_key,
                model,
                crear_prompt_limpieza(candidatos, repo.name),
                "PASO 5/5 - PROPONIENDO LIMPIEZA",
            )

            veredicto = parsear_limpieza(respuesta)

        except SystemExit:
            # call_zai llama a error() ante un fallo no recuperable. La
            # limpieza es accesoria: no puede tumbar una corrida que ya
            # produjo el README.
            print("")
            print(
                "AVISO: no se pudo obtener el juicio de limpieza. "
                "Los candidatos quedan todos en 'Revisar'."
            )
            veredicto = None

    generar_delete_files(repo, evidencia, veredicto)

    print("")
    print("=" * 70)
    print(
        " README FINAL"
    )
    print("=" * 70)
    print("")

    if final is None:

        print(
            "README.md se dejo intacto por el contrato con el humano."
        )

        print(
            f"Propuesta disponible en: {candidate}"
        )

    else:

        print(
            f"Archivo:\n{final}"
        )

    print(
        f"Tamaño de la propuesta: {len(readme):,} caracteres"
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