# P2a — Condiciones de las acciones de SM1 y vínculo de categorías difusas

Corte T2 (P2a/I1) sobre `mejoras/politicas-p2-acciones`, base `e7854e0`. Sólo condiciones de las
acciones y el hecho que vincula la categoría difusa: **no** incluye precedencias de evidencia
(P2b) ni selección de estado/plan (P2c), ni B3–B5. Todo sobre el scratch `mejoras-evaltic`; nada
se aplicó a la base original y no se leyó `.env`.

## Qué quedó representado

- Manifiesto técnico `VP-SM1-ACCIONES` con `INCLUYE` a las ocho reglas de acción y cardinalidad
  declarada de condiciones/criterios.
- 9 `(:Condicion)` con campo, ámbito, comparador y operando: 5 con operador `=`, 2 con operador
  `ausente` y 2 con operando por criterio `CE-01`/`CE-27`; 9 `REQUIERE {grupo}` y 2 `USA_CRITERIO`.
  (Recuento corregido: la redacción anterior decía «8 literales de hecho, 2 por criterio», que
  sumaba diez sobre nueve nodos.)
- 11 relaciones `OBLIGA` existentes con su `etapa` y su `campo` (`categoria_bat` / `categoria_ter`).
- La sección A de `CONSULTA_RESOLUCION` evalúa esas condiciones de forma finita (OR dentro del
  grupo, AND entre grupos) y une las obligaciones difusas; cambiar el dato cambia el plan sin
  editar Python. Las reglas protegidas del seed diagnóstico (`campo`, `valor`, `tarea`, `orden`)
  no se tocaron.

## Evidencia observada

| Paso | Comando | Resultado observado |
|---|---|---|
| RED | `… -p test_politicas_sm1_neo4j.py -v` | exit 1, 9 pruebas, 14 fallos de aserción; sin errores de preparación (`politicas_p2a_red.log`). |
| Activación | `scripts/aplicar_politicas_sm1_pruebas.py` | exit 0; vista protegida P0+P1 igual antes y después; primera aplicación 29 cambios (1 manifiesto, 8 `INCLUYE`, 9 condiciones, 2 criterios, 11 obligaciones); 866/1964/19 → 876/1983/19; segunda aplicación 0 (`politicas_p2a_carga.log`, `politicas_p2a_carga.json`). |
| Re-ejecución | mismo cargador | exit 0, `ya_aplicado`: 0 cambios, configuración aplicada válida (1/9/8/9/2/11), proyección idéntica. |
| GREEN | `… -p test_politicas_sm1_neo4j.py -v` | exit 0, 9/9 OK (`politicas_p2a_green.log`, corte original, antes de la regresión de alcance que agrega la décima). |
| Suite con grafo | `… unittest discover -s app/tests -v` | exit 0, 200 pruebas, sin omisiones (`politicas_p2a_suite.log`). |
| Offline | `… unittest discover -s app/tests -v` sin variables de Neo4j | exit 0, 90 pruebas, OK (17 omisiones por falta de grafo) (`politicas_p2a_offline.log`). |
| Diff | `git diff --check` | exit 0, sin errores de espacio. |

Protección: la vista protegida del grafo (proyección completa sin las piezas que P2a posee) es
idéntica a la foto P0 `d3bff60e…d6fc4` más las nueve propiedades de P1, antes y después del corte.
Las 19 restricciones y todas las entidades previas salvo las 11 `OBLIGA` (sólo `etapa`/`campo`)
quedan iguales, verificado dentro de la transacción antes de confirmar.

## Desvíos conservados

- La primera versión del cargador comparaba los extremos de las relaciones por la propiedad `id`
  en lugar de por `elementId`: el primer rechazo posterior a la carga fue correcto pero por un
  error del verificador. Se corrigió y se volvió a ejecutar; el rechazo quedó en el log.
- El validador de delta exigía el delta completo incluso en una segunda aplicación; se ajustó a
  los contadores declarados por el artefacto y se volvió a ejecutar. Los dos rechazos se conservan
  en `politicas_p2a_carga.log`; el estado aplicado se revalida en cada corrida.
- Consecuencia de esos dos rechazos: el JSON de la primera aplicación fue reescrito por la corrida
  posterior. La aplicación quedó evidenciada por el estado (delta exacto y configuración válida) y
  por el stdout observado (29 cambios; delta 10 nodos / 19 relaciones / 11 obligaciones), no por
  ese archivo.
- La prueba de la primera carga es entonces de sesión: se apoya en el stdout observado en esa
  corrida y en el estado aplicado revalidado después, que es el que sobrevivió. No hay artefacto
  histórico que certifique la primera aplicación y este cierre no la certifica.
- Se declaran como desvíos prohibidos de la corrida anterior: ejecuciones de `docker ps`,
  `docker inspect` y `docker start` para descubrir el entorno de Neo4j, y la escritura del log de
  RED en `/tmp/red.log` antes de usar la ruta de evidencia permitida. No se autorizan
  retroactivamente, no se repiten en este corte y no hay limpieza del temporal externo.
- Los intentos fallidos conservados (verificador por `id` en vez de `elementId`, validador de delta
  y los dos rechazos) siguen en `politicas_p2a_carga.log`; no se borran ni se reescriben.

## Corrección de alcance de la guarda (T2, continuación acotada)

Prueba previa: la tercera subconsulta de la guarda A.0 (`problemas_duplicados`) partía de
`OPTIONAL MATCH (cond:Condicion)` sin alcance. Cualquier condición de otra etapa del grafo (por
jemplo una de SM2/SM3 sin `REQUIERE` desde una regla de `SM1-acciones`) se informaba como «no está
requerida por ninguna regla de la etapa» y convertía un diagnóstico `Viable` en
`ErrorConocimiento`: una guarda global sobre datos ajenos.

Corrección: la guarda queda acotada a las condiciones de la etapa — las que requieren sus reglas
por `REQUIERE` y las que declara su versión de representación —, y se conservan las tres
detecciones: identificador ausente, identificador repetido y condición propia sin regla. Son
cuatro líneas de Cypher en `app/inferencia_sm1.py`; no se reescribió A/B/C/D ni se amplió la
validación general.

| Paso | Comando | Resultado observado |
|---|---|---|
| RED | `… -p test_politicas_sm1_neo4j.py -k test_una_condicion_de_otra_etapa_no_cambia_el_resultado_de_sm1 -v` | exit 1, 1 prueba, 1 fallo: `Viable` pasaba a `ErrorConocimiento` al crear una `Condicion` de otra etapa (`politicas_p2a_arreglo_red.log`). |
| GREEN | `… -p test_politicas_sm1_neo4j.py -v` | exit 0, 10/10 OK (`politicas_p2a_arreglo_green.log`). |
| Preservación | `… -p test_sm1_neo4j.py -k PoliticasMigradasTest -v` | exit 0, 13/13 OK, el comportamiento ordinario de SM1 no cambia (`politicas_p2a_arreglo_preserve.log`). |
| Detecciones propias | verificación en transacción revertida | exit 0: condición propia sin regla y condición propia sin identificador siguen dando `ErrorConocimiento` (`politicas_p2a_arreglo_guard.log`). |

Toda mutación de estas pruebas ocurre en una transacción que se revierte en `finally`; el grafo de
pruebas queda con las 9 condiciones, un manifiesto y el marcador `EntornoPruebas {id:'mejoras-evaltic'}`,
confirmados en `bolt://127.0.0.1:17687`, `neo4j`, `auth=None`.

## Límites

- El proceso histórico sigue **PARTIAL** por los desvíos declarados. La verificación
  independiente `mwcnh8dp-5-zffj` confirmó **PASS técnico de P2a/P3a**, sin bloqueantes,
  con 15 pruebas focalizadas y cuatro rutas públicas iguales a `e7854e0`.
- El diferencial único ejercitó `consultar_sm1`, `ejecutar_motor_sm3`, evaluación integral
  y `asistente_evaltic`, sin LLM. No se probó una invocación CLI separada.
- No hay aprobación nativa. P2b/P2c y el resto de P3 siguen pendientes: no se declara
  completo SM1, B2 ni la política financiera.
- Las dos pruebas adicionales sugeridas por el verificador son opcionales y no se agregan:
  ya observó sus efectos en sondas revertidas y no informó bloqueantes. No se repite el diferencial.
- La suite no acredita los 61 casos reales ni valida las políticas Provisionales con el experto.
- En este corte no se ejecutó la suite completa ni pruebas de SM3: hay un worker concurrente sobre
  `app/inferencia_sm3.py`, su artefacto y sus pruebas. No se verificó ese comportamiento.
- Riesgo vigente: la consulta de SM1 es compartida por evaluación integral, `consultar_sm1` y la
  CLI (Risk: item 3).
- La carga se hizo sobre el scratch; la base original sigue sin vía segura de conexión (T2P/P6).
