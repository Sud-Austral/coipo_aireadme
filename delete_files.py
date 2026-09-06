#!/usr/bin/env python3
"""
delete_files.md: propone la basura, nunca la borra.

Arquitectura
------------

Dos etapas, y la separacion es lo importante:

    1. readme3_orphans.py encuentra los candidatos de forma determinista,
       cada uno con la evidencia de por que lo parece.

    2. El modelo los JUZGA y redacta la justificacion, en una llamada
       propia. No descubre candidatos: solo puede descartar los de la lista
       y explicar los que quedan.

Sin la etapa 2 el informe seria una lista de borrados peligrosa: un sufijo
`_v2` puede ser versionado legitimo y `copy` puede ser parte del nombre.
Sin la etapa 1 el modelo podria inventar rutas.

RIEL DURO: el generador NUNCA borra. Ni por CI, ni con opt-in, ni con
bandera. delete_files.md es una lista para que decida una persona, con un
bloque `git rm` para copiar y pegar.

PRINCIPIO: DETECCION != CONCLUSION.
Detectar que algo parece huerfano no es concluir que sobra.
"""

from __future__ import annotations

import json

MAX_CANDIDATOS = 60

CABECERA = """# Archivos propuestos para borrar

> Generado por `Sud-Austral/coipo_aireadme`. **Nada se borro.**
> Esta es una lista para revisar; la decision es de una persona.
"""

LIMITACION = """
## Lo que este analisis no puede ver

La deteccion de huerfanos es estatica. No ve `importlib`, ni imports
dinamicos, ni rutas construidas en cadenas de texto, ni archivos
referenciados desde HTML, ni datos que se leen por ruta en tiempo de
ejecucion.

Por eso hay una seccion **Revisar**: no es una nota al pie, es la mitad del
informe.
"""


def crear_prompt(candidatos: list[dict], nombre_repo: str) -> str:
    """
    Prompt de la segunda etapa. El modelo juzga; no descubre.
    """

    listado = json.dumps(
        [
            {
                "ruta": c["path"],
                "bytes": c["size"],
                "categoria": c["categoria"],
                "confianza_del_detector": c["confianza"],
                "evidencia": c["evidencia"],
            }
            for c in candidatos[:MAX_CANDIDATOS]
        ],
        ensure_ascii=False,
        indent=1,
    )

    return f"""
Eres un revisor de codigo senior. Vas a clasificar candidatos a borrar del
repositorio {nombre_repo}.

============================================================
REGLA DURA
============================================================

SOLO puedes pronunciarte sobre las rutas de la lista de abajo.

No propongas ninguna ruta que no este en la lista. No inventes archivos. No
completes con lo que "seguramente tambien sobra".

============================================================
TU TAREA
============================================================

Para cada candidato, decide una de dos cosas:

  BORRAR    la evidencia basta. Es un artefacto, un resto de build o una
            copia evidente.

  REVISAR   parece huerfano pero podria no serlo. Todo lo que dependa de
            que nadie lo referencie entra aqui, salvo que la evidencia sea
            concluyente.

Ante la duda, REVISAR. Es asimetrico a proposito: proponer borrar algo vivo
cuesta mucho mas que dejar un archivo muerto un mes mas.

Escribe para cada uno una justificacion de UNA frase, concreta, basada en la
evidencia que se te da. No repitas la evidencia literal: explica que
significa.

============================================================
LO QUE NO PUEDES HACER
============================================================

- Proponer borrar codigo fuente solo porque nadie lo importe. Un punto de
  entrada, un script de operador o un modulo cargado dinamicamente no los
  importa nadie.
- Proponer borrar datos. Lo que parece una salida vieja puede ser el insumo
  del proyecto.
- Escribir comandos que borren directorios enteros.
- Suavizar la categoria REVISAR para que el informe parezca mas util.

============================================================
CANDIDATOS
============================================================

{listado}

============================================================
SALIDA
============================================================

Devuelve JSON y nada mas, con esta forma exacta:

{{
  "borrar":  [{{"ruta": "...", "porque": "..."}}],
  "revisar": [{{"ruta": "...", "porque": "..."}}]
}}
""".strip()


def parsear_respuesta(texto: str) -> dict:
    """
    Lee el JSON del modelo sin hacer fallar la corrida.
    """

    limpio = (texto or "").strip()

    for envoltura in ("```json", "```"):
        if limpio.startswith(envoltura):
            limpio = limpio[len(envoltura):].strip()
            if limpio.endswith("```"):
                limpio = limpio[:-3].strip()
            break

    try:
        datos = json.loads(limpio)

    except Exception:
        return {"borrar": [], "revisar": []}

    if not isinstance(datos, dict):
        return {"borrar": [], "revisar": []}

    return {
        "borrar": datos.get("borrar") or [],
        "revisar": datos.get("revisar") or [],
    }


def _tabla(titulo: str, filas: list[dict], indice: dict) -> list[str]:

    if not filas:
        return []

    lineas = [
        f"## {titulo}",
        "",
        "| Archivo | Tamaño | Por que |",
        "| --- | ---: | --- |",
    ]

    for fila in filas:

        ruta = fila.get("ruta", "")
        candidato = indice.get(ruta, {})
        tamano = candidato.get("size", 0)

        lineas.append(
            f"| `{ruta}` | {tamano / 1024:.0f} KB | "
            f"{fila.get('porque', '').strip()} |"
        )

    lineas.append("")

    return lineas


def construir(
    nombre_repo: str,
    candidatos: list[dict],
    veredicto: dict,
    resumen_detector: dict,
    total_archivos: int,
) -> str:
    """
    Arma delete_files.md.
    """

    indice = {c["path"]: c for c in candidatos}

    borrar = [
        f for f in veredicto.get("borrar", [])
        if f.get("ruta") in indice
    ]

    revisar = [
        f for f in veredicto.get("revisar", [])
        if f.get("ruta") in indice
    ]

    # Un candidato sobre el que el modelo no se pronuncio no se pierde: cae
    # en Revisar, que es el lado seguro.
    resueltos = {f["ruta"] for f in borrar} | {f["ruta"] for f in revisar}

    for candidato in candidatos:
        if candidato["path"] not in resueltos:
            revisar.append(
                {
                    "ruta": candidato["path"],
                    "porque": (
                        "El revisor no se pronuncio sobre este archivo. "
                        f"El detector lo marco como {candidato['categoria']}."
                    ),
                }
            )

    lineas = [CABECERA, ""]

    if not candidatos:
        lineas += [
            "No se encontro ningun candidato. El repositorio esta limpio.",
            "",
        ]
        return "\n".join(lineas)

    bytes_borrar = sum(
        indice[f["ruta"]]["size"] for f in borrar
    )

    lineas += [
        "## Cuanto se recupera",
        "",
        f"El detector encontro **{resumen_detector['archivos']}** candidatos "
        f"({resumen_detector['bytes'] / 1024:.0f} KB), el "
        f"**{resumen_detector['porcentaje_archivos']}%** de los "
        f"{total_archivos} archivos que el analizador recorre en cada "
        "corrida.",
        "",
        f"De ellos, **{len(borrar)}** se proponen para borrar "
        f"({bytes_borrar / 1024:.0f} KB) y **{len(revisar)}** quedan para "
        "revisar.",
        "",
        "Esto no es solo orden: cada archivo muerto ocupa presupuesto de "
        "contexto y empuja la evidencia real contra el corte de 30.000 "
        "caracteres que se envia al modelo.",
        "",
    ]

    lineas += _tabla("Propuestos para borrar", borrar, indice)
    lineas += _tabla("Revisar antes de decidir", revisar, indice)

    if borrar:
        lineas += [
            "## Para copiar y pegar",
            "",
            "Revisa la lista antes de ejecutar esto. **El generador no lo "
            "ejecuta.**",
            "",
            "```bash",
            *[f'git rm --cached "{f["ruta"]}"' for f in borrar],
            "```",
            "",
            "Se usa `--cached` a proposito: saca el archivo del control de "
            "versiones sin borrarlo de tu disco. Anadelo despues al "
            "`.gitignore` si corresponde.",
            "",
        ]

    lineas.append(LIMITACION)

    return "\n".join(lineas)
