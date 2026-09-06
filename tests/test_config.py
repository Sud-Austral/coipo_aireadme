#!/usr/bin/env python3
"""
`.aireadme.yml`: el canal por el que un humano le habla al generador.

Por que estos tests importan
----------------------------

Este archivo lo escribe una persona a mano, en 57 repositorios. La regla que
no se puede romper es que un error de tipografia en uno de ellos NO puede
tumbar el pipeline: cae a los valores por defecto y avisa.

    python -m pytest tests/test_config.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import readme3_scanner as sc                # noqa: E402
from readme_config import (                 # noqa: E402
    ARCHIVO,
    Config,
    bloque_declarado,
    cargar,
)


def _escribir(tmp_path: Path, contenido: str) -> Path:
    (tmp_path / ARCHIVO).write_text(contenido, encoding="utf-8")
    return tmp_path


# ============================================================
# NUNCA TUMBAR EL PIPELINE
# ============================================================

def test_sin_archivo_se_usan_los_valores_por_defecto(tmp_path):
    config = cargar(tmp_path)

    assert config.enabled
    assert config.lang == "es"
    assert not config.presente
    assert config.avisos == []


def test_un_yaml_invalido_no_aborta(tmp_path):
    """Un error de tipografia en un repositorio no puede parar la flota."""

    _escribir(tmp_path, "enabled: [sin cerrar\n  : : :")

    config = cargar(tmp_path)

    assert config.enabled is True
    assert config.presente
    assert config.avisos


def test_un_yaml_que_no_es_un_mapa_se_ignora(tmp_path):
    _escribir(tmp_path, "- uno\n- dos\n")

    config = cargar(tmp_path)

    assert config.enabled is True
    assert config.avisos


def test_un_idioma_desconocido_cae_a_espanol_con_aviso(tmp_path):
    _escribir(tmp_path, "lang: pt\n")

    config = cargar(tmp_path)

    assert config.lang == "es"
    assert any("pt" in a for a in config.avisos)


def test_las_claves_desconocidas_se_reportan(tmp_path):
    """
    Callarlas haria que un typo pase inadvertido: alguien escribe
    `ignorepaths` y cree que funciona.
    """

    _escribir(tmp_path, "ignorepaths: [x]\n")

    config = cargar(tmp_path)

    assert any("ignorepaths" in a for a in config.avisos)


# ============================================================
# LOS CAMPOS
# ============================================================

def test_enabled_false_se_respeta(tmp_path):
    _escribir(tmp_path, "enabled: false\n")

    assert cargar(tmp_path).enabled is False


def test_ignore_paths_acepta_lista_y_cadena(tmp_path):
    _escribir(tmp_path, "ignore_paths:\n  - INSUMO\n  - docs/\n")
    assert cargar(tmp_path).ignore_paths == ["INSUMO", "docs/"]

    _escribir(tmp_path, "ignore_paths: INSUMO\n")
    assert cargar(tmp_path).ignore_paths == ["INSUMO"]


def test_las_banderas_opcionales_tienen_defecto_conservador(tmp_path):
    """
    artifacts e insumos escriben o proponen cosas nuevas: se activan
    a proposito, no por omision.
    """

    config = cargar(tmp_path)

    assert config.artifacts is False
    assert config.insumos is False
    assert config.cleanup is True


# ============================================================
# TESTIMONIO HUMANO
# ============================================================

def test_lo_declarado_se_marca_como_testimonio_y_no_como_inferencia(tmp_path):
    """
    Es lo unico del contexto que no salio de leer codigo, y el modelo tiene
    que saberlo: vale mas que cualquier senal detectada.
    """

    _escribir(
        tmp_path,
        "declared: |\n  Sistema para el area de personal.\n",
    )

    bloque = "\n".join(bloque_declarado(cargar(tmp_path), "mi_repo"))

    assert "HUMAN_DECLARED" in bloque
    assert "testimonio humano" in bloque
    assert "Sistema para el area de personal." in bloque
    assert "no es una inferencia" in bloque.lower()


def test_sin_declaracion_no_se_inventa_bloque(tmp_path):
    assert bloque_declarado(cargar(tmp_path), "mi_repo") == []
    assert bloque_declarado(Config(), "mi_repo") == []


# ============================================================
# EL PROPIO ARCHIVO NO SE ANALIZA
# ============================================================

def test_el_archivo_de_configuracion_no_entra_al_analisis():
    """
    Es .yml, y su extension esta en TEXT_EXTENSIONS. Sin excluirlo, la
    prosa que escribe el humano vuelve como falsos positivos de tecnologia
    citados en [.aireadme.yml:N]. Es el mismo bug de auto-deteccion que ya
    aparecio con readme_context y con las listas de palabras clave del
    propio detector.
    """

    assert ARCHIVO in sc.IGNORED_FILES


def test_las_rutas_declaradas_se_excluyen_del_escaneo(monkeypatch):
    monkeypatch.setenv("AIREADME_IGNORE_PATHS", "INSUMO,docs")

    assert sc.is_excluded("INSUMO/archivo.html")
    assert sc.is_excluded("docs/guia.md")
    assert not sc.is_excluded("src/app.py")

    monkeypatch.delenv("AIREADME_IGNORE_PATHS")

    assert not sc.is_excluded("INSUMO/archivo.html")
