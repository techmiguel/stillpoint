# 04 · Modelo de datos Matter

Objetivo: que Home Assistant (y cualquier controlador Matter) vea lo esencial
**con clústeres estándar**, sin integración propia. Lo que Matter no
estandariza va en un clúster de fabricante, opcional para el usuario.

## Transporte

- Thread, dispositivo FTD con capacidad de router (alimentado por cable: refuerza la malla).
- Puesta en marcha por BLE con código QR / código manual impreso en la carcasa.
- Sin cuenta ni nube. Configuración (zonas, puertas, altura) por clúster de
  fabricante o, en v1, por UART/USB con una herramienta local.

## Endpoints

| EP | Tipo de dispositivo | Clúster | Atributo / evento | Significado |
|---|---|---|---|---|
| 0 | Root Node | Basic Information, OTA Requestor, … | — | estándar |
| 1 | Occupancy Sensor | Occupancy Sensing (0x0406) | `Occupancy` | alguien en la sala (incluye quietos) |
| 2–4 | Occupancy Sensor | Occupancy Sensing | `Occupancy` | ocupación por zona configurada (p. ej. cama, sofá, baño) |
| 5 | Contact Sensor | Boolean State (0x0045) | `StateValue` + evento `StateChange` | **caída** (confirmada **o** incierta) |
| 6 | Contact Sensor | Boolean State | `StateValue` | **incertidumbre**: alguna salida está en «incierto» |
| 1 | — | Clúster de fabricante 0xFFF1FC01 ([radar60_cluster.xml](../firmware/port/efr32mg26/radar60_cluster.xml)) | `PersonCount`, `FallState` (0 ninguna, 1 sospecha, 2 confirmada, 3 incierta), `Uncertain`, `ProposedExclusions`, `ContractVersion`, `ModelHash` (CRC32 del modelo) | detalle para integraciones avanzadas |

Notas:

- En Matter 1.3+ el clúster Occupancy Sensing declara el tipo de sensor; se
  declara **radar**. Confirmar la revisión exacta del clúster que soporta el SDK elegido.
- Matter no tiene un tipo de dispositivo «detector de caídas». Se usa Boolean
  State porque cualquier controlador lo muestra y automatiza; la etiqueta del
  endpoint (Fixed Label / User Label) dice «Caída». Es una decisión a revisar
  si la especificación incorpora algo específico.
- El endpoint 5 se activa tanto con caída confirmada como incierta: una caída
  que no puede verificarse **se notifica**. El tipo exacto está en el clúster
  de fabricante y en el endpoint 6.
- `Tracks[]` (id, x, y, postura, estado por persona) queda para v2: una lista
  de estructuras exige definir el tipo en ZAP y su coste de informes en Thread
  se evalúa en F2. En v1 la posición individual sale solo por el flujo de
  diagnóstico UART.
- Riesgo R7: Home Assistant puede no exponer el clúster de fabricante sin
  soporte específico. El recuento de personas queda entonces solo por
  zonas. Se comprueba en F2 con la versión vigente de python-matter-server.

## Política de publicación

- `Occupancy`: inmediato al pasar a ocupado; al pasar a vacío, cuando la
  última pista se borra (puerta: ~2 s). Sin retención fija adicional.
- Caída: evento al entrar en confirmada/incierta; se borra al levantarse 5 s
  o por comando local.
- Límite de 2 informes/s por endpoint para no cargar la malla Thread.
