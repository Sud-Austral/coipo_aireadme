#!/usr/bin/env python3
"""
Deteccion de datos posiblemente personales, para el manifiesto inverso.

Por que existe
--------------

El prompt de levantamiento de insumos abre diciendo que abrir una planilla
con RUT o correos sin haberlo declarado mete datos personales en el contexto
de un modelo de lenguaje. Este generador hace exactamente eso: recorre el
repositorio y envia hasta 30.000 caracteres a un endpoint externo.

Hoy no hay hallazgos reales en la flota COIPO —los RUT de persona son
sinteticos y los de convenios_preliminares.generated.json son de empresas,
que son dato publico, confirmado por el dueno de los datos el 2026-09-06—
pero nada garantiza que el proximo repositorio no traiga datos reales.

Lo que este modulo NO puede hacer
---------------------------------

Distinguir un RUT de empresa de uno de persona natural. Tienen el mismo
formato. Tampoco puede saber si un dato es sintetico. Por eso la salida
nunca es `contiene_pii: true`, sino `[VERIFICAR]` o `[PENDIENTE]`: son
candidatos para que decida una persona.

La prueba de que ese diseno es el correcto: sobre COIPO_ENTREGA_PLANTA el
detector produjo 298 candidatos y una persona los resolvio en una frase.
Ninguna expresion regular podia hacer esa distincion. Lo que aporta el
manifiesto es que la resolucion queda escrita y sellada con el sha256, para
no volver a litigarla en cada corrida.

PRINCIPIO: DETECCION != CONCLUSION.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from readme3_scanner import read_text

# RUT chileno. El de empresa y el de persona natural son indistinguibles.
RUT = re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]\b")

CORREO = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

TELEFONO_CL = re.compile(r"\+56\s?9\s?\d{4}\s?\d{4}\b")

# Nombres de columna o de clave que suelen acompanar datos personales.
CAMPOS_SENSIBLES = re.compile(
    r"""\b(
          rut | run | dni | pasaporte
        | correo | email | e_mail
        | telefono | celular | fono
        | direccion | domicilio
        | nombre_completo | apellido_paterno | apellido_materno
        | fecha_nacimiento
        | genero | etnia | pueblo_originario
        | afiliacion | sindicato | prevision | isapre | afp
        | diagnostico | licencia_medica
    )\b""",
    re.IGNORECASE | re.VERBOSE,
)

# Categorias especiales de la ley chilena. Cambian el regimen entero, asi
# que no se reportan como un hallazgo mas: se marcan [VERIFICAR] para
# Fiscalia.
CATEGORIA_ESPECIAL = re.compile(
    r"\b(salud|diagnostico|sindical|sindicato|afiliacion politica|"
    r"pueblo originario|etnia|discapacidad)\b",
    re.IGNORECASE,
)

# Rutas donde un dato con formato de RUT es casi siempre sintetico. No lo
# convierte en sintetico: cambia la probabilidad, y eso se dice.
RUTAS_DE_PRUEBA = re.compile(
    r"(^|/)(tests?|__tests__|spec|fixtures?|mocks?|seeds?|"
    r"factories|stubs?|demo|ejemplos?)(/|$)|"
    r"(seed|fixture|mock|sample|ejemplo)[^/]*$",
    re.IGNORECASE,
)

# Planillas: el generador no las lee (no estan en TEXT_EXTENSIONS), pero su
# sola presencia hay que declararla.
EXTENSIONES_DE_PLANILLA = {".csv", ".xlsx", ".xls", ".ods", ".dbf"}

MAX_ARCHIVOS = 400


def _sha256(ruta: Path) -> str | None:

    try:
        return hashlib.sha256(ruta.read_bytes()).hexdigest()

    except Exception:
        return None


def analizar_archivo(repo: Path, archivo: dict) -> dict | None:
    """
    Devuelve un hallazgo, o None si el archivo no dispara nada.

    NUNCA devuelve el valor encontrado: solo el patron y el conteo.
    """

    ruta = archivo["path"]

    completa = repo / ruta

    de_prueba = bool(RUTAS_DE_PRUEBA.search(ruta))

    # Una planilla se declara por lo que es, aunque no se pueda leer.
    if archivo["ext"] in EXTENSIONES_DE_PLANILLA:
        return {
            "ruta": ruta,
            "sha256": _sha256(completa),
            "motivo": "planilla",
            "detalle": (
                f"Archivo {archivo['ext']} de "
                f"{archivo['size'] / 1024:.0f} KB. El analizador no lee su "
                "contenido, pero una planilla en un repositorio hay que "
                "declararla."
            ),
            "conteos": {},
            "en_ruta_de_prueba": de_prueba,
            "marca": "[PENDIENTE]",
        }

    if not archivo["text"] or archivo["size"] > 2_000_000:
        return None

    texto = read_text(completa)

    if not texto:
        return None

    conteos = {
        "rut": len(set(RUT.findall(texto))),
        "correo": len(set(CORREO.findall(texto))),
        "telefono": len(set(TELEFONO_CL.findall(texto))),
        "campos_sensibles": len(
            {m.lower() for m in CAMPOS_SENSIBLES.findall(texto)}
        ),
    }

    # Un nombre de columna NO es un dato personal.
    #
    # Encontrar la palabra "telefono" en la etiqueta de un formulario no es
    # encontrar un telefono: es encontrar un esquema que podria contenerlo.
    # Son cosas distintas y la segunda es mucho mas debil.
    #
    # Sin esta distincion el detector se detecta a si mismo —este archivo
    # contiene "rut", "correo" y "diagnostico" como literales de su propia
    # lista— y produce 192 hallazgos en un repositorio donde no hay ninguno.
    valores = (
        conteos["rut"] + conteos["correo"] + conteos["telefono"]
    )

    if not valores:
        return None

    especiales = sorted(
        {m.lower() for m in CATEGORIA_ESPECIAL.findall(texto)}
    )

    partes = [
        f"{conteos[nombre]} {nombre}"
        for nombre in ("rut", "correo", "telefono")
        if conteos[nombre]
    ]

    detalle = "Valores con formato de dato personal: " + ", ".join(partes) + "."

    if conteos["campos_sensibles"]:
        detalle += (
            f" El archivo nombra ademas {conteos['campos_sensibles']} "
            "campo(s) que suelen acompanar datos personales."
        )

    if de_prueba:
        detalle += (
            " El archivo vive en una ruta de pruebas o fixtures, lo que "
            "hace mucho mas probable que los datos sean sinteticos. No lo "
            "prueba."
        )

    if especiales:
        detalle += (
            " Aparecen ademas terminos de categoria especial ("
            + ", ".join(especiales)
            + "), que cambian el regimen legal aplicable."
        )

    return {
        "ruta": ruta,
        "sha256": _sha256(completa),
        "motivo": "patrones de dato personal",
        "detalle": detalle,
        "conteos": conteos,
        "en_ruta_de_prueba": de_prueba,
        "categoria_especial": especiales,
        # [VERIFICAR] cuando hay una duda que solo una persona resuelve;
        # [PENDIENTE] cuando simplemente falta declararlo.
        "marca": "[VERIFICAR]" if (de_prueba or especiales) else "[PENDIENTE]",
    }


def detectar(repo: Path, files: list[dict]) -> list[dict]:
    """
    Recorre el repositorio y devuelve candidatos, nunca conclusiones.
    """

    hallazgos = []

    for archivo in files:

        if archivo.get("third_party"):
            continue

        hallazgo = analizar_archivo(repo, archivo)

        if hallazgo:
            hallazgos.append(hallazgo)

        if len(hallazgos) >= MAX_ARCHIVOS:
            break

    # Primero lo que mas patrones concentra.
    hallazgos.sort(
        key=lambda h: -sum(h["conteos"].values())
    )

    return hallazgos


def rutas_ignoradas(repo: Path) -> list[str]:
    """
    Lee el .gitignore para poder comprobar la implicacion del prompt:

        contiene_pii: true  =>  puede_versionarse: false
                            =>  la ruta va al .gitignore ANCLADA con /
    """

    archivo = repo / ".gitignore"

    if not archivo.exists():
        return []

    texto = read_text(archivo) or ""

    return [
        linea.strip()
        for linea in texto.splitlines()
        if linea.strip() and not linea.strip().startswith("#")
    ]


def esta_ignorado_con_ancla(ruta: str, patrones: list[str]) -> bool:
    """
    True si la ruta esta excluida con un patron ANCLADO con barra inicial.

    El prompt original insiste en el ancla por una razon concreta: sin la
    barra el patron casa a cualquier profundidad, y como el rsync del
    despliegue no borra lo que excluye, el directorio se queda congelado en
    el servidor.
    """

    for patron in patrones:

        if not patron.startswith("/"):
            continue

        limpio = patron.lstrip("/").rstrip("/")

        if ruta == limpio or ruta.startswith(limpio + "/"):
            return True

    return False
