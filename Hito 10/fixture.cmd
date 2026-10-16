@echo off
rem Ejecuta fixture.ps1 sin depender de la politica de ejecucion de PowerShell.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0fixture.ps1" %*
