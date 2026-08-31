# coipo_aireadme

## Descripción
Generador automático de documentación técnica para repositorios de software.

## Estructura del proyecto
- `.github/`: Contiene flujos de trabajo de GitHub Actions.
- `readme3_analyzers.py`: Analizador de código para detectar tecnologías, dependencias y capacidades.
- `readme3_evidence.py`: Recolector y procesador de evidencia del repositorio.
- `readme3_scanner.py`: Escáner de archivos para extraer información.
- `readme3.py`: Punto de entrada principal del generador.
- `validate_readme.py`: Validador de README generados.
- `makeReadme.py`: Script para generar y validar README.
- `api.json`: Archivo de configuración de API.
- `.gitignore`: Archivo para ignorar archivos en Git.
- `.gitattributes`: Archivo de atributos de Git.

## Flujo de funcionamiento
El proyecto utiliza flujos de trabajo de GitHub Actions para generar automáticamente la documentación:
- `.github/workflows/generate-readme`
- `.github/workflows/generate-readme.yml`
- `.github/workflows/readme.yml`

## Despliegue
El despliegue se realiza mediante flujos de trabajo de GitHub Actions que automatizan la generación de documentación.
