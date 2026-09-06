#!/usr/bin/env python3
"""
Insumos inversos y deteccion de dato personal.

Por que estos tests importan
----------------------------

Estos documentos afirman cosas sobre el negocio —quien sufre un problema,
que hace el sistema, que datos maneja— a partir de codigo. Es el punto del
sistema donde es mas facil que una inferencia se disfrace de hecho.

Y el detector de dato personal tiene una regla que no se puede relajar:
NUNCA transcribe un valor. Reporta el patron y el conteo. Un informe que
copia un RUT dentro de un documento versionado crea el problema que
pretende evitar.

    python -m pytest tests/test_insumos.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import readme3_scanner as sc                    # noqa: E402
from insumos_inversos import (                  # noqa: E402
    escribir,
    hay_insumos_humanos,
    parsear,
    sellar_manifiesto,
    validar_citas,
)
from readme3_pii import (                       # noqa: E402
    detectar,
    esta_ignorado_con_ancla,
)


RESPUESTA = """Aqui va texto introductorio que debe descartarse.

===== 00-PROBLEMA.md =====
## Quien sufre el problema

[INFERIDO] Existen los roles `admin` y `encargada` [backend/guards.py:12].
[PENDIENTE] Cuantas personas son.

===== 01-SOLUCION.md =====
## Que hace

Permite registrar usuarios y asignarles aplicaciones [backend/api.py:40].

===== MANIFIESTO.yaml =====
- ruta: db/catalogo.json
  sha256: "<lo calcula el script de sellado>"
  origen: "[PENDIENTE] quien lo entrego"
  contiene_pii: "[VERIFICAR] 55 correos"
  puede_versionarse: true
  uso: catalogo

===== INFORME =====
Pendientes: 1
"""


# ============================================================
# PARSEO
# ============================================================

def test_se_separan_los_tres_documentos():
    partes = parsear(RESPUESTA)

    assert set(partes) == {
        "00-PROBLEMA.md",
        "01-SOLUCION.md",
        "MANIFIESTO.yaml",
        "INFORME",
    }

    assert "texto introductorio" not in partes["00-PROBLEMA.md"]
    assert "[INFERIDO]" in partes["00-PROBLEMA.md"]


def test_una_respuesta_sin_separadores_no_produce_nada():
    """Mejor no escribir que escribir un documento a medias."""

    assert parsear("solo texto suelto") == {}
    assert parsear("") == {}


# ============================================================
# SELLADO DEL MANIFIESTO
# ============================================================

def test_el_sha256_lo_calcula_el_script_y_no_el_modelo():
    hallazgos = [
        {"ruta": "db/catalogo.json", "sha256": "abc123def456", "conteos": {}}
    ]

    sellado = sellar_manifiesto(
        parsear(RESPUESTA)["MANIFIESTO.yaml"],
        hallazgos,
    )

    assert "abc123def456" in sellado
    assert "lo calcula el script de sellado" not in sellado


def test_sin_hash_real_se_marca_pendiente_y_no_se_inventa():
    """
    Un hash inventado es peor que no tener hash: parece verificable.
    """

    sellado = sellar_manifiesto(
        parsear(RESPUESTA)["MANIFIESTO.yaml"],
        [],
    )

    assert "[PENDIENTE] sin calcular" in sellado


# ============================================================
# NO PISAR TRABAJO HUMANO
# ============================================================

def test_un_insumos_levantado_por_personas_no_se_toca(tmp_path):
    directorio = tmp_path / "insumos"
    directorio.mkdir()

    original = (
        "# Problema\n\n"
        "Lo levantamos con el area de personal el 4 de agosto.\n"
    )

    (directorio / "00-PROBLEMA.md").write_text(original, encoding="utf-8")

    assert hay_insumos_humanos(tmp_path)

    resultado = escribir(tmp_path, parsear(RESPUESTA), [])

    assert resultado["modo"] == "contraste"
    assert resultado["escritos"] == ["DERIVADO-DEL-CODIGO.md"]

    # El documento humano sigue intacto.
    assert (directorio / "00-PROBLEMA.md").read_text(
        encoding="utf-8"
    ) == original


def test_sin_insumos_previos_se_escriben_los_tres(tmp_path):
    resultado = escribir(tmp_path, parsear(RESPUESTA), [])

    assert resultado["modo"] == "creado"
    assert set(resultado["escritos"]) == {
        "00-PROBLEMA.md",
        "01-SOLUCION.md",
        "MANIFIESTO.yaml",
    }


def test_lo_derivado_se_declara_como_derivado(tmp_path):
    """
    Quien abra el documento tiene que saber en la primera linea que no lo
    escribio una persona.
    """

    escribir(tmp_path, parsear(RESPUESTA), [])

    texto = (tmp_path / "insumos" / "00-PROBLEMA.md").read_text(
        encoding="utf-8"
    )

    assert "DERIVADO DEL CODIGO" in texto.upper()
    assert "[INFERIDO]" in texto

    # Y una segunda corrida no lo confunde con trabajo humano.
    assert not hay_insumos_humanos(tmp_path)


# ============================================================
# DATO PERSONAL
# ============================================================

def _archivo(ruta, size=200):
    return {
        "path": ruta,
        "name": Path(ruta).name,
        "ext": Path(ruta).suffix,
        "language": "Python",
        "size": size,
        "text": True,
        "important": False,
        "third_party": False,
    }


def test_nunca_se_transcribe_un_valor(tmp_path):
    """
    La regla que no se puede relajar: se reporta el patron y el conteo.
    Copiar un RUT dentro de un documento versionado crea el problema que
    el informe pretende evitar.
    """

    (tmp_path / "datos.py").write_text(
        'RUTS = ["12.345.678-9", "9.876.543-2"]\n'
        'CORREOS = ["persona@conaf.cl"]\n',
        encoding="utf-8",
    )

    hallazgos = detectar(tmp_path, [_archivo("datos.py")])

    assert len(hallazgos) == 1

    texto = str(hallazgos[0])

    assert "12.345.678-9" not in texto
    assert "9.876.543-2" not in texto
    assert "persona@conaf.cl" not in texto

    assert hallazgos[0]["conteos"]["rut"] == 2
    assert hallazgos[0]["conteos"]["correo"] == 1


def test_un_nombre_de_columna_no_es_un_dato(tmp_path):
    """
    Encontrar la palabra "telefono" en una etiqueta no es encontrar un
    telefono. Sin esta distincion el detector se detecta a si mismo: este
    repositorio contiene "rut" y "correo" como literales de su propia lista
    de patrones.
    """

    (tmp_path / "formulario.py").write_text(
        'CAMPOS = ["rut", "correo", "telefono", "direccion"]\n',
        encoding="utf-8",
    )

    assert detectar(tmp_path, [_archivo("formulario.py")]) == []


def test_una_ruta_de_pruebas_cambia_la_marca(tmp_path):
    """
    Que un dato viva en fixtures/ hace mucho mas probable que sea
    sintetico. No lo prueba, y por eso el resultado es [VERIFICAR] y no una
    conclusion.
    """

    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "usuarios.py").write_text(
        'RUT = "12.345.678-9"\n', encoding="utf-8"
    )

    hallazgos = detectar(tmp_path, [_archivo("fixtures/usuarios.py")])

    assert hallazgos[0]["marca"] == "[VERIFICAR]"
    assert hallazgos[0]["en_ruta_de_prueba"]


def test_en_el_propio_repositorio_solo_saltan_los_fixtures():
    """
    Fixture negativo, con un matiz que el propio test crea: este archivo
    contiene RUT de ejemplo, asi que el detector DEBE encontrarlos. Lo que
    se exige es que no encuentre nada fuera de rutas de prueba y que todo
    lo que encuentre quede marcado [VERIFICAR], nunca como conclusion.
    """

    hallazgos = detectar(RAIZ, sc.scan(RAIZ))

    fuera_de_pruebas = [
        h["ruta"] for h in hallazgos if not h["en_ruta_de_prueba"]
    ]

    assert fuera_de_pruebas == [], fuera_de_pruebas

    for hallazgo in hallazgos:
        assert hallazgo["marca"] == "[VERIFICAR]"


def test_el_ancla_del_gitignore_se_comprueba_bien():
    """
    El prompt original insiste en la barra inicial por una razon concreta:
    sin ella el patron casa a cualquier profundidad, y el rsync del
    despliegue no borra lo que excluye.
    """

    patrones = ["/insumos/datos/", "otros/", "*.log"]

    assert esta_ignorado_con_ancla("insumos/datos/planilla.csv", patrones)
    assert esta_ignorado_con_ancla("insumos/datos", patrones)

    # Sin ancla no cuenta.
    assert not esta_ignorado_con_ancla("otros/cosa.csv", patrones)
    assert not esta_ignorado_con_ancla("insumos/otros/x.csv", patrones)


# ============================================================
# CITAS INVENTADAS
# ============================================================

EVIDENCIA_MINIMA = {
    "files": [
        {"path": "INSUMO/index.html"},
        {"path": "README.md"},
        {"path": "frontend/package.json"},
    ]
}


def test_una_cita_a_un_archivo_inexistente_se_detecta():
    """
    El fallo mas grave posible aqui. Medido sobre coipo_sitra —seis
    archivos HTML estaticos— el modelo cito auth.py, importers.py y
    models.py: el 100% de sus citas eran inventadas.

    Una cita falsa cumple la regla "sin cita no hay afirmacion" en la forma
    y la viola en el fondo, y ademas parece verificable.
    """

    partes = {
        "00-PROBLEMA.md": "Existen roles [auth.py:15] y modelos [models.py:3].",
    }

    resultado = validar_citas(partes, EVIDENCIA_MINIMA)

    assert set(resultado["inventadas"]) == {"auth.py", "models.py"}
    assert resultado["proporcion_inventada"] == 1.0


def test_una_cita_valida_se_acepta():
    partes = {
        "01-SOLUCION.md": "Publica una pagina [INSUMO/index.html:1].",
    }

    resultado = validar_citas(partes, EVIDENCIA_MINIMA)

    assert resultado["inventadas"] == []
    assert "INSUMO/index.html" in resultado["validas"]


def test_se_acepta_el_nombre_a_secas():
    """
    El modelo a veces cita `package.json` en vez de la ruta completa. Eso
    no es una invencion.
    """

    partes = {"01-SOLUCION.md": "Declara dependencias [package.json:22]."}

    resultado = validar_citas(partes, EVIDENCIA_MINIMA)

    assert resultado["inventadas"] == []


def test_las_marcas_no_se_confunden_con_citas():
    partes = {
        "00-PROBLEMA.md": (
            "Cuantas personas son es [PENDIENTE]. "
            "La norma es [VERIFICAR]. Los roles [INFERIDO]."
        )
    }

    resultado = validar_citas(partes, EVIDENCIA_MINIMA)

    assert resultado["total"] == 0
    assert resultado["inventadas"] == []


def test_el_informe_no_se_valida():
    """
    El INFORME habla de lo que falta, no afirma nada sobre el sistema.
    """

    partes = {
        "INFORME": "Falta revisar si existe algo como config.py.",
    }

    assert validar_citas(partes, EVIDENCIA_MINIMA)["total"] == 0
