# Estado consolidado de las mejoras de EvalTIC

Este documento reúne las mejoras anteriores y las correcciones mínimas más recientes,
con sus archivos, evidencia y pendientes. La estrategia elegida por el operador fue
**copiar la base actual y actualizar esa copia**, y el 13/11/2026 el procedimiento
reproducible `scripts/base_mejoras.sh` la ejecutó en tres tiempos: respaldo verificado de
la original, copia independiente actualizada con las ocho semillas aditivas, y una vez
validada la copia, **promoción de la base original** con respaldo previo obligatorio.
La original pasó de 814 nodos y 1905 relaciones a **931 y 2046**, huella `cf1a70d5…`,
idéntica a la de la copia. El respaldo inmediatamente anterior a esa escritura es
`_respaldo_original/20261113-0126-pre-promocion`, sha256 `4ab2417c…`.

## 1. Resumen de situación

| Parte | Estado registrado |
|---|---|
| Código | Rama `mejoras/politicas-sm1-estado`. El bloque mínimo del código sigue con cambios locales sin commit; esta unidad sólo registró el script de integración y su evidencia. |
| Base original/de trabajo | PG2, actualización histórica del catálogo a 333 avisos y, desde el 13/11/2026, las ocho semillas aditivas del bloque (diagnóstico B2, correcciones mínimas y políticas). Pasó de 814 nodos y 1905 relaciones a 931 y 2046; huella `cf1a70d5…`. |
| Base aislada de pruebas | Diagnóstico, políticas anteriores y correcciones nuevas aplicadas. Último snapshot: 932 nodos, 2046 relaciones, 19 restricciones y marcador de pruebas único. |
| Nueva copia de trabajo | **Creada el 13/11/2026 y ya idéntica a la original promovida**: contenedor `evaltic-neo4j-mejoras` (bolt `127.0.0.1:7688`), volumen `proyecto-ia-final_neo4j_mejoras`. 931 nodos y 2046 relaciones. Queda como gemela de comparación y respaldo caliente, no como base pendiente de promoción. |
| Respaldo | Dos respaldos verificados: `_respaldo_original/20261113-0050/` (estado previo a todo, sha256 `3131c0de…`) y `_respaldo_original/20261113-0126-pre-promocion/` (inmediatamente anterior a escribir la original, sha256 `4ab2417c…`). El primero se restauró con éxito en el volumen de la copia. |
| Validación | Comprobaciones determinísticas: pasaron. Tanda real sobre la copia (13/11/2026): 55/55 expectativas automáticas, 0 incumplimientos, 6 sondas, 0 infraestructura. |
| Conocimiento experto | Provisional; estas ejecuciones no constituyen una validación de Matías Romero. |

Los estados se basan en lo que se ejecutó y se registró. Para esta actualización se consultaron las dos
bases (original y copia) y se corrió la tanda de 61 casos contra la copia. No hubo lectura de secretos
en esta sesión: la configuración privada del proveedor la inyectó `docker compose` y sus valores nunca
entraron en la evidencia. No hubo push, PR, operaciones destructivas ni cambios en la base original.

## 2. Cambios implementados, agrupados por función

### Entrada, proveedor LLM y precio

- Se conserva la separación: el LLM enruta, extrae y redacta; la inferencia simbólica determina
  el resultado. La ejecución real más reciente utilizó la API compatible con OpenAI de NVIDIA.
- El precio se contrasta con el texto del aviso: importes cortos, cero, separadores de miles,
  expresiones en pesos y rangos no deben depender de un monto completado por el LLM.
- Un precio literal de `$1` se conserva como 1: no se agregó un precio mínimo comercial inventado.
  La falta de un precio comercial válido impide tasar.
- Se mantienen las defensas existentes contra procesadores completados por el LLM y la
  validación de año. Son protecciones conservadas, no nuevas reglas expertas de este bloque.

Archivos: [orquestador](../app/orquestador_evaltic.py),
[pruebas del cliente LLM](../app/tests/test_llm_client.py).
Evidencia histórica: [B0/B1](ejecuciones/mejoras_b1_offline.log).

### SM1: diagnóstico y reacondicionamiento

- La resolución técnica se ejecuta en Cypher y utiliza el catálogo de síntomas, diagnósticos,
  intervenciones y costos del grafo.
- Un síntoma sin diagnóstico puede dejar `VerificacionPendiente` por R3.3c; no se convierte
  automáticamente en una reparación ni en una falla irreversible.
- La evidencia del operador se aporta por un canal separado (`verificacion_tecnica`), también
  disponible en CLI/web. Ni el texto del vendedor ni un campo del LLM sustituyen esa verificación.
- Un diagnóstico reparable sin costo conocido produce conocimiento faltante. Un costo conocido
  en cero no se confunde con ausencia de conocimiento.
- Las condiciones de acciones técnicas se representan con nodos `Condicion` y sus relaciones.
  `estado_resultante` se lee del grafo para R1.1 y R3.3c; no se declara migrada toda la selección
  de estados ni toda la precedencia entre evidencias.
- Se corrigió el error de uso de `plan` antes de inicializarlo en la ruta verbose.

Archivos: [motor SM1](../app/inferencia_sm1.py), [orquestador](../app/orquestador_evaltic.py),
[guía de diagnóstico](#sm1-diagnóstico-y-reacondicionamiento).
Evidencia y límites históricos: [cierre B2](ejecuciones/).

### SM2: valuación comercial

- Se mantiene eliminada la vía que reutilizaba decisiones guardadas de casos PG2 como atajo
  de valuación: el aviso se evalúa por sus componentes, no por una coincidencia parcial de modelo.
- La valuación por componentes, RAM tasada, año, compatibilidad W11, antigüedad y estados
  comerciales se resuelven en Cypher; se mantiene el wrapper compatible de nueve campos.
- El grafo aporta la aplicación del descuento de negociación, revalorización por upgrade y
  escala de redondeo del VMA, además de la activación de R2.4 y su requisito de misma familia.
- Ocho reglas ordenadas representan estados comerciales y sus motivos.
- Se conserva la secuencia numérica RIE → cuantización → DEM; no se recalibró para mejorar
  artificialmente los casos. Parte de su precisión y de la prioridad de fuentes sigue en la consulta.

Archivos: [orquestador](../app/orquestador_evaltic.py), [valuación en Neo4j](#sm2-valuación-comercial).
No se confunde ejecución en Cypher con representación completa de cada política como datos.

### SM3 y clasificación final

- La correspondencia entre categoría de conveniencia y decisión/contraoferta se lee de los
  conjuntos difusos del grafo.
- R3.7 lee el campo y comparador del filtro de ratio de reparación; R3.8 lee las categorías
  de riesgo y demanda. Se conserva la prioridad de R3.7 sobre R3.8.
- El margen requerido usa etapas y operaciones declaradas: base → R3.4 o R3.5 → R3.6,
  con `asignar`, `maximo` y `sumar`, sin duplicar los criterios expertos.
- El grafo indica destino/precisión de cinco cuantizaciones y el límite inferior de la contraoferta.
  El cuantizador IEEE y las expresiones aritméticas finitas siguen siendo mecanismo de ejecución.
- La clasificación `Firme`/`Provisional` consulta reglas y condiciones del grafo sobre criterios,
  costos, inferencias y pendientes efectivamente registrados en la traza.

Archivos: [motor SM3](../app/inferencia_sm3.py), [orquestador](../app/orquestador_evaltic.py),
[decisión en Neo4j](#sm3-y-clasificación-final).
El [bloque práctico](ejecuciones/politicas_bloque_activacion.log) agregó 39 nodos,
50 relaciones y propiedades en cuatro reglas existentes; su segunda aplicación dio cero cambios.

### Correcciones mínimas más recientes

| Caso | Qué cambió |
|---|---|
| PC01: aviso incompleto | Evidencia de computadora/notebook más catálogo permite reconocer el dominio. Una marca sola no basta; reconocer el aviso no autoriza inventar datos ni tasarlo incompleto. |
| PC15: temperatura | Se separan throttling falso, verdadero y ausente. Falso usa caída 0; verdadero y ausente referencian CE-32 y CE-31 existentes. La negación explícita corrige también el hecho publicado si el extractor lo contradice. No se cambiaron gaussianas ni costos. |
| PC17/50: falsos bloqueos | Se eliminan el vocabulario de palabras sueltas y el fallback silencioso de esa detección. Patrones contextuales del grafo distinguen señales positivas, negaciones y expresiones como «cuenta con». |
| PC44: síntoma sin diagnóstico | Se reconoce recalentamiento/baja de frecuencia y se conserva pendiente R3.3c, sin inferir reparación. Se alineó únicamente su expectativa con aprobación humana: VMA/costo cero y plan vacío. No se presenta como reparación realizada. |
| PC48: error histórico | El ejecutor informa clase/categoría sin cuerpo privado. PC48 pasó en la última tanda; eso no demuestra cuál fue la causa de su RuntimeError anterior. |
| Devolución PI4 SM1: datos ausentes | Ciclos de batería ausentes ya no se aplican en silencio: el supuesto se declara como nodo `SupuestoOperativo` en el grafo y la respuesta lo informa en la línea «Datos asumidos por el motor». La temperatura ausente sigue sin asumirse: queda pendiente. |
| Casos integrados del PG3 (13/11/2026) | Los cinco casos daban 2 de 5. Causa: `sin_tratamiento` compara el texto libre de las fallas con los patrones del grafo, y una sola falla mal redactada anulaba el plan entero. Se agregaron patrones de redacción (batería que dura poco, service de limpieza, upgrade a SSD, y descarte de «sin soporte W11», «equipo antiguo», «upgrade de memoria», que son riesgo o plan y no fallas). Resultado: 5 de 5 y 4 de 4 en el enrutador, sin cambios de código. R3.3c sigue intacta: un síntoma desconocido sigue quedando pendiente. |

El nuevo conocimiento comprende **17 nodos y 13 relaciones**. Se conservaron todas las
entidades previas y restricciones; la segunda aplicación no produjo cambios.
Además, SM1 filtra los patrones por ámbito de diagnóstico para no mezclar patrones del enrutador.
El sufijo público del motivo R3.3 se restauró usando la regla obtenida del grafo.

Archivos: [semilla mínima](../cypher/Grupo_20_PG3_correcciones_minimas.cypher),
[regresiones con Neo4j](../app/tests/test_correcciones_minimas_neo4j.py),
[guía del bloque](#correcciones-mínimas-más-recientes),
[evidencia final](ejecuciones/correcciones_minimas_61_guardas.json).

### Catálogo, operación y herramientas de comprobación

- La actualización histórica del mercado dejó 333 avisos, 93 procesadores y 46 líneas.
  Su aplicación a la original está registrada en la [evidencia del catálogo](ejecuciones/integracion_neo4j_verificacion_carga.log).
- Se reparó históricamente la disponibilidad de APOC en la instancia original, con Neo4j/APOC
  5.26.32 y respaldo local. Es una reparación operativa previa, no una nueva regla ni una migración
  de políticas. El historial está en el [seguimiento de migración](#4-qué-se-verificó-y-qué-significan-los-resultados).
- La inspección del Neo4j original mediante MCP quedó en modo sólo lectura; no es un canal
  autorizado para aplicar migraciones. Esa configuración local y la reparación operativa no
  sustituyen las semillas del repositorio ni se despliegan simplemente copiando los archivos Python.
- El corpus contiene 61 publicaciones sintéticas críticas: 55 con expectativa automática y
  seis sondas. No son los 333 avisos reales usados para calibrar el mercado.
- El [ejecutor público](../scripts/probar_publicaciones.py) conserva códigos 0 (expectativas
  satisfechas), 1 (incumplimientos) y 2 (infraestructura). No expone salida cruda ni credenciales.
- El doble offline de clasificación se actualizó porque no simulaba una consulta introducida por
  la migración anterior. El fallo inicial quedó preservado; no se cambió el motor para ocultarlo.

## 3. Archivos de conocimiento que debe contemplar la integración

Esta tabla es un **inventario**, no una secuencia certificada de aplicación. Cada artefacto
requiere contrastar sus dependencias, identificadores y conflictos con la copia de destino.
Que un archivo sea idempotente no garantiza que sea seguro ejecutarlo sobre cualquier base.

| Archivo en `cypher/` | Aporte |
|---|---|
| [Grupo_20_PG3_diagnostico.cypher](../cypher/Grupo_20_PG3_diagnostico.cypher) | Síntomas, diagnósticos, intervenciones y resolución técnica B2. |
| [Grupo_20_PG3_politicas.cypher](../cypher/Grupo_20_PG3_politicas.cypher) | Correspondencia comercial de conveniencia. |
| [Grupo_20_PG3_politicas_sm1_acciones.cypher](../cypher/Grupo_20_PG3_politicas_sm1_acciones.cypher) | Condiciones de acciones técnicas. |
| [Grupo_20_PG3_politicas_sm1_estado.cypher](../cypher/Grupo_20_PG3_politicas_sm1_estado.cypher) | Estados resultantes de R1.1/R3.3c. |
| [Grupo_20_PG3_politicas_sm3_filtro.cypher](../cypher/Grupo_20_PG3_politicas_sm3_filtro.cypher) | Filtro de R3.7. |
| [Grupo_20_PG3_politicas_sm3_riesgo_demanda.cypher](../cypher/Grupo_20_PG3_politicas_sm3_riesgo_demanda.cypher) | Categorías de R3.8. |
| [Grupo_20_PG3_politicas_bloque.cypher](../cypher/Grupo_20_PG3_politicas_bloque.cypher) | Márgenes, cuantizaciones, valuación, estados SM2 y clasificación SM0. |
| [Grupo_20_PG3_correcciones_minimas.cypher](../cypher/Grupo_20_PG3_correcciones_minimas.cypher) | Dominio/precio, bloqueo contextual, mapeo térmico y síntoma PC44. |
| [Grupo_20_PG3_supuestos_operativos.cypher](../cypher/Grupo_20_PG3_supuestos_operativos.cypher) | Supuestos operativos: qué asume el motor cuando falta un dato que participa de una regla (devolución de la cátedra PI4 SM1). |
| [Grupo_20_PG3_patrones_redaccion.cypher](../cypher/Grupo_20_PG3_patrones_redaccion.cypher) | Redacciones del aviso que declaran una intervención conocida o que no son fallas. Sin ellos, una sola falla mal redactada anulaba el plan completo y forzaba VerificacionPendiente. |

**No usar como migración aditiva el loader actual** [cargar_grafo.sh](../scripts/cargar_grafo.sh):
siempre ejecuta el refresco de mercado y todavía no incluye todas estas políticas.
El bloque 0 de [PG2](../cypher/Grupo_20_PG2_U1_carga.cypher) borra datos. Copiar la base actual
no requiere volver a ejecutar PG2 ni recalibrar el mercado para incorporar estas mejoras.

La vía aditiva certificada es [base_mejoras.sh](../scripts/base_mejoras.sh), que respalda el
volumen, restaura la copia en un volumen nuevo, aplica **sólo** las ocho semillas de la tabla
anterior en el orden en que aparecen y descarta la copia si su huella no coincide con la
original. No usa PG2 ni `Grupo_20_PG3_mercado.cypher`.

## 4. Qué se verificó y qué significan los resultados

| Etapa | Evidencia observada | Alcance |
|---|---|---|
| B2 funcional histórico | 184 pruebas con grafo, sin omisiones | Ejecución/paridad acotadas; no cierre exhaustivo de representación ni nueva tanda real de61. |
| Bloque práctico de políticas | 50/50, exit0, siete comparaciones de preservación iguales | Base aislada; no prueba del asistente completo. |
| Correcciones mínimas: independiente | 9/9 con subcasos, exit0, sin omisiones; dos rutas públicas diferenciales idénticas | Neo4j real y LLM simulado; transacciones revertidas y snapshot intacto. |
| Correcciones mínimas: offline | 45/45 después de corregir el doble; el primer intento tuvo 39 errores y se conservó | No sustituye al LLM real ni a la prueba del grafo. |
| Motivo R3.3 | Un test dirigido con grafo real, exit0 | Corrección posterior al hallazgo independiente, sin repetir su tanda. |
| Tanda real previa (scratch) | 61 intentados, 60 completados; 54 cumplen, 0 incumplen, 6 sondas, 1 infraestructura; exit2 | PC26 sin acreditar por ConnectionError al invocar la API remota. No era 55/55. |
| **Integración en la copia (13/11/2026)** | **61 intentados, 61 completados; 55 cumplen, 0 incumplen, 6 sondas, 0 infraestructura; exit0** | Primera corrida real sin errores de infraestructura: PC26 quedó acreditado. Sobre la nueva copia de trabajo, no sobre el scratch. |
| **Promoción sobre la original (13/11/2026)** | Respaldo previo, ocho semillas aditivas, reinicio y verificación: 814→931 nodos, 1905→2046 relaciones, huella `cf1a70d5…` | La original quedó con contenido **equivalente a la copia**: mismo sha256 sobre etiquetas+propiedades de cada nodo y sobre tipo+propiedades+extremos de cada relación. La tanda de 61 no se repitió sobre la original; es esa equivalencia la que transfiere la evidencia. |

La tanda sobre la copia cumplió **55/55 expectativas automáticas con 0 infraestructura**, incluidas
PC01/15/17/26/44/48/50 según el contrato acordado. NVIDIA fue el proveedor real (`nvidia/nemotron-3.5-lightning-30b-a3b`),
usado desde `docker compose run` con la configuración privada inyectada por el propio Compose: sus
valores nunca se exportaron a esta sesión ni se registraron en la evidencia. La tanda previa del
scratch quedó con PC26 sin acreditar por un `ConnectionError`; en esta corrida PC26 completó y cumplió,
lo que acredita que el caso servía y el fallo anterior fue de transporte.

El grafo permaneció idéntico antes y después de la tanda: la copia conservó la huella
`cf1a70d5…` (931 nodos, 2046 relaciones) y la original `364ab2d5…` (814 nodos, 1905 relaciones).
La guarda está en [las guardas de la integración](ejecuciones/integracion_copia_mejoras_61_guardas.json).
En el scratch la huella histórica era `d68168fd…` con 932 nodos y 2046 relaciones.
Los conteos y hashes pertenecen a cada base concreta, no son valores que deba imponer una base futura.

**No confundir las tandas históricas:** tras B1 hubo 50 cumplen/5 incumplen/6 sondas/0 infra;
tras el bloque de políticas hubo 49/5/6/1 (infra PC48); la última es 54/0/6/1 (infra PC26).
No son un experimento A/B controlado ni permiten atribuir diferencias sólo a la migración.
Fuentes: [B0/B1](ejecuciones/mejoras_b1_offline.log),
[tanda previa](ejecuciones/publicaciones_61_scratch.LGf88w.log),
[tanda actual y guardas](ejecuciones/correcciones_minimas_61_guardas.json).
Los fallos y desvíos de proceso están preservados en esos registros; no hay aprobación nativa de revisión.

### Qué son las seis sondas

Son casos exploratorios sin una expectativa automática acordada. Se registra lo que hace
el sistema, pero no se los cuenta como aprobados ni fallidos. No significa que estén resueltos.

| Sonda | Qué observa |
|---|---|
| PC27 | Moneda extranjera en el aviso. |
| PC36 | MacBook sin procesador especificado y posible invención del extractor. |
| PC40 | Batería con buena salud y muchos ciclos. |
| PC47 | Síntoma «se apaga sola». |
| PC59 | Instrucción adversaria que pretende ocultar una falla. |
| PC60 | Instrucción adversaria que pretende imponer la decisión. |

Para convertirlas en aceptación hay que acordar el comportamiento correcto y su respaldo
experto cuando corresponda, no inventar una expectativa para declarar verde la corrida.
Corpus y detalle: [casos_publicaciones.json](../app/tests/casos_publicaciones.json),
[guía de pruebas](#7-consulta-rápida-y-evidencia-conservada).

## 5. Pendientes que no se deben presentar como terminados

- PC26 quedó **acreditado** en la tanda del 13/11/2026 sobre la copia (ver §4). No se repitió la corrida
  previa del scratch: la evidencia de este bloque es la de la copia, no la del scratch.
- Registrar los commits locales del bloque mínimo; no hubo push/PR ni entrega de esa unidad.
- Completar, si se solicita, la representación pendiente de precedencias entre evidencias SM1,
  prioridades de origen año/W11/RAM, procedencia de criterios SM2 y precisión literal de RIE.
  Las correcciones de bloqueo cubren parte del problema anterior de señales, no todo B3–B5.
- Resolver los pendientes funcionales declarados, como R1.4 `NoAmpliable` y R3.1b, sin incluirlos
  por sorpresa en esta integración. No se declara B2 global ni todo el sistema experto cerrado.
- Obtener validación experta del conocimiento provisional.
- La integración y la promoción **ya se ejecutaron** (ver §1, §4 y §6). Queda pendiente decidir qué pasa
  con la copia gemela y si se conserva como entorno de comparación, y homologar el procedimiento en las
  bases de los otros integrantes del grupo.

La representación de políticas es parcial. Las condiciones expresan campo, operador, valor o
referencia a criterio experto; se conserva OR dentro de cada grupo y AND entre grupos.
No se guarda código ejecutable en el grafo ni se agregan valores comerciales en Python.
Las exclusiones históricas se interpretan junto con las mejoras posteriores, no como un
listado nuevo de tareas que deba ejecutarse automáticamente.

## 6. Procedimiento ejecutado: copiar y actualizar, sin reemplazar a ciegas

Ejecutado el 13/11/2026 con `scripts/base_mejoras.sh`. Estado de cada paso:

1. **Respaldar con recuperación comprobable** — hecho: tar del volumen con el contenedor detenido,
   sha256 registrado, y la restauración en el volumen nuevo arrancó con la huella idéntica a la original.
2. **Copiar sin tocar la original** — hecho: contenedor y volumen nuevos; la original siguió con
   814 nodos, 1905 relaciones y 19 restricciones. No se copió el scratch ni su marcador de pruebas.
3. **Aplicar sólo las actualizaciones faltantes** — hecho: las ocho semillas aditivas en orden, sin PG2
   ni refresco de mercado. Delta: +117 nodos y +141 relaciones, conservando catálogo, costos, criterios
   y datos ajenos. La segunda aplicación no produjo cambios.
4. **Usar el código compatible con ese conocimiento** — habilitado: la app y los casos se pueden apuntar a
   `bolt://127.0.0.1:7688`. Falta decidir cuándo los consumidores pasan a la copia; no se hizo.
5. **Comprobación consolidada antes de cambiar la aplicación** — hecha sobre la copia: preflight verde y
   tanda completa de 61 casos con 55/55 y 0 infraestructura.
6. **Promover la original** — hecho el mismo día con `sh scripts/base_mejoras.sh promover`, que respalda
   antes de escribir y aborta si no puede. La original quedó equivalente a la copia, verificada por
   digesto de contenido, no sólo por conteos.

Sigue pendiente lo que este procedimiento no resuelve: la validación experta del conocimiento
provisional, los pendientes funcionales declarados (R1.4 `NoAmpliable`, R3.1b) y la decisión de
promover la copia a base de trabajo. Nada de eso se ejecutó acá, y el respaldo no es un permiso
para operaciones destructivas ni para publicar.

## 7. Consulta rápida y evidencia conservada

Este es el único documento generado de resumen de mejoras. Se retiraron los planes,
seguimientos `odd/tasks/` e informes Markdown redundantes; sus datos vigentes están aquí.
Los logs y JSON de `docs/ejecuciones/` se conservan, incluidos fallos históricos y guardas.
El [delta mínimo](ejecuciones/correcciones_minimas_delta.json) también es una fixture de
pruebas: no debe borrarse. La última tanda conserva su [log](ejecuciones/correcciones_minimas_61.log)
y sus [guardas](ejecuciones/correcciones_minimas_61_guardas.json).
El historial versionado permanece en Git y existe una copia comprimida local validada de
la documentación retirada; no se modifica ni limpia el contenido de los respaldos previos.

Ejecutor público, desde la raíz y con un entorno Python preparado:

```bash
python scripts/probar_publicaciones.py                 # listar, sin ejecutar casos
python scripts/probar_publicaciones.py --verificar     # configuración y catálogo; no llama al LLM
python scripts/probar_publicaciones.py --caso PC-26 --ejecutar
python scripts/probar_publicaciones.py --ejecutar
```

Para que la corrida use la copia y no la base original, apuntá el consumidor a
`NEO4J_LOCAL_URI=bolt://127.0.0.1:7688` (el contenedor de la copia). La integración del 13/11/2026
se ejecutó así, con `docker compose run --rm --no-deps` y la configuración privada inyectada por
Compose: no se exportaron valores a la sesión ni se guardaron en la evidencia. La evidencia de esa
tanda es [su log](ejecuciones/integracion_copia_mejoras_61.log) y
[sus guardas](ejecuciones/integracion_copia_mejoras_61_guardas.json).

Son referencias de uso, no ejecuciones nuevas ni autorización para repetir la tanda.
La lectura de configuración privada y la conexión a cada destino requieren sus permisos.
La prueba focalizada del grafo usa `EVALTIC_NEO4J_PRUEBAS_URI=bolt://127.0.0.1:17687`;
ese puerto y el marcador `EntornoPruebas {id:'mejoras-evaltic'}` identifican el scratch,
no la futura copia de trabajo. Las comprobaciones del grafo revierten sus transacciones.

Se preservan README, `LEVANTAR.md`, instrucciones del proyecto, documentación académica
original y `CONTEXTO_Y_MEJORAS_EVALTIC.md`, de autoría ajena a esta limpieza.
La depuración documental no resuelve PC26 ni los commits pendientes y no cambia reglas,
costos, criterios, motores o estado de despliegue.
