#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  EvalTIC — Asistente Inteligente Neuro-Simbólico Integrado (PG3)
  Proyecto Grupal 3 — Inteligencia Artificial — UTN Facultad Regional Mendoza
  Equipo: Grupo 20 (5K09)
    - Álvaro Tapia (SM1: Diagnóstico Técnico y Reacondicionamiento)
    - Leonel Navarta (SM2: Valuación Comercial y Demanda)
    - Luciano Romero (SM3: Evaluación de la Operación y Decisión Final)
================================================================================
  Arquitectura:
    1. System Prompt Maestro de Enrutamiento y Orquestación.
    2. Submódulo SM1 (Técnico): Extracción hardware, filtros de inviabilidad,
       lógica difusa de degradación física, plan y costos de reacondicionamiento.
    3. Submódulo SM2 (Comercial): Extracción comercial, catálogo de referencia,
       depreciación cronológica, lógica difusa de riesgo de obsolescencia y demanda, VMA.
    4. Submódulo SM3 (Financiero): Extracción financiera, filtros de riesgo,
       cálculo de márgenes y contraoferta, lógica difusa Mamdani de conveniencia.
    5. Síntesis Ejecutiva Global: Dictamen comercial integral para el revendedor.
================================================================================
"""

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# ------------------------------------------------------------------------------
# 1. Configuración de Entorno (.env)
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
if not ENV_PATH.exists():
    ENV_PATH = BASE_DIR.parent / "PI4" / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ==============================================================================
# Configuración Neo4j (Base de Conocimiento Obligatoria - Modo Local / Remoto)
# ==============================================================================
# Por defecto se utiliza la instancia LOCAL ("offline" en la máquina: bolt://localhost:7687).
# Si se desea conectar a la nube AuraDB ("online"), configurar NEO4J_TARGET=remote en .env.
NEO4J_TARGET = os.getenv("NEO4J_TARGET", "local").lower().strip()

if NEO4J_TARGET in ("local", "offline"):
    NEO4J_URI = os.getenv("NEO4J_LOCAL_URI", os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    NEO4J_USERNAME = os.getenv("NEO4J_LOCAL_USERNAME", os.getenv("NEO4J_USERNAME", "neo4j"))
    NEO4J_PASSWORD = os.getenv("NEO4J_LOCAL_PASSWORD", os.getenv("NEO4J_PASSWORD", "evaltic2026"))
    NEO4J_DATABASE = os.getenv("NEO4J_LOCAL_DATABASE", os.getenv("NEO4J_DATABASE", "neo4j"))
    TIPO_INSTANCIA = "Local Offline (Docker)"
else:
    NEO4J_URI = os.getenv("NEO4J_REMOTE_URI", os.getenv("NEO4J_URI", "neo4j+s://676a5bd9.databases.neo4j.io"))
    NEO4J_USERNAME = os.getenv("NEO4J_REMOTE_USERNAME", os.getenv("NEO4J_USERNAME", "neo4j"))
    NEO4J_PASSWORD = os.getenv("NEO4J_REMOTE_PASSWORD", os.getenv("NEO4J_PASSWORD", "evaltic2026"))
    NEO4J_DATABASE = os.getenv("NEO4J_REMOTE_DATABASE", os.getenv("NEO4J_DATABASE", "neo4j"))
    TIPO_INSTANCIA = "Remota Online (AuraDB)"

_neo4j_driver = None

def obtener_driver_neo4j():
    """Obtiene la conexión obligatoria con Neo4j. Eleva error real si el servicio está apagado."""
    global _neo4j_driver
    if _neo4j_driver is not None:
        return _neo4j_driver
    try:
        import neo4j
        driver = neo4j.GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        driver.verify_connectivity()
        _neo4j_driver = driver
        return _neo4j_driver
    except Exception as e:
        raise ConnectionError(
            f"\n[ERROR CRÍTICO NEO4J] No se pudo conectar a la base de conocimiento ({TIPO_INSTANCIA}) en {NEO4J_URI}.\n"
            f"El sistema EvalTIC requiere obligatoriamente Neo4j para ejecutar las inferencias simbólicas y difusas.\n"
            f"Si estás usando la instancia local, asegúrate de levantar el contenedor Docker con:\n"
            f"  docker start neo4j-evaltic\n"
            f"Detalle técnico: {e}"
        )

def consultar_grafo_neo4j_d1(equipo_id: str) -> dict:
    """Ejecuta la Consulta D1 del PG2 sobre el Grafo de Conocimiento en Neo4j."""
    driver = obtener_driver_neo4j()
    with driver.session(database=NEO4J_DATABASE) as session:
        q_d1 = '''
        MATCH (op:Operacion)-[:EVALUA]->(e:Equipo {id: $equipoId})<-[:OFRECE]-(p:Publicacion)
        OPTIONAL MATCH (e)-[:RECIBE_DECISION]->(dec:Decision)
        OPTIONAL MATCH (op)-[:TIENE_INDICADORES]->(ind:IndicadoresEconomicos)
        RETURN {
          equipo:           e.marca + ' ' + e.modelo,
          precio_publicado: p.precio,
          estado_operacion: op.estado,
          sm1: {
            dictamen:       head([(e)-[:TIENE_DICTAMEN]->(d) | d.resultado]),
            causa:          head([(e)-[:TIENE_DICTAMEN]->(d) | d.causa_inviabilidad]),
            intervenciones: [(e)-[:TIENE_PLAN]->()<-[:FORMA_PARTE_DE]-(i) | {tarea: i.tipo_tarea, costo: i.costo_ars, mandatoria: i.es_mandatoria, origen: i.origen}],
            costo_total:    head([(e)-[:TIENE_PLAN]->()-[:GENERA]->(x) | x.monto_total])
          },
          sm2: {
            vma:      head([(e)-[:TIENE_VALUACION]->(x) | x.monto_tasado_ars]),
            riesgo:   head([(e)-[:TIENE_RIESGO]->(x) | {nivel: x.nivel, indice: x.indice}]),
            demanda:  head([(e)-[:TIENE_DEMANDA]->(x) | {nivel: x.nivel, indice: x.indice}]),
            dictamen: head([(e)-[:TIENE_DICTAMEN_COMERCIAL]->(x) | x.veredicto])
          },
          indicadores: ind {.margen_neto, .margen_requerido, .ratio_reparacion, .contraoferta},
          reglas_crisp: CASE WHEN dec IS NULL THEN [] ELSE [(dec)-[:APLICA_REGLA]->(r) | r.id + ': ' + r.texto] END
                      + CASE WHEN ind IS NULL THEN [] ELSE [(ind)-[:APLICA_REGLA]->(r) | r.id + ': ' + r.texto] END,
          decision:  dec {.tipo, .motivo, .contraoferta}
        } AS contexto_llm
        '''
        rec = session.run(q_d1, equipoId=equipo_id).single()
        if rec and rec['contexto_llm']:
            return rec['contexto_llm']
    return None

def inferir_sm1_bat_cypher(salud: float, ciclos: float) -> tuple:
    """Infiere necesidad de reemplazo de batería mediante Cypher en Neo4j."""
    driver = obtener_driver_neo4j()
    if not driver:
        return None
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            q = '''
            WITH $salud AS salud, $ciclos AS ciclos
            MATCH (r:ReglaDifusa {base:'SM1-BAT'})-[a:ANTECEDENTE]->(cj:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(var:VariableDifusa)
            WITH salud, ciclos, r, a.grupo AS grupo,
                 max(exp(-0.5 * (((CASE var.nombre WHEN 'Salud_Bateria' THEN salud ELSE ciclos END) - cj.c) / cj.sigma)^2)) AS mu_grupo
            WITH salud, ciclos, r, min(mu_grupo) AS fuerza
            WHERE fuerza >= 0.01
            MATCH (r)-[:CONSECUENTE]->(sal:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(vs:VariableDifusa {nombre:'Necesidad_Intervencion'})
            WITH vs, collect({regla: r.id, fuerza: fuerza, c: sal.c, sigma: sal.sigma}) AS reglas
            UNWIND range(0, 100) AS i
            WITH vs, reglas, vs.min + (vs.max - vs.min) * i / 100.0 AS y
            UNWIND reglas AS rg
            WITH vs, reglas, y, rg, exp(-0.5 * ((y - rg.c) / rg.sigma)^2) AS mu_sal
            WITH vs, reglas, y, max(CASE WHEN rg.fuerza < mu_sal THEN rg.fuerza ELSE mu_sal END) AS altura
            WITH vs, reglas, sum(y * altura) / sum(altura) AS centroide
            MATCH (vs)-[:TIENE_CONJUNTO]->(s:ConjuntoDifuso)
            WITH reglas, centroide, s, exp(-0.5 * ((centroide - s.c) / s.sigma)^2) AS mu
            ORDER BY mu DESC
            WITH reglas, centroide, collect(s.etiqueta)[0] AS categoria
            RETURN round(centroide, 4) AS centroide, categoria
            '''
            res = session.run(q, salud=float(salud), ciclos=float(ciclos)).single()
            if res and res['centroide'] is not None:
                return round(float(res['centroide']), 2), res['categoria']
    except Exception:
        pass
    return None

def inferir_sm1_ter_cypher(temp: float, caida: float) -> tuple:
    """Infiere necesidad de service térmico mediante Cypher en Neo4j."""
    driver = obtener_driver_neo4j()
    if not driver:
        return None
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            q = '''
            WITH $temp AS temp, $caida AS caida
            MATCH (r:ReglaDifusa {base:'SM1-TER'})-[a:ANTECEDENTE]->(cj:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(var:VariableDifusa)
            WITH temp, caida, r, a.grupo AS grupo,
                 max(exp(-0.5 * (((CASE var.nombre WHEN 'Temperatura_CPU' THEN temp ELSE caida END) - cj.c) / cj.sigma)^2)) AS mu_grupo
            WITH temp, caida, r, min(mu_grupo) AS fuerza
            WHERE fuerza >= 0.01
            MATCH (r)-[:CONSECUENTE]->(sal:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(vs:VariableDifusa {nombre:'Necesidad_Intervencion'})
            WITH vs, collect({regla: r.id, fuerza: fuerza, c: sal.c, sigma: sal.sigma}) AS reglas
            UNWIND range(0, 100) AS i
            WITH vs, reglas, vs.min + (vs.max - vs.min) * i / 100.0 AS y
            UNWIND reglas AS rg
            WITH vs, reglas, y, rg, exp(-0.5 * ((y - rg.c) / rg.sigma)^2) AS mu_sal
            WITH vs, reglas, y, max(CASE WHEN rg.fuerza < mu_sal THEN rg.fuerza ELSE mu_sal END) AS altura
            WITH vs, reglas, sum(y * altura) / sum(altura) AS centroide
            MATCH (vs)-[:TIENE_CONJUNTO]->(s:ConjuntoDifuso)
            WITH reglas, centroide, s, exp(-0.5 * ((centroide - s.c) / s.sigma)^2) AS mu
            ORDER BY mu DESC
            WITH reglas, centroide, collect(s.etiqueta)[0] AS categoria
            RETURN round(centroide, 4) AS centroide, categoria
            '''
            res = session.run(q, temp=float(temp), caida=float(caida)).single()
            if res and res['centroide'] is not None:
                return round(float(res['centroide']), 2), res['categoria']
    except Exception:
        pass
    return None

def inferir_sm2_rie_cypher(antiguedad: float, repuestos: float, win11: bool) -> tuple:
    """Infiere riesgo de obsolescencia mediante Cypher en Neo4j."""
    driver = obtener_driver_neo4j()
    if not driver:
        return None
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            q = '''
            WITH $antiguedad AS antiguedad, $repuestos AS repuestos, $win11 AS win11
            MATCH (r:ReglaDifusa {base:'SM2-RIE'})-[a:ANTECEDENTE]->(cj:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(var:VariableDifusa)
            WITH antiguedad, repuestos, win11, r, a.grupo AS grupo,
                 max(CASE cj.tipo
                       WHEN 'crisp' THEN CASE WHEN (CASE var.nombre WHEN 'Soporte_W11' THEN win11 END) = cj.valor THEN 1.0 ELSE 0.0 END
                       ELSE exp(-0.5 * (((CASE var.nombre WHEN 'Antiguedad_Hardware' THEN antiguedad ELSE repuestos END) - cj.c) / cj.sigma)^2)
                     END) AS mu_grupo
            WITH antiguedad, repuestos, win11, r, min(mu_grupo) AS fuerza
            WHERE fuerza >= 0.01
            MATCH (r)-[:CONSECUENTE]->(sal:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(vs:VariableDifusa {nombre:'Riesgo_Obsolescencia'})
            WITH vs, collect({regla: r.id, fuerza: fuerza, c: sal.c, sigma: sal.sigma}) AS reglas
            UNWIND range(0, 100) AS i
            WITH vs, reglas, vs.min + (vs.max - vs.min) * i / 100.0 AS y
            UNWIND reglas AS rg
            WITH vs, reglas, y, rg, exp(-0.5 * ((y - rg.c) / rg.sigma)^2) AS mu_sal
            WITH vs, reglas, y, max(CASE WHEN rg.fuerza < mu_sal THEN rg.fuerza ELSE mu_sal END) AS altura
            WITH vs, reglas, sum(y * altura) / sum(altura) AS centroide
            MATCH (vs)-[:TIENE_CONJUNTO]->(s:ConjuntoDifuso)
            WITH reglas, centroide, s, exp(-0.5 * ((centroide - s.c) / s.sigma)^2) AS mu
            ORDER BY mu DESC
            WITH reglas, centroide, collect(s.etiqueta)[0] AS categoria
            RETURN round(centroide, 4) AS centroide, categoria
            '''
            res = session.run(q, antiguedad=float(antiguedad), repuestos=float(repuestos), win11=bool(win11)).single()
            if res and res['centroide'] is not None:
                c_val = round(float(res['centroide']), 2)
                cat_val = res['categoria']
                print(f"      [Cypher Neo4j SM2-RIE] Mamdani evaluado en grafo -> Centroide: {c_val} | Categoría: {cat_val}", flush=True)
                return c_val, cat_val
    except Exception:
        pass
    return None

def inferir_sm2_dem_cypher(riesgo: float, rotacion: float) -> tuple:
    """Infiere demanda comercial mediante Cypher en Neo4j."""
    driver = obtener_driver_neo4j()
    if not driver:
        return None
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            q = '''
            WITH $riesgo AS riesgo, $rotacion AS rotacion
            MATCH (r:ReglaDifusa {base:'SM2-DEM'})-[a:ANTECEDENTE]->(cj:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(var:VariableDifusa)
            WITH riesgo, rotacion, r, a.grupo AS grupo,
                 max(exp(-0.5 * (((CASE var.nombre WHEN 'Riesgo_Obsolescencia' THEN riesgo ELSE rotacion END) - cj.c) / cj.sigma)^2)) AS mu_grupo
            WITH riesgo, rotacion, r, min(mu_grupo) AS fuerza
            WHERE fuerza >= 0.01
            MATCH (r)-[:CONSECUENTE]->(sal:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(vs:VariableDifusa {nombre:'Demanda_Comercial'})
            WITH vs, collect({regla: r.id, fuerza: fuerza, c: sal.c, sigma: sal.sigma}) AS reglas
            UNWIND range(0, 100) AS i
            WITH vs, reglas, vs.min + (vs.max - vs.min) * i / 100.0 AS y
            UNWIND reglas AS rg
            WITH vs, reglas, y, rg, exp(-0.5 * ((y - rg.c) / rg.sigma)^2) AS mu_sal
            WITH vs, reglas, y, max(CASE WHEN rg.fuerza < mu_sal THEN rg.fuerza ELSE mu_sal END) AS altura
            WITH vs, reglas, sum(y * altura) / sum(altura) AS centroide
            MATCH (vs)-[:TIENE_CONJUNTO]->(s:ConjuntoDifuso)
            WITH reglas, centroide, s, exp(-0.5 * ((centroide - s.c) / s.sigma)^2) AS mu
            ORDER BY mu DESC
            WITH reglas, centroide, collect(s.etiqueta)[0] AS categoria
            RETURN round(centroide, 4) AS centroide, categoria
            '''
            res = session.run(q, riesgo=float(riesgo), rotacion=float(rotacion)).single()
            if res and res['centroide'] is not None:
                c_val = round(float(res['centroide']), 2)
                cat_val = res['categoria']
                print(f"      [Cypher Neo4j SM2-DEM] Mamdani evaluado en grafo -> Centroide: {c_val} | Categoría: {cat_val}", flush=True)
                return c_val, cat_val
    except Exception:
        pass
    return None

def inferir_sm3_conv_cypher(brecha: float, descuento: float) -> tuple:
    """Infiere conveniencia de compra mediante Cypher en Neo4j."""
    driver = obtener_driver_neo4j()
    if not driver:
        return None
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            q = '''
            WITH $brecha AS brecha, $descuento AS descuento
            MATCH (r:ReglaDifusa {base:'SM3-CONV'})-[a:ANTECEDENTE]->(cj:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(var:VariableDifusa)
            WITH brecha, descuento, r, a.grupo AS grupo,
                 max(exp(-0.5 * (((CASE var.nombre WHEN 'Brecha_Margen' THEN brecha ELSE descuento END) - cj.c) / cj.sigma)^2)) AS mu_grupo
            WITH brecha, descuento, r, min(mu_grupo) AS fuerza
            MATCH (r)-[:CONSECUENTE]->(sal:ConjuntoDifuso)
            WITH brecha, descuento, collect({regla: r.id, fuerza: fuerza, c: sal.c, sigma: sal.sigma}) AS reglas
            UNWIND range(0, 100) AS i
            WITH brecha, descuento, reglas, i / 100.0 AS y
            UNWIND reglas AS rg
            WITH brecha, descuento, reglas, y, rg, exp(-0.5 * ((y - rg.c) / rg.sigma)^2) AS mu_sal
            WITH brecha, descuento, reglas, y,
                 max(CASE WHEN rg.fuerza < mu_sal THEN rg.fuerza ELSE mu_sal END) AS altura
            WITH brecha, descuento, reglas, sum(y * altura) / sum(altura) AS centroide
            MATCH (:VariableDifusa {nombre:'Conveniencia'})-[:TIENE_CONJUNTO]->(s:ConjuntoDifuso)
            WITH brecha, descuento, reglas, centroide, s,
                 exp(-0.5 * ((centroide - s.c) / s.sigma)^2) AS mu
            ORDER BY mu DESC
            WITH brecha, descuento, reglas, centroide, collect(s.etiqueta)[0] AS categoria
            RETURN round(centroide, 4) AS centroide, categoria
            '''
            res = session.run(q, brecha=float(brecha), descuento=float(descuento)).single()
            if res and res['centroide'] is not None:
                c_val = round(float(res['centroide']), 2)
                cat_val = res['categoria']
                print(f"      [Cypher Neo4j SM3-CONV] Mamdani evaluado en grafo -> Centroide: {c_val} | Categoría: {cat_val}", flush=True)
                return c_val, cat_val
    except Exception:
        pass
    return None

# ------------------------------------------------------------------------------
# 2. Cliente Unificado de Modelos de Lenguaje (Sin Mocks)
# ------------------------------------------------------------------------------
def consultar_llm(system_prompt: str, user_content: str, json_mode: bool = False, max_tokens: int = 300) -> str:
    """Envía la consulta al LLM configurado. Eleva excepciones reales ante fallos."""
    if LLM_PROVIDER == "ollama":
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": f"{system_prompt}\n\nEntrada del usuario:\n{user_content}",
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": max_tokens
            }
        }
        if json_mode:
            payload["format"] = "json"

        try:
            resp = requests.post(OLLAMA_URL, json=payload, timeout=180)
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(
                f"[ERROR CRÍTICO EVALTIC] No se pudo conectar con Ollama en {OLLAMA_URL}. "
                f"Asegúrate de que el servicio esté activo (`ollama serve`). Detalle: {e}"
            )
        except requests.exceptions.Timeout as e:
            raise TimeoutError(
                f"[ERROR CRÍTICO EVALTIC] Tiempo de espera agotado al consultar Ollama ({OLLAMA_URL}). Detalle: {e}"
            )

        if resp.status_code != 200:
            raise RuntimeError(f"[ERROR OLLAMA] Código {resp.status_code}: {resp.text}")

        data = resp.json()
        return data.get("response", "").strip()

    elif LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("[ERROR CONFIGURACIÓN] OPENAI_API_KEY no está configurada en el archivo .env.")

        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        payload = {
            "model": OPENAI_MODEL,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        endpoint = f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions"
        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
        except Exception as e:
            raise ConnectionError(f"[ERROR CRÍTICO EVALTIC] Error de conexión con API remota ({endpoint}): {e}")

        if resp.status_code != 200:
            raise RuntimeError(f"[ERROR API REMOTA] Código {resp.status_code}: {resp.text}")

        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    else:
        raise ValueError(f"[ERROR CONFIGURACIÓN] Proveedor LLM desconocido: '{LLM_PROVIDER}'.")


# ------------------------------------------------------------------------------
# 3. Base de Conocimiento leída desde Neo4j (PG2 + catálogo PG3)
#    No hay precios, costos ni umbrales escritos en este archivo: todo sale de
#    los nodos :CriterioExperto, :CostoReparacion, :SegmentoMercado y
#    :ModeloReferencia (cypher/Grupo_20_PG3_mercado.cypher).
# ------------------------------------------------------------------------------
CRITERIOS_REQUERIDOS = [
    "bateria_reemplazo", "ram_objetivo", "anio_referencia", "anio_min_w11",
    "deprec_anual_inicial", "deprec_anual_posterior", "anios_deprec_inicial", "valor_residual_min",
    "factor_riesgo_medio", "factor_riesgo_alto", "reval_ssd", "reval_ram",
    "margen_base", "margen_alta_liquidez", "margen_riesgo_alto",
    "umbral_intervenciones", "prima_fallas", "ratio_reparacion_max",
]
COSTOS_REQUERIDOS = ["bateria", "pantalla", "teclado", "ssd_upgrade", "ram_upgrade",
                     "service_termico", "cargador", "mano_de_obra"]

_CONOCIMIENTO = None


def cargar_conocimiento(forzar: bool = False) -> dict:
    """Lee de Neo4j los criterios expertos y los costos de reparación (con caché)."""
    global _CONOCIMIENTO
    if _CONOCIMIENTO is not None and not forzar:
        return _CONOCIMIENTO
    driver = obtener_driver_neo4j()
    with driver.session(database=NEO4J_DATABASE) as s:
        criterios = {
            r["nombre"]: dict(r) for r in s.run(
                "MATCH (c:CriterioExperto) RETURN c.nombre AS nombre, c.id AS id, c.valor AS valor, "
                "c.unidad AS unidad, c.version AS version, c.estado_validacion AS estado")
        }
        costos = {
            r["tarea"]: dict(r) for r in s.run(
                "MATCH (c:CostoReparacion) RETURN c.tarea AS tarea, c.id AS id, c.costo_ars AS costo, "
                "c.descripcion AS descripcion, c.version AS version, c.estado_validacion AS estado")
        }
    faltan = [f"CriterioExperto '{n}'" for n in CRITERIOS_REQUERIDOS if n not in criterios]
    faltan += [f"CostoReparacion '{t}'" for t in COSTOS_REQUERIDOS if t not in costos]
    if faltan:
        raise RuntimeError(
            "[ERROR BASE DE CONOCIMIENTO] Faltan nodos en Neo4j: " + ", ".join(faltan) +
            ". Cargá cypher/Grupo_20_PG3_mercado.cypher (en Docker: recargar_grafo.bat).")
    _CONOCIMIENTO = {"criterios": criterios, "costos": costos}
    return _CONOCIMIENTO


def nueva_traza() -> dict:
    """Traza de la evaluación: qué datos, criterios, costos y reglas intervinieron."""
    return {"reglas": [], "criterios_usados": {}, "costos_usados": {},
            "datos_inferidos": [], "datos_pendientes": [], "referencia_mercado": None}


def CE(nombre: str, traza: dict) -> float:
    """Devuelve el valor vigente de un CriterioExperto y lo registra en la traza."""
    c = cargar_conocimiento()["criterios"][nombre]
    traza["criterios_usados"][nombre] = {k: c[k] for k in ("id", "valor", "unidad", "version", "estado")}
    return float(c["valor"])


def costo(tarea: str, traza: dict) -> int:
    """Devuelve el costo de una intervención desde :CostoReparacion y lo registra en la traza."""
    c = cargar_conocimiento()["costos"][tarea]
    traza["costos_usados"][tarea] = {k: c[k] for k in ("id", "costo", "version", "estado")}
    return int(c["costo"])


def buscar_referencia_mercado(texto: str) -> dict:
    """
    Busca en Neo4j el modelo de referencia y el segmento de mercado que coinciden con el aviso.
    El segmento de una línea específica (MacBook, gamer, corporativa) tiene prioridad sobre la gama
    que indica el procesador. Devuelve {'modelo': {...} | None, 'segmento': {...} | None}.
    """
    driver = obtener_driver_neo4j()
    q = """
    WITH toLower($texto) AS t
    OPTIONAL MATCH (m:ModeloReferencia) WHERE t =~ m.patron
    WITH t, m ORDER BY m.prioridad DESC LIMIT 1
    OPTIONAL MATCH (m)-[:PERTENECE_A_SEGMENTO]->(ms:SegmentoMercado)
    OPTIONAL MATCH (s:SegmentoMercado) WHERE t =~ s.patron
    WITH m, ms, s ORDER BY s.prioridad DESC LIMIT 1
    WITH m, CASE WHEN ms IS NOT NULL AND (s IS NULL OR ms.prioridad >= s.prioridad) THEN ms ELSE s END AS seg
    RETURN m {.id, .nombre, .anio_lanzamiento, .soporte_w11, .dias_promedio_venta, .indice_repuestos} AS modelo,
           seg {.id, .nombre, .precio_nuevo_ref_ars, .dias_promedio_venta, .indice_repuestos,
                .fuente, .estado_validacion} AS segmento
    """
    with driver.session(database=NEO4J_DATABASE) as s:
        r = s.run(q, texto=texto).single()
    return {"modelo": r["modelo"] if r else None, "segmento": r["segmento"] if r else None}


# ------------------------------------------------------------------------------
# 4. Módulo SM1: Diagnóstico Técnico y Reacondicionamiento (Álvaro Tapia)
# ------------------------------------------------------------------------------
def ejecutar_motor_sm1(datos: dict, traza: dict) -> dict:
    """Reglas crisp + lógica difusa de degradación física. Un dato no informado queda pendiente,
    no se reemplaza por un valor favorable."""
    # R1.1: falla catastrófica → inviabilidad física
    if datos.get("falla_catastrofica"):
        traza["reglas"].append("R1.1: falla catastrófica → Inviabilidad_Fisica_Insalvable")
        return {"estado": "Inviable", "es_viable": False, "regla_aplicada": "R1.1",
                "motivo": f"Falla física irreparable detectada: {datos.get('falla_catastrofica')}.",
                "plan_reparacion": [], "costo_total": 0, "cantidad_intervenciones": 0,
                "upgrades": {"ssd": False, "ram": False}}

    plan = []
    upgrades = {"ssd": False, "ram": False}

    def agregar(tarea: str, regla: str):
        c = costo(tarea, traza)
        plan.append({"tarea": cargar_conocimiento()["costos"][tarea]["descripcion"], "costo": c, "regla": regla})
        traza["reglas"].append(f"{regla} → {tarea} (${c:,})")

    # Batería: difusa si están salud y ciclos; crisp (R1.2) si solo está la salud
    salud, ciclos = datos.get("salud_bateria_pct"), datos.get("ciclos_bateria")
    if salud is not None and ciclos is not None:
        res = inferir_sm1_bat_cypher(float(salud), float(ciclos))
        if not res:
            raise RuntimeError("[ERROR INFERENCIA NEO4J] Falló la inferencia SM1-BAT.")
        if res[1] == "Obligatoria":
            agregar("bateria", f"SM1-BAT difusa ({res[0]} → {res[1]})")
    elif salud is not None:
        if float(salud) < CE("bateria_reemplazo", traza):
            agregar("bateria", "R1.2: salud de batería < CE bateria_reemplazo")
    else:
        traza["datos_pendientes"].append("Salud de batería (verificar en la revisión)")

    # Temperatura: difusa si hay temperatura; crisp si solo se informa throttling
    temp, throttling = datos.get("temperatura_cpu_c"), datos.get("thermal_throttling")
    if temp is not None:
        if throttling is None:
            traza["datos_inferidos"].append("Caída de frecuencia no informada: se toma como leve (5 %)")
        res = inferir_sm1_ter_cypher(float(temp), 20.0 if throttling else 5.0)
        if not res:
            raise RuntimeError("[ERROR INFERENCIA NEO4J] Falló la inferencia SM1-TER.")
        if res[1] in ("Obligatoria", "Recomendada"):
            agregar("service_termico", f"SM1-TER difusa ({res[0]} → {res[1]})")
    elif throttling is True:
        agregar("service_termico", "Throttling informado → service térmico")
    else:
        traza["datos_pendientes"].append("Temperatura bajo carga (prueba de estrés)")

    # Upgrades del plan
    ram = datos.get("ram_gb")
    if ram is None:
        traza["datos_pendientes"].append("Memoria RAM")
    elif ram < CE("ram_objetivo", traza):
        agregar("ram_upgrade", "Plan: RAM < CE ram_objetivo")
        upgrades["ram"] = True

    disco = str(datos.get("tipo_disco") or "").upper()
    if disco == "HDD":
        agregar("ssd_upgrade", "Plan: disco HDD → SSD")
        upgrades["ssd"] = True
    elif not disco:
        traza["datos_pendientes"].append("Tipo de disco")

    if datos.get("pantalla_danada") is True:
        agregar("pantalla", "Plan: pantalla dañada")
    if datos.get("teclado_danado") is True:
        agregar("teclado", "Plan: teclado dañado")
    if datos.get("cargador_incluido") is False:
        agregar("cargador", "Plan: sin cargador")

    n_intervenciones = len(plan)  # la mano de obra no cuenta como intervención (R3.6)
    if plan:
        agregar("mano_de_obra", "Plan: mano de obra")

    return {"estado": "Viable", "es_viable": True, "plan_reparacion": plan,
            "costo_total": sum(t["costo"] for t in plan),
            "cantidad_intervenciones": n_intervenciones, "upgrades": upgrades}


# ------------------------------------------------------------------------------
# 5. Módulo SM2: Valuación Comercial y Demanda (Leonel Navarta)
# ------------------------------------------------------------------------------
def ejecutar_motor_sm2(datos: dict, res_sm1: dict, texto: str, traza: dict) -> dict:
    """VMA con precio de referencia, rotación y repuestos tomados de Neo4j. Si el equipo no
    coincide con el catálogo o falta el año, la operación queda en Verificacion_pendiente (R3.3b)."""
    texto_busqueda = " ".join(str(x) for x in (datos.get("marca"), datos.get("modelo"),
                                               datos.get("procesador"), texto) if x)
    ref = buscar_referencia_mercado(texto_busqueda)
    modelo, seg = ref["modelo"], ref["segmento"]
    traza["referencia_mercado"] = ref

    if not seg:
        traza["reglas"].append("R3.3b: sin segmento de mercado en Neo4j → Verificacion_pendiente")
        return {"estado": "Verificacion_pendiente",
                "dato_faltante": "Procesador o línea del equipo (no coincide con ningún segmento del catálogo de Neo4j)",
                "vma_estimado_ars": 0}

    # Año: del aviso o del modelo de referencia
    anio = datos.get("anio_fabricacion")
    if anio is None and modelo and modelo.get("anio_lanzamiento"):
        anio = modelo["anio_lanzamiento"]
        traza["datos_inferidos"].append(f"Año tomado del modelo de referencia {modelo['nombre']}: {anio}")
    if anio is None:
        traza["reglas"].append("R3.3b: año de fabricación desconocido → Verificacion_pendiente")
        return {"estado": "Verificacion_pendiente", "dato_faltante": "Año de fabricación del equipo",
                "vma_estimado_ars": 0}
    antiguedad = max(0.0, CE("anio_referencia", traza) - float(anio))

    # Soporte de Windows 11: aviso → modelo → año
    win11 = datos.get("soporte_windows_11")
    if win11 is None:
        if modelo and modelo.get("soporte_w11") is not None:
            win11 = bool(modelo["soporte_w11"])
            traza["datos_inferidos"].append(f"Soporte de Windows 11 según el modelo {modelo['nombre']}: {win11}")
        else:
            win11 = float(anio) >= CE("anio_min_w11", traza)
            traza["datos_inferidos"].append(f"Soporte de Windows 11 inferido por el año ({anio}): {win11}")

    fuente_mercado = modelo if (modelo and modelo.get("indice_repuestos") is not None) else seg
    repuestos = float(fuente_mercado["indice_repuestos"])
    dias_rotacion = float(fuente_mercado["dias_promedio_venta"])
    precio_base = float(seg["precio_nuevo_ref_ars"])

    # Lógica difusa en Neo4j: riesgo de obsolescencia y demanda (encadenadas)
    res_rie = inferir_sm2_rie_cypher(antiguedad, repuestos, win11)
    if not res_rie:
        raise RuntimeError("[ERROR INFERENCIA NEO4J] Falló la inferencia SM2-RIE.")
    score_riesgo, categoria_riesgo = res_rie
    res_dem = inferir_sm2_dem_cypher(score_riesgo, dias_rotacion)
    if not res_dem:
        raise RuntimeError("[ERROR INFERENCIA NEO4J] Falló la inferencia SM2-DEM.")
    demanda = res_dem[1]

    # Depreciación cronológica (parámetros en :CriterioExperto)
    n_ini = CE("anios_deprec_inicial", traza)
    perdida = (min(antiguedad, n_ini) * CE("deprec_anual_inicial", traza)
               + max(0.0, antiguedad - n_ini) * CE("deprec_anual_posterior", traza)) / 100.0
    factor_deprec = max(CE("valor_residual_min", traza) / 100.0, 1.0 - perdida)
    if categoria_riesgo == "Alto":
        factor_riesgo = CE("factor_riesgo_alto", traza) / 100.0
    elif categoria_riesgo == "Medio":
        factor_riesgo = CE("factor_riesgo_medio", traza) / 100.0
    else:
        factor_riesgo = 1.0

    # R2.3: revalorización por los upgrades que planificó SM1 (se tasa el estado final)
    reval = 0.0
    if res_sm1.get("upgrades", {}).get("ssd"):
        reval += CE("reval_ssd", traza)
        traza["reglas"].append("R2.3: revalorización por upgrade a SSD")
    if res_sm1.get("upgrades", {}).get("ram"):
        reval += CE("reval_ram", traza)
        traza["reglas"].append("R2.3: revalorización por ampliación de RAM")

    vma = round(precio_base * factor_deprec * factor_riesgo + reval, -3)
    return {
        "estado": "Tasado",
        "segmento": seg["nombre"],
        "modelo_referencia": modelo["nombre"] if modelo else None,
        "fuente_precio": f"Neo4j :SegmentoMercado {seg['id']} ({seg.get('fuente')})",
        "precio_base_referencia": int(precio_base),
        "antiguedad_anios": antiguedad,
        "factor_depreciacion": round(factor_deprec, 3),
        "factor_riesgo": factor_riesgo,
        "revalorizaciones_ars": int(reval),
        "riesgo_obsolescencia": categoria_riesgo,
        "score_riesgo": score_riesgo,
        "demanda_comercial": demanda,
        "dias_rotacion_estimados": dias_rotacion,
        "indice_repuestos": repuestos,
        "vma_estimado_ars": int(vma),
    }


# ------------------------------------------------------------------------------
# 6. Módulo SM3: Evaluación de la Operación y Decisión Final (Luciano Romero)
# ------------------------------------------------------------------------------
def ejecutar_motor_sm3(precio: float, costo_rep: float, vma: float, n_interv: int,
                       riesgo: str, demanda: str, traza: dict) -> dict:
    """Filtros crisp (R3.7, R3.8), margen requerido en orden fijo (base → R3.4/R3.5 → R3.6)
    y conveniencia difusa (SM3-CONV en Neo4j). Todos los umbrales vienen de :CriterioExperto."""
    margen_neto = round(100.0 * (vma - precio - costo_rep) / vma, 1)
    ratio_rep = round(costo_rep / vma, 2)
    base_ind = {"precio_publicado": int(precio), "costo_reparacion": int(costo_rep), "vma_tasado": int(vma),
                "margen_neto_pct": margen_neto, "ratio_reparacion": ratio_rep}

    if ratio_rep > CE("ratio_reparacion_max", traza):
        traza["reglas"].append("R3.7: costo / VMA > CE ratio_reparacion_max → DescartarPorRiesgo")
        return {"decision": "DescartarPorRiesgo", "regla_aplicada": "R3.7",
                "motivo": f"La reparación (${costo_rep:,.0f}) supera el {CE('ratio_reparacion_max', traza):.0%} del VMA (${vma:,.0f}).",
                "indicadores": base_ind}

    if riesgo == "Alto" and demanda == "Baja":
        traza["reglas"].append("R3.8: riesgo Alto y demanda Baja → DescartarPorRiesgo")
        return {"decision": "DescartarPorRiesgo", "regla_aplicada": "R3.8",
                "motivo": "Riesgo de obsolescencia Alto con demanda comercial Baja (inmovilización de capital).",
                "indicadores": base_ind}

    # Margen requerido: paso 0 base, paso 1 R3.4 o R3.5 (excluyentes), paso 2 R3.6
    margen_req = CE("margen_base", traza)
    if demanda == "Alta" and riesgo == "Bajo":
        margen_req = CE("margen_alta_liquidez", traza)
        traza["reglas"].append("R3.4: demanda Alta y riesgo Bajo → margen requerido = CE margen_alta_liquidez")
    elif riesgo == "Alto":
        margen_req = max(margen_req, CE("margen_riesgo_alto", traza))
        traza["reglas"].append("R3.5: riesgo Alto → margen requerido = máx(margen, CE margen_riesgo_alto)")
    if n_interv >= CE("umbral_intervenciones", traza):
        margen_req += CE("prima_fallas", traza)
        traza["reglas"].append("R3.6: intervenciones ≥ CE umbral_intervenciones → + CE prima_fallas")

    contraoferta = max(0, round(vma - costo_rep - vma * margen_req / 100.0, -3))
    brecha = round(margen_neto - margen_req, 1)
    descuento = round(100.0 * (precio - contraoferta) / precio, 1) if contraoferta < precio else 0.0

    res = inferir_sm3_conv_cypher(brecha, descuento)
    if not res:
        raise RuntimeError("[ERROR INFERENCIA NEO4J] Falló la inferencia SM3-CONV.")
    score, categoria = res
    decision = {"Comprar": "Comprar", "Negociar": "ComprarConOfertaMenor", "Descartar": "DescartarPorRiesgo"}[categoria]
    traza["reglas"].append(f"SM3-CONV difusa (brecha {brecha} pp, descuento {descuento} %) → {categoria} ({score})")

    return {"decision": decision, "conveniencia_score": score, "categoria_difusa": categoria,
            "indicadores": {**base_ind, "margen_requerido_pct": margen_req, "brecha_margen_pp": brecha,
                            "descuento_requerido_pct": descuento,
                            "contraoferta_sugerida_ars": int(contraoferta) if decision == "ComprarConOfertaMenor" else None}}


# ------------------------------------------------------------------------------
# 7. Orquestador Maestro y Pipeline Integral End-to-End (PG3)
# ------------------------------------------------------------------------------
PROMPT_EXTRACTOR_INTEGRAL = """Extrae en un único objeto JSON los parámetros de la notebook para el sistema EvalTIC.
Si un dato NO aparece en el texto, poné null. No inventes valores.
Campos:
- "marca": marca comercial (string o null)
- "modelo": modelo comercial (string o null)
- "procesador": procesador tal como aparece (ej: "i5 10ma gen", "Ryzen 3 3250U") o null
- "precio_publicado": precio entero en pesos (ej: "$115.000" -> 115000)
- "anio_fabricacion": año entero (ej: 2020) o null
- "falla_catastrofica": string SOLO si no enciende o tiene motherboard/CPU/GPU quemada; sino null
- "salud_bateria_pct": entero 0-100 o null
- "ciclos_bateria": entero o null
- "temperatura_cpu_c": entero °C o null
- "thermal_throttling": bool o null
- "ram_gb": entero (4, 8, 16) o null
- "tipo_disco": "HDD" o "SSD" o null
- "pantalla_danada": bool o null
- "teclado_danado": bool o null
- "cargador_incluido": bool o null
- "soporte_windows_11": bool o null

Ejemplo:
Texto: "Vendo Acer Aspire 5 2020 i5 w11 $115.000. Batería 42% 780 ciclos, calienta 92C cuelgues térmicos, 4GB RAM, HDD 500GB, pantalla con rayas, teclado y cargador impecables."
JSON:
{"marca": "Acer", "modelo": "Aspire 5", "procesador": "i5", "precio_publicado": 115000, "anio_fabricacion": 2020, "falla_catastrofica": null, "salud_bateria_pct": 42, "ciclos_bateria": 780, "temperatura_cpu_c": 92, "thermal_throttling": true, "ram_gb": 4, "tipo_disco": "HDD", "pantalla_danada": true, "teclado_danado": false, "cargador_incluido": true, "soporte_windows_11": true}

Responde ÚNICAMENTE el JSON."""

PROMPT_SINTESIS_GERENCIAL = """Eres el Director General de EvalTIC (PG3).
Redacta un dictamen ejecutivo profesional y conciso (máximo 120 palabras) con:
- Veredicto Final (COMPRAR / NEGOCIAR CON CONTRAOFERTA / DESCARTAR / VERIFICAR ANTES DE DECIDIR).
- Resumen Técnico (SM1: viabilidad y reparaciones).
- Valuación y Mercado (SM2: VMA y riesgo/demanda).
- Estrategia Financiera (SM3: márgenes y contraoferta exacta si aplica).
Cita textualmente los números provistos. No inventes números."""

# R3.3: señales de bloqueo en el texto. El texto solo genera sospecha: hay que verificarlo en persona.
SENALES_BLOQUEO = ["icloud", "bloqueo de activ", "bloqueada", "bloqueado", "cuenta de apple",
                   "no recuerdo la cuenta", "no recuerdo la clave", "clave de bios", "contraseña de bios",
                   "bios con clave", "equipo de empresa", "administrado por", "mdm"]


def _parsear_json_llm(raw: str) -> dict:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("{"):]
    ini, fin = raw.find("{"), raw.rfind("}")
    return json.loads(raw[ini:fin + 1] if ini >= 0 and fin > ini else raw)


def extraer_datos_llm(texto: str) -> dict:
    """Extracción con el LLM; si el JSON viene mal formado reintenta una vez."""
    raw = consultar_llm(PROMPT_EXTRACTOR_INTEGRAL, texto, json_mode=True, max_tokens=260)
    try:
        return _parsear_json_llm(raw)
    except (json.JSONDecodeError, ValueError):
        raw2 = consultar_llm(PROMPT_EXTRACTOR_INTEGRAL + "\nIMPORTANTE: tu respuesta anterior no era JSON válido. "
                             "Devolvé solo el objeto JSON, sin texto adicional.", texto, json_mode=True, max_tokens=260)
        try:
            return _parsear_json_llm(raw2)
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"[ERROR PARSEO] El extractor devolvió un JSON inválido dos veces: {raw2}\nDetalle: {e}")


def _estado_decision(traza: dict) -> dict:
    """Firme solo si todos los criterios y costos usados están validados y no hubo datos inferidos ni pendientes."""
    provisionales = sorted(
        [f"{n} ({c['id']} {c['version']})" for n, c in traza["criterios_usados"].items() if c.get("estado") != "Validado"]
        + [f"costo {t} ({c['id']})" for t, c in traza["costos_usados"].items() if c.get("estado") != "Validado"])
    firme = not provisionales and not traza["datos_inferidos"] and not traza["datos_pendientes"]
    return {"estado_decision": "Firme" if firme else "Provisional", "criterios_pendientes": provisionales}


def evaluar_publicacion_integral(texto_publicacion: str, verbose: bool = True) -> dict:
    """
    Pipeline completo: Extracción LLM → filtros SM3 (bloqueo) → SM1 → SM2 → SM3 → Síntesis LLM.
    Toda la base de conocimiento (precios, costos, umbrales y reglas difusas) se lee de Neo4j.
    """
    obtener_driver_neo4j()
    cargar_conocimiento(forzar=True)  # toma los valores vigentes del grafo en cada evaluación
    traza = nueva_traza()

    if verbose:
        print("\n" + "=" * 80)
        print("  EVALTIC — ASISTENTE INTELIGENTE INTEGRADO (ORQUESTACIÓN PG3)")
        print(f"  Grafo de Conocimiento Neo4j: {TIPO_INSTANCIA} ({NEO4J_URI})")
        print("=" * 80)
        print("[Paso 1/5] Extracción de datos con el LLM...", flush=True)

    import re
    datos = extraer_datos_llm(texto_publicacion)
    txt_lower = texto_publicacion.lower()

    # Validación defensiva del precio y de la falla catastrófica contra el texto original
    match_precio = re.search(r"\$\s*([0-9]{1,3}(?:\.[0-9]{3})+|[0-9]{5,8})", texto_publicacion)
    if match_precio:
        val_p = int(match_precio.group(1).replace(".", ""))
        if datos.get("precio_publicado") is None or abs((datos.get("precio_publicado") or 0) - val_p) > 1000:
            datos["precio_publicado"] = val_p
    palabras_catastroficas = ["en corto", "quemad", "inviable", "no da video", "no enciende", "no prende",
                              "perforad", "pista rota"]
    if datos.get("falla_catastrofica") and not any(p in txt_lower for p in palabras_catastroficas):
        datos["falla_catastrofica"] = None

    marca_str = str(datos.get("marca") or "").strip().lower()
    modelo_str = str(datos.get("modelo") or "").strip().lower()
    tiene_equipo = bool(marca_str and marca_str not in ["none", "null", "generica"]) or \
                   bool(modelo_str and modelo_str not in ["none", "null", "notebook"])
    precio_val = datos.get("precio_publicado")
    if not tiene_equipo or not precio_val or precio_val <= 0:
        return {"error": "Entrada rechazada: falta marca/modelo o precio comercial válido.", "datos_extraidos": datos}

    if verbose:
        print("      Datos extraídos:")
        print("     ", json.dumps(datos, indent=6, ensure_ascii=False).replace("\n", "\n      "))

    res_sm1 = {"estado": "Sin_evaluar", "es_viable": None, "plan_reparacion": [], "costo_total": 0}
    res_sm2 = {"estado": "Sin_evaluar", "vma_estimado_ars": 0}
    precio = float(precio_val)

    # R3.3: bloqueo sospechado en el texto → verificación pendiente (no se descarta sin verificar)
    senal = next((s for s in SENALES_BLOQUEO if s in txt_lower), None)
    if senal:
        traza["reglas"].append(f"R3.3: señal de bloqueo en el aviso ('{senal}') → Verificacion_pendiente")
        res_sm3 = {"decision": "VerificacionPendiente", "regla_aplicada": "R3.3",
                   "motivo": f"El aviso sugiere un posible bloqueo ('{senal}'). Verificar en persona que el equipo "
                             "esté desvinculado antes de pagar; si el bloqueo es activo y no remediable → R3.1 (descartar).",
                   "indicadores": {"precio_publicado": int(precio)}}
    else:
        if verbose:
            print("\n[Paso 2/5] SM1 — Diagnóstico técnico y plan de reacondicionamiento...")
        res_sm1 = ejecutar_motor_sm1(datos, traza)

        if not res_sm1["es_viable"]:
            res_sm2 = {"estado": "Omitido_Por_Inviabilidad", "vma_estimado_ars": 0}
            traza["reglas"].append("R3.2: dictamen técnico insalvable → DescartarPorInviabilidad")
            res_sm3 = {"decision": "DescartarPorInviabilidad", "regla_aplicada": "R3.2", "motivo": res_sm1["motivo"],
                       "indicadores": {"precio_publicado": int(precio), "costo_reparacion": 0, "vma_tasado": 0}}
        else:
            if verbose:
                print(f"      Plan: {res_sm1['cantidad_intervenciones']} intervenciones | Costo: ${res_sm1['costo_total']:,} ARS")
                print("\n[Paso 3/5] SM2 — Valuación comercial (catálogo de Neo4j) y riesgo/demanda difusos...")
            res_sm2 = ejecutar_motor_sm2(datos, res_sm1, texto_publicacion, traza)

            if res_sm2["estado"] == "Verificacion_pendiente":
                res_sm3 = {"decision": "VerificacionPendiente", "regla_aplicada": "R3.3b",
                           "motivo": f"Falta un dato para tasar: {res_sm2['dato_faltante']}.",
                           "indicadores": {"precio_publicado": int(precio), "costo_reparacion": res_sm1["costo_total"]}}
            else:
                if verbose:
                    print(f"      Segmento: {res_sm2['segmento']} | Modelo: {res_sm2['modelo_referencia']} | "
                          f"VMA: ${res_sm2['vma_estimado_ars']:,} ARS | Riesgo: {res_sm2['riesgo_obsolescencia']} | "
                          f"Demanda: {res_sm2['demanda_comercial']}")
                    print("\n[Paso 4/5] SM3 — Evaluación financiera y conveniencia difusa...")
                res_sm3 = ejecutar_motor_sm3(precio, float(res_sm1["costo_total"]), float(res_sm2["vma_estimado_ars"]),
                                             res_sm1["cantidad_intervenciones"], res_sm2["riesgo_obsolescencia"],
                                             res_sm2["demanda_comercial"], traza)

    res_sm3.update(_estado_decision(traza))
    if res_sm3["decision"] == "VerificacionPendiente":
        res_sm3["estado_decision"] = "Pendiente"

    if verbose:
        ind = res_sm3.get("indicadores", {})
        print("\n" + "-" * 80)
        print(f"  DECISIÓN: {res_sm3['decision']} ({res_sm3['estado_decision']})")
        if res_sm3.get("motivo"):
            print(f"  Motivo: {res_sm3['motivo']}")
        if "margen_neto_pct" in ind:
            print(f"  Margen neto {ind.get('margen_neto_pct')} % | requerido {ind.get('margen_requerido_pct', '—')} % | "
                  f"contraoferta {ind.get('contraoferta_sugerida_ars') or '—'}")
        print("  Reglas activadas:")
        for r in traza["reglas"]:
            print(f"    • {r}")
        for etiqueta, clave in (("Datos inferidos", "datos_inferidos"), ("Datos a verificar", "datos_pendientes")):
            if traza[clave]:
                print(f"  {etiqueta}: " + "; ".join(traza[clave]))
        print("-" * 80)
        print("\n[Paso 5/5] Redactando el dictamen con el LLM...", flush=True)

    resumen = {
        "equipo": f"{datos.get('marca') or ''} {datos.get('modelo') or ''}".strip(),
        "precio_solicitado_ars": int(precio),
        "decision": res_sm3["decision"], "estado_decision": res_sm3["estado_decision"],
        "motivo": res_sm3.get("motivo"),
        "sm1": {"viable": res_sm1.get("es_viable"), "costo_reparacion_ars": res_sm1.get("costo_total", 0),
                "reparaciones": [t["tarea"] for t in res_sm1.get("plan_reparacion", [])]},
        "sm2": {"vma_ars": res_sm2.get("vma_estimado_ars"), "riesgo": res_sm2.get("riesgo_obsolescencia"),
                "demanda": res_sm2.get("demanda_comercial")},
        "sm3": res_sm3.get("indicadores", {}),
        "datos_a_verificar": traza["datos_pendientes"],
    }
    instruccion = f"\nVEREDICTO SIMBÓLICO: {res_sm3['decision']} (decisión {res_sm3['estado_decision'].lower()}).\n"
    if res_sm3["decision"] == "ComprarConOfertaMenor":
        ind = res_sm3["indicadores"]
        instruccion += (f"Indica contraofertar exactamente ${ind['contraoferta_sugerida_ars']:,} ARS "
                        f"({ind['descuento_requerido_pct']} % de descuento).")
    elif res_sm3["decision"] == "VerificacionPendiente":
        instruccion += f"No recomiendes comprar ni descartar todavía: indica qué verificar. Motivo: {res_sm3['motivo']}"
    elif res_sm3["decision"].startswith("Descartar"):
        instruccion += f"Recomienda no comprar. Motivo: {res_sm3.get('motivo') or 'conveniencia baja'}."
    elif res_sm3["decision"] == "Comprar":
        instruccion += "Recomienda comprar al precio pedido."
    if res_sm3["estado_decision"] == "Provisional":
        instruccion += " Aclara en una frase que los umbrales todavía son provisionales."

    dictamen = consultar_llm(PROMPT_SINTESIS_GERENCIAL + instruccion,
                             json.dumps(resumen, ensure_ascii=False), json_mode=False, max_tokens=220)
    if verbose:
        print("\n" + "=" * 80 + "\n  DICTAMEN\n" + "=" * 80)
        print(dictamen)
        print("=" * 80 + "\n")

    return {"datos_extraidos": datos, "sm1_tecnico": res_sm1, "sm2_comercial": res_sm2,
            "sm3_financiero": res_sm3, "traza": traza, "dictamen_gerencial": dictamen}


# ------------------------------------------------------------------------------
# 8. Batería de Pruebas Integradas End-to-End (5 Casos Oficiales)
#    Ya no hay atajo a los resultados guardados en el grafo: cada caso se calcula
#    y se compara con la decisión esperada.
# ------------------------------------------------------------------------------
CASOS_INTEGRADOS_PG3 = {
    "Caso 1 (Acer Aspire 5 2020 — Caso Integral con Contraoferta)":
        "Publicación: Vendo Acer Aspire 5 año 2020 con Intel i5 10ma gen (soporte Windows 11). "
        "Precio pedido: $115.000. Detalles: enciende pero la batería dura 20 minutos (salud 42%, 780 ciclos), "
        "calienta a 92°C con cuelgues térmicos. Trae 4GB de RAM y disco HDD de 500GB muy lento. "
        "El teclado tiene teclas que no responden. Pantalla y cargador impecables.",

    "Caso 2 (Lenovo ThinkPad T490 2019 — Compra Directa Aprobada)":
        "Oportunidad ThinkPad T490 2019 Core i5 8va gen, Windows 11 oficial. Piden $230.000. "
        "Equipo en estado excelente, batería al 91% con 110 ciclos, temperatura bajo carga 68°C sin throttling. "
        "Viene con 16GB RAM y SSD NVMe 512GB rápido. Pantalla y teclado perfectos con cargador original. Alta demanda corporativa.",

    "Caso 3 (Dell Inspiron 15 — Descarte por Inviabilidad Catastrófica)":
        "Dell Inspiron 15 piden $60.000 pero no da video, tiene la CPU quemada en corto insalvable y pista de placa perforada.",

    "Caso 4 (Lenovo ThinkPad T440p 2014 — Descarte por Obsolescencia e Iliquidez)":
        "Vendo ThinkPad T440p año 2014 piden $95.000. Batería agotada al 30% con 900 ciclos que requiere cambio. "
        "Sin soporte para Windows 11, equipo antiguo.",

    "Caso 5 (HP 15 Ryzen 3 2021 — Compra Aprobada con Upgrades Menores)":
        "HP 15 modelo 2021 Ryzen 3 pide $140.000. Batería al 85% y temperaturas normales. "
        "Tiene 4GB de RAM y disco HDD de 1TB. Requiere service de limpieza y upgrades estándar de memoria y SSD."
}


DECISION_ESPERADA = {
    "Caso 1": "ComprarConOfertaMenor",
    "Caso 2": "Comprar",
    "Caso 3": "DescartarPorInviabilidad",
    "Caso 4": "DescartarPorRiesgo",
    "Caso 5": "Comprar",
}


def ejecutar_bateria_pruebas():
    """Ejecuta los 5 casos y compara la decisión calculada con la esperada."""
    print("=" * 80)
    print("  BATERÍA DE PRUEBAS DE INTEGRACIÓN END-TO-END (PG3)")
    print(f"  Proveedor LLM: {LLM_PROVIDER.upper()}")
    print("=" * 80)
    filas = []
    for titulo, texto in CASOS_INTEGRADOS_PG3.items():
        print(f"\n>>> ESCENARIO: {titulo}")
        try:
            r = evaluar_publicacion_integral(texto, verbose=True)
            dec = r.get("sm3_financiero", {}).get("decision", r.get("error", "Error"))
            vma = r.get("sm2_comercial", {}).get("vma_estimado_ars", 0)
            costo_rep = r.get("sm1_tecnico", {}).get("costo_total", 0)
        except Exception as e:
            dec, vma, costo_rep = f"ERROR: {e}", 0, 0
        esperado = DECISION_ESPERADA.get(titulo.split("(")[0].strip(), "?")
        filas.append((titulo.split("(")[0].strip(), costo_rep, vma, dec, esperado))

    print("\n" + "=" * 96)
    print(f"{'Escenario':<9} | {'Costo SM1':>11} | {'VMA SM2':>11} | {'Obtenido':<26} | {'Esperado':<26} | OK")
    print("-" * 96)
    for nombre, c, v, dec, esp in filas:
        print(f"{nombre:<9} | ${c:>10,} | ${v:>10,} | {dec[:26]:<26} | {esp:<26} | {'✔' if dec == esp else '✘'}")
    print("=" * 96)
    print(f"Coinciden {sum(1 for f in filas if f[3] == f[4])} de {len(filas)} casos.\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        ejecutar_bateria_pruebas()
    elif len(sys.argv) > 1:
        evaluar_publicacion_integral(" ".join(sys.argv[1:]), verbose=True)
    else:
        print("EvalTIC — Asistente Inteligente Maestro (PG3)")
        print("Para ejecutar la batería de pruebas: python orquestador_evaltic.py --test\n")
        in_txt = input("Ingresa la publicación o descripción del equipo:\n> ")
        if in_txt.strip():
            evaluar_publicacion_integral(in_txt.strip(), verbose=True)
        else:
            ejecutar_bateria_pruebas()
