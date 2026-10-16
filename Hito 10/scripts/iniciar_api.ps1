# Prepara el entorno virtual (solo la primera vez) e inicia la API en http://127.0.0.1:8000.
# Uso: powershell -ExecutionPolicy Bypass -File .\scripts\iniciar_api.ps1 [-Puerto 8000]
param([int]$Puerto = 8000)
$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $raiz
if (-not (Test-Path -LiteralPath '.env')) { throw 'Falta .env. Copiar .env.example como .env y completar los secretos locales.' }
$py = Join-Path $raiz '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $py)) {
    python -m venv .venv
    & $py -m pip install --disable-pip-version-check -q -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }
}
# Solo localhost. --no-access-log: el middleware registra cada request con su X-Request-ID.
& $py -m uvicorn app.main:crear_app --factory --host 127.0.0.1 --port $Puerto --no-access-log
