# EvalTIC en local con Docker — Grupo 20

## Qué se levanta

| Contenedor | Para qué | URL |
|---|---|---|
| `neo4j-evaltic` | Grafo de conocimiento (Neo4j 5 Community) | http://localhost:7474 (neo4j / evaltic2026) |
| `evaltic-neo4j-init` | Corre `cypher/Grupo_20_PG2_U1_carga.cypher` la primera vez y se apaga | — |
| `evaltic-ollama` + `evaltic-ollama-pull` | LLM local (qwen2.5:1.5b); el segundo baja el modelo y se apaga | http://localhost:11434 |
| `evaltic-app` | Interfaz Streamlit (`app_web.py` + `orquestador_evaltic.py`) | http://localhost:8501 |

## Requisitos (una sola vez)

1. **Docker Desktop para Windows** con WSL 2 activado (https://www.docker.com/products/docker-desktop/).
2. Unos 4 GB de RAM libres y 4 GB de disco (Neo4j ~600 MB, Ollama + modelo ~2,5 GB, app ~500 MB).

## Levantarlo

Doble clic en **`levantar.bat`**, o desde una terminal en esta carpeta:

```
docker compose up -d --build
```

La primera vez tarda varios minutos (baja imágenes y el modelo). Para seguir el avance:

```
docker compose ps
docker logs -f evaltic-neo4j-init     # carga del grafo
docker logs -f evaltic-ollama-pull    # descarga del modelo
docker logs -f evaltic-app            # la app
```

Después abrir http://localhost:8501.

## Local en Linux (app fuera de Docker)

Si ya tenés el entorno virtual del proyecto con todas las dependencias instaladas, reutilizá ese
intérprete: no hay que crear otro entorno ni ejecutar `pip install`.

| Dato | Valor |
|---|---|
| Intérprete | `/home/alvaro/Universidad/IA/Proyecto/.venv/bin/python` |
| Repositorio que se ejecuta | `/home/alvaro/Universidad/IA/Proyecto-IA-Final` |

```
cd /home/alvaro/Universidad/IA/Proyecto-IA-Final
/home/alvaro/Universidad/IA/Proyecto/.venv/bin/python -m streamlit run app/app_web.py
```

Reutilizar el intérprete **no** reutiliza el código ni el `.env` del proyecto anterior: se ejecuta el
`app/app_web.py` de **este** repositorio y la configuración se lee de su `.env` (ver abajo). Neo4j
tiene que estar disponible antes de abrir la app; la app no levanta la base por su cuenta.

### Qué archivo `.env` se usa

| Orden | Archivo | Nota |
|---|---|---|
| 1 | `app/.env` | Tiene prioridad si existe |
| 2 | `.env` de la raíz del repositorio | Es el que se usa hoy en este repo |
| 3 | `PI4/.env` | Fallback histórico; no hace falta en este repositorio |
| 4 | Búsqueda de `python-dotenv` | Solo si ninguno de los anteriores existe |

La carga no usa `override`: las variables ya exportadas en la terminal tienen prioridad sobre el
archivo. El `.env` no se versiona y no hace falta mostrarlo para trabajar.

## Scripts

| Archivo | Qué hace |
|---|---|
| `levantar.bat` | Levanta todo |
| `probar.bat` | Corre los 5 casos oficiales (`orquestador_evaltic.py --test`) |
| `recargar_grafo.bat` | Borra el grafo y vuelve a correr el `.cypher` (usar cada vez que cambien el script de carga) |
| `detener.bat` | Apaga todo (los datos quedan guardados) |

## Usar otro LLM en lugar de Ollama

`qwen2.5:1.5b` es chico: corre en cualquier PC, pero a veces extrae mal el JSON del aviso. Para usar una API (por ejemplo Groq, que tiene plan gratis), editar `.env`:

```
COMPOSE_PROFILES=
LLM_PROVIDER=openai
OPENAI_API_KEY=tu_clave
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=llama-3.1-8b-instant
```

Si ya tienen Ollama instalado en Windows: `COMPOSE_PROFILES=` y `OLLAMA_URL_DOCKER=http://host.docker.internal:11434/api/generate`.

Después de cambiar `.env`: `docker compose up -d`.

### OpenRouter

`openai` identifica el **protocolo** compatible, no el proveedor de facturación. Para OpenRouter,
editar `.env` con valores ficticios reemplazables:

```env
LLM_PROVIDER=openai
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=TU_CLAVE_DE_OPENROUTER
OPENAI_MODEL=nvidia/nemotron-3.5-lightning:free
```

Presupuestos y razonamiento implementados en el cliente compartido:

| Tema | Comportamiento |
|---|---|
| Extracción | 1024 tokens por intento, incluido el reintento de parseo |
| Síntesis | 768 tokens |
| Piso de OpenRouter | 4096 tokens para cualquier llamada a `openrouter.ai`; se conservan los pedidos mayores |
| Razonamiento | `reasoning.enabled=false` solo con host `openrouter.ai` y modelo exacto `nvidia/nemotron-3.5-lightning:free` |
| Otros modelos y proveedores | Reciben los presupuestos de etapa (1024 extracción / 768 síntesis) o el límite explícito del llamador; no se les aplica el piso 4096 ni el override de razonamiento |

- El piso es un techo de generación, no un consumo fijo; el razonamiento cuenta dentro del mismo límite.
- Si la respuesta se corta (`finish_reason=length`) la llamada falla con un error que informa solo
  metadatos seguros. No se usa texto parcial, no se fabrica JSON y no se usa el razonamiento como salida.
- La síntesis tiene respaldo determinístico: si el LLM falla, el dictamen se arma con los datos del
  grafo y se avisa por consola con un `[Aviso Síntesis LLM]`.
- Reiniciar la app después de cambiar `.env` o el código Python: la configuración se lee al arrancar.
- Un **429** en modelos gratuitos suele ser saturación del proveedor upstream (pool compartido), no una
  clave inválida ni un problema de Neo4j. No hay reintentos automáticos ni fallback pago.
- No se afirma disponibilidad actual del modelo ni razonamiento en cero: eso depende del proveedor y
  solo se comprueba con una llamada real.

## Desarrollo (cambiar el código)

El código está en `app/`. Después de editarlo: `docker compose up -d --build app`.
Los cambios **solo de Python** no requieren recargar el grafo: alcanza con reiniciar la app. El grafo
solo se recarga cuando cambia un script `.cypher`.
También se puede correr fuera de Docker con Neo4j en el contenedor (el puerto 7687 queda publicado):

```
cd app
pip install -r requirements.txt
python orquestador_evaltic.py --test
```

Si usás el intérprete del entorno virtual que ya tenés (ver “Local en Linux”), ese `pip install` no es
necesario: las dependencias ya están instaladas.

## Problemas comunes

- **"No se pudo conectar a la base de conocimiento"**: Neo4j todavía arranca o falló la carga → `docker logs evaltic-neo4j-init`.
- **"No se pudo conectar con Ollama"**: el modelo todavía se descarga → `docker logs -f evaltic-ollama-pull`.
- **Puerto ocupado (7474, 7687, 8501 u 11434)**: hay otro Neo4j u Ollama corriendo; cerrarlo o cambiar el puerto de la izquierda en `docker-compose.yml`.
