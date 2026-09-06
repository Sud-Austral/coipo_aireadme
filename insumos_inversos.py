#!/usr/bin/env python3
"""
Reconstruye insumos/ desde el codigo: la ingenieria inversa del
levantamiento que no se hizo.

Produce 00-PROBLEMA.md, 01-SOLUCION.md y MANIFIESTO.yaml a partir de la
evidencia, con el prompt de prompts/11-derivar-insumos-desde-codigo.md.

La asimetria que manda sobre todo el diseno
-------------------------------------------

    01-SOLUCION.md   se deriva bien. El codigo ES la solucion.
    MANIFIESTO.yaml  mitad determinista (ruta, sha256, .gitignore), mitad
                     humana (`origen` es siempre [PENDIENTE]).
    00-PROBLEMA.md   casi no se deriva. Quien sufre el problema, cuantas
                     personas son, que pasa si no se hace nada y quien
                     decide que esta terminado son hechos del mundo, no del
                     codigo.

Por eso el modo inverso necesita una marca que el prompt original no tiene:
[INFERIDO]. Inferir es detectar; confirmar es concluir. El resultado no es
un levantamiento, es un borrador auditable que el area usuaria corrige.

Rieles
------

  - Nunca sobrescribe un insumos/ levantado con personas. Si ya existe, lo
    derivado va a insumos/DERIVADO-DEL-CODIGO.md.
  - Los sha256 del manifiesto los calcula este modulo, no el modelo.
  - Nunca se transcribe un valor que parezca personal: solo el patron y el
    conteo.
  - No edita .gitignore. Reporta.

PRINCIPIO: DETECCION != CONCLUSION.
"""

from __future__ import annotations

import re
from pathlib import Path

from readme3_pii import esta_ignorado_con_ancla, rutas_ignoradas

BASE_DIR = Path(__file__).resolve().parent

PROMPT_FILE = BASE_DIR / "prompts" / "11-derivar-insumos-desde-codigo.md"

DIRECTORIO = "insumos"

DOCUMENTOS = ("00-PROBLEMA.md", "01-SOLUCION.md", "MANIFIESTO.yaml")

SEPARADOR = re.compile(
    r"^=====\s*(?P<nombre>[\w.\-]+)\s*=====\s*$",
    re.MULTILINE,
)

MAX_HALLAZGOS_EN_PROMPT = 40


# ============================================================
# PROMPT
# ============================================================

def _plantilla() -> str:
    """
    Extrae el prompt del bloque ```text del archivo de prompts.

    Vive en un .md y no en una cadena de Python a proposito: es un
    documento que una persona tiene que poder leer y discutir sin abrir
    codigo, igual que el prompt original del que es contrapartida.
    """

    texto = PROMPT_FILE.read_text(encoding="utf-8")

    bloques = re.findall(
        r"```text\n(.*?)```",
        texto,
        re.DOTALL,
    )

    if not bloques:
        raise RuntimeError(
            f"No se encontro el bloque de prompt en {PROMPT_FILE}"
        )

    return bloques[0].strip()


def _bloque_pii(hallazgos: list[dict], ignorados: list[str]) -> str:

    if not hallazgos:
        return (
            "No se detectaron valores con formato de dato personal en los "
            "archivos legibles. Aun asi, `origen` sigue siendo [PENDIENTE] "
            "en todas las entradas del manifiesto."
        )

    lineas = [
        "Candidatos para el campo `contiene_pii`. NO son conclusiones: el "
        "formato de un RUT de empresa y el de una persona natural es "
        "identico, y un dato en tests/ o fixtures/ suele ser sintetico sin "
        "que eso lo garantice.",
        "",
        "Reporta el patron y el conteo. NUNCA el valor.",
        "",
    ]

    for hallazgo in hallazgos[:MAX_HALLAZGOS_EN_PROMPT]:

        anclado = esta_ignorado_con_ancla(hallazgo["ruta"], ignorados)

        lineas.append(
            f"- {hallazgo['marca']} `{hallazgo['ruta']}`\n"
            f"    sha256: {(hallazgo.get('sha256') or '')[:16]}\n"
            f"    {hallazgo['detalle']}\n"
            f"    en .gitignore anclado con barra inicial: "
            f"{'si' if anclado else 'NO'}"
        )

    if len(hallazgos) > MAX_HALLAZGOS_EN_PROMPT:
        lineas.append(
            f"\n(y {len(hallazgos) - MAX_HALLAZGOS_EN_PROMPT} archivos mas "
            "con patrones; el manifiesto los agrupa)"
        )

    return "\n".join(lineas)


def crear_prompt(
    contexto: str,
    hallazgos_pii: list[dict],
    ignorados: list[str],
    nombre_repo: str,
    insumos_existentes: bool,
) -> str:

    aviso = ""

    if insumos_existentes:
        aviso = (
            "\n\nATENCION: este repositorio YA tiene un directorio insumos/ "
            "levantado con personas. NO lo sustituyas ni lo contradigas. Lo "
            "que escribas ira a un archivo aparte y su valor esta en senalar "
            "en que difiere de lo ya declarado."
        )

    return (
        f"{_plantilla()}"
        f"{aviso}"
        "\n\n"
        "============================================================\n"
        f"REPOSITORIO: {nombre_repo}\n"
        "============================================================\n"
        "\n"
        "============================================================\n"
        "CANDIDATOS DE DATO PERSONAL\n"
        "============================================================\n"
        "\n"
        f"{_bloque_pii(hallazgos_pii, ignorados)}\n"
        "\n"
        "============================================================\n"
        "EVIDENCIA DEL CODIGO\n"
        "============================================================\n"
        "\n"
        f"{contexto}\n"
    )


# ============================================================
# RESPUESTA
# ============================================================

def parsear(respuesta: str) -> dict[str, str]:
    """
    Separa la respuesta en los documentos que declara.
    """

    if not respuesta:
        return {}

    partes: dict[str, str] = {}

    marcas = list(SEPARADOR.finditer(respuesta))

    for indice, marca in enumerate(marcas):

        inicio = marca.end()

        fin = (
            marcas[indice + 1].start()
            if indice + 1 < len(marcas)
            else len(respuesta)
        )

        partes[marca.group("nombre")] = respuesta[inicio:fin].strip()

    return partes


# ============================================================
# SELLADO
# ============================================================

def sellar_manifiesto(
    manifiesto: str,
    hallazgos: list[dict],
) -> str:
    """
    Sustituye los sha256 de marcador por los reales.

    Los calcula este modulo, no el modelo: un hash inventado seria peor que
    no tener hash, porque parece verificable.
    """

    por_ruta = {h["ruta"]: h for h in hallazgos}

    lineas = manifiesto.splitlines()

    ruta_actual = None

    salida = []

    for linea in lineas:

        coincidencia = re.match(r"\s*-?\s*ruta:\s*(.+?)\s*$", linea)

        if coincidencia:
            ruta_actual = coincidencia.group(1).strip().strip('"\'')

        if re.match(r"\s*sha256:", linea) and ruta_actual:

            hallazgo = por_ruta.get(ruta_actual)

            sha = (hallazgo or {}).get("sha256")

            indentacion = linea[: len(linea) - len(linea.lstrip())]

            linea = (
                f'{indentacion}sha256: "{sha}"'
                if sha
                else f'{indentacion}sha256: "[PENDIENTE] sin calcular"'
            )

        salida.append(linea)

    return "\n".join(salida) + "\n"


# ============================================================
# ESCRITURA
# ============================================================

def hay_insumos_humanos(repo: Path) -> bool:
    """
    True si ya existe un insumos/ que no genero este modulo.
    """

    directorio = repo / DIRECTORIO

    if not directorio.is_dir():
        return False

    for nombre in DOCUMENTOS:

        archivo = directorio / nombre

        if not archivo.exists():
            continue

        try:
            texto = archivo.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # Lo que escribe este modulo se declara a si mismo.
        if "DERIVADO DEL CODIGO" not in texto.upper():
            return True

    return False


CABECERA = """<!-- DERIVADO DEL CODIGO -->
> **Este documento no es un levantamiento.**
>
> Lo reconstruyo un analizador leyendo el codigo de `{repo}`, y por eso cada
> afirmacion lleva una de tres marcas:
>
> - `[INFERIDO]` se dedujo de la evidencia citada. Es una hipotesis con
>   respaldo, no un hecho del negocio. Confirmala o corrigela.
> - `[PENDIENTE]` ni el codigo ni nadie lo respondio.
> - `[VERIFICAR]` afirmacion juridica o dato posiblemente personal sin
>   confirmar.
>
> Corregir este borrador es mas rapido que partir de una hoja en blanco. No
> lo des por bueno.

"""


def escribir(
    repo: Path,
    partes: dict[str, str],
    hallazgos: list[dict],
) -> dict:
    """
    Escribe los documentos. Nunca pisa un insumos/ levantado con personas.
    """

    existentes = hay_insumos_humanos(repo)

    directorio = repo / DIRECTORIO

    directorio.mkdir(exist_ok=True)

    escritos = []

    if existentes:

        # Todo junto en un solo archivo aparte, para no confundirlo con lo
        # que declararon personas.
        cuerpo = [CABECERA.format(repo=repo.name)]

        cuerpo.append(
            "Este repositorio ya tiene insumos levantados con personas. "
            "Lo que sigue es lo que el analizador deduce del codigo, para "
            "contrastar.\n"
        )

        for nombre in DOCUMENTOS:
            if nombre in partes:
                cuerpo.append(f"\n---\n\n## {nombre}\n\n{partes[nombre]}\n")

        destino = directorio / "DERIVADO-DEL-CODIGO.md"

        destino.write_text("\n".join(cuerpo), encoding="utf-8")

        escritos.append(destino.name)

        return {
            "modo": "contraste",
            "escritos": escritos,
            "motivo": (
                "Ya existe un insumos/ levantado con personas. Lo derivado "
                "va aparte, en DERIVADO-DEL-CODIGO.md, para contrastar sin "
                "sustituir."
            ),
        }

    for nombre in DOCUMENTOS:

        if nombre not in partes:
            continue

        contenido = partes[nombre]

        if nombre.endswith(".yaml"):

            # El YAML tambien tiene que declararse derivado, o la corrida
            # siguiente lo confunde con un manifiesto levantado por
            # personas y se niega a actualizarlo.
            contenido = (
                "# DERIVADO DEL CODIGO\n"
                "#\n"
                "# Lo reconstruyo un analizador leyendo el codigo de "
                f"{repo.name}.\n"
                "# `origen` es [PENDIENTE] en todas las entradas: quien "
                "entrego cada\n"
                "# archivo y cuando no esta escrito en ningun repositorio.\n"
                "# `contiene_pii` son candidatos, no conclusiones.\n"
                "\n"
                + sellar_manifiesto(contenido, hallazgos)
            )

        else:
            contenido = CABECERA.format(repo=repo.name) + contenido + "\n"

        (directorio / nombre).write_text(contenido, encoding="utf-8")

        escritos.append(nombre)

    return {
        "modo": "creado",
        "escritos": escritos,
        "motivo": (
            "No habia insumos levantados. Se escribe el borrador derivado "
            "del codigo, con sus marcas."
        ),
    }


def preparar(repo: Path, files: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Reune lo que el prompt necesita del repositorio.
    """

    from readme3_pii import detectar

    return detectar(repo, files), rutas_ignoradas(repo)
