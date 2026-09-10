Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:HitoRoot = Split-Path $PSScriptRoot -Parent
$script:Utf8 = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = $script:Utf8
[Console]::OutputEncoding = $script:Utf8

function Invoke-Docker {
    param([string[]]$Arguments, [string]$InputText, [switch]$AllowFailure)
    Push-Location $script:HitoRoot
    $previousPreference = $ErrorActionPreference
    try {
        # PS 5.1 representa stderr nativo como ErrorRecord aunque el comando tenga exito.
        $ErrorActionPreference = 'Continue'
        if ($PSBoundParameters.ContainsKey('InputText')) {
            $lines = @($InputText | & docker @Arguments 2>&1)
        } else {
            $lines = @(& docker @Arguments 2>&1)
        }
        $exitCode = $LASTEXITCODE
        $result = [pscustomobject]@{
            Command = 'docker ' + ($Arguments -join ' ')
            ExitCode = $exitCode
            Text = (($lines | ForEach-Object { $_.ToString() }) -join "`n")
        }
        if ($exitCode -ne 0 -and -not $AllowFailure) {
            throw "$($result.Command) fallo ($exitCode): $($result.Text)"
        }
        return $result
    } finally {
        $ErrorActionPreference = $previousPreference
        Pop-Location
    }
}

function Invoke-Graph {
    param([string]$File, [string]$Query, [switch]$VerboseFormat, [switch]$AllowFailure)
    $arguments = @('compose','exec','-T','neo4j','sh','/workspace/container/cypher.sh','--format')
    if ($VerboseFormat) { $arguments += 'verbose' } else { $arguments += 'plain' }
    if ($File) {
        if ($File -notmatch '^queries/[a-zA-Z0-9_]+\.cypher$') { throw 'Ruta Cypher no admitida.' }
        $arguments += @('-f',"/workspace/$File")
        return Invoke-Docker -Arguments $arguments -AllowFailure:$AllowFailure
    }
    return Invoke-Docker -Arguments $arguments -InputText $Query -AllowFailure:$AllowFailure
}

function Wait-Neo4j {
    param([int]$TimeoutSeconds = 300)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $r = Invoke-Graph -Query 'RETURN 1 AS disponible;' -AllowFailure
        if ($r.ExitCode -eq 0 -and $r.Text -match '(?m)^1$') { return $r }
        Start-Sleep -Seconds 3
    } while ((Get-Date) -lt $deadline)
    throw "Neo4j no disponible en $TimeoutSeconds segundos. Ultima respuesta: $($r.Text)"
}

function Get-QueryBlocks {
    param([string]$File)
    $content = [IO.File]::ReadAllText((Join-Path $script:HitoRoot $File))
    foreach ($m in [regex]::Matches($content,'(?ms)^// @query (\w+)\r?\n(.*?)(?=^// @query |\z)')) {
        [pscustomobject]@{ Code = $m.Groups[1].Value; Query = $m.Groups[2].Value.Trim() }
    }
}

function Assert-Integrity {
    param([string]$Text)
    $rows = @($Text | ConvertFrom-Csv)
    if ($rows.Count -ne 44 -or @($rows.control | Sort-Object -Unique).Count -ne 44) {
        throw 'El verificador debe devolver exactamente 44 controles diferentes.'
    }
    $failed = @($rows | Where-Object { $_.ok -ne 'true' })
    if ($failed.Count) { throw "Integridad fallida: $($failed | ConvertTo-Json -Compress)" }
    return $rows.Count
}

function Get-TextHash {
    param([string]$Text)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($script:Utf8.GetBytes($Text)))).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose() }
}
