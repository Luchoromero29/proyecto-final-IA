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

## Desarrollo (cambiar el código)

El código está en `app/`. Después de editarlo: `docker compose up -d --build app`.
También se puede correr fuera de Docker con Neo4j en el contenedor (el puerto 7687 queda publicado):

```
cd app
pip install -r requirements.txt
python orquestador_evaltic.py --test
```

## Problemas comunes

- **"No se pudo conectar a la base de conocimiento"**: Neo4j todavía arranca o falló la carga → `docker logs evaltic-neo4j-init`.
- **"No se pudo conectar con Ollama"**: el modelo todavía se descarga → `docker logs -f evaltic-ollama-pull`.
- **Puerto ocupado (7474, 7687, 8501 u 11434)**: hay otro Neo4j u Ollama corriendo; cerrarlo o cambiar el puerto de la izquierda en `docker-compose.yml`.
