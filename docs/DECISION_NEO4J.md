# La decisión de SM3 se infiere en Neo4j

La política crisp de la operación (R3.7, R3.8, margen requerido, contraoferta y mapeo de la
categoría difusa a la decisión) dejó de estar escrita en Python: hoy son consultas Cypher en
[`app/inferencia_sm3.py`](../app/inferencia_sm3.py). El motor de
[`ejecutar_motor_sm3`](../app/orquestador_evaltic.py) solo valida la entrada, registra la
procedencia que devuelve el grafo y arma la salida pública. Cumple el criterio S9: el LLM no
toma decisiones de negocio y Python no lee criterios para decidir.

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
| `CONSULTA_CRISP` | margen neto y ratio de reparación (aritmética + cuantización decimal en el grafo), R3.7 → R3.8 → margen requerido (base → R3.4 o R3.5 → R3.6) → contraoferta → brecha y descuento | decisión y regla de descarte, criterios usados con su procedencia, textos de las reglas activadas en orden, aviso `division_por_cero` |
| `CONSULTA_DECISION` | categoría difusa de SM3-CONV → tipo de decisión; contraoferta habilitada solo al negociar | decisión y contraoferta sugerida |

Los umbrales, márgenes y primas se leen de `:CriterioExperto` **dentro** de la consulta. La
difusa SM3-CONV se sigue evaluando con la función que ya existía (`inferir_sm3_conv_cypher`):
la base Mamdani del grafo no se duplica.

## Política conservada

| Regla | Comportamiento que se mantiene |
|---|---|
| R3.7 | `round(costo / VMA, 2) > CE ratio_reparacion_max` → `DescartarPorRiesgo`; se evalúa primero |
| R3.8 | riesgo `Alto` **y** demanda `Baja` → `DescartarPorRiesgo`; sólo se evalúa si R3.7 no disparó |
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
| Mapeo categoría → decisión | El grafo no representa hoy esa correspondencia como relación; está declarada explícitamente en `CONSULTA_DECISION`. Candidato a conocimiento versionado en un bloque futuro. |
| VMA igual a cero | Se conserva el contrato anterior: `ZeroDivisionError("division by zero")`. La consulta informa `division_por_cero` y el adapter traduce el código a la misma excepción, con la traza vacía. Un VMA negativo se evalúa como antes (ratio 0, contraoferta acotada a cero). |
| Dominio de entrada | Se conserva el de la política anterior: `int`, `float` y `bool` como 0/1. Cualquier otro tipo falla con `TypeError` —la misma clase que producía la aritmética anterior— con un mensaje propio que nombra el campo, en lugar de dejar que la consulta convierta `"350000"` en silencio. |
| Alcance | Este cambio cubre SM3. Las decisiones crisp que todavía viven en SM1 (fallas, cargador, pantalla) y en SM2 (pendientes de tasación) no se tocaron. |

## Verificación

- [ ] `test_sm3_neo4j.py` pasa contra el Neo4j aislado marcado (`:EntornoPruebas {id:'mejoras-evaltic'}`).
- [ ] La suite offline sigue verde sin Neo4j (el módulo de Neo4j se omite solo).
- [ ] El dictamen del LLM no cambia la decisión ni los indicadores del grafo.
- [ ] Los criterios declarados en la traza son los del grafo, no los que lea Python.

## Siguiente paso

Revisar con el experto si el mapeo categoría difusa → decisión y las reglas R3.9/R3.10/R3.11
deben representarse como relaciones del grafo, y registrar el bloque en
[`odd/tasks/mejoras-evaltic.md`](../odd/tasks/mejoras-evaltic.md).
