<#
.SYNOPSIS
  Levanta la API del Hito 10 con uvicorn en http://127.0.0.1:<Puerto>.

.DESCRIPTION
  Comprueba el entorno virtual (.venv) y el archivo .env antes de arrancar. Con -Instalar
  crea el entorno virtual si no existe e instala requirements.txt. La API arranca aunque
  alguna base esté detenida: después verificar con .\scripts\verificar_conectividad.ps1.
  Detener con Ctrl+C (no afecta a los contenedores ni a sus datos).
  Ejecutar desde la carpeta "Hito 10":  .\scripts\iniciar_api.ps1 [-Puerto 8000] [-Recargar] [-Instalar]
#>
param(
    [ValidateRange(1, 65535)][int]$Puerto = 8000,
    [switch]$Recargar,
    [switch]$Instalar
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$python = Join-Path $raiz ".venv\Scripts\python.exe"
Set-Location $raiz

if (-not (Test-Path $python)) {
    if (-not $Instalar) {
        throw "Falta el entorno virtual .venv: ejecutar .\scripts\iniciar_api.ps1 -Instalar"
    }
    Write-Host "Creando el entorno virtual .venv con Python 3.13..."
    & python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear .venv (¿está instalado Python 3.13 como 'python'?)" }
}
if ($Instalar) {
    Write-Host "Instalando requirements.txt..."
    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "pip install falló" }
}

if (-not (Test-Path (Join-Path $raiz ".env"))) {
    throw "Falta Hito 10/.env: copiar .env.example a .env y completar usuarios y contraseñas locales."
}

$argumentos = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Puerto")
if ($Recargar) { $argumentos += "--reload" }
Write-Host "API en http://127.0.0.1:$Puerto  (Swagger UI: /docs · salud: /api/v1/salud) · Ctrl+C para detener"
& $python @argumentos
exit $LASTEXITCODE
