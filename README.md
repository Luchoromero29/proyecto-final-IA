# EvalTIC — Proyecto Final de Inteligencia Artificial (UTN FRM, Grupo 20, 5K09)

Asistente neuro-simbólico para evaluar la compra de notebooks usadas para reventa.
Combina un LLM (lectura del aviso y redacción del dictamen), un grafo de conocimiento
en Neo4j (reglas crisp, lógica difusa Mamdani, criterios expertos, catálogo de mercado
y costos) y una interfaz web en Streamlit.

| Submódulo | Responsable | Qué hace |
|---|---|---|
| SM1 | Álvaro Tapia | Diagnóstico técnico y plan de reacondicionamiento |
| SM2 | Leonel Navarta | Valuación comercial, obsolescencia y demanda |
| SM3 | Luciano Romero | Evaluación de la operación y decisión (comprar / negociar / descartar) |

## Estructura

```
app/        orquestador_evaltic.py (motor) y app_web.py (Streamlit)
cypher/     Grupo_20_PG2_U1_carga.cypher   base de conocimiento del PG2
            Grupo_20_PG3_mercado.cypher    catálogo de mercado, costos y criterios v2
            Grupo_20_PG2_U1_consultas.cypher
scripts/    cargar_grafo.sh (carga automática del grafo en Docker)
docs/       informe del PG3
```

## Levantarlo

Ver [LEVANTAR.md](LEVANTAR.md). En resumen: Docker Desktop abierto, copiar `.env.example`
a `.env` y ejecutar `levantar.bat` (o `docker compose up -d --build`).
App en http://localhost:8501 · Neo4j Browser en http://localhost:7474.
