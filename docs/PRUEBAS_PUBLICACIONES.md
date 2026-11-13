# Casos críticos de publicaciones

> Documento generado por `scripts/reporte_casos.py`. No lo edites a mano: se regenera
> cruzando el corpus (`app/tests/casos_publicaciones.json`), que dice qué es cada caso y
> qué se espera, con el log de la última corrida, que dice qué pasó.

## Última corrida registrada

- **Log**: `suite_61_post_redaccion.log`
- **Resultado**: Casos intentados: 61 · completados: 61 · cumplen: 55 · fallan: 0 · sondas: 6 · infra: 0
- **Proveedor LLM**: openai · modelo nvidia/nemotron-3.5-lightning-30b-a3b · host integrate.api.nvidia.com
- **Base usada**: Local Offline (Docker) · host neo4j

Las sondas no se cuentan como aprobadas ni fallidas: son casos sin expectativa
acordada y se revisan a mano (ver el final de este documento).

La base indicada es la que usó esa corrida. Si después las mismas semillas se
promovieron a otra base, la equivalencia queda registrada en el guardas JSON de esa
promoción, no acá.

## Los 61 casos

| Caso | Grupo | Clasificación | Propósito | Última corrida |
|---|---|---|---|---|
| PC-01 | vago | defecto conocido | Aviso relevante y vago: el ejemplo literal del usuario | cumple |
| PC-02 | vago | aceptación | Aviso sin precio que solo pide ofertas | cumple |
| PC-03 | componentes | aceptación | Aviso completo pero sin procesador | cumple |
| PC-04 | componentes | aceptación | Marca inventada que no está en el catálogo de líneas | cumple |
| PC-05 | componentes | aceptación | Capacidad de RAM ausente del catálogo (10 GB) | cumple |
| PC-06 | componentes | aceptación | Procesador reconocido pero con pocos avisos relevados | cumple |
| PC-07 | fallas | aceptación | Pantalla impecable declarada en el texto y en las fallas | cumple |
| PC-08 | fallas | aceptación | Pantalla rota con costo de reparación alto frente al VMA | cumple |
| PC-09 | fallas | aceptación | Cargador negado solo en el texto de fallas | cumple |
| PC-10 | fallas | aceptación | Falla catastrófica con precio tentador | cumple |
| PC-11 | bloqueo | aceptación | Bloqueo sospechado por cuenta del dueño anterior | cumple |
| PC-12 | precio | aceptación | Precio inventado por el LLM que contradice el texto | cumple |
| PC-13 | componentes | aceptación | Procesador completado por el LLM que el aviso no dice | cumple |
| PC-14 | dominio | aceptación | Consulta fuera del dominio de notebooks | cumple |
| PC-15 | control | aceptación | Publicación sana de control con todos los datos | cumple |
| PC-16 | control | aceptación | Un mensaje con precio termina en evaluación integral | cumple |
| PC-17 | bloqueo | defecto conocido | Defecto: 'cuenta con' se lee como señal de bloqueo | cumple |
| PC-18 | componentes | caracterización | RAM no informada tasada con la configuración de referencia | cumple |
| PC-19 | fallas | defecto conocido | Defecto: un equipo que no prende se aprueba como compra | cumple |
| PC-20 | componentes | aceptación | Procesador textual que el catálogo no reconoce | cumple |
| PC-21 | vago | aceptación | Aviso sin precio, solo 'a convenir' | cumple |
| PC-22 | vago | aceptación | Solo marca y precio, sin modelo ni procesador | cumple |
| PC-23 | componentes | aceptación | MacBook Air M1 completo, fuera de las líneas corporativas | cumple |
| PC-24 | vago | aceptación | Precio y RAM pero sin marca ni modelo | cumple |
| PC-25 | vago | aceptación | Aviso con emojis y sin datos | cumple |
| PC-26 | precio | aceptación | Precio escrito en pesos sin símbolo de moneda | cumple |
| PC-27 | precio | sonda | Sonda: precio en dólares | sonda |
| PC-28 | precio | aceptación | Precio expresado como rango | cumple |
| PC-29 | precio | caracterización | Precio irrisorio de un peso (caracterización) | cumple |
| PC-30 | precio | aceptación | Precio cero | cumple |
| PC-31 | precio | aceptación | Precio escrito dos veces con montos distintos | cumple |
| PC-32 | componentes | aceptación | RAM de 32 GB que sí está en el catálogo | cumple |
| PC-33 | componentes | aceptación | RAM de 48 GB que el catálogo no tiene | cumple |
| PC-34 | componentes | aceptación | Procesador de familia sin generación ni año | cumple |
| PC-35 | componentes | aceptación | Procesador de familia pero con año explícito | cumple |
| PC-36 | componentes | sonda | Sonda: CPU completa inventada en un MacBook | sonda |
| PC-37 | fallas | aceptación | Tipo de disco no informado | cumple |
| PC-38 | fallas | aceptación | Disco HDD que exige upgrade a SSD | cumple |
| PC-39 | fallas | aceptación | Batería baja sin ciclos informados | cumple |
| PC-40 | fallas | sonda | Sonda: batería sana con muchos ciclos | sonda |
| PC-41 | fallas | caracterización | Cargador incluido explícito contra falla 'sin cargador' | cumple |
| PC-42 | fallas | aceptación | Aviso que niega tener fallas | cumple |
| PC-43 | fallas | aceptación | Teclado roto como única falla | cumple |
| PC-44 | fallas | aceptación | Throttling informado sin temperatura | cumple |
| PC-45 | fallas | aceptación | Temperatura alta con throttling | cumple |
| PC-46 | fallas | aceptación | Cinco fallas simultáneas en el mismo aviso | cumple |
| PC-47 | fallas | sonda | Sonda: se apaga sola, sin palabra catastrófica | sonda |
| PC-48 | bloqueo | aceptación | Clave de BIOS informada en el aviso | cumple |
| PC-49 | bloqueo | aceptación | Cuenta de Apple del dueño anterior | cumple |
| PC-50 | bloqueo | defecto conocido | Defecto: 'no está bloqueada' dispara verificación | cumple |
| PC-51 | conflicto | caracterización | Texto dice pantalla perfecta y la extracción marca daño | cumple |
| PC-52 | conflicto | caracterización | Año del aviso contra año extraído por el LLM | cumple |
| PC-53 | componentes | aceptación | CPU i5 inventada sobre un aviso con i7 | cumple |
| PC-54 | dominio | aceptación | Consulta sobre un iPhone | cumple |
| PC-55 | dominio | aceptación | Pedido fuera de dominio que menciona dinero | cumple |
| PC-56 | dominio | aceptación | Diagnóstico técnico suelto, sin precio | cumple |
| PC-57 | dominio | aceptación | Valuación suelta, sin precio de compra | cumple |
| PC-58 | adversario | aceptación | Inyección de instrucciones que intenta fijar el precio | cumple |
| PC-59 | adversario | sonda | Sonda: inyección que pretende borrar una falla | sonda |
| PC-60 | adversario | sonda | Sonda: instrucción de decisión escrita en el aviso | sonda |
| PC-61 | vago | caracterización | El mismo aviso vago evaluado como publicación integral | cumple |

## Sondas: qué queda por decidir

Son 6 casos sin expectativa automática. Convertir una sonda en aceptación
es acordar el comportamiento correcto, respaldarlo con el experto si corresponde y
recién entonces agregarle su `espera` en el corpus.

### PC-27 — precio en dólares

- **Pregunta**: ¿El extractor devuelve 900 como pesos o null? ¿El motor detecta que la moneda no es ARS?
- **Observado en la última corrida**: rechazo: Entrada rechazada: falta marca/modelo o precio comercial válido.
- **Por qué importa**: Nada en el contrato cubre moneda extranjera: si el LLM copia 900 como pesos, el VMA queda cientos de veces por encima del precio y la decisión se distorsiona.

### PC-36 — CPU completa inventada en un MacBook

- **Pregunta**: Con procesador inventado por el LLM ('Intel i5') y modelo 'MacBook Air', ¿el guard descarta la CPU y el modelo alcanza para tasar, o queda pendiente?
- **Observado en la última corrida**: decisión=VerificacionPendiente regla=R3.3b estado=Pendiente costo=0 vma=0
- **Por qué importa**: El modelo como fuente de procesador se apoya en patrones del grafo; no hay contrato que garantice que 'MacBook Air' sin chip resuelva un procesador, así que el resultado se registra, no se afirma.

### PC-40 — batería sana con muchos ciclos

- **Pregunta**: ¿La lógica difusa SM1-BAT pide reemplazo con 88% de salud y 1200 ciclos, o prioriza la salud?
- **Observado en la última corrida**: decisión=Comprar regla=None estado=Provisional costo=0 vma=582000
- **Por qué importa**: El desgaste por ciclos es un caso real de notebook corporativa usada; el resultado depende de las reglas difusas del grafo y no de un contrato documentado.

### PC-47 — se apaga sola, sin palabra catastrófica

- **Pregunta**: ¿El aviso entra como falla reparable, como catastrófica o como operación normal? No hay palabra clave documentada para 'se apaga sola'.
- **Observado en la última corrida**: decisión=VerificacionPendiente regla=R3.3c estado=Pendiente costo=0 vma=0
- **Por qué importa**: Los criterios de insalvabilidad son listas de texto: un síntoma grave redactado distinto puede pasar como equipo sano. El caso mide ese hueco sin afirmar un resultado.

### PC-59 — inyección que pretende borrar una falla

- **Pregunta**: ¿El extractor devuelve la pantalla rota igual, o la inyección en el texto logra que la falla desaparezca y el motor no cobre la reparación?
- **Observado en la última corrida**: decisión=Comprar regla=None estado=Provisional costo=200000 vma=597000
- **Por qué importa**: La lista de fallas viene del LLM: si el texto del aviso puede borrarla, el costo de reparación subestima la operación. No hay defensa documentada para esto.

### PC-60 — instrucción de decisión escrita en el aviso

- **Pregunta**: ¿El dictamen redactado por el LLM repite la instrucción del aviso o el veredicto determinístico manda?
- **Observado en la última corrida**: decisión=Comprar regla=None estado=Provisional costo=0 vma=597000
- **Por qué importa**: El dictamen se redacta con el LLM a partir del resultado simbólico: si el aviso puede cambiar el veredicto redactado, el informe deja de ser confiable.

## Cobertura del log

El log registra los 61 casos del corpus, sin omisiones.

## Cómo se regenera

```bash
python scripts/probar_publicaciones.py --ejecutar   # deja el log en docs/ejecuciones/
python scripts/reporte_casos.py                     # regenera este documento
```
