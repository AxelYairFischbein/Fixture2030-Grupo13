<#
.SYNOPSIS
  Genera la evidencia de Neo4j (Fase 4: CU-05, CU-06, CU-07 y catálogo de partidos) en docs/evidencia/neo4j_*.

.DESCRIPTION
  1. Corre las pruebas de integración de Neo4j (pytest -m integration tests/integracion/test_neo4j.py)
     contra el contenedor del Hito 5 con la muestra cargada.
  2. Levanta la API con uvicorn y recorre la lista de control de la Fase 4 con curl.exe.
  3. Con -ConDetencion detiene Neo4j (docker compose stop en Hito 5), verifica 503 en CU-05,
     CU-06 y CU-07 y que CU-08 sigue respondiendo con el catálogo ya cargado (casos_de_uso.md
     §3.2), y siempre lo vuelve a levantar.
  4. Verifica que ni routes/ ni services/ importen neo4j y que ninguna respuesta de Neo4j
     incluya "estado" (el estado del partido pertenece a IRIS, §3.1).

  No lee ni imprime credenciales: la API las toma de Hito 10/.env.
  Ejecutar desde la carpeta "Hito 10":  .\scripts\evidencia_neo4j.ps1 [-ConDetencion]
#>
param(
    [int]$Puerto = 8016,
    [switch]$ConDetencion
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$evidencia = Join-Path $raiz "docs\evidencia"
$python = Join-Path $raiz ".venv\Scripts\python.exe"
$composeHito5 = Join-Path (Split-Path -Parent $raiz) "Hito 5\docker-compose.yml"
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
    return $salida
}

function Docker-Compose([string[]]$argumentos) {
    # En PowerShell 5.1 lo que docker escribe en stderr se vuelve un error terminante
    # con ErrorActionPreference=Stop: se relaja solo para esta llamada.
    $ErrorActionPreference = "Continue"
    $salida = & docker compose -f $composeHito5 @argumentos 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw "docker compose $($argumentos -join ' ') falló" }
    return $salida
}

function Esperar-Api {
    for ($i = 0; $i -lt 40; $i++) {
        & curl.exe -s -o NUL --max-time 5 "$base/api/v1/salud"
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "La API no respondió en $base"
}

function Esperar-Neo4j {
    $contenedor = Docker-Compose @("ps", "-aq", "neo4j") | Select-Object -Last 1
    for ($i = 0; $i -lt 90; $i++) {
        $estado = & docker inspect -f "{{.State.Health.Status}}" $contenedor
        if ($estado -eq "healthy") { return }
        Start-Sleep -Seconds 1
    }
    throw "Neo4j no volvió a estar healthy"
}

$marca = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$dia1 = "desde=2030-06-10T00:00:00Z&hasta=2030-06-11T00:00:00Z"

# 1. Pruebas de integración de Neo4j
$archivoPytest = "neo4j_pytest_integracion.txt"
Remove-Item (Join-Path $evidencia $archivoPytest) -ErrorAction SilentlyContinue
Escribir $archivoPytest @("# Neo4j (Fase 4) · pytest -m integration tests/integracion/test_neo4j.py", "# Generado: $marca", "")
$salidaPytest = & $python -m pytest -m integration tests/integracion/test_neo4j.py -v -rs -p no:cacheprovider 2>&1 | ForEach-Object { "$_" }
Escribir $archivoPytest $salidaPytest

# 2. Lista de control con la API levantada
$archivoControl = "neo4j_lista_de_control.txt"
$logApi = Join-Path $evidencia "neo4j_api.log"
Remove-Item (Join-Path $evidencia $archivoControl), $logApi -ErrorAction SilentlyContinue
Escribir $archivoControl @(
    "# Neo4j (Fase 4) · Lista de control (plan_de_implementacion.md)",
    "# Generado: $marca · API en $base · respuestas crudas de curl.exe -i"
)

$respuestasNeo4j = @()
$api = Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "$Puerto" `
    -WorkingDirectory $raiz -RedirectStandardError $logApi -RedirectStandardOutput "$logApi.out" `
    -PassThru -WindowStyle Hidden
try {
    Esperar-Api
    Pedir $archivoControl "Salud con Neo4j arriba -> catálogo cargado con 64 partidos" "/api/v1/salud" | Out-Null
    $respuestasNeo4j += Pedir $archivoControl "CU-05 · EQ-001 -> PAR-001 y PAR-033 (Q04/Q06), sin estado" "/api/v1/equipos/EQ-001/partidos"
    Pedir $archivoControl "CU-05 · EQ-999 -> 404 EQUIPO_NO_ENCONTRADO" "/api/v1/equipos/EQ-999/partidos" | Out-Null
    Pedir $archivoControl "CU-05 · EQ-1 -> 400 VALIDACION (sin consultar Neo4j)" "/api/v1/equipos/EQ-1/partidos" | Out-Null
    $respuestasNeo4j += Pedir $archivoControl "CU-06 · PAR-001 -> 2 eventos con 4 participantes (Q07)" "/api/v1/partidos/PAR-001/eventos"
    Pedir $archivoControl "CU-06 · PAR-001 limite=1 -> 1 evento con sus 2 participantes" "/api/v1/partidos/PAR-001/eventos?limite=1" | Out-Null
    Pedir $archivoControl "CU-06 · PAR-999 -> 404 PARTIDO_NO_ENCONTRADO" "/api/v1/partidos/PAR-999/eventos" | Out-Null
    $respuestasNeo4j += Pedir $archivoControl "CU-07 · 2030-06-10 -> PAR-001…PAR-008 (Q09), sin estado" "/api/v1/partidos?$dia1"
    Pedir $archivoControl "CU-07 · estadioId=EST-99 -> 200 items [] (vacío válido)" "/api/v1/partidos?$dia1&estadioId=EST-99" | Out-Null
    Pedir $archivoControl "CU-07 · intervalo invertido -> 400 VALIDACION (sin consultar Neo4j)" "/api/v1/partidos?desde=2030-06-11T00:00:00Z&hasta=2030-06-10T00:00:00Z" | Out-Null
    Pedir $archivoControl "CU-07 · fecha sin zona -> 400 VALIDACION" "/api/v1/partidos?desde=2030-06-10T00:00:00&hasta=2030-06-11T00:00:00Z" | Out-Null

    if ($ConDetencion) {
        Escribir $archivoControl @("", "## Neo4j detenido (docker compose stop neo4j en Hito 5)")
        try {
            Docker-Compose @("stop", "neo4j") | Out-Null
            Pedir $archivoControl "CU-05 con Neo4j detenido -> 503, nunca 200 vacío" "/api/v1/equipos/EQ-001/partidos" | Out-Null
            Pedir $archivoControl "CU-06 con Neo4j detenido -> 503" "/api/v1/partidos/PAR-001/eventos" | Out-Null
            Pedir $archivoControl "CU-07 con Neo4j detenido -> 503" "/api/v1/partidos?$dia1" | Out-Null
            Pedir $archivoControl "CU-08 con Neo4j detenido -> 200: usa el catálogo ya cargado (§3.2)" "/api/v1/partidos/PAR-001/comentarios?minuto=2030-06-10T18:01:00Z" | Out-Null
            Pedir $archivoControl "Salud con Neo4j detenido -> neo4j no_disponible, catálogo sigue cargado" "/api/v1/salud" | Out-Null
        } finally {
            Docker-Compose @("start", "neo4j") | Out-Null
            Esperar-Neo4j
        }
        Pedir $archivoControl "CU-05 después de volver a levantar Neo4j -> 200 (el driver reconecta)" "/api/v1/equipos/EQ-001/partidos" | Out-Null
    }
} finally {
    Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 300
    if (Test-Path "$logApi.out") {
        Get-Content "$logApi.out" | Add-Content $logApi -Encoding UTF8
        Remove-Item "$logApi.out"
    }
}

# 3. Las respuestas de Neo4j no proyectan estado (§3.1)
$conEstado = $respuestasNeo4j | Select-String -Pattern '"estado"\s*:'
Escribir $archivoControl @("", "### Las respuestas de CU-05, CU-06 y CU-07 no incluyen el campo estado")
if ($conEstado) {
    Escribir $archivoControl ($conEstado | ForEach-Object { $_.Line })
} else {
    Escribir $archivoControl "Sin coincidencias de '`"estado`":' en las respuestas 200 de CU-05, CU-06 y CU-07."
}

# 4. Las rutas y servicios no importan el driver
$coincidencias = Select-String -Path "app\routes\*.py", "app\services\*.py" -Pattern "^\s*(from|import)\s+neo4j"
Escribir $archivoControl @("", "### Ningún archivo de app/routes ni app/services importa neo4j")
if ($coincidencias) {
    Escribir $archivoControl ($coincidencias | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line)" })
} else {
    Escribir $archivoControl "Sin coincidencias de 'import neo4j' / 'from neo4j' en app/routes ni app/services."
}

Write-Host "Evidencia generada en $evidencia"
