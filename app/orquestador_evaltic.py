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
  Arquitectura (patrón sándwich):
    1. Extracción (LLM): el LLM solo pasa el aviso a JSON (datos y lista de fallas).
    2. Base de conocimiento en Neo4j (Cypher): criterios expertos, costos, reglas
       difusas y catálogo de componentes (procesadores, líneas, RAM) calibrado con
       avisos reales de Mercado Libre. Nada de precios ni umbrales en Python; si el
       aviso menciona un componente que no está en el grafo, la evaluación da error.
    3. Motores simbólicos y difusos:
       - SM1 (Técnico): plan y costo de reacondicionamiento; difusa SM1-BAT / SM1-TER.
       - SM2 (Comercial): valuación por componentes en Cypher; difusa SM2-RIE / SM2-DEM.
       - SM3 (Financiero): filtros crisp, margen requerido y difusa SM3-CONV.
    4. Dictamen (LLM): redacta la síntesis con los números ya calculados
       (si el LLM falla, se arma un dictamen determinístico de respaldo).
================================================================================
"""

import os
import sys
import json
import re
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse
from dotenv import load_dotenv

# ------------------------------------------------------------------------------
# 1. Configuración de Entorno (.env)
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

# Orden explícito de búsqueda: .env de la app, .env de la raíz de este repositorio,
# fallback histórico PI4/.env y, si ninguno existe, la búsqueda preexistente de dotenv.
ENV_PATH_CANDIDATOS = (
    BASE_DIR / ".env",
    BASE_DIR.parent / ".env",
    BASE_DIR.parent / "PI4" / ".env",
)


def _resolver_env_path(candidatos=None) -> Optional[Path]:
    """Devuelve el primer archivo .env existente según el orden de precedencia."""
    for candidato in (ENV_PATH_CANDIDATOS if candidatos is None else candidatos):
        ruta = Path(candidato)
        if ruta.exists():
            return ruta
    return None


def _cargar_configuracion_entorno() -> Optional[Path]:
    """
    Carga el .env elegido sin `override`: las variables ya exportadas en el entorno
    tienen prioridad sobre el archivo, para no pisar la configuración del usuario.
    """
    ruta = _resolver_env_path()
    if ruta is not None:
        load_dotenv(ruta)
    else:
        load_dotenv()
    return ruta


ENV_PATH = _cargar_configuracion_entorno()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ==============================================================================
# Configuración Neo4j (Base de Conocimiento Obligatoria - Modo Local / Remoto)
# ==============================================================================
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

# ==============================================================================
# Consultas en Cypher sobre Neo4j (Todo se consulta en el Grafo - Sin Hardcodear)
# ==============================================================================

def consultar_fallas_catastroficas_en_grafo() -> list:
    """Consulta en Neo4j mediante Cypher las descripciones de fallas catastróficas registradas."""
    driver = obtener_driver_neo4j()
    if not driver:
        return []
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            q = "MATCH (f:FallaCatastrofica) RETURN collect(toLower(f.descripcion)) AS descripciones"
            rec = session.run(q).single()
            if rec and rec["descripciones"]:
                return rec["descripciones"]
    except Exception:
        pass
    return []


def consultar_senales_bloqueo_en_grafo() -> list:
    """Consulta en Neo4j mediante Cypher tipos y descripciones de bloqueo cargados en el grafo."""
    driver = obtener_driver_neo4j()
    senales = ["icloud", "bloqueada", "bloqueado", "cuenta", "clave de bios", "contraseña", "bios con clave", "mdm"]
    if not driver:
        return senales
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            q = "MATCH (b:Bloqueo) RETURN collect(DISTINCT toLower(b.tipo)) AS tipos"
            rec = session.run(q).single()
            if rec and rec["tipos"]:
                for t in rec["tipos"]:
                    if t and t not in senales:
                        senales.append(t)
    except Exception:
        pass
    return senales


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
                return c_val, cat_val
    except Exception:
        pass
    return None


# ------------------------------------------------------------------------------
# 2. Cliente Unificado de Modelos de Lenguaje (Solo para Parsear JSON)
# ------------------------------------------------------------------------------
# Motivos de finalización que se informan tal cual; cualquier otro se reporta como
# 'unknown' para no exponer texto arbitrario del proveedor en los errores.
_FINISH_REASON_CONOCIDOS = frozenset({
    "stop", "length", "content_filter", "tool_calls", "function_call", "error",
})

# Piso de generación exclusivo de OpenRouter: el razonamiento consume el mismo
# presupuesto de tokens, así que los pedidos chicos no alcanzan para el JSON o el texto.
OPENROUTER_HOST = "openrouter.ai"
OPENROUTER_MAX_TOKENS_MINIMO = 4096

# Desactivación real de razonamiento: solo para el host y el modelo verificados.
OPENROUTER_MODELO_SIN_RAZONAMIENTO = "nvidia/nemotron-3.5-lightning:free"


def _entero_no_negativo(valor) -> Any:
    """Devuelve el conteo si es un entero no negativo; en otro caso 'unknown'."""
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        return "unknown"
    return valor


def _metadatos_respuesta(data) -> str:
    """
    Resume SOLO metadatos seguros de la respuesta: motivo de finalización de un
    conjunto conocido y conteos de tokens de completion/razonamiento. Nunca incluye
    el texto ni el razonamiento devuelto por el modelo.
    """
    choices = data.get("choices") if isinstance(data, dict) else None
    choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    finish_reason = choice.get("finish_reason")
    # Se verifica el tipo antes de consultar el conjunto: un valor malformado (lista, dict,
    # número) no debe romper el manejo controlado ni exponerse en el mensaje.
    finish_seguro = (
        finish_reason
        if isinstance(finish_reason, str) and finish_reason in _FINISH_REASON_CONOCIDOS
        else "unknown"
    )
    usage = data.get("usage") if isinstance(data, dict) else None
    usage = usage if isinstance(usage, dict) else {}
    detalles = usage.get("completion_tokens_details")
    detalles = detalles if isinstance(detalles, dict) else {}
    reasoning_tokens = detalles.get("reasoning_tokens", usage.get("reasoning_tokens"))
    return (
        f"finish_reason={finish_seguro}; "
        f"completion_tokens={_entero_no_negativo(usage.get('completion_tokens'))}; "
        f"reasoning_tokens={_entero_no_negativo(reasoning_tokens)}"
    )


def _validar_respuesta_chat(data) -> str:
    """
    Valida la estructura choices/message/content de una respuesta compatible OpenAI.

    - Rechaza `finish_reason=length` siempre, incluso si llegó texto parcial.
    - Rechaza contenido nulo, blanco o no textual; no lo convierte en cadena vacía
      ni fabrica JSON.
    - Nunca usa el razonamiento del modelo como respuesta.
    - El error incluye únicamente metadatos seleccionados, no el cuerpo recibido.
    """
    if not isinstance(data, dict):
        raise RuntimeError(
            "[ERROR RESPUESTA LLM] Cuerpo de respuesta inválido: no es un objeto JSON. "
            f"Metadatos: {_metadatos_respuesta(data)}"
        )
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError(
            "[ERROR RESPUESTA LLM] 'choices' ausente, vacío o no es una lista. "
            f"Metadatos: {_metadatos_respuesta(data)}"
        )
    choice = choices[0]
    if not isinstance(choice, dict):
        raise RuntimeError(
            "[ERROR RESPUESTA LLM] El primer elemento de 'choices' no es un objeto. "
            f"Metadatos: {_metadatos_respuesta(data)}"
        )
    if choice.get("finish_reason") == "length":
        raise RuntimeError(
            "[ERROR RESPUESTA LLM] Respuesta truncada por límite de tokens (finish_reason=length): "
            "el texto quedó incompleto y no se usa. "
            f"Metadatos: {_metadatos_respuesta(data)}"
        )
    message = choice.get("message")
    if not isinstance(message, dict):
        raise RuntimeError(
            "[ERROR RESPUESTA LLM] 'message' ausente o inválido en la respuesta. "
            f"Metadatos: {_metadatos_respuesta(data)}"
        )
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(
            "[ERROR RESPUESTA LLM] 'content' ausente, vacío o no textual en la respuesta. "
            f"Metadatos: {_metadatos_respuesta(data)}"
        )
    return content.strip()


def consultar_llm(system_prompt: str, user_content: str, json_mode: bool = False, max_tokens: int = 300) -> str:
    """
    Envía la consulta al LLM configurado.
    El LLM se utiliza única y exclusivamente para parsear el texto a JSON.
    """
    if LLM_PROVIDER == "ollama":
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": f"{system_prompt}\n\nEntrada del usuario:\n{user_content}",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": max_tokens
            }
        }
        # Para Ollama CPU no pasamos format="json" ya que genera bloqueos/timeouts en qwen2.5.
        # _parsear_json_llm se encarga de extraer el objeto JSON del texto devuelto.

        try:
            resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
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
        host = urlparse(OPENAI_BASE_URL).hostname
        # Piso solo para OpenRouter: conserva los presupuestos mayores que pida el llamador
        # y no altera a Ollama ni a otros proveedores compatibles.
        max_tokens_efectivo = (
            max(max_tokens, OPENROUTER_MAX_TOKENS_MINIMO) if host == OPENROUTER_HOST else max_tokens
        )
        payload = {
            "model": OPENAI_MODEL,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens_efectivo
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if host == OPENROUTER_HOST and OPENAI_MODEL == OPENROUTER_MODELO_SIN_RAZONAMIENTO:
            # Desactivación real del razonamiento (no solo ocultarlo) para el modelo verificado.
            payload["reasoning"] = {"enabled": False}

        endpoint = f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions"
        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
        except Exception as e:
            raise ConnectionError(f"[ERROR CRÍTICO EVALTIC] Error de conexión con API remota ({endpoint}): {e}")

        if resp.status_code != 200:
            raise RuntimeError(f"[ERROR API REMOTA] Código {resp.status_code}: {resp.text}")

        data = resp.json()
        return _validar_respuesta_chat(data)

    else:
        raise ValueError(f"[ERROR CONFIGURACIÓN] Proveedor LLM desconocido: '{LLM_PROVIDER}'.")


# ------------------------------------------------------------------------------
# 3. Base de Conocimiento leída desde Neo4j mediante Cypher
#    Sin hardcodear precios, costos ni criterios: todo sale de los nodos
#    :CriterioExperto, :CostoReparacion, :SegmentoMercado y :ModeloReferencia.
# ------------------------------------------------------------------------------
_CONOCIMIENTO = None

# Nodos obligatorios: si falta alguno en Neo4j la evaluación se corta con error
# (no se reemplaza por un valor por defecto).
CRITERIOS_REQUERIDOS = [
    "bateria_reemplazo", "ram_objetivo", "anio_referencia", "anio_min_w11", "reval_ssd",
    "descuento_negociacion", "min_muestras_mercado",
    "margen_base", "margen_alta_liquidez", "margen_riesgo_alto",
    "umbral_intervenciones", "prima_fallas", "ratio_reparacion_max",
]
COSTOS_REQUERIDOS = ["bateria", "pantalla", "teclado", "ssd_upgrade", "ram_upgrade",
                     "service_termico", "cargador", "mano_de_obra"]


class ConocimientoFaltante(Exception):
    """El aviso menciona algo que no está en la base de conocimiento (procesador, línea, RAM)."""


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
            ". Cargá cypher/Grupo_20_PG3_mercado.cypher (en Docker: actualizar.bat).")
    _CONOCIMIENTO = {"criterios": criterios, "costos": costos}
    return _CONOCIMIENTO


def nueva_traza() -> dict:
    """Traza de la evaluación: qué datos, criterios, costos y reglas intervinieron."""
    return {"reglas": [], "criterios_usados": {}, "costos_usados": {},
            "datos_inferidos": [], "datos_pendientes": [], "referencia_mercado": None}


def CE(nombre: str, traza: dict) -> float:
    """Devuelve el valor vigente de un CriterioExperto de Neo4j y lo registra en la traza."""
    c = cargar_conocimiento()["criterios"].get(nombre)
    if not c:
        raise RuntimeError(f"[ERROR BASE DE CONOCIMIENTO] No existe el CriterioExperto '{nombre}' en Neo4j.")
    traza["criterios_usados"][nombre] = {k: c[k] for k in ("id", "valor", "unidad", "version", "estado")}
    return float(c["valor"])


def costo(tarea: str, traza: dict) -> int:
    """Devuelve el costo de una intervención desde :CostoReparacion y lo registra en la traza."""
    c = cargar_conocimiento()["costos"].get(tarea)
    if not c:
        raise RuntimeError(f"[ERROR BASE DE CONOCIMIENTO] No existe el CostoReparacion '{tarea}' en Neo4j.")
    traza["costos_usados"][tarea] = {k: c[k] for k in ("id", "costo", "version", "estado")}
    return int(c["costo"])


def consultar_mercado_componentes(procesador: str, texto: str, ram_informada: Optional[int],
                                  ram_final: int, hdd_a_ssd: bool) -> dict:
    """
    Valuación por componentes, resuelta en Cypher sobre Neo4j:
      - identifica el :Procesador (regex sobre el procesador que extrajo el LLM),
      - identifica la :Linea y su :GrupoLinea (regex sobre marca + modelo + texto),
      - toma el factor de la :CapacidadRAM final (después de los upgrades de SM1),
      - calcula valor de mercado = valor del procesador × factor de línea × factor de RAM
        y VMA = valor de mercado × (1 − CE descuento_negociacion) + CE reval_ssd si se cambia HDD por SSD.
    Devuelve lo que encontró (None en lo que no existe en el grafo).
    """
    driver = obtener_driver_neo4j()
    q = """
    WITH toLower($procesador) AS tp, toLower($texto) AS tt
    OPTIONAL MATCH (p:Procesador) WHERE tp =~ p.patron
    WITH tt, p ORDER BY p.prioridad DESC LIMIT 1
    // R2.4: sin muestras propias → generación anterior más cercana de la misma familia con datos
    OPTIONAL MATCH (v:Procesador)
      WHERE p.valor_ref_ars IS NULL AND p.anio IS NOT NULL AND v.familia = p.familia AND v <> p
        AND v.valor_ref_ars IS NOT NULL AND v.anio IS NOT NULL AND v.anio <= p.anio
    WITH tt, p, v ORDER BY v.anio DESC, v.n_muestras DESC LIMIT 1
    OPTIONAL MATCH (l:Linea) WHERE tt =~ l.patron
    WITH p, v, l ORDER BY l.prioridad DESC LIMIT 1
    OPTIONAL MATCH (l)-[:PERTENECE_A_GRUPO]->(g:GrupoLinea)
    OPTIONAL MATCH (ri:CapacidadRAM {gb: $ram_informada})
    OPTIONAL MATCH (r:CapacidadRAM {gb: $ram_final})
    MATCH (cd:CriterioExperto {nombre: 'descuento_negociacion'}), (cs:CriterioExperto {nombre: 'reval_ssd'})
    WITH p, v, l, g, ri, r, cd, cs, coalesce(p.valor_ref_ars, v.valor_ref_ars) AS valor_proc
    WITH p, v, l, g, ri, r, cd, cs, valor_proc,
         CASE WHEN valor_proc IS NOT NULL AND l IS NOT NULL AND r IS NOT NULL
              THEN valor_proc * l.factor_precio * r.factor END AS valor_mercado
    RETURN p {.nombre, .familia, .gama, .anio, .soporte_w11, .valor_ref_ars, .n_muestras,
              .fuente_valor, .estado_validacion} AS procesador,
           CASE WHEN p.valor_ref_ars IS NULL AND v IS NOT NULL
                THEN v {.nombre, .anio, .valor_ref_ars, .n_muestras} END AS generacion_anterior,
           valor_proc,
           l {.nombre, .marca, .factor_precio, .origen_factor, .estado_validacion} AS linea,
           g {.nombre, .dias_promedio_venta, .indice_repuestos} AS grupo,
           ri IS NOT NULL AS ram_informada_existe,
           r {.gb, .factor} AS ram,
           valor_mercado,
           CASE WHEN valor_mercado IS NULL THEN null
                ELSE toInteger(round((valor_mercado * (1 - cd.valor / 100.0)
                                      + CASE WHEN $hdd_a_ssd THEN cs.valor ELSE 0 END) / 1000.0)) * 1000
           END AS vma
    """
    with driver.session(database=NEO4J_DATABASE) as s:
        # "5500 U" → "5500u": el sufijo del modelo a veces viene separado del número
        procesador = re.sub(r"(\d)\s+([a-z]{1,2})\b", r"\1\2", (procesador or "").lower())
        r = s.run(q, procesador=procesador, texto=texto or "", ram_informada=ram_informada,
                  ram_final=ram_final, hdd_a_ssd=bool(hdd_a_ssd)).single()
    return dict(r) if r else {}


# ------------------------------------------------------------------------------
# 4. Módulo SM1: Diagnóstico Técnico y Reacondicionamiento (Álvaro Tapia)
#    No cataloga fallas críticas aisladas: preserva y evalúa TODAS las fallas.
# ------------------------------------------------------------------------------
def ejecutar_motor_sm1(datos: dict, traza: dict) -> dict:
    """
    Evalúa el estado físico del equipo, plan de reparaciones y costos.
    No se catalogan fallas críticas aisladas: se procesan y ponen TODAS las fallas.
    Las fallas catastróficas se consultan en Neo4j mediante Cypher.
    """
    fallas = datos.get("fallas") or []
    if not isinstance(fallas, list):
        fallas = [str(fallas)] if fallas else []

    # Consultar en Neo4j las descripciones de fallas catastróficas registradas
    catastroficas_grafo = consultar_fallas_catastroficas_en_grafo()
    criterios_insalvables = ["quemad", "en corto", "cortocircuito", "no da video", "perforad", "pista rota", "sulfataci", "insalvable"]

    falla_insalvable_hallada = None
    for f in fallas:
        f_low = str(f).lower()
        if any(cat in f_low for cat in catastroficas_grafo) or any(crit in f_low for crit in criterios_insalvables):
            falla_insalvable_hallada = f
            break

    # R1.1: Falla catastrófica detectada en la ontología del grafo → inviabilidad física
    if falla_insalvable_hallada:
        traza["reglas"].append(f"R1.1: falla insalvable detectada ('{falla_insalvable_hallada}') → Inviabilidad_Fisica_Insalvable")
        return {
            "estado": "Inviable",
            "es_viable": False,
            "regla_aplicada": "R1.1",
            "motivo": f"Falla física irreparable detectada en el grafo: {falla_insalvable_hallada}.",
            "plan_reparacion": [],
            "costo_total": 0,
            "cantidad_intervenciones": 0,
            "upgrades": {"ssd": False, "ram": False},
            "fallas": fallas
        }

    plan = []
    upgrades = {"ssd": False, "ram": False}

    def agregar(tarea: str, regla: str):
        c = costo(tarea, traza)
        desc = cargar_conocimiento()["costos"].get(tarea, {}).get("descripcion", tarea)
        plan.append({"tarea": desc, "costo": c, "regla": regla})
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

    # Upgrades del plan (consultados en Neo4j)
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

    # Mapeo de fallas informadas a tareas en CostoReparacion de Neo4j
    #  El LLM a veces lista como "falla" algo positivo ("pantalla perfecta"): esas se ignoran.
    positivos = ("perfect", "impecable", "excelente", "funciona", "sin detalle", "sin rayas", "nuev", "ok", "bien")
    fallas_negativas = [str(f).lower() for f in fallas if not any(p in str(f).lower() for p in positivos)]
    txt_fallas = " ".join(fallas_negativas)
    if datos.get("pantalla_danada") is True or any(k in txt_fallas for k in ("pantalla", "display", "raya")):
        agregar("pantalla", "Plan: pantalla dañada")
    if datos.get("teclado_danado") is True or any(k in txt_fallas for k in ("teclado", "tecla")):
        agregar("teclado", "Plan: teclado dañado")
    # El campo cargador_incluido manda; la lista de fallas solo se usa si el campo viene vacío
    cargador = datos.get("cargador_incluido")
    if cargador is False or (cargador is None and "sin cargador" in txt_fallas):
        agregar("cargador", "Plan: reposición de cargador")

    n_intervenciones = len(plan)  # la mano de obra no cuenta como intervención (R3.6)
    if plan:
        agregar("mano_de_obra", "Plan: mano de obra")

    return {
        "estado": "Viable",
        "es_viable": True,
        "plan_reparacion": plan,
        "costo_total": sum(t["costo"] for t in plan),
        "cantidad_intervenciones": n_intervenciones,
        "upgrades": upgrades,
        "fallas": fallas
    }


# ------------------------------------------------------------------------------
# 5. Módulo SM2: Valuación Comercial y Demanda (Leonel Navarta)
# ------------------------------------------------------------------------------
def ejecutar_motor_sm2(datos: dict, res_sm1: dict, texto: str, traza: dict) -> dict:
    """
    Valuación por componentes (precios de mercado relevados) y riesgo/demanda difusos.
      - Procesador, línea o RAM informados que no existen en el grafo → ConocimientoFaltante (error).
      - Procesador no informado, año desconocido o procesador sin muestras de mercado suficientes
        → Verificacion_pendiente (falta de dato ≠ valor favorable).
    """
    pendiente = lambda regla, dato: (traza["reglas"].append(f"{regla} → Verificacion_pendiente"),
                                     {"estado": "Verificacion_pendiente", "dato_faltante": dato,
                                      "vma_estimado_ars": 0})[1]

    proc_txt = str(datos.get("procesador") or "").strip()
    proc_desde_modelo = False
    if not proc_txt or proc_txt.lower() in ("null", "none"):
        # A veces el procesador viene dentro del modelo ("MacBook Air M1"): se prueba con el modelo
        proc_txt = str(datos.get("modelo") or "").strip()
        proc_desde_modelo = True
        if not proc_txt:
            return pendiente("R3.3b: procesador no informado", "Procesador del equipo (no figura en el aviso)")

    # RAM final: la que queda después del plan de SM1 (si se amplía, la de CE ram_objetivo)
    ram_objetivo = int(CE("ram_objetivo", traza))
    ram = datos.get("ram_gb")
    try:
        ram = int(ram) if ram is not None else None
    except (TypeError, ValueError):
        ram = None
    if ram is None:
        ram_final = ram_objetivo
        traza["datos_inferidos"].append(
            f"RAM no informada: se tasa con la configuración de referencia ({ram_objetivo} GB, CE ram_objetivo)")
    else:
        ram_final = ram_objetivo if res_sm1.get("upgrades", {}).get("ram") else ram
    hdd_a_ssd = bool(res_sm1.get("upgrades", {}).get("ssd"))

    texto_busqueda = " ".join(str(x) for x in (datos.get("marca"), datos.get("modelo"), texto) if x)
    ref = consultar_mercado_componentes(proc_txt, texto_busqueda, ram, ram_final, hdd_a_ssd)
    traza["referencia_mercado"] = {k: ref.get(k) for k in ("procesador", "generacion_anterior", "linea", "grupo", "ram")}
    proc, linea, grupo = ref.get("procesador"), ref.get("linea"), ref.get("grupo")

    # Lo que el aviso menciona y no está en la base de conocimiento → error explícito
    if not proc and proc_desde_modelo:
        return pendiente("R3.3b: procesador no informado", "Procesador del equipo (no figura en el aviso)")
    if proc and proc_desde_modelo:
        traza["datos_inferidos"].append(f"Procesador tomado del modelo '{proc_txt}': {proc['nombre']}")
    if not proc:
        raise ConocimientoFaltante(
            f"El procesador '{proc_txt}' no está en la base de conocimiento (Neo4j :Procesador).")
    if not linea:
        equipo = f"{datos.get('marca') or ''} {datos.get('modelo') or ''}".strip() or "sin marca"
        raise ConocimientoFaltante(
            f"La marca o línea del equipo ('{equipo}') no está en la base de conocimiento (Neo4j :Linea).")
    if ram is not None and not ref.get("ram_informada_existe"):
        raise ConocimientoFaltante(
            f"La capacidad de RAM informada ({ram} GB) no está en la base de conocimiento (Neo4j :CapacidadRAM).")
    if not ref.get("ram"):
        raise ConocimientoFaltante(
            f"La capacidad de RAM {ram_final} GB no está en la base de conocimiento (Neo4j :CapacidadRAM).")

    # Procesador reconocido pero sin avisos suficientes para tener un precio de referencia
    min_muestras = int(CE("min_muestras_mercado", traza))
    gen_ant = ref.get("generacion_anterior")
    if proc.get("valor_ref_ars") is None and not gen_ant:
        return pendiente(
            f"R3.3b: {proc['nombre']} con {proc.get('n_muestras', 0)} avisos relevados (< CE min_muestras_mercado) "
            f"y sin generación anterior con datos",
            f"Precio de mercado para {proc['nombre']} (hay {proc.get('n_muestras', 0)} avisos relevados; "
            f"se necesitan {min_muestras})")
    if gen_ant:
        traza["reglas"].append(
            f"R2.4: {proc['nombre']} sin muestras suficientes → valor de la generación anterior "
            f"{gen_ant['nombre']} (${gen_ant['valor_ref_ars']:,}, {gen_ant['n_muestras']} avisos)")
        traza["datos_inferidos"].append(
            f"Valor de {proc['nombre']} tomado de {gen_ant['nombre']} (generación anterior, supuesto conservador R2.4)")
    valor_proc = int(ref["valor_proc"])

    # Año: aviso → generación del procesador (dato inferido)
    anio = datos.get("anio_fabricacion")
    if anio is None and proc.get("anio"):
        anio = proc["anio"]
        traza["datos_inferidos"].append(f"Año estimado por el procesador {proc['nombre']} (Neo4j): {anio}")
    if anio is None:
        return pendiente("R3.3b: año de fabricación desconocido", "Año de fabricación del equipo")
    antiguedad = max(0.0, CE("anio_referencia", traza) - float(anio))

    # Soporte de Windows 11: aviso → procesador → año ≥ CE anio_min_w11
    win11 = datos.get("soporte_windows_11")
    if win11 is None:
        if proc.get("soporte_w11") is not None:
            win11 = bool(proc["soporte_w11"])
            traza["datos_inferidos"].append(f"Soporte de Windows 11 según el procesador {proc['nombre']}: {win11}")
        else:
            win11 = float(anio) >= CE("anio_min_w11", traza)
            traza["datos_inferidos"].append(f"Soporte de Windows 11 inferido por el año ({anio}): {win11}")

    repuestos = float(grupo["indice_repuestos"])
    dias_rotacion = float(grupo["dias_promedio_venta"])

    # Lógica difusa en Neo4j: riesgo de obsolescencia y demanda (encadenadas)
    res_rie = inferir_sm2_rie_cypher(antiguedad, repuestos, win11)
    if not res_rie:
        raise RuntimeError("[ERROR INFERENCIA NEO4J] Falló la inferencia SM2-RIE.")
    score_riesgo, categoria_riesgo = res_rie
    res_dem = inferir_sm2_dem_cypher(score_riesgo, dias_rotacion)
    if not res_dem:
        raise RuntimeError("[ERROR INFERENCIA NEO4J] Falló la inferencia SM2-DEM.")
    demanda = res_dem[1]

    # Criterios que usó la consulta de valuación (para la trazabilidad)
    descuento = CE("descuento_negociacion", traza)
    reval = 0
    if hdd_a_ssd:
        reval = int(CE("reval_ssd", traza))
        traza["reglas"].append("R2.3: revalorización por upgrade a SSD (CE reval_ssd)")
    traza["reglas"].append(
        f"SM2 componentes: {proc['nombre']} (${valor_proc:,}) × {linea['nombre']} ({linea['factor_precio']}) "
        f"× RAM {ram_final} GB ({ref['ram']['factor']}) − {descuento:.0f} % de negociación")

    vma = int(ref["vma"])
    print(f"      [Cypher Neo4j SM2] {proc['nombre']} · {linea['nombre']} · {ram_final} GB → VMA ${vma:,}", flush=True)
    return {
        "estado": "Tasado",
        "procesador": proc["nombre"],
        "linea": linea["nombre"],
        "grupo_linea": grupo["nombre"],
        "valor_ref_procesador_ars": valor_proc,
        "valor_desde_generacion_anterior": gen_ant["nombre"] if gen_ant else None,
        "muestras_procesador": proc.get("n_muestras"),
        "factor_linea": linea["factor_precio"],
        "origen_factor_linea": linea.get("origen_factor"),
        "ram_tasada_gb": ram_final,
        "factor_ram": ref["ram"]["factor"],
        "valor_mercado_ars": int(round(ref["valor_mercado"], -3)),
        "descuento_negociacion_pct": descuento,
        "revalorizaciones_ars": reval,
        "fuente_precio": proc.get("fuente_valor"),
        "antiguedad_anios": antiguedad,
        "riesgo_obsolescencia": categoria_riesgo,
        "score_riesgo": score_riesgo,
        "demanda_comercial": demanda,
        "dias_rotacion_estimados": dias_rotacion,
        "indice_repuestos": repuestos,
        "vma_estimado_ars": vma,
    }


# ------------------------------------------------------------------------------
# 6. Módulo SM3: Evaluación de la Operación y Decisión Final (Luciano Romero)
# ------------------------------------------------------------------------------
def ejecutar_motor_sm3(precio: float, costo_rep: float, vma: float, n_interv: int,
                       riesgo: str, demanda: str, traza: dict) -> dict:
    """Filtros crisp (R3.7, R3.8), margen requerido y conveniencia difusa en Neo4j."""
    margen_neto = round(100.0 * (vma - precio - costo_rep) / vma, 1)
    ratio_rep = round(costo_rep / vma, 2) if vma > 0 else 0.0
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
# 7. Orquestador Maestro y Pipeline Integral End-to-End
#    El LLM se encarga ÚNICA Y EXCLUSIVAMENTE de parsear el JSON.
#    El dictamen se construye determinísticamente a partir de los datos del grafo.
# ------------------------------------------------------------------------------
PROMPT_EXTRACTOR_INTEGRAL = """Extrae en un único objeto JSON los parámetros de la notebook para el sistema EvalTIC.
El LLM se encarga única y exclusivamente de parsear los datos presentes en el texto a formato JSON.
No inventes valores. Si un dato NO aparece en el texto, poné null.
No agregues comentarios en el JSON (no uses // ni /* */).
NO clasifiques ni catalogues fallas críticas: incluye en "fallas" TODAS las fallas, roturas, faltantes, deterioros o problemas informados en el texto.

Campos del JSON:
- "marca": marca comercial (string o null)
- "modelo": modelo comercial (string o null)
- "procesador": procesador copiado textual del aviso, sin completar modelos que no estén escritos (o null)
- "precio_publicado": precio entero en pesos (ej: "$115.000" -> 115000) o null
- "anio_fabricacion": año entero (ej: 2020) o null
- "salud_bateria_pct": entero 0-100 o null
- "ciclos_bateria": entero o null
- "temperatura_cpu_c": entero °C o null
- "thermal_throttling": bool o null
- "ram_gb": entero (4, 8, 16) o null
- "tipo_disco": "HDD" o "SSD" o null
- "pantalla_danada": true solo si el aviso dice que la pantalla está dañada; false si dice que está bien; si no, null
- "teclado_danado": true solo si el aviso dice que el teclado está dañado; false si dice que está bien; si no, null
- "cargador_incluido": bool o null
- "soporte_windows_11": bool o null
- "fallas": lista con TODAS las fallas, daños, desgastes o problemas reportados (lista de strings). NO incluyas cosas que están bien.

Ejemplo:
Texto: "Vendo Acer Aspire 5 2020 i5 w11 $115.000. Batería 42% 780 ciclos, calienta 92C cuelgues térmicos, 4GB RAM, HDD 500GB, pantalla con rayas, teclado roto, sin cargador."
JSON:
{"marca": "Acer", "modelo": "Aspire 5", "procesador": "i5", "precio_publicado": 115000, "anio_fabricacion": 2020, "salud_bateria_pct": 42, "ciclos_bateria": 780, "temperatura_cpu_c": 92, "thermal_throttling": true, "ram_gb": 4, "tipo_disco": "HDD", "pantalla_danada": true, "teclado_danado": true, "cargador_incluido": false, "soporte_windows_11": true, "fallas": ["batería baja duración (42%, 780 ciclos)", "calienta 92°C con cuelgues térmicos", "disco HDD", "pantalla con rayas", "teclado roto", "sin cargador"]}

Responde ÚNICAMENTE el objeto JSON."""


def _parsear_json_llm(raw: str) -> dict:
    """Extrae y parsea el objeto JSON de la salida cruda del LLM, limpiando comentarios y markdown."""
    raw = (raw or "").strip()
    if "```" in raw:
        partes = raw.split("```")
        for p in partes:
            if "{" in p and "}" in p:
                raw = p
                if raw.startswith("json"):
                    raw = raw[4:]
                break
    raw = re.sub(r"//.*", "", raw)
    raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)
    raw = re.sub(r",\s*([\]}])", r"\1", raw)
    ini, fin = raw.find("{"), raw.rfind("}")
    return json.loads(raw[ini:fin + 1] if ini >= 0 and fin > ini else raw)


def extraer_datos_llm(texto: str) -> dict:
    """
    Extracción con el LLM. El LLM se encarga ÚNICA Y EXCLUSIVAMENTE de parsear el JSON.
    Garantiza que 'fallas' contenga la lista de todas las fallas reportadas.
    """
    raw = consultar_llm(PROMPT_EXTRACTOR_INTEGRAL, texto, json_mode=False, max_tokens=1024)
    try:
        datos = _parsear_json_llm(raw)
    except (json.JSONDecodeError, ValueError):
        raw2 = consultar_llm(PROMPT_EXTRACTOR_INTEGRAL + "\nIMPORTANTE: Devolvé solo el objeto JSON, sin texto adicional.",
                             texto, json_mode=False, max_tokens=1024)
        try:
            datos = _parsear_json_llm(raw2)
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"[ERROR PARSEO] El extractor devolvió un JSON inválido dos veces: {raw2}\nDetalle: {e}")

    # Normalizar fallas para asegurar que siempre sea una lista
    fallas_val = datos.get("fallas")
    if not isinstance(fallas_val, list):
        datos["fallas"] = [str(fallas_val)] if fallas_val else []

    return datos


PROMPT_SINTESIS_GERENCIAL = """Eres el Director General de EvalTIC (PG3), sistema neuro-simbólico de evaluación y tasación de notebooks usadas.
A partir del resumen consolidado de la evaluación técnica (SM1), comercial (SM2) y financiera (SM3), redacta una síntesis ejecutiva comercial profesional, no determinista y concisa (máximo 120 palabras).

La síntesis ejecutiva debe incluir:
1. Veredicto Final claro: COMPRAR DIRECTO, NEGOCIAR CON CONTRAOFERTA, DESCARTAR POR INVIABILIDAD / RIESGO, o VERIFICAR ANTES DE DECIDIR.
2. Resumen Técnico (SM1): condición del equipo, todas las fallas reportadas y plan de reacondicionamiento necesario con sus costos.
3. Valuación y Mercado (SM2): VMA tasado, nivel de riesgo y demanda comercial.
4. Estrategia Financiera (SM3): márgenes proyectados, contraoferta sugerida si aplica o motivo de descarte/verificación.

Reglas:
- Mencioná textualmente todas las fallas y problemas informados en el resumen.
- Utilizá los valores numéricos y montos provistos en el resumen, sin inventar cifras.
- Redactá con estilo profesional, ejecutivo y directo, sin formato JSON ni etiquetas markdown innecesarias.
"""


def generar_sintesis_gerencial_llm(resumen: dict) -> str:
    """
    Genera la Síntesis General / Dictamen Ejecutivo utilizando el LLM de forma no determinista,
    basándose en el resumen de resultados simbólicos y difusos (SM1, SM2, SM3, fallas).
    En caso de contingencia o indisponibilidad del LLM, recurre a generar_dictamen_sintesis como respaldo.
    """
    resumen_json = json.dumps(resumen, ensure_ascii=False, indent=2)
    prompt_usuario = f"Resumen de evaluación para redactar la síntesis general ejecutiva:\n{resumen_json}"
    try:
        dictamen_llm = consultar_llm(
            PROMPT_SINTESIS_GERENCIAL,
            prompt_usuario,
            json_mode=False,
            max_tokens=768
        )
        if dictamen_llm and len(dictamen_llm.strip()) > 20:
            if respuesta_sin_inventos(dictamen_llm, resumen):
                return dictamen_llm.strip()
            print("      [Control anti-alucinación] El dictamen del LLM traía números que no están en el resultado "
                  "de Neo4j; se usa el dictamen determinístico.", flush=True)
    except Exception as e:
        print(f"      [Aviso Síntesis LLM] Falla al generar síntesis con LLM ({e}), recurriendo a síntesis determinística de respaldo.", flush=True)

    return generar_dictamen_sintesis(resumen)


def generar_dictamen_sintesis(resumen: dict) -> str:
    """
    Genera el Dictamen Ejecutivo Final de forma determinística a partir de los datos
    simbólicos y difusos obtenidos de Neo4j y del aviso, sin llamar al LLM.
    """
    dec = resumen["decision"]
    estado = resumen.get("estado_decision", "Firme")
    motivo = resumen.get("motivo", "")
    sm1 = resumen.get("sm1", {})
    sm2 = resumen.get("sm2", {})
    sm3 = resumen.get("sm3", {})
    fallas = resumen.get("fallas", [])

    veredicto_map = {
        "Comprar": "COMPRAR DIRECTO",
        "ComprarConOfertaMenor": "NEGOCIAR CON CONTRAOFERTA",
        "DescartarPorInviabilidad": "DESCARTAR POR INVIABILIDAD TÉCNICA",
        "DescartarPorRiesgo": "DESCARTAR POR RIESGO",
        "VerificacionPendiente": "VERIFICAR ANTES DE DECIDIR"
    }
    vered_txt = veredicto_map.get(dec, dec.upper())

    lineas = [
        f"DICTAMEN EJECUTIVO EVALTIC — {resumen.get('equipo', 'Notebook')}",
        f"• Veredicto Final: {vered_txt} (Decisión {estado.lower()})."
    ]
    if motivo:
        lineas.append(f"• Motivo: {motivo}")

    # Presentación obligatoria de TODAS las fallas detectadas
    if fallas:
        lineas.append(f"• Fallas y problemas reportados: {', '.join(str(f) for f in fallas)}.")
    else:
        lineas.append("• Fallas y problemas reportados: Ninguno (equipo en condición operativa normal).")

    # Resumen Técnico SM1
    if sm1.get("viable") is False:
        lineas.append(f"• Resumen Técnico (SM1): Inviable. {sm1.get('causa') or motivo}")
    elif sm1.get("viable") is True:
        reps = sm1.get("reparaciones", [])
        costo_r = sm1.get("costo_reparacion_ars", 0)
        reps_str = ", ".join(reps) if reps else "Ninguna requerida"
        lineas.append(f"• Resumen Técnico (SM1): Físicamente reparable. Plan: {reps_str} (Costo total: ${costo_r:,} ARS).")
    else:
        lineas.append("• Resumen Técnico (SM1): Evaluación técnica pendiente de verificación física.")

    # Valuación y Mercado SM2
    if sm2.get("vma_ars"):
        lineas.append(f"• Valuación Comercial (SM2): VMA tasado en ${sm2['vma_ars']:,} ARS | Riesgo de obsolescencia: {sm2.get('riesgo', '—')} | Demanda comercial: {sm2.get('demanda', '—')}.")
    else:
        lineas.append("• Valuación Comercial (SM2): Tasación no aplicable (operación descartada o en verificación).")

    # Estrategia Financiera SM3
    if dec == "ComprarConOfertaMenor" and sm3.get("contraoferta_sugerida_ars"):
        lineas.append(f"• Estrategia Financiera (SM3): Sugerir contraoferta exacta de ${sm3['contraoferta_sugerida_ars']:,} ARS "
                     f"(Descuento requerido: {sm3.get('descuento_requerido_pct', 0)}%, Margen neto proyectado: {sm3.get('margen_neto_pct', 0)}% vs {sm3.get('margen_requerido_pct', 0)}% requerido).")
    elif dec == "Comprar":
        lineas.append(f"• Estrategia Financiera (SM3): Operación aprobada al precio pedido (${sm3.get('precio_publicado', 0):,} ARS). "
                     f"Margen neto: {sm3.get('margen_neto_pct', 0)}% (Requerido: {sm3.get('margen_requerido_pct', 0)}%).")
    elif dec == "VerificacionPendiente":
        lineas.append("• Estrategia Financiera (SM3): No desembolsar fondos hasta completar la verificación de datos requeridos.")
    else:
        lineas.append("• Estrategia Financiera (SM3): Descartar adquisición. Los costos o el riesgo de obsolescencia superan la rentabilidad permitida.")

    if resumen.get("datos_a_verificar"):
        lineas.append(f"• Datos pendientes de validación en taller: {'; '.join(resumen['datos_a_verificar'])}.")

    return "\n".join(lineas)


def _estado_decision(traza: dict) -> dict:
    """Firme solo si todos los criterios y costos usados están validados y no hubo datos inferidos ni pendientes."""
    provisionales = sorted(
        [f"{n} ({c['id']} {c.get('version', '')})" for n, c in traza["criterios_usados"].items() if c.get("estado") != "Validado"]
        + [f"costo {t} ({c['id']})" for t, c in traza["costos_usados"].items() if c.get("estado") != "Validado"])
    firme = not provisionales and not traza["datos_inferidos"] and not traza["datos_pendientes"]
    return {"estado_decision": "Firme" if firme else "Provisional", "criterios_pendientes": provisionales}


def evaluar_publicacion_integral(texto_publicacion: str, verbose: bool = True) -> dict:
    """
    Pipeline completo neuro-simbólico:
      1. El LLM se encarga de parsear el JSON y extraer todas las fallas sin catalogar fallas críticas aisladas.
      2. Cada aviso se evalúa con la base de conocimiento de Neo4j (sin reutilizar casos guardados).
      3. Toda la base de conocimiento (costos, criterios, modelos, reglas, bloqueos) se consulta en Neo4j.
      4. El sistema preserva y pone TODAS las fallas detectadas en el informe.
      5. Síntesis general ejecutiva redactada de forma no determinista con el LLM (con fallback determinístico).
    """
    obtener_driver_neo4j()
    cargar_conocimiento(forzar=True)
    traza = nueva_traza()

    if verbose:
        print("\n" + "=" * 80)
        print("  EVALTIC — ASISTENTE INTELIGENTE INTEGRADO (ORQUESTACIÓN PG3)")
        print(f"  Grafo de Conocimiento Neo4j: {TIPO_INSTANCIA} ({NEO4J_URI})")
        print("=" * 80)
        print("[Paso 1/4] Extracción y parseo de datos estructurados con el LLM...", flush=True)

    # 1. Extracción con el LLM (único uso del LLM)
    datos = extraer_datos_llm(texto_publicacion)
    txt_lower = texto_publicacion.lower()

    # Validación defensiva del precio contra el texto original
    match_precio = re.search(r"\$\s*([0-9]{1,3}(?:\.[0-9]{3})+|[0-9]{5,8})", texto_publicacion)
    if match_precio:
        val_p = int(match_precio.group(1).replace(".", ""))
        if datos.get("precio_publicado") is None or abs((datos.get("precio_publicado") or 0) - val_p) > 1000:
            datos["precio_publicado"] = val_p

    # Validación defensiva del procesador: el LLM a veces completa un modelo que no está en el aviso
    # (ej. "Ryzen 3" → "Ryzen 3 3250U"). Solo se conservan las palabras que aparecen en el texto original.
    proc_llm = str(datos.get("procesador") or "")

    def _en_texto(tk: str) -> bool:
        if tk in txt_lower:
            return True
        m = re.match(r"(\d+)(st|nd|rd|th|ma|va|na|ta|ra|da|a|°|º)$", tk)  # "10th" ≈ "10ma" del aviso
        return bool(m and re.search(r"\b" + m.group(1) + r"\s*[a-z°º.]{0,3}\s*gen", txt_lower))

    tokens = [tk for tk in re.findall(r"[a-z0-9°º]+", proc_llm.lower()) if _en_texto(tk)]
    proc_validado = " ".join(tokens) if any(tk not in ("intel", "amd", "core", "cpu") for tk in tokens) else None
    if proc_llm and proc_validado != proc_llm.lower():
        datos["procesador"] = proc_validado

    # Validación defensiva del año: si el LLM no lo extrajo pero el aviso lo dice ("año 2021", "modelo 2021")
    if datos.get("anio_fabricacion") is None:
        m_anio = re.search(r"\b(?:año|modelo|del)\s+(20[0-3]\d)\b", txt_lower)
        if m_anio:
            datos["anio_fabricacion"] = int(m_anio.group(1))

    # Validación defensiva de la RAM: "8GB de RAM", "memoria 8GB", "16 RAM". Si el aviso lo dice, manda el texto.
    m_ram = (re.search(r"(\d{1,2})\s*(?:gb)?\s*(?:de\s*)?(?:ram|memoria)\b", txt_lower)
             or re.search(r"(?:ram|memoria)\D{0,12}?(\d{1,2})\s*gb", txt_lower))
    if m_ram:
        datos["ram_gb"] = int(m_ram.group(1))

    marca_str = str(datos.get("marca") or "").strip().lower()
    modelo_str = str(datos.get("modelo") or "").strip().lower()
    tiene_equipo = bool(marca_str and marca_str not in ["none", "null", "generica"]) or \
                   bool(modelo_str and modelo_str not in ["none", "null", "notebook"])
    precio_val = datos.get("precio_publicado")
    if not tiene_equipo or not precio_val or precio_val <= 0:
        return {"error": "Entrada rechazada: falta marca/modelo o precio comercial válido.", "datos_extraidos": datos}

    fallas_publicacion = datos.get("fallas") or []
    if not isinstance(fallas_publicacion, list):
        fallas_publicacion = [str(fallas_publicacion)] if fallas_publicacion else []

    if verbose:
        print("      Datos extraídos por el LLM:")
        print("     ", json.dumps(datos, indent=6, ensure_ascii=False).replace("\n", "\n      "))
        print(f"      Fallas reportadas ({len(fallas_publicacion)}): {fallas_publicacion}")

    precio = float(precio_val)

    todas_las_fallas = list(fallas_publicacion)
    res_sm1 = {"estado": "Sin_evaluar", "es_viable": None, "plan_reparacion": [], "costo_total": 0, "fallas": todas_las_fallas}
    res_sm2 = {"estado": "Sin_evaluar", "vma_estimado_ars": 0}

    # 2. Evaluación simbólica y difusa: cada aviso se calcula con la base de conocimiento de Neo4j
    #    (no se reutilizan resultados guardados de casos anteriores).
    if verbose:
        print("\n[Paso 2/4] Evaluación con reglas, criterios y catálogo de componentes de Neo4j...", flush=True)

    # R3.3: señal de bloqueo en el texto → verificación pendiente (no se descarta sin verificar)
    senales_bloqueo = consultar_senales_bloqueo_en_grafo()
    bloqueo_detectado = next((s for s in senales_bloqueo if s in txt_lower), None)

    if bloqueo_detectado:
        traza["reglas"].append(f"R3.3: señal de bloqueo en el aviso ('{bloqueo_detectado}') → Verificacion_pendiente")
        res_sm3 = {
            "decision": "VerificacionPendiente",
            "regla_aplicada": "R3.3",
            "motivo": f"El aviso sugiere un posible bloqueo ('{bloqueo_detectado}'). Verificar desvinculación en persona antes del pago (R3.3).",
            "indicadores": {"precio_publicado": int(precio)}
        }
    else:
        # SM1 Técnico
        res_sm1 = ejecutar_motor_sm1(datos, traza)

        if not res_sm1["es_viable"]:
            res_sm2 = {"estado": "Omitido_Por_Inviabilidad", "vma_estimado_ars": 0}
            traza["reglas"].append("R3.2: dictamen técnico insalvable → DescartarPorInviabilidad")
            res_sm3 = {
                "decision": "DescartarPorInviabilidad",
                "regla_aplicada": "R3.2",
                "motivo": res_sm1["motivo"],
                "indicadores": {"precio_publicado": int(precio), "costo_reparacion": 0, "vma_tasado": 0}
            }
        else:
            if verbose:
                print(f"      SM1: {res_sm1['cantidad_intervenciones']} intervenciones | Costo: ${res_sm1['costo_total']:,} ARS")
            # SM2 Comercial (valuación por componentes)
            try:
                res_sm2 = ejecutar_motor_sm2(datos, res_sm1, texto_publicacion, traza)
            except ConocimientoFaltante as e:
                if verbose:
                    print(f"      [ERROR BASE DE CONOCIMIENTO] {e}")
                return {"error": f"Base de conocimiento incompleta: {e}", "datos_extraidos": datos, "traza": traza}

            if res_sm2["estado"] == "Verificacion_pendiente":
                res_sm3 = {
                    "decision": "VerificacionPendiente",
                    "regla_aplicada": "R3.3b",
                    "motivo": f"Falta un dato para tasar: {res_sm2['dato_faltante']}.",
                    "indicadores": {"precio_publicado": int(precio), "costo_reparacion": res_sm1["costo_total"]}
                }
            else:
                # SM3 Financiero
                res_sm3 = ejecutar_motor_sm3(
                    precio, float(res_sm1["costo_total"]), float(res_sm2["vma_estimado_ars"]),
                    res_sm1["cantidad_intervenciones"], res_sm2["riesgo_obsolescencia"],
                    res_sm2["demanda_comercial"], traza
                )

    res_sm3.update(_estado_decision(traza))
    if res_sm3["decision"] == "VerificacionPendiente":
        res_sm3["estado_decision"] = "Pendiente"

    # 3. Síntesis General / Dictamen Ejecutivo (generado con LLM, no determinista)
    if verbose:
        print("\n[Paso 3/4] Generando síntesis general ejecutiva con LLM (no determinista)...", flush=True)

    resumen_dictamen = {
        "equipo": f"{datos.get('marca') or ''} {datos.get('modelo') or ''}".strip() or "Notebook",
        "precio_solicitado_ars": int(precio),
        "decision": res_sm3["decision"],
        "estado_decision": res_sm3["estado_decision"],
        "motivo": res_sm3.get("motivo"),
        "fallas": todas_las_fallas,
        "sm1": {
            "viable": res_sm1.get("es_viable"),
            "causa": res_sm1.get("motivo"),
            "costo_reparacion_ars": res_sm1.get("costo_total", 0),
            "reparaciones": [t.get("tarea", str(t)) for t in res_sm1.get("plan_reparacion", [])]
        },
        "sm2": {
            "vma_ars": res_sm2.get("vma_estimado_ars"),
            "riesgo": res_sm2.get("riesgo_obsolescencia"),
            "demanda": res_sm2.get("demanda_comercial")
        },
        "sm3": res_sm3.get("indicadores", {}),
        "datos_a_verificar": traza["datos_pendientes"]
    }

    dictamen = generar_sintesis_gerencial_llm(resumen_dictamen)

    if verbose:
        print("\n" + "-" * 80)
        print(f"  DECISIÓN FINAL: {res_sm3['decision']} ({res_sm3['estado_decision']})")
        if res_sm3.get("motivo"):
            print(f"  Motivo: {res_sm3['motivo']}")
        print(f"  Fallas Registradas: {todas_las_fallas}")
        ind = res_sm3.get("indicadores", {})
        if "margen_neto_pct" in ind and ind.get("margen_neto_pct") is not None:
            print(f"  Margen neto: {ind.get('margen_neto_pct')}% | Requerido: {ind.get('margen_requerido_pct', '—')}% | "
                  f"Contraoferta: {ind.get('contraoferta_sugerida_ars') or '—'}")
        print("  Reglas activadas:")
        for r in traza["reglas"]:
            print(f"    • {r}")
        print("-" * 80)
        print("\n" + "=" * 80 + "\n  DICTAMEN EJECUTIVO\n" + "=" * 80)
        print(dictamen)
        print("=" * 80 + "\n")

    return {
        "datos_extraidos": datos,
        "fallas_detectadas": todas_las_fallas,
        "sm1_tecnico": res_sm1,
        "sm2_comercial": res_sm2,
        "sm3_financiero": res_sm3,
        "traza": traza,
        "dictamen_gerencial": dictamen
    }


# ------------------------------------------------------------------------------
# 7b. Asistente unificado: System Prompt maestro de enrutamiento + flujos por submódulo
#     Punto de entrada único (CLI y web). El LLM clasifica la consulta y cada
#     submódulo sigue el patrón sándwich: prompt de extracción (JSON estricto) →
#     consulta Cypher / motor de reglas sobre Neo4j → prompt de explicación.
# ------------------------------------------------------------------------------
PROMPT_MAESTRO_ENRUTAMIENTO = """Sos el enrutador de EvalTIC, un asistente que evalúa notebooks usadas para reventa.
Tu única tarea es clasificar el mensaje del usuario en UNA intención. No respondas la consulta.
Límites: el conocimiento experto (precios, costos, umbrales y reglas) está en la base de conocimiento Neo4j;
vos nunca das valores ni recomendaciones propias.

Intenciones posibles:
- "evaluacion_integral": un aviso o una oferta de venta de una notebook con precio pedido, o la pregunta
  de si conviene comprarla. Usa los tres submódulos (técnico, comercial y decisión).
- "diagnostico_tecnico": preguntas sobre el estado físico o la reparación de una notebook (batería, temperatura,
  RAM, disco, pantalla, teclado, cargador, fallas) SIN precio de compra. Submódulo SM1.
- "valuacion_comercial": preguntas sobre cuánto vale o a cuánto se revende una notebook según su procesador,
  marca/línea o RAM, SIN pedir una decisión de compra. Submódulo SM2.
- "fuera_de_dominio": cualquier otra cosa (otros productos, charla general, pedidos sin relación).

Respondé ÚNICAMENTE un JSON: {"intencion": "<una de las cuatro>", "motivo": "<frase corta>"}"""

PROMPT_EXTRACCION_SM1 = """Extraé en un único objeto JSON los datos técnicos de la notebook que figuran en el mensaje.
Si un dato NO aparece, poné null. No inventes valores. No agregues texto fuera del JSON.
Campos:
- "marca", "modelo": string o null
- "salud_bateria_pct": entero 0-100 o null
- "ciclos_bateria": entero o null
- "temperatura_cpu_c": entero °C o null
- "thermal_throttling": bool o null
- "ram_gb": entero o null
- "tipo_disco": "HDD" o "SSD" o null
- "pantalla_danada": true/false/null
- "teclado_danado": true/false/null
- "cargador_incluido": bool o null
- "fallas": lista de fallas o problemas informados (strings); [] si no hay
Respondé ÚNICAMENTE el JSON."""

PROMPT_EXPLICACION_SM1 = """Sos el técnico de EvalTIC. Explicá al usuario, en español claro y en menos de 120 palabras,
el diagnóstico técnico de su notebook. Usá ÚNICAMENTE los datos del resultado que te paso (vienen de la base de
conocimiento Neo4j): reparaciones del plan con su costo, reglas que se activaron y datos que faltan verificar.
No inventes costos, umbrales ni reparaciones. Si hay datos pendientes, pedí que se verifiquen.
Aclarás en una frase que los costos son provisionales (todavía no validados por el experto)."""

PROMPT_EXTRACCION_SM2 = """Extraé en un único objeto JSON los datos comerciales de la notebook que figuran en el mensaje.
Si un dato NO aparece, poné null. No inventes valores ni completes modelos de procesador que no estén escritos.
No agregues texto fuera del JSON.
Campos:
- "marca", "modelo": string o null
- "procesador": procesador copiado textual del mensaje o null
- "ram_gb": entero o null
- "tipo_disco": "HDD" o "SSD" o null
- "anio_fabricacion": entero o null
- "soporte_windows_11": bool o null
Respondé ÚNICAMENTE el JSON."""

PROMPT_EXPLICACION_SM2 = """Sos el tasador de EvalTIC. Explicá al usuario, en español claro y en menos de 120 palabras,
cuánto vale su notebook en el mercado de usados y por qué. Usá ÚNICAMENTE los datos del resultado que te paso
(vienen de la base de conocimiento Neo4j): valor de referencia del procesador y cantidad de avisos relevados,
factor de la línea, factor de la RAM, valor de mercado, VMA, riesgo de obsolescencia y demanda.
No inventes precios ni factores. Si el resultado está pendiente o con error, explicá qué dato falta.
Aclarás en una frase que los valores son provisionales (relevamiento de Mercado Libre del 9/11/2026)."""

RESPUESTA_FUERA_DE_DOMINIO = ("EvalTIC solo evalúa notebooks usadas para reventa: diagnóstico técnico, valuación "
                              "comercial y decisión de compra. Pegá un aviso de venta o hacé una consulta sobre una notebook.")


def _llm_json(prompt: str, texto: str) -> dict:
    """Llama al LLM con un prompt de extracción y devuelve el JSON (reintenta una vez)."""
    for intento in range(2):
        extra = "" if intento == 0 else "\nIMPORTANTE: devolvé solo el objeto JSON, sin texto adicional."
        try:
            return _parsear_json_llm(consultar_llm(prompt + extra, texto, json_mode=False, max_tokens=220))
        except (json.JSONDecodeError, ValueError):
            continue
    raise ValueError("[ERROR PARSEO] El LLM no devolvió un JSON válido.")


def _numeros(texto: str) -> set:
    """Números de 2 o más cifras de un texto, sin separadores de miles ni decimales (1.500 / 1,500 → 1500)."""
    return {re.sub(r"[.,]", "", n).lstrip("0") for n in re.findall(r"\d[\d.,]*\d", texto)} - {""}


def respuesta_sin_inventos(texto_llm: str, resultado) -> bool:
    """Control anti-alucinación: todo número de la respuesta del LLM tiene que estar en el resultado de Neo4j."""
    return _numeros(texto_llm) <= _numeros(json.dumps(resultado, ensure_ascii=False, default=str))


def _explicar(prompt: str, resultado: dict, respaldo: str) -> str:
    """Prompt de explicación: el LLM redacta solo a partir del resultado de Neo4j.
    Si la respuesta trae un número que no está en el resultado, se descarta y se usa el respaldo determinístico."""
    try:
        txt = consultar_llm(prompt, json.dumps(resultado, ensure_ascii=False, default=str), max_tokens=220)
        if txt and len(txt.strip()) > 20:
            if respuesta_sin_inventos(txt, resultado):
                return txt.strip()
            print("      [Control anti-alucinación] La explicación del LLM traía números que no están en Neo4j; "
                  "se usa la respuesta de respaldo.", flush=True)
    except Exception as e:
        print(f"      [Aviso LLM] No se pudo redactar la explicación ({e}); se usa la respuesta de respaldo.", flush=True)
    return respaldo


def enrutar_consulta(texto: str) -> dict:
    """System Prompt maestro: clasifica la consulta. Si la salida del LLM no es válida, usa una regla de respaldo."""
    validas = {"evaluacion_integral", "diagnostico_tecnico", "valuacion_comercial", "fuera_de_dominio"}
    tiene_precio = bool(re.search(r"\$\s*\d|\d{3}\.\d{3}|\bpiden\b|\bprecio\b", texto.lower()))
    try:
        r = _llm_json(PROMPT_MAESTRO_ENRUTAMIENTO, texto)
        intencion = str(r.get("intencion", "")).strip()
        if intencion in validas:
            # Regla de consistencia: un aviso con precio siempre pasa por los tres submódulos
            if tiene_precio and intencion in ("diagnostico_tecnico", "valuacion_comercial"):
                return {"intencion": "evaluacion_integral", "origen": "regla (el mensaje tiene precio)",
                        "motivo": r.get("motivo")}
            return {"intencion": intencion, "origen": "LLM", "motivo": r.get("motivo")}
    except Exception:
        pass
    return {"intencion": "evaluacion_integral" if tiene_precio else "fuera_de_dominio",
            "origen": "regla de respaldo", "motivo": "salida del enrutador no válida"}


def consultar_sm1(texto: str, verbose: bool = True) -> dict:
    """Flujo SM1 (diagnóstico técnico): extracción → reglas y difusa SM1 en Neo4j → explicación."""
    cargar_conocimiento(forzar=True)
    traza = nueva_traza()
    datos = _llm_json(PROMPT_EXTRACCION_SM1, texto)
    res = ejecutar_motor_sm1(datos, traza)
    resultado = {"submodulo": "SM1", "viable": res.get("es_viable"), "motivo": res.get("motivo"),
                 "plan_reparacion": res.get("plan_reparacion"), "costo_total_ars": res.get("costo_total"),
                 "reglas": traza["reglas"], "datos_pendientes": traza["datos_pendientes"],
                 "datos_inferidos": traza["datos_inferidos"]}
    plan = ", ".join(f"{t['tarea']} (${t['costo']:,})" for t in res.get("plan_reparacion", [])) or "ninguna reparación"
    respaldo = (f"Diagnóstico: {res.get('motivo') or 'equipo reparable'}. Plan: {plan}. "
                f"Costo total: ${res.get('costo_total', 0):,} ARS (costos provisionales).")
    explicacion = _explicar(PROMPT_EXPLICACION_SM1, resultado, respaldo)
    if verbose:
        print("      Datos extraídos (SM1):", json.dumps(datos, ensure_ascii=False))
        print(f"      Plan: {plan} | Costo: ${res.get('costo_total', 0):,} ARS")
    return {"intencion": "diagnostico_tecnico", "datos_extraidos": datos, "sm1_tecnico": res,
            "traza": traza, "respuesta": explicacion}


def consultar_sm2(texto: str, verbose: bool = True) -> dict:
    """Flujo SM2 (valuación): extracción → consulta Cypher de componentes y difusa SM2 en Neo4j → explicación."""
    cargar_conocimiento(forzar=True)
    traza = nueva_traza()
    datos = _llm_json(PROMPT_EXTRACCION_SM2, texto)
    # Mismas validaciones contra el texto que en la evaluación integral
    txt_lower = texto.lower()
    tokens = [tk for tk in re.findall(r"[a-z0-9°º]+", str(datos.get("procesador") or "").lower()) if tk in txt_lower]
    datos["procesador"] = " ".join(tokens) if any(tk not in ("intel", "amd", "core", "cpu") for tk in tokens) else None
    try:
        res = ejecutar_motor_sm2(datos, {"upgrades": {}}, texto, traza)  # se tasa el equipo tal como está
    except ConocimientoFaltante as e:
        res = {"estado": "Error", "error": str(e), "vma_estimado_ars": 0}
    resultado = {"submodulo": "SM2", **{k: v for k, v in res.items()}, "reglas": traza["reglas"],
                 "datos_inferidos": traza["datos_inferidos"]}
    if res["estado"] == "Tasado":
        respaldo = (f"{res['procesador']} en línea {res['linea']}: valor de mercado ${res['valor_mercado_ars']:,} ARS; "
                    f"VMA ${res['vma_estimado_ars']:,} ARS. Riesgo {res['riesgo_obsolescencia']}, demanda "
                    f"{res['demanda_comercial']} (valores provisionales).")
    else:
        respaldo = f"No se pudo tasar: {res.get('error') or res.get('dato_faltante')}."
    # Pendiente o error: la respuesta es el motivo, sin pasar por el LLM (no hay números que explicar)
    explicacion = _explicar(PROMPT_EXPLICACION_SM2, resultado, respaldo) if res["estado"] == "Tasado" else respaldo
    if verbose:
        print("      Datos extraídos (SM2):", json.dumps(datos, ensure_ascii=False))
        print(f"      Resultado SM2: {res.get('estado')} | VMA ${res.get('vma_estimado_ars', 0):,} ARS")
    return {"intencion": "valuacion_comercial", "datos_extraidos": datos, "sm2_comercial": res,
            "traza": traza, "respuesta": explicacion}


def asistente_evaltic(texto: str, verbose: bool = True) -> dict:
    """Punto de entrada único: enruta la consulta y ejecuta el o los submódulos que correspondan."""
    ruta = enrutar_consulta(texto)
    if verbose:
        print(f"\n[Enrutador] Intención: {ruta['intencion']} ({ruta['origen']}) — {ruta.get('motivo') or ''}", flush=True)
    if ruta["intencion"] == "evaluacion_integral":
        r = evaluar_publicacion_integral(texto, verbose=verbose)
        r["intencion"] = "evaluacion_integral"
        r["respuesta"] = r.get("dictamen_gerencial") or r.get("error")
    elif ruta["intencion"] == "diagnostico_tecnico":
        r = consultar_sm1(texto, verbose=verbose)
    elif ruta["intencion"] == "valuacion_comercial":
        r = consultar_sm2(texto, verbose=verbose)
    else:
        r = {"intencion": "fuera_de_dominio", "respuesta": RESPUESTA_FUERA_DE_DOMINIO}
    r["enrutamiento"] = ruta
    if verbose and ruta["intencion"] != "evaluacion_integral":
        print("\n" + "=" * 80 + "\n  RESPUESTA\n" + "=" * 80 + f"\n{r['respuesta']}\n" + "=" * 80)
    return r


# ------------------------------------------------------------------------------
# 8. Batería de Pruebas Integradas End-to-End (5 Casos Oficiales)
# ------------------------------------------------------------------------------
CASOS_INTEGRADOS_PG3 = {
    "Caso 1 (Acer Aspire 5 2020 — Caso Integral con Contraoferta)":
        "Publicación: Vendo Acer Aspire 5 año 2020 con Intel i5 10ma gen (soporte Windows 11). "
        "Precio pedido: $350.000. Detalles: enciende pero la batería dura 20 minutos (salud 42%, 780 ciclos), "
        "calienta a 92°C con cuelgues térmicos. Trae 4GB de RAM y disco HDD de 500GB muy lento. "
        "El teclado y la pantalla funcionan perfecto y trae el cargador original.",

    "Caso 2 (Lenovo ThinkPad T490 2019 — Compra Directa Aprobada)":
        "Oportunidad ThinkPad T490 2019 Core i5 8va gen, Windows 11 oficial. Piden $400.000. "
        "Equipo en estado excelente, batería al 91% con 110 ciclos, temperatura bajo carga 68°C sin throttling. "
        "Viene con 16GB RAM y SSD NVMe 512GB rápido. Pantalla y teclado perfectos con cargador original. Alta demanda corporativa.",

    "Caso 3 (Dell Inspiron 15 — Descarte por Inviabilidad Catastrófica)":
        "Dell Inspiron 15 piden $150.000 pero no da video, tiene la CPU quemada en corto insalvable y pista de placa perforada.",

    "Caso 4 (Lenovo ThinkPad T470 2017 — Descarte por Obsolescencia e Iliquidez)":
        "Vendo Lenovo ThinkPad T470 año 2017 con Intel Core i5, piden $300.000. "
        "Batería agotada al 30% con 900 ciclos que requiere cambio. 4GB de RAM y disco HDD de 500GB. "
        "Sin soporte para Windows 11, equipo antiguo.",

    "Caso 5 (HP 15 Ryzen 3 2021 — Compra Aprobada con Upgrades Menores)":
        "HP 15 modelo 2021 Ryzen 3 pide $220.000. Batería al 85% y temperaturas normales. "
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
    print(f"  Proveedor LLM: {LLM_PROVIDER.upper()} (Solo Extracción y Parseo JSON)")
    print(f"  Grafo Neo4j: {TIPO_INSTANCIA} ({NEO4J_URI})")
    print("=" * 80)
    filas = []
    for titulo, texto in CASOS_INTEGRADOS_PG3.items():
        print(f"\n>>> ESCENARIO: {titulo}")
        try:
            r = evaluar_publicacion_integral(texto, verbose=True)
            dec = r.get("sm3_financiero", {}).get("decision", r.get("error", "Error"))
            vma = r.get("sm2_comercial", {}).get("vma_estimado_ars", 0)
            costo_rep = r.get("sm1_tecnico", {}).get("costo_total", 0)
            fallas_cnt = len(r.get("fallas_detectadas", []))
        except Exception as e:
            dec, vma, costo_rep, fallas_cnt = f"ERROR: {e}", 0, 0, 0
        esperado = DECISION_ESPERADA.get(titulo.split("(")[0].strip(), "?")
        filas.append((titulo.split("(")[0].strip(), costo_rep, vma, fallas_cnt, dec, esperado))

    print("\n" + "=" * 105)
    print(f"{'Escenario':<9} | {'Costo SM1':>11} | {'VMA SM2':>11} | {'Fallas':>6} | {'Obtenido':<26} | {'Esperado':<26} | OK")
    print("-" * 105)
    for nombre, c, v, f_cnt, dec, esp in filas:
        print(f"{nombre:<9} | ${c:>10,} | ${v:>10,} | {f_cnt:>6} | {dec[:26]:<26} | {esp:<26} | {'✔' if dec == esp else '✘'}")
    print("=" * 105)
    print(f"Coinciden {sum(1 for f in filas if f[4] == f[5])} de {len(filas)} casos.\n")


CONSULTAS_ENRUTAMIENTO = [
    ("La batería de mi notebook está al 45% con 850 ciclos y calienta a 90 grados. ¿Qué hay que reparar y cuánto sale?",
     "diagnostico_tecnico"),
    ("¿Cuánto vale una Lenovo ThinkPad con Intel Core i5 10ma gen y 16GB de RAM?", "valuacion_comercial"),
    (CASOS_INTEGRADOS_PG3["Caso 2 (Lenovo ThinkPad T490 2019 — Compra Directa Aprobada)"], "evaluacion_integral"),
    ("¿Me pasás una receta de empanadas?", "fuera_de_dominio"),
]


def ejecutar_pruebas_enrutador():
    """Verifica que el System Prompt maestro envíe cada consulta al submódulo correcto."""
    print("\n" + "=" * 80 + "\n  PRUEBAS DEL ENRUTADOR (System Prompt maestro)\n" + "=" * 80)
    filas = []
    for texto, esperado in CONSULTAS_ENRUTAMIENTO:
        try:
            r = asistente_evaltic(texto, verbose=False)
            obtenido = r["enrutamiento"]["intencion"]
            detalle = (r.get("sm3_financiero", {}).get("decision") or r.get("sm2_comercial", {}).get("estado")
                       or (f"plan ${r['sm1_tecnico']['costo_total']:,}" if r.get("sm1_tecnico") else "") or "—")
        except Exception as e:
            obtenido, detalle = f"ERROR: {e}", ""
        filas.append((texto[:48], obtenido, esperado, detalle))
    for t, o_, e_, d in filas:
        print(f"{'✔' if o_ == e_ else '✘'} {t:<48} → {o_:<20} (esperado {e_}) {d}")
    print(f"Enrutamiento correcto en {sum(1 for f in filas if f[1] == f[2])} de {len(filas)} consultas.\n")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        ejecutar_bateria_pruebas()
        ejecutar_pruebas_enrutador()
    elif len(sys.argv) > 1:
        asistente_evaltic(" ".join(sys.argv[1:]), verbose=True)
    else:
        print("EvalTIC — Asistente Inteligente (PG3)")
        print("Para ejecutar las pruebas: python orquestador_evaltic.py --test\n")
        in_txt = input("Escribí un aviso de venta o una consulta sobre una notebook:\n> ")
        if in_txt.strip():
            asistente_evaltic(in_txt.strip(), verbose=True)
        else:
            ejecutar_bateria_pruebas()
