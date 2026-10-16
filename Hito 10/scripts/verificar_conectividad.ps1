<#
.SYNOPSIS
  Verifica la conectividad de la API con sus seis fuentes usando GET /api/v1/salud.

.DESCRIPTION
  Muestra el estado de cada dependencia y del catálogo de partidos y, para cada falla,
  qué contenedor levantar y con qué comando. No usa credenciales: solo consulta la API.
  Termina con código 0 si el estado es "ok" y 1 si está degradado o la API no responde.
  Ejecutar desde la carpeta "Hito 10":  .\scripts\verificar_conectividad.ps1 [-BaseUrl http://127.0.0.1:8000]
#>
param([string]$BaseUrl = "http://127.0.0.1:8000")

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

# Dependencia → hito, puerto en el host y pasos adicionales tras levantarla.
$fuentes = [ordered]@{
    mongodb   = @{ hito = "Hito 4"; puerto = "27017"; extra = "Si el volumen está vacío, cargar los datos con el procedimiento de Hito 4/README.md." }
    neo4j     = @{ hito = "Hito 5"; puerto = "7687";  extra = "Credenciales en Hito 5/.env; deben coincidir con NEO4J_USER/NEO4J_PASSWORD de Hito 10/.env." }
    cassandra = @{ hito = "Hito 6"; puerto = "9042";  extra = "Cassandra tarda 1-2 minutos en aceptar conexiones después de arrancar." }
    redis     = @{ hito = "Hito 7"; puerto = "16379"; extra = "La API usa el puerto 16379 del host, no 6379." }
    influxdb  = @{ hito = "Hito 8"; puerto = "8181";  extra = "El token se lee del archivo INFLUX_TOKEN_FILE (Hito 8/.local/admin.token)." }
    iris      = @{ hito = "Hito 9"; puerto = "1972";  extra = "Para CU-19 cargar además el envoltorio: .\scripts\cargar_servicio_iris.ps1" }
}

try {
    $salud = Invoke-RestMethod -Uri "$BaseUrl/api/v1/salud" -TimeoutSec 30
} catch {
    Write-Host "La API no responde en $BaseUrl." -ForegroundColor Red
    Write-Host "  Levantarla en otra terminal con: .\scripts\iniciar_api.ps1"
    exit 1
}

Write-Host "API en $BaseUrl · estado general: $($salud.estado)"
$fallas = 0
foreach ($nombre in $fuentes.Keys) {
    $estado = $salud.dependencias.$nombre
    $f = $fuentes[$nombre]
    switch ($estado) {
        "disponible" { Write-Host ("  [OK]    {0,-10} disponible" -f $nombre) -ForegroundColor Green }
        "no_configurada" {
            $fallas++
            Write-Host ("  [CONF]  {0,-10} no_configurada: revisar las variables de {0} en Hito 10/.env" -f $nombre) -ForegroundColor Yellow
        }
        default {
            $fallas++
            $compose = Join-Path $repo "$($f.hito)\docker-compose.yml"
            Write-Host ("  [FALLA] {0,-10} {1} (puerto {2} del host)" -f $nombre, $estado, $f.puerto) -ForegroundColor Red
            Write-Host "          Levantar el contenedor del $($f.hito):  docker compose -f `"$compose`" up -d"
            Write-Host "          Comprobar que publica el puerto:       docker compose -f `"$compose`" ps"
            Write-Host "          $($f.extra)"
        }
    }
}

$catalogo = $salud.catalogoPartidos
if ($catalogo.estado -eq "cargado") {
    Write-Host ("  [OK]    catálogo   {0} partidos, última carga {1}" -f $catalogo.partidos, $catalogo.ultimaCarga) -ForegroundColor Green
} else {
    $fallas++
    Write-Host "  [FALLA] catálogo   no_cargado: depende de Neo4j (Hito 5)." -ForegroundColor Red
    Write-Host "          Con Neo4j arriba, la API lo reintenta como máximo cada 30 s cuando llega una request"
    Write-Host "          de comentarios o estadísticas; mientras tanto esas rutas responden 503."
}

if ($fallas -eq 0 -and $salud.estado -eq "ok") {
    Write-Host "Todas las dependencias están disponibles." -ForegroundColor Green
    exit 0
}
Write-Host "$fallas problema(s) de conectividad." -ForegroundColor Yellow
exit 1
