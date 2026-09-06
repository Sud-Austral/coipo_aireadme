#!/usr/bin/env python3
"""
Validacion de comandos: de codigo muerto a comprobacion util.

Por que existe
--------------

get_evidence_commands buscaba `analysis[*]["package_json"]`, una clave que
analyze_files() nunca escribe: solo escribe python, javascript y sql. El
conjunto quedaba siempre vacio y el bloque que compara comandos nunca
llegaba a ejecutarse, asi que los comandos inventados no se detectaban.

Al resucitarlo aparecio el problema contrario: avisaba de comandos que
existen. Un README escribe `npm run build   # genera dist/` y el
package.json declara el script como `build`. Sobre COIPO_PDF_EXCEL marcaba
como no verificados los siete scripts declarados en su propio manifiesto.

    python -m pytest tests/test_validador.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from validate_readme import (          # noqa: E402
    extract_commands,
    get_evidence_commands,
    normalizar_comando,
)


EVIDENCIA = {
    "npm_scripts": [
        {"name": "build", "command": "vite build", "manifest": "package.json"},
        {"name": "dev", "command": "vite", "manifest": "package.json"},
    ],
    "manifests": [
        {
            "path": "package.json",
            "kind": "npm",
            "third_party": False,
            "dependencies": [],
            "scripts": [],
        },
        {
            "path": "backend/requirements.txt",
            "kind": "python",
            "third_party": False,
            "dependencies": [],
            "scripts": [],
        },
    ],
}


# ============================================================
# NORMALIZACION
# ============================================================

def test_se_quita_el_comentario_de_shell():
    assert normalizar_comando(
        "npm run build            # genera dist/"
    ) == "npm run build"


def test_se_colapsan_los_espacios():
    assert normalizar_comando(
        "  pip   install  -r   requirements.txt  "
    ) == "pip install -r requirements.txt"


def test_una_almohadilla_pegada_no_es_comentario():
    """`docker run img#tag` no lleva comentario."""

    assert normalizar_comando("docker run img#tag") == "docker run img#tag"


# ============================================================
# EL CONJUNTO DE EVIDENCIA YA NO ESTA VACIO
# ============================================================

def test_los_scripts_llegan_a_la_evidencia():
    """Antes esto devolvia siempre un conjunto vacio."""

    comandos = get_evidence_commands(EVIDENCIA)

    assert comandos, "el conjunto de comandos sigue vacio"
    assert "vite build" in comandos


def test_se_acepta_el_nombre_del_script_y_no_solo_su_comando():
    comandos = get_evidence_commands(EVIDENCIA)

    assert "npm run build" in comandos
    assert "npm run dev" in comandos


def test_se_aceptan_los_comandos_del_gestor_si_hay_manifiesto():
    comandos = get_evidence_commands(EVIDENCIA)

    assert "npm install" in comandos
    assert "npm ci" in comandos
    assert "pip install -r backend/requirements.txt" in comandos


def test_sin_manifiesto_npm_no_se_aceptan_sus_comandos():
    evidencia = {
        "npm_scripts": [],
        "manifests": [
            {
                "path": "backend/requirements.txt",
                "kind": "python",
                "third_party": False,
                "dependencies": [],
                "scripts": [],
            }
        ],
    }

    comandos = get_evidence_commands(evidencia)

    assert "npm install" not in comandos
    assert "pip install -r backend/requirements.txt" in comandos


def test_un_manifiesto_de_terceros_no_aporta_comandos():
    evidencia = {
        "npm_scripts": [],
        "manifests": [
            {
                "path": "plugins/tema/package.json",
                "kind": "npm",
                "third_party": True,
                "dependencies": [],
                "scripts": [],
            }
        ],
    }

    assert "npm install" not in get_evidence_commands(evidencia)


# ============================================================
# EXTRACCION DESDE EL README
# ============================================================

def test_el_readme_y_la_evidencia_casan_pese_al_comentario():
    """El caso real que producia siete avisos falsos."""

    readme = (
        "## Ejecucion\n\n"
        "```bash\n"
        "npm run build            # genera dist/\n"
        "npm run dev              # http://localhost:5173\n"
        "```\n"
    )

    mencionados = extract_commands(readme)
    respaldados = get_evidence_commands(EVIDENCIA)

    sin_respaldo = mencionados - respaldados

    assert not sin_respaldo, f"avisos falsos: {sin_respaldo}"


def test_un_comando_inventado_si_se_detecta():
    """Que no avise de mas no puede significar que no avise de nada."""

    readme = "```bash\nnpm run deploy-produccion\n```\n"

    sin_respaldo = extract_commands(readme) - get_evidence_commands(EVIDENCIA)

    assert "npm run deploy-produccion" in sin_respaldo
