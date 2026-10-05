# 10 · Riesgos y limitaciones conocidas

| ID | Riesgo / limitación | Probabilidad | Impacto | Mitigación | Estado |
|---|---|---|---|---|---|
| R1 | El simulador es optimista: la respiración real es más débil y el multitrayecto más complejo | alta | alto | F1 con datos reales antes de cualquier ajuste fino; ninguna métrica sintética se publica | abierto |
| R2 | Interferentes fijos (ventilador) cuentan como persona hasta aprenderse (20 s en simulación) | media | medio | persistir zonas aprendidas; zonas excluidas manuales; medir en G1–G2 | abierto |
| R3 | Dos personas quietas a la misma distancia del sensor (±6 cm) dan una sola detección de respiración con ángulo mezclado | media | medio | se conservan ambas pistas estáticas por la lógica de habitación; se documenta; posible mejora con más chirps/RX en v2 | aceptado v1 |
| R4 | Intercambio de identidades al cruzarse dos personas | media | bajo para recuento, medio para postura | penalización de asociación pista quieta ↔ medida rápida; métrica de intercambios en el banco | mitigado parcial |
| R5 | El MVP del EFR32MG26 o la RAM no bastan para DSP + Matter | media | alto | medir en F2; plan B (PSoC Edge E84 + EFR32MG24 RCP) | abierto |
| R6 | Persona tumbada en cama alta / baja confundida con caída | media | alto | regla de altura (0,55 m) + zona «cama» configurable donde tumbarse no es caída; escenario A3 | abierto |
| R7 | Home Assistant no expone el clúster de fabricante (recuento, posturas) | alta | medio | lo esencial va en clústeres estándar; recuento por zonas; seguir la evolución de Matter | abierto |
| R8 | Caídas simuladas ≠ caídas reales de personas mayores | cierta | alto | constar en cada métrica; incluir caídas lentas y desde sentado; no presentar como dispositivo médico | aceptado |
| R9 | Radomo impreso desafina el radar (espesor, humedad, aditivos de color) | media | medio | cupones de espesor medidos con el kit; PETG natural, relleno 100 % | abierto |
| R10 | El BGT60TR13C no está en el catálogo de montaje del fabricante | media | medio | consigna de piezas o módulo de radar comercial como alternativa | abierto |
| R11 | Disponibilidad o coste de los kits | baja | medio | pedir kits al inicio de F1 | abierto |
| R12 | El proyecto abre un frente nuevo sin cerrar los anteriores del plan personal | — | — | decisión explícita del responsable antes de F1 | abierto |
