# CLAUDE.md — Contexto del proyecto EvalTIC

## Qué es
Proyecto final (PG3) de **Inteligencia Artificial, UTN FRM, comisión 5K09, Grupo 20**.
**EvalTIC** es un asistente neuro-simbólico ("patrón sándwich") que evalúa si conviene comprar una
notebook usada para reventa: LLM (enruta, lee el aviso y redacta) → base de conocimiento en **Neo4j**
(reglas crisp, lógica difusa Mamdani, criterios expertos, catálogo de componentes calibrado con avisos
reales, costos) → LLM.

| Submódulo | Responsable | Qué hace |
|---|---|---|
| SM0 | Grupo | Enrutador (System Prompt maestro), extracción con LLM y redacción del dictamen |
| SM1 | Álvaro Tapia | Diagnóstico técnico, plan y costo de reacondicionamiento |
| SM2 | Leonel Navarta | Valuación por componentes (VMA), riesgo de obsolescencia y demanda |
| SM3 | Luciano Romero (dueño del repo) | Decisión: Comprar / ComprarConOfertaMenor / Descartar / VerificacionPendiente |

## Estructura
```
app/orquestador_evaltic.py   enrutador, adaptadores SM1/SM2/SM3, pipeline y pruebas
app/inferencia_sm1.py        resolución técnica explícita en Cypher
app/inferencia_sm3.py        política financiera y cuantización explícitas en Cypher
app/app_web.py               interfaz Streamlit (usa asistente_evaltic)
app/requirements.txt
cypher/Grupo_20_PG2_U1_carga.cypher      base del PG2 (bloques 0–20; el bloque 0 BORRA todo)
cypher/Grupo_20_PG3_mercado.cypher       componentes, líneas, RAM, avisos, costos y criterios (idempotente)
cypher/Grupo_20_PG2_U1_consultas.cypher  consultas de ejemplo
datos/relevamiento_mercado.csv           333 avisos de Mercado Libre (9 y 10/11/2026); seed que carga el PG3 con LOAD CSV
scripts/cargar_grafo.sh      lo ejecuta el contenedor neo4j-init (LF obligatorio)
docker-compose.yml, Dockerfile, *.bat, LEVANTAR.md, docs/ (informes)
```

## Entorno de Luciano (Windows)
- Docker Desktop. Servicios: `neo4j-evaltic` (Neo4j 5.26 community, 7474/7687, neo4j/evaltic2026; monta
  `./datos` en `/var/lib/neo4j/import` para el LOAD CSV, sin `:ro` porque la imagen hace chown),
  `evaltic-neo4j-init` (carga PG2 si la base está vacía y SIEMPRE el script PG3), `evaltic-app` (8501).
- **Ollama instalado en Windows** con `qwen2.5:1.5b` (`ollama serve` tiene que estar corriendo). En `.env`:
  `COMPOSE_PROFILES=` (vacío) y `OLLAMA_URL_DOCKER=http://host.docker.internal:11434/api/generate`.
- `.env` NO se versiona; `.env.example` sí.
- Comandos: `levantar.bat`, `actualizar.bat` (recarga grafo + rebuild), `probar.bat` (`--test`), `detener.bat`.
  Equivalentes: `docker compose up -d --build`, `docker compose run --rm -e RECARGAR=1 neo4j-init`,
  `docker compose exec app python orquestador_evaltic.py "consulta o aviso"`.
- Git: remoto `git@github.com:Luchoromero29/proyecto-final-IA.git`, rama `main`. Luciano hace push con su SSH.
- Al escribir código con barras invertidas (regex) desde la herramienta Bash, las `\\` se colapsan:
  usar Write/Edit para esas líneas.

## Principio central (lo pidió la cátedra)
**Ningún precio, costo ni umbral escrito en Python.** Todo se lee de Neo4j, y si el aviso menciona algo que
no está en el grafo, la evaluación da **error** (`ConocimientoFaltante`), no un valor por defecto.
- `(:CriterioExperto {nombre, valor, unidad, version, estado_validacion})`: CE-01..CE-30 en PG3 mercado;
  CE-31/32 Provisionales en el seed diagnóstico B2. Se consultan desde las reglas de Cypher;
  `CE()` conserva el acceso de los adaptadores.
  CE-21..26 y reval_ram quedaron con `en_uso=false` (los reemplazó la valuación por componentes).
- `(:CostoReparacion {tarea, costo_ars})`, leídos con `costo()`.
- `(:Procesador {nombre, familia, gama, anio, soporte_w11, patron, prioridad, valor_ref_ars, n_muestras})`:
  familia + generación (Core i3/i5/i7 2da–14va, Ryzen 3000–7035, Apple M1–M3, Celeron/N100, etc.) y nodos
  "familia sola" sin año. `patron` = regex Java sobre el procesador que extrae el LLM.
- `(:Linea {nombre, marca, patron, prioridad, factor_precio, origen_factor})-[:PERTENECE_A_GRUPO]->(:GrupoLinea
  {dias_promedio_venta, indice_repuestos})`. Grupos: Corporativa, Consumo, Gamer, Premium, Nacional/genérica.
- `(:CapacidadRAM {gb, factor})` (8 GB = 1,00).
- `(:AvisoMercado)` cargados del CSV, con `TIENE_PROCESADOR`, `DE_LINEA`, `TIENE_RAM`. La sección 31 del PG3
  calibra con medianas: valor del procesador y factor de cada línea (si la línea tiene < CE-29 = 5 avisos, usa el
  de su grupo). Procesador con < CE-29 avisos → sin `valor_ref_ars` → **R2.4** (`(:Regla)` en el PG3): toma el valor
  de la generación anterior más cercana de la misma familia con datos (dato inferido, supuesto conservador);
  si no hay, verificación pendiente. Las series Ryzen tienen el sufijo U/H opcional y existen 7040/7045/8040.
- Reglas difusas `(:ReglaDifusa {base})`: SM1-BAT, SM1-TER, SM2-RIE, SM2-DEM, SM3-CONV (Mamdani en Cypher).
Todos los valores son PROVISIONALES (falta la entrevista con el experto Matías Romero).

## Flujo (`asistente_evaltic` → enrutador)
0. **Enrutador** (`PROMPT_MAESTRO_ENRUTAMIENTO`): evaluacion_integral / diagnostico_tecnico (SM1) /
   valuacion_comercial (SM2) / fuera_de_dominio. Un mensaje con precio siempre va a la evaluación integral.
   SM1 y SM2 sueltos tienen su prompt de extracción y de explicación (`consultar_sm1`, `consultar_sm2`).
Evaluación integral (`evaluar_publicacion_integral`):
1. `extraer_datos_llm` (JSON con lista `fallas`). Validaciones contra el texto: precio, procesador (descarta
   modelos que el LLM completa) y año.
2. **R3.3**: señales de bloqueo → `VerificacionPendiente`.
3. **SM1**: resolución completa en Cypher (`consultar_resolucion_sm1`). Síntoma sin diagnóstico →
   `VerificacionPendiente` R3.3c; sólo la evidencia separada del operador puede liberar la guarda.
   Diagnóstico reparable sin costo conocido → `ConocimientoFaltante`; costo conocido en cero no es ausencia.
   R1.1 falla catastrófica → inviable (→ R3.2). Batería SM1-BAT / R1.2, temperatura SM1-TER, RAM <
   CE ram_objetivo, HDD→SSD, pantalla/teclado (booleans o fallas no redactadas en positivo), cargador, mano de obra.
4. **SM2** (`inferir_valuacion_sm2_cypher`; wrapper compatible `consultar_mercado_componentes`, Cypher): VMA = valor del procesador × factor de línea × factor de
   la RAM final (después de upgrades) × (1 − CE descuento_negociacion) + CE reval_ssd si HDD→SSD.
   Año: aviso → procesador (inferido) → pendiente. W11: aviso → procesador → año. Riesgo SM2-RIE (antigüedad,
   repuestos del grupo, W11) → demanda SM2-DEM (rotación del grupo).
5. **SM3**: R3.7 ratio > CE ratio_reparacion_max; R3.8 riesgo Alto + demanda Baja; margen requerido base →
   R3.4 o R3.5 → R3.6; contraoferta; conveniencia difusa SM3-CONV.
6. Firme/Provisional (`_estado_decision`) y dictamen con LLM (respaldo determinístico).

## Devoluciones de la cátedra a respetar
- Los umbrales no van escritos en las reglas: se referencian instancias de CriterioExperto.
- Margen requerido con política de combinación explícita (base → R3.4 o R3.5 → R3.6).
- Falta de dato ≠ estado favorable: queda PENDIENTE (y lo que no existe en el grafo da error).
- Texto sospechoso de bloqueo → verificación pendiente, no bloqueo confirmado.
- R1.4 (RAM soldada) NO es inviabilidad física: limitación `NoAmpliable` (pendiente).
- Mantener visible el estado de validación hasta la salida final.
- Lógica difusa solo para conceptos graduales.
- PG3: System Prompt maestro que enrute, interfaz unificada y pruebas que crucen submódulos.

## Estado del proyecto
- [x] Probado contra Neo4j real. `--test`: 5/5 casos integrales + 4/4 enrutador.
- [x] Valuación por componentes calibrada con 333 avisos; error mediano 14,7 % contra el precio publicado
      (66,2 % dentro de ±25 %, CE-29 = 5; medido sobre los mismos datos de la calibración).
- [x] Se quitó el atajo de Leonel que devolvía decisiones guardadas de casos del PG2 (matcheaba mal: HP 15 → Dell Inspiron 15).
- [ ] Entregables: PI4 de cada integrante y PG3 (informe PDF, diagramas, zip con export de Neo4j, video/infografía).
- [ ] R1.4 `NoAmpliable`; R3.1b rechazo comercial directo.
- [x] B2 técnico: síntomas/diagnóstico, fallas→tareas, valuación y decisión en Cypher; verificación independiente y 184 pruebas en Neo4j aislado.
- [ ] B2 despliegue (T2P): vía segura para aplicar sólo el seed aditivo a la base original y repetir 61 publicaciones reales.
- [ ] B3: interpretar señales de bloqueo por contexto; no confundirlo con el diagnóstico B2.
- [ ] qwen2.5:1.5b extrae mal a veces (completa procesadores, mete positivos en fallas); alternativa: Groq.

## Migración B2

El seed `cypher/Grupo_20_PG3_diagnostico.cypher` es aditivo e idempotente y se verificó en el
grafo aislado. El loader completo **no es una migración aditiva**: corre primero el refresco del
mercado. No usar una recarga completa para aplicar sólo B2 sobre datos de trabajo. Ese paso
sigue pendiente de un procedimiento seguro del operador; ver `docs/DIAGNOSTICO_TECNICO.md`.
La verificación independiente final de RIE→DEM dio PASS (184 pruebas con grafo, sin omisiones).
Eso completa el cierre técnico del código, no una corrida real nueva de las 61 publicaciones.
La evidencia, los intentos fallidos preservados y las limitaciones están en
`docs/ejecuciones/mejoras_b2_cierre.md`. No hay aprobación nativa de revisión ni push/PR.

## Convenciones
- Todo en español (código, comentarios, UI, commits).
- `scripts/*.sh` y `*.csv` con LF (`.gitattributes`); `.bat` con CRLF.
- No commitear `.env`, `_respaldo_original/` ni zips.
- Después de cambiar Python: `docker compose up -d --build app`. Después de cambiar un `.cypher` o el CSV:
  `docker compose run --rm neo4j-init`.
- Luciano prefiere respuestas cortas y prácticas y que se cumpla la consigna sin sobredimensionar.
