[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"
Set-StrictMode -Version Latest

$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$EvidenceDir = Join-Path $ProjectDir "evidencias"
New-Item -ItemType Directory -Path $EvidenceDir -Force | Out-Null
Set-Location $ProjectDir

function Save-Evidence {
    param(
        [Parameter(Mandatory)] [string] $Name,
        [Parameter(Mandatory)] [scriptblock] $Action
    )

    $path = Join-Path $EvidenceDir $Name
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # Windows PowerShell transforma stderr nativo informativo de Docker en
        # NativeCommandError. Se silencia ese canal y se valida el exit code.
        $ErrorActionPreference = "SilentlyContinue"
        $output = @(& $Action 2>&1)
        $output | Out-File -LiteralPath $path -Encoding utf8
    }
    catch {
        $_ | Out-String | Add-Content -LiteralPath $path -Encoding utf8
        throw
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}

function Assert-LastExitCode {
    param([Parameter(Mandatory)] [string] $Operation)
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation falló con código $LASTEXITCODE."
    }
}

function Wait-MongoHealthy {
    for ($attempt = 1; $attempt -le 60; $attempt += 1) {
        $state = (& docker inspect --format '{{.State.Health.Status}}' fixture2030-mongodb 2>$null | Out-String).Trim()
        "Intento ${attempt}: health=$state"
        if ($state -eq "healthy") {
            return
        }
        Start-Sleep -Seconds 2
    }
    throw "MongoDB no alcanzó el estado healthy dentro del tiempo esperado."
}

function Invoke-MongoFile {
    param([Parameter(Mandatory)] [string] $ContainerPath)
    & docker compose exec -T mongodb mongosh --quiet `
        --username $script:MongoUser `
        --password $script:MongoPassword `
        --authenticationDatabase admin `
        fixture2030 `
        --file $ContainerPath
    Assert-LastExitCode "mongosh --file $ContainerPath"
}

function Invoke-MongoEval {
    param([Parameter(Mandatory)] [string] $Expression)
    & docker compose exec -T mongodb mongosh --quiet `
        --username $script:MongoUser `
        --password $script:MongoPassword `
        --authenticationDatabase admin `
        fixture2030 `
        --eval $Expression
    Assert-LastExitCode "mongosh --eval"
}

Save-Evidence "01_docker_compose_config.txt" {
    docker compose config --quiet
    Assert-LastExitCode "docker compose config"
    Write-Output "Configuracion Compose valida"
}

Save-Evidence "02_inicio_y_estado_contenedor.txt" {
    docker version --format 'Client={{.Client.Version}} Server={{.Server.Version}}'
    Assert-LastExitCode "docker version"
    docker compose version
    Assert-LastExitCode "docker compose version"
    docker compose up -d
    Assert-LastExitCode "docker compose up -d"
    Wait-MongoHealthy
    docker compose ps
    Assert-LastExitCode "docker compose ps"
}

$script:MongoUser = (& docker compose exec -T mongodb printenv MONGO_INITDB_ROOT_USERNAME | Out-String).Trim()
Assert-LastExitCode "lectura de MONGO_INITDB_ROOT_USERNAME"
$script:MongoPassword = (& docker compose exec -T mongodb printenv MONGO_INITDB_ROOT_PASSWORD | Out-String).Trim()
Assert-LastExitCode "lectura de MONGO_INITDB_ROOT_PASSWORD"

Save-Evidence "03_disponibilidad_mongodb.txt" {
    Invoke-MongoEval 'const ping = db.adminCommand({ ping: 1 }); print(EJSON.stringify({ database: db.getName(), ping, version: db.version() }, null, 2));'
}

Save-Evidence "04_inicializacion_e_indices.txt" {
    Invoke-MongoFile "/workspace/scripts/init/01_collections.js"
    Invoke-MongoFile "/workspace/scripts/validations/02_validators.js"
    Invoke-MongoFile "/workspace/scripts/indexes/03_indexes.js"
}

Save-Evidence "05_carga_inicial.txt" {
    Invoke-MongoFile "/workspace/scripts/data/02_seed.js"
}

Save-Evidence "06_segunda_carga_idempotente.txt" {
    Invoke-MongoFile "/workspace/scripts/data/02_seed.js"
}

Save-Evidence "07_integridad_validadores_indices.txt" {
    Invoke-MongoFile "/workspace/scripts/verification/07_verify_integrity.js"
}

Save-Evidence "08_rechazo_datos_invalidos.txt" {
    Invoke-MongoFile "/workspace/scripts/verification/08_test_validation.js"
}

Save-Evidence "09_operaciones_crud_controladas.txt" {
    Invoke-MongoFile "/workspace/scripts/operations/04_demo_crud.js"
}

Save-Evidence "10_consultas_y_agregaciones.txt" {
    Invoke-MongoFile "/workspace/scripts/queries/05_queries.js"
}

Save-Evidence "11_comparacion_rendimiento_indice.txt" {
    Invoke-MongoFile "/workspace/scripts/performance/06_compare_index.js"
}

Save-Evidence "12_integridad_canonica_final.txt" {
    Invoke-MongoFile "/workspace/scripts/verification/07_verify_integrity.js"
}

Save-Evidence "13_persistencia_despues_reinicio.txt" {
    docker compose restart mongodb
    Assert-LastExitCode "docker compose restart mongodb"
    Wait-MongoHealthy
    Invoke-MongoEval 'const ping = db.adminCommand({ ping: 1 }); print(EJSON.stringify({ afterRestart: true, ping, version: db.version() }, null, 2));'
    Invoke-MongoFile "/workspace/scripts/verification/07_verify_integrity.js"
}

Save-Evidence "14_estado_final_contenedor.txt" {
    docker compose ps
    Assert-LastExitCode "docker compose ps"
    docker inspect --format 'name={{.Name}} status={{.State.Status}} health={{.State.Health.Status}} restartCount={{.RestartCount}}' fixture2030-mongodb
    Assert-LastExitCode "docker inspect"
}

@(
    "Evidencias generadas: $((Get-Date).ToString('o'))",
    "Base: fixture2030",
    "Estado: todas las etapas finalizaron sin error",
    "Advertencia: este procedimiento nunca ejecuta docker compose down -v"
) | Out-File -LiteralPath (Join-Path $EvidenceDir "00_resumen_ejecucion.txt") -Encoding utf8

Write-Host "Evidencias generadas correctamente en $EvidenceDir"
