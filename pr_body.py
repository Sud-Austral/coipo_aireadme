#!/usr/bin/env python3
"""
Informe de la corrida: que se hizo, con que evidencia, y que NO se pudo
verificar.

Por que existe
--------------

El cuerpo del pull request era un texto fijo que describia el proceso
—"se analizo el repositorio, se extrajo evidencia, se genero un README"—
identico en todos los repositorios. No decia nada de ESTE repositorio: ni
que evidencia se uso, ni que quedo sin verificar, ni por que.

Ademas, desde que existe el contrato con el humano hay corridas que
deliberadamente NO modifican nada. Sin PR no hay diff, y la propuesta del
generador se volveria invisible. Por eso el mismo informe se escribe en el
resumen de la ejecucion, que se ve en la pestana Actions sin abrir ningun
pull request ni generar ruido en el repositorio.

PRINCIPIO: DETECCION != CONCLUSION.
El informe separa lo que esta respaldado por evidencia de lo que no, y no
presenta lo segundo como si fuera lo primero.
"""

from __future__ import annotations

import json
from pathlib import Path


def _cita(item: dict) -> str:
    archivo = item.get("file")

    if not archivo:
        return ""

    linea = item.get("line")

    return f"`{archivo}:{linea}`" if linea else f"`{archivo}`"


def _tecnologias(evidencia: dict) -> list[str]:

    tecnologias = evidencia.get("technologies") or {}

    firmes = []
    mencionadas = []

    for nombre, datos in sorted(tecnologias.items()):

        procedencia = datos.get("provenance", "mentioned")

        if procedencia == "mentioned":
            mencionadas.append(nombre)
            continue

        evidencias = datos.get("evidence") or [{}]

        firmes.append(
            f"| {nombre} | `{procedencia}` | {_cita(evidencias[0])} |"
        )

    lineas = []

    if firmes:
        lineas += [
            "### Stack detectado",
            "",
            "Cada tecnología con el origen de su evidencia.",
            "",
            "| Tecnología | Procedencia | Evidencia |",
            "| --- | --- | --- |",
            *firmes,
            "",
        ]

    if mencionadas:
        lineas += [
            "### Nombres que aparecen pero NO son evidencia",
            "",
            "Estos nombres estan en algun texto del repositorio, pero no se",
            "declaran en ningun manifiesto, no se importan y no se cargan",
            "como recurso. **No se documentaron**, y no deberian.",
            "",
            "> " + ", ".join(f"`{n}`" for n in sorted(mencionadas)),
            "",
        ]

    return lineas


def _inventario(evidencia: dict) -> list[str]:

    manifiestos = evidencia.get("manifests") or []
    propios = [m for m in manifiestos if not m.get("third_party")]
    terceros = [m for m in manifiestos if m.get("third_party")]

    filas = [
        ("Archivos analizados", evidencia.get("metadata", {}).get("file_count", 0)),
        ("Manifiestos propios", len(propios)),
        ("Dependencias declaradas", sum(len(m["dependencies"]) for m in propios)),
        ("Scripts", len(evidencia.get("npm_scripts") or [])),
        ("Endpoints", len(evidencia.get("api") or [])),
        ("Tablas", len(evidencia.get("database_tables") or [])),
        ("Variables de entorno", len(evidencia.get("environment_variables") or [])),
    ]

    lineas = [
        "### Evidencia recogida",
        "",
        "| | |",
        "| --- | ---: |",
        *[f"| {nombre} | {valor} |" for nombre, valor in filas],
        "",
    ]

    if terceros:
        lineas += [
            f"Se ignoraron **{len(terceros)}** manifiestos de codigo de "
            "terceros que el repositorio versiona pero que no son del "
            "proyecto.",
            "",
        ]

    return lineas


def _sin_verificar(evidencia: dict, auditoria: str) -> list[str]:

    lineas = []

    capacidades = evidencia.get("capability_signals") or {}

    debiles = [
        nombre
        for nombre, datos in capacidades.items()
        if datos.get("confidence") == "low"
    ]

    if debiles:
        lineas += [
            "Señales de capacidad con respaldo débil, tratadas como "
            "indicios y no como funcionalidades: "
            + ", ".join(f"`{c}`" for c in sorted(debiles)),
            "",
        ]

    avisos = [
        linea.strip("- ").strip()
        for linea in (auditoria or "").splitlines()
        if linea.strip().startswith("- ")
    ]

    if avisos:
        lineas += [
            "<details>",
            "<summary>"
            f"El auditor levantó {len(avisos)} advertencia(s)"
            "</summary>",
            "",
            *[f"- {a}" for a in avisos[:40]],
            "",
            "</details>",
            "",
        ]

    if not lineas:
        return []

    return ["### Lo que no se pudo verificar", ""] + lineas


def construir(
    nombre_repo: str,
    resultado_merge,
    evidencia: dict,
    auditoria: str = "",
    propuesta: str | None = None,
    artefactos: list[dict] | None = None,
) -> str:
    """
    Arma el informe en Markdown.
    """

    titulos = {
        "creado": "README creado",
        "fusionado": "Bloques gestionados actualizados",
        "respetado": "No se modificó nada",
        "bloqueado": "Repositorio bloqueado",
    }

    lineas = [
        f"## {titulos.get(resultado_merge.accion, resultado_merge.accion)}",
        "",
        resultado_merge.motivo,
        "",
    ]

    if resultado_merge.conflictos:
        lineas += [
            "**Bloques congelados por edición humana:** "
            + ", ".join(f"`{c}`" for c in resultado_merge.conflictos),
            "",
            "El generador detectó que su contenido cambió desde la última "
            "corrida, así que no los tocó.",
            "",
        ]

    lineas += _inventario(evidencia)
    lineas += _tecnologias(evidencia)
    lineas += _sin_verificar(evidencia, auditoria)

    if artefactos:
        from readme3_artifacts import bloque_para_el_informe

        lineas += bloque_para_el_informe(artefactos)

    # Cuando no se escribe nada, la propuesta tiene que verse en alguna
    # parte o el trabajo se pierde.
    if propuesta and not resultado_merge.escribe:
        lineas += [
            "<details>",
            "<summary>Propuesta del generador (no aplicada)</summary>",
            "",
            "```markdown",
            propuesta.strip(),
            "```",
            "",
            "</details>",
            "",
        ]

    lineas += [
        "---",
        "",
        "Generado por "
        "[`Sud-Austral/coipo_aireadme`]"
        "(https://github.com/Sud-Austral/coipo_aireadme) "
        f"sobre `{nombre_repo}`.",
        "",
        "Todo lo documentado procede de la evidencia citada arriba. "
        "Si algo no cuadra, corrígelo en el README: el generador respeta "
        "lo que edites.",
    ]

    return "\n".join(lineas)


def escribir(
    destino: Path,
    contenido: str,
) -> Path:

    destino.write_text(contenido, encoding="utf-8")

    return destino


def cargar_evidencia(ruta: Path) -> dict:

    try:
        return json.loads(ruta.read_text(encoding="utf-8"))

    except Exception:
        return {}
