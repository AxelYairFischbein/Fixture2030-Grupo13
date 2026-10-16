<#
.SYNOPSIS
  Genera la evidencia de IRIS (Fase 7: CU-18 y CU-19) en docs/evidencia/iris_*.

.DESCRIPTION
  1. Carga el envoltorio FixtureH10.Servicio (cargar_servicio_iris.ps1).
  2. Corre las pruebas de integración de IRIS (pytest -m integration tests/integracion/test_iris.py)
     contra el contenedor del Hito 9 y el Redis del Hito 7.
  3. Crea sesiones de prueba (crear_sesiones_prueba.ps1) y un partido temporal PAR-9xx
     (tests/integracion/iris_temporal.py), levanta la API con uvicorn y recorre la lista de
     control de la Fase 7 con curl.exe. PAR-001 solo se lee. El temporal se borra siempre.
  4. Con -ConDetencion detiene IRIS (docker compose stop en Hito 9), verifica 503 y siempre lo
     vuelve a levantar.
  5. Verifica que ni routes/ ni services/ importen el SDK de IRIS, que no quede ningún ID de
     sesión completo y que la contraseña de IRIS no aparezca en la evidencia ni en git diff.

  Los IDs de sesión se enmascaran (SES-PRUEBA-3f9a…). La contraseña se lee de .env solo para
  buscarla en la evidencia: nunca se imprime ni se escribe.
  Ejecutar desde la carpeta "Hito 10":  .\scripts\evidencia_iris.ps1 [-ConDetencion]
#>
param(
    [int]$Puerto = 8014,
    [switch]$ConDetencion
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$evidencia = Join-Path $raiz "docs\evidencia"
$local = Join-Path $raiz ".local"
$python = Join-Path $raiz ".venv\Scripts\python.exe"
$composeHito9 = Join-Path (Split-Path -Parent $raiz) "Hito 9\docker-compose.yml"
$base = "http://127.0.0.1:$Puerto"
$patronId = 'SES-PRUEBA-([0-9a-f]{4})[0-9a-f]{28}'
New-Item -ItemType Directory -Force $evidencia, $local | Out-Null
Set-Location $raiz

function Enmascarar([string[]]$lineas) {
    return $lineas | ForEach-Object { "$_" -replace $patronId, 'SES-PRUEBA-$1…' }
}

function Escribir([string]$archivo, [string[]]$lineas) {
    Enmascarar $lineas | Out-File -FilePath (Join-Path $evidencia $archivo) -Encoding utf8 -Append
}

function Pedir {
    param([string]$Archivo, [string]$Titulo, [string]$Metodo, [string]$Ruta,
          [string]$Sesion = "", [string]$Cuerpo = "")
    $argumentos = @("-s", "-i", "--max-time", "15", "-X", $Metodo, "-w", "`n(tiempo_total_s=%{time_total})")
    $descripcion = "$Metodo $Ruta"
    if ($Sesion) {
        $argumentos += @("-H", "X-Session-Id: $Sesion")
        $descripcion += "  [X-Session-Id: $Sesion]"
    }
    if ($Cuerpo) {
        # El body va por archivo: PowerShell 5.1 rompe las comillas de un JSON pasado a curl.exe.
        $archivoCuerpo = Join-Path $local "cuerpo_evidencia.json"
        [IO.File]::WriteAllText($archivoCuerpo, $Cuerpo, (New-Object Text.UTF8Encoding $false))
        $argumentos += @("-H", "Content-Type: application/json", "--data-binary", "@$archivoCuerpo")
        $descripcion += "  body: $Cuerpo"
    }
    Escribir $Archivo @("", "### $Titulo", $descripcion)
    $salida = & curl.exe @argumentos "$base$Ruta"
    Escribir $Archivo $salida
    return $salida
}

function Transicion([string]$Titulo, [string]$Partido, [string]$Estado, [string]$Sesion) {
    $cuerpo = '{"nuevoEstado":"' + $Estado + '"}'
    Pedir $archivoControl $Titulo "POST" "/api/v1/partidos/$Partido/acta/transiciones" $Sesion $cuerpo | Out-Null
}

function Python-Temporal([string[]]$argumentos) {
    $ErrorActionPreference = "Continue"
    $salida = & $python -m tests.integracion.iris_temporal @argumentos 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw "iris_temporal $($argumentos -join ' ') falló: $($salida -join ' ')" }
    return ($salida | Select-Object -Last 1).Trim()
}

function Docker-Compose([string[]]$argumentos) {
    # En PowerShell 5.1 lo que docker escribe en stderr se vuelve un error terminante
    # con ErrorActionPreference=Stop: se relaja solo para esta llamada.
    $ErrorActionPreference = "Continue"
    $salida = & docker compose -f $composeHito9 @argumentos 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw "docker compose $($argumentos -join ' ') falló" }
    return $salida
}

function Esperar-Api {
    for ($i = 0; $i -lt 40; $i++) {
        # /salud puede tardar el timeout de una fuente caída (IRIS: 3 s).
        & curl.exe -s -o NUL --max-time 10 "$base/api/v1/salud"
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "La API no respondió en $base"
}

$marca = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

# 1. Envoltorio cargado
& (Join-Path $PSScriptRoot "cargar_servicio_iris.ps1")

# 2. Pruebas de integración de IRIS
$archivoPytest = "iris_pytest_integracion.txt"
Remove-Item (Join-Path $evidencia $archivoPytest) -ErrorAction SilentlyContinue
Escribir $archivoPytest @("# IRIS (Fase 7) · pytest -m integration tests/integracion/test_iris.py", "# Generado: $marca", "")
$salidaPytest = & $python -m pytest -m integration tests/integracion/test_iris.py -v -rs -p no:cacheprovider 2>&1 | ForEach-Object { "$_" }
Escribir $archivoPytest $salidaPytest

# 3. Sesiones de prueba (IDs aleatorios, solo en .local/)
& (Join-Path $PSScriptRoot "crear_sesiones_prueba.ps1") -BaseUrl $base | Out-Null
$sesiones = (Get-Content (Join-Path $local "sesiones_prueba.json") -Raw -Encoding UTF8 | ConvertFrom-Json).sesiones
$operador = ($sesiones | Where-Object rol -eq "operador").sesionId
$lector = ($sesiones | Where-Object rol -eq "lector").sesionId

# 4. Lista de control con la API levantada
$archivoControl = "iris_lista_de_control.txt"
$logApi = Join-Path $evidencia "iris_api.log"
Remove-Item (Join-Path $evidencia $archivoControl), $logApi -ErrorAction SilentlyContinue
Escribir $archivoControl @(
    "# IRIS (Fase 7) · Lista de control (plan_de_implementacion.md)",
    "# Generado: $marca · API en $base · respuestas crudas de curl.exe -i"
)

$temporal = $null
$api = Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "$Puerto" `
    -WorkingDirectory $raiz -RedirectStandardError "$logApi.err" -RedirectStandardOutput "$logApi.out" `
    -PassThru -WindowStyle Hidden
try {
    Esperar-Api
    $temporal = Python-Temporal @("crear")
    Escribir $archivoControl "# Partido temporal creado para las transiciones: $temporal (PENDIENTE, EST-01, sin eventos)"

    Pedir $archivoControl "Salud con IRIS arriba" "GET" "/api/v1/salud" | Out-Null
    Pedir $archivoControl "CU-18 · PAR-001 -> PENDIENTE, EST-01, ARB-001 y dos eventos (sin ID ni licencia)" "GET" "/api/v1/partidos/PAR-001/acta" | Out-Null
    Pedir $archivoControl "CU-18 · PAR-002 existe en Neo4j y no tiene acta -> 404 ACTA_NO_ENCONTRADA" "GET" "/api/v1/partidos/PAR-002/acta" | Out-Null
    Pedir $archivoControl "CU-18 · PAR-1 -> 400 VALIDACION (sin consultar IRIS)" "GET" "/api/v1/partidos/PAR-1/acta" | Out-Null
    Pedir $archivoControl "CU-18 · temporal $temporal -> PENDIENTE y eventos []" "GET" "/api/v1/partidos/$temporal/acta" | Out-Null

    Transicion "CU-19 · $temporal EN_JUEGO -> 200 cambio true" $temporal "EN_JUEGO" $operador
    Transicion "CU-19 · repetir EN_JUEGO -> 200 cambio false (no llama a CambiarEstado)" $temporal "EN_JUEGO" $operador
    Transicion "CU-19 · FINALIZADO -> 200 cambio true" $temporal "FINALIZADO" $operador
    Transicion "CU-19 · volver a EN_JUEGO -> 409 TRANSICION_NO_PERMITIDA con el estado actual" $temporal "EN_JUEGO" $operador
    Pedir $archivoControl "CU-18 · el estado quedó FINALIZADO" "GET" "/api/v1/partidos/$temporal/acta" | Out-Null
    Transicion "CU-19 · repetir FINALIZADO -> 200 cambio false" $temporal "FINALIZADO" $operador
    Transicion "CU-19 · nuevoEstado PENDIENTE -> 400 VALIDACION (sin consultar Redis ni IRIS)" $temporal "PENDIENTE" $operador
    Transicion "CU-19 · sin X-Session-Id -> 401 SESION_REQUERIDA" $temporal "EN_JUEGO" ""
    Transicion "CU-19 · sesión de lector -> 403 ROL_NO_AUTORIZADO" $temporal "EN_JUEGO" $lector
    Transicion "CU-19 · PAR-002 sin acta -> 404 ACTA_NO_ENCONTRADA" "PAR-002" "EN_JUEGO" $operador
    Pedir $archivoControl "CU-18 · PAR-001 sigue PENDIENTE" "GET" "/api/v1/partidos/PAR-001/acta" | Out-Null

    if ($ConDetencion) {
        Escribir $archivoControl @("", "## IRIS detenido (docker compose stop iris en Hito 9)")
        try {
            Docker-Compose @("stop", "iris") | Out-Null
            Pedir $archivoControl "CU-18 con IRIS detenido -> 503" "GET" "/api/v1/partidos/PAR-001/acta" | Out-Null
            Transicion "CU-19 con IRIS detenido -> 503 (sin cambios)" $temporal "EN_JUEGO" $operador
            Pedir $archivoControl "Salud con IRIS detenido -> 200 degradado" "GET" "/api/v1/salud" | Out-Null
        } finally {
            Docker-Compose @("start", "iris") | Out-Null
        }
        for ($i = 0; $i -lt 60; $i++) {
            $codigo = & curl.exe -s -o NUL -w "%{http_code}" --max-time 10 "$base/api/v1/partidos/PAR-001/acta"
            if ($codigo -eq "200") { break }
            Start-Sleep -Seconds 2
        }
        Pedir $archivoControl "CU-18 después de volver a levantar IRIS -> 200 (la API reconecta)" "GET" "/api/v1/partidos/PAR-001/acta" | Out-Null
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
    Remove-Item (Join-Path $local "cuerpo_evidencia.json") -ErrorAction SilentlyContinue
    if ($temporal) {
        Python-Temporal @("borrar", $temporal) | Out-Null
        Escribir $archivoControl @("", "(Se borró el partido temporal $temporal; PAR-001 no se modificó.)")
    }
}

# 5. Las rutas y servicios no importan el SDK de IRIS
$coincidencias = Select-String -Path "app\routes\*.py", "app\services\*.py" -Pattern "^\s*(from|import)\s+iris"
Escribir $archivoControl @("", "### Ningún archivo de app/routes ni app/services importa iris")
if ($coincidencias) {
    Escribir $archivoControl ($coincidencias | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line)" })
} else {
    Escribir $archivoControl "Sin coincidencias de 'import iris' / 'from iris' en app/routes ni app/services."
}

# 6. Ningún ID de sesión completo ni la contraseña de IRIS en la evidencia
$filtrados = Select-String -Path (Join-Path $evidencia "iris_*") -Pattern $patronId
if ($filtrados) { throw "Hay IDs de sesión completos en docs/evidencia/iris_*: revisar antes de versionar." }
$secreto = & $python -c "from dotenv import dotenv_values; print(dotenv_values('.env').get('IRIS_PASSWORD') or '')"
if ($secreto) {
    $enArchivos = Select-String -Path (Join-Path $evidencia "iris_*"), "tests\*.py", "tests\integracion\*.py", "app\*.py", "app\*\*.py", "iris\*" -SimpleMatch -Pattern $secreto -Quiet
    $ErrorActionPreference = "Continue"
    $diff = (& git diff HEAD -- . 2>$null) -join "`n"
    $ErrorActionPreference = "Stop"
    $enDiff = $diff.Contains($secreto)
    $secreto = $null
    Escribir $archivoControl @("", "### La contraseña de IRIS no aparece en docs/evidencia/iris_*, tests/, app/, iris/ ni git diff")
    if ($enArchivos -or $enDiff) { throw "La contraseña de IRIS aparece en la evidencia, el código o git diff: revisar antes de versionar." }
    Escribir $archivoControl "Sin coincidencias."
}

Write-Host "Evidencia generada en $evidencia (IDs de sesión enmascarados)"
