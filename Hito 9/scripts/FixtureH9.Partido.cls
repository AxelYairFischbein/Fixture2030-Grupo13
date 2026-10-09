Class FixtureH9.Partido Extends %Persistent
{

Property Codigo As %String(MAXLEN = 24, COLLATION = "EXACT") [ Required ];

Property EstadioCodigo As %String(MAXLEN = 6) [ Required ];

Property Estado As %String(VALUELIST = ",PENDIENTE,EN_JUEGO,FINALIZADO") [ InitialExpression = "PENDIENTE", Required ];

Property Arbitro As FixtureH9.Arbitro [ Required ];

Relationship Eventos As FixtureH9.Evento [ Cardinality = children, Inverse = Partido ];

Index PorCodigo On Codigo [ Unique ];

/// Interfaz de escritura para transiciones. Devuelve el estado del guardado.
Method CambiarEstado(nuevo As %String) As %Status
{
    Set valido = ((..Estado = "PENDIENTE") && (nuevo = "EN_JUEGO")) || ((..Estado = "EN_JUEGO") && (nuevo = "FINALIZADO"))
    If 'valido {
        Quit $System.Status.Error(5001, "Transicion no permitida: "_..Estado_" -> "_nuevo)
    }
    Set anterior = ..Estado
    Set ..Estado = nuevo
    Set sc = ..%Save()
    If $System.Status.IsError(sc) { Set ..Estado = anterior }
    Quit sc
}

}
