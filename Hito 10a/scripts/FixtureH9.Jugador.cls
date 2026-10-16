Class FixtureH9.Jugador Extends FixtureH9.Persona
{

Property Numero As %Integer(MINVAL = 1, MAXVAL = 26) [ Required ];

Property Posicion As %String(VALUELIST = ",ARQUERO,DEFENSOR,MEDIOCAMPISTA,DELANTERO") [ Required ];

}
