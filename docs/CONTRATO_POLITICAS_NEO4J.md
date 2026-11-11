# Contrato de representación incremental de políticas — P0

Actualizar el modelo existente, no sustituirlo. Contrato derivado del [plan aprobado](PLAN_MIGRACION_POLITICAS_NEO4J.md); ejecución y evidencia en [seguimiento](../odd/tasks/migracion-politicas-neo4j.md).
Base funcional: `80654c9`. Entorno examinado: scratch marcado `mejoras-evaltic`, no base original. Conocimiento observado, no validación del experto.

## Qué se conserva y qué se agrega

El inventario actual tiene 866 nodos, 1964 relaciones y 19 restricciones. `Regla`, `USA_CRITERIO`, `ORDENA`, `OBLIGA`, `ACTIVA`, diagnósticos, costos y los cinco sistemas difusos se conservan. Los `Frame`/`Slot` existentes describen propiedades mediante facetas/demonios textuales; no son condiciones ejecutables de una regla. `Operacion` y `Decision` contienen casos/resultados, no catálogos de operadores ni una definición alternativa de inferencia.

No interpretar sus textos como programas ni convertir sus instancias en otra ontología. El destino de cada política queda fijado abajo; cada corte completa sus registros concretos con los valores del comportamiento vigente, antes de activar su consumidor. No se cargan anticipadamente todas las estructuras.

| Superficie | Forma mínima y cardinalidad | Necesidad comprobada |
| --- | --- | --- |
| Regla simple existente | `campo`, nuevo `operador`, literal en `valor` **o** una referencia `USA_CRITERIO` identificada para la comparación; nunca ambos operandos. | RAM, disco y batería. `valor` hoy es booleano: números/cadenas requieren validación explícita, sin coerciones nuevas. |
| Condición compuesta | Única etiqueta auxiliar `Condicion`, identificador estable, `campo`, `operador`, literal tipado o relación `USA_CRITERIO`; `Regla-[:REQUIERE {grupo}]->Condicion`, 0..n. | R3.8 exige dos hechos; batería combina comparación con ausencia de ciclos. OR dentro del grupo y AND entre grupos. Sin árbol/DSL abierto. Una regla no mezcla forma simple y compuesta. |
| Consecuencia | Conservar `ORDENA`/`OBLIGA`; para efectos escalares agregar destino, operación y literal **o** CE referenciado con rol. Operaciones de combinación: asignar, máximo, sumar. | Margen base → R3.4 o R3.5 → R3.6. No copiar valores CE a otra propiedad. |
| Secuencia y exclusión | `etapa`, `prioridad_inferencia`, grupo de exclusión en las mismas reglas. Un empate ambiguo es configuración inválida. | R3.7 antes de R3.8; exclusión R3.4/R3.5; prima posterior. No reutilizar `orden` del plan técnico como prioridad inferencial. |
| Cálculo | `Regla` representa la fórmula derivada; única etiqueta auxiliar `PasoCalculo`, enlazada por `PASO {orden}`. Dos operandos como máximo, cada uno tipado: hecho, CE enlazado, resultado previo o literal. Un resultado por paso; referencias previas y orden único, sin ciclos. | Margen, ratio, contraoferta, descuento, brecha, valuación y antigüedad ya calculados actualmente. No hacen falta etiquetas `Formula` y `Termino` además de `Regla`. |
| Selección técnica de versión | Cuando una etapa requiera un conjunto de reglas, `VersionPoliticas {id, version, etapa, activa, ids_requeridos}` y `INCLUYE` a sus reglas actuales/cálculos. Un conjunto activo por etapa; referencias/cardinalidad completas. No hace falta para la correspondencia P1. | Evitar activar todo `Regla` o ignorar una regla obligatoria ausente. No ampliar `VersionParametros` FIS sin alterar a sus consumidores ni usar su validación experta como versión de representación. |
| Correspondencia P1 | Sólo tres propiedades nuevas en `Conveniencia.*`: `resultado_decision`, `contraoferta_habilitada`, `representacion_version`. | Sustituir el CASE por categoría, manteniendo los tres conjuntos y `TIENE_CONJUNTO` existentes. No nuevos nodos `Decision`. |

Son **dos formas auxiliares de expresión** y un manifiesto técnico para la activación, no un nuevo modelo de dominio. `Condicion` no almacena fórmulas; `PasoCalculo` no ejecuta texto. La creación de cada registro debe citar una política de la matriz; no agregar nodos sin consumidor/prueba ni generalizar operadores para hipotéticos usos futuros.

### Operaciones y tipado

- Comparadores finitos: igualdad/desigualdad, orden numérico, existencia/ausencia y las operaciones de texto ya utilizadas. El ámbito/patrón y el tratamiento del dato ausente pertenecen a la condición. No agregar interpretación de expresiones.
- Cálculo finito: suma, resta, producto, división, máximo y cuantización. Una selección condicional se expresa con las condiciones/prioridades de la regla, no con un operador de lenguaje arbitrario.
- Un CE/costo se referencia por relación y se registra sólo si se usa. Referencia faltante, comparador incompatible, operandos ambiguos, ciclos, orden repetido o salida sin correspondencia invalidan la configuración, no crean un resultado favorable.
- Los literales matemáticos y el lugar del redondeo son conocimiento. El mecanismo IEEE ya probado se conserva; **no** sustituir todo por `round()` ni etiquetar todos los redondeos como medio-par. La cuantización IEEE de SM3/RIE y el redondeo Cypher existente tienen identidades distintas.
- El orden RIE sigue categoría sobre centroide crudo → redondeo existente a cuatro decimales → cuantización IEEE a dos → DEM. VMA conserva división/redondeo/multiplicación a miles y la ubicación actual del adicional SSD; contraoferta conserva cuantización y límite no negativo en su orden actual.

## Destino de todas las áreas y retornos tempranos

| Área | Representación y contrato a conservar | Ancla funcional actual |
| --- | --- | --- |
| I1 | Condiciones simples/compuestas en las reglas de acción y consecuencias `ORDENA`/`OBLIGA`; mismos CE/costos. | `inferencia_sm1.py:28–79`; diagnóstico:41–70. |
| I2 | Prioridades por clase de evidencia y exclusión en reglas/patrones, sin cambiar detección positiva/irreversible. | `inferencia_sm1.py:81–137`. |
| I3 | Reglas de verificación/reparabilidad/estado con condiciones, prioridades y efectos; canal del operador sigue validación de entrada. | `inferencia_sm1.py:139–190`; orquestador:864–1016. |
| I4 | Orden técnico y consecuencias actuales, agregación única de tareas y mano de obra; no confundir tarea compartida con referencia corrupta. | `inferencia_sm1.py:196–238`. |
| I5 | R3.7/R3.8 actuales, grupos de condiciones y precedencia explícita. | `inferencia_sm3.py:148–151`. |
| I6 | Regla de margen base como representación de cálculo ya vigente; R3.4/R3.5 excluyentes y luego R3.6. | `inferencia_sm3.py:152–159`; Slot/demonio PG2:148. |
| I7 | Pasos de cálculo y cuantización con operandos/orden/método/precisión, referenciados desde sus reglas. | `inferencia_sm3.py:134–175`; cuantizador:49–115; valuación y RIE. |
| I8 | Propiedades nuevas en los tres ConjuntoDifuso existentes; ambas salidas se leen de datos. | `inferencia_sm3.py:210–217`; PG2:349–354. |
| I9 | Regla de valuación y pasos que consumen los mismos factores/catálogo, con condiciones de descuento/upgrades. | orquestador:640–700; mercado:211–300. |
| I10 | Reglas de prioridad de fuentes/desempates y R2.4 actualmente consumida, no una reinterpretación del PG2. | orquestador:648–700; mercado:342–348. |
| I11 | Reglas de estado/motivo y procedencia de cada rama realmente usada. | orquestador:686–745,1057–1097. |
| I12 | Clasificación final en reglas sobre inferencias/pendientes/validación usada, no sobre metadatos técnicos nuevos. | orquestador:1502–1509. |
| I13 | Patrones/señales vigentes enlazados a R3.3, con ámbito y semántica actual de subcadena; sin corrección B3 encubierta. | orquestador:138–155,1605–1618. |
| I14 | Conservar ReglaDifusa, antecedentes/consecuentes/grupos/parámetros y comprobar consumo, sin duplicarlos. | orquestador:157–350; PG2, sección 7. |
| R3.2 | Condición de inviabilidad y consecuencia DescartarInviabilidadTecnica, sin omitir trazas ni confundir pendiente con irreparable. | orquestador:1628–1639. |
| R3.3c | Estado técnico pendiente y consecuencia/motivo actuales. | orquestador:1640–1652. |
| R3.3b | Estado comercial pendiente y motivo actuales; misma autoridad del consumidor vigente. | orquestador:1057–1097,1658–1671. |
| Rechazo de entrada | Sigue como validación de transporte, no regla experta nueva. | orquestador:1583. |

Las anclas corresponden a la base indicada y pueden desplazarse al editar. Esta matriz fija destinos, no afirma que todas las filas estén implementadas. Cada corte detalla sus registros y prueba cambios de datos sin editar Python.

### Autoridad del legado y conflictos

1. **R2.4:** PG2 define una penalización por repuestos; mercado actualiza el mismo ID a generación anterior y conserva relaciones antiguas. Para paridad se representa la política de generación anterior que usa el consumidor vigente. No borrar/renombrar el nodo, reactivar el significado viejo ni registrar automáticamente todos sus `USA_CRITERIO`; documentar las relaciones históricas no utilizadas.
2. **R3.3b:** el camino PG2 por instancias `Operacion` no es el consumidor actual. Se migra la clasificación pública actual y se conserva el camino histórico sin activarlo ni unificar semánticas por semejanza del ID.
3. **Reglas reemplazadas:** R3.9–R3.11 y `REEMPLAZA_A` se preservan. La selección es por manifiesto de etapa, no por enumeración indiscriminada de `Regla`.
4. **Caída de base:** una desconexión total ya levanta ConnectionError antes de las señales. Un fallo de consulta con driver existente, en cambio, se oculta usando ocho señales Python. Eliminar esa lista cambia el comportamiento. **P5 debe reproducirlo con un driver simulado y pedir la decisión humana antes de activar esa diferencia.** No agregar caché ni decidir que toda excepción sea pendiente. Esto no bloquea P1–P4.

## Primera unidad P1

| Conjunto existente | resultado_decision | contraoferta_habilitada |
| --- | --- | --- |
| Conveniencia.Comprar | Comprar | false |
| Conveniencia.Negociar | ComprarConOfertaMenor | true |
| Conveniencia.Descartar | DescartarPorRiesgo | false |

- Allowlist: únicamente esas propiedades nuevas y `representacion_version` en esos tres nodos; no tocar `c`, `sigma`, `tipo`, `etiqueta`, `estado_validacion`, IDs, relaciones ni actores históricos.
- Un solo artefacto aditivo nuevo, con precondiciones sobre presencia/tipo/identidad y conflictos de propiedades antes de modificar; ejecutar en transacción explícita y verificar el resultado antes de confirmar. La segunda aplicación no cambia la proyección.
- Consumidor: `resolver_decision_sm3_cypher(driver, base, categoria, contraoferta)` conserva firma y las claves `decision`/`contraoferta_sugerida_ars`. Categoría inexistente sigue devolviendo una fila con ambos valores `None`; no convertirla inadvertidamente en ausencia de fila.
- Ningún CASE selecciona por nombre de categoría. Un CASE que verifica tipo/cardinalidad o aplica la habilitación booleana leída es mecanismo.
- Pruebas: paridad de las tres correspondencias y categoría desconocida; cambiar resultado y habilitación en una transacción de prueba cambia la salida pública sin editar código; configuración incompleta/ambigua no compra; idempotencia y protección del resto del grafo. Rollback explícito de las mutaciones de prueba, sin borrar nodos ajenos.

## Segunda unidad P2a — condiciones de las acciones de SM1

Superficie: `app/inferencia_sm1.py` (sólo la sección A de `CONSULTA_RESOLUCION` y el transporte
de error del adaptador), `cypher/Grupo_20_PG3_politicas_sm1_acciones.cypher`,
`scripts/aplicar_politicas_sm1_pruebas.py` y `app/tests/test_politicas_sm1_neo4j.py`.

| Pieza | Forma exacta | Comprobación previa |
| --- | --- | --- |
| Manifiesto | `(:VersionPoliticas {id:'VP-SM1-ACCIONES', version:'politicas-SM1-acciones-v1', etapa:'SM1-acciones', activa:true, ids_requeridos:[8], obligaciones_requeridas:11})` | uno solo por etapa; ids únicos y completos; ningún otro manifiesto de la etapa |
| Miembros | `(:VersionPoliticas)-[:INCLUYE {condiciones, criterios}]->(:Regla)` × 8 | cardinalidad declarada = condiciones/criterios reales; ningún miembro ajeno ni que no sea `Regla` |
| Condiciones | `(:Condicion {id, campo, ambito, operador, valor?, representacion_version})` × 9 | ids estables y únicos; `ambito` ∈ {`hechos`,`campos`}; `operador` ∈ {`=`,`<`,`ausente`,`presente`}; operando único (`valor` xor `USA_CRITERIO`; `ausente`/`presente` sin operando) |
| Grupos | `(:Regla)-[:REQUIERE {grupo}]->(:Condicion)` × 9 | una sola regla requiere cada condición y con el grupo declarado |
| Criterios | `(:Condicion)-[:USA_CRITERIO]->(:CriterioExperto)` × 2 (`CE-01`, `CE-27`) | existe una vez, valor numérico; una condición declara como máximo un criterio |
| Categorías difusas | `(:ReglaDifusa)-[:OBLIGA {etapa:'SM1-acciones', campo}]->(:CostoReparacion)` × 11 | conserva `categorias` y `orden` previos; `campo` no vacío; base de SM1 con su cardinalidad |

Semántica conservada: un grupo se satisface con cualquiera de sus condiciones (OR) y la regla con
todos sus grupos (AND); una regla sin condiciones (mano de obra) se agrega al final si el plan
tiene intervenciones. `=`, `<`, `ausente` y `presente` son comparadores finitos; un hecho ausente
no satisface una comparación (nunca se convierte en favorable) y `<` sólo compara operandos
numéricos. `orden`, costos, tareas y la procedencia (`criterio_*`) se leen como antes: la cola de
la sección A no cambió, así que el plan, el total y las claves de `reglas` son los mismos.

Consecuencias preservadas: `ORDENA` y `OBLIGA` existentes; P2a no agrega costos ni cambia
prioridades expertas. No se toca `campo`, `valor`, `tarea`, `orden`, `requiere_plan` ni
`cuenta_como_intervencion` de las `Regla` (el seed diagnóstico las vuelve a `SET`) ni ningún
criterio, costo, conjunto, diagnóstico o propiedad de validación experta. La versión de
representación no es validación: todo sigue Provisional donde ya lo estaba.

Configuración inválida: el grafo devuelve la lista `configuracion_invalida` (manifiesto ausente o
repetido, regla sin costo único, condiciones que no coinciden con las declaradas, operador no
admitido, operando ambiguo, criterio faltante/ambiguo/no numérico, obligación sin hecho o
categorías, condición propia no requerida por la etapa). `consultar_resolucion_sm1` la traduce al error de
conocimiento existente (`ConocimientoFaltante` con el motivo concreto) y `consultar_sm1` la
publica como `ErrorConocimiento`; no hay `RuntimeError`, ni un `collect` más corto convertido en
plan vacío o reparación gratuita. Una configuración sin manifiesto también falla explícitamente,
aunque no haya condiciones cargadas.

Alcance deliberadamente excluido: precedencias de evidencia textual (P2b) y selección de
estado/plan/combinación (P2c) siguen en la consulta. P2a no reordena, no cambia estados y no
corrige B3–B5.

Pruebas (`test_politicas_sm1_neo4j.py`, cada mutación en una transacción que se revierte):
cambiar el comparador, el campo, el ámbito, el grupo o el criterio enlazado cambia el plan público;
reapuntar el `campo` de una `OBLIGA` cambia la acción difusa; la segunda aplicación no cambia la
proyección; una configuración previa distinta se rechaza sin escribir; seis configuraciones
inválidas/incompletas producen `ErrorConocimiento` con su motivo y sin plan. La paridad de
comportamiento la cubren `test_sm1_neo4j.py`, la suite con grafo (200 pruebas) y la offline
(90, 17 omisiones por falta de Neo4j), sin tocar el corpus ni el grafo de trabajo.

## Referencia observada y seguridad de ejecución

- Nueva suite antes de la migración: **184 pruebas, sin omisiones, exit 0**, en `ejecuciones/politicas_p0_baseline_pruebas.log`.
- Referencia pública fija: cuatro consultas de correspondencia y una evaluación integral T14 con extracción/redacción controladas, `ejecuciones/politicas_p0_referencia_publica.json`; decisión integral `Comprar`.
- Grafo antes/después del baseline idéntico: SHA256 `d3bff60e62990562ccca493ce95840d731f788b4a606f5412d9bff0dd23d6fc4`. Proyección completa protegida bajo `_respaldo_original/politicas-p0-80654c9/`; inventario en `ejecuciones/politicas_p0_grafo.json`.
- Runner: `PYTHONDONTWRITEBYTECODE=1 EVALTIC_NEO4J_PRUEBAS_URI=bolt://127.0.0.1:17687 EVALTIC_NEO4J_PRUEBAS_DATABASE=neo4j /home/alvaro/Universidad/IA/Proyecto/.venv/bin/python -m unittest discover -s app/tests -v`.
- Los fixtures mockean `dotenv.load_dotenv` antes de importar, usan driver explícito/authNone y exigen marcador; la comprobación puntual de SM3 confirmó eso, **no** una guarda de host/puerto dentro del fixture. El endpoint fijo lo proporciona este runner. Diagnóstico usa la base `neo4j` de forma fija: no afirmar que respeta la variable de base de otros módulos.
- No hubo acceso original, `.env`, API/LLM, actualización del grafo ni nuevas dependencias. No se necesita un RED para esta documentación/baseline; el cambio de comportamiento P1 sí empieza por RED.
