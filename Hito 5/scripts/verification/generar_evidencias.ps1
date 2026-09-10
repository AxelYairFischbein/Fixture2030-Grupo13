#requires -Version 5.1
param()
. "$PSScriptRoot/../common.ps1"
$runId = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$evidenceRoot = Join-Path $script:HitoRoot 'docs/evidencia'
$runDirectory = Join-Path $evidenceRoot $runId
$null = New-Item -ItemType Directory -Path $runDirectory -Force
$steps = New-Object System.Collections.Generic.List[object]
$summary = [ordered]@{ inicioUtc=$runId; estado='EN_CURSO'; directorio=$runId; pasos=$steps }
function Save-Step {
    param([string]$Name, $Result, [string]$Query = '')
    [IO.File]::WriteAllText((Join-Path $runDirectory "$Name.txt"), $Result.Text+"`n", $script:Utf8)
    $steps.Add([pscustomobject]@{ evidencia="$Name.txt"; utc=[DateTime]::UtcNow.ToString('o'); comando=$Result.Command; consulta=$Query; exitCode=$Result.ExitCode })
    Write-Host "Registrado: $Name (exit $($Result.ExitCode))"
    if ($Result.ExitCode -ne 0) { throw "Fallo en $Name. Revisar $runDirectory/$Name.txt" }
    return $Result.Text
}
function Run-File {
    param([string]$Name,[string]$File,[switch]$VerboseFormat)
    return Save-Step $Name (Invoke-Graph -File $File -VerboseFormat:$VerboseFormat -AllowFailure)
}
function Verify-Step {
    param([string]$Name)
    $t = Run-File $Name 'queries/06_verify.cypher'
    return Assert-Integrity $t
}
try {
    # Se redaccionan los valores de autenticacion de la salida REAL de config.
    $config = Invoke-Docker @('compose','config') -AllowFailure
    $config.Text = [regex]::Replace($config.Text,'(?m)^(\s*NEO4J_AUTH:\s*).+$','$1[REDACTADO]')
    $null = Save-Step '01_compose_config' $config
    $null = Save-Step '02_inicio' (Invoke-Docker @('compose','up','-d') -AllowFailure)
    $null = Save-Step '03_disponibilidad' (Wait-Neo4j)
    $null = Save-Step '04_estado_inicial' (Invoke-Docker @('compose','ps') -AllowFailure)
    $version = Save-Step '05_version' (Invoke-Graph -Query 'CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition;' -AllowFailure)
    $summary.version = $version
    $null = Save-Step '05_imagen' (Invoke-Docker @('image','inspect','neo4j:latest','--format','{{json .RepoDigests}}') -AllowFailure)
    $null = Save-Step '05_montajes' (Invoke-Docker @('inspect',((Invoke-Docker @('compose','ps','-q','neo4j')).Text.Trim()),'--format','{{json .Mounts}}') -AllowFailure)
    $null = Run-File '06_estructura' 'queries/01_constraints.cypher'
    $schemaQuery = "SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties RETURN name, type, labelsOrTypes, properties ORDER BY name;"
    $schema = Save-Step '06_restricciones' (Invoke-Graph -Query $schemaQuery -AllowFailure) $schemaQuery
    if (@($schema | ConvertFrom-Csv).Count -ne 6) { throw 'Se esperaban seis restricciones.' }
    $indexQuery = 'SHOW INDEXES YIELD name, state, type RETURN name, state, type ORDER BY name;'
    $indexes = Save-Step '06_indices' (Invoke-Graph -Query $indexQuery -AllowFailure) $indexQuery
    $indexRows = @($indexes | ConvertFrom-Csv)
    if (@($indexRows | Where-Object { $_.state -ne 'ONLINE' }).Count -or -not ($indexRows.name -contains 'idx_partido_inicio')) { throw 'Indices no disponibles.' }
    $countQuery = 'MATCH (n) RETURN count(n) AS nodosAntes;'
    $null = Save-Step '07_antes_carga' (Invoke-Graph -Query $countQuery -AllowFailure) $countQuery
    $null = Run-File '08_primera_carga' 'queries/02_load.cypher' -VerboseFormat
    $summary.controlesIntegridad = Verify-Step '09_integridad_primera'
    $first = Run-File '10_snapshot_primera' 'queries/09_snapshot.cypher'
    $null = Run-File '11_segunda_carga' 'queries/02_load.cypher' -VerboseFormat
    $null = Verify-Step '12_integridad_segunda'
    $second = Run-File '13_snapshot_segunda' 'queries/09_snapshot.cypher'
    $summary.hashPrimera = Get-TextHash $first
    $summary.hashSegunda = Get-TextHash $second
    if ($first -cne $second) { throw 'La segunda carga modifico el contenido del grafo.' }
    $summary.idempotencia = 'OK: contenido completo y recuentos identicos'
    # Seis rechazos independientes, dentro de transacciones que nunca se confirman.
    $cases = @(
        @{codigo='N01'; cypher="CREATE (:Equipo {equipoId:'EQ-001'});"},
        @{codigo='N02'; cypher="CREATE (:Equipo {codigo:'F01'});"},
        @{codigo='N03'; cypher="CREATE (:Jugador {jugadorId:'JUG-0001'});"},
        @{codigo='N04'; cypher="CREATE (:Partido {partidoId:'PAR-001'});"},
        @{codigo='N05'; cypher="CREATE (:Estadio {estadioId:'EST-01'});"},
        @{codigo='N06'; cypher="CREATE (:EventoDeportivo {eventoId:'EVT-PAR-001-LOCAL'});"}
    )
    foreach ($case in $cases) {
        $query = ":begin`n$($case.cypher)`n:rollback"
        $negative = Invoke-Graph -Query $query -AllowFailure
        [IO.File]::WriteAllText((Join-Path $runDirectory "$($case.codigo)_rechazo.txt"),$negative.Text+"`n",$script:Utf8)
        $steps.Add([pscustomobject]@{evidencia="$($case.codigo)_rechazo.txt";utc=[DateTime]::UtcNow.ToString('o');comando=$negative.Command;consulta=$query;exitCode=$negative.ExitCode})
        if ($negative.ExitCode -eq 0 -or $negative.Text -notmatch 'already exists|ConstraintValidationFailed|constraint') { throw "No se comprobo rechazo de $($case.codigo)." }
    }
    $summary.rechazosUnicidad = 6
    $crud = Run-File '14_crud' 'queries/03_crud.cypher'
    foreach ($pattern in @('"C01_preexistentes", 0, 0','"C02_creado", 1, 1','"C04_actualizado", 72, 72','"C05_reasignado", "JUG-0022", "JUG-0022"','"C07_eliminado", 1, 1','"C07_residuos", 0, 0')) {
        if (-not $crud.Contains($pattern)) { throw "CRUD no verificable: $pattern" }
    }
    $null = Verify-Step '15_integridad_post_crud'
    $postCrud = Run-File '16_snapshot_post_crud' 'queries/09_snapshot.cypher'
    if ($first -cne $postCrud) { throw 'CRUD o pruebas negativas alteraron el canon.' }
    $summary.crud = 'OK: altas, lectura, cambios y bajas; canon identico'
    $expected = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'resultados_esperados.json') -Encoding UTF8 -Raw | ConvertFrom-Json
    $queryResults = New-Object System.Collections.Generic.List[object]
    foreach ($file in @('queries/04_graph_queries.cypher','queries/05_analysis.cypher')) {
        foreach ($block in Get-QueryBlocks $file) {
            $t = Save-Step $block.Code (Invoke-Graph -Query $block.Query -AllowFailure) $block.Query
            $rows = @($t | ConvertFrom-Csv)
            $exp = $expected.PSObject.Properties[$block.Code].Value
            if ($rows.Count -ne $exp.filas) { throw "$($block.Code): cantidad de filas incorrecta." }
            foreach ($field in $exp.columnas.PSObject.Properties) {
                $actualValues = @($rows | ForEach-Object { $_.PSObject.Properties[$field.Name].Value })
                if (($actualValues -join '|') -cne ($field.Value -join '|')) { throw "$($block.Code): valores incorrectos para $($field.Name)." }
            }
            $queryResults.Add([pscustomobject]@{codigo=$block.Code;filas=$rows.Count;estado='OK';resultado=$rows})
        }
    }
    $summary.consultas = $queryResults
    $null = Run-File '24_browser_consultas' 'queries/07_browser.cypher'
    $null = Run-File '17_plan_indice' 'queries/08_index_plan.cypher' -VerboseFormat
    $null = Save-Step '18_reinicio' (Invoke-Docker @('compose','restart','neo4j') -AllowFailure)
    $null = Save-Step '19_disponibilidad_reinicio' (Wait-Neo4j)
    $null = Verify-Step '20_integridad_persistencia'
    $afterRestart = Run-File '21_snapshot_persistencia' 'queries/09_snapshot.cypher'
    $summary.hashPersistencia = Get-TextHash $afterRestart
    if ($first -cne $afterRestart) { throw 'El contenido cambio despues del reinicio.' }
    $summary.persistencia = 'OK: contenido completo y recuentos identicos despues del reinicio'
    # La consulta puede responder antes del proximo healthcheck del contenedor.
    $healthDeadline = (Get-Date).AddSeconds(60)
    do {
        $id = (Invoke-Docker @('compose','ps','-q','neo4j')).Text.Trim()
        $health = Invoke-Docker @('inspect',$id,'--format','{{.State.Health.Status}}')
        if ($health.Text.Trim() -eq 'healthy') { break }
        Start-Sleep -Seconds 3
    } while ((Get-Date) -lt $healthDeadline)
    if ($health.Text.Trim() -ne 'healthy') { throw 'El contenedor no finalizo saludable.' }
    $null = Save-Step '22_salud_final' $health
    $null = Save-Step '23_estado_final' (Invoke-Docker @('compose','ps') -AllowFailure)
    $http = Invoke-WebRequest -Uri 'http://localhost:7474/browser/' -UseBasicParsing
    $bolt = Test-NetConnection -ComputerName localhost -Port 7687 -WarningAction SilentlyContinue
    if ($http.StatusCode -ne 200 -or -not $bolt.TcpTestSucceeded) { throw 'HTTP o Bolt no disponibles.' }
    $summary.browserHttp = $http.StatusCode
    $summary.boltTcp = $bolt.TcpTestSucceeded
    $summary.estado = 'OK'
} catch {
    $summary.estado = 'FALLO'
    $summary.error = $_.Exception.Message
    throw
} finally {
    $summary.finUtc = [DateTime]::UtcNow.ToString('o')
    $json = $summary | ConvertTo-Json -Depth 15
    [IO.File]::WriteAllText((Join-Path $runDirectory '00_resumen.json'),$json+"`n",$script:Utf8)
    if ($summary.estado -eq 'OK') {
        [IO.File]::WriteAllText((Join-Path $evidenceRoot 'ultima_ejecucion.json'),$json+"`n",$script:Utf8)
    }
    Write-Host "Estado: $($summary.estado). Evidencias: $runDirectory"
}
