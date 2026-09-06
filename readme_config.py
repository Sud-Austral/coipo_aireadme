#!/usr/bin/env python3
"""
`.aireadme.yml`: el canal por el que un humano le habla al generador.

Por que existe
--------------

El generador solo escucha al codigo. Pero hay cosas que ningun analizador
puede deducir —para que existe el proyecto, que carpetas no vienen al caso,
en que idioma se documenta— y que la persona que lo mantiene sabe de sobra.

Es el complemento positivo de DETECCION != CONCLUSION: si el analizador no
puede concluir, que lo declare alguien que si sabe.

Cuatro campos en la v1
----------------------

    enabled       false apaga el generador en este repositorio.
    lang          es | en
    ignore_paths  rutas que no aportan nada al analisis.
    declared      testimonio humano: proposito, area usuaria, lo que sea.
                  Se le entrega al modelo marcado como declaracion, nunca
                  como inferencia.

Se dejan fuera `sections.owned` y `sections.skip`: multiplican los casos de
la fusion y no hay demanda demostrada.

Un YAML invalido NO aborta
--------------------------

Cae a los valores por defecto y avisa. Un error de tipografia en un
repositorio no puede tumbar el pipeline de la flota.

Nota honesta sobre `enabled: false`
-----------------------------------

Apaga la generacion, pero no es una salida de confianza: el workflow
reutilizable se invoca desde el stub antes de que nadie lea este archivo.
Para salirse de verdad hay que quitar el stub.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ARCHIVO = ".aireadme.yml"

IDIOMAS = {"es", "en"}


@dataclass
class Config:
    enabled: bool = True
    lang: str = "es"
    ignore_paths: list[str] = field(default_factory=list)
    declared: str = ""
    artifacts: bool = False
    cleanup: bool = True
    insumos: bool = False

    avisos: list[str] = field(default_factory=list)
    presente: bool = False


def _como_lista(valor) -> list[str]:

    if isinstance(valor, str):
        return [valor.strip()] if valor.strip() else []

    if isinstance(valor, list):
        return [str(v).strip() for v in valor if str(v).strip()]

    return []


def cargar(repo: Path) -> Config:
    """
    Lee `.aireadme.yml`. Nunca falla.
    """

    archivo = repo / ARCHIVO

    if not archivo.exists():
        return Config()

    try:
        import yaml

    except ImportError:
        return Config(
            presente=True,
            avisos=[
                f"{ARCHIVO} existe pero falta PyYAML. Se usan los valores "
                "por defecto."
            ],
        )

    try:
        datos = yaml.safe_load(
            archivo.read_text(encoding="utf-8", errors="ignore")
        )

    except Exception as exc:
        return Config(
            presente=True,
            avisos=[
                f"{ARCHIVO} no es YAML valido y se ignora: {exc}. "
                "Un error de tipografia en un repositorio no puede tumbar "
                "el pipeline."
            ],
        )

    if not isinstance(datos, dict):
        return Config(
            presente=True,
            avisos=[
                f"{ARCHIVO} no contiene un mapa de claves. Se ignora."
            ],
        )

    avisos: list[str] = []

    idioma = str(datos.get("lang", "es")).lower().strip()

    if idioma not in IDIOMAS:
        avisos.append(
            f"lang='{idioma}' no reconocido. Se usa 'es'. "
            f"Valores validos: {', '.join(sorted(IDIOMAS))}."
        )
        idioma = "es"

    declarado = datos.get("declared") or ""

    if not isinstance(declarado, str):
        declarado = str(declarado)

    desconocidas = set(datos) - {
        "enabled", "lang", "ignore_paths", "declared",
        "artifacts", "cleanup", "insumos",
    }

    if desconocidas:
        avisos.append(
            "Claves no reconocidas, se ignoran: "
            + ", ".join(sorted(desconocidas))
        )

    return Config(
        enabled=bool(datos.get("enabled", True)),
        lang=idioma,
        ignore_paths=_como_lista(datos.get("ignore_paths")),
        declared=declarado.strip(),
        artifacts=bool(datos.get("artifacts", False)),
        cleanup=bool(datos.get("cleanup", True)),
        insumos=bool(datos.get("insumos", False)),
        avisos=avisos,
        presente=True,
    )


def bloque_declarado(config: Config, repo_nombre: str) -> list[str]:
    """
    Lo que el humano declaro, para el contexto del modelo.

    Va marcado de forma explicita como testimonio y no como inferencia: es
    lo unico del contexto que no salio de leer codigo.
    """

    if not config.declared:
        return []

    return [
        "",
        "## HUMAN_DECLARED",
        "",
        "Lo que sigue lo escribio una PERSONA en "
        f"{ARCHIVO} de {repo_nombre}.",
        "",
        "No es una inferencia del analizador: es testimonio humano, y por",
        "tanto vale mas que cualquier senal detectada. Uselo para redactar",
        "la descripcion y el objetivo. Si contradice a una senal, manda",
        "esto.",
        "",
        f"[{ARCHIVO}]",
        config.declared,
    ]


PLANTILLA = """# Configuracion del generador de README.
#
# Todos los campos son opcionales. Este archivo es el unico canal por el
# que le puedes decir algo al generador que no pueda deducir leyendo el
# codigo.

# Poner en false apaga la generacion en este repositorio.
#
# Aviso honesto: apaga la generacion, pero no es una salida de confianza.
# El workflow se invoca desde .github/workflows/readme.yml antes de que
# nadie lea este archivo. Para salirse del todo, quita ese stub.
enabled: true

# Idioma del README generado: es | en
lang: es

# Rutas que no aportan nada al analisis. Utiles cuando el repositorio
# versiona codigo de terceros que el detector no reconoce como tal.
ignore_paths: []

# Testimonio humano. Esto es lo mas util que puedes escribir aqui.
#
# El analizador sabe que hace el codigo. No sabe PARA QUE existe, quien lo
# usa ni por que se construyo. Eso solo lo sabes tu, y lo que escribas aca
# se le entrega al modelo marcado como declaracion humana, con mas peso que
# cualquier senal detectada.
#
# declared: |
#   Sistema para el area de X. Lo usan N personas de Y.
#   Reemplazo a una planilla que se mantenia a mano.

# Propuestas de artefactos deterministas (.env.example, docs/API.md) en el
# cuerpo del pull request. Desactivado por defecto.
artifacts: false

# Propuesta de limpieza en delete_files.md. Nunca borra nada.
cleanup: true

# Reconstruir insumos/ desde el codigo. Es un artefacto pesado que se
# corrige a mano, asi que no se regenera en cada push.
insumos: false
"""
