<#
.SYNOPSIS
  Genera la evidencia transversal de la API (no atada a una fuente) en docs/evidencia/api_*.

.DESCRIPTION
  1. api_pytest_unitarias.txt: pytest -m "not integration" -v (adaptadores falsos, sin Docker).
  2. api_openapi_verificacion.txt: exportar_openapi.ps1 -Verificar (openapi.yaml = app.openapi(), RNF2).
  3. api_correlacion_request_id.txt: levanta la API, envía una request por fuente con un
     X-Request-Id fijo y extrae del log de la API las líneas con ese id (acceso, adaptador y
     manejador de errores), RF18 / RNF10. Incluye una entrada inválida (400) para mostrar que
     no hay línea de adaptador (RNF3) y una request con X-Session-Id para mostrar que el ID de
     sesión no aparece en el log.
  4. api_revision_secretos.txt: sobre los archivos que git versionaría en Hito 10/ (versionados
     y nuevos no ignorados) busca los valores reales de las contraseñas de .env y del token de
     InfluxDB (solo informa la cantidad, nunca el valor), IDs de sesión completos y la lista de
     apariciones de password|token|secret para revisión manual.
  5. Agrega a api_pytest_unitarias.txt si newman está instalado (la colección no se ejecuta acá).

  Los IDs de sesión se enmascaran (SES-PRUEBA-3f9a…). Las credenciales se leen de .env solo
  para buscarlas: nunca se imprimen ni se escriben.
  Ejecutar desde la carpeta "Hito 10":  .\scripts\evidencia_api.ps1 [-Puerto 8018]
#>
param([ValidateRange(1, 65535)][int]$Puerto = 8018)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$evidencia = Join-Path $raiz "docs\evidencia"
$python = Join-Path $raiz ".venv\Scripts\python.exe"
$base = "http://127.0.0.1:$Puerto"
$patronId = 'SES-PRUEBA-([0-9a-f]{4})[0-9a-f]{28}'
New-Item -ItemType Directory -Force $evidencia | Out-Null
Set-Location $raiz

function Enmascarar([string[]]$lineas) {
    return $lineas | ForEach-Object { "$_" -replace $patronId, 'SES-PRUEBA-$1…' }
}

function Escribir([string]$archivo, [string[]]$lineas) {
    Enmascarar $lineas | Out-File -FilePath (Join-Path $evidencia $archivo) -Encoding utf8 -Append
}

function Nuevo-Archivo([string]$archivo, [string[]]$encabezado) {
    Remove-Item (Join-Path $evidencia $archivo) -ErrorAction SilentlyContinue
    Escribir $archivo $encabezado
}

function Ejecutar([scriptblock]$bloque) {
    # Captura stdout y stderr de un ejecutable nativo sin que PowerShell 5.1 los vuelva errores.
    $ErrorActionPreference = "Continue"
    $salida = & $bloque 2>&1 | ForEach-Object { "$_" }
    return @{ salida = $salida; codigo = $LASTEXITCODE }
}

function Esperar-Api {
    for ($i = 0; $i -lt 40; $i++) {
        & curl.exe -s -o NUL --max-time 10 "$base/api/v1/salud"
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "La API no respondió en $base"
}

$marca = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

# 1. Unitarias
$archivo = "api_pytest_unitarias.txt"
Nuevo-Archivo $archivo @("# API · pytest -m `"not integration`" (adaptadores falsos, sin Docker)", "# Generado: $marca", "")
$r = Ejecutar { & $python -m pytest -m "not integration" -v -p no:cacheprovider }
Escribir $archivo ($r.salida + @("", "(código de salida: $($r.codigo))"))

# 2. OpenAPI versionado = app.openapi()
$archivo = "api_openapi_verificacion.txt"
Nuevo-Archivo $archivo @("# API · scripts/exportar_openapi.ps1 -Verificar (RNF2)", "# Generado: $marca", "")
$r = Ejecutar { powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "exportar_openapi.ps1") -Verificar }
Escribir $archivo ($r.salida + @("", "(código de salida: $($r.codigo); 0 = openapi/openapi.yaml coincide con app.openapi())"))

# 3. Correlación por X-Request-Id
& (Join-Path $PSScriptRoot "crear_sesiones_prueba.ps1") -BaseUrl $base | Out-Null
$sesiones = (Get-Content (Join-Path $raiz ".local\sesiones_prueba.json") -Raw -Encoding UTF8 | ConvertFrom-Json).sesiones
$lector = ($sesiones | Where-Object rol -eq "lector").sesionId

$archivo = "api_correlacion_request_id.txt"
Nuevo-Archivo $archivo @(
    "# API · Correlación entre la respuesta y el log por X-Request-Id (RF18, RNF10)",
    "# Generado: $marca · API en $base (uvicorn, LOG_LEVEL de .env)",
    "# Para cada request: encabezados de la respuesta y las líneas del log de la API que llevan",
    "# el mismo request_id (middleware app.acceso, adaptador app.adapters.* y app.manejadores)."
)
$pedidos = @(
    @{ id = "11111111-1111-4111-8111-000000000001"; titulo = "CU-01 · MongoDB + Redis (cache-aside)"; ruta = "/api/v1/equipos/EQ-001" },
    @{ id = "11111111-1111-4111-8111-000000000002"; titulo = "CU-06 · Neo4j"; ruta = "/api/v1/partidos/PAR-001/eventos" },
    @{ id = "11111111-1111-4111-8111-000000000003"; titulo = "CU-08 · Cassandra (partido validado contra el catálogo)"; ruta = "/api/v1/partidos/PAR-001/comentarios?minuto=2030-06-10T18:01:00Z" },
    @{ id = "11111111-1111-4111-8111-000000000004"; titulo = "CU-16 · InfluxDB"; ruta = "/api/v1/partidos/PAR-001/estadisticas/comparacion?desde=2026-10-16T00:12:00Z&hasta=2026-10-16T00:17:00Z" },
    @{ id = "11111111-1111-4111-8111-000000000005"; titulo = "CU-18 · IRIS"; ruta = "/api/v1/partidos/PAR-001/acta" },
    @{ id = "11111111-1111-4111-8111-000000000006"; titulo = "CU-11 · Redis con X-Session-Id (el ID no debe aparecer en el log)"; ruta = "/api/v1/sesiones/actual"; sesion = $lector },
    @{ id = "11111111-1111-4111-8111-000000000007"; titulo = "CU-04 · JUG-9999 -> 404 (el adaptador consulta y no encuentra)"; ruta = "/api/v1/jugadores/JUG-9999" },
    @{ id = "11111111-1111-4111-8111-000000000008"; titulo = "CU-01 · EQ-1 -> 400 (no hay línea de adaptador: no se consultó la base)"; ruta = "/api/v1/equipos/EQ-1" },
    @{ id = "no-es-un-uuid"; titulo = "X-Request-Id inválido -> la API genera uno nuevo"; ruta = "/api/v1/equipos/EQ-002" }
)

$logApi = Join-Path $raiz ".local\api_evidencia_correlacion.log"
Remove-Item $logApi, "$logApi.out" -ErrorAction SilentlyContinue
$api = Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "$Puerto" `
    -WorkingDirectory $raiz -RedirectStandardError $logApi -RedirectStandardOutput "$logApi.out" `
    -PassThru -WindowStyle Hidden
$respuestas = @()
try {
    Esperar-Api
    foreach ($p in $pedidos) {
        $argumentos = @("-s", "-i", "--max-time", "15", "-H", "X-Request-Id: $($p.id)")
        if ($p.sesion) { $argumentos += @("-H", "X-Session-Id: $($p.sesion)") }
        $salida = & curl.exe @argumentos "$base$($p.ruta)"
        $respuestas += , @{ pedido = $p; salida = $salida }
    }
    Start-Sleep -Milliseconds 500
} finally {
    Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 300
}
$lineasLog = Get-Content $logApi -Encoding UTF8
foreach ($r in $respuestas) {
    $p = $r.pedido
    $devuelto = ($r.salida | Select-String -Pattern '^x-request-id:\s*(\S+)').Matches | Select-Object -First 1
    $idDevuelto = if ($devuelto) { $devuelto.Groups[1].Value } else { "(sin encabezado)" }
    Escribir $archivo @("", "### $($p.titulo)", "GET $($p.ruta)  [X-Request-Id enviado: $($p.id)$(if ($p.sesion) { "; X-Session-Id: $($p.sesion)" })]")
    Escribir $archivo ($r.salida | Where-Object { $_ -match '^(HTTP/|x-request-id|x-cache|content-type)' })
    Escribir $archivo @("Cuerpo: $(($r.salida | Select-Object -Last 1))", "", "Líneas del log con request_id=${idDevuelto}:")
    Escribir $archivo ($lineasLog | Where-Object { $_ -like "*request_id=$idDevuelto *" } | ForEach-Object { "  $_" })
}
$filtrados = $lineasLog | Select-String -SimpleMatch $lector
Escribir $archivo @("", "### El ID de sesión enviado en X-Session-Id no aparece en el log",
    $(if ($filtrados) { "APARECE $(@($filtrados).Count) vez/veces: revisar el middleware." } else { "Sin apariciones del ID de sesión en $(@($lineasLog).Count) líneas de log." }))

# 4. Revisión de secretos sobre lo que git versionaría
$archivo = "api_revision_secretos.txt"
Nuevo-Archivo $archivo @(
    "# API · Revisión de secretos en los archivos versionables de Hito 10/ (RNF7)",
    "# Generado: $marca",
    "# Archivos: git ls-files -co --exclude-standard (versionados + nuevos no ignorados), sin binarios."
)
$archivos = Ejecutar { git ls-files -co --exclude-standard -- . }
$archivos = $archivos.salida | Where-Object { $_ -and $_ -notmatch '\.(pdf|png|jpg|pyc)$' } | ForEach-Object { Join-Path $raiz $_ } |
    Where-Object { Test-Path $_ -PathType Leaf }

$valores = @()
foreach ($linea in Get-Content (Join-Path $raiz ".env") -Encoding UTF8) {
    if ($linea -match '^\s*(\w*PASSWORD)\s*=\s*(.+?)\s*$' -and $Matches[2].Length -ge 4) {
        $valores += @{ nombre = $Matches[1]; valor = $Matches[2] }
    }
    if ($linea -match '^\s*INFLUX_TOKEN_FILE\s*=\s*(.+?)\s*$') {
        $rutaToken = Join-Path $raiz $Matches[1]
        if (Test-Path $rutaToken) { $valores += @{ nombre = "token de InfluxDB"; valor = (Get-Content $rutaToken -Raw).Trim() } }
    }
}
Escribir $archivo @("", "### Valores reales de .env y del token buscados literalmente en $(@($archivos).Count) archivos")
$hayFiltracion = $false
foreach ($v in $valores) {
    $n = @(Select-String -Path $archivos -SimpleMatch $v.valor -ErrorAction SilentlyContinue).Count
    if ($n -gt 0) { $hayFiltracion = $true }
    Escribir $archivo "  $($v.nombre): $n apariciones"
}
foreach ($s in $sesiones) {
    $n = @(Select-String -Path $archivos -SimpleMatch $s.sesionId -ErrorAction SilentlyContinue).Count
    if ($n -gt 0) { $hayFiltracion = $true }
    Escribir $archivo "  ID de la sesión vigente de $($s.rol) (.local/sesiones_prueba.json): $n apariciones"
}
# Cualquier otro texto con forma de ID completo se lista enmascarado para revisarlo a mano
# (por ejemplo, constantes ficticias de las pruebas unitarias, que nunca existen en Redis).
$ids = @(Select-String -Path $archivos -Pattern $patronId -ErrorAction SilentlyContinue)
Escribir $archivo "  Textos con forma de ID de sesión completo (SES-PRUEBA- + 32 hex): $($ids.Count)"
Escribir $archivo ($ids | ForEach-Object { "    $($_.Path.Substring($raiz.Length + 1)):$($_.LineNumber): $($_.Line.Trim())" })

Escribir $archivo @("", "### Apariciones de password|token|secret (para revisión manual; los valores de relleno son 'completar_localmente')")
if ($hayFiltracion) {
    Escribir $archivo "No se listan las líneas porque hay un valor real filtrado: corregir antes de versionar."
} else {
    Select-String -Path $archivos -Pattern 'password|token|secret' -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -notlike "*\docs\evidencia\api_revision_secretos.txt" } |
        Group-Object Path | ForEach-Object {
            $relativo = $_.Name.Substring($raiz.Length + 1)
            Escribir $archivo "  $relativo ($($_.Count)): líneas $(($_.Group | ForEach-Object LineNumber) -join ', ')"
        }
}

# 5. newman
$newman = Get-Command newman -ErrorAction SilentlyContinue
Escribir "api_pytest_unitarias.txt" @("", "### Colección de Postman (newman)",
    $(if ($newman) { "Instalado en $($newman.Source): la colección se ejecuta con scripts/ejecutar_pruebas.ps1." } else { "No instalado en esta notebook: la colección postman/fixture2030_collection.json no se ejecutó con newman." }))

if ($hayFiltracion) { throw "Hay un secreto o un ID de sesión completo en archivos versionables: ver $archivo" }
Write-Host "Evidencia generada en $evidencia (IDs de sesión enmascarados)"
