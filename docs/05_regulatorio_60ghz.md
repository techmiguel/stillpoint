# 05 · Emisión en 60 GHz (Europa)

El proyecto no pasa certificación en la v1, pero **sus parámetros de emisión
deben estar dentro de lo permitido**. Esta tabla es la referencia de diseño;
antes de cualquier venta se contrasta con las versiones vigentes de los
documentos citados.

| Referencia | Qué fija (resumen) |
|---|---|
| Decisión 2006/771/CE y modificaciones (SRD), ERC/REC 70-03 | dispositivos de corto alcance no específicos en 57–64 GHz: 100 mW (20 dBm) PIRE, con límites adicionales de potencia de salida y densidad |
| ETSI EN 305 550 | norma armonizada para SRD de 40–246 GHz (métodos de medida) |
| Directiva 2014/53/UE (RED) | marco de comercialización |

## Cómo se aplica en el diseño

| Parámetro | Límite de diseño | Valor v1 | Dónde se impone |
|---|---|---|---|
| Banda ocupada | dentro de 57,0–64,0 GHz | 60,0–61,25 GHz | `RadarConfig.check_eu`, `rf_radar_check_eu` |
| PIRE | ≤ 20 dBm | objetivo 10 dBm (margen ≥ 10 dB) | ídem; la potencia TX del BGT60 se fija al mínimo que cumpla P1 |
| Ciclo de trabajo | < 100 % | 11 % | ídem |

- La configuración del radar está en firmware y no es modificable por
  Matter; cualquier configuración que no pase la comprobación se rechaza y el
  radar no se arranca (fallo seguro).
- El BGT60TR13C se comercializa para esta banda; su hoja de datos indica la
  potencia de salida y la ganancia de antena para estimar la PIRE. La
  estimación y la medida aproximada (analizador o medidor de potencia con
  bocina de 60 GHz, si se dispone de acceso) se documentan en F4 (criterio S4).
- El radomo no debe concentrar el haz: lámina plana de espesor λ/2, sin lentes.
