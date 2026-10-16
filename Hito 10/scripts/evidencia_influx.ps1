<#
.SYNOPSIS
  Genera la evidencia de InfluxDB (Fase 6: CU-15, CU-16 y CU-17) en docs/evidencia/influx_*.

.DESCRIPTION
  1. Corre las pruebas de integración de InfluxDB (pytest -m integration tests/integracion/test_influx.py)
     contra el contenedor del Hito 8 con la carga de muestra.
  2. Levanta la API con uvicorn y recorre la lista de control de la Fase 6 con curl.exe sobre la
     ventana de la carga (Hito 8/datos/muestra.json: [fin - 300 s, fin)), que no es del calendario
     2030 sino de la fecha en que se cargaron los puntos.
  3. Con -ConDetencion detiene InfluxDB (docker compose stop en Hito 8), verifica 503 (nunca 200
     vacío) y siempre lo vuelve a levantar.
  4. Verifica que ni routes/ ni services/ importen httpx y que el token no aparezca en la
     evidencia ni en git diff.

  El token se lee solo para buscarlo en la evidencia: nunca se imprime ni se escribe.
  La API toma la ruta del token de Hito 10/.env (INFLUX_TOKEN_FILE).
  Ejecutar desde la carpeta "Hito 10":  .\scripts\evidencia_influx.ps1 [-ConDetencion]
#>
param(
    [int]$Puerto = 8013,
    [switch]$ConDetencion
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$hito8 = Join-Path (Split-Path -Parent $raiz) "Hito 8"
$evidencia = Join-Path $raiz "docs\evidencia"
$python = Join-Path $raiz ".venv\Scripts\python.exe"
$composeHito8 = Join-Path $hito8 "docker-compose.yml"
$base = "http://127.0.0.1:$Puerto"
New-Item -ItemType Directory -Force $evidencia | Out-Null
Set-Location $raiz

function Escribir([string]$archivo, [string[]]$lineas) {
    $lineas | Out-File -FilePath (Join-Path $evidencia $archivo) -Encoding utf8 -Append
}

function Pedir {
    param([string]$Archivo, [string]$Titulo, [string]$Ruta)
    Escribir $Archivo @("", "### $Titulo", "GET $Ruta")
    $salida = & curl.exe -s -i --max-time 15 -w "`n(tiempo_total_s=%{time_total})" "$base$Ruta"
    Escribir $Archivo $salida
    return $salida
}

function Docker-Compose([string[]]$argumentos) {
    # En PowerShell 5.1 lo que docker escribe en stderr se vuelve un error terminante
    # con ErrorActionPreference=Stop: se relaja solo para esta llamada.
    $ErrorActionPreference = "Continue"
    $salida = & docker compose -f $composeHito8 @argumentos 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw "docker compose $($argumentos -join ' ') falló" }
    return $salida
}

function Esperar-Api {
    for ($i = 0; $i -lt 40; $i++) {
        # /salud puede tardar el timeout de una fuente caída (MongoDB: 2 s).
        & curl.exe -s -o NUL --max-time 5 "$base/api/v1/salud"
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "La API no respondió en $base"
}

function Iso([long]$segundos) {
    return [DateTimeOffset]::FromUnixTimeSeconds($segundos).UtcDateTime.ToString("yyyy-MM-ddTHH:mm:ssZ")
}

$marca = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$muestra = Get-Content (Join-Path $hito8 "datos\muestra.json") -Raw | ConvertFrom-Json
$desde = Iso ($muestra.fin - 300)
$hasta = Iso $muestra.fin
$ventana = "desde=$desde&hasta=$hasta"

# 1. Pruebas de integración de InfluxDB
$archivoPytest = "influx_pytest_integracion.txt"
Remove-Item (Join-Path $evidencia $archivoPytest) -ErrorAction SilentlyContinue
Escribir $archivoPytest @("# InfluxDB (Fase 6) · pytest -m integration tests/integracion/test_influx.py", "# Generado: $marca", "")
$salidaPytest = & $python -m pytest -m integration tests/integracion/test_influx.py -v -rs -p no:cacheprovider 2>&1 | ForEach-Object { "$_" }
Escribir $archivoPytest $salidaPytest

# 2. Lista de control con la API levantada
$archivoControl = "influx_lista_de_control.txt"
$logApi = Join-Path $evidencia "influx_api.log"
Remove-Item (Join-Path $evidencia $archivoControl), $logApi -ErrorAction SilentlyContinue
Escribir $archivoControl @(
    "# InfluxDB (Fase 6) · Lista de control (plan_de_implementacion.md)",
    "# Generado: $marca · API en $base · respuestas crudas de curl.exe -i",
    "# Ventana de la carga de muestra (Hito 8/datos/muestra.json, fin - 300 s): [$desde, $hasta)"
)

$api = Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "$Puerto" `
    -WorkingDirectory $raiz -RedirectStandardError "$logApi.err" -RedirectStandardOutput "$logApi.out" `
    -PassThru -WindowStyle Hidden
try {
    Esperar-Api
    $comparacion = "/api/v1/partidos/PAR-001/estadisticas/comparacion?$ventana"
    $evolucion = "/api/v1/partidos/PAR-001/estadisticas/evolucion?$ventana"
    $recientes = "/api/v1/partidos/PAR-001/equipos/EQ-001/estadisticas/recientes?hasta=$hasta"

    Pedir $archivoControl "Salud con InfluxDB arriba" "/api/v1/salud" | Out-Null
    Pedir $archivoControl "CU-16 · PAR-001 -> EQ-001 300 muestras, 49.975, 30 pases, 1 tiro; EQ-002 300, 50.025, 25, 1; 0 inválidos" $comparacion | Out-Null
    Pedir $archivoControl "CU-17 · 1m -> 5 intervalos por equipo; las sumas coinciden con CU-16 (30 y 25 pases)" $evolucion | Out-Null
    Pedir $archivoControl "CU-17 · 5m solo EQ-002 -> bins de 5 min UTC (cortados por la ventana), mismos totales" "$evolucion&resolucion=5m&equipoId=EQ-002" | Out-Null
    Pedir $archivoControl "CU-15 · EQ-001 -> 5 observaciones en orden descendente y ultimaObservacion" $recientes | Out-Null
    Pedir $archivoControl "CU-15 · ventana sin puntos (hasta = ahora) -> 200 items [] y ultimaObservacion null" "/api/v1/partidos/PAR-001/equipos/EQ-001/estadisticas/recientes" | Out-Null
    Pedir $archivoControl "CU-16 · desde > hasta -> 400 VALIDACION (sin consultar)" "/api/v1/partidos/PAR-001/estadisticas/comparacion?desde=$hasta&hasta=$desde" | Out-Null
    Pedir $archivoControl "CU-16 · ventana de 6 min -> 400 VALIDACION" "/api/v1/partidos/PAR-001/estadisticas/comparacion?desde=$(Iso ($muestra.fin - 360))&hasta=$hasta" | Out-Null
    Pedir $archivoControl "CU-17 · ventana de 3 h -> 400 VALIDACION" "/api/v1/partidos/PAR-001/estadisticas/evolucion?desde=$(Iso ($muestra.fin - 10800))&hasta=$hasta" | Out-Null
    Pedir $archivoControl "CU-17 · resolucion=10m -> 400 VALIDACION" "$evolucion&resolucion=10m" | Out-Null
    Pedir $archivoControl "CU-16 · fecha sin zona -> 400 VALIDACION" "/api/v1/partidos/PAR-001/estadisticas/comparacion?desde=$($desde.TrimEnd('Z'))&hasta=$hasta" | Out-Null
    Pedir $archivoControl "CU-16 · PAR-999 -> 404 PARTIDO_NO_ENCONTRADO (catálogo, sin consultar InfluxDB)" "/api/v1/partidos/PAR-999/estadisticas/comparacion?$ventana" | Out-Null
    Pedir $archivoControl "CU-15 · EQ-003 no disputa PAR-001 -> 404 EQUIPO_NO_PARTICIPA" "/api/v1/partidos/PAR-001/equipos/EQ-003/estadisticas/recientes?hasta=$hasta" | Out-Null
    Pedir $archivoControl "CU-16 · PAR-003 existe y no tiene puntos -> 200 equipos []" "/api/v1/partidos/PAR-003/estadisticas/comparacion?$ventana" | Out-Null

    if ($ConDetencion) {
        Escribir $archivoControl @("", "## InfluxDB detenido (docker compose stop influxdb en Hito 8)")
        try {
            Docker-Compose @("stop", "influxdb") | Out-Null
            Pedir $archivoControl "CU-16 con InfluxDB detenido -> 503, nunca 200 vacío" $comparacion | Out-Null
            Pedir $archivoControl "CU-15 con InfluxDB detenido -> 503" $recientes | Out-Null
            Pedir $archivoControl "Salud con InfluxDB detenido -> 200 degradado" "/api/v1/salud" | Out-Null
        } finally {
            Docker-Compose @("start", "influxdb") | Out-Null
        }
        for ($i = 0; $i -lt 30; $i++) {
            $codigo = & curl.exe -s -o NUL -w "%{http_code}" --max-time 5 "$base$comparacion"
            if ($codigo -eq "200") { break }
            Start-Sleep -Seconds 2
        }
        Pedir $archivoControl "CU-16 después de volver a levantar InfluxDB -> 200" $comparacion | Out-Null
    }
} finally {
    Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 300
    foreach ($parcial in "$logApi.err", "$logApi.out") {
        if (Test-Path $parcial) {
            Get-Content $parcial | Add-Content $logApi -Encoding UTF8
            Remove-Item $parcial
        }
    }
}

# 3. Las rutas y servicios no importan el cliente HTTP de InfluxDB
$coincidencias = Select-String -Path "app\routes\*.py", "app\services\*.py" -Pattern "^\s*(from|import)\s+httpx"
Escribir $archivoControl @("", "### Ningún archivo de app/routes ni app/services importa httpx")
if ($coincidencias) {
    Escribir $archivoControl ($coincidencias | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line)" })
} else {
    Escribir $archivoControl "Sin coincidencias de 'import httpx' / 'from httpx' en app/routes ni app/services."
}

# 4. El token no aparece en la evidencia, en los tests ni en git diff
$token = (Get-Content (Join-Path $hito8 ".local\admin.token") -Raw).Trim()
$enArchivos = Select-String -Path (Join-Path $evidencia "influx_*"), "tests\*.py", "tests\integracion\*.py", "app\*.py", "app\*\*.py" -SimpleMatch -Pattern $token -Quiet
$ErrorActionPreference = "Continue"
$diff = (& git diff HEAD -- . 2>$null) -join "`n"
$ErrorActionPreference = "Stop"
$enDiff = $diff.Contains($token)
$token = $null
Escribir $archivoControl @("", "### El token de InfluxDB no aparece en docs/evidencia/influx_*, tests/, app/ ni git diff")
if ($enArchivos -or $enDiff) { throw "El token de InfluxDB aparece en la evidencia, el código o git diff: revisar antes de versionar." }
Escribir $archivoControl "Sin coincidencias."

Write-Host "Evidencia generada en $evidencia"
