# EvalTIC — Proyecto Final de Inteligencia Artificial (UTN FRM, Grupo 20, 5K09)

Asistente neuro-simbólico que decide **si conviene comprar una notebook usada para reacondicionarla y
revenderla**. Sigue el patrón sándwich: LLM → base de conocimiento en Neo4j → LLM. El LLM **extrae** los
datos del aviso y **redacta** el dictamen; los precios, los costos, los umbrales y la decisión los pone el
sistema experto. Es la entrega final del PG3.

| Submódulo | Responsable | Qué hace |
|---|---|---|
| SM0 (transversal) | Grupo | Enrutado de la consulta, extracción con LLM y redacción del dictamen |
| SM1 | Álvaro Tapia | Diagnóstico técnico, plan y costo de reacondicionamiento |
| SM2 | Leonel Navarta | Valuación por componentes (VMA), riesgo de obsolescencia y demanda |
| SM3 | Luciano Romero | Decisión final: comprar, negociar, descartar o verificar |

Decisiones posibles: `Comprar`, `ComprarConOfertaMenor`, `DescartarPorInviabilidad`, `DescartarPorRiesgo`
y `VerificacionPendiente`.

```text
Aviso en lenguaje natural
  → LLM: extracción a JSON (validada contra el texto)
  → SM1: viabilidad y reacondicionamiento (cortocircuito si es inviable)
  → SM2: mercado, riesgo y demanda (reglas difusas en Cypher)
  → SM3: filtros crisp, margen requerido y conveniencia difusa
  → LLM: dictamen narrado (con respaldo determinístico)
```

## Arranque rápido (Docker)

1. Abrir Docker Desktop (WSL 2).
2. Si **no** existe `.env`, copiar `.env.example` a `.env`. Si ya existe, **no** lo pises: es configuración
   local y no se versiona.
3. **Antes de levantar**: `neo4j-init` escribe en la base y puede **borrar** datos del grafo. Usalo solo
   sobre una base **dedicada a EvalTIC** y con lo que ya tengas respaldado. Detalle y comandos:
   [Carga del grafo](#carga-del-grafo).
4. Doble clic en `levantar.bat`, o `docker compose up -d --build`.
5. Abrir http://localhost:8501 · Neo4j Browser en http://localhost:7474 (usuario `neo4j`; la clave es
   `evaltic2026` solo si no cambiaste `NEO4J_PASSWORD`).
6. Verificar con `probar.bat` (o `docker compose exec app python orquestador_evaltic.py --test`).

Los servicios `ollama` y `ollama-pull` de Compose están bajo el perfil `ollama`. Si usás un **Ollama del
host** (Windows), dejá `COMPOSE_PROFILES=` vacío y apuntá `OLLAMA_URL_DOCKER` a
`http://host.docker.internal:11434/api/generate`. Detalle completo y problemas comunes:
[LEVANTAR.md](LEVANTAR.md).

## Cómo se usa

El punto de entrada único es `asistente_evaltic` en `app/orquestador_evaltic.py`; la interfaz web
(`app/app_web.py`) lo importa y no tiene lógica de negocio propia.

| Vía | Comando |
|---|---|
| Web | http://localhost:8501 (sidebar con proveedor LLM, estado del grafo, casos precargados y pestañas por submódulo) |
| CLI, una consulta | `docker compose exec app python orquestador_evaltic.py "aviso o consulta"` |
| CLI, pruebas oficiales | `docker compose exec app python orquestador_evaltic.py --test` |

## Estructura

```text
app/orquestador_evaltic.py   motor: enrutador, SM1, SM2, SM3, pipeline y pruebas oficiales
app/app_web.py               interfaz Streamlit (solo presentación)
app/tests/                   pruebas offline de la capa LLM (sin API ni Neo4j)
cypher/Grupo_20_PG2_U1_carga.cypher       base del PG2: esquema, reglas, frames y difusa
cypher/Grupo_20_PG3_mercado.cypher        componentes, líneas, RAM, avisos, costos y criterios (incluye CE-29 v2)
cypher/Grupo_20_PG2_U1_consultas.cypher   consultas de ejemplo
datos/relevamiento_mercado.csv            333 avisos de Mercado Libre (9/11/2026), seed del PG3
scripts/cargar_grafo.sh                   carga automática usado por el contenedor neo4j-init
docs/                                     entregables PG3 y PI4 (ver docs/README.md)
odd/tasks/                                registro de la adaptación de la capa LLM
docker-compose.yml · Dockerfile · *.bat   entorno local (Neo4j + init + app + Ollama opcional)
```

## Flujo de la evaluación integral

1. **Enrutador** (`PROMPT_MAESTRO_ENRUTAMIENTO`): clasifica en `evaluacion_integral`,
   `diagnostico_tecnico` (SM1), `valuacion_comercial` (SM2) o `fuera_de_dominio`. Una consulta con precio
   siempre se fuerza a evaluación integral, aunque el LLM diga otra cosa. Si la salida del LLM no es
   válida, hay una regla de respaldo. SM1 y SM2 sueltos tienen su propio prompt de extracción, su consulta
   al grafo y su prompt de explicación.
2. **Extracción** con el LLM a un JSON con lista de `fallas`. Se valida contra el texto original: precio,
   procesador (se descartan modelos que el LLM completó y no figuran en el aviso) y año.
3. **R3.3**: señales de bloqueo en el texto → `VerificacionPendiente` (no se descarta sin verificar).
4. **SM1**: R1.1 falla catastrófica → inviabilidad (luego R3.2). Batería (SM1-BAT o R1.2), temperatura
   (SM1-TER), upgrade de RAM por debajo de `CE ram_objetivo`, HDD → SSD, pantalla/teclado/cargador y mano
   de obra. En el cargador manda el campo `cargador_incluido`: `false` cobra la reposición y `true` no la
   cobra aunque el aviso lo nombre; la falla con la frase «sin cargador» solo se usa cuando el campo viene
   `null`.
5. **SM2**: valuación por componentes en Cypher y luego riesgo/demanda difusos.
6. **SM3**: R3.7 → R3.8 → margen requerido (base, R3.4/R3.5, R3.6) → contraoferta y conveniencia difusa.
7. **Estado de la decisión** (`Firme`/`Provisional`) y dictamen final.

Cada aviso se recalcula contra la base de conocimiento: **no se reutilizan decisiones guardadas** de casos
anteriores.

## Base de conocimiento (Neo4j, obligatoria)

Sin Neo4j no hay evaluación: el sistema **no** cae a valores por defecto. Precios, costos, factores,
umbrales y catálogos se leen con Cypher; los criterios se leen con `CE()` y los costos con `costo()`, y
cada lectura queda registrada en la traza.

| Nodo | Contenido |
|---|---|
| `(:CriterioExperto)` CE-01..CE-30 | Umbrales y márgenes (`valor`, `unidad`, `version`, `estado_validacion`) |
| `(:CostoReparacion)` | Costo por tarea de SM1 |
| `(:Procesador)` | Familia y generación, año, soporte de Windows 11, valor de referencia y muestras |
| `(:Linea)` / `(:GrupoLinea)` | Factor de precio, rotación esperada e índice de repuestos |
| `(:CapacidadRAM)` | Factor de precio por capacidad (8 GB = 1,00) |
| `(:AvisoMercado)` | Avisos reales del CSV, enlazados a procesador, línea y RAM |
| `(:VariableDifusa)`, `(:ConjuntoDifuso)`, `(:ReglaDifusa)` | 5 bases Mamdani y 27 reglas |

- Las reglas difusas (SM1-BAT 5, SM1-TER 6, SM2-RIE 7, SM2-DEM 4, SM3-CONV 5) se evalúan **siempre** en
  Cypher; SM2-DEM consume el centroide continuo de riesgo, no solo su etiqueta.
- El PG3 calibra el valor del procesador y el factor de cada línea con **medianas** sobre los 333 avisos
  (sección 31 de `cypher/Grupo_20_PG3_mercado.cypher`). Si una línea tiene menos de
  `CE min_muestras_mercado` avisos, usa el factor de su grupo. Ese criterio es **CE-29 en versión v2 = 5
  avisos**: la v1 usaba 3 y la calibración guarda `valor_anterior` para la trazabilidad.
  Traer los cambios de Git no actualiza una base ya cargada: para aplicar CE-29 v2 hay que actualizar el
  PG3 siguiendo las advertencias de [Carga del grafo](#carga-del-grafo).
- Si el aviso menciona un procesador, línea o capacidad de RAM que no existe en el grafo → error
  `ConocimientoFaltante`. Si un procesador existe pero tiene menos de 5 avisos, o falta un dato para tasar
  → `VerificacionPendiente`.
- Falta de dato **no** es un estado favorable: queda pendiente y visible.
- No todo el conocimiento está en el grafo: quedan listas de palabras clave en Python (fallas
  insalvables, señales de bloqueo, términos positivos) y el armado del plan y de las fórmulas.
- Todos los criterios, costos, factores y calibraciones son **provisionales**: falta la validación con el
  experto (Matías Romero).

### Valuación y decisión en corto

```text
valor de mercado = valor del procesador × factor de línea × factor de RAM final
VMA              = valor de mercado × (1 − CE descuento_negociacion/100) + CE reval_ssd (solo si HDD → SSD)
```

La RAM final es la que queda después de los upgrades de SM1; el VMA se redondea a miles. Si el aviso no
informa la RAM, SM2 tasa con la configuración de referencia (`CE ram_objetivo`, 8 GB) y lo registra como dato
inferido, mientras SM1 la deja como pendiente: eso **no** es un error; `ConocimientoFaltante` queda para una
capacidad que el aviso menciona y no existe en `:CapacidadRAM`. Antes de buscar el `:Procesador`, el texto del
procesador se normaliza en minúsculas y se une el sufijo separado del modelo («Ryzen 5 5500 U» → «ryzen 5 5500u»); el
match sigue siendo el regex `patron` del grafo, así que no se agrega un modelo que el aviso no diga. Si el año
no está en el aviso se toma el del procesador y, si tampoco hay, la tasación queda pendiente. El soporte de
Windows 11 se resuelve aviso → procesador → año contra `CE anio_min_w11`.

Orden de SM3: R3.7 (costo de reparación / VMA sobre `CE ratio_reparacion_max`) y R3.8 (riesgo Alto con
demanda Baja) descartan antes de la conveniencia; el margen requerido se arma con la base, R3.4 o R3.5 y
R3.6; al final la difusa SM3-CONV elige entre comprar, negociar y descartar.

`Firme` exige que **todos** los criterios y costos usados estén validados y que no haya datos inferidos ni
pendientes. Como los criterios cargados son provisionales, lo habitual es `Provisional`; algunos
cortocircuitos que no usan ningún criterio pueden quedar `Firme`. Una verificación pendiente se informa
como `Pendiente`.

## Capa LLM

`consultar_llm` es un único cliente compartido con dos ramas: **Ollama** (por defecto) y cualquier API
**compatible con OpenAI** (`LLM_PROVIDER=openai`), incluida OpenRouter. En la rama compatible con OpenAI se
valida la respuesta: `choices` no vacío, `message` objeto, `content` string no blanco y rechazo de
`finish_reason=length` aunque haya llegado texto parcial. El error informa solo metadatos seguros
(motivo de finalización conocido y conteos de tokens). Nunca se usa el razonamiento como respuesta ni se
fabrica JSON.

| Etapa | Presupuesto (`max_tokens`) |
|---|---|
| Extracción integral | 1024 por intento, incluido el reintento de parseo |
| Síntesis del dictamen | 768 |
| Enrutador y extracciones SM1/SM2 | 220 por intento (con el reintento de parseo existente) |
| Explicaciones de SM1/SM2 | 220 |
| Llamada directa al cliente | 300 por defecto |

- **Piso de OpenRouter**: si el host es `openrouter.ai`, el pedido se eleva a 4096 y se conservan los
  pedidos mayores. Es un techo de generación, no un consumo fijo. No altera a otros proveedores ni a
  Ollama.
- **Razonamiento**: `reasoning.enabled=false` se envía **solo** con host `openrouter.ai` y modelo exacto
  `nvidia/nemotron-3.5-lightning:free`. No hay un interruptor genérico ni variables por etapa.
- **Razonamiento en NVIDIA**: `chat_template_kwargs.enable_thinking=false` se envía **solo** con host exacto
  `integrate.api.nvidia.com` y modelo exacto `nvidia/nemotron-3.5-lightning-30b-a3b`. Es el mismo apagado
  real, en el campo que expone la plantilla de chat de NVIDIA, y el id de modelo es distinto del de
  OpenRouter. No aplica piso de tokens: el presupuesto del llamador se envía sin cambios (220, 300, 768,
  1024 o el que pida). Un host parecido (`api.nvidia.com`, subdominios o sufijos engañosos) no lo activa.
  La validación de respuesta sigue rechazando `finish_reason=length` y `content` nulo.
- No se agregan reintentos de transporte ni fallback a modelos pagos.
- La rama de Ollama conserva su extracción previa de la respuesta: **no** tiene el mismo validador
  estructural.
- Los errores HTTP distintos de 200 todavía incluyen `resp.text` en el mensaje; no se afirma que todo el
  cliente sanee cualquier error. Un 429 en modelos gratuitos suele ser saturación del pool del proveedor.
- **Control anti-alucinación**: los números de dos o más cifras que usa el LLM al redactar deben existir en
  el resultado consolidado. Si no, se descarta el texto y se usa el respaldo determinístico (se avisa por
  consola con `[Aviso Síntesis LLM]`). Es una guarda numérica, no una garantía semántica completa.
- Cambiar `.env` o el código Python exige reiniciar la app: la configuración se lee al arrancar.

## Pruebas

| Qué | Comando | Requiere servicios |
|---|---|---|
| Offline (cliente LLM y publicaciones, 71 tests) | `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s app/tests -v` | No |
| Oficiales (5 casos integrales + 4 de enrutador) | `probar.bat` o `docker compose exec app python orquestador_evaltic.py --test` | Sí: Neo4j cargado y LLM disponible |

Las pruebas oficiales comparan la decisión calculada con la esperada e informan el enrutamiento correcto.
Las salidas reales de corridas anteriores están en `docs/ejecuciones/`. Este README **no** documenta una
corrida end-to-end nueva: los números de precisión de los informes (error mediano 14,9 % y 67,7 % de las
estimaciones dentro de ±25 %, medidos sobre 217 avisos tasables con CE-29 = 5) son observaciones sobre los
mismos avisos usados para calibrar, no una validación independiente.

El caso integral 4 usa «Core i5» sin generación: `Core i5 7ma gen` registra 4 avisos relevados y con CE-29 = 5
no recibe valor de referencia, así que quedaría `VerificacionPendiente` en lugar de descartarse por riesgo.

## Configuración (`.env`)

El archivo no se versiona (`.env.example` sí). Orden de búsqueda, sin `override` (las variables ya
exportadas en la terminal tienen prioridad):

| Orden | Archivo |
|---|---|
| 1 | `app/.env` |
| 2 | `.env` de la raíz del repositorio |
| 3 | `PI4/.env` (fallback histórico) |
| 4 | Búsqueda preexistente de `python-dotenv` |

Variables principales: `LLM_PROVIDER`, `OLLAMA_*`, `OPENAI_*` (clave, base URL y modelo) y
`NEO4J_TARGET` con su bloque `NEO4J_LOCAL_*` o `NEO4J_REMOTE_*`. Después de cualquier cambio hay que recrear
la app: en local, reiniciarla; en Docker, `docker compose up -d --force-recreate --no-deps app` (ver
[Cambios de código y configuración](#cambios-de-codigo-y-configuracion)). Los ejemplos de OpenRouter y Groq,
con valores ficticios reemplazables, están en [LEVANTAR.md](LEVANTAR.md).

<a id="carga-del-grafo"></a>

## Carga del grafo: leé esto antes de recargar

`cypher/Grupo_20_PG2_U1_carga.cypher` **borra todo**: empieza con `MATCH (n) DETACH DELETE n`.

- `neo4j-init` ejecuta el PG2 solo si el contador de `:ReglaDifusa` es 0 o si pasás `RECARGAR=1`. Ese
  chequeo detecta “base sin reglas”, no “base vacía”: puede ejecutarse sobre una base con otros datos y
  borrarlos aunque `RECARGAR` esté en 0.
- El PG3 se ejecuta **siempre** y tampoco es inocuo:
  - elimina el catálogo viejo (`SegmentoMercado`, `ModeloReferencia`, `GeneracionProcesador`);
  - **borra todas las `Linea`** y las reconstruye desde el catálogo de líneas escrito en el propio script
    `.cypher` (no desde el CSV);
  - **borra todos los `AvisoMercado`** y los recarga desde `datos/relevamiento_mercado.csv`.

  Usa `MERGE` para no duplicar nodos, pero no es puramente aditivo: no hay recarga “idempotente” sin
  borrados.
- Por eso: cargá solo sobre una base **dedicada a EvalTIC**, con respaldo previo. No la apuntes a una base
  compartida.
- `docker compose up -d neo4j` levanta la base **sin** cargar datos; los datos los carga `neo4j-init`.

### Actualizar el grafo (sin reset total)

Con el PG2 **ya cargado** en la base dedicada y un cambio en el PG3 o en el CSV, la recarga normal es:

```bash
docker compose run --rm -e RECARGAR=0 neo4j-init
```

Sigue escribiendo: reconstruye las líneas y los avisos de mercado. Y si la base no tuviera `:ReglaDifusa`,
igual dispara el PG2 destructivo. Por eso **no es seguro** sobre un grafo ajeno.

### Reset total (solo intencional)

`RECARGAR=1` (o `actualizar.bat`) fuerza **PG2 + PG3**: equivale a borrar el grafo completo y volver a
cargarlo. Usalo solo si es eso lo que querés, con respaldo y sobre la base dedicada; nunca como paso normal
de actualización.

<a id="cambios-de-codigo-y-configuracion"></a>

### Cambios de código y configuración

| Cambio | Qué hacer | ¿Recarga el grafo? |
|---|---|---|
| Python (Docker) | `docker compose up -d --build --no-deps app` | No |
| Python (venv local) | Reiniciar Streamlit | No |
| `.env` (venv local) | Reiniciar Streamlit | No |
| `.env` del contenedor | `docker compose up -d --force-recreate --no-deps app` | No |
| PG3 (`Grupo_20_PG3_mercado.cypher`) o CSV | Recarga normal de la sección anterior | Sí |
| PG2 (`Grupo_20_PG2_U1_carga.cypher`) | Reset total intencional, con respaldo; no usar la recarga normal para aplicar sus cambios | Sí, borra todo |

El `Dockerfile` hace `COPY app/ .` y **no** hay volumen de código: un cambio de Python dentro del contenedor
exige reconstruir la imagen. `--no-deps` evita que se vuelva a ejecutar el inicializador (y el borrado del
grafo). Para cambios de configuración de otro servicio, recreá ese servicio con `--no-deps` en lugar de
levantar todo el stack.

## Local en Linux (app fuera de Docker)

Esta es la configuración con la que el grupo ejecuta la app en esta máquina; es opcional y no una ruta
universal. Reutiliza el entorno virtual que ya tiene las dependencias: no hace falta crear otro ni ejecutar
`pip install`. Si no lo tenés, creá un virtualenv propio e instalá `app/requirements.txt`.

```bash
cd /home/alvaro/Universidad/IA/Proyecto-IA-Final
/home/alvaro/Universidad/IA/Proyecto/.venv/bin/python -m streamlit run app/app_web.py --server.address 127.0.0.1
```

Reutilizar el intérprete **no** reutiliza el código ni el `.env` del proyecto anterior: se ejecuta el
`app/app_web.py` de este repositorio y su propia configuración. Neo4j tiene que estar disponible antes de
abrir la app. Más detalle en [LEVANTAR.md](LEVANTAR.md).

## Entregables

Informe del PG3, infografía, los tres PI4, diagramas, salidas de ejecución y export de Neo4j:
[docs/README.md](docs/README.md).

## Cambios recientes de la calibración

Ajustes posteriores a la primera calibración; las salidas y tablas completas están en
`docs/ejecuciones/` y en `docs/fuentes_html/Grupo_20_PG3_ProyectoFinal.html`.

| Cambio | Efecto |
|---|---|
| CE-29 a 5 avisos (v2) | Un procesador con menos de 5 avisos no recibe valor de referencia y la evaluación queda `VerificacionPendiente`; una línea con menos de 5 avisos usa el factor de su grupo. Reduce la dependencia de muestras escasas; no elimina toda sensibilidad a valores atípicos. |
| Sufijo del procesador separado | El procesador se normaliza antes del match («Ryzen 5 5500 U» → «ryzen 5 5500u»), permitiendo reconocer el sufijo separado sin cambiar el catálogo ni descartar el resto del texto. |
| Cargador | `cargador_incluido` manda: `false` cobra la reposición, `true` no la cobra y la frase «sin cargador» solo cuenta si el campo viene `null`. No toda mención al cargador se trata igual. |
| RAM leída del texto | Si el LLM no devuelve `ram_gb`, la evaluación integral la busca en el aviso («8GB de RAM», «memoria 8GB», «16 gb ram») antes de seguir; si tampoco aparece, SM2 tasa con 8 GB de referencia y lo marca como inferido. |

## Estado y pendientes

- [x] Evaluación integral, enrutador y submódulos sueltos funcionando contra Neo4j real, según las corridas
      registradas en `docs/ejecuciones/` (este README no ejecuta una corrida E2E nueva).
- [x] Valuación por componentes con calibración por medianas sobre los 333 avisos (sección 31 del PG3;
      valores provisionales), con 217 avisos tasables con CE-29 = 5.
- [x] Capa LLM adaptada: presupuestos por etapa, validación de respuestas y razonamiento desactivado para
      el modelo verificado en OpenRouter y para NVIDIA Lightning en su propio host; 34 pruebas del cliente
      dentro de las 71 pruebas offline de `app/tests/`.
- [ ] Validación de criterios, costos y factores con el experto (todo sigue `Provisional`).
- [ ] R1.4 (RAM soldada sin expansión) como limitación `NoAmpliable` y R3.1b (rechazo comercial directo).
- [ ] Pasar al grafo las listas de palabras clave que todavía viven en Python.
- [ ] `qwen2.5:1.5b` extrae mal a veces (completa procesadores o cuela aspectos positivos en `fallas`);
      alternativa: un modelo más grande por API.

---

Nota de procedencia: este README se consolidó a partir de la exploración del repositorio actual y de las
notas locales `CONTEXTO_Y_MEJORAS_EVALTIC.md` (no versionado, con la historia de otra copia del proyecto).
Cuando el código y esas notas difieren, manda el código de este repositorio.
