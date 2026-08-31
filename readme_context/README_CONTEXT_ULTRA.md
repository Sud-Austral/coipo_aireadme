# PROJECT EVIDENCE CONTEXT
PROJECT=target
FILES=13
GENERATED=2026-08-31T02:06:06.904423

## EVIDENCE_POLICY

This context contains repository evidence.
Signals are not guaranteed business features.
Do not infer unsupported functionality.
Prefer explicit files, dependencies and source evidence.
If evidence is insufficient, omit the claim.

## STACK
LANG=Python,YAML,JSON,Markdown
TECH=Angular[low],Django[low],Docker[medium],Express[low],FastAPI[low],Flask[low],Leaflet[low],Mapbox[low],MongoDB[low],MySQL[low],Node.js[low],NumPy[low],OpenCV[low],Pandas[low],PostgreSQL[low],React[medium],Redis[low],SQLAlchemy[low],SQLite[low],Tailwind[low],Vite[medium],Vue[low],YOLO[low]

## STRUCTURE
ROOTS=.github(3),readme3_analyzers.py(1),.gitignore(1),readme3_evidence.py(1),api.json(1),.gitattributes(1),readme3_scanner.py(1),README.md(1),readme3.py(1),validate_readme.py(1),makeReadme.py(1)

## KEY_FILES
README.md,.github/workflows/generate-readme,.github/workflows/generate-readme.yml,.github/workflows/readme.yml,api.json

## CAPABILITY_SIGNALS
Autenticación [confidence=medium]
  login [readme3_analyzers.py:883]
  logout [readme3_analyzers.py:884]
  auth [readme3_analyzers.py:885]
  jwt [readme3_analyzers.py:886]
  token [readme3_analyzers.py:887]
  authenticate [readme3_analyzers.py:888]
  login [readme3_evidence.py:128]
  auth [readme3_evidence.py:127]
Mapas / cartografía [confidence=low]
  leaflet [readme3_analyzers.py:588]
  mapbox [readme3_analyzers.py:591]
  cartografia [readme3_analyzers.py:893]
  mapa [readme3_analyzers.py:890]
  leaflet [validate_readme.py:407]
  mapbox [validate_readme.py:408]
Exportación [confidence=low]
  export [readme3_analyzers.py:193]
  exportar [readme3_analyzers.py:898]
  csv [readme3_analyzers.py:899]
  xlsx [readme3_analyzers.py:900]
  excel [readme3_analyzers.py:901]
Carga de archivos [confidence=medium]
  upload [readme3_analyzers.py:904]
  archivo [readme3_analyzers.py:756]
  file [readme3_analyzers.py:9]
  document [readme3_analyzers.py:907]
  archivo [readme3_evidence.py:26]
  file [readme3_evidence.py:8]
  document [readme3_evidence.py:886]
  archivo [readme3_scanner.py:13]
Reportes / analítica [confidence=low]
  report [readme3_analyzers.py:909]
  reporte [readme3_analyzers.py:909]
  dashboard [readme3_analyzers.py:912]
  analytics [readme3_analyzers.py:913]
  estadistica [readme3_analyzers.py:914]
Procesamiento de datos [confidence=medium]
  pandas [readme3_analyzers.py:597]
  numpy [readme3_analyzers.py:600]
  dataframe [readme3_analyzers.py:919]
  etl [readme3_analyzers.py:920]
  etl [readme3_evidence.py:806]
  pandas [validate_readme.py:410]
  numpy [validate_readme.py:411]
IA / Machine Learning [confidence=low]
  tensorflow [readme3_analyzers.py:923]
  pytorch [readme3_analyzers.py:924]
  torch [readme3_analyzers.py:924]
  yolo [readme3_analyzers.py:607]
  machine learning [readme3_analyzers.py:922]
  yolo [validate_readme.py:413]

## PYTHON
readme3_analyzers.py|F=analyze_python,analyze_js,analyze_sql,analyze_package_json,analyze_requirements,detect_technologies,dependencies,analyze_files,detect_env_vars,detect_capabilities|I=__future__,ast,json,re,pathlib,readme3_scanner
readme3_evidence.py|F=existing_readme,summarize_existing_readme,important_files,structure,collect_api,collect_tables,generate_context,build_evidence_json|I=__future__,collections,datetime,pathlib,readme3_scanner,readme3_analyzers
readme3_scanner.py|F=read_text,rel_path,language,add_unique,evidence_item,line_number,scan|I=__future__,os,pathlib
readme3.py|F=main|I=__future__,json,sys,datetime,pathlib,readme3_scanner,readme3_analyzers,readme3_evidence
validate_readme.py|F=load_json,get_evidence_environment_variables,get_evidence_endpoints,get_evidence_technologies,get_evidence_tables,get_evidence_commands,extract_env_variables,extract_endpoints,extract_technologies,extract_table_mentions,extract_commands,validate,main|I=__future__,json,re,sys,pathlib
makeReadme.py|F=error,run_command,load_api,run_readme3,get_context_files,get_existing_readme,limit_context,create_generation_prompt,call_zai,clean_response,save_candidate,validate_readme,create_repair_prompt,save_final,main|I=json,subprocess,sys,pathlib,requests

## EXISTING_README
# coipo_aireadme

## DEPLOYMENT_FILES
.github/workflows/generate-readme,.github/workflows/generate-readme.yml,.github/workflows/readme.yml

## README_RULES

Generate README.md only from repository evidence.
Do not invent features.
Do not invent technologies.
Do not invent endpoints.
Do not invent database tables.
Do not invent environment variables.
Do not invent commands.
Do not infer production architecture from filenames alone.
Treat capability signals as signals, not confirmed features.
Prefer explicit source evidence.
Omit unsupported sections.