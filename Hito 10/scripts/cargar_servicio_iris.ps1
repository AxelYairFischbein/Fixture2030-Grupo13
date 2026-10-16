<#
.SYNOPSIS
  Carga y compila Hito 10/iris/FixtureH10.Servicio.cls en el IRIS del Hito 9 (namespace USER).

.DESCRIPTION
  Ejecuta scripts/cargar_servicio_iris.py, que envía el texto de la clase por el SDK de
  Python con las credenciales de Hito 10/.env (IRIS_USER, IRIS_PASSWORD) y la compila.
  No copia archivos al contenedor, no abre el Terminal y no toca el paquete FixtureH9.
  Es repetible: volver a ejecutarlo reemplaza la clase por la versión del repositorio.
  Ejecutar desde la carpeta "Hito 10":  .\scripts\cargar_servicio_iris.ps1
#>
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$python = Join-Path $raiz ".venv\Scripts\python.exe"
Set-Location $raiz
& $python (Join-Path $PSScriptRoot "cargar_servicio_iris.py")
if ($LASTEXITCODE -ne 0) { throw "No se pudo cargar FixtureH10.Servicio (ver el mensaje anterior)." }
