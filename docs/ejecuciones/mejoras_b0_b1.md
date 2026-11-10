# B0/B1: causas aisladas e integridad del precio

**Precio corregido y probado; el producto todavía tiene cinco incumplimientos en esta tanda.**
Base: `67de236`. Sin recargar ni modificar Neo4j. Mismo proveedor/modelo NVIDIA y catálogo.

## B0: reproducción real antes de corregir

Se envolvieron temporalmente `extraer_datos_llm` y `ejecutar_motor_sm1` con
`unittest.mock.patch`, llamando al asistente público a través del ejecutor existente. Se copió
la extracción antes de validarla y la entrada a SM1; no se modificaron sus resultados. Tres
casos reales, sin reintentos del ejecutor: job-9, salida 0, 28 s.

[Datos de extracción, entrada SM1 y traza](mejoras_b0_aislamiento.json).

| Caso | Hechos observados | Capa responsable identificada |
|---|---|---|
| PC-15 | Extracción y SM1 reciben 68 °C, throttling=false y fallas vacías. Servicio térmico 30000 + mano de obra 40000; SM1-TER 0.38 → Recomendada. | Inferencia térmica y conversión de throttling a caída de frecuencia; no es un error de extracción en esta reproducción. |
| PC-19 | Extracción y SM1 reciben No prende/No carga. SM1 devuelve Viable, costo 0, sin intervenciones; termina Comprar. | SM1 no resuelve esos síntomas. No atribuirlo al LLM ni a Mamdani. |
| PC-29 | El LLM devuelve 115000 y la validación conserva 115000 para un aviso de $1. | Extracción incorrecta y guard que no reconoce montos cortos. La coincidencia con el ejemplo del prompt no prueba su causa. |

No se agregó un framework de logging ni se registraron claves, razonamientos internos o cuerpos
de error del proveedor. Los valores de costos son observaciones del grafo, no constantes nuevas.

## B1: corrección y pruebas

El pipeline usa el **primer monto literal** con símbolo `$` o unidad `pesos`, incluyendo
montos cortos y cero; admite puntos de miles. No depende del tipo/valor de precio devuelto por
el LLM, ni permite diferencias de 1000 pesos. Sin un monto respaldado en ese formato, deja el
precio desconocido y usa el rechazo existente antes de tasar. El prompt refuerza el contrato.

No se agregaron precio mínimo, conversión de moneda, valuación estimada ni costos por defecto.
No se amplió la interpretación a todas las abreviaturas o formatos monetarios posibles.
Se conservó el comportamiento del primer monto para rangos y precios múltiples.

| Verificación | Resultado | Evidencia |
|---|---|---|
| Offline anterior al cambio | 71/71, salida 0 | [Base](mejoras_b0_offline_base.log) |
| RED de integridad | 8 métodos, 8 fallos de aserción y 1 error contando subtests; salida 1 | [RED](mejoras_b1_red.log) |
| GREEN de integridad | 8/8, salida 0 | [GREEN](mejoras_b1_green.log) |
| Suite completa | 79/79, salida 0 | [Offline](mejoras_b1_offline.log) |
| Tanda real B1 | 61/61 completados; 50 cumplen, 5 fallan, 6 sondas, 0 infra; salida 1, 5 min 39 s | [NVIDIA](mejoras_b1_nvidia.log) |

La salida RED original está conservada sin pérdida en
[JSON](mejoras_b1_red_original.json), SHA256 `d25519382b6038585f0a8cb4e576e0c06cfdb188c4dbf927dc39c8f28e8b6369`.
La vista `.log` solo omite un espacio final generado por unittest que disparaba el chequeo
estructural de Git; no se eliminaron fallos, errores ni mensajes.

Las pruebas nuevas invocan el asistente público con LLM/grafo simulados. Comprueban precio
extraído y usado en SM3, formatos previos, rechazos sin tasación/síntesis, cero y precio LLM
inventado o de tipo incorrecto. No se cambió el corpus ni se enseñó al fixture original a pasar.
No hay consultas Cypher nuevas que requieran validar mutaciones en una base aislada en B1.
La inferencia con grafo aislado y extracción controlada sigue siendo necesaria para los bloques
que cambien conocimiento/inferencia; no se presenta esta suite simulada como esa cobertura.

**PC-29 ahora cumple:** precio 1 según el verificador, costo 0, VMA 645000;
la decisión en esta tanda fue ComprarConOfertaMenor. B1 corrige extracción, no la credibilidad
comercial de un anuncio de un peso ni toda la política financiera.

Siguen fallando PC-01, PC-15, PC-17, PC-19 y PC-50, fuera de la corrección B1. PC-47 sigue siendo
sonda y termina Comprar/costo 0. Las seis sondas no se cuentan como aprobadas.

## Límites y continuación

B2 espera resolver la política de síntomas/confirmación. El usuario pidió discutir si estos
síntomas hacen que una compra deje de convenir; no se aplicó una definición experta implícita.
No se modificaron aún reglas térmicas, bloqueo ni enrutamiento.

Risk: none para el cambio B1: validación local del pipeline integral pedido y su prompt,
sin cambiar helpers de SM1/SM2 sueltos, consultas, formatos persistidos, dependencias o permisos.
El cambio intencional del contrato de precio se prueba explícitamente; las futuras reglas del
grafo tienen su propia evaluación de riesgo y verificación.
