/// Servicio del Hito 10 sobre el modelo del Hito 9 (namespace USER).
/// Lo invoca la API REST con el SDK nativo de Python (CU-19). No modifica las
/// clases FixtureH9: solo las usa. El estado se cambia unicamente con
/// FixtureH9.Partido.CambiarEstado(), nunca con UPDATE SQL.
Class FixtureH10.Servicio Extends %RegisteredObject
{

/// La API la consulta para comprobar que este envoltorio esta cargado.
Parameter VERSION = "1";

/// Codigo de error con que FixtureH9.Partido.CambiarEstado() rechaza una transicion.
Parameter ERRORREGLA = 5001;

ClassMethod Version() As %String
{
    Quit ..#VERSION
}

/// Cambia el estado del partido con codigo de negocio `codigo` a `nuevo`.
/// Localiza el partido por el indice PorCodigo, toma un bloqueo exclusivo que espera
/// como maximo `espera` segundos, vuelve a leer el estado bajo el bloqueo y recien
/// entonces decide. Devuelve "RESULTADO|anterior|actual", con RESULTADO en:
///   OK                      la transicion se aplico y se guardo
///   SIN_CAMBIO              el estado ya era `nuevo`; no se llamo a CambiarEstado
///   NO_ENCONTRADO           no existe un Partido con ese codigo
///   TRANSICION_NO_PERMITIDA CambiarEstado rechazo la transicion; el estado no cambio
///   BLOQUEADO               otro proceso retiene el partido; no se aplico nada
///   ERROR                   cualquier otra falla; el detalle no sale de IRIS
/// No devuelve IDs internos.
ClassMethod Transicionar(codigo As %String, nuevo As %String, espera As %Integer = 2) As %String
{
    If '##class(FixtureH9.Partido).PorCodigoExists(codigo, .id) { Quit "NO_ENCONTRADO||" }
    Set sc = ##class(FixtureH9.Partido).%LockId(id, 0, espera)
    If $System.Status.IsError(sc) { Quit "BLOQUEADO||" }
    Set resultado = "ERROR||"
    Try {
        // Se abre despues de bloquear: el estado leido es el vigente.
        Set p = ##class(FixtureH9.Partido).%OpenId(id, 0, .sc)
        If '$IsObject(p) {
            // Borrado entre la busqueda por codigo y el bloqueo.
            Set resultado = "NO_ENCONTRADO||"
        } ElseIf p.Estado = nuevo {
            Set resultado = "SIN_CAMBIO|"_p.Estado_"|"_p.Estado
        } Else {
            Set anterior = p.Estado
            Set sc = p.CambiarEstado(nuevo)
            If $System.Status.IsOK(sc) {
                Set resultado = "OK|"_anterior_"|"_p.Estado
            } ElseIf ..EsRechazoDeRegla(sc) {
                // CambiarEstado no guardo: el estado persistido sigue siendo el anterior.
                Set resultado = "TRANSICION_NO_PERMITIDA|"_anterior_"|"_anterior
            }
        }
    } Catch {
        Set resultado = "ERROR||"
    }
    Do ##class(FixtureH9.Partido).%UnlockId(id, 0)
    Quit resultado
}

/// Distingue el rechazo de la regla de transicion de una falla de guardado.
ClassMethod EsRechazoDeRegla(sc As %Status) As %Boolean [ Private ]
{
    Quit ($System.Status.GetErrorCodes(sc) = ..#ERRORREGLA) && ($System.Status.GetErrorText(sc) [ "Transicion no permitida")
}

}
