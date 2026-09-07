# Que se construyo

## Que hace, en dos parrafos

Permite recorrer un repositorio, clasificar sus archivos y separar el codigo
propio del que solo viene incrustado [readme3_scanner.py], leer sus
manifiestos para saber que declara usar [readme3_manifests.py], extraer de
su codigo las rutas expuestas, las tablas, las variables de entorno y las
dependencias [readme3_analyzers.py], y armar con todo eso un cuerpo de
evidencia con la cita de donde salio cada cosa [readme3_evidence.py].
Permite ademas distinguir lo que un repositorio declara de lo que solo
menciona [readme3_provenance.py], detectar patrones de dato personal y
comprobar si esas rutas estan ignoradas con ancla [readme3_pii.py], y
proponer archivos que parecen haber quedado huerfanos
[readme3_orphans.py], [delete_files.py].

Permite despues redactar la documentacion a partir de esa evidencia y no de
otra cosa [makeReadme.py], validar el texto redactado contra la evidencia
para detectar variables, endpoints, tablas, tecnologias y comandos que no
existen [validate_readme.py], calcular una huella de la evidencia para no
volver a redactar cuando nada cambio [readme3_fingerprint.py], fusionar el
resultado sin tocar lo que escribio una persona [readme_merge.py] y
entregarlo como cambio propuesto con el detalle de en que se apoya
[pr_body.py]. Y permite operar eso sobre muchos repositorios a la vez:
censarlos [fleet_scan.py], elegir cuales tocar [fleet_select.py], publicar un
inventario [fleet_card.py], instalar el flujo en cada uno [propagar.py] y
auditar que quedo instalado [auditar_workflows.py].

Permite tambien lo que produjo este mismo documento: reconstruir los insumos
de un proyecto ya construido a partir de su evidencia, con validacion de que
cada cita apunte a un archivo que existe de verdad
[insumos_inversos.py], [prompts/11-derivar-insumos-desde-codigo.md].

## Roles: quien ve que

No hay roles en el codigo. El analizador busco guardas, decoradores de
autorizacion y tablas de permisos y no encontro ninguno; tampoco hay rutas
expuestas ni base de datos. Esta seccion, que en un sistema de negocio es la
mas solida, aca esta vacia y hay que decirlo asi.

[INFERIDO] Lo que hace las veces de control de acceso es el token con el que
se habla con la plataforma, leido del entorno [propagar.py:641],
[github_client.py]. Todo lo que el sistema puede hacer, lo puede hacer con
el alcance de ese token; y lo que hace incluye escribir archivos en
repositorios ajenos [propagar.py]. Quien custodia ese token: [PENDIENTE].

[INFERIDO] Hay un limite de alcance declarado en codigo: el cliente decide
si un repositorio esta dentro o fuera [github_client.py]. Cual es el
criterio exacto y quien lo fija es [PENDIENTE].

[INFERIDO] La unica decision reservada a una persona es aceptar o rechazar
el cambio propuesto [pr_body.py], [README.md], y el rechazo se recuerda para
no reproponer [fleet_select.py].

## De donde salen los datos

[INFERIDO] La fuente principal es la plataforma donde viven los
repositorios, consultada por su API con un token
[github_client.py], [propagar.py:641]. QUIEN ES DUENO de esa organizacion y
de sus repositorios es [PENDIENTE].

[INFERIDO] La segunda fuente es un servicio de modelo de lenguaje externo al
que se le manda el contexto para redactar [makeReadme.py]. Que proveedor es,
quien paga esa cuenta y bajo que condiciones se le manda contenido de
repositorios privados: [PENDIENTE] y [VERIFICAR].

[INFERIDO] La tercera es la configuracion opcional que cada repositorio
puede declarar sobre si mismo [readme_config.py],
[.aireadme.yml.example], mas una lista de rutas a ignorar que llega por
variable de entorno [makeReadme.py:1339]. Lo declarado se trata como
testimonio y no como inferencia, y hay una prueba que lo fija
[tests/test_config.py].

[INFERIDO] El resultado del censo se guarda como archivo en el propio
repositorio [fleet/catalogo.json], [fleet/CATALOGO.md]. Es un dato derivado,
no una fuente.

## Que NO hace

Las ausencias siguientes se afirman porque el analizador enumero la
categoria completa. Siguen marcadas.

[INFERIDO] No expone ninguna ruta: la enumeracion de endpoints del
analizador sobre este repositorio esta vacia. No es un servicio, es un
proceso que corre y termina.

[INFERIDO] No tiene base de datos: la enumeracion de tablas esta vacia. Todo
el estado que conserva son archivos.

[INFERIDO] No borra archivos. Propone borrados y deja el comando en manos de
quien revisa [delete_files.py], y hay una prueba que fija que el comando
sugerido no borra del disco [tests/test_limpieza.py].

[INFERIDO] No edita el archivo de exclusiones de un repositorio cuando
encuentra un dato personal versionado: comprueba si la ruta esta ignorada
con ancla y lo reporta [readme3_pii.py].

[INFERIDO] No sobrescribe documentacion escrita por una persona, y eso no es
una promesa del texto sino una condicion fijada en pruebas
[readme_merge.py], [tests/test_contrato.py].

[INFERIDO] No usa ninguna de las tecnologias que nombra. Las veintitres que
el analizador encontro al analizarse a si mismo aparecen todas como
mencionadas y ninguna como declarada, porque estan en sus propias reglas de
deteccion [readme3_analyzers.py]. Hay una prueba dedicada a que el
repositorio no se detecte tecnologias a si mismo
[tests/test_engine.py]. Sus dependencias reales son tres
[requirements.txt:5], [requirements.txt:6], [requirements.txt:7].

## Iteraciones

[INFERIDO] Hay cinco flujos de trabajo distintos: integracion continua,
censo de flota, barrido de flota, generacion de documentacion y el flujo
corto que se instala en cada repositorio
[.github/workflows/ci.yml], [.github/workflows/fleet-census.yml],
[.github/workflows/fleet-sweep.yml], [.github/workflows/generate-readme.yml],
[.github/workflows/readme.yml]. El de generacion es, con diferencia, el
archivo de configuracion mas largo del repositorio.

[INFERIDO] Hay siete archivos de prueba, uno por cada regla que el sistema
se impuso: configuracion, contrato de no sobrescritura, motor de deteccion,
huella, insumos derivados, limpieza y validador
[tests/test_config.py], [tests/test_contrato.py], [tests/test_engine.py],
[tests/test_huella.py], [tests/test_insumos.py], [tests/test_limpieza.py],
[tests/test_validador.py]. La forma de leer eso: cada regla se rompio alguna
vez, o se temio que se rompiera.

[INFERIDO] El nombre del analizador lleva un tres [readme3.py]: hubo al
menos dos versiones anteriores que no estan en este repositorio.

[INFERIDO] Hay operacion documentada aparte [docs/OPERACION.md] y una
herramienta para dejar en cero las ramas de un ambiente
[reset_uat_branches.py], lo que apunta a que existe mas de un ambiente en la
flota. Cual y quien lo administra es [PENDIENTE].
