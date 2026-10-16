<#
.SYNOPSIS
  Mide la latencia de lectura de la API (un endpoint por fuente) y la guarda en docs/evidencia/api_latencia.txt (RNF18).

.DESCRIPTION
  Método: levanta la API con uvicorn (un proceso, sin --reload) en la notebook y, por cada
  endpoint, hace 1 request de calentamiento y luego -Repeticiones requests secuenciales con
  curl.exe (un cliente, sin concurrencia, conexión nueva por request). Se toma time_total de
  curl (desde abrir la conexión hasta recibir el último byte) y se informan mín, p50, p95 y
  máx (percentil por rango más cercano). Toda request que no devuelva el código esperado
  se cuenta como error y no entra en las estadísticas.

  CU-01 MISS borra la copia de Redis antes de cada request con docker compose exec; ese
  tiempo queda fuera de la medición. El resto de los endpoints repite la misma request,
  así que las cachés de cada motor están calientes.

  Los IDs de sesión se crean con crear_sesiones_prueba.ps1 y no se escriben en la salida.
  Ejecutar desde la carpeta "Hito 10":  .\scripts\medir_latencia.ps1 [-Repeticiones 50] [-Puerto 8017]
#>
param(
    [ValidateRange(5, 1000)][int]$Repeticiones = 50,
    [ValidateRange(1, 65535)][int]$Puerto = 8017
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$repo = Split-Path -Parent $raiz
$evidencia = Join-Path $raiz "docs\evidencia"
$python = Join-Path $raiz ".venv\Scripts\python.exe"
$composeHito7 = Join-Path $repo "Hito 7\docker-compose.yml"
$base = "http://127.0.0.1:$Puerto"
$salidaArchivo = Join-Path $evidencia "api_latencia.txt"
Set-Location $raiz

function Esperar-Api {
    for ($i = 0; $i -lt 40; $i++) {
        & curl.exe -s -o NUL --max-time 10 "$base/api/v1/salud"
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "La API no respondió en $base"
}

function Borrar-Cache {
    $ErrorActionPreference = "Continue"
    & docker compose -f $composeHito7 exec -T redis redis-cli DEL "fixture2030:h7:demo:cache:equipo:EQ-001" 2>&1 | Out-Null
}

function Percentil([double[]]$ordenados, [double]$p) {
    $indice = [Math]::Ceiling($p / 100 * $ordenados.Count) - 1
    return $ordenados[[Math]::Max(0, $indice)]
}

function Medir($caso) {
    $tiempos = New-Object System.Collections.Generic.List[double]
    $errores = 0
    for ($i = 0; $i -le $Repeticiones; $i++) {
        if ($caso.antes) { & $caso.antes }
        $argumentos = @("-s", "-o", "NUL", "--max-time", "15", "-w", "%{http_code} %{time_total}")
        if ($caso.sesion) { $argumentos += @("-H", "X-Session-Id: $($caso.sesion)") }
        $codigo, $tiempo = (& curl.exe @argumentos "$base$($caso.ruta)") -split ' '
        if ($i -eq 0) { continue }  # calentamiento
        if ($codigo -ne "$($caso.esperado)") { $errores++; continue }
        $tiempos.Add([double]::Parse($tiempo, [Globalization.CultureInfo]::InvariantCulture) * 1000)
    }
    $ordenados = [double[]]($tiempos | Sort-Object)
    if ($ordenados.Count -eq 0) {
        return "{0,-38} {1,5} {2,6}   sin respuestas con el código esperado" -f $caso.nombre, $ordenados.Count, $errores
    }
    return "{0,-38} {1,5} {2,6} {3,8:N1} {4,8:N1} {5,8:N1} {6,8:N1}" -f $caso.nombre, $ordenados.Count, $errores,
        $ordenados[0], (Percentil $ordenados 50), (Percentil $ordenados 95), $ordenados[-1]
}

# Ventana de la carga de muestra del Hito 8 (igual que evidencia_influx.ps1)
$muestra = Get-Content (Join-Path $repo "Hito 8\datos\muestra.json") -Raw | ConvertFrom-Json
$hasta = [DateTimeOffset]::FromUnixTimeSeconds($muestra.fin).UtcDateTime.ToString("yyyy-MM-ddTHH:mm:ssZ")
$desde = [DateTimeOffset]::FromUnixTimeSeconds($muestra.fin - 300).UtcDateTime.ToString("yyyy-MM-ddTHH:mm:ssZ")

& (Join-Path $PSScriptRoot "crear_sesiones_prueba.ps1") -BaseUrl $base | Out-Null
$sesiones = (Get-Content (Join-Path $raiz ".local\sesiones_prueba.json") -Raw -Encoding UTF8 | ConvertFrom-Json).sesiones
$lector = ($sesiones | Where-Object rol -eq "lector").sesionId

$casos = @(
    @{ nombre = "CU-01 equipo EQ-001 (Redis HIT)"; ruta = "/api/v1/equipos/EQ-001"; esperado = 200 },
    @{ nombre = "CU-01 equipo EQ-001 (MISS -> MongoDB)"; ruta = "/api/v1/equipos/EQ-001"; esperado = 200; antes = ${function:Borrar-Cache} },
    @{ nombre = "CU-03 plantel EQ-002 (MongoDB, 24)"; ruta = "/api/v1/equipos/EQ-002/jugadores"; esperado = 200 },
    @{ nombre = "CU-06 eventos PAR-001 (Neo4j)"; ruta = "/api/v1/partidos/PAR-001/eventos"; esperado = 200 },
    @{ nombre = "CU-08 comentarios minuto (Cassandra)"; ruta = "/api/v1/partidos/PAR-001/comentarios?minuto=2030-06-10T18:01:00Z"; esperado = 200 },
    @{ nombre = "CU-11 sesión vigente (Redis)"; ruta = "/api/v1/sesiones/actual"; esperado = 200; sesion = $lector },
    @{ nombre = "CU-16 comparación 5 min (InfluxDB)"; ruta = "/api/v1/partidos/PAR-001/estadisticas/comparacion?desde=$desde&hasta=$hasta"; esperado = 200 },
    @{ nombre = "CU-18 acta PAR-001 (IRIS)"; ruta = "/api/v1/partidos/PAR-001/acta"; esperado = 200 },
    @{ nombre = "CU-01 EQ-1 (400, sin consultar)"; ruta = "/api/v1/equipos/EQ-1"; esperado = 400 }
)

$marca = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1).Name.Trim()
$ramGb = [Math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
$so = (Get-CimInstance Win32_OperatingSystem).Caption
$versionPython = (& $python --version) -join ""
$dockerInfo = (& docker info --format "{{.ServerVersion}} · {{.NCPU}} CPU · {{.MemTotal}} bytes" 2>$null) -join ""

$filas = @()
$api = Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "$Puerto", "--log-level", "warning" `
    -WorkingDirectory $raiz -RedirectStandardError (Join-Path $raiz ".local\api_latencia.log") `
    -RedirectStandardOutput (Join-Path $raiz ".local\api_latencia.log.out") -PassThru -WindowStyle Hidden
try {
    Esperar-Api
    foreach ($caso in $casos) {
        Write-Host "Midiendo $($caso.nombre)…"
        $filas += Medir $caso
    }
} finally {
    Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
}

$contenido = @(
    "# API · Latencia de lectura por endpoint (RNF18)",
    "# Generado: $marca con scripts/medir_latencia.ps1 -Repeticiones $Repeticiones",
    "",
    "## Método",
    "- Cliente: curl.exe en la misma notebook, $Repeticiones requests secuenciales por endpoint después de 1 de calentamiento,",
    "  sin concurrencia y con una conexión TCP nueva por request. Métrica: time_total de curl, en milisegundos.",
    "- Percentiles por rango más cercano sobre las requests con el código HTTP esperado; las demás se cuentan en 'errores'.",
    "- API: uvicorn app.main:app, un proceso, sin --reload, log en nivel warning (sin log de acceso durante la medición).",
    "- CU-01 MISS borra la copia de Redis antes de cada request (docker compose exec, fuera del tiempo medido).",
    "",
    "## Entorno",
    "- Notebook: $so · $cpu · $ramGb GB de RAM.",
    "- $versionPython. Bases en Docker Desktop en la misma máquina (motor $dockerInfo), un nodo por motor,",
    "  con los puertos publicados en 127.0.0.1 y los timeouts de .env (casos_de_uso.md §6.3).",
    "",
    "## Volumen",
    "- Datos de muestra de los Hitos 4 a 9: 64 equipos y 1.536 jugadores (MongoDB), 64 partidos (Neo4j),",
    "  comentarios de muestra de PAR-001 (Cassandra), 300 muestras por equipo en la ventana de PAR-001 (InfluxDB,",
    "  [$desde, $hasta)) y un acta con dos eventos (IRIS).",
    "",
    "## Resultados (ms)",
    ("{0,-38} {1,5} {2,6} {3,8} {4,8} {5,8} {6,8}" -f "Endpoint", "n", "errores", "mín", "p50", "p95", "máx")
) + $filas + @(
    "",
    "## Limitaciones",
    "- Un solo cliente secuencial: no mide throughput ni comportamiento bajo concurrencia (uvicorn usa un threadpool",
    "  para las rutas síncronas; con muchas requests simultáneas la latencia puede ser otra).",
    "- Cliente, API y bases comparten CPU y RAM de la notebook; otros procesos influyen en las cifras.",
    "- Volúmenes de muestra, muy menores a los de producción; las cachés de cada motor están calientes.",
    "- Una sola corrida: las cifras sirven para comparar órdenes de magnitud entre fuentes, no como SLA."
)
$contenido | Out-File -FilePath $salidaArchivo -Encoding utf8
Write-Host "Resultado en $salidaArchivo"
