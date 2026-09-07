#!/usr/bin/env python3
"""
Candidatos a borrar: que no proponga barbaridades.

Por que estos tests importan
----------------------------

Es la unica salida del sistema que le dice a alguien "borra esto". Un falso
positivo aqui cuesta mucho mas que en cualquier otro sitio: proponer borrar
codigo vivo es peor que dejar un archivo muerto un mes mas.

La primera version del detector proponia 586 archivos y 1 GB en
COIPO_LICITACION_IA. Eran los PDF de licitaciones que el proyecto procesa,
es decir su insumo. Tambien marcaba como huerfana la documentacion de
coipo_moodle y el script de operador repuntar_stubs.py de este mismo
repositorio.

Estos tests fijan esas tres lecciones.

    python -m pytest tests/test_limpieza.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from delete_files import construir, parsear_respuesta   # noqa: E402
from readme3_orphans import (                           # noqa: E402
    NUNCA_CANDIDATO,
    find_candidates,
    resumen,
)


def _archivo(ruta, size=100, ext=None, text=True, third=False):
    return {
        "path": ruta,
        "name": Path(ruta).name,
        "ext": ext if ext is not None else Path(ruta).suffix,
        "language": "Python" if ruta.endswith(".py") else "Other",
        "size": size,
        "text": text,
        "important": False,
        "third_party": third,
    }


# ============================================================
# LO QUE NUNCA SE PROPONE
# ============================================================

def test_los_archivos_intocables_estan_protegidos():
    for ruta in [
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        ".gitignore",
        ".github/workflows/ci.yml",
        "package.json",
        "backend/requirements.txt",
        "Dockerfile",
        "docker-compose.yml",
        "db/migrations/001_init.sql",
        "tests/test_algo.py",
        ".env.example",
        "CLAUDE.md",
    ]:
        assert NUNCA_CANDIDATO.search(ruta), f"{ruta} deberia estar protegido"


def test_los_artefactos_del_bot_no_estan_protegidos():
    """
    El patron de README era tan ancho que protegia readme_context/ y
    README_CANDIDATE.md, es decir la basura del propio generador.
    """

    assert not NUNCA_CANDIDATO.search("readme_context/README_EVIDENCE.json")
    assert not NUNCA_CANDIDATO.search("README_CANDIDATE.md")
    assert not NUNCA_CANDIDATO.search("readme_report.md")


# ============================================================
# LAS TRES LECCIONES
# ============================================================

def test_la_documentacion_no_es_huerfana(tmp_path):
    """
    Un .md no lo importa nadie. Eso es lo normal, no una señal de que sobre.
    Marcaba las guias de INSUMO/ de coipo_moodle.
    """

    (tmp_path / "INSUMO").mkdir()
    (tmp_path / "INSUMO" / "guia-despliegue.md").write_text(
        "# Guia\n\nTexto.\n", encoding="utf-8"
    )

    candidatos = find_candidates(
        tmp_path,
        [_archivo("INSUMO/guia-despliegue.md")],
        {},
    )

    assert candidatos == []


def test_un_script_de_operador_no_es_huerfano(tmp_path):
    """
    repuntar_stubs.py, vivo y en uso, aparecia como candidato a borrar en
    este mismo repositorio: nadie lo importa porque es un ejecutable.
    """

    (tmp_path / "herramienta.py").write_text(
        'import sys\n\n\ndef main():\n    pass\n\n\n'
        'if __name__ == "__main__":\n    main()\n',
        encoding="utf-8",
    )

    candidatos = find_candidates(
        tmp_path,
        [_archivo("herramienta.py")],
        {},
    )

    assert candidatos == []


def test_los_datos_no_se_proponen(tmp_path):
    """
    La categoria de datos se retiro: proponia 586 archivos y 1 GB en
    COIPO_LICITACION_IA, que eran el insumo del proyecto.
    """

    (tmp_path / "INSUMO").mkdir()
    (tmp_path / "INSUMO" / "licitacion.pdf").write_bytes(b"x" * 900_000)

    candidatos = find_candidates(
        tmp_path,
        [_archivo("INSUMO/licitacion.pdf", size=900_000, text=False)],
        {},
    )

    assert candidatos == []


# ============================================================
# LO QUE SI SE PROPONE
# ============================================================

def test_una_variante_se_propone_solo_si_existe_el_original(tmp_path):
    (tmp_path / "modulo.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "modulo_old.py").write_text("x = 0\n", encoding="utf-8")
    (tmp_path / "solitario_old.py").write_text("y = 0\n", encoding="utf-8")

    candidatos = find_candidates(
        tmp_path,
        [
            _archivo("modulo.py"),
            _archivo("modulo_old.py"),
            _archivo("solitario_old.py"),
        ],
        {},
    )

    rutas = {c["path"]: c for c in candidatos}

    assert "modulo_old.py" in rutas
    assert rutas["modulo_old.py"]["categoria"] == "variante o respaldo"

    # No hay "solitario.py", asi que no hay de que sea copia.
    assert rutas.get("solitario_old.py", {}).get("categoria") != (
        "variante o respaldo"
    )


def test_un_modulo_importado_no_es_huerfano(tmp_path):
    (tmp_path / "util.py").write_text("def f():\n    pass\n", encoding="utf-8")

    candidatos = find_candidates(
        tmp_path,
        [_archivo("util.py")],
        {"app.py": {"python": {"imports": [{"value": "util"}]}}},
    )

    assert candidatos == []


def test_el_codigo_de_terceros_no_se_propone(tmp_path):
    (tmp_path / "plugin.js").write_text("var x;\n", encoding="utf-8")

    candidatos = find_candidates(
        tmp_path,
        [_archivo("plugins/tema/plugin.js", third=True)],
        {},
    )

    assert candidatos == []


# ============================================================
# EL INFORME
# ============================================================

def test_lo_no_juzgado_cae_del_lado_seguro():
    """
    Si el modelo no se pronuncia sobre un candidato, va a Revisar. Nunca a
    Borrar.
    """

    candidatos = [
        {
            "path": "a.py",
            "size": 100,
            "categoria": "huerfano aparente",
            "confianza": "media",
            "evidencia": "nadie lo nombra",
        }
    ]

    md = construir(
        "demo",
        candidatos,
        {"borrar": [], "revisar": []},
        resumen(candidatos, 10),
        10,
    )

    assert "Revisar antes de decidir" in md
    assert "`a.py`" in md
    assert "Propuestos para borrar" not in md


def test_el_modelo_no_puede_proponer_rutas_que_no_existen():
    """
    La lista de candidatos es la unica fuente. Si el modelo inventa una
    ruta, se descarta.
    """

    candidatos = [
        {
            "path": "a.py",
            "size": 100,
            "categoria": "huerfano aparente",
            "confianza": "media",
            "evidencia": "nadie lo nombra",
        }
    ]

    md = construir(
        "demo",
        candidatos,
        {
            "borrar": [
                {"ruta": "a.py", "porque": "muerto"},
                {"ruta": "inventado.py", "porque": "no existe"},
            ],
            "revisar": [],
        },
        resumen(candidatos, 10),
        10,
    )

    assert "`a.py`" in md
    assert "inventado.py" not in md


def test_el_comando_sugerido_no_borra_del_disco():
    """
    `git rm --cached` saca del control de versiones sin destruir nada.
    """

    candidatos = [
        {
            "path": "basura.pyc",
            "size": 100,
            "categoria": "resto de build o entorno",
            "confianza": "alta",
            "evidencia": "compilado",
        }
    ]

    md = construir(
        "demo",
        candidatos,
        {"borrar": [{"ruta": "basura.pyc", "porque": "compilado"}],
         "revisar": []},
        resumen(candidatos, 10),
        10,
    )

    assert "git rm --cached" in md
    assert "rm -rf" not in md
    assert "**Nada se borro.**" in md


def test_una_respuesta_invalida_no_tumba_la_corrida():
    assert parsear_respuesta("esto no es json") == {
        "borrar": [], "revisar": []
    }
    assert parsear_respuesta("") == {"borrar": [], "revisar": []}
    assert parsear_respuesta(
        '```json\n{"borrar": [], "revisar": []}\n```'
    ) == {"borrar": [], "revisar": []}


def test_la_configuracion_por_convencion_esta_protegida():
    """
    Su herramienta la carga por convencion; nadie la importa. Eso no la
    vuelve huerfana. Medido: el detector proponia borrar vite.config.js de
    COIPO_PDF_EXCEL.
    """

    for ruta in [
        "frontend/vite.config.js",
        "tailwind.config.cjs",
        "eslint.config.js",
        "next.config.mjs",
        "tsconfig.json",
        "backend/conftest.py",
        "manage.py",
        "backend/wsgi.py",
        "setup.cfg",
        "pytest.ini",
        "alembic.ini",
    ]:
        assert NUNCA_CANDIDATO.search(ruta), f"{ruta} deberia estar protegido"


def test_el_codigo_normal_sigue_siendo_candidato():
    """Proteger configuracion no puede significar proteger todo."""

    assert not NUNCA_CANDIDATO.search("src/app.py")
    assert not NUNCA_CANDIDATO.search("utils/viejo.py")
    assert not NUNCA_CANDIDATO.search("web/src/componentes/Tabla.jsx")
