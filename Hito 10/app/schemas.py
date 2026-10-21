"""Modelos de request y response. Son la fuente del contrato OpenAPI."""

from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

# Patrones de identificadores del Fixture (Hitos 4 a 9). Se validan antes de consultar.
EQUIPO_ID = r"^EQ-\d{3}$"
PARTIDO_ID = r"^PAR-\d{3}$"
USUARIO_ID = r"^USR-\d{5}$"
SESION_ID = r"^SES-[0-9a-f]{24}$"
ACTA_CODIGO = r"^[A-Z0-9][A-Z0-9-]{2,23}$"
IDEMPOTENCY_KEY = r"^[A-Za-z0-9-]{8,64}$"
CURSOR = r"^\d{13}_[A-Za-z0-9-]{1,64}$"


class Confederacion(str, Enum):
    AFC = "AFC"
    CAF = "CAF"
    CONCACAF = "CONCACAF"
    CONMEBOL = "CONMEBOL"
    OFC = "OFC"
    UEFA = "UEFA"


class Posicion(str, Enum):
    ARQUERO = "ARQUERO"
    DEFENSOR = "DEFENSOR"
    MEDIOCAMPISTA = "MEDIOCAMPISTA"
    DELANTERO = "DELANTERO"


class Intervalo(str, Enum):
    s10 = "10s"
    s30 = "30s"
    m1 = "1m"
    m5 = "5m"


class EstadoPartido(str, Enum):
    PENDIENTE = "PENDIENTE"
    EN_JUEGO = "EN_JUEGO"
    FINALIZADO = "FINALIZADO"


# --- Envoltorio común ----------------------------------------------------------------
class Traza(BaseModel):
    fuente: str = Field(examples=["mongodb"])
    operacion: str = Field(examples=["buscar_equipo"])
    resultado: str = Field(examples=["ok"])
    ms: float


class Paginacion(BaseModel):
    pagina: int | None = None
    tamanio: int | None = None
    total: int | None = None
    siguienteCursor: str | None = None


class Meta(BaseModel):
    requestId: str
    fuentes: list[Traza] = Field(description="Operaciones realmente ejecutadas contra cada fuente en este request.")
    paginacion: Paginacion | None = None
    cache: str | None = Field(None, description="HIT, MISS o BYPASS (Redis no disponible).")


class Respuesta(BaseModel, Generic[T]):
    data: T
    meta: Meta


class ErrorDetalle(BaseModel):
    codigo: str = Field(examples=["RECURSO_NO_ENCONTRADO"])
    mensaje: str = Field(examples=["No existe el equipo EQ-999."])
    requestId: str
    dependencia: str | None = Field(None, examples=["mongodb"])
    detalles: list[dict] | None = None


class ErrorRespuesta(BaseModel):
    error: ErrorDetalle


# --- MongoDB ---------------------------------------------------------------------------
class EquipoResumen(BaseModel):
    equipoId: str
    codigo: str
    nombre: str
    confederacion: Confederacion
    rankingReferencia: int
    estado: str


class Sede(BaseModel):
    ciudad: str
    pais: str


class Equipo(EquipoResumen):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "equipoId": "EQ-001", "codigo": "F01", "nombre": "Seleccion Sintetica 01", "confederacion": "AFC",
        "region": "ASIA_PACIFICO", "rankingReferencia": 1, "estado": "PRESELECCIONADO",
        "sedeBase": {"ciudad": "Ciudad Sintetica 01", "pais": "Pais Sintetico 01"},
        "participacionesMundiales": 1, "titulosMundiales": 0, "actualizadoEn": "2026-09-02T00:00:00Z"}]})
    region: str
    sedeBase: Sede
    participacionesMundiales: int
    titulosMundiales: int
    actualizadoEn: str


class Jugador(BaseModel):
    jugadorId: str
    equipoId: str
    nombre: str
    apellido: str
    posicion: Posicion
    numeroCamiseta: int
    fechaNacimiento: str
    alturaCm: int
    pieHabil: str
    partidosInternacionales: int
    golesInternacionales: int
    estadoPlantel: str


# --- Neo4j ----------------------------------------------------------------------------
class EquipoEnPartido(BaseModel):
    equipoId: str
    codigo: str
    nombre: str
    rol: str = Field(examples=["LOCAL"])


class Estadio(BaseModel):
    estadioId: str
    nombre: str
    ciudad: str


class Involucrado(BaseModel):
    jugadorId: str
    nombre: str
    apellido: str
    rol: str = Field(examples=["SALE"])


class EventoPartido(BaseModel):
    eventoId: str
    tipo: str
    minuto: int
    involucrados: list[Involucrado]


class Partido(BaseModel):
    partidoId: str
    grupo: str
    fase: str
    estado: str
    jornada: int
    inicio: str
    estadio: Estadio | None
    equipos: list[EquipoEnPartido]
    eventos: list[EventoPartido]


class PartidoAgenda(BaseModel):
    partidoId: str
    grupo: str
    estado: str
    inicio: str
    rol: str
    estadioId: str
    rivalId: str | None


# --- Cassandra ------------------------------------------------------------------------
class Comentario(BaseModel):
    comentarioId: str
    usuarioId: str
    contenido: str
    estado: str
    likes: int
    creadoEn: str


class ComentarioCreado(Comentario):
    partidoId: str
    minuto: str
    segmento: int


class ComentarioNuevo(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "examples": [{"usuarioId": "USR-00001", "contenido": "Gran presión del local en el inicio"}]})
    usuarioId: str = Field(pattern=USUARIO_ID)
    contenido: str = Field(min_length=1, max_length=280)


class VentanaComentarios(BaseModel):
    partidoId: str
    desde: str
    hasta: str
    particiones: int = Field(description="Particiones (minuto, segmento) consultadas.")
    items: list[Comentario]


# --- Redis ----------------------------------------------------------------------------
class SesionNueva(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"usuarioId": "USR-00001"}]})
    usuarioId: str = Field(pattern=USUARIO_ID)
    rol: str = Field("lector", pattern=r"^(lector|moderador)$")


class Sesion(BaseModel):
    sesionId: str
    usuarioId: str
    estado: str
    rol: str
    ultimaActividad: int = Field(description="Segundos Unix UTC según el reloj de Redis.")
    expiraEnSegundos: int


# --- InfluxDB -------------------------------------------------------------------------
class PuntoResumen(BaseModel):
    inicio: str
    equipoId: str
    muestras: int
    posesionMedia: float | None
    tiros: int | None
    pasesAcumulados: int | None


class Estadisticas(BaseModel):
    partidoId: str
    equipoId: str | None
    desde: str | None
    hasta: str | None
    intervalo: Intervalo
    puntos: list[PuntoResumen]


# --- IRIS -----------------------------------------------------------------------------
class Arbitro(BaseModel):
    id: str
    codigo: str
    nombre: str
    nacionalidad: str
    licencia: str


class JugadorActa(BaseModel):
    id: str
    codigo: str
    nombre: str
    numero: int
    posicion: str


class EventoActa(BaseModel):
    id: str = Field(description="ID de IRIS dependiente del padre, por ejemplo 1||1.")
    tipo: str
    minuto: int
    jugador: JugadorActa


class Acta(BaseModel):
    id: str
    codigo: str
    estadioCodigo: str
    estado: EstadoPartido
    arbitro: Arbitro
    eventos: list[EventoActa]


class CambioEstado(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"estado": "EN_JUEGO"}]})
    estado: EstadoPartido


class ActaCambio(BaseModel):
    cambio: bool = Field(description="false si el partido ya estaba en el estado pedido (PUT idempotente).")
    acta: Acta


# --- Salud ----------------------------------------------------------------------------
class EstadoFuente(BaseModel):
    fuente: str
    estado: str = Field(examples=["ok"])
    ms: float
