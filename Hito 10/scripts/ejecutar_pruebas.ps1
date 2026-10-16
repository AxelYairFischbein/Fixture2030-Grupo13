<#
.SYNOPSIS
  Ejecuta todas las pruebas del Hito 10: unitarias, integración y la colección de Postman.

.DESCRIPTION
  1. pytest -m "not integration": unitarias con adaptadores falsos, sin Docker (incluye la
     comparación de openapi/openapi.yaml con app.openapi(), RNF2).
  2. pytest -m integration: contra los contenedores de los Hitos 4 a 9 (las que no encuentran
     su contenedor se informan como omitidas). Se salta con -SinIntegracion.
  3. Colección postman/fixture2030_collection.json con newman, si está instalado
     (npm install -g newman). Antes crea sesiones de prueba (crear_sesiones_prueba.ps1) y un
     acta temporal PAR-9xx para CU-19, levanta la API en segundo plano en -Puerto y, al
     terminar, detiene la API y borra el acta temporal. No corre la carpeta
     "Dependencias caídas (manual)". Se salta con -SinNewman.

  Los IDs de sesión quedan solo en .local/ (ignorado por git) y el log de la API en
  .local/api_pruebas.log. Termina con código distinto de 0 si alguna etapa falló.
  Ejecutar desde la carpeta "Hito 10":  .\scripts\ejecutar_pruebas.ps1 [-SinIntegracion] [-SinNewman] [-Puerto 8015]
#>
param(
    [switch]$SinIntegracion,
    [switch]$SinNewman,
    [ValidateRange(1, 65535)][int]$Puerto = 8015
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$local = Join-Path $raiz ".local"
$python = Join-Path $raiz ".venv\Scripts\python.exe"
$coleccion = Join-Path $raiz "postman\fixture2030_collection.json"
$entorno = Join-Path $local "postman_entorno_local.json"
$base = "http://127.0.0.1:$Puerto"
$carpetaManual = "Dependencias caídas (manual)"
Set-Location $raiz
New-Item -ItemType Directory -Force $local | Out-Null
if (-not (Test-Path $python)) { throw "Falta .venv: ejecutar .\scripts\iniciar_api.ps1 -Instalar" }

$resultados = [ordered]@{}

function Etapa([string]$nombre, [scriptblock]$bloque) {
    Write-Host ""
    Write-Host "=== $nombre ===" -ForegroundColor Cyan
    try {
        $codigo = & $bloque
        $resultados[$nombre] = if ($codigo -eq 0) { "pasó" } else { "falló (código $codigo)" }
    } catch {
        Write-Host $_.Exception.Message -ForegroundColor Red
        $resultados[$nombre] = "falló: $($_.Exception.Message)"
    }
}

function Python-Temporal([string[]]$argumentos) {
    $ErrorActionPreference = "Continue"
    $salida = & $python -m tests.integracion.iris_temporal @argumentos 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw "iris_temporal $($argumentos -join ' ') falló: $($salida -join ' ')" }
    return ($salida | Select-Object -Last 1).Trim()
}

function Esperar-Api {
    for ($i = 0; $i -lt 40; $i++) {
        # /salud puede tardar el timeout de una fuente caída.
        & curl.exe -s -o NUL --max-time 10 "$base/api/v1/salud"
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "La API no respondió en $base (ver .local/api_pruebas.log)"
}

# 1. Unitarias
Etapa "pytest unitarias" {
    & $python -m pytest -m "not integration" -q | Out-Host
    $LASTEXITCODE
}

# 2. Integración
if ($SinIntegracion) {
    $resultados["pytest integración"] = "omitida (-SinIntegracion)"
} else {
    Etapa "pytest integración" {
        & $python -m pytest -m integration -q -rs | Out-Host
        $LASTEXITCODE
    }
}

# 3. Colección de Postman con newman
$newman = Get-Command newman -ErrorAction SilentlyContinue
if ($SinNewman) {
    $resultados["newman"] = "omitida (-SinNewman)"
} elseif (-not $newman) {
    Write-Host ""
    Write-Host "newman no está instalado: la colección no se ejecutó." -ForegroundColor Yellow
    Write-Host "  Instalar con: npm install -g newman   (o importar la colección en Postman y usar el Runner)"
    $resultados["newman"] = "no ejecutada (newman no instalado)"
} else {
    Etapa "newman" {
        & (Join-Path $PSScriptRoot "crear_sesiones_prueba.ps1") -BaseUrl $base | Out-Host
        $logApi = Join-Path $local "api_pruebas.log"
        $api = Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "$Puerto" `
            -WorkingDirectory $raiz -RedirectStandardError $logApi -RedirectStandardOutput "$logApi.out" `
            -PassThru -WindowStyle Hidden
        $temporal = $null
        try {
            Esperar-Api
            try {
                $temporal = Python-Temporal @("crear")
                Write-Host "Acta temporal para CU-19: $temporal"
            } catch {
                Write-Host "No se pudo crear el acta temporal (¿IRIS arriba?): se omiten las transiciones reales de CU-19." -ForegroundColor Yellow
            }
            $carpetas = (Get-Content $coleccion -Raw -Encoding UTF8 | ConvertFrom-Json).item |
                ForEach-Object { $_.name } | Where-Object { $_ -ne $carpetaManual }
            $argumentos = @("run", $coleccion, "-e", $entorno, "--env-var", "baseUrl=$base")
            if ($temporal) { $argumentos += @("--env-var", "partidoTemporal=$temporal") }
            foreach ($c in $carpetas) { $argumentos += @("--folder", $c) }
            & newman @argumentos | Out-Host
            $LASTEXITCODE
        } finally {
            Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 300
            if (Test-Path "$logApi.out") {
                Get-Content "$logApi.out" | Add-Content $logApi -Encoding UTF8
                Remove-Item "$logApi.out"
            }
            if ($temporal) { Python-Temporal @("borrar", $temporal) | Out-Null }
        }
    }
}

Write-Host ""
Write-Host "=== Resumen ===" -ForegroundColor Cyan
$fallo = $false
foreach ($etapa in $resultados.Keys) {
    $estado = $resultados[$etapa]
    $color = if ($estado -eq "pasó") { "Green" } elseif ($estado -like "falló*") { "Red" } else { "Yellow" }
    if ($estado -like "falló*") { $fallo = $true }
    Write-Host ("  {0,-20} {1}" -f $etapa, $estado) -ForegroundColor $color
}
if ($fallo) { exit 1 }
exit 0
