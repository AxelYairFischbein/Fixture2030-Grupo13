/// Actas adicionales PAR-002..PAR-025 para la demostracion de la API.
/// Equipos y estadio siguen la carga del grafo (Hito 5): PAR-n enfrenta EQ-(2n-1) y EQ-(2n)
/// en EST-((n-1) mod 8 + 1). Jugadores y posiciones siguen la semilla del Hito 4.
/// Idempotente: omite los partidos que ya existen y nunca modifica PAR-001.
Class FixtureH9.Partidos Extends %RegisteredObject
{

ClassMethod Cargar(desde As %Integer = 2, hasta As %Integer = 25) As %Status
{
    Set sc = $$$OK, creados = 0
    Try {
        For n = desde:1:hasta {
            Set codigo = "PAR-"_$Translate($Justify(n, 3), " ", "0")
            If (n < 2) || ##class(FixtureH9.Partido).PorCodigoExists(codigo) {
                Write codigo, ": ya existe, se conserva", !
                Continue
            }
            Set local = 2 * n - 1, visitante = 2 * n
            Set p = ##class(FixtureH9.Partido).%New()
            Set p.Codigo = codigo
            Set p.EstadioCodigo = "EST-0"_((n - 1) # 8 + 1)
            Set p.Arbitro = ..Arbitro(n # 5 + 2)
            // Gol del local, tarjeta al visitante, cambio del local y, en partidos pares, gol visitante.
            Do ..Evento(p, "GOL", 10 + (n * 7 # 30), local, 20 + (n # 5))
            Do ..Evento(p, "TARJETA", 30 + (n * 3 # 15), visitante, 4 + (n # 8))
            Do ..Evento(p, "CAMBIO", 60 + (n # 10), local, 12 + (n # 8))
            If n # 2 = 0 { Do ..Evento(p, "GOL", 70 + (n # 20), visitante, 20 + (n + 2 # 5)) }
            Do ..Exigir(p.%Save())  // un solo guardado del arbol: partido y eventos
            // Estados variados para mostrar transiciones, siempre mediante la regla del dominio.
            Set destino = n # 3
            If destino >= 1 { Do ..Exigir(p.CambiarEstado("EN_JUEGO")) }
            If destino = 2 { Do ..Exigir(p.CambiarEstado("FINALIZADO")) }
            Write codigo, ": creado | ", p.EstadioCodigo, " | ", p.Estado, " | eventos=", p.Eventos.Count(), !
            Set creados = creados + 1
        }
        Write "PARTIDOS CREADOS: ", creados, !
    } Catch ex {
        Set sc = ex.AsStatus()
    }
    Quit sc
}

ClassMethod Evento(p As FixtureH9.Partido, tipo As %String, minuto As %Integer, equipo As %Integer, camiseta As %Integer)
{
    Set e = ##class(FixtureH9.Evento).%New()
    Set e.Tipo = tipo, e.Minuto = minuto, e.Jugador = ..Jugador(equipo, camiseta)
    Do ..Exigir(p.Eventos.Insert(e))
}

/// Jugador con el codigo, nombre y posicion de la semilla del Hito 4. Reutiliza el existente.
ClassMethod Jugador(equipo As %Integer, camiseta As %Integer) As FixtureH9.Jugador
{
    Set num = (equipo - 1) * 24 + camiseta, sufijo = $Translate($Justify(num, 4), " ", "0")
    Set j = ##class(FixtureH9.Jugador).PorCodigoOpen("JUG-"_sufijo)
    Quit:$IsObject(j) j
    Set j = ##class(FixtureH9.Jugador).%New()
    Set j.Codigo = "JUG-"_sufijo, j.Nombre = "Nombre"_sufijo_" Apellido"_sufijo
    Set j.Nacionalidad = "F"_$Translate($Justify(equipo, 2), " ", "0"), j.Numero = camiseta
    Set j.Posicion = $Select(camiseta <= 3: "ARQUERO", camiseta <= 11: "DEFENSOR", camiseta <= 19: "MEDIOCAMPISTA", 1: "DELANTERO")
    Do ..Exigir(j.%Save())
    Quit j
}

ClassMethod Arbitro(k As %Integer) As FixtureH9.Arbitro
{
    Set sufijo = $Translate($Justify(k, 3), " ", "0")
    Set a = ##class(FixtureH9.Arbitro).PorCodigoOpen("ARB-"_sufijo)
    Quit:$IsObject(a) a
    Set a = ##class(FixtureH9.Arbitro).%New()
    Set a.Codigo = "ARB-"_sufijo, a.Nombre = "Arbitro Sintetico "_$Extract(sufijo, 2, 3)
    Set a.Nacionalidad = "F"_(50 + k), a.Licencia = "LIC-DEMO-"_sufijo
    Do ..Exigir(a.%Save())
    Quit a
}

ClassMethod Exigir(sc As %Status)
{
    If $System.Status.IsError(sc) { $$$ThrowStatus(sc) }
}

}
