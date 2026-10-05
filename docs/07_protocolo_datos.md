# 07 · Protocolo de datos

## Principios

1. Nadie se graba sin consentimiento escrito firmado antes de la sesión
   ([plantilla](07b_consentimiento_plantilla.md)). Se puede retirar en cualquier momento.
2. El radar no capta imagen ni voz. Aun así, los datos se tratan como
   personales: se guardan con un identificador seudónimo (`S07`), nunca con nombre.
3. La tabla que une identificador y persona se guarda aparte, cifrada, y solo
   la ve el responsable de datos.
4. Entrenamiento, validación y prueba se separan **por persona y por sala**
   con [split.py](../ml/radarref/split.py); las sesiones que mezclarían se
   descartan. Sin esto ninguna métrica vale.
5. Las caídas son **simuladas por adultos sanos** sobre colchoneta. Esta
   limitación se escribe junto a cada métrica de caída publicada: las caídas
   reales de personas mayores son más lentas, más variadas y a menudo sin
   recuperación, y pueden comportarse distinto.

## Qué se graba por sesión

| Fichero | Contenido |
|---|---|
| `raw/*.npz` | tramas ADC del kit (solo F1–F3) |
| `features/*.bin` | registros del contrato v1 (66 B por pista y trama) |
| `labels.csv` | intervalos etiquetados: inicio, fin, persona, actividad |
| `session.yaml` | persona (seudónimo), sala, altura de montaje, mobiliario, hora, versión de firmware y contrato |

## Etiquetado sin cámara

En salas privadas (baño, dormitorio) no se usa cámara. El etiquetado sigue
un guion con marcas de tiempo: un operador registra cada cambio con una
aplicación de pulsaciones sincronizada por NTP. En una sala de laboratorio,
con consentimiento específico, puede usarse cámara solo para verificar las
etiquetas; esos vídeos no salen del equipo de etiquetado y se borran al validar.

## Guion por sesión (≈ 25 min)

| Bloque | Actividades | Repeticiones |
|---|---|---|
| Presencia | entrar, caminar, quedarse de pie, sentarse 3 min quieto, salir | 3 |
| Postura | de pie ↔ sentado ↔ tumbado (sofá, cama, suelo) | 3 de cada |
| Confusores | sentarse de golpe, tumbarse rápido en la cama, agacharse a recoger, atarse los zapatos, ejercicio | 3 de cada |
| Caídas | hacia delante, hacia atrás, lateral, desde sentado, resbalón lento; sobre colchoneta | 2 de cada (10 por sesión) |
| Dos personas | una quieta, otra pasa por delante y se detiene; cruce | 3 |

Ojo con el tamaño: por la separación por persona y sala, las ≥ 100 caídas
del criterio F1 tienen que salir **solo de la partición de prueba**. Ejemplo
de reparto: 4 personas de prueba × 3 sesiones × 10 caídas en la sala de
prueba = 120 caídas; las 8 personas restantes graban en las otras 3 salas
para entrenamiento y validación (≈ 160–240 caídas).

## Conjuntos públicos

Se usan solo para prototipar (forma de las señales, arquitectura del
modelo). Antes de usarlos se comprueba su licencia. No sirven como modelo
final porque usan otros radares, frecuencias y montajes; ninguna métrica
publicada sale de ellos.
