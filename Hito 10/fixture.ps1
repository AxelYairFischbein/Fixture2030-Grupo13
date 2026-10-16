# Atajos del Hito 10. Solo requiere Windows + Docker Desktop (Python no hace falta).
# Uso: .\fixture.cmd <comando>    o    powershell -ExecutionPolicy Bypass -File .\fixture.ps1 <comando>
param(
    [ValidateSet('ayuda','todo','preparar','api','abrir','estado','verificar','influx','pruebas','unitarias','latencia','logs','detener')]
    [string]$Comando = 'ayuda'
)
# 'Continue': en PowerShell 5.1 la salida de error de docker no debe cortar el script; se controla $LASTEXITCODE.
$ErrorActionPreference = 'Continue'
$OutputEncoding = New-Object System.Text.UTF8Encoding $false   # sin BOM en el stdin de docker
$raiz = $PSScriptRoot
$repo = Split-Path -Parent $raiz
Set-Location -LiteralPath $raiz

$HITOS = [ordered]@{
    'Hito 4' = @{ servicio = 'mongodb';   puertos = 27017 }
    'Hito 5' = @{ servicio = 'neo4j';     puertos = 7474, 7687 }
    'Hito 6' = @{ servicio = 'cassandra'; puertos = 9042 }
    'Hito 7' = @{ servicio = 'redis';     puertos = 16379 }
    'Hito 8' = @{ servicio = 'influxdb';  puertos = 8181 }
    'Hito 9' = @{ servicio = 'iris';      puertos = 1972, 52773 }
}

function Paso($texto) { Write-Host "`n== $texto" -ForegroundColor Cyan }
function Fallar($texto) { Write-Host "ERROR: $texto" -ForegroundColor Red; exit 1 }
function Compose($hito) { , @('compose', '-f', (Join-Path $repo "$hito\docker-compose.yml")) }
function Dc($hito) { $a = Compose $hito; $input | & docker @a @args }   # $input reenvía el stdin recibido por tubería
function Esperar($descripcion, [scriptblock]$prueba, [int]$segundos = 240) {
    $limite = (Get-Date).AddSeconds($segundos)
    Write-Host -NoNewline "Esperando $descripcion"
    while ((Get-Date) -lt $limite) {
        if (& $prueba) { Write-Host ' listo'; return }
        Write-Host -NoNewline '.'
        Start-Sleep -Seconds 5
    }
    Fallar "$descripcion no respondió en $segundos s. Revisar: docker ps y docker logs."
}

function Docker-Listo {
    docker info *> $null
    if ($LASTEXITCODE -ne 0) { Fallar 'Docker no responde. Abrir Docker Desktop, esperar a que diga "Engine running" y repetir.' }
}

function Revisar-Puertos {
    # Un puerto ocupado por un proceso que no es Docker impediría iniciar la base correspondiente.
    $docker = 'com.docker.backend', 'wslrelay', 'vpnkit', 'docker', 'dockerd', 'com.docker.proxy'
    foreach ($hito in $HITOS.Keys) {
        foreach ($p in $HITOS[$hito].puertos) {
            $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($c) {
                $proc = (Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue).ProcessName
                if ($proc -and $docker -notcontains $proc) { Fallar "El puerto $p ($hito) está ocupado por '$proc'. Cerrar ese programa y repetir." }
            }
        }
    }
    $c = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c) {
        $proc = (Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue).ProcessName
        if ($proc -and $docker -notcontains $proc) { Fallar "El puerto 8000 (API) está ocupado por '$proc'. Si es una API iniciada a mano, cerrarla con Ctrl+C." }
    }
}

function Leer-Env($ruta) {
    $v = @{}
    if (Test-Path -LiteralPath $ruta) {
        Get-Content -LiteralPath $ruta | Where-Object { $_ -match '^\s*([A-Z0-9_]+)=(.*)$' } | ForEach-Object { $v[$Matches[1]] = $Matches[2].Trim() }
    }
    $v
}

function Preparar-Archivos {
    Paso 'Archivos locales'
    foreach ($d in 'cassandra', 'influxdb', 'iris') { New-Item -ItemType Directory -Force -Path (Join-Path $env:USERPROFILE "docker\data\$d") | Out-Null }
    New-Item -ItemType Directory -Force -Path (Join-Path $repo 'Hito 8\.local') | Out-Null
    $env5 = Join-Path $repo 'Hito 5\.env'
    if (-not (Test-Path -LiteralPath $env5)) { Copy-Item (Join-Path $repo 'Hito 5\.env.example') $env5; Write-Host 'Creado Hito 5\.env desde su ejemplo.' }
    if (-not (Test-Path -LiteralPath '.env')) {
        $h4 = Leer-Env (Join-Path $repo 'Hito 4\.env')
        $neo = (Leer-Env $env5)['NEO4J_AUTH']
        $clave = 'Api' + (-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ }))
        $texto = (Get-Content -LiteralPath '.env.example' -Raw) `
            -replace '(?m)^MONGO_USER=.*$', "MONGO_USER=$(if ($h4['MONGO_ROOT_USERNAME']) { $h4['MONGO_ROOT_USERNAME'] } else { 'admin' })" `
            -replace '(?m)^MONGO_PASSWORD=.*$', "MONGO_PASSWORD=$(if ($h4['MONGO_ROOT_PASSWORD']) { $h4['MONGO_ROOT_PASSWORD'] } else { 'password123' })" `
            -replace '(?m)^NEO4J_PASSWORD=.*$', "NEO4J_PASSWORD=$($neo.Split('/', 2)[1])" `
            -replace '(?m)^IRIS_PASSWORD=.*$', "IRIS_PASSWORD=$clave"
        [IO.File]::WriteAllText((Join-Path $raiz '.env'), $texto, (New-Object System.Text.UTF8Encoding $false))
        Write-Host 'Creado Hito 10\.env con las credenciales de laboratorio y una clave IRIS aleatoria.'
    }
}

function Iniciar-Bases {
    Paso 'Contenedores de los Hitos 4 a 9'
    foreach ($hito in $HITOS.Keys) {
        Dc $hito up -d
        if ($LASTEXITCODE -ne 0) { Fallar "No se pudo iniciar $hito." }
    }
}

function Cargar-Mongo {
    Paso 'MongoDB (Hito 4)'
    # Sin comillas dobles dentro de los argumentos: PowerShell 5.1 no las escapa al llamar a docker.
    $mongo = { param($extra) Dc 'Hito 4' exec -T mongodb sh -c "mongosh --quiet -u `$MONGO_INITDB_ROOT_USERNAME -p `$MONGO_INITDB_ROOT_PASSWORD --authenticationDatabase admin fixture2030 $extra" }
    Esperar 'MongoDB' { (& $mongo "--eval 'db.adminCommand({ping:1}).ok'" 2>$null) -match '1' }
    foreach ($f in 'init/01_collections.js', 'validations/02_validators.js', 'indexes/03_indexes.js', 'data/02_seed.js') {
        & $mongo "--file /workspace/scripts/$f" | Out-Null
        if ($LASTEXITCODE -ne 0) { Fallar "Falló $f" }
    }
    Write-Host 'Muestra cargada (64 equipos, 1.536 jugadores; carga idempotente).'
}

function Cargar-Neo4j {
    Paso 'Neo4j (Hito 5)'
    $cypher = { param($extra) Dc 'Hito 5' exec -T neo4j sh -c "cypher-shell -u neo4j -p `${NEO4J_AUTH#*/} -d neo4j --format plain $extra" }
    Esperar 'Neo4j' { (& $cypher "'RETURN 1 AS ok'" 2>$null) -match '1' }
    foreach ($f in '01_constraints', '02_load') {
        & $cypher "-f /workspace/queries/$f.cypher" | Out-Null
        if ($LASTEXITCODE -ne 0) { Fallar "Falló $f.cypher" }
    }
    Write-Host 'Grafo cargado (MERGE idempotente).'
}

function Cargar-Cassandra {
    Paso 'Cassandra (Hito 6)'
    Esperar 'Cassandra (el primer arranque tarda 1-2 minutos)' { Dc 'Hito 6' exec -T cassandra cqlsh -e 'SHOW VERSION' *> $null; $LASTEXITCODE -eq 0 } 300
    foreach ($f in 'esquema.cql', 'carga_muestra.cql') {
        Dc 'Hito 6' exec -T cassandra cqlsh -f "/scripts/$f" | Out-Null
        if ($LASTEXITCODE -ne 0) { Fallar "Falló $f" }
    }
    Write-Host 'Esquema y 12 comentarios de muestra cargados.'
}

function Preparar-Iris {
    Paso 'IRIS (Hito 9)'
    $sano = { (docker inspect -f '{{.State.Health.Status}}' (Dc 'Hito 9' ps -q iris) 2>$null) -eq 'healthy' }
    $limite = (Get-Date).AddSeconds(300)
    $ajustado = $false
    Write-Host -NoNewline 'Esperando IRIS'
    while (-not (& $sano)) {
        # Carpeta durable nueva: IRIS no puede hacer chown (procedimiento documentado en el Hito 9).
        # Una sola vez: docker logs conserva el error de arranques anteriores.
        if (-not $ajustado -and (Dc 'Hito 9' logs --tail 40 iris 2>&1 | Out-String) -match 'Error executing chown') {
            Write-Host ' ajustando propietario de /durable'
            Dc 'Hito 9' exec -T --user root iris chown 51773:51773 /durable
            if ($LASTEXITCODE -eq 0) { $ajustado = $true; Dc 'Hito 9' restart iris | Out-Null }
            Start-Sleep -Seconds 10
        }
        if ((Get-Date) -gt $limite) { Fallar 'IRIS no quedó healthy. Revisar: docker compose -f "..\Hito 9\docker-compose.yml" logs iris' }
        Write-Host -NoNewline '.'
        Start-Sleep -Seconds 5
    }
    Write-Host ' listo'
    # Primera línea vacía: si PowerShell antepone un BOM, queda en una línea sin instrucciones.
    $os = @'

Set sc =$System.OBJ.LoadDir("/scripts", "ck-d", .errores)
Write "COMPILACION=", +sc, !
If '##class(FixtureH9.Partido).PorCodigoExists("PAR-001") { Set sc = ##class(FixtureH9.Demo).Ejecutar() Write "DEMO=", +sc, ! }
Halt
'@
    $salida = $os | Dc 'Hito 9' exec -T iris iris session IRIS -U USER | Out-String
    if ($salida -notmatch 'COMPILACION=1' -or $salida -match 'DEMO=0') { Write-Host $salida; Fallar 'No se pudieron compilar o cargar las clases FixtureH9.' }
    Write-Host 'Clases compiladas y muestra PAR-001 disponible.'
    & (Join-Path $raiz 'scripts\iris_crear_usuario_api.ps1')
}

function Influx-Cli($token) {
    # El token viaja por stdin, nunca como argumento.
    # PowerShell 5.1 agrega BOM y CRLF al stdin: se conservan solo caracteres válidos de token.
    # Sin comillas dobles en el argumento: PowerShell 5.1 no las escapa al llamar a docker.
    $token | Dc 'Hito 8' exec -T influxdb sh -c 'INFLUXDB3_AUTH_TOKEN=$(head -n 1 | tr -cd A-Za-z0-9_=+/.-); export INFLUXDB3_AUTH_TOKEN; exec influxdb3 $@' sh @args
}

function Preparar-Influx {
    Paso 'InfluxDB (Hito 8)'
    Esperar 'InfluxDB' {
        try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:8181/health | Out-Null; $true }
        catch { $_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401 }
    }
    $archivo = Join-Path $repo 'Hito 8\.local\admin.token'
    if (-not (Test-Path -LiteralPath $archivo)) {
        $json = Dc 'Hito 8' exec -T influxdb influxdb3 create token --admin --format json | Out-String
        if ($LASTEXITCODE -ne 0) { Fallar 'No se pudo crear el token de InfluxDB. Si el nodo ya tenía uno, copiarlo a Hito 8\.local\admin.token.' }
        [IO.File]::WriteAllText($archivo, ($json | ConvertFrom-Json).token + "`n", (New-Object System.Text.UTF8Encoding $false))
        Write-Host 'Token creado en Hito 8\.local\admin.token (no se muestra).'
    }
    $token = (Get-Content -LiteralPath $archivo -Raw).Trim()
    $bases = Influx-Cli $token show databases --format json | Out-String
    if ($LASTEXITCODE -ne 0) { Fallar 'El token de Hito 8\.local\admin.token no es válido para esta instancia.' }
    if ($bases -notmatch 'fixture2030_h8') {
        Influx-Cli $token create database --retention-period 7d fixture2030_h8 | Out-Null
        Write-Host 'Base fixture2030_h8 creada con retención de 7 días.'
    }
}

function Api-Arriba {
    Paso 'API (contenedor grupo13-hito10-api)'
    docker compose up -d --build api
    if ($LASTEXITCODE -ne 0) { Fallar 'No se pudo construir o iniciar la API.' }
    Esperar 'la API' { try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 http://127.0.0.1:8000/api/v1/salud).StatusCode -eq 200 } catch { $false } } 120
}

function En-Api { docker compose run --rm api @args }

switch ($Comando) {
    'ayuda' {
        @'
Hito 10 - requiere solo Windows + Docker Desktop. Ejecutar dentro de la carpeta "Hito 10":

  .\fixture.cmd todo        Prepara todo (bases, datos, credenciales), levanta la API y abre el navegador
  .\fixture.cmd preparar    Solo prepara bases y datos (idempotente: se puede repetir)
  .\fixture.cmd api         (Re)construye y levanta la API en http://127.0.0.1:8000/
  .\fixture.cmd abrir       Abre la interfaz y Swagger
  .\fixture.cmd estado      Contenedores y salud de la API
  .\fixture.cmd verificar   Conectividad y latencia de cada base
  .\fixture.cmd influx      Agrega 30 minutos de estadísticas recientes (si el gráfico sale vacío)
  .\fixture.cmd pruebas     Pruebas unitarias + integración (dentro del contenedor)
  .\fixture.cmd unitarias   Solo pruebas unitarias
  .\fixture.cmd latencia    Medición de latencia
  .\fixture.cmd logs        Logs de la API (Ctrl+C para salir)
  .\fixture.cmd detener     Detiene API y bases SIN borrar datos
'@
    }
    'todo' {
        Docker-Listo; Revisar-Puertos; Preparar-Archivos; Iniciar-Bases
        Cargar-Mongo; Cargar-Neo4j; Cargar-Cassandra; Preparar-Influx; Preparar-Iris
        Api-Arriba
        Paso 'Estadísticas recientes en InfluxDB'; En-Api python scripts/cargar_muestra_influx.py
        Paso 'Listo'
        Write-Host 'Interfaz: http://127.0.0.1:8000/    Swagger: http://127.0.0.1:8000/docs' -ForegroundColor Green
        Start-Process 'http://127.0.0.1:8000/'
    }
    'preparar' {
        Docker-Listo; Revisar-Puertos; Preparar-Archivos; Iniciar-Bases
        Cargar-Mongo; Cargar-Neo4j; Cargar-Cassandra; Preparar-Influx; Preparar-Iris
    }
    'api'       { Docker-Listo; Api-Arriba; Write-Host 'http://127.0.0.1:8000/' -ForegroundColor Green }
    'abrir'     { Start-Process 'http://127.0.0.1:8000/'; Start-Process 'http://127.0.0.1:8000/docs' }
    'estado'    {
        docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
        try { Write-Host "API /salud: $((Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 http://127.0.0.1:8000/api/v1/salud).StatusCode)" }
        catch { Write-Host 'API /salud: no responde o alguna base está caída (ver .\fixture.cmd verificar)' }
    }
    'verificar' { En-Api python scripts/verificar_conectividad.py }
    'influx'    { En-Api python scripts/cargar_muestra_influx.py }
    'pruebas'   { En-Api python -m pytest -p no:cacheprovider tests -v; exit $LASTEXITCODE }
    'unitarias' { En-Api python -m pytest -p no:cacheprovider tests/unit -v; exit $LASTEXITCODE }
    'latencia'  { En-Api python scripts/medir_latencia.py --url http://host.docker.internal:8000 }
    'logs'      { docker compose logs -f api }
    'detener'   {
        docker compose stop
        foreach ($hito in $HITOS.Keys) { Dc $hito stop }
        Write-Host 'Detenido. Los datos se conservan (no usar "down -v").'
    }
}
