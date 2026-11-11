# Plan de correcciones de extracción e inferencia de EvalTIC

**Estado: aplicación autorizada y en curso.** El seguimiento y las decisiones actuales están en
[odd/tasks/mejoras-evaltic.md](../odd/tasks/mejoras-evaltic.md). El objetivo es corregir las causas de las decisiones
incorrectas sin cambiar de modelo, debilitar las pruebas ni reemplazar el patrón neuro-simbólico.
Preparado sobre `integracion/mejoras-con-pruebas`, referencia `67de236`.

**B2: código implementado y verificado técnicamente en Neo4j aislado.** La verificación
independiente final RIE→DEM dio PASS, con 184 pruebas aprobadas sin omisiones. La aplicación
aditiva sobre la base original y la nueva tanda NVIDIA de 61 siguen pendientes (T2P); no se
presenta como un cierre end-to-end. B3–B5 permanecen pendientes. Ver
[evidencia y límites de B2](ejecuciones/mejoras_b2_cierre.md).

## Punto de partida

- [Última tanda real](ejecuciones/publicaciones_criticas_integracion_resumen.md): 61 completados,
  49 cumplen, 6 no cumplen, 6 sondas y 0 errores de infraestructura reportados.
- Incumplimientos: PC-01, PC-15, PC-17, PC-19, PC-29 y PC-50. Hallazgo adicional relevante: PC-47.
- Suite offline: 71/71 aprobada. Usa fixtures y caracterizaciones; no demuestra que el motor
  resuelva correctamente los defectos observados en vivo.
- Neo4j actualizado: 333 avisos, 93 procesadores, 46 líneas y 11 capacidades RAM.
- [Respaldo y actualización verificados](ejecuciones/integracion_neo4j_actualizacion.md).

Pedido que origina este plan:

> Perfecto, deja el plan armado para poder solucionar estos problemas. Entiendo que es mas que nada aplicar guardarails al LLM para que la extracción sea lo mas limpia posible, y quizas modificar algo del grafo con las nuevas reglas de sintoma relevante y luego daño irreparable si se confirma

## Enfoque: dos garantías, no solo un prompt mejor

1. **Integridad de los hechos:** lo que llega al motor debe estar respaldado por el aviso.
2. **Corrección de la inferencia:** incluso con extracción correcta, el motor no puede tratar
   un síntoma relevante sin resolver como un estado favorable.

Un guardrail de extracción no resuelve por sí solo una falla que SM1 recibió pero ignoró.
Tampoco alcanza trasladar una búsqueda incorrecta de subcadenas desde Python a Neo4j.

```text
Aviso → extracción LLM → validación/normalización → inferencia Neo4j → explicación LLM
```

| Capa | Responsabilidad |
|---|---|
| LLM de entrada | Extraer hechos, conservar evidencia y reconocer lo no informado; no diagnosticar causas ni inventar valores. |
| Python | Validar tipos, formatos y correspondencia con el texto; coordinar el flujo y transmitir incertidumbre. |
| Neo4j | Alojar conocimiento experto, relaciones síntoma/diagnóstico/intervención, costos, umbrales y reglas aplicadas por consultas explícitas. |
| LLM de salida | Explicar el resultado simbólico sin cambiar decisión, plan o costos. |

No agregar una ontología paralela ni un motor genérico de reglas. Reutilizar entidades y estados
existentes siempre que alcancen. Ningún precio, costo o umbral de negocio nuevo va en Python.

## Bloques de trabajo y criterios de cierre

Los bloques siguientes conservan el contrato del plan adoptado. Su estado de ejecución se
registra en el documento de seguimiento. Resolver por causa de raíz, no por publicación.

### B0. Aislar los errores y mejorar la evidencia de las pruebas

**Antes de modificar políticas.** Reutilizar la traza existente para distinguir:
texto original, extracción recibida, datos normalizados, entradas a la inferencia, reglas
activadas y costos consultados. No guardar claves, razonamientos internos del modelo ni cuerpos
de error del proveedor. Limitar la captura a lo necesario para reproducir los casos.

- Reproducir PC-15, PC-19 y PC-29 e identificar la primera etapa que produce el dato incorrecto.
- Mantener el manejo del fallo del proveedor separado del resultado fuera de dominio del router.
- No atribuir causas a Mamdani, al prompt o al catálogo basándose solo en la decisión final.
- Cierre: cada corrección siguiente tiene un ejemplo reproducible y una capa responsable
  identificada; las incertidumbres restantes se consignan, no se rellenan con supuestos.

### B1. Garantizar la integridad de la extracción — prioridad alta

**Caso principal: PC-29.** El precio `$1` debe conservarse como `1`, no como `115000`.

- Exigir correspondencia del precio normalizado con un fragmento real del aviso.
- Cubrir los formatos ya admitidos: monto corto, cero, miles, rango y precio escrito en pesos.
- No reemplazar un precio con una valuación estimada, costo de reparación o valor por defecto.
- Validar los campos antes de calcular indicadores financieros; ante falta/contradicción no
  inferir un hecho favorable. Conservar los rechazos y solicitudes de datos pertinentes.
- Reforzar el prompt con el contrato anterior, pero hacer cumplir la garantía mediante
  validación determinista: el prompt solo no es la barrera final.
- Cierre: PC-29 respeta el precio literal y los formatos vecinos mantienen su comportamiento.

**Límite:** corregir la extracción no introduce una política nueva de precio mínimo o señuelo.
Si se desea evaluar si `$1` es comercialmente creíble, esa política se acuerda con el experto
por separado y se representa en el grafo; no se improvisa un umbral para aprobar el test.

### B2. Tratar síntomas relevantes y diagnósticos confirmados — prioridad alta

**Casos principales: PC-19 y PC-47.** Política Provisional adoptada por el usuario para
`no prende`, `no carga` y `se apaga sola`, sin atribuir validación a Matías. El LLM extrae hechos;
la inferencia de Neo4j determina el tratamiento. No es una lista exhaustiva de síntomas:

| Situación | Tratamiento propuesto |
|---|---|
| Síntoma afirmado y reconocido, con intervención definida | Aplicar su regla y costo del grafo. |
| Síntoma relevante con causa/intervención todavía sin resolver | Solicitar verificación técnica; no recomendar Comprar suponiendo reparación cero. |
| Daño irreparable confirmado según el criterio experto | Aplicar las reglas de inviabilidad existentes R1.1/R3.2. |
| Síntoma negado o descripción positiva | No generar una falla/reparación por la sola palabra. |
| Conocimiento necesario inexistente en el catálogo | Error explícito de conocimiento faltante; no inventar una solución. |

- `No prende`, `no carga` y `se apaga sola` describen síntomas; no prueban por sí solos una placa
  irreparable ni justifican asumir que el equipo está sano.
- Reutilizar `Falla`, `Bloqueo`, `Intervencion`, `Regla`, `CriterioExperto` y `CostoReparacion`;
  agregar solamente el conocimiento que falte y conectar sus consultas con el pipeline real.
- Llevar al grafo las asociaciones expertas y palabras/patrones que hoy deciden negocio en
  Python. No trasladar sin revisión asociaciones incorrectas de síntoma a daño irreversible.
- Propagar la incertidumbre de SM1 hasta SM3 y la salida final. Revisar evaluación integral y
  diagnóstico SM1 suelto. No confundir un valor desconocido con `False` mediante `if not ...`
  y descartarlo accidentalmente como inviabilidad, ni convertirlo en viabilidad favorable.
- Usar las decisiones y mecanismos de pendientes existentes antes de introducir estados nuevos.
- Cierre: un síntoma relevante reconocido no queda sin tratamiento; PC-19/PC-47 no obtienen una
  compra favorable por omisión. Casos reparables, sanos y catastróficos conservan su tratamiento.

**Validación experta pendiente:** ampliar y validar el catálogo de síntomas, los protocolos de
verificación y la evidencia de irreparabilidad. La política conservadora para los tres síntomas
acordados está autorizada como Provisional; no se agregan otros diagnósticos por analogía. Un texto ambiguo no equivale a diagnóstico confirmado.
Precisar cómo se consideran declaraciones del aviso frente a inspección técnica, sin cambiar
silenciosamente los casos catastróficos existentes. Reglas nuevas versionadas y Provisionales
hasta la validación; sus condiciones cuantitativas, si existen, referencian criterios del grafo.

### B3. Interpretar bloqueo y negación por contexto

**Casos principales: PC-17 y PC-50.** Una sola corrección semántica para ambos falsos positivos.

- Distinguir `cuenta con batería` de una cuenta que bloquea el equipo.
- Separar señal afirmada, negada, desconocida y contradictoria, con evidencia del aviso.
- `No está bloqueada` no es evidencia de bloqueo activo; tampoco certifica por sí sola que un
  técnico haya verificado el equipo. Conservar la procedencia de la declaración.
- No usar una regla genérica `aparece no → negar falla`: `no prende` afirma un síntoma.
- Reutilizar los estados existentes del bloqueo; no sumar excepciones por modelo o por caso PC.
- Cierre: PC-17/PC-50 dejan de disparar por subcadena, sin perder las detecciones válidas de
  clave BIOS, cuenta de un dueño anterior y frases contradictorias que requieren verificación.

### B4. Corregir el enrutamiento de entradas insuficientes

**Caso principal: PC-01.** `computadora asus, anda joya` no debe tratarse automáticamente como
consulta ajena al dominio; puede requerir aclarar si es notebook, modelo y precio.

- Separar intención de completitud del aviso: reconocer el dominio no autoriza inventar datos.
- Conservar el enrutamiento integral cuando existe precio y las consultas SM1/SM2 sueltas.
- Revisar el respaldo del router para no convertir errores del proveedor en clasificación
  semántica aparente. No cambiar mensajes/contratos sin documentarlos y probar sus consumidores.
- Cierre: PC-01 y las entradas incompletas relevantes reciben rechazo/aclaración coherente;
  los casos realmente fuera de dominio y PC-25/PC-56/PC-57 siguen funcionando.

### B5. Resolver la reparación térmica inesperada y cerrar cobertura

**Caso principal: PC-15.** Depende de B0 para conocer la causa.

- Si el hecho cambió en extracción/normalización, corregir esa capa, no compensarlo en la difusa.
- Si con hechos correctos la inferencia recomienda un servicio incorrecto, revisar activaciones,
  conjuntos, reglas y criterios de SM1-TER con el experto. No asumir que 68 °C determina por sí
  solo una categoría sin contexto ni introducir umbrales en Python.
- Cierre: PC-15 cumple su contrato y se conservan los casos donde el servicio sí corresponde.
- Incorporar una prueba explícita del fallback R2.4, que la tanda anterior no acredita, sin
  aprovechar este bloque para cambiar su política de valuación.
- Revisar las sondas con el experto antes de convertirlas en aceptación. Para PC-60, usar un caso
  cuyo resultado esperado contradiga la instrucción inyectada; coincidir en Comprar no prueba
  resistencia. PC-59 no basta como garantía general frente a inyecciones.

## Pruebas y modo de trabajo

Aplicar ODD por bloque: explorar lo necesario, resolver incertidumbre real, registrar alcance,
observar RED, implementar lo mínimo, observar GREEN y guardar una unidad revisable con sus
pruebas y documentación. No agregar un framework de guardrails ni dependencias sin necesidad.

1. **Offline determinista:** tipos, formatos, evidencia, enrutamiento y propagación de datos.
2. **Neo4j real aislado + extracción controlada:** comprobar la inferencia sin depender del LLM.
3. **End-to-end NVIDIA:** comprobar que el aviso completo produce el resultado acordado.

Cada prueba nueva exige el comportamiento correcto, no enseña al fixture a ocultar el defecto.
Usar las funciones públicas del asistente y cubrir los comportamientos existentes que comparten
los helpers modificados. Los tests de errores deben comprobar ausencia de una recomendación o
reparación favorable inventada; las pruebas aisladas no deben alterar datos del grafo de trabajo.

Por iteración, ejecutar casos enfocados y regresiones vecinas. Al cerrar un bloque relevante,
ejecutar la suite offline y el corpus de 61 con la misma configuración de modelo y versión de
conocimiento fijadas. No confundir una expectativa ajustada por decisión experta con una mejora
del motor; registrar ambas cosas por separado.

- Mantener corpus y logs históricos. Los nuevos casos se agregan con su expectativa justificada.
- Reutilizar el entorno validado; no reconstruirlo ni recargar el grafo de trabajo por cada test.
- Las pruebas de Cypher que mutan datos usan un grafo dedicado y reconstruible.
- Versionar cambios del conocimiento en Cypher, con fuente, estado y regla/criterio utilizado.
- Priorizar migraciones acotadas. Toda carga destructiva sobre datos de trabajo requiere
  autorización específica y respaldo verificado; no ejecutar `RECARGAR=1` para cargar solo PG3.
- Preservar adaptación NVIDIA, configuración privada y archivos ajenos. No cambiar de modelo
  ni usar proveedores pagos para esconder incumplimientos.
- Mantener commits locales por unidad con pruebas/docs; push y PR son decisiones separadas.
- Tras aprobar la ejecución de un bloque, continuar sin confirmaciones rutinarias. Consultar
  únicamente criterios expertos/producto no resueltos, permisos requeridos o riesgos nuevos.

## Orden recomendado y primer paso

**B0 → B1 → B2 → B3 → B4 → B5.** B0 acompaña cada investigación, no es un proyecto de logging.
El primer bloque B0/B1 aisló PC-29 y garantizó integridad del precio. B2 ya tiene aprobación
Provisional para los tres síntomas acordados; toda decisión de negocio debe inferirse en Neo4j.

El plan original no modificó código, corpus ni grafo. Después se autorizó su aplicación:
B0 aisló las causas y B1 corrigió la integridad del precio. B2 tiene política Provisional aprobada;
los resultados y comprobaciones vigentes están en el seguimiento, no se presume cierre total.
