# Prompt: derivar los insumos desde el codigo

Contrapartida de `10-levantar-insumos.md` (en `coipo_master_produccion`).

Aquel se usa **antes** de escribir codigo, y su regla es no redactar nada sin
preguntarle a una persona, porque no hay otra fuente. Este se usa **despues**,
sobre un proyecto que ya existe, y aqui si hay otra fuente: el codigo.

Por eso no es el mismo prompt con las respuestas borradas. Necesita una marca
que el original no tiene, `[INFERIDO]`, y una regla dura distinta: alli era
sobre **leer**, aqui es sobre **escribir**.

Lo envia `insumos_inversos.py` junto al `README_CONTEXT_ULTRA.md`.

---

## El prompt

```text
Vamos a reconstruir los insumos de un proyecto que YA ESTA CONSTRUIDO. No hay
area usuaria en esta conversacion y no puedes preguntar nada: tu unica fuente
es la evidencia extraida del codigo, que viene mas abajo. Al final tiene que
existir insumos/ con 00-PROBLEMA.md, 01-SOLUCION.md y MANIFIESTO.yaml.

Esto no es un levantamiento. Es la ingenieria inversa del levantamiento que no
se hizo, y sirve para dos cosas: que exista documentacion donde hoy no hay
ninguna, y que el area usuaria tenga un borrador concreto que corregir en vez
de una hoja en blanco. Un borrador que se puede corregir vale. Uno que se
presenta como verdad, no.

## REGLA DURA, y no es negociable

SIN CITA NO HAY AFIRMACION. Cada frase que diga algo sobre el sistema lleva o
una cita [archivo:linea] tomada de la evidencia, o una marca. No hay tercera
opcion. Si no puedes citar y no quieres marcar, borra la frase.

La evidencia dice que hace el codigo. No dice que quiso hacer nadie, ni para
quien, ni por que. Confundir esas dos cosas es el unico error grave que puedes
cometer aca.

## Las tres marcas

  [INFERIDO]   lo dedujiste de la evidencia, y la cita va al lado. Es una
               hipotesis con respaldo, no un hecho del negocio. La confirma o
               la corrige el area usuaria.
  [PENDIENTE]  ni el codigo ni nadie lo respondio. Lo cierra una persona del
               negocio.
  [VERIFICAR]  hay una afirmacion juridica o normativa, o un dato que podria
               ser personal, que nadie ha confirmado. Lo cierra Fiscalia o
               Auditoria.

Inferir es detectar. Confirmar es concluir. Tu detectas; concluye otro.

## 00-PROBLEMA.md - que estaba roto, deducido de lo que se construyo

Aca la cadena de inferencia es debil y tienes que escribirla como lo que es:
"el sistema gestiona X, luego probablemente habia un problema con X".
Redactalo completo, no lo dejes en blanco, pero marca cada afirmacion.

  - Quien sufre el problema. Los ROLES si estan en el codigo: guards,
    decoradores, middleware de autorizacion, tabla de permisos. Nombralos con
    su cita y marcalos [INFERIDO]. CUANTAS PERSONAS son es [PENDIENTE]
    siempre: una tabla de usuarios con 40 filas de prueba no es un dato de
    dotacion.
  - Como lo resolvian antes. Si hay importadores de planilla (read_excel,
    read_csv, un endpoint de carga, columnas que replican una hoja de
    calculo), puedes inferir que el ingreso era manual: marcalo [INFERIDO] con
    la cita. QUIEN mantenia esa planilla y CUANTO TARDABA es [PENDIENTE].
  - Que pasa si no se hace nada. El codigo no lo responde. [PENDIENTE], sin
    excepcion. No lo deduzcas de que el sistema exista.
  - Volumen. Indices, paginacion, particiones y tipos de columna te dan un
    ORDEN DE MAGNITUD y nada mas: un BIGINT no prueba que haya millones de
    filas. Escribe el indicio con su cita, marcalo [INFERIDO], y deja la cifra
    como [PENDIENTE].
  - Quien decide que esta terminado. [PENDIENTE], sin excepcion.

## 01-SOLUCION.md - que se construyo

Aca si estas en tu terreno: el codigo ES la solucion. Este documento deberia
salir casi completo y con citas densas.

  - Que hace el sistema, en dos parrafos y sin nombrar tecnologia. Sale de los
    endpoints, las tablas y los docstrings. Describe capacidades, no archivos:
    "permite registrar convenios y consultarlos por institucion", nunca "tiene
    un modulo convenios.py".
  - Roles: quien ve que. Es la parte mas solida que vas a escribir. Cada rol
    con la cita del guard o decorador que lo impone y que operaciones
    habilita. Si un rol existe en el codigo pero ninguna ruta lo usa, dilo.
  - De donde salen los datos. Conexiones externas, APIs consumidas,
    migraciones, archivos semilla. La FUENTE es [INFERIDO] con cita; QUIEN ES
    DUENO de esa fuente es [PENDIENTE].
  - Que NO hace. Cuidado, porque la ausencia de evidencia no es evidencia de
    ausencia. Solo puedes afirmar una ausencia cuando el analizador busco de
    forma exhaustiva esa categoria: "no existe ningun endpoint cuyo path
    contenga export, descarga o informe" es afirmable; "no tiene
    trazabilidad" no lo es. Y marcala igual.
  - Iteraciones. Tags, CHANGELOG, migraciones numeradas. [INFERIDO].

## MANIFIESTO.yaml - el sellado, al reves

En el levantamiento normal el manifiesto se declara ANTES de abrir nada. Aca
los archivos ya estan abiertos, asi que el manifiesto documenta lo que hay y
deja constancia de lo que falta declarar.

    - ruta: backend/scripts/convenios.generated.json
      sha256: "<lo calcula el script de sellado>"
      origen: "[PENDIENTE] quien lo entrego y cuando"
      contiene_pii: "[VERIFICAR] 298 patrones de RUT; el formato de empresa y
                     el de persona natural son identicos"
      puede_versionarse: true
      uso: catalogo_convenios

  - ruta, sha256 y puede_versionarse no los redactas tu: los calcula el
    script.
  - origen es SIEMPRE [PENDIENTE]. "Quien lo entrego, cuando y en que reunion"
    no esta escrito en ningun repositorio, y no lo inventes desde el autor del
    commit.
  - contiene_pii: reporta el patron y el conteo, NUNCA el valor. No
    transcribas un RUT ni un correo dentro del documento. Si el archivo vive
    en tests/, fixtures/, mocks/ o seed, dilo, porque cambia mucho la
    probabilidad de que sea sintetico, pero no lo des por sintetico tu.
  - Si un archivo ya trae una nota de resolucion de una corrida anterior y su
    sha256 no cambio, respetala y no lo vuelvas a marcar.
  - Si contiene_pii se confirma true, entonces puede_versionarse es false, y
    entonces la ruta tiene que estar en .gitignore ANCLADA CON BARRA INICIAL.
    Si no lo esta, es un hallazgo del informe. No edites .gitignore tu.

## Lo que NO puedes hacer

  - Convertir un nombre de archivo, de carpeta o de dependencia en una
    funcionalidad. Que exista pandas no significa que haya analitica.
  - Ascender un [INFERIDO] a hecho porque suena razonable.
  - Inventar cifras, nombres de personas, areas, instituciones o normas.
  - Citar una ley por su numero: eso es [VERIFICAR] siempre, incluso si
    aparece escrita en el propio codigo.
  - Transcribir datos que parezcan personales dentro de los documentos.
  - Borrar, mover o editar archivos, .gitignore incluido. Tu escribes
    documentos.
  - Sobrescribir un insumos/ existente. Si ya hay uno levantado con personas,
    el tuyo se llama insumos/DERIVADO-DEL-CODIGO.md y reporta en que difiere.

## Como termina

Devuelve los tres documentos separados EXACTAMENTE por estas lineas, cada una
sola en su renglon y sin nada mas:

===== 00-PROBLEMA.md =====
===== 01-SOLUCION.md =====
===== MANIFIESTO.yaml =====
===== INFORME =====

En INFORME van tres listas:

  - los [PENDIENTE], con a quien habria que preguntarle cada uno;
  - los [VERIFICAR], con quien los cierra;
  - que partes del sistema NO pudiste describir porque la evidencia no
    llegaba: un modulo sin docstrings, un front sin rutas detectables, una
    tabla que ningun endpoint toca. Esa lista dice donde esta ciego el
    analizador, y suele ser la mas util de las tres.
```

---

## Las tres inversiones

Sin estas tres, esto seria el prompt original mal aplicado.

**1. La regla dura cambia de objeto.** En el original es *"sin entrada en el
manifiesto, no abras el archivo"*: una regla sobre **leer**. Aca los archivos
ya se leyeron, asi que la regla pasa a ser sobre **escribir**: sin cita no hay
afirmacion.

**2. Aparece `[INFERIDO]`**, que el original no necesita porque alli no hay
nada que inferir. Es lo que hace posible el ejercicio inverso sin romper
`DETECCION != CONCLUSION`: inferir es detectar, confirmar es concluir, y
concluir sigue siendo del humano.

**3. `00-PROBLEMA.md` se redacta hacia atras**, desde la solucion, y el prompt
obliga a escribir esa cadena de inferencia en voz alta en vez de ocultarla. Es
la parte mas debil del ejercicio y por eso es la que mas marcas lleva.
