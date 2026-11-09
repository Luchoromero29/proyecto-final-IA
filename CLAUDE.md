# CLAUDE.md — Contexto del proyecto EvalTIC

## Qué es
Proyecto final (PG3) de **Inteligencia Artificial, UTN FRM, comisión 5K09, Grupo 20**.
**EvalTIC** es un asistente neuro-simbólico ("patrón sándwich") que evalúa si conviene comprar una
notebook usada para reventa: LLM (lee el aviso y redacta el dictamen) → base de conocimiento en
**Neo4j** (reglas crisp, lógica difusa Mamdani, criterios expertos, catálogo de mercado, costos) → LLM.

| Submódulo | Responsable | Qué hace |
|---|---|---|
| SM0 | Grupo | Ingesta con LLM (extracción JSON del aviso) y redacción del dictamen |
| SM1 | Álvaro Tapia | Diagnóstico técnico, plan y costo de reacondicionamiento |
| SM2 | Leonel Navarta | Valuación (VMA), riesgo de obsolescencia y demanda |
| SM3 | Luciano Romero (dueño del repo) | Decisión: Comprar / ComprarConOfertaMenor / Descartar / VerificacionPendiente |

Antes de tocar SM2 en profundidad conviene consultarlo con Leonel; SM1 con Álvaro.

## Estructura
```
app/orquestador_evaltic.py   motor completo (SM1, SM2, SM3, pipeline, pruebas)
app/app_web.py               interfaz Streamlit
app/requirements.txt
cypher/Grupo_20_PG2_U1_carga.cypher      base del PG2 (bloques 0–20; el bloque 0 BORRA todo)
cypher/Grupo_20_PG3_mercado.cypher       catálogo de mercado, costos y criterios v2 (idempotente, MERGE)
cypher/Grupo_20_PG2_U1_consultas.cypher  consultas de ejemplo
scripts/cargar_grafo.sh      lo ejecuta el contenedor neo4j-init (LF obligatorio)
docker-compose.yml, Dockerfile, *.bat, LEVANTAR.md, docs/ (informe PG3)
```

## Entorno de Luciano (Windows)
- Docker Desktop. Servicios: `neo4j-evaltic` (Neo4j 5.26 community, 7474/7687, neo4j/evaltic2026),
  `evaltic-neo4j-init` (carga PG2 si la base está vacía y SIEMPRE el script PG3), `evaltic-app` (8501).
  Ollama en Docker existe como perfil opcional, pero NO se usa.
- **Ollama instalado en Windows** con `qwen2.5:1.5b`. En `.env`: `COMPOSE_PROFILES=` (vacío) y
  `OLLAMA_URL_DOCKER=http://host.docker.internal:11434/api/generate`.
- `.env` NO se versiona (tiene claves); `.env.example` sí.
- Comandos: `levantar.bat` (up), `actualizar.bat` (recarga grafo PG2+PG3 y rebuild de la app),
  `probar.bat` (`python orquestador_evaltic.py --test` dentro del contenedor), `recargar_grafo.bat`, `detener.bat`.
  Equivalentes: `docker compose up -d --build`, `docker compose run --rm -e RECARGAR=1 neo4j-init`,
  `docker compose exec app python orquestador_evaltic.py "texto del aviso"`.
- Git: remoto `git@github.com:Luchoromero29/proyecto-final-IA.git`, rama `main`. Luciano hace push con su SSH.

## Principio central (lo pidió la cátedra)
**Ningún precio, costo ni umbral escrito en Python.** Todo se lee de Neo4j:
- `(:CriterioExperto {nombre, valor, unidad, version, estado_validacion})` CE-01..CE-28. Se leen con `CE(nombre, traza)`.
- `(:CostoReparacion {tarea, costo_ars})` — tareas: bateria, pantalla, teclado, ssd_upgrade, ram_upgrade,
  service_termico, cargador, mano_de_obra. Se leen con `costo(tarea, traza)`.
- `(:SegmentoMercado {precio_nuevo_ref_ars, dias_promedio_venta, indice_repuestos, patron, prioridad})`:
  SEG-APPLE, GAMER, CORPORATIVA, ALTA, MEDIA, ENTRADA, BASICA. `patron` = regex Java sobre el texto en minúsculas.
- `(:ModeloReferencia {anio_lanzamiento, soporte_w11, dias_promedio_venta, indice_repuestos, patron, prioridad})`
  -[:PERTENECE_A_SEGMENTO]-> segmento (opcional; si no tiene, el segmento lo decide el procesador).
- Reglas difusas `(:ReglaDifusa {base})` con bases SM1-BAT, SM1-TER, SM2-RIE, SM2-DEM, SM3-CONV;
  la inferencia Mamdani corre en Cypher (`inferir_*_cypher`).
Si se necesita un valor nuevo: agregarlo como nodo en `Grupo_20_PG3_mercado.cypher` (con MERGE, estado
'Provisional') y sumarlo a `CRITERIOS_REQUERIDOS`/`COSTOS_REQUERIDOS` si es obligatorio.
Todos los valores son PROVISIONALES (precios: relevamiento web 5/11/2026; costos: estimación del grupo;
falta la entrevista con el experto Matías Romero).

## Pipeline (`evaluar_publicacion_integral`)
1. `cargar_conocimiento(forzar=True)` y `nueva_traza()`.
2. `extraer_datos_llm` (JSON, reintenta 1 vez). Validación del precio con regex y de la falla catastrófica
   con palabras clave. Sin marca/modelo o precio → rechazo.
3. **R3.3**: señales de bloqueo en el texto (`SENALES_BLOQUEO`: icloud, "no recuerdo la cuenta"…) →
   `VerificacionPendiente` (el texto solo genera sospecha; R3.1 descartaría solo con bloqueo confirmado).
4. **SM1** `ejecutar_motor_sm1`: R1.1 falla catastrófica → inviable (→ R3.2 DescartarPorInviabilidad).
   Batería: difusa SM1-BAT si hay salud y ciclos; crisp R1.2 (CE bateria_reemplazo) si solo salud;
   si no hay datos → `datos_pendientes`. Temperatura: SM1-TER. Plan: RAM < CE ram_objetivo, HDD→SSD,
   pantalla, teclado, cargador, mano de obra (la mano de obra NO cuenta como intervención).
5. **SM2** `ejecutar_motor_sm2`: `buscar_referencia_mercado` (modelo + segmento). Sin segmento o sin año
   → `Verificacion_pendiente` (R3.3b). Año: aviso → modelo de referencia. W11: aviso → modelo → año ≥ CE anio_min_w11.
   Riesgo SM2-RIE → demanda SM2-DEM (encadenada, rotación del catálogo). VMA = precio_nuevo × factor
   depreciación (CE-21..24) × factor riesgo (CE-25/26) + revalorización por upgrades de SM1 (R2.3, CE reval_ssd/ram).
6. **SM3** `ejecutar_motor_sm3`: R3.7 ratio > CE ratio_reparacion_max; R3.8 riesgo Alto + demanda Baja;
   margen requerido en orden fijo: CE margen_base → R3.4 (Alta+Bajo → margen_alta_liquidez) o R3.5 (Alto →
   máx con margen_riesgo_alto) → R3.6 (+prima_fallas si intervenciones ≥ umbral). Contraoferta =
   VMA − costo − VMA×margen_req. Conveniencia difusa SM3-CONV (brecha, descuento).
7. `_estado_decision`: **Firme** solo si todos los criterios/costos usados están Validados y no hubo datos
   inferidos ni pendientes; si no, **Provisional** (con `criterios_pendientes`). VerificacionPendiente → "Pendiente".
8. Dictamen con el LLM. El resultado incluye `traza` (reglas, criterios_usados, costos_usados,
   datos_inferidos, datos_pendientes, referencia_mercado); `app_web.py` la muestra.

## Devoluciones de la cátedra a respetar
- Los umbrales no van escritos en las reglas: se referencian instancias de CriterioExperto (con nombre, unidad, versión).
- Margen requerido con política de combinación explícita (base → R3.4 o R3.5 → R3.6).
- Falta de dato ≠ estado favorable: debe quedar DESCONOCIDO/PENDIENTE (nada de "repuesto=Disponible",
  "riesgo=Bajo", "demanda=Media" por defecto).
- Texto sospechoso de bloqueo → verificación pendiente, no bloqueo confirmado.
- R1.4 (RAM soldada 4 GB) NO es inviabilidad física: modelar como limitación `NoAmpliable` y que SM2/SM3 decidan.
- Mantener visible el estado de validación hasta la salida final (firme/provisional + criterios pendientes).
- Lógica difusa solo para conceptos graduales (margen, desgaste, rotación, riesgo); falta de dato, bloqueo
  conocido o disponibilidad no relevada quedan FUERA de la lógica difusa.

## Estado actual y pendientes (noviembre de 2026)
- [x] **Probar contra Neo4j real** (9/11/2026): PG2+PG3 cargan sin errores y `--test` corre contra Neo4j real.
      Primero `actualizar.bat`, revisar `docker logs evaltic-neo4j-init`, después `probar.bat`.
- [ ] **Deducir el año desde el procesador** (siguiente tarea acordada): agregar al script PG3 nodos
      `(:GeneracionProcesador {patron, anio, familia})` (ej. "i5 10ma gen"/"10210U" → 2020, "8550U" → 2018,
      "Ryzen 5 7520U" → 2022, "M1" → 2020), usarlos en SM2 después del modelo de referencia y antes de
      quedar en verificación pendiente; registrar el año como dato inferido.
- [ ] Los 5 casos de `CASOS_INTEGRADOS_PG3` tienen precios de la escala vieja del PG1 (ej. Acer a $115.000);
      con el catálogo nuevo probablemente no den la decisión de `DECISION_ESPERADA`. Actualizar los precios
      pedidos a valores de hoy o las decisiones esperadas.
- [ ] R1.4 `NoAmpliable` (RAM soldada) — no implementado.
- [ ] R3.1b rechazo comercial directo (equipo Frankenstein / arquitectura propietaria) — no implementado en Python.
- [ ] SM2: el riesgo pesa tres veces (factor en el VMA, demanda y margen requerido). Charlar con Leonel.
- [ ] `consultar_grafo_neo4j_d1` quedó sin uso (antes era un atajo que devolvía resultados guardados; se eliminó).
- [ ] qwen2.5:1.5b extrae mal a veces; alternativa: Groq (ver LEVANTAR.md).

## Convenciones
- Todo en español (código, comentarios, UI, mensajes de commit).
- `scripts/*.sh` con fin de línea LF (`.gitattributes`); `.bat` con CRLF.
- No commitear `.env`, `_respaldo_original/` ni zips.
- Después de cambiar Python: `docker compose up -d --build app`. Después de cambiar un `.cypher`: `actualizar.bat`.
- Luciano prefiere respuestas cortas y prácticas y que se cumpla la consigna sin sobredimensionar.
