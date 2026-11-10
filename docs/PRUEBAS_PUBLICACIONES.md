# Pruebas de publicaciones críticas

## Corrección de precio B1

El precio usado por el pipeline se valida contra el primer monto literal con `$` o `pesos`,
incluyendo cero y montos cortos. Sin respaldo en esos formatos se rechaza antes de tasar;
no se inventa un monto ni se admite una tolerancia monetaria. No agrega conversión de divisas
ni una política de precio mínimo.

La [evidencia B0/B1](ejecuciones/mejoras_b0_b1.md) registra **79/79 offline** y una tanda real
con **50 cumplen, 5 fallan, 6 sondas y 0 infra** sobre 61 completados. PC-29 ahora cumple;
los otros defectos no se corrigieron en ese bloque. La evidencia histórica se conserva.

## Corpus y ejecutor

Corpus de 61 publicaciones **sintéticas** (avisos escritos para este corpus, no avisos reales
recolectados) que miden cómo se comporta EvalTIC frente a entradas vagas, incompletas,
contradictorias y adversariales, sin tocar el motor. 55 casos tienen expectativa automática
(45 de aceptación, 6 de caracterización, 4 defectos conocidos) y 6 son sondas que solo se
registran. Las pruebas offline viven en `app/tests/test_publicaciones_criticas.py`, las del
ejecutor en `app/tests/test_probar_publicaciones.py` y la ejecución real en
`scripts/probar_publicaciones.py`.

## Camino rápido

Desde la raíz del repositorio, con el entorno virtual del proyecto:

```bash
# 1. Lista el corpus. No importa el motor, no lee el .env, no usa red.
python scripts/probar_publicaciones.py

# 2. Chequeo previo: configuración, Neo4j y catálogo. No consume tokens.
python scripts/probar_publicaciones.py --verificar

# 3. Un solo caso real (empezá siempre por acá).
python scripts/probar_publicaciones.py --caso PC-01 --ejecutar

# 4. Todos los casos reales: consume cuota del proveedor.
python scripts/probar_publicaciones.py --ejecutar

# 5. Pruebas automáticas (offline, sin red ni LLM real).
python app/tests/test_publicaciones_criticas.py -v
python app/tests/test_probar_publicaciones.py -v
```

Códigos de salida del ejecutor: `0` todo cumple, `1` algún caso no cumple su expectativa,
`2` infraestructura o uso incorrecto. Un error de infraestructura nunca se cuenta como
cumplido ni como rechazo de dominio: se informa solo la clase de la excepción o el tipo de
error, y se corta con código `2`.

## Qué verifica cada nivel

| Clasificación | ¿Offline? | ¿Se afirma? | Dónde está la expectativa |
|---|---|---|---|
| `aceptacion` (45) | Sí | Sí | `espera` (contrato) + `espera_offline` (valores de fixture) |
| `caracterizacion` (6) | Sí | Sí, es el comportamiento actual documentado | `espera` + `espera_offline` según el caso |
| `defecto_conocido` (4) | Sí | Se informa estado abierto o reparado | `observado_hoy` (hoy) + `espera` (contrato) |
| `sonda` (6) | No se ejecuta | No: solo se imprime lo observado | `sonda` (la pregunta que se quiere responder) |

Dos campos separan lo que vale en cualquier entorno de lo que solo vale con fixtures:

- `espera`: verificable contra el grafo real y el texto literal de la publicación. No incluye
  años, fallas ni CPUs extraídas por el fixture, ni costos o VMA calculados con valores de prueba.
- `espera_offline`: sí puede fijar la extracción simulada, el catálogo de prueba y los montos
  derivados. Las pruebas offline comprueban ambos campos; el ejecutor real comprueba solo `espera`.

Cuando el desenlace en vivo depende de la calibración del grafo o de lo que extraiga el modelo
(PC-06, PC-13, PC-23, PC-35, PC-51, PC-53), la expectativa viva es un invariante necesario
—la publicación no se rechaza, y si se tasa, se tasa el componente que el aviso menciona— y la
expectativa fuerte queda en `espera_offline`. No se fuerza un defecto simulado sobre el modelo real.

Los defectos no usan `xfail`. La prueba offline informa `estado=abierto` mientras el contrato
falle y, en ese caso, exige que el comportamiento observado coincida con `observado_hoy`. Si el
motor se repara, la prueba informa `estado=reparado` y pasa: la suite no fija el bug.

El verificador de expectativas tiene una sola fuente: `scripts/probar_publicaciones.py`. Las
pruebas offline importan de ahí `_comprobar` y `validar_espera`, así que una clave o un tipo de
resultado no soportado falla en vez de ignorarse en silencio.

## Grupos del corpus

| Grupo | Casos | Qué busca |
|---|---|---|
| `vago` (7) | PC-01, 02, 21, 22, 24, 25, 61 | Avisos sin precio, sin modelo o con emojis: nada que tasar. |
| `precio` (7) | PC-12, 26, 27, 28, 29, 30, 31 | Precio inventado, sin `$`, rango, duplicado, cero, irrisorio y dólares. |
| `componentes` (14) | PC-03, 04, 05, 06, 13, 18, 20, 23, 32, 33, 34, 35, 36, 53 | CPU/RAM/línea ausentes, desconocidas o sub-calibradas; familia sin año; Apple. |
| `fallas` (16) | PC-07 a 10, 19, 37 a 47 | Negaciones, pantalla, teclado, batería, cargador, HDD, temperatura y múltiples fallas. |
| `bloqueo` (5) | PC-11, 17, 48, 49, 50 | iCloud, cuenta del dueño, clave de BIOS y falsos positivos por subcadena. |
| `conflicto` (2) | PC-51, 52 | Texto contra extracción: pantalla "perfecta" marcada dañada y año contradictorio. |
| `dominio` (5) | PC-14, 54, 55, 56, 57 | Receta, iPhone, préstamo y los flujos sueltos SM1/SM2. |
| `control` (2) | PC-15, 16 | Publicación sana y precio que obliga a la evaluación integral. |
| `adversario` (3) | PC-58, 59, 60 | Instrucciones dentro del aviso: precio falso, borrar fallas, pedir "Comprar". |

## Qué se simula y qué no

| Frontera | Offline | Ejecución real |
|---|---|---|
| Respuestas del LLM (extracción, enrutador, redacción) | Simuladas con `extraccion_llm` e `intencion_router` | LLM del `.env` |
| Criterios y costos (`cargar_conocimiento`) | Fixture con valores de prueba | `:CriterioExperto` y `:CostoReparacion` del grafo |
| Catálogo de componentes (`consultar_mercado_componentes`) | Fixture con la forma del Cypher | Cypher real |
| Reglas difusas SM1-BAT/TER, SM2-RIE/DEM, SM3-CONV | Fixture `(centroide, categoría)` | Cypher real |
| Fallas catastróficas y señales de bloqueo | Listas fixture | Nodos del grafo + listas de respaldo |
| Conexión Neo4j | `obtener_driver_neo4j` simulado | Neo4j local |

No se simula, en ninguna de las dos modalidades: enrutamiento y regla "precio ⇒ integral",
validaciones defensivas de precio, CPU, año y RAM, reglas crisp SM1 (R1.1, R1.2, R1.3) y su
mapeo de fallas a tareas, plan y costos con mano de obra, encadenamiento SM1 → SM2 → SM3,
filtros R3.7 y R3.8, margen requerido R3.4/R3.5/R3.6, contraoferta, `_estado_decision` y el
control anti-alucinación del dictamen. El resultado que se afirma nunca se mockea.

## Hallazgos actuales

1. **PC-01 — el enrutador manda una publicación de notebook a `fuera_de_dominio`.** Con el
   modelo OpenRouter configurado, `asistente_evaltic("computadora asus, anda joya")` devolvió
   `intencion=fuera_de_dominio`, sin error ni decisión. Ese silencio no es una respuesta válida
   para un aviso del dominio. PC-61 separa el otro plano: evaluada como publicación integral, la
   misma entrada se rechaza por falta de precio/modelo y no fabrica tasación.
2. **PC-17 y PC-50 — señales de bloqueo por subcadena.** `"cuenta"` dentro de "cuenta con
   batería nueva" y `"bloqueada"` dentro de "no está bloqueada" disparan verificación pendiente
   sobre equipos limpios.
3. **PC-19 — un equipo que no prende se aprueba.** "No prende y no carga" no está en las fallas
   catastróficas ni genera reparación: el motor tasa el equipo como sano y lo compra por precio bajo.
4. **Caracterizaciones que conviene revisar con el experto:** un aviso de `$1` se aprueba
   (PC-29), el año que devuelve el LLM no se contrasta contra el texto (PC-52), el booleano de
   pantalla manda sobre el texto (PC-51), `cargador_incluido` manda sobre la lista de fallas
   (PC-41) y la RAM no informada se tasa con `CE ram_objetivo` (PC-18).

## Privacidad y ruido del motor

La salida y el error del motor se capturan y se descartan alrededor de cada llamada: el respaldo
determinístico del dictamen imprime la excepción completa, que puede contener texto del proveedor.
De la configuración solo se muestra el host de las URLs (nunca usuario, clave ni query). Los
errores se informan por clase (`ConnectionError`, `TimeoutError`, …). Un `error` devuelto por el
motor cuyo texto es un problema de base de conocimiento se trata como infraestructura, salvo que
el propio caso lo prevea; nunca se cuenta como cumplido.

## Prerrequisito del grafo

El ejecutor real necesita el catálogo PG3 cargado (`Procesador`, `Linea`, `CapacidadRAM`). Sin él
toda publicación termina en `ConocimientoFaltante` y no tiene sentido gastar tokens. `--verificar`
hace un chequeo previo —proveedor configurado, conexión a Neo4j, criterios y costos, conteos del
catálogo— y aborta con código `2` si falta algo. Estado medido después de actualizar únicamente
PG3 en la rama integrada (333 avisos de mercado):

```
Catálogo PG3: Procesador=93 (con precio=24) · Linea=46 · CapacidadRAM=11
```

La actualización se realizó después de respaldar el volumen, restaurar el dump en un destino
vacío, comprobar su consistencia y comparar el contenido restaurado con el original. No se
importó el dump versionado ni se ejecutó el reset de PG2. La carga de PG3 también borra y
reconstruye líneas y avisos: no debe confundirse con una migración puramente aditiva.

`--verificar` valida la **configuración** y el grafo, no que el proveedor remoto responda: eso solo
lo muestra una llamada real. Si falta el catálogo, el ejecutor **no** recarga nada: mirá la sección
«Carga del grafo» del README y cargá sobre una base dedicada con respaldo, porque el script de
carga del PG2 borra los datos existentes. No hay recarga automática.

## Proveedor del modelo

El corpus no depende de un proveedor: usa el LLM configurado en el `.env`. Desde la adaptación de la
capa LLM (S8) el cliente también soporta **NVIDIA Nemotron 3.5 Lightning** en
`https://integrate.api.nvidia.com/v1` con el modelo `nvidia/nemotron-3.5-lightning-30b-a3b`. Para ese
host y ese modelo exactos el cliente envía `chat_template_kwargs: {"enable_thinking": false}` y deja
`max_tokens` como lo pide cada llamador (sin piso). No es un interruptor genérico: otros modelos en ese
host y el mismo modelo en otros hosts no reciben el campo.

Esa adaptación está cubierta por 5 pruebas nuevas del cliente. La suite integrada tiene
71 pruebas offline: las 69 anteriores más 2 del contrato de la consulta de mercado. El fixture
incluye `valor_proc` y `generacion_anterior`, sin simular el fallback R2.4 ni relajar las
expectativas del corpus.
El [smoke real NVIDIA](ejecuciones/publicaciones_criticas_nvidia_smoke.log) verificó los 9 campos
esperados y una evaluación integral: 4 respuestas HTTP 200, finalización `stop` y 0 tokens de
razonamiento. La [tanda de 32 pendientes con NVIDIA](ejecuciones/publicaciones_criticas_nvidia_pendientes.log)
completó los 32 sin errores de infraestructura: 27 cumplen, 2 fallan y 3 son sondas. Los otros 29
casos se completaron con OpenRouter; no se presenta como una corrida homogénea de 61 con NVIDIA.
La evidencia original de OpenRouter se conserva tal como se registró.

### Tanda completa después de integrar las mejoras

Los **61 casos** se ejecutaron con NVIDIA sobre el PG3 actualizado: **49 cumplen, 6 no cumplen,
6 sondas y 0 errores de infraestructura reportados**, salida 1 en 7 min 12 s. Los incumplimientos
son PC-01, PC-15, PC-17, PC-19, PC-29 y PC-50. No se cambiaron sus expectativas.

Consultá el [resumen de integración](ejecuciones/publicaciones_criticas_integracion_resumen.md),
el [log completo](ejecuciones/publicaciones_criticas_integracion_nvidia.log) y la
[evidencia de actualización y respaldo](ejecuciones/integracion_neo4j_actualizacion.md).
La ejecución quedó completa; no se afirma que los 61 aprobaron ni que se corrigieron los defectos.

## Costos y límites

- Cada caso puede hacer varias llamadas al modelo: enrutador, extracción y síntesis. El enrutador
  y la extracción pueden reintentar el parseo. No se midió el total de llamadas ni tokens de esta
  tanda; los casos se ejecutan en serie, sin reintentos de transporte.
- El corpus no pretende cubrir "todas las situaciones": cubre los tipos de entrada que el usuario
  pidió, con más de un ejemplo por tipo, y 6 sondas para lo que no tiene contrato conocido.
- Las sondas dependen del modelo configurado; no se afirman resultados. Los fixtures no son
  conocimiento de producción: precios, costos, factores y umbrales reales salen del grafo.
- Las pruebas offline no demuestran el comportamiento en vivo; solo el ejecutor real contra el LLM
  y Neo4j lo hace. La corrida de integración completa está registrada arriba, con sus fallos
  y sondas explícitos; no es una certificación de todas las mejoras ni de exactitud general.
- Riesgos previstos en vivo: otros avisos vagos sin precio (PC-21, PC-24, PC-25) pueden reportar la
  misma desviación de enrutamiento que PC-01; los casos que dependen de calibración (PC-06, PC-13,
  PC-23, PC-35, PC-51, PC-53) pueden terminar en verificación pendiente; y PC-26 depende de que el
  extractor devuelva el monto escrito como "320.000 pesos".

## Archivos

| Archivo | Rol |
|---|---|
| `app/tests/casos_publicaciones.json` | Corpus y expectativas (contrato, fixtures, defectos y sondas). |
| `app/tests/test_publicaciones_criticas.py` | Pruebas offline con fronteras simuladas. |
| `app/tests/test_probar_publicaciones.py` | Pruebas del ejecutor: conteo, privacidad, `via`, expectativas. |
| `scripts/probar_publicaciones.py` | Ejecutor real, opt-in, serial, con chequeo previo; fuente única del verificador. |
| `docs/PRUEBAS_PUBLICACIONES.md` | Esta guía. |

## Resultado de la primera tanda real

Se intentaron los 61 casos: 29 completados (18 cumplidos, 8 incumplimientos originales y 3 sondas)
y 32 no completados por infraestructura/proveedor. Uno de los 8 incumplimientos era un error del
oráculo PC-16: el origen del enrutamiento debe ser una regla solo en el fixture que simula una
clasificación equivocada. Se corrigió sin repetir llamadas al proveedor.

Consultá el [resumen final con todas las tandas](ejecuciones/publicaciones_criticas_resumen.md) y
la [salida original](ejecuciones/publicaciones_criticas_openrouter.log). Después se autorizó cambiar
a NVIDIA directa y adaptar su cliente. Los 32 pendientes ya se completaron: 27 cumplen, 2 fallan,
3 sondas y 0 errores de infraestructura. Hay evidencia real para los 61 casos entre ambos
proveedores; eso **no** significa que los 61 hayan pasado ni que se haya corregido la lógica de
negocio. Los incumplimientos y límites de las sondas están registrados en el resumen.
