# Hito 10 · Envoltorio IRIS `FixtureH10.Servicio`

La API cambia el estado de un partido (CU-19) solo con `FixtureH9.Partido.CambiarEstado()`, que valida la transición y guarda (Hito 9). Como el SDK nativo de Python invoca mejor métodos de clase que métodos de instancia sobre objetos abiertos con bloqueo, este directorio agrega un envoltorio en un paquete propio, `FixtureH10`, **sin modificar el Hito 9**.

## Qué hace

`FixtureH10.Servicio.Transicionar(codigo, nuevo, espera = 2)`:

1. Localiza el partido por el índice único `PorCodigo` (código de negocio, por ejemplo `PAR-001`).
2. Toma un bloqueo exclusivo con `%LockId(id, 0, espera)`. La espera está acotada (`IRIS_ESPERA_BLOQUEO_S`, 2 s por defecto) para que sea menor que el timeout del cliente (3 s).
3. Abre el objeto **después** de bloquear, así el estado que lee es el vigente.
4. Si el estado ya es el pedido, no llama a `CambiarEstado` (idempotencia de CU-19).
5. Si no, llama a `CambiarEstado(nuevo)` y libera el bloqueo siempre.

Devuelve `"RESULTADO|anterior|actual"`:

| Resultado | Significado | Respuesta de la API |
|---|---|---|
| `OK` | La transición se aplicó y se guardó | `200`, `cambio: true` |
| `SIN_CAMBIO` | El estado ya era el pedido | `200`, `cambio: false` |
| `NO_ENCONTRADO` | No existe un `Partido` con ese código | `404 ACTA_NO_ENCONTRADA` |
| `TRANSICION_NO_PERMITIDA` | `CambiarEstado` rechazó la transición (error 5001); el estado no cambió | `409 TRANSICION_NO_PERMITIDA` |
| `BLOQUEADO` | Otro proceso retiene el partido; no se aplicó nada | `504 DEPENDENCIA_TIMEOUT` (reintento seguro) |
| `ERROR` | Cualquier otra falla; el detalle no sale de IRIS | `500 ERROR_INTERNO` |

No devuelve IDs internos. `Version()` permite comprobar que la clase está cargada.

## Cómo cargarlo

Requisitos: el contenedor del Hito 9 levantado y `healthy`, la muestra cargada (`FixtureH9.Demo.Ejecutar()`, ver `Hito 9/README.md`) y `IRIS_USER` / `IRIS_PASSWORD` completos en `Hito 10/.env`.

### Opción 1: script (recomendada)

Desde la carpeta `Hito 10`, en PowerShell:

```powershell
.\scripts\cargar_servicio_iris.ps1
```

Envía el texto de la clase por el SDK de Python (`%Compiler.UDL.TextServices.SetTextFromString`) y la compila con `$System.OBJ.Compile("FixtureH10.Servicio", "ck-d")`. No copia archivos al contenedor ni abre el Terminal, y no recompila `FixtureH9`. Termina con `COMPILACION OK: FixtureH10.Servicio versión 1 en el namespace USER`. Se puede repetir: reemplaza la clase por la versión del repositorio.

### Opción 2: Terminal IRIS (manual, igual que el Hito 9)

El Compose del Hito 9 monta solo `Hito 9/scripts` en `/scripts`, así que primero se copia el archivo al contenedor. Desde la raíz del repositorio:

```powershell
$contenedor = docker compose -f '.\Hito 9\docker-compose.yml' ps -q iris
docker cp '.\Hito 10\iris\FixtureH10.Servicio.cls' "${contenedor}:/tmp/FixtureH10.Servicio.cls"
docker compose -f '.\Hito 9\docker-compose.yml' exec iris iris session IRIS -U USER
```

En el Terminal (ObjectScript):

```objectscript
Set sc = $System.OBJ.Load("/tmp/FixtureH10.Servicio.cls", "ck")
If $System.Status.IsError(sc) { Do $System.Status.DisplayError(sc) }
Write ##class(FixtureH10.Servicio).Version(), !
Halt
```

## Si falta el envoltorio

`GET /partidos/{id}/acta` (CU-18) funciona igual, porque lee por SQL proyectado. `POST /partidos/{id}/acta/transiciones` (CU-19) responde `500 ERROR_INTERNO` y el log de la API dice `falta cargar FixtureH10.Servicio (ver Hito 10/iris/README.md)`. Las pruebas de integración de IRIS se omiten con ese mismo aviso.

## Cómo quitarlo

En el Terminal: `Do $System.OBJ.Delete("FixtureH10.Servicio")`. Solo borra la clase del envoltorio; no toca los datos ni las clases del Hito 9.
