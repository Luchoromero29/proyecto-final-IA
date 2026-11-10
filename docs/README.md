# EvalTIC — Carpeta de entrega (PG3 y PI4)

**Grupo 20 — Inteligencia Artificial 5K09 — UTN FRM — 2026**
Álvaro Tapia (SM1) · Leonel Navarta (SM2) · Luciano Romero (SM3)

## Documentación
| Archivo | Qué es |
|---|---|
| `Grupo_20_PG3_ProyectoFinal.pdf` | Informe ejecutivo final del PG3 (arquitectura, base de conocimiento, casos de uso, pruebas, evaluación, trazabilidad, manual de uso en el anexo) |
| `Grupo_20_PG3_Infografia.pdf` | Infografía / resumen ejecutivo de una página |
| `PI4/Tapia_Alvaro_PI4_U4.pdf` | PI4 de SM1 (diagnóstico técnico) |
| `PI4/Navarta_Leonel_PI4_U4.pdf` | PI4 de SM2 (valuación por componentes) |
| `PI4/Romero_Luciano_PI4_U4.pdf` | PI4 de SM3 (decisión y orquestación) |
| `diagramas/` | Arquitectura y modelo del grafo (SVG) |
| `ejecuciones/` | Salidas reales de terminal: casos integrales, SM1, SM2 y entradas con error |
| `neo4j/neo4j.dump` | Exportación de la base Neo4j 5.26 (`neo4j-admin database load neo4j --from-path=docs/neo4j`) |
| `fuentes_html/` | Fuentes editables de los informes (se convierten a PDF con Edge/Chrome) |

## Implementación (raíz del repositorio)
- `app/` — código Python (`orquestador_evaltic.py`, `app_web.py`) y `requirements.txt`.
- `cypher/` — scripts de carga (PG2 y PG3) y consultas de ejemplo.
- `datos/relevamiento_mercado.csv` — 289 avisos de Mercado Libre (9/11/2026), seed de la base.
- `docker-compose.yml`, `Dockerfile`, `.env.example`, `*.bat`, `scripts/` — configuración y arranque.

## Uso rápido
```
docker compose up -d --build                                  # levanta Neo4j, carga el grafo y la app
docker compose exec app python orquestador_evaltic.py --test  # 5 casos integrales + enrutador
```
App: http://localhost:8501 · Neo4j Browser: http://localhost:7474 (neo4j / evaltic2026).
Requiere Ollama con `qwen2.5:1.5b` corriendo en la máquina (ver `LEVANTAR.md`).

## Casos de prueba integrales (resultados del 9/11/2026)
| Caso | Decisión |
|---|---|
| 1 · Acer Aspire 5 i5 10ma gen, $350.000, 4 reparaciones | Comprar con oferta menor |
| 2 · ThinkPad T490 i5 8va gen 16 GB, $400.000 | Comprar |
| 3 · Dell Inspiron 15 con CPU quemada | Descartar por inviabilidad |
| 4 · ThinkPad T470 i5 7ma gen sin W11, $300.000 | Descartar por riesgo (R3.8) |
| 5 · HP 15 Ryzen 3 2021, $220.000 | Comprar |
