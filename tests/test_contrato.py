#!/usr/bin/env python3
"""
Contrato con el humano: el generador no destruye documentacion escrita por
una persona.

Contexto que motiva estos tests
-------------------------------

save_final() hacia write_text() sobre README.md sin leer nada. Medido sobre
la flota COIPO: de 24 repositorios, 14 tienen README escrito a mano —entre
ellos COIPO_LICITACION_IA con 17 KB y coipo_n8n con 11 KB— y 10 tienen un
marcador de posicion de menos de 32 bytes.

Es decir, el comportamiento anterior habria destruido 14 documentos que
ningun analizador puede reconstruir leyendo codigo, para reemplazarlos por
un README generado.

    python -m pytest tests/test_contrato.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from readme_merge import (      # noqa: E402
    envolver,
    es_placeholder,
    merge,
    normalizar,
    sha_de,
)

GENERADO = "# proyecto\n\n## Descripcion\n\nGenerado desde la evidencia.\n"


# ============================================================
# LO QUE NO SE TOCA
# ============================================================

def test_un_readme_humano_no_se_modifica():
    """El caso que motivo todo esto."""

    humano = (
        "# COIPO_PDF_EXCEL - Consolidador Previred\n\n"
        "Herramienta web para el area de personal: se le entrega el ZIP\n"
        "con los comprobantes PDF y devuelve una planilla Excel\n"
        "consolidada, con el layout de 108 columnas de Previred.\n\n"
        "## Uso\n\n1. Abrir el sitio.\n2. Arrastrar el .zip.\n"
    )

    resultado = merge(humano, GENERADO, "COIPO_PDF_EXCEL")

    assert resultado.accion == "respetado"
    assert resultado.contenido == humano
    assert not resultado.escribe


def test_el_sentinela_de_bloqueo_manda_sobre_todo():
    """Incluso un placeholder se respeta si declara el bloqueo."""

    bloqueado = "# repo\n<!-- ai-readme:lock -->\n"

    resultado = merge(bloqueado, GENERADO, "repo")

    assert resultado.accion == "bloqueado"
    assert not resultado.escribe


# ============================================================
# LO QUE SI SE ESCRIBE
# ============================================================

def test_un_placeholder_se_rellena():
    """Es exactamente para esto que existe el generador."""

    resultado = merge("# mi_repo\n", GENERADO, "mi_repo")

    assert resultado.accion == "creado"
    assert resultado.escribe
    assert "AI:BEGIN" in resultado.contenido
    assert "Generado desde la evidencia." in resultado.contenido


def test_un_readme_inexistente_se_crea():
    resultado = merge(None, GENERADO, "mi_repo")

    assert resultado.accion == "creado"
    assert resultado.escribe


def test_el_bloque_gestionado_se_actualiza():
    """Con marcadores intactos, el bot puede actualizar su propia parte."""

    previo = envolver("Texto viejo del bot")

    resultado = merge(previo, GENERADO, "mi_repo")

    assert resultado.accion == "fusionado"
    assert "Generado desde la evidencia." in resultado.contenido
    assert "Texto viejo del bot" not in resultado.contenido
    assert not resultado.conflictos


def test_texto_humano_alrededor_del_bloque_sobrevive():
    """Lo de fuera del bloque es del humano y no se toca."""

    previo = (
        "# Mi proyecto\n\n"
        "Parrafo escrito por una persona que debe sobrevivir.\n\n"
        + envolver("Texto viejo del bot")
        + "\n## Licencia\n\nEscrito a mano tambien.\n"
    )

    resultado = merge(previo, GENERADO, "mi_repo")

    assert resultado.accion == "fusionado"
    assert "Parrafo escrito por una persona que debe sobrevivir." in (
        resultado.contenido
    )
    assert "Escrito a mano tambien." in resultado.contenido


def test_un_bloque_editado_a_mano_queda_congelado():
    """
    Si alguien edito el interior del bloque, el sha deja de coincidir y el
    generador no lo pisa: lo reporta como conflicto.
    """

    previo = envolver("Texto original")
    editado = previo.replace(
        "Texto original",
        "Texto corregido a mano por una persona",
    )

    resultado = merge(editado, GENERADO, "mi_repo")

    assert resultado.accion == "respetado"
    assert "readme" in resultado.conflictos
    assert "Texto corregido a mano por una persona" in resultado.contenido
    assert not resultado.escribe


# ============================================================
# ESTABILIDAD DEL SHA
# ============================================================

def test_el_sha_no_depende_del_final_de_linea():
    """
    .gitattributes declara `* text=auto`, el desarrollo es en Windows y los
    runners son Ubuntu. Sin normalizar, todos los bloques saldrian como
    "editados por un humano" en la primera corrida en CI y el pipeline se
    congelaria entero en silencio.
    """

    assert sha_de("una\ndos\n") == sha_de("una\r\ndos\r\n")
    assert sha_de("una  \ndos\t\n") == sha_de("una\ndos\n")


def test_normalizar_es_idempotente():
    texto = "  una  \r\n dos \r\n\r\n"
    assert normalizar(normalizar(texto)) == normalizar(texto)


def test_una_corrida_sin_cambios_no_marca_conflicto():
    """El bloque que el propio bot escribio debe poder actualizarse."""

    escrito = envolver(GENERADO)

    resultado = merge(escrito, GENERADO, "mi_repo")

    assert resultado.accion == "fusionado"
    assert not resultado.conflictos


# ============================================================
# PLACEHOLDER
# ============================================================

def test_deteccion_de_placeholder():
    assert es_placeholder(None, "repo")
    assert es_placeholder("", "repo")
    assert es_placeholder("# repo", "repo")
    assert es_placeholder("# repo\n", "repo")
    assert es_placeholder("#  REPO  \n", "repo")

    largo = "# repo\n\n" + ("Documentacion real. " * 20)
    assert not es_placeholder(largo, "repo")
