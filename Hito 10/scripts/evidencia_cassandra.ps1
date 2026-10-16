<#
.SYNOPSIS
  Genera la evidencia de Cassandra (Fase 5: CU-08, CU-09, CU-10 y CU-20) en docs/evidencia/cassandra_*.

.DESCRIPTION
  1. Corre las pruebas de integración de Cassandra (pytest -m integration -k cassandra) contra el
     contenedor del Hito 6 (con carga_muestra.cql) y el Redis del Hito 7.
  2. Crea sesiones de prueba con crear_sesiones_prueba.ps1 (IDs aleatorios en .local/).
  3. Levanta la API con uvicorn y recorre la lista de control de la Fase 5 con curl.exe:
     lecturas de la muestra, publicación idempotente en PAR-064, 409, moderación y 404 sin escribir.
  4. Con -ConDetencion detiene Cassandra (docker compose stop en Hito 6), verifica 503/504 (nunca
     200 []) y siempre la vuelve a levantar.
  5. Borra el comentario publicado (las dos tablas y la clave de idempotencia) y verifica que ni
     routes/ ni services/ importen cassandra.

  Los IDs de sesión son credenciales: todo lo que se escribe en docs/evidencia pasa por
  Enmascarar (SES-PRUEBA-3f9a…) y al final se comprueba que no quedó ningún ID completo.
  No lee ni imprime credenciales: la API las toma de Hito 10/.env.
  Ejecutar desde la carpeta "Hito 10":  .\scripts\evidencia_cassandra.ps1 [-ConDetencion]
#>
param(
    [int]$Puerto = 8012,
    [switch]$ConDetencion
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$evidencia = Join-Path $raiz "docs\evidencia"
$local = Join-Path $raiz ".local"
$python = Join-Path $raiz ".venv\Scripts\python.exe"
$composeHito6 = Join-Path (Split-Path -Parent $raiz) "Hito 6\docker-compose.yml"
$composeHito7 = Join-Path (Split-Path -Parent $raiz) "Hito 7\docker-compose.yml"
$base = "http://127.0.0.1:$Puerto"
$prefijo = "fixture2030:h7:demo:"
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
          [string]$Sesion = "", [string]$Clave = "", [string]$Cuerpo = "")
    $argumentos = @("-s", "-i", "--max-time", "15", "-X", $Metodo, "-w", "`n(tiempo_total_s=%{time_total})")
    $descripcion = "$Metodo $Ruta"
    if ($Sesion) {
        $argumentos += @("-H", "X-Session-Id: $Sesion")
        $descripcion += "  [X-Session-Id: $Sesion]"
    }
    if ($Clave) {
        $argumentos += @("-H", "Idempotency-Key: $Clave")
        $descripcion += "  [Idempotency-Key: $Clave]"
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

function Cuerpo-Json([string[]]$salida) {
    $linea = $salida | Where-Object { $_ -like "{*" } | Select-Object -Last 1
    return $linea | ConvertFrom-Json
}

function Docker-Compose([string]$archivo, [string[]]$argumentos) {
    # En PowerShell 5.1 lo que docker escribe en stderr se vuelve un error terminante
    # con ErrorActionPreference=Stop: se relaja solo para esta llamada.
    $ErrorActionPreference = "Continue"
    $salida = & docker compose -f $archivo @argumentos 2>&1 | ForEach-Object { "$_" }
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

function Esperar-Cassandra {
    for ($i = 0; $i -lt 90; $i++) {
        $ErrorActionPreference = "Continue"
        & docker compose -f $composeHito6 exec -T cassandra cqlsh -e "SELECT release_version FROM system.local" *> $null
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Seconds 2
    }
    throw "Cassandra no volvió a aceptar conexiones CQL"
}

function Borrar-Comentario($comentario) {
    # Las dos filas por clave completa y el registro de idempotencia.
    $id = $comentario.comentarioId
    $creado = $comentario.creadoEn
    $minuto = $creado.Substring(0, 16) + ":00Z"
    $dia = $creado.Substring(0, 10)
    $segmento = & $python -c "import sys, zlib; print(zlib.crc32(sys.argv[1].encode('utf-8')) % 4)" $id
    $cql = "DELETE FROM fixture2030_comentarios.comentarios_por_partido WHERE partido_id = '$($comentario.partidoId)' " +
           "AND minuto = '$minuto' AND segmento = $segmento AND creado_en = '$creado' AND comentario_id = '$id'; " +
           "DELETE FROM fixture2030_comentarios.comentarios_por_usuario WHERE usuario_id = '$($comentario.usuarioId)' " +
           "AND dia = '$dia' AND creado_en = '$creado' AND comentario_id = '$id';"
    Docker-Compose $composeHito6 @("exec", "-T", "cassandra", "cqlsh", "-e", $cql) | Out-Null
    Docker-Compose $composeHito7 @("exec", "-T", "redis", "redis-cli", "DEL", "${prefijo}idem:comentario:$id") | Out-Null
}

$marca = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

# 1. Pruebas de integración de Cassandra
$archivoPytest = "cassandra_pytest_integracion.txt"
Remove-Item (Join-Path $evidencia $archivoPytest) -ErrorAction SilentlyContinue
Escribir $archivoPytest @("# Cassandra (Fase 5) · pytest -m integration -k cassandra", "# Generado: $marca", "")
$salidaPytest = & $python -m pytest -m integration -k cassandra -v -rs -p no:cacheprovider 2>&1 | ForEach-Object { "$_" }
Escribir $archivoPytest $salidaPytest

# 2. Sesiones de prueba (IDs aleatorios, solo en .local/)
& (Join-Path $PSScriptRoot "crear_sesiones_prueba.ps1") -BaseUrl $base | Out-Null
$sesiones = (Get-Content (Join-Path $local "sesiones_prueba.json") -Raw -Encoding UTF8 | ConvertFrom-Json).sesiones
$lector = $sesiones | Where-Object rol -eq "lector"
$moderador = ($sesiones | Where-Object rol -eq "moderador").sesionId

# 3. Lista de control con la API levantada
$archivoControl = "cassandra_lista_de_control.txt"
$logApi = Join-Path $evidencia "cassandra_api.log"
Remove-Item (Join-Path $evidencia $archivoControl), $logApi -ErrorAction SilentlyContinue
Escribir $archivoControl @(
    "# Cassandra (Fase 5) · Lista de control (plan_de_implementacion.md)",
    "# Generado: $marca · API en $base · respuestas crudas de curl.exe -i",
    "# Sesiones creadas con scripts/crear_sesiones_prueba.ps1; los IDs se muestran enmascarados.",
    "# Lecturas sobre la muestra del Hito 6 (carga_muestra.cql); escrituras sobre PAR-064, borradas al final."
)

$publicado = $null
$api = Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "$Puerto" `
    -WorkingDirectory $raiz -RedirectStandardError "$logApi.err" -RedirectStandardOutput "$logApi.out" `
    -PassThru -WindowStyle Hidden
try {
    Esperar-Api
    $q1 = "/api/v1/partidos/PAR-001/comentarios?minuto=2030-06-10T18:01:00Z"
    $q2 = "/api/v1/partidos/PAR-001/comentarios?desde=2030-06-10T18:00:30Z&hasta=2030-06-10T18:02:10Z"
    $escritura = "/api/v1/partidos/PAR-064/comentarios"

    Pedir $archivoControl "Salud con Cassandra arriba" "GET" "/api/v1/salud" | Out-Null
    Pedir $archivoControl "CU-08 · Q1 anónimo -> 200 solo visibles (008, 005, 006)" "GET" $q1 | Out-Null
    Pedir $archivoControl "CU-08 · Q1 moderador -> 200 todos los estados (008, 007, 005, 006, 004)" "GET" $q1 $moderador | Out-Null
    Pedir $archivoControl "CU-08 · Q2 ventana moderador -> 200 (009 … 002), igual que consultas.cql" "GET" $q2 $moderador | Out-Null
    Pedir $archivoControl "CU-08 · Q2 con limite=3 -> siguienteCursor" "GET" "$q2&limite=3" $moderador | Out-Null
    Pedir $archivoControl "CU-08 · ventana de 6 min -> 400 VALIDACION (sin consultar)" "GET" "/api/v1/partidos/PAR-001/comentarios?desde=2030-06-10T18:00:00Z&hasta=2030-06-10T18:06:00Z" | Out-Null
    Pedir $archivoControl "CU-08 · PAR-999 -> 404 PARTIDO_NO_ENCONTRADO (catálogo, sin consultar Cassandra)" "GET" "/api/v1/partidos/PAR-999/comentarios" | Out-Null
    Pedir $archivoControl "CU-10 · historial propio de $($lector.usuarioId) el 2030-06-10 -> 200" "GET" "/api/v1/usuarios/$($lector.usuarioId)/comentarios?dia=2030-06-10" $lector.sesionId | Out-Null
    Pedir $archivoControl "CU-10 · el lector pide el historial de USR-00003 -> 403" "GET" "/api/v1/usuarios/USR-00003/comentarios?dia=2030-06-10" $lector.sesionId | Out-Null

    $clave = [guid]::NewGuid().ToString()
    $cuerpo = '{"contenido": "Comentario de evidencia de la Fase 5"}'
    Pedir $archivoControl "CU-09 · sin X-Session-Id -> 401 sin escribir" "POST" $escritura "" $clave $cuerpo | Out-Null
    Pedir $archivoControl "CU-09 · sin Idempotency-Key -> 400" "POST" $escritura $lector.sesionId "" $cuerpo | Out-Null
    $salida = Pedir $archivoControl "CU-09 · publicar -> 201" "POST" $escritura $lector.sesionId $clave $cuerpo
    $publicado = Cuerpo-Json $salida
    Pedir $archivoControl "CU-09 · reintento con la misma clave -> 201, mismo comentarioId y creadoEn" "POST" $escritura $lector.sesionId $clave $cuerpo | Out-Null
    Pedir $archivoControl "CU-09 · misma clave con otro body -> 409 IDEMPOTENCY_KEY_REUTILIZADA" "POST" $escritura $lector.sesionId $clave '{"contenido": "Otro texto"}' | Out-Null

    $minuto = $publicado.creadoEn.Substring(0, 16) + ":00Z"
    $dia = $publicado.creadoEn.Substring(0, 10)
    Pedir $archivoControl "CU-08 · minuto de la publicación -> el comentario aparece una sola vez" "GET" "${escritura}?minuto=$minuto" | Out-Null
    Pedir $archivoControl "CU-10 · historial del autor el $dia -> aparece una sola vez" "GET" "/api/v1/usuarios/$($lector.usuarioId)/comentarios?dia=$dia" $lector.sesionId | Out-Null

    $rutaModeracion = "$escritura/$clave"
    Pedir $archivoControl "CU-20 · creadoEn equivocado -> 404 COMENTARIO_NO_ENCONTRADO sin escribir" "PATCH" $rutaModeracion $moderador "" '{"creadoEn": "2030-06-10T18:01:21.000Z", "estado": "oculto"}' | Out-Null
    Pedir $archivoControl "CU-20 · lector intenta moderar -> 403" "PATCH" $rutaModeracion $lector.sesionId "" "{`"creadoEn`": `"$($publicado.creadoEn)`", `"estado`": `"oculto`"}" | Out-Null
    Pedir $archivoControl "CU-20 · moderador oculta -> 200 cambio=true" "PATCH" $rutaModeracion $moderador "" "{`"creadoEn`": `"$($publicado.creadoEn)`", `"estado`": `"oculto`"}" | Out-Null
    Pedir $archivoControl "CU-20 · repetido -> 200 cambio=false (sin escribir)" "PATCH" $rutaModeracion $moderador "" "{`"creadoEn`": `"$($publicado.creadoEn)`", `"estado`": `"oculto`"}" | Out-Null
    Pedir $archivoControl "CU-08 · anónimo -> el comentario oculto ya no aparece" "GET" "${escritura}?minuto=$minuto" | Out-Null
    Pedir $archivoControl "CU-08 · moderador -> sigue apareciendo con estado oculto" "GET" "${escritura}?minuto=$minuto" $moderador | Out-Null
    Pedir $archivoControl "CU-10 · historial del autor -> estado oculto" "GET" "/api/v1/usuarios/$($lector.usuarioId)/comentarios?dia=$dia" $lector.sesionId | Out-Null

    if ($ConDetencion) {
        Escribir $archivoControl @("", "## Cassandra detenida (docker compose stop cassandra en Hito 6)")
        try {
            Docker-Compose $composeHito6 @("stop", "cassandra") | Out-Null
            Pedir $archivoControl "CU-08 con Cassandra detenida -> 503/504, nunca 200 []" "GET" $q1 | Out-Null
            Pedir $archivoControl "CU-09 con Cassandra detenida -> 503/504" "POST" $escritura $lector.sesionId ([guid]::NewGuid().ToString()) $cuerpo | Out-Null
            Pedir $archivoControl "Salud con Cassandra detenida -> 200 degradado" "GET" "/api/v1/salud" | Out-Null
        } finally {
            Docker-Compose $composeHito6 @("start", "cassandra") | Out-Null
            Esperar-Cassandra
        }
        # El driver reconecta solo; se da un margen antes de registrar la lectura.
        for ($i = 0; $i -lt 30; $i++) {
            $codigo = & curl.exe -s -o NUL -w "%{http_code}" --max-time 5 "$base$q1"
            if ($codigo -eq "200") { break }
            Start-Sleep -Seconds 2
        }
        Pedir $archivoControl "CU-08 después de volver a levantar Cassandra -> 200" "GET" $q1 | Out-Null
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
    if ($publicado) {
        Borrar-Comentario $publicado
        Escribir $archivoControl @("", "(Se borró el comentario de evidencia de las dos tablas y su clave de idempotencia.)")
    }
}

# 4. Las rutas y servicios no importan el driver
$coincidencias = Select-String -Path "app\routes\*.py", "app\services\*.py" -Pattern "^\s*(from|import)\s+cassandra"
Escribir $archivoControl @("", "### Ningún archivo de app/routes ni app/services importa cassandra")
if ($coincidencias) {
    Escribir $archivoControl ($coincidencias | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line)" })
} else {
    Escribir $archivoControl "Sin coincidencias de 'import cassandra' / 'from cassandra' en app/routes ni app/services."
}

# 5. Ningún ID de sesión completo en la evidencia
$filtrados = Select-String -Path (Join-Path $evidencia "cassandra_*") -Pattern $patronId
if ($filtrados) { throw "Hay IDs de sesión completos en docs/evidencia/cassandra_*: revisar antes de versionar." }

Write-Host "Evidencia generada en $evidencia (IDs de sesión enmascarados)"
