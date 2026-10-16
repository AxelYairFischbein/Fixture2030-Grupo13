Class FixtureH9.Persona Extends %Persistent
{

Property Codigo As %String(MAXLEN = 16, COLLATION = "EXACT") [ Required ];

Property Nombre As %String(MAXLEN = 80) [ Required ];

Property Nacionalidad As %String(MINLEN = 3, MAXLEN = 3) [ Required ];

// Evita duplicar personas y permite localizar la muestra por su codigo.
Index PorCodigo On Codigo [ Unique ];

}
