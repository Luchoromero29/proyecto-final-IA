# Adaptación acotada de la capa LLM de EvalTIC
Objetivo: portar las mejoras aprobadas sin reemplazar el sistema experto; tracker local `feat/adaptacion-llm`; estrategia `auto-chain`, `feature-branch-chain`, elegida por el usuario.
Runner: `/home/alvaro/Universidad/IA/Proyecto/.venv/bin/python`; base `d63a14c5d7a5241200734fbebda5eb6f20849f4e`; pruebas offline, sin API ni Neo4j reales.

## Specs
- S1: «Leé CONTEXTO_Y_MEJORAS_EVALTIC.md. Explorá primero esta versión del repositorio. con un subagente explorador y mapeá sus componentes equivalentes. Después decime como adaptar las mejoras documentadas, sin sobrescribir la aplicación ni cambiar sus reglas de negocio.
Esta nueva version tiene muchas mejoras en la logica del negocio, Neo4J.» Comprobación: preservar motores, prompts, casos, Cypher y ruta D1; portar solo la capa LLM aprobada, con pruebas de compatibilidad.
- S2: «Perfecto, arma un plan de implementación y hacelo.» Comprobación: plan y evidencia RED/GREEN del cliente público, validaciones y alcance OpenRouter documentados en CONTEXTO_Y_MEJORAS_EVALTIC.md §§8–12.
- S3: «Tené en cuenta que el .env que está en la carpeta es el mío, que usaba en el proyecto anterior así que usamos eso.» Comprobación: seleccionar el `.env` de este repositorio, sin modificarlo, imprimir secretos ni usar el de la copia anterior; respetar variables exportadas.
- S4: «Y los límites de tokens se van a agrandar un poco no solo para openrouter.» Comprobación: extracción y síntesis aumentan también para Ollama y otros proveedores; preservar límites explícitos del cliente fuera de la regla específica de OpenRouter.
- S5: «Para actualizar el levantar.md agregando mi configuración tené en cuenta que yo tengo un entorno virtual en universidad/IA/proyecto donde levanto la app, con todas las dependencias instaladas y todo listo.» Comprobación: LEVANTAR.md documenta este repositorio con el intérprete existente, sin reinstalaciones ni copias; ejemplos sin claves reales.
- S6: «Si hace falta pregúntame algo o busca la información que necesites. Luego una vez este plan manda a un worker a qué implemente todo» Comprobación: implementación completa delegada a un worker acotado; padre valida resultados y cierra.

## Tasks
- T1 [S1–S6] inline — done — Plan y entorno comprobados; commit del tracker: a9f154d.
- T2 [S1–S6] delegated (`gentle-ai-worker`, pedido explícito y context backstop) — done — RED inicial exit 1; corrección con RED 29 tests/2 errores exit 1, GREEN final repetido por padre 29 tests exit 0 y compilación exit 0; commits: 7c3ac6f (entorno/presupuestos), f6b565f (validación), 4ed1953 (OpenRouter).
- T3 [S1–S6] inline (slicing delegado al mismo worker) — done — Cadena local guardada y comprobada; tres slices 333/225/115 líneas; ASSESS no evaluable por untracked, sin aprobación nativa; plan exige self-verification cumplida; cierre en este registro.

## Log
### L1 — Pedido original
Leé CONTEXTO_Y_MEJORAS_EVALTIC.md. Explorá primero esta versión del repositorio. con un subagente explorador y mapeá sus componentes equivalentes. Después decime como adaptar las mejoras documentadas, sin sobrescribir la aplicación ni cambiar sus reglas de negocio.
Esta nueva version tiene muchas mejoras en la logica del negocio, Neo4J.

### L2 — Autorización de implementación
Perfecto, arma un plan de implementación y hacelo. Tené en cuenta que el .env que está en la carpeta es el mío, que usaba en el proyecto anterior así que usamos eso. Y los límites de tokens se van a agrandar un poco no solo para openrouter. Para actualizar el levantar.md agregando mi configuración tené en cuenta que yo tengo un entorno virtual en universidad/IA/proyecto donde levanto la app, con todas las dependencias instaladas y todo listo. Si hace falta pregúntame algo o busca la información que necesites. Luego una vez este plan manda a un worker a qué implemente todo

### L3 — Plan técnico y supuestos explícitos
- Valores elegidos para «un poco»: extracción 1024 tokens (incluido su reintento existente), síntesis 768; OpenRouter mantiene piso 4096 y límites mayores. No se agregan variables genéricas ni reintentos/fallbacks pagos.
- En OpenRouter + modelo exacto `nvidia/nemotron-3.5-lightning:free`, enviar `reasoning.enabled=false`. No generalizar a otros modelos; no afirmar disponibilidad actual sin API real.
- Validar estructura choices/message/content y rechazar `finish_reason=length`; metadatos seguros, sin reasoning como respuesta. Conservar payloads ajenos, json_mode=False del extractor, parser, prompts y respaldo determinístico existente.
- Configuración: preferencia app/.env → raíz del repositorio/.env → fallback PI4 existente → búsqueda preexistente si nada existe; load_dotenv sin override para preservar variables exportadas. No leer/imprimir/modificar secretos; pruebas con dotenv y transporte aislados.
- Entorno confirmado: `/home/alvaro/Universidad/IA/Proyecto/.venv/bin/python` importa requests, dotenv, neo4j y streamlit. El `.env` de la raíz existe y está ignorado. No usar el `.env` ni el código de `/home/alvaro/Universidad/IA/Proyecto`.
- No modificar motores, prompts, Cypher, UI, dependencias, Docker ni datos; ruta D1 activa preservada. No ejecutar APIs, Neo4j, cargas, instalaciones ni levantar servidores. Documentar comandos de arranque, no ejecutarlos.
- Comprobar RED/GREEN offline, payloads previos, aumento de presupuestos en ambas etapas, respaldo determinístico, resolución de configuración y una comparación diferencial aislada base/cambio. Invariantes del dominio por lectura/AST, no por inventar una corrida integral.
- RDD global activo. Evaluar diff al volver el writer y seguir únicamente el plan/continuación nativos aplicables. Sin push/PR. Una unidad coherente; no comprimir pruebas para una cuota de líneas.

### L4 — Revisión del primer handoff
- Worker mw9mz97i-2-67e2 entregó cliente, 28 tests y LEVANTAR.md; reportó RED exit 1 (11 fallos/23 errores con subtests), GREEN exit 0, diferencial sin regresiones no pedidas y AST de dominio intacta.
- Padre repitió suite: 28 tests OK, exit 0; compilación en memoria OK, exit 0.
- Padre reprodujo por consultar_llm con transporte/dotenv simulados: finish_reason=['length'] y content=None produce TypeError, exit 1, en vez del RuntimeError previsto. Una corrección acotada al mismo worker más test de regresión.
- ASSESS invocado una vez sobre diff: herramienta falló sin diagnóstico útil; evaluación indisponible, no aprobación ni evidencia de reviewDue. Sin reintento automático.
- Tamaño real: 647 líneas de código/pruebas/docs (más tracker), mayor que estimación. Antes del commit se requiere decisión de estrategia de entrega; no eliminar pruebas por cuota.
- APIs, Neo4j y Streamlit reales siguen sin ejecutar por alcance. Carpeta temporal del worker /tmp/evaltic-diff-NaY0Pg contenía solo sondas y copias sin secretos; eliminada al cerrar.

### L5 — Corrección y estrategia de entrega
- Corrección mw9n8y25-3-qo58: finish_reason malformado se valida por tipo antes de la whitelist; regresión observó RED (29 tests, 2 errores, exit 1) y GREEN (29 tests, exit 0). Padre repitió 29 tests y compilación, ambos exit 0.
- Decisión humana en selector: «Cadena sobre una rama de funcionalidad — recomendada», token feature-branch-chain. No autoriza push ni PR.
- Una única pasada de partición: tracker local con plan; slice 1 configuración .env + presupuestos por etapa + sus tests/docs; slice 2 validación de respuestas/metadatos + sus tests/docs; slice 3 piso/razonamiento OpenRouter + sus tests/docs. Dependencias lineales en ese orden; cada rama futura apunta a su padre inmediato, primera al tracker.
- No se descartan pruebas ni se comprime el código. Mismo worker prepara patches de índice y comprueba los snapshots aislados; padre conserva estado final y hace los commits locales, sin publicar.
- Tracker local creado: a9f154d (49 líneas, solo plan). ASSESS de este nuevo candidato committedOnly: nativeRisk=unassessable por archivos no rastreados sin declaración explícita; plan nativo: writerSelfVerification=true, independentVerifier=false. Sin aprobación nativa; la verificación propia sigue siendo la exigida. No cambiar autoridad ni iniciar review sin reviewDue/continuación.

### L6 — Slices locales y comprobaciones
- Worker mw9ndw8r-4-m6f9 preparó snapshots aislados: s1 13 tests, s2 23 tests, s3 29 tests; suites y compilaciones exit 0. Los tres patches acumulados son byte-idénticos al estado final probado. No hay cambios de motores, prompts, pipeline, UI o Cypher.
- Slice 1: feat/adaptacion-llm-01-entorno → feat/adaptacion-llm, commit 7c3ac6f, 333 líneas autoradas; configuración, presupuestos y arranque Linux, 13 tests. Rollback: selección previa de .env y presupuestos 260.
- Slice 2: feat/adaptacion-llm-02-validacion → feat/adaptacion-llm-01-entorno, commit f6b565f, 225 líneas; validación y metadatos, 23 tests acumulados. Rollback: retorno previo .strip() sin validación. Las funciones documentan su contrato; el resumen de usuario en LEVANTAR se incorpora con slice 3.
- ASSESS committedOnly por cada slice, contra su padre inmediato: unassessable por archivo no rastreado sin declaración explícita; writerSelfVerification=true, independentVerifier=false. Sin reviewDue ofrecido ni aprobación nativa. No se reintenta el mismo candidato ni se muta autoridad.
- Slice 3: feat/adaptacion-llm-03-openrouter → feat/adaptacion-llm-02-validacion, commit 4ed1953; política OpenRouter y documentación; 115 líneas, 29 tests acumulados. Rollback: elimina piso y override, conserva presupuesto por etapa y validación. La cadena elegida resuelve el exceso acumulado: ninguna slice supera 400. Sin push/PR.

### L7 — Cierre verificado
- Estado final del worktree de los tres archivos de implementación idéntico al HEAD 4ed1953 y a snapshots probados. Padre comprobó AST contra base: todas las funciones previas sin cambios salvo cliente y literales 1024/768 de los dos llamadores. Cypher, UI, Docker y dependencias sin cambios (`git diff --exit-code`, exit 0).
- Resultado: 29 tests offline OK y compilación OK; comparación diferencial del worker sin diferencias no solicitadas. Cada snapshot intermedio tiene suite y compilación exit 0. .env preservado e ignorado; no se leyeron/imprimieron credenciales.
- Evaluación nativa por cada nuevo candidato: nativeRisk=unassessable, requiere declaración explícita de untracked; sin reviewDue/continuación ofrecida y sin aprobación. Plan emitido: writerSelfVerification=true, independentVerifier=false; cumplido. No se modificó autoridad ni se habilitó review por cuenta del agente.
- Temporales generados /tmp/evaltic-diff-NaY0Pg y /tmp/evaltic-slices-gV9YlF eliminados. CONTEXTO_Y_MEJORAS_EVALTIC.md permanece untracked, como al inicio, y no se incluyó en commits.
- Risk: none. Los cambios de contrato del cliente y presupuestos están expresamente solicitados; funciones de negocio compartidas, prompts y parser no cambiaron.
- Pendiente opcional externo, no bloqueante del portado offline: prueba humana con la API y el Neo4j configurados. No se verifica disponibilidad del proveedor, razonamiento cero, datos cargados ni funcionamiento E2E hasta esa prueba. No ejecutar recargas destructivas para probar estos cambios de Python.
