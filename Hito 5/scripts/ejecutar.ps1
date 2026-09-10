param(
    [ValidateSet('esperar','estructura','carga','crud','consultas','analisis','verificar','plan','snapshot','browser')]
    [string]$Accion = 'verificar'
)
. "$PSScriptRoot/common.ps1"
if ($Accion -eq 'esperar') { (Wait-Neo4j).Text; exit 0 }
$files = @{
    estructura='01_constraints'; carga='02_load'; crud='03_crud'; consultas='04_graph_queries';
    analisis='05_analysis'; verificar='06_verify'; plan='08_index_plan'; snapshot='09_snapshot'; browser='07_browser'
}
$result = Invoke-Graph -File "queries/$($files[$Accion]).cypher" -VerboseFormat:($Accion -eq 'plan')
$result.Text
if ($Accion -eq 'verificar') { $null = Assert-Integrity $result.Text }
