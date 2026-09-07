# coipo_aireadme

Escribe y mantiene el `README.md` de los repositorios `coipo_*` de
Sud-Austral, leyendo su código.

**No tienes que hacer nada para que funcione.** Está instalado en los 57
repositorios en alcance y se dispara solo.

---

## Cómo funciona, en una frase

Cuando haces `push` a `main` en un repositorio `coipo_*`, el bot lo analiza,
escribe un README y te abre un Pull Request. Tú lo revisas y decides.

```
push a main
   │
   ├─ ¿el README está escrito a mano?  ──── sí ──▶  no lo toca. Fin.
   │
   ├─ ¿cambió algo desde la última vez? ─── no ──▶  no llama al modelo. Fin.
   │
   └─ sí ──▶ analiza el código ──▶ redacta ──▶ valida ──▶ abre un PR
```

Los dos primeros cortes son la mayor parte de las corridas. En la flota
actual, **14 de 24 repositorios tienen el README escrito a mano** y el bot
no los toca nunca.

## Qué haces tú

Una sola cosa: **revisar el Pull Request y mergearlo, o cerrarlo**.

Si lo cierras sin fusionar, el sistema lo anota y **no te lo vuelve a
proponer**. Cerrarlo es una respuesta válida.

## Qué NO tienes que hacer

- No tienes que instalarlo. Ya está.
- No tienes que configurarlo. `.aireadme.yml` es opcional.
- No tienes que protegerte de él. Si el README lo escribiste tú, no lo toca.

---

## Las reglas que se impuso

**Nunca sobrescribe documentación humana.** Si el README tiene contenido y
no declara bloques `AI:BEGIN`, no se modifica. Punto. La propuesta va en el
cuerpo del PR para que la mires si quieres.

**Nunca inventa.** Cada tecnología que documenta viene de un manifiesto, de
un `import` o de un recurso cargado en el HTML, y lleva su cita
`[archivo:línea]`. Lo que solo aparece mencionado en un texto se emite
aparte, marcado como *no evidencia*.

**Nunca borra.** `delete_files.md` propone archivos que parecen sobrar, con
un `git rm --cached` para copiar y pegar. Lo ejecutas tú o no lo ejecuta
nadie.

El principio que las ordena está escrito en el código:

> **DETECCIÓN != CONCLUSIÓN.**
> El analizador no decide qué significa el software. Recopila evidencia.

---

## Ver qué haría antes de que lo haga

```bash
python preview.py "D:/GitHub/COIPO_ENTREGA_PLANTA"
```

No llama al modelo ni escribe nada. Te dice qué evidencia ve, con qué
procedencia, qué decidiría hacer con el README y qué propondría borrar.

## Pedirle algo distinto

Pon un `.aireadme.yml` en la raíz del repositorio. Los cuatro campos que
importan:

```yaml
# Apaga la generación en este repositorio.
enabled: true

# Rutas que no aportan nada al análisis.
ignore_paths: []

# Lo más útil que puedes escribir aquí.
#
# El analizador sabe QUÉ hace el código. No sabe PARA QUÉ existe ni quién
# lo usa. Eso solo lo sabes tú, y pesa más que cualquier señal detectada.
declared: |
  Sistema para el área de X. Lo usan N personas de Y.
  Reemplazó a una planilla que se mantenía a mano.

# Reconstruir insumos/ desde el código (00-PROBLEMA, 01-SOLUCIÓN,
# MANIFIESTO). Es pesado y se corrige a mano, así que no va por defecto.
insumos: false
```

Hay una plantilla comentada en [`.aireadme.yml.example`](.aireadme.yml.example).

Para que deje de tocar un repositorio del todo, borra
`.github/workflows/readme.yml`. Es la única salida definitiva: `enabled:
false` para la generación, pero el workflow se sigue invocando.

---

## Qué más produce

| | |
| --- | --- |
| `delete_files.md` | Archivos que parecen sobrar, con evidencia. Nunca borra. |
| `insumos/` | `00-PROBLEMA.md`, `01-SOLUCIÓN.md` y `MANIFIESTO.yaml` deducidos del código. Opt-in. |
| Informe por corrida | En el PR y en el resumen de la ejecución: qué evidencia se usó y qué NO se pudo verificar. |
| [Catálogo público](fleet/CATALOGO.md) | Qué hay construido en COIPO. |
| `Sud-Austral/coipo_index` | El inventario completo, privado. |

---

## Para quien lo mantenga

Todo lo operativo está en [`docs/OPERACION.md`](docs/OPERACION.md): crear
los dos secretos, medir un lote antes de encender los cron, y qué mirar
cuando algo falla.

Dos cosas que conviene saber antes de tocar nada:

**La flota consume el tag `v1`, no `main`.** Mergear a `main` no despliega
nada. Publicar es mover el tag a propósito, después de que el golden set
esté verde. `main` es rama de trabajo.

**El modo de fallo más peligroso es silencioso.** Si el corte por huella se
calcula mal, la flota entera deja de documentarse sin que salte ninguna
alarma: un job saltado se ve gris, no rojo. Si un lunes nadie generó nada,
empieza por ahí.

```bash
python -m pytest tests/          # 110 tests
python auditar_workflows.py      # estado real de la flota
```

El fixture negativo del golden set es **este mismo repositorio**: contiene
el diccionario de nombres de tecnologías, así que un detector basado en
texto se atribuye a sí mismo React, Django, MongoDB y YOLO. El test exige
cero. Antes de la corrección medía 30 de 30.
