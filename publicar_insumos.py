#!/usr/bin/env python3
"""
Publica los insumos derivados en sus repositorios.

Valida antes de escribir
------------------------

Ningun documento se sube sin pasar dos controles:

  1. Toda cita [archivo:linea] apunta a un archivo que existe de verdad.
     Es el control mas importante. Medido sobre coipo_sitra, un modelo
     llego a citar auth.py, models.py y tres archivos mas que no existian:
     el 100% de sus citas eran inventadas. Una cita falsa es peor que
     ninguna, porque parece verificable.

  2. Ningun documento transcribe un valor con formato de dato personal.
     Se reporta el patron y el conteo, nunca el valor. Copiar un RUT dentro
     de un documento versionado crea el problema que el manifiesto pretende
     evitar.

Y nunca pisa un insumos/ levantado con personas.

    python publicar_insumos.py --origen ./generados --evidencia ./evidencia
    python publicar_insumos.py --origen ./generados --evidencia ./evidencia --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from github_client import GitHubClient
from insumos_inversos import DOCUMENTOS, validar_citas
from readme3_pii import CORREO_NO_PERSONAL, RUT, _correos_personales

MENSAJE = """docs: insumos derivados del codigo

00-PROBLEMA.md, 01-SOLUCION.md y MANIFIESTO.yaml reconstruidos leyendo el
codigo de este repositorio.

NO son un levantamiento. Cada afirmacion lleva una de tres marcas:

  [INFERIDO]   se dedujo de la evidencia citada. Es una hipotesis con
               respaldo, no un hecho del negocio.
  [PENDIENTE]  ni el codigo ni nadie lo respondio.
  [VERIFICAR]  afirmacion juridica o dato posiblemente personal.

Corregirlos es mas rapido que partir de una hoja en blanco. No los des por
buenos: lo que el codigo no puede saber esta marcado como tal.

Toda cita [archivo:linea] se comprobo contra la lista real de archivos
antes de publicar.

Generado por Sud-Austral/coipo_aireadme."""


def _valores_personales(texto: str) -> list[str]:
    """
    Valores con formato de dato personal transcritos en el documento.

    El manifiesto habla DE ellos; nunca los contiene.
    """

    hallazgos = list(set(RUT.findall(texto)))

    hallazgos += [
        c for c in _correos_personales(texto)
        if not CORREO_NO_PERSONAL.search(c)
    ]

    return hallazgos


def _sellar(manifiesto: str, evidencia: dict, repo_dir: Path | None) -> str:
    """
    Sustituye los sha256 de marcador por los reales, si se pueden calcular.
    """

    lineas = manifiesto.splitlines()
    salida = []
    ruta_actual = None

    for linea in lineas:

        coincidencia = re.match(r"\s*-?\s*ruta:\s*(.+?)\s*$", linea)

        if coincidencia:
            ruta_actual = coincidencia.group(1).strip().strip("\"'")

        if re.match(r"\s*sha256:", linea):

            sangria = linea[: len(linea) - len(linea.lstrip())]

            sha = None

            if repo_dir and ruta_actual:
                archivo = repo_dir / ruta_actual
                if archivo.is_file():
                    import hashlib
                    sha = hashlib.sha256(
                        archivo.read_bytes()
                    ).hexdigest()

            linea = (
                f'{sangria}sha256: "{sha}"'
                if sha
                else f'{sangria}sha256: "[PENDIENTE] sin calcular"'
            )

        salida.append(linea)

    return "\n".join(salida) + "\n"


def revisar(
    nombre: str,
    documentos: dict[str, str],
    evidencia: dict,
) -> list[str]:
    """
    Devuelve los problemas encontrados. Vacio significa publicable.
    """

    problemas = []

    faltantes = [d for d in DOCUMENTOS if d not in documentos]

    if faltantes:
        problemas.append(f"faltan documentos: {', '.join(faltantes)}")

    citas = validar_citas(documentos, evidencia)

    if citas["inventadas"]:
        problemas.append(
            f"{len(citas['inventadas'])} de {citas['total']} citas apuntan "
            f"a archivos que no existen: "
            f"{', '.join(citas['inventadas'][:6])}"
        )

    if citas["total"] == 0:
        problemas.append(
            "ninguna cita: un documento sin citas no es verificable"
        )

    for documento, texto in documentos.items():

        valores = _valores_personales(texto)

        if valores:
            problemas.append(
                f"{documento} transcribe {len(valores)} valor(es) con "
                f"formato de dato personal"
            )

    return problemas


def main() -> int:

    parser = argparse.ArgumentParser()
    parser.add_argument("--origen", required=True)
    parser.add_argument("--evidencia", required=True)
    parser.add_argument("--local", default="d:/GitHub")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo", action="append", default=[])

    argumentos = parser.parse_args()

    origen = Path(argumentos.origen)
    base_evidencia = Path(argumentos.evidencia)
    local = Path(argumentos.local) if argumentos.local else None

    client = None if argumentos.dry_run else GitHubClient()

    carpetas = sorted(
        d for d in origen.iterdir()
        if d.is_dir()
        and (not argumentos.repo or d.name in argumentos.repo)
    )

    publicados, rechazados, saltados = [], [], []

    for carpeta in carpetas:

        nombre = carpeta.name

        archivo_evidencia = base_evidencia / f"{nombre}.json"

        if not archivo_evidencia.exists():
            rechazados.append((nombre, "sin evidencia recolectada"))
            continue

        evidencia = json.loads(
            archivo_evidencia.read_text(encoding="utf-8")
        )

        documentos = {
            d: (carpeta / d).read_text(encoding="utf-8")
            for d in DOCUMENTOS
            if (carpeta / d).exists()
        }

        problemas = revisar(nombre, documentos, evidencia)

        if problemas:
            rechazados.append((nombre, "; ".join(problemas)))
            continue

        # Sellado del manifiesto con hashes reales cuando hay clon local.
        repo_dir = None

        if local:
            for candidato in (local / nombre, local / nombre.upper()):
                if candidato.is_dir():
                    repo_dir = candidato
                    break

        documentos["MANIFIESTO.yaml"] = _sellar(
            documentos["MANIFIESTO.yaml"], evidencia, repo_dir
        )

        info = evidencia.get("_repo", {})

        full_name = info.get("nombre") and (
            info.get("full_name") or f"Sud-Austral/{nombre}"
        )

        rama = info.get("default_branch", "main")

        if argumentos.dry_run:
            publicados.append(nombre)
            print(f"   [seco] {nombre}: {len(documentos)} documentos")
            continue

        # No pisar un insumos/ levantado con personas.
        existente, _ = client.get_file(
            full_name, "insumos/00-PROBLEMA.md", rama
        )

        if existente and "DERIVADO DEL CODIGO" not in existente.upper():
            saltados.append(
                (nombre, "ya tiene insumos levantados con personas")
            )
            continue

        error = None

        for documento, contenido in documentos.items():

            ruta = f"insumos/{documento}"

            _, sha = client.get_file(full_name, ruta, rama)

            respuesta = client.put_file(
                repository=full_name,
                path=ruta,
                branch=rama,
                content=contenido,
                sha=sha,
                message=MENSAJE,
            )

            if respuesta.status_code not in (200, 201):
                error = f"{ruta}: HTTP {respuesta.status_code}"
                break

        if error:
            rechazados.append((nombre, error))
        else:
            publicados.append(nombre)
            print(f"   publicado {nombre}")

    print()
    print("=" * 70)
    print(f" Publicados : {len(publicados)}")
    print(f" Saltados   : {len(saltados)}")
    print(f" Rechazados : {len(rechazados)}")
    print("=" * 70)

    for nombre, motivo in saltados:
        print(f"   SALTADO   {nombre}: {motivo}")

    for nombre, motivo in rechazados:
        print(f"   RECHAZADO {nombre}: {motivo}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
