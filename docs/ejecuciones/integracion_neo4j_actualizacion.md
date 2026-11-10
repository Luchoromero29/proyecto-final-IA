# Neo4j actualizado a la versión integrada de PG3

PG3 se ejecutó correctamente después de verificar el respaldo. La verificación independiente
aprobó la seguridad de los datos y la preservación comprobada; no es una aprobación funcional
de los 61 casos, que se registran por separado.

## Antes y después

| Dato | Antes | Después |
|---|---:|---:|
| Avisos de mercado | 289 | 333 |
| Procesadores | 83 | 93 |
| Procesadores con precio | 18 | 24 |
| Líneas | 45 | 46 |
| Capacidades RAM | 11 | 11 |
| Nodos totales | 759 | 814 |
| Relaciones totales | 1780 | 1905 |

Los 333 IDs de avisos coinciden exactamente con el CSV. XPS está presente. Hay 19 restricciones,
CE `min_muestras_mercado=5/v2` y R2.4 implementada, todavía Provisional.

## Respaldo y recuperación disponible

Ubicación local ignorada por Git: `_respaldo_original/neo4j-actualizacion.7Jn5Ne/`.
No se versionan sus datos ni se elimina el respaldo después de las pruebas.

- `volumen/`: copia fría completa del volumen previo, incluidos `system` y autenticación.
- `neo4j.dump`: respaldo de la base `neo4j`; **no incluye por sí solo `system`/usuarios**.
- `restauracion/`: destino nuevo donde se restauró y verificó el dump, sin tocar el original.
- Inventarios antes/después y exportaciones de comparación, conservados en el mismo directorio.

SHA-256 del dump (262.596 bytes comprimidos):

```text
056b97a8090a8d038e10ff4eb38015f75b2c16fd61cfc93275714bbb1d383e24
```

La validación no se limitó al tamaño: `load --info` reconoció 55 archivos / 271.745.024 bytes
sin comprimir; una restauración real en destino vacío y el chequeo de consistencia pasaron.
Después se levantó esa copia aislada, sin red ni puertos publicados, y la exportación de
propiedades de nodos y relaciones coincidió byte a byte con la del original (8.243 líneas).
SHA-256 de ambas exportaciones:

```text
9fb54e1e3a6cbf6bb7ae84ffffd4813d188d0f78ddbc903aaa8200a15a469daf
```

Ante un problema futuro existe copia completa para recuperación, pero **no se ejecutó rollback**:
restaurar sobre la base real sería una operación destructiva distinta y requiere autorización.

## Ejecución y preservación

Se usó la misma imagen Neo4j 5.26.32, fijada por ID. La copia se tomó con el servidor detenido y
el volumen fuente montado de solo lectura. Se reinició únicamente el contenedor existente.

Después de validar el respaldo y los hashes del Cypher/CSV/código, se envió exclusivamente
`Grupo_20_PG3_mercado.cypher` por stdin a `cypher-shell --fail-fast`: salida 0. **No se ejecutó
`neo4j-init`, `RECARGAR=1`, el reset de PG2 ni la importación del dump versionado.**

Se comprobó igualdad profunda antes/después para:
- 118 nodos protegidos de casos, operaciones, decisiones, submódulos y reglas/conjuntos difusos.
- Sus 320 relaciones internas, con propiedades.
- Las 19 restricciones.

Los inventarios completos **no** son idénticos, porque los conteos del catálogo cambiaron.
Para otras etiquetas la verificación independiente comprobó conteos, no igualdad de cada valor.
PG3 recalibró y sobrescribió los datos de catálogo/costos autorizados. No se garantiza preservar
ajustes manuales de esos valores; el estado previo está en el respaldo.

## Fallos de preparación conservados

- Primera consulta de comparación: `toString` no admitía propiedades lista; cero comparaciones.
- Primer servidor aislado: timeout 90 s, contenedor terminado con código 3; cero comparaciones.
- Preparación con memoria acotada: volvió a salir con código 3, sin OOM ni arranque del servidor.
- Diagnóstico independiente: el entrypoint fallaba en el dry-run; el hostname no tenía resolución
  en `--network none`. El helper final usó hostname y entrada hosts local y pudo arrancar.
- El helper final se detuvo tras la comparación; terminó con 137 por el límite de parada. Eso
  afectó solo al scratch, después de la comparación aprobada, no al Neo4j original.
- Los comandos administrativos imprimieron advertencias de hostname, pero dump/load/check
  terminaron con salida 0. Las advertencias no se ocultaron del log.

Los intentos fallidos no se presentan como aprobados ni se atribuyen a corrupción de la base.

## Evidencia y verificación independiente

- [Respaldo y consistencia](integracion_neo4j_respaldo.log).
- [Comparación y gate de carga](integracion_neo4j_verificacion_carga.log).
- [Salida de PG3](integracion_neo4j_carga_pg3.log).
- [Comparación fallida 1](integracion_neo4j_comparacion_intento1.log).
- [Comparación incompleta 2](integracion_neo4j_comparacion_intento2.log).
- [Preparación fallida v3](integracion_neo4j_verificador_v3.log).

Verifier independiente `mwb64t5t-6-0818`: PASS para S2/S4/S5 y S6 en el alcance T2, y PASS para
Risk item 1. Confirmó hashes, igualdad de exportaciones, preservación del conjunto protegido,
IDs del CSV y aritmética de altas/bajas de nodos/relaciones mediante consultas solo de lectura.
No repitió operaciones de mantenimiento ni la tanda LLM. La evaluación nativa estuvo indisponible
por archivos sin seguimiento; no se inventa aprobación nativa ni se sustituye por este dictamen.

Risk: item 1 — reconstrucción de datos almacenados, autorizada expresamente y precedida de
respaldo restaurado/verificado. Se aplicó el script integrado sin editar su lógica.
