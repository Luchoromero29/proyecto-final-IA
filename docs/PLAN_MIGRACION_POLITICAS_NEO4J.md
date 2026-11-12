# Actualizar el grafo de EvalTIC para representar sus políticas

**Plan aprobado; implementación iniciada por P0.** Seguimiento: [migracion-politicas-neo4j.md](../odd/tasks/migracion-politicas-neo4j.md). Completar el modelo existente con las condiciones,
consecuencias y políticas que hoy están incrustadas en consultas del código. No reemplazar el
modelo, recalibrar el conocimiento ni cambiar las decisiones que ya produce correctamente.

Base de código examinada: `80654c9`, rama `mejoras/b2-diagnostico-neo4j`. El inventario procede de
archivos versionados, no de una inspección nueva de la base original. B2 se reabre por representación
del conocimiento; sus pruebas funcionales y commits anteriores se conservan como referencia.

## Ejecución vigente: un bloque, una comprobación final

El último pedido sustituye la secuencia de cierre y comprobación por cada regla/corte:

> Perfecto, quiero un enfoque simple. Quiero que hagamos todo un bloque primero, sin exdernos y solo al final 1 verificacion, no mas.
> Sin sobreingenieria ni sobredimensionar las cosas. Ajusta el plan, dejalo actualizado y continua con la migracion

- Primero implementar conjuntamente lo pendiente de SM1, SM3, SM2 y clasificación, reutilizando el modelo actual.
- Preparar las pruebas durante la implementación, **sin ejecutarlas ni lanzar verificadores intermedios**.
- Al terminar, **una única verificación funcional consolidada e independiente**, proporcional al cambio; no suite200, matrices ni una segunda corrida del escritor.
- Si esa ejecución falla, registrar y detener; no repetir automáticamente.
- La integridad transaccional al aplicar datos se conserva, sin convertirla en más rondas funcionales.
- No ampliar a B3–B5, modificar el fallback de caída de Neo4j, crear motores/infraestructura ni aplicar sobre la original de sólo lectura. Esas fronteras se declaran, no se resuelven por sorpresa.
- Los61casos originales permanecen pendientes; no son otra corrida automática ni una prueba ya acreditada.

Las tablas siguientes conservan el inventario técnico y sus criterios; no son gates de verificación intermedia. Rige S9 del seguimiento para el calendario actual.

## 1. Decisión y límites

El pedido es una **actualización incremental**, no otro sistema experto:

> Pero aplica buenas practicas, se quirurjico con las agregaciones, porque actualmente funciona, no quiero un model nuevo, quiero un modelo mejor que resuelva los problemas que tenga el actual mediante una actualización

- Reutilizar entidades, identificadores, relaciones y criterios actuales antes de agregar otros.
- Representar las políticas en el grafo; consultar ese conocimiento desde Cypher determinista.
- Mantener Python como transporte, validación de entrada, coordinación e interfaz. El LLM sólo
  enruta, extrae hechos y redacta; no genera consultas de negocio ni decide diagnósticos o compras.
- Conservar comportamiento, errores públicos, prioridades, trazas y precisión numérica. Una
  diferencia no prevista bloquea su unidad; no se corrige cambiando las expectativas del corpus.
- No crear un motor universal, una ontología paralela, dependencias nuevas, `eval`, un DSL abierto
  ni propiedades con fragmentos de Cypher/Python para ejecutar después.
- Versionar las actualizaciones de conocimiento en Cypher para reproducirlas. Eso no convierte al
  archivo en el decisor: el evaluador debe leer los datos cargados en Neo4j, no repetir sus reglas.

**No alcanza** mover cadenas de `.py` a `.cypher`, agregar nodos decorativos `Regla`, guardar sólo
su descripción o elegir un algoritmo particular con `if regla.id == 'R3.8'`.

## 2. Reutilización primero

| Elemento actual | Uso en la actualización | Qué no hacer |
| --- | --- | --- |
| `Regla`, `PERTENECE_A`, `USA_CRITERIO` | Conservar IDs; completar sus condiciones, efectos y dependencias. | Duplicar R3.4–R3.8 o reemplazar sus identificadores. |
| `CriterioExperto`, `CostoReparacion` | Referenciar los valores existentes; registrar los realmente utilizados. | Copiar umbrales/costos a expresiones o crear criterios distintos con el mismo significado. |
| `ReglaDifusa`, `VariableDifusa`, `ConjuntoDifuso`, `ANTECEDENTE`, `CONSECUENTE` | Mantener las cinco bases difusas y sus parámetros. Reutilizar su convención de grupos cuando corresponda. | Convertir condiciones booleanas en conjuntos gaussianos o reconstruir Mamdani. |
| `PatronTexto`, `FallaSintoma`, `Diagnostico`, `Intervencion` | Conservar patrones, diagnósticos y asociaciones ya incorporados por B2. | Inventar nuevas causas, diagnósticos o protocolos técnicos. |
| `ORDENA`, `OBLIGA`, `SE_REPARA_CON` | Reutilizar las consecuencias técnicas y los costos enlazados. | Crear otra tabla de reparaciones que compita con la existente. |
| `ConjuntoDifuso` de salida de `SM3-CONV` | Añadir el resultado comercial asociado y si corresponde informar contraoferta. | Crear otra ontología de decisiones si bastan propiedades de los tres conjuntos actuales. |
| `VersionParametros` y metadatos existentes | Revisar consumidores antes de ampliar su cobertura; registrar la versión de representación. | Mezclar sin revisión versiones FIS con versiones de representación crisp o sobrescribir validaciones expertas. |

El PG2 ya representa reglas crisp con texto y `USA_CRITERIO`, y reglas difusas con antecedentes
estructurados. Su convención es **OR dentro del mismo grupo y AND entre grupos**. Son semánticas
que deben conservarse, no una razón para usar nodos difusos donde sólo hace falta una comparación.

### Agregados mínimos permitidos por el diseño

1. Completar propiedades/relaciones de las reglas actuales cuando puedan expresar la política sin ambigüedad.
2. Para condiciones compuestas que `campo`/`valor` no puedan representar, evaluar una estructura
   auxiliar de condiciones vinculada a la misma `Regla`. Su necesidad y forma se cierran en P0;
   no se agrega una etiqueta por síntoma, comparación o submódulo.
3. Para fórmulas, representar operandos, operación y secuencia como datos estructurados finitos,
   reutilizando la representación anterior donde sea correcto. Si hacen falta pasos auxiliares,
   justificar su uso con las fórmulas existentes antes de incorporarlos. No guardar texto ejecutable
   ni listas de mapas como propiedades de Neo4j.

P0 debe entregar **un único esquema mínimo**, con el antes/después de propiedades y relaciones,
cardinalidades y ejemplos de cada forma necesaria. No promete cero agregados, pero rechaza agregados
sin una política concreta que los necesite. No introduce un modelo de dominio alternativo.

## 3. Inventario que debe quedar cubierto

Inventario inicial agrupado: cada fila debe terminar con representación de datos, consumidor,
prueba y versión identificados. P0 debe desglosarlo y revisar también los retornos tempranos del
pipeline —incluidos R3.2, R3.3b y R3.3c—, valores por defecto y correspondencias entre estado y
decisión. No alcanza migrar SM3 ni dar esta tabla por exhaustiva sin esa comprobación.

| ID | Política a representar | Estado y reutilización | Fuente actual |
| --- | --- | --- | --- |
| I1 | Batería, temperatura, RAM, disco, pantalla, teclado y cargador | Ya existen acciones y costos enlazados; faltan comparadores y condiciones compuestas de varias ramas. | [SM1](../app/inferencia_sm1.py), `CONSULTA_RESOLUCION`, sección A; [seed diagnóstico](../cypher/Grupo_20_PG3_diagnostico.cypher). |
| I2 | Prioridad entre evidencia irreversible, síntoma, descripción positiva e intervención | Patrones y tratamientos ya son datos; su precedencia todavía depende de cadenas `CASE`. | SM1, sección B. |
| I3 | Verificación del operador, reparabilidad, estado técnico final y su propagación a decisión integral | Diagnósticos y costos ya existen; faltan la selección ordenada de estados y sus condiciones. La validación del canal del operador permanece como validación de entrada. | SM1, secciones C y estado final; [orquestador](../app/orquestador_evaltic.py), `ejecutar_motor_sm1`. |
| I4 | Plan único, orden, mano de obra e intervención contable | Reutilizar `orden`, `requiere_plan`, `cuenta_como_intervencion` y consecuencias actuales. Explicitar selección y combinación; no confundir duplicados legítimos de tarea con datos corruptos. | SM1, armado del plan y retorno. |
| I5 | R3.7/R3.8 y su precedencia | `Regla` y criterios existen, pero condiciones y consecuencia están codificadas en Cypher. | [SM3](../app/inferencia_sm3.py), `CONSULTA_CRISP`; [PG2](../cypher/Grupo_20_PG2_U1_carga.cypher), sección 6. |
| I6 | Margen base → R3.4 o R3.5 → R3.6 | Representar condiciones, exclusión, orden y operaciones asignar/máximo/sumar, referenciando los CE actuales. | SM3, `CONSULTA_CRISP`. |
| I7 | Fórmulas financieras y cuantización aplicada | Margen, ratio, contraoferta, límite no negativo, brecha y descuento: operandos, orden y precisiones son parte del contrato. Incluir el orden RIE: categoría sobre centroide crudo → cuatro decimales → cuantización a dos, y la cuantización de VMA a miles. El algoritmo numérico genérico se reutiliza. | SM3, consultas y `_cuantizar`; orquestador, `inferir_sm2_rie_cypher` y valuación. |
| I8 | Categoría difusa → decisión y habilitación de contraoferta | Extender `Conveniencia.Comprar`, `Conveniencia.Negociar`, `Conveniencia.Descartar`; evitar el `CASE` por categoría. | SM3, `CONSULTA_DECISION`; PG2, sección 7. |
| I9 | Valuación por componentes y factores aplicables | Procesadores, líneas, RAM y factores ya existen; representar fórmula y condiciones de upgrades/descuento. | Orquestador, `_CONSULTA_VALUACION_SM2`; [PG3 mercado](../cypher/Grupo_20_PG3_mercado.cypher). |
| I10 | Prioridad de año/W11/RAM, R2.4 y desempates | Conservar el orden actual de fuentes, generación anterior, muestras y desempates; no recalibrar el catálogo. | Misma consulta y `inferir_valuacion_sm2_cypher`. |
| I11 | Estados y motivos de SM2; procedencia por rama | Representar clasificación y motivo. `USA_CRITERIO` declara dependencias, pero no significa que todos los CE se usaron en toda evaluación. | Misma consulta, `_criterios_valuacion_sm2`, `_pendiente_valuacion_sm2`. |
| I12 | Firme/Provisional | Es política de dominio: debe leer inferencias, pendientes y validación efectivamente utilizada, no quedar como excepción permanente en Python. | Orquestador, `_estado_decision`. |
| I13 | Señales de bloqueo R3.3 y su fuente de conocimiento | El respaldo Python y los nodos `Bloqueo` actuales no son un catálogo único de señales. Preferir los `PatronTexto` existentes enlazados a R3.3, con ámbito explícito; no convertir instancias de bloqueo por equipo en un catálogo paralelo. | Orquestador, consulta de señales y `evaluar_publicacion_integral`; PG2, nodos `Bloqueo`. |
| I14 | Reglas difusas ya estructuradas y su consumo | Conservar antecedentes/consecuentes y comprobar que configuración y mecanismo ejecutado coinciden. No duplicar conocimiento ya representado. | PG2, sección 7; orquestador, `inferir_sm*_cypher`. |

**Frontera con los bloques originales:** I13 migra la representación de las señales actuales,
no corrige todavía las negaciones/falsos positivos de B3. La política actual de R2.4 sí se cubre
en I10; recalibrarla o ampliar su cobertura comercial sigue separado en B5. El enrutamiento y la
completitud de B4 quedan identificados en el plan original, no se agregan encubiertamente aquí.
El sistema completo no puede declararse cerrado mientras esos pendientes sigan abiertos.

## 4. Conocimiento frente a mecanismo

| Debe ser conocimiento leído del grafo | Puede permanecer como mecanismo de ejecución |
| --- | --- |
| Campo, comparador, valor o referencia a CE; agrupación AND/OR y tratamiento del dato desconocido. | Implementación determinista de comparadores admitidos y evaluación de grupos. |
| Condiciones y consecuencias de R3.x/SM1; prioridades y forma de combinar efectos. | Lectura ordenada, aplicación de la operación indicada y construcción del resultado. |
| Fórmula de valuación, operandos, selección de factores y pasos de margen/contraoferta. | Suma, resta, multiplicación, división y máximo como operaciones finitas; sin interpretar código arbitrario. |
| Qué resultado se cuantiza, precisión y posición del redondeo. | Algoritmo IEEE-754 ya probado. No recalibrarlo ni sustituirlo por `round()` con semántica diferente. |
| Validación experta y clasificación final Firme/Provisional. | Transporte de esa clasificación y traducción al formato público. |
| Señales, patrones y tratamientos de negocio. | Normalización de texto, comprobación de tipos, conexión, mensajes técnicos e interfaz. |

Un `CASE operador WHEN ...` que implementa comparaciones es mecanismo; un `CASE` que conoce
que riesgo Alto + demanda Baja descarta es una política incrustada. La diferencia se verifica
con pruebas de cambios de datos, no contando cuántos `if` quedan en el archivo. `Regla.texto`
puede conservarse para lectura humana, pero no se interpreta como código ni sustituye la condición
estructurada. Su explicación debe mantenerse consistente con los datos realmente evaluados.

## 5. Secuencia de implementación propuesta

El bloque reúne datos, consumidores, pruebas preparadas y documentación mínima. Se implementa
completo antes de una única comprobación final; no se verifica cada fila ni cada regla al avanzar.
Las filas P0–P6 identifican áreas y criterios, no rondas adicionales de verificación.

| Paso | Área de implementación | Criterio para la comprobación final |
| --- | --- | --- |
| P0 — contrato e inventario final | Confirmar el esquema del entorno aislado por vía permitida; matriz I1–I14 con IDs, campos, comparadores, orden, consecuencias, fórmulas, procedencia y errores. Resolver representación mínima y alcance de cada archivo. Contrastar el original antes de P6, sin bloquear la planificación por su acceso pendiente. | Modelo incremental documentado; ninguna condición sin destino ni agregado sin justificación. Captura de referencia pública con configuración fijada. |
| P1 — correspondencia comercial | Agregar a los tres conjuntos `Conveniencia.*` el resultado y la habilitación de contraoferta; adaptar sólo su lectura. | Cambiar esa correspondencia en el grafo aislado cambia la salida pública sin editar Python; paridad con los valores originales. |
| P2 — condiciones técnicas | Migrar I1–I4 por grupos coherentes: acciones, precedencias/estados y combinación del plan. Reutilizar diagnósticos, patrones, costos y metadatos. | Mismos planes, costos, pendientes e inviabilidad; preservación de datos faltantes y verificación separada del operador. |
| P3 — política financiera | Migrar I5–I7: descarte, margen por etapas y fórmulas/precisiones. Reutilizar el cuantizador y el mapeo de P1. | R3.7 precede R3.8; R3.4/R3.5 y después R3.6 conservan aplicación y traza; paridad numérica observada. |
| P4 — valuación | Migrar I9–I11 y cuantización SM2 de I7: fórmula, fuentes, condiciones, R2.4, desempates, clasificación y procedencia. | Firma y nueve campos del wrapper compatibles; inválidos, ausentes, estados mixtos, VMA a miles y RIE→DEM conservan contrato. |
| P5 — clasificación final y cobertura | Migrar I12/I13 y verificar I14. Auditar que no quede una copia decisoria de esas políticas en Python ni en ramas específicas de Cypher. | Todas las filas tienen prueba de representación y paridad, o un bloqueo explícito; no declarar S9 cumplido si se excluyó alguna. |
| P6 — aplicación controlada | Inventario y respaldo vigente de la base original, actualización aditiva y despliegue compatible; recién después, corrida homogénea de 61 casos. | Vía de conexión y ejecución autorizadas, respaldo validado, recuperación comprobable y comparación registrada. |

Los pasos P2–P4 se subdividen en unidades de unas 400 líneas autorales cuando sea posible. No
se comprimen consultas ni se eliminan pruebas para aparentar cortes chicos. Si una unidad exige
ampliar el modelo o abarcar otra área, se revisa su límite antes de crecer. Se mantiene la cadena
local de entregas; push/PR y operaciones destructivas no quedan autorizados por este documento.

### Dos decisiones que no se deben ocultar

- **Lógica del legado:** se copia la semántica actual de comparadores, prioridades y desempates,
  con su carácter Provisional. No se presenta el comportamiento observado como validación del experto.
- **Fallback ante fallo de Neo4j:** eliminar la lista estática de bloqueo puede cambiar el resultado
  de errores de conexión que hoy se ocultan. Debe reproducirse y fijarse ese contrato en P0/P5:
  no prometer paridad donde no la hay ni agregar una caché o fallback de negocio en Python para
  esconderla. Si hace falta un cambio observable, se separa y acuerda antes de activarlo; los demás
  cortes no dependen de resolverlo para documentarse o probarse aislados.

## 6. Actualización aditiva, activación y recuperación

- Crear un artefacto versionado separado, por ejemplo `cypher/Grupo_20_PG3_politicas.cypher`
  **al implementar**. No editar ni ejecutar el bloque destructivo PG2 ni el refresco de mercado
  como atajo para esta migración. No se creó ese script durante la planificación.
- Identificar objetos por claves estables y reutilizar restricciones existentes. Validar que los
  IDs encontrados correspondan al objeto esperado. `MERGE` por sí solo no demuestra idempotencia
  ni impide sobrescribir propiedades: cualquier diferencia previa exige una decisión explícita.
- Declarar por corte la lista permitida de altas y cambios de propiedades/relaciones. No renombrar
  ni eliminar actores, CE, costos, conjuntos o reglas anteriores. No modificar sus valores/calibración.
- Separar metadatos de representación de la versión/validación del conocimiento experto. `estado`
  legado y `estado_validacion` no son intercambiables. Conservar los valores y fuentes anteriores.
  Añadir metadatos técnicos no debe convertir por sí solo una salida Firme en Provisional ni registrar
  criterios que la evaluación no utilizó.
- Comprobar referencias, cardinalidades, operadores y completitud antes de activar. Declarar el
  conjunto vigente por etapa: no evaluar indiscriminadamente todo nodo `Regla`, ni reactivar reglas
  no implementadas o reemplazadas como R3.9–R3.11 (`REEMPLAZA_A`). Las reglas obligatorias faltantes
  deben detectarse, no omitirse silenciosamente. Aplicar cada unidad en una transacción controlada
  con precondiciones, sin cargas parcialmente activadas.
- La versión anterior de la aplicación debe tolerar los datos adicionales; la nueva debe detectar
  conocimiento incompleto, no caer en una política equivalente escrita en código. La secuencia de
  despliegue es datos completos → validación → consumidor; el modo de activación se fija en P0.
- Comparar la proyección de propiedades/relaciones protegidas y el delta autorizado, no exigir
  que el digest de todo el grafo sea idéntico después de añadir conocimiento legítimo.
- Ejecutar dos veces la actualización en el entorno aislado: la segunda no debe añadir duplicados
  ni cambiar valores, estados o resultados. Después probar compatibilidad con consumidores PG2/PG3.
- Antes de P6, obtener inventario y respaldo **vigentes**, verificar su restauración en destino
  aislado y documentar recuperación. El respaldo histórico no autoriza reemplazar datos más recientes.
- Para recuperar, preferir retirar el consumidor nuevo dejando datos aditivos compatibles inactivos,
  si esa compatibilidad fue comprobada. Remover propiedades/nodos requiere propiedad de los cambios,
  inventario y autorización específica; nunca reset, limpieza masiva ni dump viejo sobre trabajo actual.

## 7. Pruebas que acreditan la migración

**Prueba distintiva:** modificar una condición o consecuencia representada en el grafo cambia el
resultado público sin modificar archivos `.py`. Cambiar sólo un CE no alcanza: eso ya era posible.

| Comprobación | Qué debe demostrar |
| --- | --- |
| Comparador, grupo o prioridad | La misma entrada activa otra regla al cambiar sólo esos datos; comparar decisión, plan, costo y regla aplicada según corresponda. |
| Consecuencia comercial | Cambiar el resultado asociado a `Conveniencia.*` cambia la decisión y la habilitación de contraoferta, sin otra tabla en código. |
| Fórmula o combinación | Cambiar un operando/paso de una fórmula soportada cambia VMA/margen/contraoferta mediante datos, sin expresiones ejecutables. |
| Sin cambios de conocimiento | Mismos hechos → mismas salidas públicas, errores, stdout/stderr y exit codes; incluir integral, SM1, SM2, CLI y consumidores compartidos que se toquen. |
| Conocimiento inválido | Operador no admitido, referencia faltante, categoría sin correspondencia, grupos ambiguos o pasos inconsistentes producen error explícito, nunca compra favorable ni omisión silenciosa. |
| Duplicados y combinación | Detectar IDs/relaciones estructuralmente duplicados o efectos contradictorios; conservar que varias reglas legítimas puedan ordenar una misma tarea una sola vez. |
| Procedencia | Registrar sólo criterios y costos usados; mantener Firme/Provisional y metadatos. Una regla declarada pero no aplicada no debe contaminar la salida. |
| Idempotencia y protección | Sin delta adicional en la segunda carga; propiedades protegidas, registros ajenos y consumidores previos conservados. |

Las mutaciones de representación usan un grafo dedicado con marcador y hechos controlados;
restauran su propio fixture o transacción, sin modificar datos originales. Los cambios de configuración
inválida tienen contrato de error explícito; no se confunden con datos faltantes del aviso.

Al implementar: RED de cada regla/garantía antes de su cambio, GREEN enfocado y regresiones de
interfaces compartidas. El diferencial antiguo/nuevo se ejecuta como comprobación acotada; los
tests versionados no dependen de leer commits de Git. Conservar stdout, stderr, códigos y fallos
previos, sin ajustes de expectativas para disimular diferencias.

La referencia histórica es **184 pruebas con grafo sin omisiones** y offline `Ran 90 / OK
(skipped=15)`, más verificaciones I/J/L. No se ejecutaron de nuevo para escribir este plan. Esas
pruebas acreditan comportamiento, no por sí solas representación del conocimiento. Hay que añadir
las pruebas anteriores y verificar independientemente los cambios de contratos/lógica compartida.

Los 61 casos con LLM real son una capa posterior a la actualización controlada de P6, con modelo y conocimiento fijados. Ni esos
casos ni la inferencia controlada autorizan afirmar que Matías validó políticas todavía Provisionales.

## 8. Condición de cierre y situación actual

- [ ] I1–I14 tienen representación y consumo reales, sin duplicación decisoria en código.
- [ ] El modelo existente se conserva y cada agregado tiene necesidad demostrada.
- [ ] Las pruebas de cambio de datos, paridad, procedencia e idempotencia pasan por unidad.
- [ ] Los desvíos observables están separados y resueltos, no escondidos como refactorización.
- [ ] La verificación independiente aplicable se completó; ninguna revisión nativa se supone aprobada.
- [ ] Para cerrar también la aplicación original: inventario/respaldo/actualización permitidos y 61 casos reales registrados.

**Ahora:** sólo se preparó este plan y se reconciliaron los documentos de alcance. No se modificaron
la aplicación, los seeds, el corpus, las dependencias ni una base de datos. T2 sigue pendiente de
implementación; T2P espera una vía segura autorizada que no lea `.env` directa o indirectamente.
B3–B5 mantienen sus objetivos propios; no se convierten en cambios de negocio implícitos de esta migración.

## Referencias

- [Seguimiento y requisitos literales](../odd/tasks/mejoras-evaltic.md), S9/S10 y L33–L34.
- [Plan original B0–B5](PLAN_MEJORAS_EVALTIC.md).
- [Diagnóstico técnico](DIAGNOSTICO_TECNICO.md), [valuación](VALUACION_NEO4J.md) y [decisión](DECISION_NEO4J.md).
- [Evidencia funcional B2 y alcance rectificado](ejecuciones/mejoras_b2_cierre.md).
- Inventario de sólo lectura: `gentle-ai-explore`, tarea `mwbmxz81-m-bge9`; contraste puntual del
  PG2 sobre reglas, criterios, grupos y consecuentes existentes. No constituye inventario del grafo instalado.
