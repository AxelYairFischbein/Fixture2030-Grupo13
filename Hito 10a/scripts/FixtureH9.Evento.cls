Class FixtureH9.Evento Extends %Persistent
{

Property Tipo As %String(VALUELIST = ",GOL,TARJETA,CAMBIO") [ Required ];

Property Minuto As %Integer(MINVAL = 0, MAXVAL = 130) [ Required ];

Property Jugador As FixtureH9.Jugador [ Required ];

Relationship Partido As FixtureH9.Partido [ Cardinality = parent, Inverse = Eventos ];

// Respalda la recuperacion de los eventos relacionados con un partido.
Index PorPartido On Partido;

}
