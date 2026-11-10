# Actualizar y validar la integración de EvalTIC
Rama: `integracion/mejoras-con-pruebas`; base `8187583`. Entrega local por unidades; sin push ni PR. Estimación: menos de 300 líneas autorales, excluidos logs generados.
Runner autorizado: `/home/alvaro/Universidad/IA/Proyecto/.venv/bin/python`. Preservar baseline `59026ec`, corpus y evidencia histórica.

## Specs
S1. «Claro, actualiza todo lo necesario.» — Adaptar el fixture al contrato de mercado incorporado por el merge, sin relajar expectativas ni cambiar reglas de negocio.
S2. «Quizaas haya que actualizar todo el grafo de NEO4J. Y si lo haces esta bien para que quede en la ultima version.» — Comprobar el grafo y actualizarlo si corresponde, revisando previamente la seguridad de la carga.
S3. «Hacelo, y luego corre las pruebas.» — Ejecutar pruebas offline y, con prerrequisitos disponibles, los 61 casos reales; conservar evidencia nueva separada del baseline.
S4. «Te autorizo a tomas decisiones obvias. Si hay algo destructivo para y decime» — Resolver preparaciones ordinarias, detenerse antes de operaciones destructivas; no ejecutar reset PG2 ni reemplazar el grafo con el dump.

## Tasks
T1 | S1,S3,S4 | worker por context backstop; padre integra | done | Fixture adaptado sin cambiar producción/corpus; RED2tests exit1, GREEN2/2 exit0, suite71/71 exit0. Commit pendiente.
T2 | S2,S4 | explorer mapa; padre operaciones | in_progress | Explorer revisa seguridad de carga antes de arrancar o modificar Neo4j; contenido no comprobado.
T3 | S3,S4 | padre | pending | Ejecutar corpus real, registrar comparación y limitaciones, cerrar documentación; commit pendiente.

## Log
L1. Pedido original: «Claro, actualiza todo lo necesario. Quizaas haya que actualizar todo el grafo de NEO4J. Y si lo haces esta bien para que quede en la ultima version. Hacelo, y luego corre las pruebas. Te autorizo a tomas decisiones obvias. Si hay algo destructivo para y decime».
L2. Estado heredado: 69 pruebas offline con 31 KeyError por fixture sin valor_proc/generacion_anterior; suite baseline 69/69. Neo4j detenido; contenido actual sin verificar. El verificador anterior está finalizado; ningún child incierto al autorizar este nuevo trabajo. No se repiten sus intentos automáticamente: esta autorización nueva permite adaptar fixture y volver a verificar. Archivo ajeno CONTEXTO_Y_MEJORAS_EVALTIC.md intacto y sin seguimiento.
L3. Una exploración de seguridad de la carga está delegada a gentle-ai-explore, task mwb016vk-2-03b1. No modifica grafo ni archivos. La recarga no se presume segura por llamarse idempotente.
L4. T1 completada por worker mwb02gc3-3-rv0r: campo valor_proc y generacion_anterior=None en fixture; dos pruebas del contrato. RED2tests exit1; GREEN2/2 exit0; suite71/71 exit0. No expectativas/casos ni producción modificados. Assess: nativeRisk unassessable por archivos sin seguimiento; plan selfVerification, sin verifier independiente ni aprobación nativa. Lectura estructural del diff y git diff --check por padre.
