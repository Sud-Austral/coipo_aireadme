<!-- AI:BEGIN id=readme sha=53c974e0503b -->
# coipo_aireadme

## Stack técnico
- Python
- YAML
- Markdown
- JSON
- Text

## Estructura del proyecto
El proyecto contiene 45 archivos organizados en:
- `tests/` (7 archivos)
- `.github/` (5 archivos, incluyendo workflows)
- `fleet/` (2 archivos)
- Múltiples scripts Python para procesamiento de READMEs y análisis de repositorios

## Requisitos
- Python
- Dependencias (requirements.txt):
  - requests==2.32.3
  - PyYAML==6.0.2
  - pytest==8.3.4

## Configuración
- Variable de entorno: `AIREADME_IGNORE_PATHS`
- Archivo de configuración de ejemplo: `.aireadme.yml.example`

## Pruebas
El proyecto utiliza pytest para pruebas unitarias. Los archivos de prueba se encuentran en el directorio `tests/`.

## Despliegue
El proyecto utiliza GitHub Actions para CI/CD con los siguientes workflows:
- `.github/workflows/ci.yml`
- `.github/workflows/fleet-census.yml`
- `.github/workflows/fleet-sweep.yml`
- `.github/workflows/generate-readme.yml`
- `.github/workflows/readme.yml`
<!-- AI:END id=readme -->
