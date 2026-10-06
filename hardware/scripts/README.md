# Scripts de la placa rev A

La fuente de verdad es `hardware/radar60.kicad_pcb`. Estos scripts registran
cómo se hizo la colocación de la cara inferior y el rutado (KiCad 10 + Python
`pcbnew`, Freerouting 2.5 con Java 25) y regeneran los ficheros de fabricación.

## Fabricación (lo único que hace falta para pedir la placa)

```bash
bash hardware/scripts/fabricacion.sh
```

Rellena las zonas, **falla si el ERC o la DRC tienen algún error** (la DRC
incluye la paridad con el esquema) y deja en `hardware/fab/revA/`:

| Fichero | Contenido |
|---|---|
| `radar60_gerber.zip` | Gerber de las 4 capas, máscaras, serigrafías, pasta, contorno y taladros (para subir) |
| `bom.csv` | BOM en formato JLCPCB (columna `LCSC` vacía: se rellena al elegir piezas) |
| `cpl.csv` | posiciones en formato JLCPCB (56 componentes; puntos de prueba y Tag-Connect fuera) |
| `esquema.pdf`, `placa.pdf` | revisión |
| `erc.rpt`, `drc.rpt`, `drc_completo.rpt` | informes (el completo incluye avisos) |

También exporta `mechanical/cad/placa_revA.step`, la placa montada que usa
`mechanical/freecad_carcasa.py` para comprobar interferencias con la carcasa.

## Orden en que se aplicaron los pasos

Partiendo del commit con la cara superior colocada (91f0ae8):

1. `revA_1_colocacion.py`: 4 capas y apilado JLC04161H-7628, zonas prohibidas
   (antena del MGM260P en todas las capas, In2 sin pistas bajo el radar, apoyos
   de la carcasa sin componentes), colocación de la cara inferior.
2. `revA_2_radar.py`: rutado manual del entorno del radar (fan-out del BGA,
   desacoplos directos a cada bola, reloj de 80 MHz, raíles) y planos de GND.
3. `revA_3_autorutado.py`: resto del rutado con Freerouting; GND no se ruta
   (va por planos), In1 queda como plano entero.
4. `revA_4_gnd.py`: vía de GND junto a cada pad y cosido de planos, cada vía
   validada con la DRC de KiCad.
5. `revA_5_retoques.py`: retoques puntuales sobre el resultado del autorutado.
6. `revA_6_serigrafia.py`: referencias sin solapes (las que no caben, solo en Fab).
7. `revA_7_acabado.py`: descripciones y hojas de datos desde el esquema.
8. `revA_8_huellas.py`: huellas refrescadas desde su biblioteca (atributo SMD y
   modelos 3D), comprobando que ningún pad se mueve.
9. `revA_3_autorutado.py --levantar /USB_DP,/USB_DN,/CC1,/VBUS`: rutado
   parcial alrededor de J1 respetando los tetones del conector (zonas de la
   huella de biblioteca) y la holgura de 0,4 mm a sus agujeros no metalizados.
10. `revA_9_usb_islas.py`: USB_DP de J1 a U5 por B.Cu e islas de GND.
11. `revA_6_serigrafia.py` y `revA_8_huellas.py` de nuevo, tras `modelos_3d.py`.

Freerouting no es determinista entre ejecuciones: los pasos 5 y 10 trabajan
sobre coordenadas del resultado concreto que se obtuvo y no son reaplicables
tal cual a otro rutado. Para cambios futuros se edita la placa en KiCad y se
vuelve a ejecutar `fabricacion.sh`.

Notas de la API de KiCad 10 aprendidas por las malas: solo funciona un
`LoadBoard` por proceso, y tras `BOARD.Remove()` el envoltorio SWIG deja de ser
fiable en ese proceso; por eso los scripts eliminan al final y lanzan
subprocesos.

## Modelos 3D

`modelos_3d.py` (FreeCAD) genera envolventes en `hardware/lib/radar60.3dshapes`
para lo que la biblioteca de KiCad no trae: BGT60TR13C, MGM260P, USB-C
GT-USB-7051x y oscilador SiT PQFN. Las alturas del módulo (2,2 mm) y del USB-C
(7,0 mm) son aproximadas y hay que confirmarlas con las hojas de datos; la
comprobación mecánica deja margen (8,4 mm libres sobre la placa).
