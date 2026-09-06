#!/usr/bin/env python3
"""
Contrato con el humano: el generador nunca pisa documentacion escrita por
una persona.

Por que existe
--------------

save_final() hacia write_text() sobre README.md sin leer, sin diff y sin
respaldo. Medido sobre la flota: de 14 README sustanciales, 12 estan
escritos a mano. Entre ellos COIPO_LICITACION_IA (18 KB), coipo_n8n (12 KB)
y COIPO_PDF_EXCEL, que documenta a mano el layout de 108 columnas de
Previred y las cuatro hojas del Excel que produce.

Ninguna de esas paginas la puede reconstruir un analizador leyendo codigo.
Perderlas seria un daño neto, y era lo que iba a pasar en el proximo push.

El contrato
-----------

    (a) El README tiene marcadores AI:BEGIN / AI:END
        Se reemplaza SOLO el interior de los bloques cuyo sha coincide con
        el contenido actual. Si alguien edito un bloque a mano, ese bloque
        queda congelado y se reporta como conflicto.

    (b) El README es un placeholder (o no existe)
        Se escribe entero, envuelto en marcadores, para que a partir de
        entonces se pueda fusionar.

    (c) El README esta escrito y NO tiene marcadores
        NO SE TOCA. Ni se sobrescribe ni se le anexa nada. La propuesta
        viaja en el cuerpo del pull request para que decida una persona.

        Quien quiera que el bot gestione una parte de su README solo tiene
        que poner los marcadores a mano alrededor de esa parte.

El sha se calcula sobre contenido NORMALIZADO
---------------------------------------------

.gitattributes declara `* text=auto`, el desarrollo es en Windows y los
runners son Ubuntu. Sin normalizar finales de linea, todos los bloques
saldrian marcados como "editados por un humano" en la primera corrida en CI
y el pipeline se congelaria entero en silencio.

PRINCIPIO: DETECCION != CONCLUSION.
Detectar que un bloque cambio no autoriza a decidir cual version vale.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

MARCA_INICIO = re.compile(
    r"<!--\s*AI:BEGIN\s+id=(?P<id>[\w.-]+)"
    r"(?:\s+sha=(?P<sha>[0-9a-f]+))?\s*-->",
    re.IGNORECASE,
)

MARCA_FIN = re.compile(
    r"<!--\s*AI:END(?:\s+id=(?P<id>[\w.-]+))?\s*-->",
    re.IGNORECASE,
)

SENTINELA_LOCK = re.compile(
    r"<!--\s*ai-readme:lock\s*-->",
    re.IGNORECASE,
)

BLOQUE_PRINCIPAL = "readme"

# Un README por debajo de esto, o que solo repite el nombre del repositorio,
# no es documentacion: es el marcador de posicion que crea GitHub.
UMBRAL_PLACEHOLDER = 200


@dataclass
class Resultado:
    accion: str
    contenido: str
    conflictos: list[str] = field(default_factory=list)
    motivo: str = ""

    @property
    def escribe(self) -> bool:
        return self.accion in {"creado", "fusionado"}


# ============================================================
# UTILIDADES
# ============================================================

def normalizar(texto: str) -> str:
    """
    Normaliza para que el sha sea estable entre Windows y Linux.
    """

    lineas = [
        linea.rstrip()
        for linea in texto.replace("\r\n", "\n").split("\n")
    ]

    return "\n".join(lineas).strip()


def sha_de(texto: str) -> str:
    return hashlib.sha256(
        normalizar(texto).encode("utf-8")
    ).hexdigest()[:12]


def esta_bloqueado(readme: str) -> bool:
    """El repositorio pidio explicitamente que no se le toque."""

    return bool(SENTINELA_LOCK.search(readme or ""))


def es_placeholder(readme: str | None, nombre_repo: str) -> bool:
    """
    True si el README no es documentacion real.
    """

    if not readme:
        return True

    texto = normalizar(readme)

    if not texto:
        return True

    if len(texto) < UMBRAL_PLACEHOLDER:
        return True

    # "# nombre_repo" y nada mas.
    sin_titulo = re.sub(
        r"^#\s*" + re.escape(nombre_repo) + r"\s*$",
        "",
        texto,
        flags=re.IGNORECASE | re.MULTILINE,
    ).strip()

    return not sin_titulo


def tiene_marcadores(readme: str | None) -> bool:
    return bool(readme and MARCA_INICIO.search(readme))


# ============================================================
# BLOQUES
# ============================================================

def envolver(contenido: str, identificador: str = BLOQUE_PRINCIPAL) -> str:
    """Envuelve contenido generado en un bloque gestionado."""

    cuerpo = normalizar(contenido)

    return (
        f"<!-- AI:BEGIN id={identificador} sha={sha_de(cuerpo)} -->\n"
        f"{cuerpo}\n"
        f"<!-- AI:END id={identificador} -->\n"
    )


def parse_bloques(readme: str) -> list[dict]:
    """
    Devuelve los bloques gestionados encontrados, con su sha declarado y su
    contenido actual.
    """

    bloques = []

    for inicio in MARCA_INICIO.finditer(readme):

        fin = MARCA_FIN.search(readme, inicio.end())

        if not fin:
            continue

        bloques.append(
            {
                "id": inicio.group("id"),
                "sha_declarado": inicio.group("sha"),
                "contenido": readme[inicio.end():fin.start()],
                "inicio": inicio.start(),
                "fin": fin.end(),
            }
        )

    return bloques


# ============================================================
# FUSION
# ============================================================

def merge(
    readme_actual: str | None,
    readme_generado: str,
    nombre_repo: str,
) -> Resultado:
    """
    Aplica el contrato. Nunca destruye texto humano.
    """

    generado = normalizar(readme_generado)

    # ----------------------------------------------------------
    # Bloqueo explicito
    # ----------------------------------------------------------

    if readme_actual and esta_bloqueado(readme_actual):
        return Resultado(
            accion="bloqueado",
            contenido=readme_actual,
            motivo=(
                "El README declara <!-- ai-readme:lock -->. "
                "El generador no lo toca."
            ),
        )

    # ----------------------------------------------------------
    # El orden importa: los marcadores se comprueban ANTES que el tamaño.
    #
    # Un README que solo contiene un bloque gestionado corto seria
    # clasificado como marcador de posicion si se mirara el tamaño primero,
    # y se reescribiria entero en vez de fusionarse.
    # ----------------------------------------------------------

    if tiene_marcadores(readme_actual):
        return _fusionar_bloques(readme_actual, generado)

    # ----------------------------------------------------------
    # (b) placeholder o inexistente
    # ----------------------------------------------------------

    if es_placeholder(readme_actual, nombre_repo):
        return Resultado(
            accion="creado",
            contenido=envolver(generado),
            motivo=(
                "No habia documentacion: solo un marcador de posicion. "
                "Se escribe el README generado dentro de un bloque "
                "gestionado."
            ),
        )

    # ----------------------------------------------------------
    # (c) documentacion humana sin marcadores
    # ----------------------------------------------------------

    return Resultado(
        accion="respetado",
        contenido=readme_actual,
        motivo=(
                "Este README esta escrito a mano y no declara ningun bloque "
                "gestionado por el generador, asi que NO se modifica.\n"
                "\n"
                "La propuesta del generador va en el cuerpo del pull "
                "request. Si quieres que el bot mantenga una parte, "
                "envuelvela en el README con:\n"
                "\n"
                "    <!-- AI:BEGIN id=descripcion -->\n"
                "    ...contenido gestionado...\n"
                "    <!-- AI:END id=descripcion -->"
            ),
        )


def _fusionar_bloques(readme: str, generado: str) -> Resultado:
    """
    Reemplaza el interior de los bloques gestionados cuyo sha coincide.

    Un bloque cuyo contenido cambio desde la ultima generacion fue
    editado por una persona: queda congelado y se reporta.
    """

    # ----------------------------------------------------------
    # (a) hay marcadores: se fusiona bloque a bloque
    # ----------------------------------------------------------

    resultado = readme
    conflictos: list[str] = []
    reemplazos = 0

    # De atras hacia adelante para no invalidar los offsets.
    for bloque in reversed(parse_bloques(readme)):

        sha_actual = sha_de(bloque["contenido"])

        if (
            bloque["sha_declarado"]
            and bloque["sha_declarado"] != sha_actual
        ):
            conflictos.append(bloque["id"])
            continue

        nuevo = (
            f"<!-- AI:BEGIN id={bloque['id']} sha={sha_de(generado)} -->\n"
            f"{generado}\n"
            f"<!-- AI:END id={bloque['id']} -->"
        )

        resultado = (
            resultado[:bloque["inicio"]]
            + nuevo
            + resultado[bloque["fin"]:]
        )

        reemplazos += 1

    if not reemplazos:
        return Resultado(
            accion="respetado",
            contenido=readme,
            conflictos=conflictos,
            motivo=(
                "Todos los bloques gestionados fueron editados a mano "
                "desde la ultima generacion. Se respetan tal cual."
            ),
        )

    return Resultado(
        accion="fusionado",
        contenido=resultado if resultado.endswith("\n") else resultado + "\n",
        conflictos=conflictos,
        motivo=(
            f"Se actualizaron {reemplazos} bloque(s) gestionado(s)."
            + (
                f" {len(conflictos)} quedaron congelados por edicion humana."
                if conflictos
                else ""
            )
        ),
    )
