# Crea o actualiza el usuario IRIS que utiliza la API (rol propio y SELECT sobre FixtureH9).
# Lee IRIS_USER e IRIS_PASSWORD de .env. La contraseña se envía por stdin al Terminal del
# contenedor del Hito 9: no aparece en argumentos de procesos, logs ni en el repositorio.
$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $raiz '.env'
if (-not (Test-Path -LiteralPath $envFile)) { throw 'Falta .env. Copiar .env.example como .env y completar IRIS_PASSWORD.' }
$cfg = @{}
Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^\s*([A-Z_]+)=(.*)$' } | ForEach-Object { $cfg[$Matches[1]] = $Matches[2].Trim() }
$usuario = $cfg['IRIS_USER']; $clave = $cfg['IRIS_PASSWORD']
if (-not $usuario -or -not $clave) { throw 'Completar IRIS_USER e IRIS_PASSWORD en .env.' }
if ($usuario -notmatch '^[A-Za-z_][A-Za-z0-9_]{2,30}$' -or $clave -notmatch '^[A-Za-z0-9]{12,64}$') {
    throw 'IRIS_USER o IRIS_PASSWORD con formato no admitido (usar letras y numeros, clave de 12 a 64).'
}

# Rol mínimo: datos de USER y ejecución nativa de métodos (CambiarEstado) desde el driver.
$objectscript = @"
If '##class(Security.Roles).Exists("fixture_api_rol") { Do ##class(Security.Roles).Create("fixture_api_rol","API Hito 10","%DB_USER:RW,%Native_ClassExecution:U") }
If ##class(Security.Users).Exists("$usuario") { Set p("Password")="$clave", p("Roles")="fixture_api_rol", p("ChangePassword")=0, p("Enabled")=1  Set sc=##class(Security.Users).Modify("$usuario",.p) } Else { Set sc=##class(Security.Users).Create("$usuario","fixture_api_rol","$clave","API Hito 10","USER","","",0,1) }
Write "USUARIO STATUS=", +sc, !
ZN "USER"
Set r=##class(%SQL.Statement).%ExecDirect(,"GRANT SELECT ON SCHEMA FixtureH9 TO $usuario")
Write "GRANT SQLCODE=", r.%SQLCODE, !
Halt
"@
# PowerShell 5.1 antepone un BOM al stdin de procesos nativos si no se fija la codificación.
$OutputEncoding = New-Object System.Text.UTF8Encoding $false
$compose = Join-Path (Split-Path -Parent $raiz) 'Hito 9\docker-compose.yml'
$objectscript | docker compose -f $compose exec -T iris iris session IRIS -U %SYS | Select-String -Pattern 'USUARIO|GRANT'
