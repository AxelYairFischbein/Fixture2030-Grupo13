# Atajos del Hito 10. Uso: .\fixture.ps1 <comando>   (ver .\fixture.ps1 ayuda)
param(
    [ValidateSet('ayuda','todo','bases','esperar','verificar','api','abrir','influx','iris-usuario','pruebas','unitarias','latencia','detener')]
    [string]$Comando = 'ayuda'
)
$ErrorActionPreference = 'Stop'
$raiz = $PSScriptRoot
$repo = Split-Path -Parent $raiz
$hitos = 'Hito 4','Hito 5','Hito 6','Hito 7','Hito 8','Hito 9'
$py = Join-Path $raiz '.venv\Scripts\python.exe'
Set-Location -LiteralPath $raiz

function Venv {
    if (-not (Test-Path -LiteralPath $py)) {
        Write-Host 'Creando .venv e instalando dependencias (solo la primera vez)...'
        python -m venv .venv
        & $py -m pip install --disable-pip-version-check -q -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }
    }
}

function Env {
    if (-not (Test-Path -LiteralPath '.env')) { throw 'Falta .env: Copy-Item .env.example .env y completar las contraseñas.' }
}

function Bases {
    foreach ($h in $hitos) {
        Write-Host "Iniciando $h..."
        docker compose -f (Join-Path $repo "$h\docker-compose.yml") up -d
        if ($LASTEXITCODE -ne 0) { throw "No se pudo iniciar $h. ¿Docker Desktop está abierto?" }
    }
}

function Esperar {
    Env; Venv
    Write-Host 'Esperando a que respondan las seis bases (hasta 3 minutos)...'
    $limite = (Get-Date).AddMinutes(3)
    do {
        & $py -X utf8 scripts\verificar_conectividad.py
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Seconds 10
    } while ((Get-Date) -lt $limite)
    throw 'Alguna base no respondió. Revisar con: docker ps'
}

function Api { Env; Venv; Write-Host 'API en http://127.0.0.1:8000/  (Ctrl+C para detener)'; & $py -m uvicorn app.main:crear_app --factory --host 127.0.0.1 --port 8000 --no-access-log }

switch ($Comando) {
    'ayuda' {
        @'
Comandos (ejecutar dentro de "Hito 10"):
  .\fixture.ps1 todo          Inicia las 6 bases, espera a que respondan y levanta la API
  .\fixture.ps1 bases         Inicia los contenedores de los Hitos 4 a 9
  .\fixture.ps1 esperar       Repite la verificación hasta que respondan las 6 bases
  .\fixture.ps1 verificar     Estado y latencia de cada base (una vez)
  .\fixture.ps1 api           Levanta la API y la interfaz en http://127.0.0.1:8000/
  .\fixture.ps1 abrir         Abre la interfaz y Swagger en el navegador
  .\fixture.ps1 influx        Agrega puntos recientes a InfluxDB (si el gráfico sale vacío)
  .\fixture.ps1 iris-usuario  Crea el usuario IRIS de la API (una vez por instancia)
  .\fixture.ps1 pruebas       Pruebas unitarias + integración
  .\fixture.ps1 unitarias     Solo pruebas unitarias (no necesitan bases)
  .\fixture.ps1 latencia      Mide latencia (con la API levantada en otra terminal)
  .\fixture.ps1 detener       Detiene las 6 bases SIN borrar datos
'@
    }
    'todo'         { Bases; Esperar; Api }
    'bases'        { Bases }
    'esperar'      { Esperar }
    'verificar'    { Env; Venv; & $py -X utf8 scripts\verificar_conectividad.py }
    'api'          { Api }
    'abrir'        { Start-Process 'http://127.0.0.1:8000/'; Start-Process 'http://127.0.0.1:8000/docs' }
    'influx'       { Env; Venv; & $py -X utf8 scripts\cargar_muestra_influx.py }
    'iris-usuario' { & (Join-Path $raiz 'scripts\iris_crear_usuario_api.ps1') }
    'pruebas'      { Env; Venv; & (Join-Path $raiz 'scripts\ejecutar_pruebas.ps1') }
    'unitarias'    { Venv; & (Join-Path $raiz 'scripts\ejecutar_pruebas.ps1') -SoloUnitarias }
    'latencia'     { Venv; & $py -X utf8 scripts\medir_latencia.py }
    'detener'      { foreach ($h in $hitos) { docker compose -f (Join-Path $repo "$h\docker-compose.yml") stop } }
}
