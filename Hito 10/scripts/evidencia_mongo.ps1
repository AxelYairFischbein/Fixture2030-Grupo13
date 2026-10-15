<#
.SYNOPSIS
  Genera la evidencia de MongoDB (Fase 2: CU-01 a CU-04) en docs/evidencia/mongo_*.

.DESCRIPTION
  1. Corre las pruebas de integración (pytest -m integration) contra el contenedor del Hito 4.
  2. Levanta la API con uvicorn y recorre la lista de control de la Fase 2 con curl.exe.
  3. Con -ConDetencion detiene MongoDB (docker compose stop en Hito 4), verifica 503 y
     salud "no_disponible" y siempre vuelve a levantarlo, aunque algo falle en el medio.
  4. Verifica que ni routes/ ni services/ importen pymongo.

  No lee ni imprime credenciales: la API las toma de Hito 10/.env.
  Ejecutar desde la carpeta "Hito 10":  .\scripts\evidencia_mongo.ps1 [-ConDetencion]
  Convención de nombres: un script y un prefijo por fuente (mongo_, redis_, neo4j_,
  cassandra_, influx_, iris_).
#>
param(
    [int]$Puerto = 8010,
    [switch]$ConDetencion
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$evidencia = Join-Path $raiz "docs\evidencia"
$python = Join-Path $raiz ".venv\Scripts\python.exe"
$composeHito4 = Join-Path (Split-Path -Parent $raiz) "Hito 4\docker-compose.yml"
$base = "http://127.0.0.1:$Puerto"
New-Item -ItemType Directory -Force $evidencia | Out-Null
Set-Location $raiz

function Escribir([string]$archivo, [string[]]$lineas) {
    $lineas | Out-File -FilePath (Join-Path $evidencia $archivo) -Encoding utf8 -Append
}

function Pedir([string]$archivo, [string]$titulo, [string]$ruta) {
    Escribir $archivo @("", "### $titulo", "GET $ruta")
    $salida = & curl.exe -s -i --max-time 15 -w "`n(tiempo_total_s=%{time_total})" "$base$ruta"
    Escribir $archivo $salida
}

function Docker-Compose([string]$accion) {
    # En PowerShell 5.1 el progreso que docker escribe en stderr se vuelve un error
    # terminante con ErrorActionPreference=Stop: se relaja solo para esta llamada.
    $ErrorActionPreference = "Continue"
    & docker compose -f $composeHito4 $accion mongodb 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "docker compose $accion mongodb falló" }
}

function Esperar-Api {
    for ($i = 0; $i -lt 40; $i++) {
        & curl.exe -s -o NUL --max-time 2 "$base/api/v1/salud"
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "La API no respondió en $base"
}

function Esperar-Mongo {
    for ($i = 0; $i -lt 60; $i++) {
        $estado = & docker inspect -f "{{.State.Health.Status}}" fixture2030-mongodb
        if ($estado -eq "healthy") { return }
        Start-Sleep -Seconds 1
    }
    throw "MongoDB no volvió a estar healthy"
}

$marca = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

# 1. Pruebas de integración
$archivoPytest = "mongo_pytest_integracion.txt"
Remove-Item (Join-Path $evidencia $archivoPytest) -ErrorAction SilentlyContinue
Escribir $archivoPytest @("# MongoDB (Fase 2) · pytest -m integration", "# Generado: $marca", "")
$salidaPytest = & $python -m pytest -m integration -v -rs -p no:cacheprovider 2>&1 | ForEach-Object { "$_" }
Escribir $archivoPytest $salidaPytest

# 2. Lista de control con la API levantada
$archivoControl = "mongo_lista_de_control.txt"
$logApi = Join-Path $evidencia "mongo_api.log"
Remove-Item (Join-Path $evidencia $archivoControl), $logApi -ErrorAction SilentlyContinue
Escribir $archivoControl @(
    "# MongoDB (Fase 2) · Lista de control (plan_de_implementacion.md)",
    "# Generado: $marca · API en $base · respuestas crudas de curl.exe -i"
)

$api = Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "$Puerto" `
    -WorkingDirectory $raiz -RedirectStandardError $logApi -RedirectStandardOutput "$logApi.out" `
    -PassThru -WindowStyle Hidden
try {
    Esperar-Api
    Pedir $archivoControl "Salud con MongoDB arriba" "/api/v1/salud"
    Pedir $archivoControl "CU-01 · EQ-001 -> 200" "/api/v1/equipos/EQ-001"
    Pedir $archivoControl "CU-01 · EQ-999 -> 404 EQUIPO_NO_ENCONTRADO" "/api/v1/equipos/EQ-999"
    Pedir $archivoControl "CU-01 · EQ-1 -> 400 VALIDACION" "/api/v1/equipos/EQ-1"
    Pedir $archivoControl "CU-02 · CONMEBOL rankingMax=50 -> 8 equipos (Q03)" "/api/v1/equipos?confederacion=CONMEBOL&rankingMax=50"
    Pedir $archivoControl "CU-02 · confederación fuera del enum -> 400" "/api/v1/equipos?confederacion=FIFA"
    Pedir $archivoControl "CU-03 · EQ-002 -> 24 jugadores (Q07)" "/api/v1/equipos/EQ-002/jugadores"
    Pedir $archivoControl "CU-03 · EQ-001 limite=5 pagina=2 -> JUG-0006..JUG-0010 (Q06)" "/api/v1/equipos/EQ-001/jugadores?limite=5&pagina=2"
    Pedir $archivoControl "CU-03 · EQ-999 -> 404 (no plantel vacío)" "/api/v1/equipos/EQ-999/jugadores"
    Pedir $archivoControl "CU-04 · JUG-0313 -> 200" "/api/v1/jugadores/JUG-0313"
    Pedir $archivoControl "CU-04 · JUG-9999 -> 404 JUGADOR_NO_ENCONTRADO" "/api/v1/jugadores/JUG-9999"

    if ($ConDetencion) {
        Escribir $archivoControl @("", "## MongoDB detenido (docker compose stop mongodb en Hito 4)")
        try {
            Docker-Compose "stop"
            Pedir $archivoControl "CU-01 con MongoDB detenido -> 503 en menos de ~3 s" "/api/v1/equipos/EQ-001"
            Pedir $archivoControl "CU-03 con MongoDB detenido -> 503, nunca 200 vacío" "/api/v1/equipos/EQ-002/jugadores"
            Pedir $archivoControl "Salud con MongoDB detenido -> 200 degradado" "/api/v1/salud"
        } finally {
            Docker-Compose "start"
            Esperar-Mongo
        }
        Pedir $archivoControl "CU-01 después de volver a levantar MongoDB -> 200" "/api/v1/equipos/EQ-001"
    }
} finally {
    Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
    if (Test-Path "$logApi.out") {
        Get-Content "$logApi.out" | Add-Content $logApi
        Remove-Item "$logApi.out"
    }
}

# 3. Las rutas y servicios no importan el driver
$coincidencias = Select-String -Path "app\routes\*.py", "app\services\*.py" -Pattern "pymongo|bson"
Escribir $archivoControl @("", "### Ningún archivo de app/routes ni app/services importa pymongo")
if ($coincidencias) {
    Escribir $archivoControl ($coincidencias | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line)" })
} else {
    Escribir $archivoControl "Sin coincidencias de 'pymongo|bson' en app/routes ni app/services."
}

Write-Host "Evidencia generada en $evidencia"
