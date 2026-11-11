# B2 — cierre técnico y límites de la evidencia

La inferencia técnica, la valuación y la decisión se trasladaron a Neo4j.
Este cierre de código **no certifica una carga sobre la base original ni una nueva corrida real de 61 publicaciones**. La entrevista y la validación del experto siguen pendientes.

## Resultado funcional verificado

- Un síntoma sin diagnóstico confirmado queda en `VerificacionPendiente`, no en compra favorable con costo cero ni en inviabilidad confirmada.
- La evidencia explícita del operador tiene un canal separado. La extracción del LLM no autoriza diagnóstico, plan ni costo.
- Un diagnóstico sin reparación o sin costo conocido falla con `ConocimientoFaltante`; un costo conocido de cero sigue siendo válido.
- El grafo resuelve precedencias, deduplicación del plan, cantidades, costos, upgrades, valuación, márgenes, contraoferta y decisión. Python transporta los resultados.
- Los CE-31/32 son conocimiento **Provisional**, no validado por Matías Romero. La procedencia adicional no se oculta para fingir una salida Firme.
- RIE conserva la categoría calculada sobre el centroide crudo, el redondeo a cuatro decimales del grafo y la cuantización IEEE-754 a dos decimales del contrato previo. Esa segunda operación ahora ocurre en Cypher antes de alimentar DEM.

## Verificaciones independientes

| Ejecución | Alcance y resultado |
| --- | --- |
| I, `mwbfpnum-i-wlim` | SM1/SM2 y aislamiento; encontró un error real en `consultar_sm1(verbose=True)` para pendientes/error. Se corrigió con RED/GREEN. |
| J, `mwbgblql-j-8924` | 182 pruebas con Neo4j, sin omisiones; 90 offline con 14 omisiones. Revalidó el arreglo verbose y SM3/S4/S8. Encontró que el redondeo legado de RIE todavía alimentaba DEM desde Python: faltaba S9. |
| K, `mwbh3tqe-k-drfo` | Falló el proveedor: **cero herramientas, cero pruebas y ningún veredicto**. Se preserva; no se computa como aprobación. |
| L, `mwbhjn5o-l-jxtj` | Nueva ejecución del mismo rol, solicitada explícitamente por el humano. **PASS acotado a RIE→DEM y consumidores**, sin blockers. Dos pruebas enfocadas y suite de **184 pruebas, sin omisiones, exit 0**. |

El PASS de L completa la prueba independiente que faltaba al candidato revisado por I/J; no reemplaza ni amplía retroactivamente sus alcances. No es una aprobación nativa de RDD.

### Sondas de L

El verificador informó estos resultados, ejecutados contra el motor público y un Neo4j aislado con marcador `mejoras-evaltic`:

- Matriz de 396 entradas: **264 comparables sin diferencias** en score/categoría y **132 sin soporte difuso en ambas versiones**. No son 396 resultados calculados exitosamente.
- Otros 16 extremos/fronteras conservan resultado o ausencia de resultado del legado.
- Tres variantes tasadas: DEM recibe exactamente el score público de RIE, idéntico al legado; demanda y decisión conservadas. Una variante Ryzen 5 4600H queda pendiente antes de ejecutar RIE por falta de muestras, como antes.
- Grafo antes/después: 866 nodos, 1964 relaciones y 32 criterios, con digest idéntico. Estado del workspace idéntico.
- `.env` no leído: `dotenv.load_dotenv` reemplazado antes de importar, driver explícito al scratch sin autenticación. No se usaron LLM, API de proveedor ni base original.

Evidencia primaria informada por L: `/tmp/verify-rie-GAYoam/` (`focused.log`, `focused2.log`, `suite.log`, `salida_probe_rie2.json` y sondas). Se preserva, sin limpieza ni lectura adicional del padre sobre rutas externas. El reporte de L entregado a esta sesión y su persistencia Engram registran la procedencia.

El preflight del padre contó 29 archivos/648801 bytes **antes** de actualizar el seguimiento con L29; el payload posterior de L contó 29/649565. El archivo de seguimiento cambió entre ambas mediciones. La diferencia de tamaño no se presenta como prueba de igualdad byte a byte de todo el payload.

## Intentos fallidos y límites que se conservan

- L invocó inicialmente la prueba enfocada desde un directorio incorrecto: `ModuleNotFoundError`, exit 1, sin prueba del producto ejecutada. Corrigió el directorio dentro de su ejecución y observó 2/2 y después 184/184. No se oculta el primer comando fallido.
- El diferencial previo del padre, `mejoras_b2_rie_diferencial.json`, conserva 24 cadenas completas, ocho resultados RIE `None` equivalentes en los que **el arnés no ejercitó DEM**, y tres rutas públicas completas. No se informa como 35 ejecuciones completas.
- Dos resultados integrales sólo agregaron CE-31 Provisional a `criterios_pendientes`, por el traslado solicitado de conocimiento térmico. Los análisis originales terminaron en exit 1 (procedencia adicional y, después, ocho errores del arnés); `mejoras_b2_rie_diferencial_clasificado.json` explica los límites sin reejecutar ni borrar fallos.
- La prueba de costo faltante de SM1 se escribió junto con la reescritura: no hubo RED ejecutado propio. No se inventa ese paso.
- Los otros redondeos Python BAT/TER/DEM/CONV/valor mostrado fueron revisados por linkage: hoy sólo se consumen sus categorías o son formato. Si aparece un consumidor numérico de esos scores, debe volver a comprobarse S9.
- Valores fuera del soporte difuso pueden devolver `None` y producir el error ya existente. No se introdujo un valor favorable por defecto.
- Los auxiliares externos declarados por L (`/tmp/gitstatus_before_488365.txt`, `/tmp/verify_rie_scratch_path_488365.txt`) y todos los temporales anteriores se conservan. La sugerencia del hijo de borrarlos no autoriza al padre ni levanta una denegación previa.

## Entrega local por unidades

Los cortes se preparan mediante blobs del índice y se exportan a un directorio ignorado para probar **exactamente el contenido de cada corte**. El árbol de trabajo final aprobado no se sobrescribe. No se eliminan pruebas/comentarios ni se comprime código para reducir artificialmente el tamaño.

1. Diagnóstico y reacondicionamiento SM1, seed aditivo, interfaz y pruebas del mismo comportamiento.
2. Política SM3 y cuantización numérica, con pruebas y guía.
3. Valuación SM2 y compatibilidad, con pruebas y guía.
4. RIE→DEM: último cambio de contrato, con regresiones enfocadas.
5. Cierre documental y evidencia, enlazando los commits observados.

Los cortes de migración superan el objetivo de unas 400 líneas: incluyen consultas declarativas, adaptadores y pruebas extensas del mismo comportamiento. Es **sobrecarga de revisión declarada**, no una excepción que habilite push/PR. Se mantienen separadas las tres migraciones y el remanente RIE de alto riesgo. La reversión es por unidad y sus dependientes; no se revierte ni reescribe historia heredada ni se tocan archivos ajenos.

Cada exportación sólo incluye `app/`, `scripts/` y `cypher/` versionados en su índice; no contiene `.env`, `.git`, backups, dependencias ni datos de la base original. Las suites usan el marcador y el driver aislado. Sus resultados se registran en `mejoras_b2_corteN_pruebas.log`.

| Corte | Suite sobre su índice exportado | Resultado |
| --- | --- | --- |
| SM1 | 118 pruebas | exit 0, sin omisiones |
| SM3 | 149 pruebas | exit 0, sin omisiones |
| SM2 | 182 pruebas | exit 0, sin omisiones |
| RIE→DEM, contenido final | 184 pruebas | exit 0, sin omisiones |

Son ejecuciones de regresión sucesivas, **no 633 pruebas diferentes**. La suite final tiene 184.
La ejecución offline posterior al último cambio imprimió `Ran 90 tests` / `OK (skipped=15)`,
exit 0: al retirar deliberadamente `EVALTIC_NEO4J_PRUEBAS_URI`, las clases/módulos que necesitan
Neo4j se omiten explícitamente. La ejecución con URI sí pasó las 184 sin omisiones. Log:
`mejoras_b2_offline_final.log`.

RDD sigue encendido. Los ASSESS por corte comprometido siguen devolviendo `nativeRisk=unassessable`
por archivos sin seguimiento que exigen declaración, incluso con `committedOnly=true`. Su plan
alto por ítem 3 exige autoverificación y verificación independiente, ambas cubiertas; no ofrece
`reviewDue`/START. No se infiere ni inventa aprobación nativa. Un intento de ASSESS desde Codemode
fue rechazado antes de invocación nativa por ser herramienta sólo directa; el ASSESS posterior
se llamó directamente y se conserva ese fallo de preparación del harness.

## Commits y readback final

| Unidad | Commit local |
| --- | --- |
| Diagnóstico y reacondicionamiento SM1 | `33756b8` |
| Política y decisión SM3 | `a3196b1` |
| Valuación y procedencia SM2 | `2d5742b` |
| Cuantización RIE→DEM | `1a19136` |

Los cuatro commits se observaron con exit 0 en `mejoras/b2-diagnostico-neo4j`. La documentación
final se guarda en un commit de cierre aparte; no se publica la rama.

El readback final comprobó siete hashes de los archivos capturados antes de separar los índices:
no cambió el código aprobado. `app/orquestador_evaltic.py` conserva SHA-256
`17d748050d5018becfede2cb7765096dcd597823f406e933ae878e1658cc6f25`.
Corpus y CSV son byte-idénticos a B1; los cuatro nodos AST que contienen la adaptación NVIDIA
(incluido `consultar_llm`) son idénticos al mismo baseline. Compilación de `app/*.py`, LF y
ausencia de diferencias de runtime frente a HEAD: OK. Evidencia:
`mejoras_b2_cierre_integridad.log`.

La primera invocación de este readback terminó en exit 1 porque el padre supuso el archivo
inexistente `app/llm_client.py`, confundiendo el nombre de un test con el módulo de producción.
El comando quedó incompleto; no fue una regresión del producto. Se corrigió la comprobación
para comparar los nodos reales de `orquestador_evaltic.py` contra B1 y se obtuvo el resultado
anterior. No se creó ese módulo ni se modificó el runtime para hacer pasar el chequeo.

## Fuera de este cierre técnico

- T2P: inventario/respaldo y aplicación exclusivamente aditiva sobre la base original; el acceso a `.env` fue denegado y no se sortea mediante otro proceso, contenedor o herramienta.
- Nuevas 61 publicaciones con modelo real y comparación homogénea. La última corrida real continúa siendo la de B1: 50 cumplen, 5 fallan, 6 sondas, cero fallos de infraestructura.
- B3–B5: interpretación contextual de bloqueo, enrutamiento/respaldo y térmico/R2.4/sondas.
- Validación del experto y publicación: no hay push, PR ni cambio de modelo autorizado por este cierre.
- El corpus y sus expectativas históricas se preservan. PC-19 pasa la regla estricta en pruebas controladas; no se etiqueta retrospectivamente como una nueva aceptación real sin la corrida correspondiente.

**Riesgo: ítem 3** — interfaces y lógica compartidas por rutas públicas. Las pruebas funcionales y la verificación independiente son evidencia técnica; la autoridad nativa se informa por separado y no se presume aprobada.
