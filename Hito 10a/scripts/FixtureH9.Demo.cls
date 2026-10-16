Class FixtureH9.Demo Extends %RegisteredObject
{

/// Ejecuta la muestra y las comprobaciones. Detiene el flujo ante un fallo.
ClassMethod Ejecutar() As %Status
{
    Try {
        Write "Hito 9 | ", $ZDateTime($Horolog, 3), " | namespace ", $Namespace, !
        Write $ZVersion, !
        Do ..CrearMuestra()
        Do ..Exigir(..Verificar())
        Do ..ProbarAtomicidad()
        Do ..ProbarTransicionesYBorrado()
        Write "DEMO OK: muestra conservada, validaciones y borrado comprobados.", !
    } Catch error {
        Return error.AsStatus()
    }
    Quit 1
}

ClassMethod CrearMuestra()
{
    If ##class(FixtureH9.Partido).PorCodigoExists("PAR-001") {
        Write "Muestra existente: no se vuelve a cargar.", !
        Quit
    }
    Do ..Afirmar('##class(FixtureH9.Persona).PorCodigoExists("JUG-0001"), "Jugador preexistente sin muestra. Revisar sin sobrescribir.")
    Do ..Afirmar('##class(FixtureH9.Persona).PorCodigoExists("ARB-001"), "Arbitro preexistente sin muestra. Revisar sin sobrescribir.")
    Set j = ##class(FixtureH9.Jugador).%New()
    Set j.Codigo = "JUG-0001", j.Nombre = "Nombre0001 Apellido0001", j.Nacionalidad = "F01"
    Set j.Numero = 1, j.Posicion = "ARQUERO"
    Set a = ##class(FixtureH9.Arbitro).%New()
    Set a.Codigo = "ARB-001", a.Nombre = "Arbitro Sintetico 01", a.Nacionalidad = "F01", a.Licencia = "LIC-DEMO-001"
    Set p = ..Arbol("PAR-001", j, a)
    // Un solo guardado alcanza al padre, los dos hijos y las personas referenciadas.
    Do ..Exigir(p.%Save())
    Write "Un %Save del padre: Partido ID=", p.%Id(), ", eventos=", p.Eventos.Count(), !
}

ClassMethod Arbol(codigo As %String, j As FixtureH9.Jugador, a As FixtureH9.Arbitro, invalido As %Boolean = 0) As FixtureH9.Partido
{
    Set p = ##class(FixtureH9.Partido).%New()
    Set p.Codigo = codigo, p.EstadioCodigo = "EST-01", p.Arbitro = a
    For n = 1:1:2 {
        Set e = ##class(FixtureH9.Evento).%New()
        Set e.Minuto = $Select(n=1:15, 1:75), e.Jugador = j
        If '(invalido && (n=2)) { Set e.Tipo = $Select(n=1:"TARJETA", 1:"CAMBIO") }
        Do ..Exigir(p.Eventos.Insert(e))
    }
    Quit p
}

/// Solo lectura. Tambien se ejecuta despues de recrear, sin importar ni cargar.
ClassMethod Verificar() As %Status
{
    Try {
        Do ..Afirmar(##class(FixtureH9.Partido).PorCodigoExists("PAR-001", .id), "No existe PAR-001.")
        Set p = ##class(FixtureH9.Partido).%OpenId(id,,.sc)
        Do ..Exigir(sc)
        Do ..Afirmar((p.Codigo="PAR-001") && (p.EstadioCodigo="EST-01") && (p.Estado="PENDIENTE"), "Atributos inesperados en la muestra.")
        Do ..Afirmar(p.Eventos.Count()=2, "Se esperaban dos eventos.")
        Write "OBJ Partido ID=", id, " | ", p.Codigo, " | ", p.EstadioCodigo, " | ", p.Estado, !
        Set a = p.Arbitro
        Do ..Afirmar(a.%IsA("FixtureH9.Persona") && a.%IsA("FixtureH9.Arbitro"), "Herencia de Arbitro incorrecta.")
        Do ..Afirmar((a.Codigo="ARB-001") && (a.Licencia="LIC-DEMO-001"), "Arbitro inesperado.")
        Write "OBJ Arbitro ID=", a.%Id(), " | ", a.Codigo, " | ", a.Nombre, " | ", a.Licencia, !
        Set clave = "", cantidad = 0
        For {
            Set e = p.Eventos.GetNext(.clave)
            Quit:clave=""
            Do ..Afirmar(e.Partido.%Id()=id, "La referencia inversa no coincide.")
            Do ..Afirmar(((e.Minuto=15)&&(e.Tipo="TARJETA")) || ((e.Minuto=75)&&(e.Tipo="CAMBIO")), "Evento inesperado.")
            Set j = e.Jugador
            Do ..Afirmar(j.%IsA("FixtureH9.Persona") && j.%IsA("FixtureH9.Jugador"), "Herencia de Jugador incorrecta.")
            Do ..Afirmar((j.Codigo="JUG-0001") && (j.Numero=1) && (j.Posicion="ARQUERO"), "Jugador inesperado.")
            Set eventos(e.%Id()) = $ListBuild(e.Tipo,e.Minuto,j.%Id())
            Set cantidad = cantidad + 1
            Write "OBJ Evento ID=", e.%Id(), " | ", e.Tipo, " | minuto=", e.Minuto, " | inversa Partido=", e.Partido.%Id(), !
        }
        Do ..Afirmar(cantidad=2, "Navegacion incompleta.")
        Write "OBJ Jugador ID=", j.%Id(), " | ", j.Codigo, " | ", j.Nombre, " | ", j.Posicion, !
        Set rs = ..Consulta("SELECT ID, Codigo, EstadioCodigo, Estado, Arbitro FROM FixtureH9.Partido WHERE ID = ?", id)
        Do ..Afirmar(rs.%Next(), "Falta la fila SQL del partido.")
        Do ..Afirmar((rs.%Get("Codigo")=p.Codigo) && (rs.%Get("EstadioCodigo")=p.EstadioCodigo) && (rs.%Get("Estado")=p.Estado) && (rs.%Get("Arbitro")=a.%Id()), "Partido SQL diferente del objeto.")
        Write "SQL Partido ID=", rs.%Get("ID"), " | ", rs.%Get("Codigo"), " | ", rs.%Get("Estado"), !
        Set rs = ..Consulta("SELECT ID, Partido, Tipo, Minuto, Jugador FROM FixtureH9.Evento WHERE Partido = ? ORDER BY Minuto", id)
        Set cantidad = 0
        While rs.%Next() {
            Set eid = rs.%Get("ID")
            Do ..Afirmar($Data(eventos(eid)), "Evento SQL ausente de la navegacion.")
            Do ..Afirmar((rs.%Get("Partido")=id) && (eventos(eid)=$ListBuild(rs.%Get("Tipo"),rs.%Get("Minuto"),rs.%Get("Jugador"))), "Evento SQL diferente del objeto.")
            Write "SQL Evento ID=", eid, " | Partido=", rs.%Get("Partido"), " | ", rs.%Get("Tipo"), " | minuto=", rs.%Get("Minuto"), !
            Set cantidad = cantidad + 1
        }
        Do ..Afirmar(cantidad=2, "Recuento SQL de eventos incorrecto.")
        For n = 1:1:2 {
            Set persona = $Select(n=1:j, 1:a)
            Set rs = ..Consulta("SELECT ID, Codigo, Nombre, Nacionalidad FROM FixtureH9.Persona WHERE ID = ?", persona.%Id())
            Do ..Afirmar(rs.%Next(), "Falta la persona en SQL.")
            Do ..Afirmar((rs.%Get("Codigo")=persona.Codigo) && (rs.%Get("Nombre")=persona.Nombre) && (rs.%Get("Nacionalidad")=persona.Nacionalidad), "Persona SQL diferente del objeto.")
            Write "SQL Persona ID=", rs.%Get("ID"), " | ", rs.%Get("Codigo"), " | ", rs.%Get("Nombre"), !
        }
        Write "VERIFICACION OK: 1 partido, 2 eventos, 1 jugador y 1 arbitro. Objetos = SQL.", !
    } Catch error {
        Return error.AsStatus()
    }
    Quit 1
}

ClassMethod ProbarAtomicidad()
{
    Do ..Afirmar('##class(FixtureH9.Partido).PorCodigoExists("H9-INVALIDO"), "Ya existe H9-INVALIDO. Revisar sin borrar.")
    Set j = ##class(FixtureH9.Jugador).PorCodigoOpen("JUG-0001",,.sc)
    Do ..Exigir(sc)
    Set a = ##class(FixtureH9.Arbitro).PorCodigoOpen("ARB-001",,.sc)
    Do ..Exigir(sc)
    Set antes = ..ContarEventos(j.%Id())
    Set p = ..Arbol("H9-INVALIDO", j, a, 1)
    Set sc = p.%Save()
    Do ..Afirmar($System.Status.IsError(sc), "El hijo sin Tipo fue aceptado.")
    Write "RECHAZO ESPERADO: hijo sin Tipo obligatorio. ", $System.Status.GetErrorText(sc), !
    Do ..Afirmar('##class(FixtureH9.Partido).PorCodigoExists("H9-INVALIDO"), "Quedo un padre parcial.")
    Set despues = ..ContarEventos(j.%Id())
    Do ..Afirmar(antes=despues, "Quedaron hijos parciales.")
    Write "ATOMICIDAD OK: padre invalido ausente, eventos antes=", antes, ", despues=", despues, ". Ningun hijo nuevo.", !
}

ClassMethod ProbarTransicionesYBorrado()
{
    Do ..Afirmar('##class(FixtureH9.Partido).PorCodigoExists("H9-TEMPORAL"), "Ya existe H9-TEMPORAL. Revisar sin borrar.")
    Set j = ##class(FixtureH9.Jugador).PorCodigoOpen("JUG-0001",,.sc)
    Do ..Exigir(sc)
    Set a = ##class(FixtureH9.Arbitro).PorCodigoOpen("ARB-001",,.sc)
    Do ..Exigir(sc)
    Set p = ..Arbol("H9-TEMPORAL", j, a)
    Do ..Exigir(p.%Save())
    Set id = p.%Id()
    Do ..Exigir(p.CambiarEstado("EN_JUEGO"))
    Do ..Exigir(p.CambiarEstado("FINALIZADO"))
    Set sc = p.CambiarEstado("EN_JUEGO")
    Do ..Afirmar($System.Status.IsError(sc), "Se permitio reabrir un partido finalizado.")
    Write "TRANSICIONES OK: PENDIENTE -> EN_JUEGO -> FINALIZADO.", !
    Write "RECHAZO ESPERADO: ", $System.Status.GetErrorText(sc), !
    Set rs = ..Consulta("SELECT Estado FROM FixtureH9.Partido WHERE ID = ?", id)
    Do ..Afirmar(rs.%Next(), "No existe el partido temporal.")
    Do ..Afirmar((rs.%Get("Estado")="FINALIZADO") && (p.Estado="FINALIZADO"), "El rechazo modifico el estado.")
    Write "SQL estado posterior al rechazo: ", rs.%Get("Estado"), !
    Set clave = "", n = 0
    For {
        Set e = p.Eventos.GetNext(.clave)
        Quit:clave=""
        Set n = n+1, hijos(n) = e.%Id()
    }
    Do ..Afirmar(n=2, "Arbol temporal incompleto.")
    Set e = "", p = ""
    Do ..Exigir(##class(FixtureH9.Partido).%DeleteId(id))
    Do ..Afirmar('##class(FixtureH9.Partido).%ExistsId(id), "No se borro el padre temporal.")
    For n = 1:1:2 { Do ..Afirmar('##class(FixtureH9.Evento).%ExistsId(hijos(n)), "Sobrevivio un hijo temporal.") }
    Do ..Afirmar(..ContarEventos(j.%Id())=2, "Se alteraron los eventos de la muestra.")
    Do ..Afirmar(##class(FixtureH9.Partido).PorCodigoExists("PAR-001"), "Se altero el partido principal.")
    Do ..Afirmar(##class(FixtureH9.Jugador).%ExistsId(j.%Id()) && ##class(FixtureH9.Arbitro).%ExistsId(a.%Id()), "Se borraron personas independientes.")
    Write "BORRADO OK: padre temporal y sus 2 hijos ausentes. Muestra y personas conservadas.", !
}

ClassMethod ContarEventos(jugador As %String) As %Integer
{
    Set rs = ..Consulta("SELECT COUNT(*) AS Total FROM FixtureH9.Evento WHERE Jugador = ?", jugador)
    Do ..Afirmar(rs.%Next(), "No se obtuvo el recuento.")
    Quit rs.%Get("Total")
}

ClassMethod Consulta(sql As %String, valor As %String) As %SQL.StatementResult
{
    Set rs = ##class(%SQL.Statement).%ExecDirect(, sql, valor)
    Do ..Afirmar(rs.%SQLCODE >= 0, "Error SQL: "_rs.%Message)
    Quit rs
}

ClassMethod Exigir(sc As %Status)
{
    If $System.Status.IsError(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
}

ClassMethod Afirmar(condicion As %Boolean, mensaje As %String)
{
    If 'condicion { Do ..Exigir($System.Status.Error(5001, mensaje)) }
}

}
