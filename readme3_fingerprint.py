#!/usr/bin/env python3
"""
Huella de la evidencia: no regenerar lo que no cambio.

Por que existe
--------------

El generador llamaba al modelo en cada push a main, hubiera cambiado algo o
no. Con 57 repositorios y un barrido semanal eso son 57 llamadas y hasta 57
pull requests por semana aunque nadie haya tocado una dependencia.

La huella se calcula sobre las senales ESTABLES de la evidencia. Si coincide
con la que quedo sellada en el README, no hay nada nuevo que documentar y la
corrida termina sin llamar al modelo.

Que entra y que no
------------------

Entra lo que describe el software: tecnologias con procedencia concluyente,
dependencias declaradas, scripts, endpoints, tablas, variables de entorno y
archivos importantes.

NO entra nada que cambie sin que cambie el software:

    metadata.generated_at   cambia en cada ejecucion
    los numeros de linea    se mueven al editar cualquier archivo
    la seccion analysis     es el detalle completo del AST
    las tecnologias `mentioned`
                            provienen de texto libre, incluido el propio
                            README; incluirlas haria que el README generado
                            moviera su propia huella y nunca convergiera

PRINCIPIO: DETECCION != CONCLUSION.
La huella detecta que la evidencia no cambio. No concluye que el README sea
correcto.
"""

from __future__ import annotations

import hashlib
import json
import re

MARCADOR = re.compile(
    r"<!--\s*ai-readme-fingerprint:\s*sha256:(?P<sha>[0-9a-f]{8,64})\s*-->",
    re.IGNORECASE,
)

PROCEDENCIAS_CONCLUYENTES = {"declared", "imported", "vendored"}


def _tecnologias(evidencia: dict) -> list[str]:

    tecnologias = evidencia.get("technologies") or {}

    return sorted(
        f"{nombre}:{datos.get('provenance')}"
        for nombre, datos in tecnologias.items()
        if datos.get("provenance") in PROCEDENCIAS_CONCLUYENTES
    )


def _dependencias(evidencia: dict) -> list[str]:

    salida = []

    for manifiesto in evidencia.get("manifests") or []:

        if manifiesto.get("third_party"):
            continue

        for dependencia in manifiesto.get("dependencies", []):
            salida.append(
                f"{manifiesto['path']}::"
                f"{dependencia['name']}@{dependencia.get('version') or ''}"
            )

    return sorted(salida)


def _scripts(evidencia: dict) -> list[str]:

    return sorted(
        f"{s.get('name')}={s.get('command')}"
        for s in evidencia.get("npm_scripts") or []
    )


def _api(evidencia: dict) -> list[str]:

    return sorted(
        f"{item.get('method')} {item.get('path')}"
        for item in evidencia.get("api") or []
    )


def _tablas(evidencia: dict) -> list[str]:

    return sorted(
        str(item.get("value"))
        for item in evidencia.get("database_tables") or []
    )


def _variables(evidencia: dict) -> list[str]:

    return sorted(
        str(item.get("value"))
        for item in evidencia.get("environment_variables") or []
    )


def canonico(evidencia: dict) -> dict:
    """
    Reduce la evidencia a lo que describe el software, ordenado.
    """

    return {
        "technologies": _tecnologias(evidencia),
        "dependencies": _dependencias(evidencia),
        "scripts": _scripts(evidencia),
        "api": _api(evidencia),
        "tables": _tablas(evidencia),
        "env": _variables(evidencia),
        "important_files": sorted(
            evidencia.get("important_files") or []
        ),
    }


def compute(evidencia: dict) -> str:
    """
    sha256 de la evidencia canonica.
    """

    texto = json.dumps(
        canonico(evidencia),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def leer(readme: str | None) -> str | None:
    """
    Extrae la huella sellada en un README, si la lleva.
    """

    if not readme:
        return None

    coincidencia = MARCADOR.search(readme)

    return coincidencia.group("sha") if coincidencia else None


def quitar(readme: str | None) -> str:
    """
    Elimina el marcador.

    Se usa antes de enviar el README existente al modelo: si lo viera, lo
    copiaria o lo mutilaria, y una huella corrupta obliga a regenerar
    siempre.
    """

    if not readme:
        return ""

    return MARCADOR.sub("", readme).rstrip() + "\n"


def sellar(readme: str, huella: str) -> str:
    """
    Anade o reemplaza el marcador al final del README.
    """

    limpio = quitar(readme).rstrip()

    return (
        f"{limpio}\n\n"
        f"<!-- ai-readme-fingerprint: sha256:{huella} -->\n"
    )
