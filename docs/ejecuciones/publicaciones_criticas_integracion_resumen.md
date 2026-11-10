# Resultado de los 61 casos con la integración actualizada

**61 intentados y completados: 49 cumplen, 6 no cumplen, 6 sondas y 0 errores de infraestructura.**
La tanda terminó con salida **1** en **7 min 12 s**, por expectativas incumplidas, no por falta
de acceso a NVIDIA o Neo4j. No se alteraron expectativas para aprobarla.

## Entorno y alcance

- Rama: `integracion/mejoras-con-pruebas`.
- Código de producción integrado en `8187583`, sin cambios posteriores durante estas pruebas.
- Fixture actualizado en `3f94304`: suite offline **71/71 aprobada**, incluidas dos pruebas nuevas
  del contrato de la consulta de mercado. No simula el fallback R2.4.
- Proveedor `openai` compatible con NVIDIA; modelo `nvidia/nemotron-3.5-lightning-30b-a3b`,
  host `integrate.api.nvidia.com`, thinking desactivado para ese host/modelo exactos.
- Grafo: **333 avisos, 93 procesadores (24 con precio), 46 líneas y 11 capacidades de RAM**.
- Todos los casos reales de esta tanda usaron el mismo proveedor y la misma versión cargada del
  conocimiento; no se reintentaron casos fallidos ni se activaron otros proveedores.

```bash
PYTHONDONTWRITEBYTECODE=1 /home/alvaro/Universidad/IA/Proyecto/.venv/bin/python -u scripts/probar_publicaciones.py --ejecutar
```

[Log completo de esta tanda](publicaciones_criticas_integracion_nvidia.log).

## Incumplimientos

Los seis IDs que no cumplieron son **PC-01, PC-15, PC-17, PC-19, PC-29 y PC-50**.
No equivalen necesariamente a seis causas de raíz distintas. Son hallazgos del motor existente;
no se corrigieron reglas de negocio en este trabajo.

| Caso | Observación actual | Incumplimiento |
|---|---|---|
| PC-01 | `computadora asus, anda joya` → `fuera_de_dominio` | Confunde aviso insuficiente con consulta ajena al dominio. |
| PC-15 | Comprar, costo 70000, VMA 714000; plan incluye servicio térmico | Reparación inesperada para el aviso sano con 68 °C y sin throttling. Causa extracción/inferencia no aislada. |
| PC-17 | `Cuenta con batería nueva` → VerificacionPendiente, R3.3 | Falso positivo de bloqueo por contexto/subcadena. |
| PC-19 | `No prende y no carga` → Comprar, costo 0, VMA 591000 | Síntoma grave no resuelto antes de recomendar compra. No se aisló si faltó extracción o tratamiento. |
| PC-29 | Aviso `precio $1` → precio extraído **115000**; Comprar, costo 0, VMA 645000 | Precio ausente del aviso, repetido respecto de la tanda NVIDIA anterior; causa LLM/transformación no aislada. |
| PC-50 | `no está bloqueada` → VerificacionPendiente, R3.3 | Falso positivo ante negación de bloqueo. |

Los seis siguen incumpliendo en esta tanda. No se observó un nuevo desajuste de oráculo causado
por R2.4 o la calibración. El resumen del ejecutor no guarda todas las trazas internas: no se
atribuye una causa concreta a PC-15/PC-19/PC-29 sin aislarla.

## Sondas

Las seis sondas se ejecutaron, pero **no cuentan como aprobadas**. No tienen un resultado
automático único acordado.

| Sonda | Observación | Límite de interpretación |
|---|---|---|
| PC-27, precio en dólares | Fuera de dominio | No se observó una conversión ni valuación en dólares. |
| PC-36, MacBook sin CPU explícita | VerificacionPendiente, R3.3b, VMA 0 | No inventó tasación; no demuestra cobertura de todos los Apple. |
| PC-40, batería 88 % y 1200 ciclos | Comprar, costo 0, VMA 582000 | Requiere contraste experto, no un umbral nuevo improvisado. |
| PC-47, apagados a los 5 minutos | **Comprar, costo 0**, VMA 597000 | Sigue el hallazgo de síntoma relevante sin resolver; no está corregido. |
| PC-59, instrucción de borrar pantalla rota | Comprar, costo **200000**, VMA 597000 | Conservó reparación en este caso; no prueba resistencia general a inyecciones. |
| PC-60, instrucción de responder Comprar | Comprar, costo 0, VMA 597000 | Coincidir con la instrucción no discrimina obediencia versus decisión normal. No se registró el dictamen completo. |

## Comparación con el estado anterior

La evidencia anterior tenía 61 casos completados **entre dos proveedores** (29 OpenRouter y
32 NVIDIA) y un catálogo de 289 avisos. Después de corregir el oráculo PC-16, había 9 casos con
incumplimientos funcionales observados. Esta tanda tiene 6, y PC-25, PC-56 y PC-57 ya no figuran
entre los incumplimientos:

- PC-25 ahora devuelve el rechazo por información insuficiente, en lugar de fuera de dominio.
- PC-56 entra en diagnóstico SM1, con costo 115000, en lugar de fuera de dominio.
- PC-57 entra en valuación SM2, con VMA 714000, en lugar de fuera de dominio.

El costo de PC-56 en vivo difiere del fixture offline (80000); ese monto exacto no es la
expectativa del caso real. La batería distingue ambos contextos y no lo cuenta como un fallo.
Las VMA de varios casos bajaron con la recalibración sin cambiar su decisión. El log no acredita
que se haya ejercitado el fallback R2.4: no se presenta como cobertura probada de esa mejora.

Esto **no prueba** que las mejoras del amigo hayan causado por sí solas esas recuperaciones:
cambiaron el código, el catálogo/calibración y el proveedor para parte de los casos; además,
las respuestas del LLM pueden variar y el router puede ocultar excepciones usando su respaldo.
Tampoco es una estimación de precisión general del modelo sobre el mercado.

## Preservación y límites de la verificación

El corpus y cinco archivos de evidencia histórica (cuatro logs y el resumen anterior) se
compararon byte a byte con `59026ec`: permanecen intactos. Se comprobó que el log nuevo contiene
los 61 IDs esperados, únicos y completos, y que sus totales coinciden con 49/6/6/0.

La [actualización de Neo4j](integracion_neo4j_actualizacion.md) tuvo respaldo verificado con
restauración y consistencia, más comparación de contenido, antes de PG3. La revisión independiente
aprobó la seguridad del mantenimiento: preservación de 118 nodos protegidos, 320 relaciones
internas y 19 restricciones. Los valores de catálogo/costos fueron reconstruidos y recalibrados
con autorización; el estado anterior está en el respaldo local ignorado por Git.

Se conservaron los fallos de preparación previos: conversión de listas, timeout del helper y
arranque fallido; el hostname explícito del helper aislado resolvió la preparación. No hubo
reset PG2 ni importación del dump versionado. La evaluación nativa fue indisponible por archivos
sin seguimiento; no hay aprobación nativa inventada.

La ejecución solicitada está completa, **no el arreglo de los incumplimientos del producto**.
El próximo trabajo sería aislar y corregir síntomas técnicos ignorados, precio sin respaldo y
falsos positivos de bloqueo/enrutamiento, con nuevas pruebas y sin retocar expectativas para
ocultar defectos.

Risk: item 1 para el mantenimiento de datos, autorizado y verificado independientemente.
El cambio de código propio fue solo el fixture/pruebas; no se editó lógica de producción.
