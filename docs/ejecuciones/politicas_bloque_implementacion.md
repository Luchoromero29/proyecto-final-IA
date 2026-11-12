# Implementación del bloque TB — políticas de SM3, SM2 y clasificación

Estado: **implementado y verificado en el alcance acotado; datos activados únicamente en scratch**.
El padre aplicó el artefacto con comparación completa antes del commit: 39 nodos nuevos,
50 relaciones nuevas y propiedades permitidas en cuatro reglas; primera aplicación 93, segunda 0.
Inventario final: 915 nodos, 2033 relaciones y 19 restricciones. Registro:
`politicas_bloque_activacion.log`. La única comprobación funcional final (TV) terminó: 50/50
pruebas, salida 0, sin omisiones, 22,466 s; siete comparaciones de preservación iguales.

## Resultado de la única verificación final

Verificador: `mwe6l335-2-89yu`. Se ejecutaron una vez los módulos del bloque (24), condiciones
SM1 (15) y filtros SM3 (11). No se ejecutaron los módulos completos ni la suite de 200.
Un diferencial capturó siete casos contra `a0085c4`: R3.4, R3.5, R3.6, margen IEEE 1,25,
valuación SM2 y clasificación Firme/Provisional. Objetos, trazas, stdout/stderr de producción y
códigos de salida coinciden. Los módulos previo/actual se importaron desde sus árboles separados.
Los dos casos de clasificación invocaron el helper de producción; esto no acredita el asistente/CLI.

El snapshot completo antes/después de la suite y al final coincide:
`7ddde337694a58e45320d2c0967148af2fb5f224486aebc62247ae9d0912e19d`;
915 nodos, 2033 relaciones, 19 restricciones y marcador único. Fuentes congeladas sin cambios.

Desvío registrado: el primer comparador incluyó rutas de importación, distintas por diseño.
Se corrigió únicamente esa comparación sobre los JSON ya capturados, sin ejecutar producción
otra vez. El primer log se preserva. No se declara una ejecución de proceso sin desvíos.
Artefactos: `_respaldo_original/verificacion-bloque.7z5bh6n4/` (`pruebas.log`,
`diferencial.log`, `comparacion.json`, `informe.md`). No hay aprobación nativa ni B2 global cerrado. Este documento declara el delta exacto, cómo activarlo y qué
queda explícitamente afuera; no reemplaza a [DECISION_NEO4J.md](../DECISION_NEO4J.md),
[VALUACION_NEO4J.md](../VALUACION_NEO4J.md) ni
[CONTRATO_POLITICAS_NEO4J.md](../CONTRATO_POLITICAS_NEO4J.md).

## Áreas cubiertas

| Área | Qué pasó a datos del grafo | Consumidor |
|---|---|---|
| I6 margen requerido | Manifiesto de etapa, paso 0 (base), R3.4/R3.5 excluyentes, R3.6; condiciones con grupo, destino y operación `asignar`/`maximo`/`sumar` | `inferencia_sm3.CONSULTA_CRISP` |
| I7 cálculo y cuantización SM3 | Destino y precisión de las cinco cuantizaciones (`margen_neto` 1, `ratio_reparacion` 2, `contraoferta` −3 con límite 0.0, `descuento` 1, `brecha` 1) | Ídem, sobre el cuantizador IEEE intacto |
| I9 fórmula de valuación | Escala de redondeo del VMA (1000) y qué criterios aplica (descuento de negociación y revalorización por upgrade) | `orquestador_evaltic._CONSULTA_VALUACION_SM2` |
| I10 R2.4 | Activación y requisito de misma familia | Ídem (`OPTIONAL MATCH` de generación anterior) |
| I11 estado comercial | Ocho reglas ordenadas con su estado y motivo resultantes y nueve condiciones sobre los hechos de la consulta | Ídem, con `EVALUAR_CONDICIONES` |
| I12 Firme/Provisional | Dos reglas ordenadas y cuatro condiciones sobre los conteos de la traza | `orquestador_evaltic.CONSULTA_CLASIFICACION_DECISION` vía `_estado_decision` |

Mecanismo que sigue en Python/Cypher fijo, y por qué: la expresión aritmética de cada paso
(`100·(VMA−precio−costo)/VMA`, `costo/VMA`, contraoferta, descuento, brecha, VMA), el algoritmo
IEEE de `_CUANTIZAR`, los comparadores finitos (`=`, `<`, `>=`, `ausente`, `presente`, OR dentro
del grupo y AND entre grupos) y el `CASE` que ordena los pasos del cálculo por su destino. No hay
motor de fórmulas, DSL, texto ejecutable ni dependencias nuevas.

## Allowlist exacta del artefacto

Archivo: `cypher/Grupo_20_PG3_politicas_bloque.cypher` (una sola consulta, sin `LOAD CSV`, sin
APOC). Devuelve `conflictos`, `actualizadas`, `errores`.

### Propiedades nuevas en nodos existentes (4)

| Nodo | Propiedades |
|---|---|
| `Regla R3.4` | `etapa='SM3-margen'`, `prioridad_inferencia=20`, `efecto_destino='margen_paso1'`, `efecto_operacion='asignar'`, `grupo_exclusion='SM3-MARGEN-PASO1'`, `traza_texto` (texto actual de la traza) |
| `Regla R3.5` | `etapa='SM3-margen'`, `prioridad_inferencia=30`, `efecto_destino='margen_paso1'`, `efecto_operacion='maximo'`, `grupo_exclusion='SM3-MARGEN-PASO1'`, `traza_texto` |
| `Regla R3.6` | `etapa='SM3-margen'`, `prioridad_inferencia=40`, `efecto_destino='margen_req'`, `efecto_operacion='sumar'`, `traza_texto` |
| `Regla R2.4` | `rol='r24'`, `r24_activo=true`, `r24_misma_familia=true` |

No se tocan `texto`, `tipo`, `implementada`, `estado`, `estado_validacion`, `version`, criterios
enlazados ni relaciones previas de esas reglas.

### Nodos nuevos (39)

| Etiqueta | IDs | Propiedades |
|---|---|---|
| `VersionPoliticas` | `VP-SM3-MARGEN`, `VP-SM3-CALCULO`, `VP-SM2-VALUACION`, `VP-SM2-ESTADO`, `VP-SM0-CLASIFICACION` | `version='politicas-bloque-v1'`, `representacion_version='politicas-bloque-v1'`, `etapa`, `activa=true`, `ids_requeridos` |
| `Regla` | `SM3-MARGEN-BASE` | texto, tipo, implementada, `estado='Provisional'`, `etapa`, `prioridad_inferencia=10`, `efecto_destino`, `efecto_operacion`, `rol='base'` |
| `Regla` | `SM2-VALUACION` | texto, tipo, implementada, estado, `etapa='SM2-valuacion'`, `rol='formula'`, `escala_redondeo_ars=1000`, `aplica_descuento_negociacion=true`, `aplica_revalorizacion_upgrade=true` |
| `Regla` | `SM2-EST-01` … `SM2-EST-08` | texto, tipo, implementada, estado, `etapa='SM2-estado'`, `prioridad_inferencia` 10…80, `estado_resultante`, `motivo_resultante` (salvo `EST-08`, que queda `Tasado` sin motivo) |
| `Regla` | `SM0-CLAS-01`, `SM0-CLAS-02` | texto, tipo, implementada, estado, `etapa='SM0-clasificacion'`, `prioridad_inferencia` 10/20, `estado_resultante` `Firme`/`Provisional` |
| `PasoCalculo` | `PC-SM3-MARGEN-NETO`, `PC-SM3-RATIO`, `PC-SM3-CONTRATOFERTA`, `PC-SM3-DESCUENTO`, `PC-SM3-BRECHA` | `destino`, `decimales` (1, 2, −3, 1, 1) y `limite_inferior_ars=0.0` en la contraoferta |
| `Condicion` | `CND-SM3-R34-RIESGO`, `CND-SM3-R34-DEMANDA`, `CND-SM3-R35-RIESGO`, `CND-SM3-R36-INTERV` | `campo` (`riesgo`/`demanda`/`n_interv`), `operador` (`=`/`>=`), `representacion_version='politicas-bloque-v1'` |
| `Condicion` | `CND-SM2-EST-01-PROCESADOR`, `-01-ORIGEN`, `-02-PROCESADOR`, `-03-LINEA`, `-04-DECLARADA`, `-04-INFORMADA`, `-05-TASADA`, `-06-VALOR`, `-07-ANIO` | `campo`, `operador` (`ausente`/`presente`/`=`), `valor` cuando compara, y la misma versión |
| `Condicion` | `CND-SM0-CRITERIOS`, `-COSTOS`, `-INFERIDOS`, `-PENDIENTES` | `campo` del hecho, `operador='='`, `valor=0` |

### Relaciones nuevas (50)

| Tipo | Cantidad | Detalle |
|---|---|---|
| `INCLUYE` | 21 | 4 al margen, 5 a los pasos de cálculo, 2 a valuación/R2.4, 8 al estado comercial, 2 a la clasificación |
| `REQUIERE {grupo}` | 17 | 4 del margen, 9 del estado comercial, 4 de la clasificación |
| `USA_CRITERIO` | 2 | `SM3-MARGEN-BASE → margen_base` y `CND-SM3-R36-INTERV → umbral_intervenciones` (criterios existentes) |
| `PERTENECE_A` | 10 | reglas nuevas a `:Submodulo` `SM2`/`SM3` (misma convención del PG2) |

Ningún criterio, costo, componente, conjunto difuso, diagnóstico, patrón, `estado_validacion` ni
regla ajena se modifica. El artefacto valida **todas** las precondiciones antes de escribir
(objeto esperado presente una sola vez, objeto nuevo no duplicado, toda propiedad o relación
declarada ausente o ya con el mismo valor, criterios y submódulos de referencia presentes); ante
cualquier conflicto no escribe nada, devuelve `conflictos>0`, `actualizadas=0` y `errores` con el
motivo. La segunda aplicación devuelve `conflictos=0`, `actualizadas=0`.

Corrección estructural previa a TV: las diez relaciones `PERTENECE_A`, que ya figuraban en
las escrituras y en esta allowlist, se incorporaron también a la lista de precondiciones del
artefacto. Así se validan antes de escribir y el contador incluye las 50 relaciones declaradas;
no se cambian reglas de negocio ni se ejecutaron pruebas para esta corrección.

## Activación (la ejecuta el padre en el scratch marcado)

1. Sobre el grafo `EntornoPruebas {id:'mejoras-evaltic'}` (nunca el original), abrir una
   transacción explícita y ejecutar el artefacto una vez.
2. Exigir `conflictos = 0`, `errores = []` y `actualizadas = 93` en la primera aplicación
   (39 nodos nuevos + 4 conjuntos de propiedades declaradas + 50 relaciones).
3. Ejecutarlo de nuevo en la misma transacción: `actualizadas = 0`.
4. Comparar la proyección protegida antes/después y confirmar que el delta es exactamente el de
   esta allowlist; recién entonces confirmar la transacción.
5. Ningún consumidor nuevo debe apuntar al grafo de trabajo hasta que ese grafo tenga el
   artefacto: sin él, SM3, la valuación SM2 y la clasificación final fallan con error explícito
   (no compran ni tasan con valores por defecto).

## Pruebas incluidas en TV

`app/tests/test_politicas_bloque_neo4j.py` (24 pruebas, cada una en una transacción que se
revierte; cargan el artefacto dentro de la transacción y cambian sólo datos):

- margen: política por defecto (base), R3.4, R3.5 con su máximo, R3.6 con prima y orden de la
  traza, operación declarada por la regla, exclusión inválida, precisión de cuantización como
  dato, límite no negativo como dato, precedencia R3.7 conservada;
- valuación: contrato por defecto, escala del VMA, descuento aplicado por la regla, activación de
  R2.4 y su pendiente sin generación anterior, estado resultante y prioridad de las reglas de
  estado, condición con hecho no declarado;
- clasificación: Firme, Provisional por dato inferido/pendiente, criterio sin validar, estado
  resultante como dato, condición inválida;
- artefacto: segunda aplicación sin cambios, conflicto atómico sin escrituras y criterios/costos
  intactos.

Comando único ejecutado en TV (una sola corrida, sin suite de 200 ni matrices): módulo nuevo,
condiciones SM1 y filtros R3.7/R3.8. Los módulos completos propuestos inicialmente no se
agregaron como gates:

```bash
(cd app/tests && EVALTIC_NEO4J_PRUEBAS_URI=bolt://127.0.0.1:17687 PYTHONDONTWRITEBYTECODE=1 \
  /home/alvaro/Universidad/IA/Proyecto/.venv/bin/python -m unittest -v \
  test_politicas_bloque_neo4j test_politicas_sm1_neo4j test_politicas_sm3_filtro_neo4j)
```

Resultado observado: 50 pruebas, salida 0, sin omisiones. No se repite esta corrida ni se
agregan comprobaciones funcionales por cada commit local.

## Qué queda explícitamente afuera

- **P2b** (prioridad entre clases de evidencia textual y restricción de origen en SM1) y la
  construcción de estado/plan de SM1 (T2c implementado y activado sólo en scratch, todavía integrado al cierre del bloque) siguen donde estaban; no se reescriben acá.
- **P5/I13** señales de bloqueo: la lista de ocho señales Python ante fallo de consulta con driver
  existente **no se toca**, ni se agrega caché; si el grafo no tiene esta etapa, la evaluación
  falla con el error explícito que ya usa cada motor. Decisión de negocio pendiente.
- La **cuantización de RIE** (centroide crudo → `round` a 4 → IEEE a 2 → DEM) conserva su
  precisión literal en la consulta difusa: representarla exigiría otra etapa de cálculo y no se
  agregó. La ruta y el orden binario se preservan tal cual.
- Las prioridades de origen de año/W11/RAM se conservan en la consulta; no se declaran
  representadas por la nueva configuración de R2.4 (que sólo aporta activación y familia).
- **Procedencia de la valuación** (`criterios_usados`): la lista de criterios aplicados se deriva
  de hechos que ya resuelve la consulta (estado tasado, origen del año, upgrade). Representar la
  correspondencia hecho→criterio como datos sería un agregado decorativo, así que no se hizo; el
  conjunto de criterios usados no cambia.
- **B3–B5**, recalibración de R2.4, enrutamiento/completitud y la aplicación a la base original
  (P6/T6) siguen separados. Los 61 casos originales no se ejecutaron.
- Sin verificación nativa, sin aprobación y sin declaración de B2 completo: la única verificación
  es la de TV sobre el grafo aislado.
