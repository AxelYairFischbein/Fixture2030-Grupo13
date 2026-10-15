<#
.SYNOPSIS
  Genera la evidencia de Redis (Fase 3: CU-11 a CU-14 y caché de CU-01) en docs/evidencia/redis_*.

.DESCRIPTION
  1. Corre las pruebas de integración de Redis (pytest -m integration -k redis) contra el
     contenedor del Hito 7 y el MongoDB del Hito 4.
  2. Crea sesiones de prueba con crear_sesiones_prueba.ps1 (IDs aleatorios en .local/).
  3. Levanta la API con uvicorn y recorre la lista de control de la Fase 3 con curl.exe.
  4. Con -ConDetencion detiene Redis (docker compose stop en Hito 7), verifica BYPASS en
     CU-01 y 503 (no 401) en sesiones, y siempre lo vuelve a levantar.
  5. Verifica que ni routes/ ni services/ importen redis.

  Los IDs de sesión son credenciales: todo lo que se escribe en docs/evidencia pasa por
  Enmascarar (SES-PRUEBA-3f9a…) y al final se comprueba que no quedó ningún ID completo.
  No lee ni imprime credenciales: la API las toma de Hito 10/.env.
  Ejecutar desde la carpeta "Hito 10":  .\scripts\evidencia_redis.ps1 [-ConDetencion]
#>
param(
    [int]$Puerto = 8011,
    [switch]$ConDetencion
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$evidencia = Join-Path $raiz "docs\evidencia"
$python = Join-Path $raiz ".venv\Scripts\python.exe"
$composeHito7 = Join-Path (Split-Path -Parent $raiz) "Hito 7\docker-compose.yml"
$base = "http://127.0.0.1:$Puerto"
$prefijo = "fixture2030:h7:demo:"
$patronId = 'SES-PRUEBA-([0-9a-f]{4})[0-9a-f]{28}'
New-Item -ItemType Directory -Force $evidencia | Out-Null
Set-Location $raiz

function Enmascarar([string[]]$lineas) {
    return $lineas | ForEach-Object { "$_" -replace $patronId, 'SES-PRUEBA-$1…' }
}

function Escribir([string]$archivo, [string[]]$lineas) {
    Enmascarar $lineas | Out-File -FilePath (Join-Path $evidencia $archivo) -Encoding utf8 -Append
}

function Pedir([string]$archivo, [string]$titulo, [string]$metodo, [string]$ruta, [string]$sesion = "") {
    $argumentos = @("-s", "-i", "--max-time", "15", "-X", $metodo, "-w", "`n(tiempo_total_s=%{time_total})")
    $descripcion = "$metodo $ruta"
    if ($sesion) {
        $argumentos += @("-H", "X-Session-Id: $sesion")
        $descripcion += "  [X-Session-Id: $sesion]"
    }
    Escribir $archivo @("", "### $titulo", $descripcion)
    $salida = & curl.exe @argumentos "$base$ruta"
    Escribir $archivo $salida
}

function Docker-Compose([string[]]$argumentos) {
    # En PowerShell 5.1 lo que docker escribe en stderr se vuelve un error terminante
    # con ErrorActionPreference=Stop: se relaja solo para esta llamada.
    $ErrorActionPreference = "Continue"
    $salida = & docker compose -f $composeHito7 @argumentos 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw "docker compose $($argumentos -join ' ') falló" }
    return $salida
}

function Esperar-Api {
    for ($i = 0; $i -lt 40; $i++) {
        & curl.exe -s -o NUL --max-time 2 "$base/api/v1/salud"
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "La API no respondió en $base"
}

function Esperar-Redis {
    $contenedor = Docker-Compose @("ps", "-q", "redis") | Select-Object -Last 1
    for ($i = 0; $i -lt 60; $i++) {
        $estado = & docker inspect -f "{{.State.Health.Status}}" $contenedor
        if ($estado -eq "healthy") { return }
        Start-Sleep -Seconds 1
    }
    throw "Redis no volvió a estar healthy"
}

$marca = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

# 1. Pruebas de integración de Redis
$archivoPytest = "redis_pytest_integracion.txt"
Remove-Item (Join-Path $evidencia $archivoPytest) -ErrorAction SilentlyContinue
Escribir $archivoPytest @("# Redis (Fase 3) · pytest -m integration -k redis", "# Generado: $marca", "")
$salidaPytest = & $python -m pytest -m integration -k redis -v -rs -p no:cacheprovider 2>&1 | ForEach-Object { "$_" }
Escribir $archivoPytest $salidaPytest

# 2. Sesiones de prueba (IDs aleatorios, solo en .local/)
& (Join-Path $PSScriptRoot "crear_sesiones_prueba.ps1") -BaseUrl $base | Out-Null
$sesiones = (Get-Content (Join-Path $raiz ".local\sesiones_prueba.json") -Raw -Encoding UTF8 | ConvertFrom-Json).sesiones
$lector = ($sesiones | Where-Object rol -eq "lector").sesionId
$moderador = ($sesiones | Where-Object rol -eq "moderador").sesionId
$operador = ($sesiones | Where-Object rol -eq "operador").sesionId

# 3. Lista de control con la API levantada
$archivoControl = "redis_lista_de_control.txt"
$logApi = Join-Path $evidencia "redis_api.log"
Remove-Item (Join-Path $evidencia $archivoControl), $logApi -ErrorAction SilentlyContinue
Escribir $archivoControl @(
    "# Redis (Fase 3) · Lista de control (plan_de_implementacion.md)",
    "# Generado: $marca · API en $base · respuestas crudas de curl.exe -i",
    "# Sesiones creadas con scripts/crear_sesiones_prueba.ps1; los IDs se muestran enmascarados."
)

$api = Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "$Puerto" `
    -WorkingDirectory $raiz -RedirectStandardError "$logApi.err" -RedirectStandardOutput "$logApi.out" `
    -PassThru -WindowStyle Hidden
try {
    Esperar-Api
    Docker-Compose @("exec", "-T", "redis", "redis-cli", "DEL", "${prefijo}cache:equipo:EQ-001") | Out-Null
    Escribir $archivoControl @("", "(Se eliminó la copia ${prefijo}cache:equipo:EQ-001 para empezar sin caché.)")

    Pedir $archivoControl "Salud con Redis arriba" "GET" "/api/v1/salud"
    Pedir $archivoControl "CU-01 · primera lectura de EQ-001 -> 200 X-Cache: MISS" "GET" "/api/v1/equipos/EQ-001"
    Pedir $archivoControl "CU-01 · segunda lectura de EQ-001 -> 200 X-Cache: HIT" "GET" "/api/v1/equipos/EQ-001"
    Pedir $archivoControl "CU-11 · sin X-Session-Id -> 401 SESION_REQUERIDA" "GET" "/api/v1/sesiones/actual"
    Pedir $archivoControl "CU-11 · formato inválido -> 400 VALIDACION (sin consultar Redis)" "GET" "/api/v1/sesiones/actual" "corta"
    Pedir $archivoControl "CU-11 · sesión inexistente -> 401 SESION_NO_VIGENTE" "GET" "/api/v1/sesiones/actual" "SES-PRUEBA-inexistente"
    Pedir $archivoControl "CU-11 · sesión lector -> 200 sin ID ni ultima_actividad" "GET" "/api/v1/sesiones/actual" $lector
    Pedir $archivoControl "CU-12 · actividad del lector -> 200 expiraEnSegundos 1800" "POST" "/api/v1/sesiones/actual/actividad" $lector
    Pedir $archivoControl "CU-14 · lector -> 403 ROL_NO_AUTORIZADO" "DELETE" "/api/v1/cache/equipos/EQ-001" $lector
    Pedir $archivoControl "CU-14 · operador con EQ-1 -> 400 VALIDACION" "DELETE" "/api/v1/cache/equipos/EQ-1" $operador
    Pedir $archivoControl "CU-14 · operador -> 204" "DELETE" "/api/v1/cache/equipos/EQ-001" $operador
    Pedir $archivoControl "CU-14 · repetido -> 204 (no había copia)" "DELETE" "/api/v1/cache/equipos/EQ-001" $operador
    Pedir $archivoControl "CU-01 · después de invalidar -> 200 X-Cache: MISS" "GET" "/api/v1/equipos/EQ-001"
    Pedir $archivoControl "CU-13 · cerrar la sesión del moderador -> 204" "DELETE" "/api/v1/sesiones/actual" $moderador
    Pedir $archivoControl "CU-13 · cierre repetido -> 204" "DELETE" "/api/v1/sesiones/actual" $moderador
    Pedir $archivoControl "CU-11 · sesión cerrada -> 401 SESION_NO_VIGENTE" "GET" "/api/v1/sesiones/actual" $moderador
    Pedir $archivoControl "CU-12 · actividad de la sesión cerrada -> 401 (no se recrea)" "POST" "/api/v1/sesiones/actual/actividad" $moderador

    if ($ConDetencion) {
        Escribir $archivoControl @("", "## Redis detenido (docker compose stop redis en Hito 7)")
        try {
            Docker-Compose @("stop", "redis") | Out-Null
            Pedir $archivoControl "CU-01 con Redis detenido -> 200 X-Cache: BYPASS (desde MongoDB)" "GET" "/api/v1/equipos/EQ-001"
            Pedir $archivoControl "CU-11 con Redis detenido -> 503, no 401" "GET" "/api/v1/sesiones/actual" $lector
            Pedir $archivoControl "CU-13 con Redis detenido -> 503, no 204" "DELETE" "/api/v1/sesiones/actual" $lector
            Pedir $archivoControl "CU-14 con Redis detenido -> 503" "DELETE" "/api/v1/cache/equipos/EQ-001" $operador
            Pedir $archivoControl "Salud con Redis detenido -> 200 degradado" "GET" "/api/v1/salud"
        } finally {
            Docker-Compose @("start", "redis") | Out-Null
            Esperar-Redis
        }
        Pedir $archivoControl "CU-11 después de volver a levantar Redis -> 200 (AOF conserva la sesión)" "GET" "/api/v1/sesiones/actual" $lector
        Pedir $archivoControl "CU-01 después de volver a levantar Redis -> 200 MISS o HIT" "GET" "/api/v1/equipos/EQ-001"
    }
} finally {
    Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 300
    foreach ($parcial in "$logApi.err", "$logApi.out") {
        if (Test-Path $parcial) {
            Enmascarar (Get-Content $parcial) | Add-Content $logApi -Encoding UTF8
            Remove-Item $parcial
        }
    }
}

# 4. Las rutas y servicios no importan el driver
$coincidencias = Select-String -Path "app\routes\*.py", "app\services\*.py" -Pattern "^\s*(from|import)\s+redis"
Escribir $archivoControl @("", "### Ningún archivo de app/routes ni app/services importa redis")
if ($coincidencias) {
    Escribir $archivoControl ($coincidencias | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line)" })
} else {
    Escribir $archivoControl "Sin coincidencias de 'import redis' / 'from redis' en app/routes ni app/services."
}

# 5. Ningún ID de sesión completo en la evidencia
$filtrados = Select-String -Path (Join-Path $evidencia "redis_*") -Pattern $patronId
if ($filtrados) { throw "Hay IDs de sesión completos en docs/evidencia/redis_*: revisar antes de versionar." }

Write-Host "Evidencia generada en $evidencia (IDs de sesión enmascarados)"
