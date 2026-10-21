# Ejecuta las pruebas. -SoloUnitarias no necesita ninguna base de datos.
# Uso: powershell -ExecutionPolicy Bypass -File .\scripts\ejecutar_pruebas.ps1 [-SoloUnitarias]
param([switch]$SoloUnitarias)
$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $raiz
$py = Join-Path $raiz '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $py)) { throw 'Falta .venv: ejecutar primero scripts\iniciar_api.ps1 o crear el entorno.' }

& $py scripts\exportar_openapi.py
if ($SoloUnitarias) {
    & $py -m pytest tests\unit -v -p no:cacheprovider
    exit $LASTEXITCODE
}
& $py scripts\verificar_conectividad.py
if ($LASTEXITCODE -ne 0) { throw 'Hay fuentes no disponibles. Revisar los contenedores antes de las pruebas de integración.' }
& $py -m pytest tests -v -p no:cacheprovider
exit $LASTEXITCODE
