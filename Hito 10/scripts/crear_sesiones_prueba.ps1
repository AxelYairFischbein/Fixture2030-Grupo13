<#
.SYNOPSIS
  Crea tres sesiones de prueba en el Redis del Hito 7 (roles lector, moderador y operador).

.DESCRIPTION
  La API no crea sesiones (casos_de_uso.md §7.2: el login queda fuera del módulo). Este
  script las crea con la misma estructura del Hito 7 (Hash sesion_id, usuario_id,
  ultima_actividad, estado, rol y TTL en un único EVAL, como carga_muestra.redis) sin
  modificar archivos del Hito 7.

  Los IDs de sesión son credenciales:
  - se generan al azar en cada ejecución (RandomNumberGenerator, 128 bits);
  - se escriben solo en Hito 10/.local/sesiones_prueba.json y en el entorno de Postman
    Hito 10/.local/postman_entorno_local.json, ambos ignorados por git (el script se
    detiene si .local/ no está ignorado);
  - en la consola se muestran enmascarados (SES-PRUEBA-3f9a…);
  - las sesiones de la ejecución anterior se eliminan con DEL antes de crear las nuevas.

  No usa credenciales: ejecuta redis-cli con docker compose exec dentro del contenedor.
  Ejecutar desde la carpeta "Hito 10":  .\scripts\crear_sesiones_prueba.ps1
#>
param(
    [string]$Prefijo = "fixture2030:h7:demo:",
    [ValidateRange(1, 86400)][int]$TtlSegundos = 1800,
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$carpetaLocal = Join-Path $raiz ".local"
$archivoSesiones = Join-Path $carpetaLocal "sesiones_prueba.json"
$archivoPostman = Join-Path $carpetaLocal "postman_entorno_local.json"
$composeHito7 = Join-Path (Split-Path -Parent $raiz) "Hito 7\docker-compose.yml"

# Mismo EVAL que Hito 7/scripts/carga_muestra.redis, con valores por argumento.
$luaCrear = "local t=redis.call('TIME')[1]; redis.call('HSET',KEYS[1],'sesion_id',ARGV[1],'usuario_id',ARGV[2],'ultima_actividad',t,'estado','activa','rol',ARGV[3]); redis.call('EXPIRE',KEYS[1],ARGV[4]); return redis.call('TTL',KEYS[1])"

$roles = @(
    @{ rol = "lector";    usuarioId = "USR-00001"; variable = "sesionLector" },
    @{ rol = "moderador"; usuarioId = "USR-00002"; variable = "sesionModerador" },
    @{ rol = "operador";  usuarioId = "USR-00003"; variable = "sesionOperador" }
)

function Redis-Cli([string[]]$argumentos) {
    # En PowerShell 5.1 lo que docker escribe en stderr se vuelve un error terminante
    # con ErrorActionPreference=Stop: se relaja solo para esta llamada.
    $ErrorActionPreference = "Continue"
    $salida = & docker compose -f $composeHito7 exec -T redis redis-cli @argumentos 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0 -or ($salida -match "^(ERR|WRONGTYPE|NOSCRIPT|\(error\))")) {
        throw "redis-cli falló. ¿Está levantado el Redis del Hito 7? (docker compose -f `"$composeHito7`" up -d)"
    }
    return $salida
}

function Nuevo-IdSesion {
    $bytes = New-Object byte[] 16
    $generador = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generador.GetBytes($bytes) } finally { $generador.Dispose() }
    return "SES-PRUEBA-" + (($bytes | ForEach-Object { $_.ToString("x2") }) -join "")
}

function Enmascarar([string]$sesionId) {
    return $sesionId.Substring(0, 15) + "…"
}

function Escribir-Json([string]$ruta, $objeto) {
    # UTF-8 sin BOM para que Postman y json.load lo lean sin problemas.
    $json = $objeto | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText($ruta, $json, (New-Object System.Text.UTF8Encoding $false))
}

# 1. .local/ tiene que estar ignorado por git antes de escribir credenciales.
New-Item -ItemType Directory -Force $carpetaLocal | Out-Null
& git -C $raiz check-ignore -q (Join-Path $carpetaLocal "sesiones_prueba.json")
if ($LASTEXITCODE -ne 0) {
    throw "Hito 10/.local/ no está ignorado por git: revisar .gitignore antes de generar sesiones."
}

# 2. Comprobar el contenedor.
if ((Redis-Cli @("PING")) -notcontains "PONG") { throw "Redis del Hito 7 no respondió PONG." }

# 3. Cerrar las sesiones de la ejecución anterior (DEL es idempotente).
if (Test-Path $archivoSesiones) {
    $anteriores = Get-Content $archivoSesiones -Raw -Encoding UTF8 | ConvertFrom-Json
    $claves = @($anteriores.sesiones | ForEach-Object { "$($anteriores.prefijo)sesion:$($_.sesionId)" })
    if ($claves.Count -gt 0) {
        $borradas = Redis-Cli (@("DEL") + $claves)
        Write-Host "Sesiones anteriores eliminadas: $borradas de $($claves.Count) (las vencidas ya no existían)."
    }
}

# 4. Crear las sesiones nuevas.
$creadas = @()
foreach ($r in $roles) {
    $sesionId = Nuevo-IdSesion
    $ttl = Redis-Cli @("EVAL", $luaCrear, "1", "${Prefijo}sesion:$sesionId", $sesionId, $r.usuarioId, $r.rol, "$TtlSegundos")
    if ([int]($ttl | Select-Object -Last 1) -le 0) { throw "La sesión $($r.rol) quedó sin TTL." }
    $creadas += [ordered]@{
        rol       = $r.rol
        usuarioId = $r.usuarioId
        sesionId  = $sesionId
        expiraEn  = (Get-Date).ToUniversalTime().AddSeconds($TtlSegundos).ToString("yyyy-MM-ddTHH:mm:ssZ")
        variable  = $r.variable
    }
}

# 5. Archivos locales (ignorados por git).
Escribir-Json $archivoSesiones ([ordered]@{
    generado = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    prefijo  = $Prefijo
    ttlSegundos = $TtlSegundos
    sesiones = @($creadas | ForEach-Object { [ordered]@{ rol = $_.rol; usuarioId = $_.usuarioId; sesionId = $_.sesionId; expiraEn = $_.expiraEn } })
})

$valores = @([ordered]@{ key = "baseUrl"; value = $BaseUrl; type = "default"; enabled = $true })
$valores += @($creadas | ForEach-Object { [ordered]@{ key = $_.variable; value = $_.sesionId; type = "secret"; enabled = $true } })
Escribir-Json $archivoPostman ([ordered]@{
    id     = [guid]::NewGuid().ToString()
    name   = "Fixture 2030 H10 - local"
    values = $valores
    _postman_variable_scope = "environment"
})

Write-Host "Sesiones creadas (TTL $TtlSegundos s, prefijo $Prefijo):"
foreach ($c in $creadas) {
    Write-Host ("  {0,-10} {1}  {2}  variable Postman: {3}" -f $c.rol, $c.usuarioId, (Enmascarar $c.sesionId), $c.variable)
}
Write-Host "IDs completos solo en: $archivoSesiones"
Write-Host "Entorno de Postman:    $archivoPostman"
