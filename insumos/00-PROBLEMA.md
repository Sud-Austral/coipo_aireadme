# Que estaba roto, deducido de lo que se construyo

Este repositorio es una herramienta interna y no un sistema de negocio, asi
que la cadena de inferencia tiene una vuelta de mas: del codigo se deduce
que problema tenia el equipo que lo escribio, no que problema tenia un area
usuaria. Va marcado igual.

## El objeto del problema

El sistema analiza repositorios ajenos, redacta su documentacion y propone
el resultado como cambio a revisar [makeReadme.py], [readme3.py],
[pr_body.py]. [INFERIDO] Luego probablemente habia un problema con la
documentacion de los repositorios: no existia, o existia desactualizada.

[INFERIDO] El problema no era solo la falta de documentacion, sino la
desconfianza en la que se escribe automaticamente. Casi todo el codigo esta
dedicado a no equivocarse: un modulo que separa lo declarado en un
manifiesto de lo apenas mencionado en un comentario
[readme3_provenance.py], [readme3_manifests.py], un validador que compara el
texto redactado contra la evidencia y detecta variables, endpoints, tablas y
comandos inventados [validate_readme.py], una huella que evita volver a
llamar al modelo cuando nada cambio [readme3_fingerprint.py], y una fusion
que se niega a tocar documentacion escrita por una persona
[readme_merge.py]. Se construyo mas control que produccion.

[INFERIDO] Antes se hacia a mano, o no se hacia. El repositorio guarda un
propagador que instala el mismo flujo de trabajo en muchos repositorios de
una vez [propagar.py] y un auditor que revisa si esos flujos quedaron bien
puestos [auditar_workflows.py]: se estaba resolviendo un problema de escala,
no de un repositorio suelto. CUANTO tardaba antes escribir un README y QUIEN
lo hacia es [PENDIENTE].

## Quien sufre el problema

[INFERIDO] Quien recibe el resultado es quien revisa el cambio propuesto: el
sistema no publica, propone [pr_body.py], y el propio README del repositorio
declara que la unica accion esperada de una persona es revisar y fusionar o
cerrar [README.md]. Cerrar sin fusionar es una respuesta valida y el sistema
la recuerda [fleet_select.py].

[INFERIDO] No hay roles en el sentido habitual: no hay guardas, ni
decoradores de autorizacion, ni tabla de permisos en el repositorio. El
unico control de acceso que aparece es el token con el que se habla con la
plataforma [propagar.py:641], [github_client.py]. Quien tiene ese token y
con que alcance es [PENDIENTE], y es la pregunta de seguridad principal de
este repositorio.

CUANTAS PERSONAS revisan estos cambios: [PENDIENTE], siempre.
Quien es responsable de la herramienta: [PENDIENTE].

## Como lo resolvian antes

[INFERIDO] Sin herramienta. La existencia de un repuntador de documentacion
minima [repuntar_stubs.py] sugiere que el punto de partida de la flota eran
archivos casi vacios. QUIEN los escribio y cuando es [PENDIENTE].

## Que pasa si no se hace nada

[PENDIENTE], sin excepcion. Que un repositorio quede sin documentar tiene
consecuencias, pero cuales y para quien no lo dice el codigo.

## Volumen

[INFERIDO] El volumen se mide en repositorios, no en filas. Hay un censo de
flota, un selector y un catalogo publicado
[fleet_scan.py], [fleet_select.py], [fleet_card.py],
[fleet/catalogo.json], [fleet/CATALOGO.md]. El propio README declara una
cifra de repositorios en alcance [README.md]; es una autodeclaracion del
repositorio y hay que tratarla como tal: [PENDIENTE] confirmarla contra la
organizacion.

[INFERIDO] No hay base de datos ni indices: el estado vive en archivos
[fleet/catalogo.json], [api.json]. El diseno no espera crecer por ese lado.

## Quien decide que esta terminado

[PENDIENTE], sin excepcion. El codigo describe como se propone un cambio
[pr_body.py] y como se recuerda un rechazo [fleet_select.py], pero no quien
tiene la ultima palabra sobre la documentacion de un repositorio ajeno.

## Marco normativo

[VERIFICAR] El sistema detecta patrones de dato personal en los
repositorios que analiza y comprueba si las rutas afectadas estan ignoradas
con ancla [readme3_pii.py]. Que se considera dato personal, que hay que
hacer cuando aparece uno versionado y quien responde por ello no lo decide
esta herramienta.

[VERIFICAR] El sistema envia contenido de repositorios —privados incluidos,
segun distingue el propio inventario [fleet_card.py]— a un servicio de
modelo de lenguaje externo [makeReadme.py]. Que se envia, a donde y bajo que
condicion es una pregunta juridica antes que tecnica, y no se responde aca.
