# La decisión de SM3 se infiere en Neo4j

SM3 ejecuta la inferencia en Neo4j mediante consultas de
[`app/inferencia_sm3.py`](../app/inferencia_sm3.py). **Ejecutar una política en Neo4j no
significa que esté representada como conocimiento:** las condiciones/fórmulas de
`CONSULTA_CRISP` todavía requieren la migración P3. P1 sí representa la correspondencia de
categoría y habilitación de contraoferta en los tres conjuntos `Conveniencia.*` existentes.
El [contrato de migración](CONTRATO_POLITICAS_NEO4J.md) fija las etapas restantes; no se
declara S9 completo. El LLM no toma decisiones; el adaptador valida, registra procedencia y
presenta el resultado.

**Alcance P3a (condición de R3.7).** La condición del filtro R3.7 ya se lee como datos: la
`Regla` `R3.7` guarda `filtro_campo` y `filtro_comparador`, y el umbral es el criterio que ya
enlaza su `USA_CRITERIO` (sin nodos, criterios ni valores nuevos). `CONSULTA_CRISP` consume
esos datos y una configuración ausente, ambigua o inválida no devuelve fila (el adaptador
conserva el error existente); no decide nada en Python. El artefacto
`cypher/Grupo_20_PG3_politicas_sm3_filtro.cypher` está probado en una transacción revertida,
y activado **sólo en el scratch marcado**: dos propiedades nuevas, primera aplicación 1 y segunda 0; grafo protegido validado antes del commit (`ejecuciones/politicas_p3a_activacion.log`). La base original sigue pendiente de P6. No se
migraron las consecuencias de R3.7 ni el resto de la política financiera.

**Alcance P3b (categorías de R3.8).** Las dos categorías que disparan R3.8 ya se leen como
datos: la `Regla` `R3.8` guarda `filtro_riesgo` y `filtro_demanda` y `CONSULTA_CRISP` compara
la entrada con ellas (igualdad de ambas y conjunción finita, en ese orden después de R3.7).
La categoría no se inventa: se valida contra los conjuntos que el grafo ya declara en
`(:VariableDifusa)-[:TIENE_CONJUNTO]->(:ConjuntoDifuso)`, y una configuración ausente o
inválida no devuelve fila (mismo error existente). La traza y el motivo del dictamen
interpolan las categorías leídas (una sola frase fija), con ambos textos por defecto
idénticos a los anteriores. El artefacto
`cypher/Grupo_20_PG3_politicas_sm3_riesgo_demanda.cypher` se probó en transacciones
revertidas y se activó **sólo en el scratch marcado**: primera aplicación 1, segunda 0,
únicamente dos propiedades nuevas y resto del grafo/restricciones idénticos antes del commit
(`ejecuciones/politicas_p3b_activacion.log`). La base original sigue pendiente de P6. No se migraron los márgenes R3.4/R3.5/R3.6, las
fórmulas, la contraoferta ni la precedencia: R3.8 no se declara completa por sus categorías.

## Camino rápido

1. Ver qué resuelve el grafo: `app/inferencia_sm3.py` (la cuantización decimal
   `_CUERPO_CUANTIZADOR` y las consultas `CONSULTA_CRISP` y `CONSULTA_DECISION`).
2. Probar la inferencia contra el Neo4j aislado de pruebas (sólo lectura):

   ```bash
   EVALTIC_NEO4J_PRUEBAS_URI=bolt://127.0.0.1:17687 \
     PYTHONDONTWRITEBYTECODE=1 /home/alvaro/Universidad/IA/Proyecto/.venv/bin/python \
     -m unittest discover -s app/tests -p test_sm3_neo4j.py -v
   ```

3. Probar el pipeline sin Neo4j (los dobles de Cypher viven en
   `app/tests/test_publicaciones_criticas.py`):

   ```bash
   PYTHONDONTWRITEBYTECODE=1 /home/alvaro/Universidad/IA/Proyecto/.venv/bin/python \
     -m unittest discover -s app/tests -v
   ```

## Qué resuelve cada consulta

| Consulta | Resuelve | Devuelve además |
|---|---|---|
| `CONSULTA_CRISP` | margen neto y ratio de reparación (aritmética + cuantización decimal en el grafo), R3.7 → R3.8 → margen requerido (base → R3.4 o R3.5 → R3.6) → contraoferta → brecha y descuento; el campo/comparador de R3.7 y las categorías de R3.8 salen de la `Regla` | decisión y regla de descarte, criterios usados con su procedencia, textos de las reglas activadas en orden, aviso `division_por_cero` |
| `CONSULTA_DECISION` | lee `resultado_decision` y `contraoferta_habilitada` del ConjuntoDifuso correspondiente; valida cardinalidad y contrato, sin elegir por categoría | decisión y contraoferta sugerida |

Los umbrales, márgenes y primas se leen de `:CriterioExperto` **dentro** de la consulta. La
difusa SM3-CONV se sigue evaluando con la función que ya existía (`inferir_sm3_conv_cypher`):
la base Mamdani del grafo no se duplica.

## Política conservada

| Regla | Comportamiento que se mantiene |
|---|---|
| R3.7 | `round(costo / VMA, 2) > CE ratio_reparacion_max` → `DescartarPorRiesgo`; se evalúa primero |
| R3.8 | riesgo `Alto` **y** demanda `Baja` → `DescartarPorRiesgo`, con ambas categorías leídas de `Regla('R3.8')` (`filtro_riesgo`/`filtro_demanda`) y validadas contra los conjuntos del grafo; sólo se evalúa si R3.7 no disparó |
| R3.4 | demanda `Alta` y riesgo `Bajo` → margen requerido = `CE margen_alta_liquidez` |
| R3.5 | riesgo `Alto` → margen requerido = máximo entre `CE margen_base` y `CE margen_riesgo_alto` (excluyente con R3.4) |
| R3.6 | intervenciones ≥ `CE umbral_intervenciones` → margen requerido += `CE prima_fallas` |
| Contraoferta | `max(0, redondeo a miles de VMA − costo − VMA × margen/100)`; nunca negativa |
| Descuento | 0 cuando la contraoferta no es menor que el precio pedido |
| Decisión | `Comprar` → `Comprar`; `Negociar` → `ComprarConOfertaMenor`; `Descartar` → `DescartarPorRiesgo` |

## La cuantización decimal también vive en el grafo

`round(x, 1)`, `round(x, 2)` y `round(x, -3)` de la política anterior redondean el valor
binario IEEE-754 exacto, medio al par. `round()` de Cypher redondea la representación decimal
y **no coincide** en los empates decimales inexactos: `round(6.55, 1)` da 6,5 en Python y 6,6
en Cypher; con `costo / VMA = 101.000 / 200.000 = 0,505` esa diferencia cambia la decisión de
R3.7. El adapter no puede redondear (sería aritmética de negocio en Python), así que la
cuantización se resuelve con aritmética entera explícita dentro de la consulta
(`_CUERPO_CUANTIZADOR` en `app/inferencia_sm3.py`):

1. Casos triviales: `null`, cero con su signo, y valores por debajo de medio cuanto (redondean
   a cero con el signo del valor).
2. **Atajo de representación binaria:** si la separación entre doubles en ese valor,
   `2^(est − 52)`, ya es mayor o igual al cuanto decimal (0,1 / 0,01 / 1.000), se devuelve el
   valor tal cual. La cuantización mueve el valor menos de medio cuanto y el double
   representable más cercano al resultado decimal es el propio valor; tampoco puede haber
   empate: con 1 o 2 decimales, `ulp >= 10^-decimales` implica que `valor · 10^decimales` no
   es un semientero; con miles, `ulp >= 1000` implica que el valor es múltiplo de 1024 y 500
   no lo es. El atajo va antes de la aritmética entera, así que las magnitudes enormes
   (`10^300`) nunca llegan a desbordar.
3. El valor absoluto se normaliza como `m · 2^(est − 52)`: `est` sale del logaritmo y se corrige
   comparando con la potencia efectiva; el escalado por potencias de dos no pierde bits, así
   que `m` es la mantisa entera exacta de 53 bits.
4. `valor · 10^decimales = numerador · 2^dos / denominador`, todo entero (`denominador` = 125
   cuando se redondea a miles).
5. División entera, comparación del resto con la mitad del divisor y desempate al par. Si el
   valor ya es múltiplo exacto del cuanto se devuelve tal cual, sin punto flotante.

La utilidad se aplica cuatro veces en la consulta (margen neto, ratio, contraoferta, brecha y
descuento) y el adapter solo transporta los resultados: no queda ningún redondeo en Python.

**Verificación** contra `round()` de Python: 4.923 comparaciones de la matriz de empates,
ceros con signo, negativos y valores diminutos; 2.196 comparaciones de un barrido de magnitudes
(potencias de dos y sus vecinos binarios desde 2⁻⁶⁰ hasta 2¹⁰²³, los bordes del atajo en
2⁴⁴..2⁶⁴ y los dos valores que habían fallado: `123456789012345.67` con dos decimales y
`10^300` con miles); y 1.350 combinaciones de la política completa. Todas sin diferencias.
Con el atajo, la zona que antes perdía el último dígito (magnitudes donde el cuanto decimal es
más fino que la separación binaria) y la que desbordaba la aritmética entera quedan resueltas
por representación, sin precisión arbitraria ni dependencias.

La traza conserva su forma: `traza["criterios_usados"]` guarda `id`, `valor`, `unidad`,
`version` y `estado` de cada criterio que usó la rama aplicada, en su orden de lectura, y
`traza["reglas"]` guarda los textos en el mismo orden que antes.

## Quién tiene la última palabra

- **El LLM de entrada** extrae hechos y fallas; no completa valores ni decide.
- **El LLM de salida** redacta el dictamen; nunca reemplaza `decision`, `categoria_difusa`,
  `conveniencia_score` ni `indicadores`. Si el texto inventa cifras, se descarta y se usa el
  dictamen determinístico del grafo.
- **El grafo** decide: compara contra los criterios, combina el margen, calcula la
  contraoferta y mapea la categoría difusa.

## Límites conocidos

| Límite | Detalle |
|---|---|
| Cuantización decimal | Reproduce el redondeo IEEE-754 de la política anterior en todo el rango verificado de magnitudes (2⁻⁶⁰ a 2¹⁰²³, incluidos empates exactos e inexactos). No hay precisión arbitraria ni dependencias nuevas: el atajo de representación binaria cubre los extremos. |
| Mapeo categoría → decisión | P1: propiedades de los tres conjuntos existentes, con `representacion_version=politicas-P1-v1`. Sin configuración válida se devuelve la fila nula que el orquestador rechaza explícitamente, no una compra por defecto. |
| VMA igual a cero | Se conserva el contrato anterior: `ZeroDivisionError("division by zero")`. La consulta informa `division_por_cero` y el adapter traduce el código a la misma excepción, con la traza vacía. Un VMA negativo se evalúa como antes (ratio 0, contraoferta acotada a cero). |
| Dominio de entrada | Se conserva el de la política anterior: `int`, `float` y `bool` como 0/1. Cualquier otro tipo falla con `TypeError` —la misma clase que producía la aritmética anterior— con un mensaje propio que nombra el campo, en lugar de dejar que la consulta convierta `"350000"` en silencio. |
| Alcance | La ejecución/paridad previa de SM1/SM2/SM3 no acredita representación completa. P1 cubre I8; P2–P5 migran condiciones, fórmulas, estados y señales sobre el modelo existente, sin recalibrar ni reactivar reglas reemplazadas. |

## Verificación

- [ ] `test_sm3_neo4j.py` pasa contra el Neo4j aislado marcado (`:EntornoPruebas {id:'mejoras-evaltic'}`).
- [ ] La suite offline sigue verde sin Neo4j (el módulo de Neo4j se omite solo).
- [ ] El dictamen del LLM no cambia la decisión ni los indicadores del grafo.
- [ ] Los criterios declarados en la traza son los del grafo, no los que lea Python.

## Actualización P1: datos antes del consumidor

El artefacto [Grupo_20_PG3_politicas.cypher](../cypher/Grupo_20_PG3_politicas.cypher) es
una sola consulta aditiva. No ejecuta PG2, no refresca mercado ni modifica parámetros
Mamdani, costos, CE o validación experta. Antes de cambiar nada exige los tres nodos/enlaces
correctos y propiedades nuevas ausentes o iguales a lo esperado. Cualquier conflicto
rechaza el conjunto completo: `configuradas=0`, `actualizadas=0`, `errores` no vacío.

Se ejecuta en una transacción explícita, comprobando `configuradas=3` y `errores=[]`
**antes** de confirmar. Primera aplicación sin datos P1: `actualizadas=3`; segunda:
`actualizadas=0`. No ejecutar la recarga general ni continuar ante un resultado rechazado.
En esta etapa sólo se aplicó al scratch marcado. La aplicación original sigue pendiente
del acceso permitido, inventario, respaldo y recuperación P6; no desplegar el consumidor
nuevo contra una base que todavía no tenga esta actualización.

La actualización conserva `c`, `sigma`, `tipo`, `etiqueta`, relaciones y
`estado_validacion`. La versión de representación no valida el conocimiento experto ni
altera Firme/Provisional. Los valores originales siguen habilitando oferta sólo en
Negociar; cambiar ese dato en el grafo, no el nombre de categoría en código, decide ahora
la habilitación.

Pruebas de representación y protección, en transacciones que se revierten:

```bash
EVALTIC_NEO4J_PRUEBAS_URI=bolt://127.0.0.1:17687 \
  PYTHONDONTWRITEBYTECODE=1 /home/alvaro/Universidad/IA/Proyecto/.venv/bin/python \
  -m unittest discover -s app/tests -p test_politicas_neo4j.py -v
```

Evidencia P1: RED 3 fallos → GREEN 7/7; suite completa 191/191 sin omisiones;
diferencial de 12 entradas/rutas públicas contra `c46164f`, sin diferencias de resultado,
excepción, stdout o stderr. Se conserva el primer intento de carga fallido por el
comparador Date/DateTime del arnés: rollback confirmado, corregida serialización, sin
ampliar allowlist. Logs y JSON en `docs/ejecuciones/politicas_p1_*`.

## Actualización TB: margen y cuantización como datos

El margen requerido ya no se decide con un `CASE` de riesgos y demandas en la consulta. La etapa
`SM3-margen` del artefacto
[Grupo_20_PG3_politicas_bloque.cypher](../cypher/Grupo_20_PG3_politicas_bloque.cypher)
declara, como datos, el paso 0 (`SM3-MARGEN-BASE` → CE `margen_base`), R3.4 (`asignar`
CE `margen_alta_liquidez`), R3.5 (`maximo` CE `margen_riesgo_alto`) y R3.6 (`sumar`
CE `prima_fallas`), con su `prioridad_inferencia`, su `grupo_exclusion` y sus condiciones
(`riesgo = 'Bajo'`, `demanda = 'Alta'`, `riesgo = 'Alto'`, `n_interv >= CE umbral_intervenciones`).
La consulta evalúa esos grupos (OR dentro del grupo, AND entre grupos) y combina los efectos
según la operación declarada. Un empate dentro del mismo grupo de exclusión, un miembro del
manifiesto que no coincide con `ids_requeridos`, una operación o un destino no admitidos, o un
efecto sin exactamente un criterio cortan la evaluación sin fila: el motor informa el error
existente, nunca un margen favorable por defecto.

La etapa `SM3-calculo` declara además **qué resultado se cuantiza y con qué precisión**
(`PasoCalculo.margen_neto=1`, `ratio_reparacion=2`, `contraoferta=-3` con
`limite_inferior_ars=0.0`, `descuento=1`, `brecha=1`). Cambiar `decimales` o el límite en el
grafo cambia la salida pública sin editar Python; el algoritmo IEEE del cuantizador y la
expresión aritmética de cada paso siguen siendo mecanismo fijo. La traza (`reglas_activadas`)
se arma con el `traza_texto` de cada regla aplicada, en el mismo orden de prioridad que antes,
y la procedencia conserva exactamente el mismo conjunto y orden de criterios
(`margen_base`, paso 1 aplicado, `umbral_intervenciones`, `prima_fallas` si corresponde).

Se conserva R3.7 antes de R3.8 y el margen (base → R3.4 o R3.5 → R3.6) después: los filtros
crisp siguen resolviéndose primero y, si descartan, el margen y la contraoferta quedan nulos.
Detalle del delta, allowlist y activación en
[ejecuciones/politicas_bloque_implementacion.md](ejecuciones/politicas_bloque_implementacion.md).

## Siguiente paso

P2: representar condiciones/precedencias técnicas, sin cambiar diagnóstico ni costos.
Continuidad y requisitos en
[`odd/tasks/migracion-politicas-neo4j.md`](../odd/tasks/migracion-politicas-neo4j.md).
R3.9/R3.10/R3.11 siguen reemplazadas; no activarlas por enumerar todas las reglas.
