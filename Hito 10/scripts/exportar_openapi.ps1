<#
.SYNOPSIS
  Exporta el contrato OpenAPI de la API a openapi/openapi.yaml (RNF2).

.DESCRIPTION
  Ejecuta scripts/exportar_openapi.py con el Python del entorno virtual. El contrato se
  genera desde app.openapi() con valores ficticios de configuración: no lee .env ni
  secretos y no se conecta a ninguna base. Con -Verificar no escribe nada y termina con
  código 1 si el archivo versionado difiere (lo mismo comprueba tests/test_openapi.py).
  Ejecutar desde la carpeta "Hito 10":  .\scripts\exportar_openapi.ps1 [-Verificar]
#>
param([switch]$Verificar)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$python = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Falta el entorno virtual: ejecutar .\scripts\iniciar_api.ps1 -Instalar"
}
$argumentos = @((Join-Path $PSScriptRoot "exportar_openapi.py"))
if ($Verificar) { $argumentos += "--verificar" }
& $python @argumentos
exit $LASTEXITCODE
