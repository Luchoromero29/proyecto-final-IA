#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Casos críticos de publicaciones — pruebas offline del pipeline público (S2, S3, S7).

El corpus vive en `casos_publicaciones.json`: 60 publicaciones vagas, incompletas,
contradictorias o adversariales, agrupadas por tipo. Cada caso declara:

  - `espera`: expectativa de contrato, verificable también contra el grafo real.
  - `espera_offline`: valores que solo tienen sentido con los fixtures de este archivo.
  - `observado_hoy`: comportamiento actual de un defecto conocido (la `espera` sigue
    siendo la expectativa estricta y se comprueba que hoy NO se cumple).
  - `sonda`: caso exploratorio sin expectativa; no se ejecuta offline.

Acá se ejecuta `asistente_evaltic` con las fronteras externas simuladas (respuestas
del LLM y funciones de consulta al grafo, incluida la resolución crisp). Los adaptadores,
el encadenamiento SM1 → SM2 → SM3, las validaciones defensivas y el enrutamiento se ejecutan
de verdad. Las consultas y reglas se prueban contra Neo4j en los módulos *_neo4j.py.
La ejecución real está en `scripts/probar_publicaciones.py`.

Ejecutar desde la raíz del repositorio:
    python app/tests/test_publicaciones_criticas.py -v
"""

import json
import os
import re
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

APP_DIR = Path(__file__).resolve().parents[1]
RAIZ = APP_DIR.parent
for _ruta in (str(APP_DIR), str(RAIZ)):
    if _ruta not in sys.path:
        sys.path.insert(0, _ruta)

# ------------------------------------------------------------------------------
# Aislamiento previo a la importación del motor: sin red ni .env real
# ------------------------------------------------------------------------------
ENTORNO_PRUEBA = {
    "LLM_PROVIDER": "ollama",
    "OLLAMA_URL": "http://ollama.invalid/api/generate",
    "OLLAMA_MODEL": "modelo-ollama-de-prueba",
    "NEO4J_TARGET": "local",
    "NEO4J_LOCAL_URI": "bolt://neo4j.invalid:7687",
    "NEO4J_LOCAL_USERNAME": "usuario-de-prueba",
    "NEO4J_LOCAL_PASSWORD": "clave-ficticia-neo4j",
    "NEO4J_LOCAL_DATABASE": "neo4j",
}
for _clave, _valor in ENTORNO_PRUEBA.items():
    os.environ.setdefault(_clave, _valor)

with mock.patch("dotenv.load_dotenv", return_value=False):
    import orquestador_evaltic as oe

# El verificador de expectativas vive en el ejecutor: una sola fuente para offline y real.
from scripts.probar_publicaciones import (  # noqa: E402  (módulo sin efectos de import)
    CLAVES_ESPERA, TIPOS_RESULTADO, _comprobar, validar_espera,
)

CORPUS = json.loads((APP_DIR / "tests" / "casos_publicaciones.json").read_text(encoding="utf-8"))
CASOS = {caso["id"]: caso for caso in CORPUS["casos"]}
GRUPOS_VALIDOS = set(CORPUS["grupos"])
CLASIFICACIONES = {"aceptacion", "caracterizacion", "defecto_conocido", "sonda"}

# ------------------------------------------------------------------------------
# Fixtures del grafo: misma forma que las consultas Cypher, valores de prueba
# ------------------------------------------------------------------------------
DESCRIPCIONES = {
    "bateria": "Reemplazo de batería",
    "pantalla": "Reemplazo de módulo de pantalla",
    "teclado": "Reemplazo de teclado",
    "ssd_upgrade": "Reemplazo de HDD por SSD 480 GB",
    "ram_upgrade": "Ampliación de RAM a 8 GB",
    "service_termico": "Service térmico (pasta térmica y limpieza)",
    "cargador": "Cargador compatible",
    "mano_de_obra": "Mano de obra y control de calidad",
}
COSTOS_PRUEBA = {"bateria": 60000, "pantalla": 180000, "teclado": 45000, "ssd_upgrade": 50000,
                 "ram_upgrade": 40000, "service_termico": 30000, "cargador": 25000, "mano_de_obra": 20000}
CRITERIOS_PRUEBA = {
    "bateria_reemplazo": 70, "ram_objetivo": 8, "anio_referencia": 2026, "anio_min_w11": 2019,
    "reval_ssd": 15000, "descuento_negociacion": 10, "min_muestras_mercado": 5,
    "margen_base": 12, "margen_alta_liquidez": 10, "margen_riesgo_alto": 18,
    "umbral_intervenciones": 3, "prima_fallas": 5, "ratio_reparacion_max": 0.5,
    # Caídas sintéticas de frecuencia: criterios del grafo (CE-31 / CE-32), no constantes de Python.
    "caida_termica_sin_throttling": 5, "caida_termica_con_throttling": 20,
}
CONOCIMIENTO_FALSO = {
    "criterios": {nombre: {"id": f"CE-{i:02d}", "valor": valor, "unidad": "fixture",
                           "version": "prueba", "estado": "Validado"}
                  for i, (nombre, valor) in enumerate(CRITERIOS_PRUEBA.items(), start=1)},
    "costos": {tarea: {"id": f"COS-{tarea[:3].upper()}", "costo": COSTOS_PRUEBA[tarea],
                       "descripcion": DESCRIPCIONES[tarea], "version": "prueba", "estado": "Validado"}
               for tarea in COSTOS_PRUEBA},
}
SENALES_BLOQUEO_FALSAS = ["icloud", "bloqueada", "bloqueado", "cuenta", "clave de bios", "mdm"]

# ------------------------------------------------------------------------------
# Inferencia de SM1: el catálogo de patrones vive en el grafo
# (cypher/Grupo_20_PG3_diagnostico.cypher). Acá se replica la forma del contrato de las
# consultas para probar el cableado del pipeline sin Neo4j; la inferencia real se prueba
# contra el grafo aislado en test_diagnostico_neo4j.py y test_sm1_neo4j.py.
# (identificador, tratamiento, regex, descripción, tarea, orden, síntoma)
PATRONES_SM1_PRUEBA = (
    ("PT-CAT-NO-VIDEO", "inviable", r"no\s+da\s+video", "No da video", None, 1, None),
    ("PT-CAT-QUEMADO", "inviable", r"quemad", "Componente quemado", None, 1, None),
    ("PT-CAT-CORTO", "inviable", r"\ben\s+corto\b", "Componente en cortocircuito", None, 1, None),
    ("PT-CAT-PERFORADO", "inviable", r"perforad", "Placa perforada", None, 1, None),
    ("PT-CAT-PISTA-ROTA", "inviable", r"pista\s+rota", "Pista de placa rota", None, 1, None),
    ("PT-CAT-SULFATACION", "inviable", r"sulfataci", "Sulfatación por derrame", None, 1, None),
    ("PT-CAT-INSALVABLE", "inviable", r"insalvable", "Falla declarada insalvable", None, 1, None),
    ("PT-SIN-NO-PRENDE", "verificar", r"\bno\s+prende\b", "No prende", None, 1, ("FS-NO-PRENDE", "No prende")),
    ("PT-SIN-NO-CARGA", "verificar", r"\bno\s+carga\b", "No carga", None, 1, ("FS-NO-CARGA", "No carga")),
    ("PT-SIN-SE-APAGA", "verificar", r"\bse\s+apaga(\s+sola|\s+solo)?\b", "Se apaga sola", None, 1,
     ("FS-SE-APAGA-SOLA", "Se apaga sola")),
    ("PT-INT-PANTALLA", "intervencion", r"\b(pantalla|display|rayas?)\b", "Pantalla dañada", "pantalla", 5, None),
    ("PT-INT-TECLADO", "intervencion", r"\b(teclado|tecla|teclas)\b", "Teclado dañado", "teclado", 6, None),
    ("PT-INT-CARGADOR", "intervencion", r"sin\s+cargador", "Sin cargador", "cargador", 7, None),
    ("PT-INT-BATERIA", "intervencion",
     r"bater[ií]a\s+(agotad|agotada|muert|dañad|dañada|hinchad|hinchada|inflad|baja|no\s+retiene)",
     "Batería agotada o degradada", "bateria", 1, None),
    ("PT-INT-DISCO", "intervencion", r"(\bhdd\b|disco\s+(r[ií]gido|mec[aá]nico))", "Disco mecánico",
     "ssd_upgrade", 4, None),
    ("PT-INT-TERMICO", "intervencion", r"\b(calienta|sobrecalienta|t[eé]rmicos?)\b", "Sobrecalentamiento",
     "service_termico", 2, None),
    ("PT-DESC-BATERIA-MEDIDA", "descartar", r"bater[ií]a\s+(al\s+)?\d{1,3}\s*%",
     "Nivel de batería medido en el aviso (lo evalúa SM1-BAT)", None, 0, None),
    ("PT-DESC-POSITIVO", "descartar", r"\b(perfect[oa]s?|impecables?|excelentes?|funciona|funcionando)\b",
     "Descripción positiva", None, 0, None),
    ("PT-DESC-SIN-DETALLES", "descartar", r"\bsin\s+(detalles?|rayas?)\b", "Sin detalles ni rayas", None, 0, None),
    ("PT-DESC-NUEVO", "descartar", r"\bnuev[oa]s?\b", "Componente nuevo", None, 0, None),
    ("PT-DESC-CONFORME", "descartar", r"\b(ok|bien)\b", "Estado conforme", None, 0, None),
    ("PT-DESC-SIN-FALLAS", "descartar", r"(no\s+tiene\s+fallas|sin\s+fallas|ninguna\s+falla)", "Sin fallas",
     None, 0, None),
)

# Diagnósticos que el operador puede confirmar (el costo sale de :CostoReparacion del grafo).
DIAGNOSTICOS_SM1_PRUEBA = {
    "bateria": ("DIA-BATERIA", True, "bateria", 1),
    "cargador": ("DIA-CARGADOR", True, "cargador", 7),
    "pantalla": ("DIA-PANTALLA", True, "pantalla", 5),
    "teclado": ("DIA-TECLADO", True, "teclado", 6),
    "termico": ("DIA-TERMICO", True, "service_termico", 2),
    "almacenamiento": ("DIA-ALMACENAMIENTO", True, "ssd_upgrade", 4),
    "placa": ("DIA-PLACA", False, None, 50),
}


def _evidencias_sm1_falsas(evidencias, campos):
    """Misma forma que la consulta Cypher de evidencias de SM1."""
    filas = []
    for ev in evidencias:
        texto = " ".join(str(ev["texto"]).lower().split())
        for ident, tratamiento, patron, descripcion, tarea, orden, sintoma in PATRONES_SM1_PRUEBA:
            if ev["origen"] != "falla" and tratamiento not in ("inviable", "verificar"):
                continue
            if not re.search(patron, texto):
                continue
            filas.append({
                "texto": ev["texto"], "origen": ev["origen"], "patron": ident, "descripcion": descripcion,
                "tratamiento": tratamiento,
                # El campo estructurado manda sobre el texto del aviso.
                "aplicable": not (ident == "PT-INT-CARGADOR" and campos.get("cargador_incluido") is True),
                "sintoma": sintoma[0] if sintoma else None,
                "sintoma_descripcion": sintoma[1] if sintoma else None,
                "regla": {"inviable": "R1.1", "verificar": "R3.3c"}.get(tratamiento),
                "intervencion": "INT-" + ident[3:] if tarea else None,
                "tarea": tarea, "tarea_descripcion": DESCRIPCIONES.get(tarea),
                "descripcion_costo": DESCRIPCIONES.get(tarea), "costo_ars": COSTOS_PRUEBA.get(tarea),
                "costo_id": CONOCIMIENTO_FALSO["costos"][tarea]["id"] if tarea else None,
                "costo_version": "prueba" if tarea else None,
                "costo_estado": "Validado" if tarea else None,
                "patron_estado": "Provisional", "patron_version": "v1", "orden": orden,
            })
    return filas


def _reglas_sm1_falsas(hechos):
    """Misma forma que la consulta Cypher de reglas estructuradas de SM1."""
    filas = []

    def agregar(tarea, regla, orden, criterio=None, requiere_plan=False, cuenta=True, campo=None):
        filas.append({
            "tarea": tarea, "descripcion": DESCRIPCIONES[tarea], "costo_ars": COSTOS_PRUEBA[tarea],
            "costo_id": CONOCIMIENTO_FALSO["costos"][tarea]["id"], "costo_version": "prueba",
            "costo_estado": "Validado", "regla": regla, "orden": orden,
            "requiere_plan": requiere_plan, "cuenta_como_intervencion": cuenta,
            "criterio_nombre": criterio, "criterio_id": CONOCIMIENTO_FALSO["criterios"][criterio]["id"]
            if criterio else None,
            "criterio_valor": CRITERIOS_PRUEBA.get(criterio), "criterio_unidad": "fixture" if criterio else None,
            "criterio_version": "prueba" if criterio else None,
            "criterio_estado": "Validado" if criterio else None,
        })

    salud, ciclos = hechos.get("salud"), hechos.get("ciclos")
    if hechos.get("categoria_bat") == "Obligatoria":
        agregar("bateria", "SM1-BAT", 1)
    elif salud is not None and ciclos is None and float(salud) < CRITERIOS_PRUEBA["bateria_reemplazo"]:
        agregar("bateria", "SM1-BAT-CRISP", 1, criterio="bateria_reemplazo")
    if hechos.get("categoria_ter") in ("Obligatoria", "Recomendada"):
        agregar("service_termico", "SM1-TER", 2)
    elif hechos.get("temp") is None and hechos.get("throttling") is True:
        agregar("service_termico", "SM1-TER-CRISP", 2)
    ram = hechos.get("ram")
    if ram is not None and float(ram) < CRITERIOS_PRUEBA["ram_objetivo"]:
        agregar("ram_upgrade", "SM1-RAM-ACCION", 3, criterio="ram_objetivo")
    if str(hechos.get("disco") or "").upper() == "HDD":
        agregar("ssd_upgrade", "SM1-DISCO-ACCION", 4)
    campos = hechos.get("campos") or {}
    for campo, valor, tarea, orden in (("pantalla_danada", True, "pantalla", 5),
                                       ("teclado_danado", True, "teclado", 6),
                                       ("cargador_incluido", False, "cargador", 7)):
        if campos.get(campo) is valor:
            agregar(tarea, "SM1-" + tarea.upper() + "-ACCION", orden, campo=campo)
    agregar("mano_de_obra", "SM1-MANO-OBRA-ACCION", 9, requiere_plan=True, cuenta=False)
    return filas


def _diagnosticos_sm1_falsos(diagnosticos):
    """Misma forma que la consulta Cypher de diagnósticos confirmados por el operador."""
    filas = []
    for solicitado in diagnosticos:
        base = DIAGNOSTICOS_SM1_PRUEBA.get(str(solicitado).strip().lower())
        fila = {"solicitado": solicitado, "id": None, "nombre": None, "descripcion": None, "reparable": None,
                "motivo": None, "orden": 50, "tarea": None, "descripcion_costo": None, "costo_ars": None,
                "costo_id": None, "costo_version": None, "costo_estado": None, "regla": None}
        if base:
            identificador, reparable, tarea, orden = base
            fila.update({"id": identificador, "nombre": str(solicitado).strip().lower(),
                         "descripcion": DESCRIPCIONES.get(tarea), "reparable": reparable, "orden": orden,
                         "regla": "R1.1" if not reparable else None,
                         "motivo": "Daño irreparable confirmado en la verificación técnica" if not reparable else None})
            if tarea:
                fila.update({"tarea": tarea, "descripcion_costo": DESCRIPCIONES[tarea],
                             "costo_ars": COSTOS_PRUEBA[tarea],
                             "costo_id": CONOCIMIENTO_FALSO["costos"][tarea]["id"],
                             "costo_version": "prueba", "costo_estado": "Validado"})
        filas.append(fila)
    return filas
CATALOGO_PROCESADORES = {
    "i5 10ma gen": {"nombre": "Intel Core i5-1035G1", "anio": 2020, "soporte_w11": True,
                    "valor_ref_ars": 250000, "n_muestras": 12},
    "i5": {"nombre": "Intel Core i5 (generación no informada)", "anio": None, "soporte_w11": None,
           "valor_ref_ars": 150000, "n_muestras": 9},
    "ryzen 3": {"nombre": "AMD Ryzen 3 3250U", "anio": 2021, "soporte_w11": True,
                "valor_ref_ars": 180000, "n_muestras": 8},
    "ryzen 7 5700u": {"nombre": "AMD Ryzen 7 5700U", "anio": 2021, "soporte_w11": True,
                      "valor_ref_ars": None, "n_muestras": 2},
    "m1": {"nombre": "Apple M1", "anio": 2020, "soporte_w11": False,
           "valor_ref_ars": 520000, "n_muestras": 7},
}
# (clave textual, nombre de línea, factor, grupo, días de venta, índice de repuestos)
LINEAS_FALSAS = (
    ("thinkpad", "ThinkPad", 1.2, "GRP-CORP", 25, 0.8),
    ("aspire", "Aspire", 0.9, "GRP-CONSUMO", 40, 0.5),
    ("inspiron", "Inspiron", 0.9, "GRP-CONSUMO", 40, 0.5),
    ("hp", "HP 15/240/250", 0.85, "GRP-CONSUMO", 40, 0.5),
    ("vivobook", "VivoBook", 0.95, "GRP-CONSUMO", 40, 0.5),
    ("macbook", "MacBook Air", 1.35, "GRP-PREMIUM", 20, 1.0),
)
# Factores del catálogo real (:CapacidadRAM, 8 GB = 1,00); 10 y 48 GB no existen.
FACTORES_RAM = {2: 0.80, 4: 0.90, 6: 0.93, 8: 1.00, 12: 1.04, 16: 1.08, 20: 1.10,
                24: 1.12, 32: 1.15, 40: 1.17, 64: 1.20}
TEXTO_EXPLICACION_FALSO = "Dictamen ejecutivo de prueba, sin cifras ni montos."


def _valuacion_falsa(procesador, modelo, texto, ram_informada, ram_ampliada, hdd_a_ssd,
                     anio_informado, soporte_w11_informado, traza=None,
                     ram_final_fijada=None, aplicar_politica_ram=True):
    """Devuelve la misma forma que la consulta Cypher de valuación, con fixtures.

    No simula R2.4: el catálogo de prueba ya trae el componente que corresponde a cada
    aviso y los procesadores sin muestras quedan sin precio. La RAM tasada, el año, el
    soporte de Windows 11 y el estado replican la política porque son el contrato que
    consume el motor; la política real se comprueba contra Neo4j en test_sm2_neo4j.py.
    """
    aviso_proc = str(procesador or "").strip()
    modelo_txt = str(modelo or "").strip()
    origen_proc = "aviso" if aviso_proc else "modelo"
    proc = CATALOGO_PROCESADORES.get((aviso_proc or modelo_txt).lower())
    linea = next((l for l in LINEAS_FALSAS if l[0] in str(texto or "").lower()), None)
    ram_objetivo = CRITERIOS_PRUEBA["ram_objetivo"]
    if not aplicar_politica_ram:
        ram_final, ram_origen = ram_final_fijada, "fijada"
    elif ram_informada is None:
        ram_final, ram_origen = ram_objetivo, "referencia"
    elif ram_ampliada:
        ram_final, ram_origen = ram_objetivo, "ampliada"
    else:
        ram_final, ram_origen = ram_informada, "aviso"
    factor_ram = FACTORES_RAM.get(ram_final)
    ram_informada_existe = ram_informada in FACTORES_RAM
    valor_proc = (proc or {}).get("valor_ref_ars")
    # Igual que el Cypher: valor del procesador × factor de línea × factor de RAM.
    valor = None
    if valor_proc is not None and linea and factor_ram:
        valor = valor_proc * linea[2] * factor_ram
    reval = CRITERIOS_PRUEBA["reval_ssd"] if hdd_a_ssd else 0
    vma = None
    if valor is not None:
        vma = int(round((valor * (1 - CRITERIOS_PRUEBA["descuento_negociacion"] / 100.0)
                         + reval) / 1000.0)) * 1000
    anio = anio_informado if anio_informado is not None else (proc or {}).get("anio")
    anio_origen = "aviso" if anio_informado is not None else "procesador"
    if soporte_w11_informado is not None:
        win11, w11_origen = bool(soporte_w11_informado), "aviso"
    elif (proc or {}).get("soporte_w11") is not None:
        win11, w11_origen = bool(proc["soporte_w11"]), "procesador"
    else:
        win11 = None if anio is None else anio >= CRITERIOS_PRUEBA["anio_min_w11"]
        w11_origen = "anio"
    antiguedad = None
    if anio is not None:
        antiguedad = max(0.0, float(CRITERIOS_PRUEBA["anio_referencia"] - anio))
    if proc is None and origen_proc == "modelo":
        estado, motivo = "Verificacion_pendiente", "procesador_no_informado"
    elif proc is None:
        estado, motivo = "ConocimientoFaltante", "procesador_desconocido"
    elif linea is None:
        estado, motivo = "ConocimientoFaltante", "linea_desconocida"
    elif ram_informada is not None and not ram_informada_existe:
        estado, motivo = "ConocimientoFaltante", "ram_informada_desconocida"
    elif factor_ram is None:
        estado, motivo = "ConocimientoFaltante", "ram_tasada_desconocida"
    elif valor_proc is None:
        estado, motivo = "Verificacion_pendiente", "procesador_sin_muestras"
    elif anio is None:
        estado, motivo = "Verificacion_pendiente", "anio_desconocido"
    else:
        estado, motivo = "Tasado", None
    conocimiento_completo = (proc is not None and linea is not None and factor_ram is not None
                             and not (ram_informada is not None and not ram_informada_existe))
    usados = []
    if aviso_proc or modelo_txt:
        usados.append("ram_objetivo")
    if (aviso_proc or modelo_txt) and conocimiento_completo:
        usados.append("min_muestras_mercado")
    if estado == "Tasado":
        usados.append("anio_referencia")
        usados.append("descuento_negociacion")
        if hdd_a_ssd:
            usados.append("reval_ssd")
        if w11_origen == "anio":
            usados.append("anio_min_w11")
    return {
        "estado": estado,
        "motivo_clave": motivo,
        "procesador": dict(proc) if proc else None,
        "procesador_origen": origen_proc,
        "generacion_anterior": None,
        "valor_origen": "propio" if proc else None,
        "valor_proc": valor_proc,
        "linea": {"nombre": linea[1], "marca": linea[0], "factor_precio": linea[2],
                  "origen_factor": "fixture", "estado_validacion": "Provisional"} if linea else None,
        "grupo": {"nombre": linea[3], "dias_promedio_venta": linea[4], "indice_repuestos": linea[5]}
        if linea else None,
        "ram_informada_existe": ram_informada_existe,
        "ram": {"gb": ram_final, "factor": factor_ram} if factor_ram else None,
        "ram_final": ram_final,
        "ram_origen": ram_origen,
        "anio": anio,
        "anio_origen": anio_origen,
        "soporte_w11": win11,
        "w11_origen": w11_origen,
        "antiguedad": antiguedad,
        "valor_mercado": valor,
        "vma": vma,
        "revalorizacion_ssd": reval,
        "criterios_usados": usados,
        "criterios": {nombre: float(CRITERIOS_PRUEBA[nombre]) for nombre in
                      ("ram_objetivo", "anio_referencia", "anio_min_w11", "min_muestras_mercado",
                       "descuento_negociacion", "reval_ssd")},
    }


# Campos que devuelve la consulta Cypher de componentes (contrato público de SM2).
CAMPOS_VALUACION = {"estado", "motivo_clave", "procesador", "procesador_origen",
                    "generacion_anterior", "valor_origen", "valor_proc", "linea", "grupo",
                    "ram_informada_existe", "ram", "ram_final", "ram_origen", "anio",
                    "anio_origen", "soporte_w11", "w11_origen", "antiguedad", "valor_mercado",
                    "vma", "revalorizacion_ssd", "criterios_usados", "criterios"}


# Las inferencias difusas devuelven (centroide, categoría), como el Cypher real.
def _sm1_bat_falso(salud, ciclos):
    return (0.8, "Obligatoria") if salud < 70 else (0.2, "No requerida")


def _sm1_ter_falso(temperatura, caida):
    return (0.9, "Obligatoria") if temperatura >= 90 else (0.1, "No requerida")


def _sm2_rie_falso(antiguedad, repuestos, win11):
    return (0.85, "Alto") if antiguedad >= 8 else (0.15, "Bajo")


def _sm2_dem_falso(riesgo, rotacion):
    return (0.8, "Alta") if rotacion < 30 else (0.2, "Baja")


def _sm3_conv_falso(brecha, descuento):
    if brecha >= 5:
        return 0.9, "Comprar"
    if brecha >= 0:
        return 0.6, "Negociar"
    return 0.2, "Descartar"


def _sm3_criterio(nombre):
    """Un :CriterioExperto con la forma que devuelve el Cypher, con el valor del fixture."""
    return dict(CONOCIMIENTO_FALSO["criterios"][nombre], nombre=nombre)

def _sm3_crisp_falso(driver, base, precio, costo_rep, vma, n_interv, riesgo, demanda):
    """Doble de CONSULTA_CRISP: misma aritmética, cuantización, política y procedencia."""
    c = {nombre: datos["valor"] for nombre, datos in CONOCIMIENTO_FALSO["criterios"].items()}
    ratio_max = c["ratio_reparacion_max"]
    if vma == 0:
        # La consulta real informa la división por cero; el adapter reproduce la excepción.
        return {"division_por_cero": True, "regla": None, "decision": None, "margen_neto": None,
                "ratio_reparacion": None, "margen_req": None, "brecha": None, "descuento": None,
                "contraoferta": None, "ratio_max": ratio_max, "reglas_activadas": [], "criterios": []}

    margen_neto = round(100.0 * (vma - precio - costo_rep) / vma, 1)
    ratio_rep = round(costo_rep / vma, 2) if vma > 0 else 0.0
    descartar = {"division_por_cero": False, "ratio_reparacion": ratio_rep, "margen_neto": margen_neto,
                 "margen_req": None, "brecha": None, "descuento": None, "contraoferta": None,
                 "ratio_max": ratio_max}
    if ratio_rep > ratio_max:
        return dict(descartar, decision="DescartarPorRiesgo", regla="R3.7",
                    reglas_activadas=["R3.7: costo / VMA > CE ratio_reparacion_max → DescartarPorRiesgo"],
                    criterios=[_sm3_criterio("ratio_reparacion_max")])
    if riesgo == "Alto" and demanda == "Baja":
        return dict(descartar, decision="DescartarPorRiesgo", regla="R3.8",
                    reglas_activadas=["R3.8: riesgo Alto y demanda Baja → DescartarPorRiesgo"],
                    criterios=[_sm3_criterio("ratio_reparacion_max")])

    reglas, criterios = [], [_sm3_criterio("ratio_reparacion_max"), _sm3_criterio("margen_base")]
    if demanda == "Alta" and riesgo == "Bajo":
        margen_paso1 = c["margen_alta_liquidez"]
        criterios.append(_sm3_criterio("margen_alta_liquidez"))
        reglas.append("R3.4: demanda Alta y riesgo Bajo → margen requerido = CE margen_alta_liquidez")
    elif riesgo == "Alto":
        margen_paso1 = max(c["margen_base"], c["margen_riesgo_alto"])
        criterios.append(_sm3_criterio("margen_riesgo_alto"))
        reglas.append("R3.5: riesgo Alto → margen requerido = máx(margen, CE margen_riesgo_alto)")
    else:
        margen_paso1 = c["margen_base"]
    criterios.append(_sm3_criterio("umbral_intervenciones"))
    margen_req = margen_paso1
    if n_interv >= c["umbral_intervenciones"]:
        margen_req += c["prima_fallas"]
        criterios.append(_sm3_criterio("prima_fallas"))
        reglas.append("R3.6: intervenciones ≥ CE umbral_intervenciones → + CE prima_fallas")

    contraoferta = max(0, round(vma - costo_rep - vma * margen_req / 100.0, -3))
    descuento = round(100.0 * (precio - contraoferta) / precio, 1) if contraoferta < precio else 0.0
    return dict(descartar, decision=None, regla=None, margen_req=float(margen_req),
                brecha=round(margen_neto - margen_req, 1), descuento=descuento,
                contraoferta=float(contraoferta), reglas_activadas=reglas, criterios=criterios)

def _sm3_decision_falsa(driver, base, categoria, contraoferta):
    """Doble de CONSULTA_DECISION: mapeo de la categoría difusa y contraoferta habilitada."""
    return {"decision": {"Comprar": "Comprar", "Negociar": "ComprarConOfertaMenor",
                          "Descartar": "DescartarPorRiesgo"}[categoria],
            "contraoferta_sugerida_ars": contraoferta if categoria == "Negociar" else None}


def _llm_falso(extraccion, intencion_router):
    """Responde por familia de prompt: extracción, enrutador o redacción."""
    def responder(system_prompt, user_content, json_mode=False, max_tokens=300):
        if system_prompt.startswith((oe.PROMPT_EXTRACTOR_INTEGRAL, oe.PROMPT_EXTRACCION_SM1,
                                     oe.PROMPT_EXTRACCION_SM2)):
            return json.dumps(extraccion, ensure_ascii=False)
        if system_prompt.startswith(oe.PROMPT_MAESTRO_ENRUTAMIENTO):
            return json.dumps({"intencion": intencion_router, "motivo": "fixture"})
        return TEXTO_EXPLICACION_FALSO
    return responder


def _resolucion_sm1_falsa(hechos, evidencias, fallas, verificacion):
    """
    Oráculo de esta suite: devuelve la MISMA forma que la consulta Cypher de resolución de
    SM1 y aplica la misma política con el catálogo de prueba. La inferencia real (patrones,
    precedencia, estado y costos) se prueba contra el grafo aislado en
    test_diagnostico_neo4j.py y test_sm1_neo4j.py; acá sólo se ejercita el cableado del pipeline.
    """
    filas = _evidencias_sm1_falsas(evidencias, hechos.get("campos") or {})
    por_texto = {}
    for fila in filas:
        por_texto.setdefault(fila["texto"], []).append(fila)
    inviables, sintomas, intervenciones, sin_tratamiento = [], {}, [], []
    for texto, grupo in por_texto.items():
        aplicables = [f for f in grupo if f["aplicable"]]
        inv = [f for f in aplicables if f["tratamiento"] == "inviable"]
        ver = [f for f in aplicables if f["tratamiento"] == "verificar"]
        inter = [f for f in aplicables if f["tratamiento"] == "intervencion"]
        if inv:
            inviables.extend(inv)
        elif ver:
            for fila in ver:
                sintomas[fila["sintoma"]] = fila
        elif not aplicables or any(f["tratamiento"] == "descartar" for f in grupo):
            continue
        else:
            intervenciones.extend(inter)
    sin_tratamiento = [f for f in fallas if f not in por_texto]

    validada = bool(verificacion and verificacion.get("fuente") and verificacion.get("diagnosticos"))
    diagnosticos = _diagnosticos_sm1_falsos(verificacion["diagnosticos"] if validada else [])
    desconocidos = sorted({d["solicitado"] for d in diagnosticos if not d["id"]})
    incompletos = sorted({d["solicitado"] for d in diagnosticos
                          if d.get("reparable") is True and (not d.get("tarea") or d.get("costo_ars") is None)})
    irreparables = [d for d in diagnosticos if d.get("reparable") is False]
    reparaciones = [d for d in diagnosticos
                    if d.get("reparable") is True and d.get("tarea") and d.get("costo_ars") is not None]
    confirmados = sorted({d["nombre"] for d in diagnosticos if d.get("nombre")})

    sintomas_detectados = [{"sintoma": s["sintoma"], "descripcion": s["sintoma_descripcion"],
                            "regla": s["regla"]} for s in sintomas.values()]
    pendientes = (0 if validada else len(sintomas_detectados)) + len(sin_tratamiento)
    if inviables:
        estado, causa_origen = "Inviable", "aviso"
        regla, causa = inviables[0]["regla"], inviables[0]["descripcion"]
    elif desconocidos or incompletos:
        estado, causa_origen, regla, causa = "ConocimientoFaltante", None, None, None
    elif irreparables:
        estado, causa_origen = "Inviable", "verificacion"
        regla, causa = irreparables[0]["regla"], irreparables[0]["motivo"]
    elif pendientes:
        estado, causa_origen = "VerificacionPendiente", None
        regla = next((s["regla"] for s in sintomas_detectados if s["regla"]), "R3.3c")
        causa = None
    else:
        estado, causa_origen, regla, causa = "Viable", None, None, None

    def fila_plan(tarea, regla, orden, costo, criterio=None, cuenta=True):
        return {"tarea": tarea, "descripcion_costo": DESCRIPCIONES[tarea], "costo_ars": costo,
                "costo_id": CONOCIMIENTO_FALSO["costos"][tarea]["id"] if tarea in CONOCIMIENTO_FALSO["costos"] else None,
                "costo_version": "prueba", "costo_estado": "Validado", "regla": regla, "orden": orden,
                "cuenta_como_intervencion": cuenta,
                "criterio_nombre": criterio, "criterio_id": CONOCIMIENTO_FALSO["criterios"][criterio]["id"]
                if criterio else None, "criterio_valor": CRITERIOS_PRUEBA.get(criterio),
                "criterio_unidad": "fixture" if criterio else None,
                "criterio_version": "prueba" if criterio else None,
                "criterio_estado": "Validado" if criterio else None}

    candidatas = []
    if estado == "Viable":
        reglas = [r for r in _reglas_sm1_falsas(hechos) if not r["requiere_plan"]]
        candidatas = [fila_plan(r["tarea"], r["regla"], r["orden"], r["costo_ars"], r["criterio_nombre"])
                      for r in reglas]
        candidatas += [fila_plan(f["tarea"], f["regla"] or f["patron"], f["orden"], f["costo_ars"])
                       for f in intervenciones]
        candidatas += [fila_plan(d["tarea"], d.get("regla") or "Verificación del operador", d["orden"],
                                 d["costo_ars"]) for d in reparaciones]
    candidatas.sort(key=lambda f: (f["orden"], f["tarea"]))
    plan, vistas = [], set()
    for fila in candidatas:
        if fila["tarea"] in vistas:
            continue
        vistas.add(fila["tarea"])
        plan.append(fila)
    if plan:
        mano = [r for r in _reglas_sm1_falsas(hechos) if r["requiere_plan"]][0]
        plan.append(fila_plan(mano["tarea"], mano["regla"], mano["orden"], mano["costo_ars"], cuenta=False))

    return {
        "estado": estado, "regla_aplicada": regla, "causa": causa, "causa_origen": causa_origen,
        "pendientes": pendientes, "plan": plan,
        "costo_total": sum(f["costo_ars"] for f in plan),
        "cantidad_intervenciones": len([f for f in plan if f["cuenta_como_intervencion"]]),
        "upgrades": {"ssd": "ssd_upgrade" in vistas, "ram": "ram_upgrade" in vistas},
        "sintomas_detectados": sintomas_detectados,
        "sin_tratamiento": sin_tratamiento, "desconocidos": desconocidos,
        "incompletos": incompletos, "confirmados": confirmados,
    }


class Ejecucion:
    def __init__(self, resultado, mercado, llm):
        self.resultado = resultado
        self.mercado = mercado
        self.llm = llm


def _ejecutar(caso):
    """Ejecuta el pipeline público con las fronteras externas simuladas."""
    with mock.patch.object(oe, "obtener_driver_neo4j", return_value=mock.Mock()), \
            mock.patch.object(oe, "cargar_conocimiento", return_value=CONOCIMIENTO_FALSO), \
            mock.patch.object(oe, "consultar_senales_bloqueo_en_grafo", return_value=SENALES_BLOQUEO_FALSAS), \
            mock.patch.object(oe, "consultar_resolucion_sm1", side_effect=_resolucion_sm1_falsa), \
            mock.patch.object(oe, "inferir_valuacion_sm2_cypher", side_effect=_valuacion_falsa) as mercado, \
            mock.patch.object(oe, "inferir_sm1_bat_cypher", side_effect=_sm1_bat_falso), \
            mock.patch.object(oe, "inferir_sm1_ter_cypher", side_effect=_sm1_ter_falso), \
            mock.patch.object(oe, "inferir_sm2_rie_cypher", side_effect=_sm2_rie_falso), \
            mock.patch.object(oe, "inferir_sm2_dem_cypher", side_effect=_sm2_dem_falso), \
            mock.patch.object(oe, "inferir_sm3_conv_cypher", side_effect=_sm3_conv_falso), \
            mock.patch.object(oe, "inferir_sm3_crisp_cypher", side_effect=_sm3_crisp_falso), \
            mock.patch.object(oe, "resolver_decision_sm3_cypher", side_effect=_sm3_decision_falsa), \
            mock.patch.object(oe, "consultar_llm",
                              side_effect=_llm_falso(caso.get("extraccion_llm") or {},
                                                     caso.get("intencion_router", "evaluacion_integral"))) as llm:
        with redirect_stdout(StringIO()):
            if caso.get("via") == "integral":  # entrada integral explícita para separar el enrutamiento
                resultado = oe.evaluar_publicacion_integral(caso["entrada"], verbose=False)
            else:
                resultado = oe.asistente_evaltic(caso["entrada"], verbose=False)
    return Ejecucion(resultado, mercado, llm)


# ------------------------------------------------------------------------------
# Pruebas
# ------------------------------------------------------------------------------
class CorpusTest(unittest.TestCase):
    """El corpus es la especificación de los casos: se valida su integridad."""

    def test_tiene_al_menos_cuarenta_y_cinco_casos_con_ids_estables(self):
        ids = [caso["id"] for caso in CORPUS["casos"]]
        self.assertGreaterEqual(len(ids), 45)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids, sorted(ids))
        for ident in ids:
            self.assertRegex(ident, r"^PC-\d{2}$")

    def test_incluye_el_ejemplo_literal_del_usuario(self):
        self.assertIn("computadora asus, anda joya", [caso["entrada"] for caso in CORPUS["casos"]])

    def test_cada_caso_declara_grupo_entrada_motivo_y_clasificacion(self):
        for caso in CORPUS["casos"]:
            with self.subTest(caso=caso["id"]):
                self.assertIn(caso["grupo"], GRUPOS_VALIDOS)
                self.assertIn(caso["clasificacion"], CLASIFICACIONES)
                self.assertTrue(caso["entrada"].strip())
                self.assertGreaterEqual(len(caso["por_que_critico"]), 40, "falta justificar el caso")

    def test_hay_casos_en_todos_los_grupos(self):
        usados = {caso["grupo"] for caso in CORPUS["casos"]}
        self.assertEqual(GRUPOS_VALIDOS, usados)

    def test_las_sondas_no_tienen_expectativa_y_son_solo_en_vivo(self):
        self.assertEqual(set(CORPUS["solo_en_vivo"]),
                         {caso["id"] for caso in CORPUS["casos"] if caso["clasificacion"] == "sonda"})
        for caso in CORPUS["casos"]:
            with self.subTest(caso=caso["id"]):
                if caso["clasificacion"] == "sonda":
                    self.assertEqual("solo_vivo", caso["verificacion"])
                    self.assertNotIn("espera", caso)
                    self.assertGreaterEqual(len(caso["sonda"]), 20)
                else:
                    self.assertEqual("offline_y_vivo", caso["verificacion"])
                    self.assertIn("resultado", caso["espera"])
                    self.assertIsInstance(caso.get("extraccion_llm"), dict)

    def test_cada_expectativa_comprueba_algo_concreto(self):
        for caso in (c for c in CORPUS["casos"] if c["clasificacion"] != "sonda"):
            with self.subTest(caso=caso["id"]):
                claves = set(caso["espera"]) | set(caso.get("espera_offline") or {})
                self.assertGreater(len(claves - {"resultado"}), 0, "expectativa vacía o solo de tipo")
                self.assertLessEqual(claves, CLAVES_ESPERA, "clave de expectativa no soportada")

    def test_expectativas_declaran_solo_claves_y_tipos_conocidos(self):
        for caso in CORPUS["casos"]:
            with self.subTest(caso=caso["id"]):
                if caso["clasificacion"] == "sonda":
                    self.assertNotIn("espera", caso)
                    continue
                self.assertIn(caso["espera"]["resultado"], TIPOS_RESULTADO)
                for campo in ("espera", "espera_offline", "observado_hoy"):
                    if campo in caso:
                        validar_espera(caso[campo])

    def test_la_expectativa_en_vivo_no_depende_de_la_extraccion_simulada(self):
        para_fixtures = ("procesador_extraido", "anio_extraido", "fallas", "costo_total")
        for caso in (c for c in CORPUS["casos"] if c["clasificacion"] != "sonda"):
            with self.subTest(caso=caso["id"]):
                for clave in para_fixtures:
                    self.assertNotIn(clave, caso["espera"], "va en espera_offline")
                if "vma" in caso["espera"]:
                    self.assertEqual(0, caso["espera"]["vma"], "un VMA tasado depende del grafo real")

    def test_los_defectos_documentan_comportamiento_actual_y_expectativa_estricta(self):
        for caso in CORPUS["casos"]:
            if caso["clasificacion"] != "defecto_conocido":
                continue
            with self.subTest(caso=caso["id"]):
                self.assertIn("observado_hoy", caso)
                self.assertNotEqual(caso["espera"], caso["observado_hoy"])


class ContratoMercadoTest(unittest.TestCase):
    """El fixture de valuación expone la misma forma que la consulta Cypher del motor."""

    def test_el_fixture_devuelve_los_campos_de_la_consulta_publica(self):
        for procesador, texto in (("i5 10ma gen", "ThinkPad T14"), ("ryzen 7 5700u", "hp 250 g8"),
                                  ("celeron n4020", "sin marca")):
            with self.subTest(procesador=procesador):
                self.assertEqual(CAMPOS_VALUACION,
                                 set(_valuacion_falsa(procesador, "", texto, 8, False, False,
                                                      2021, None)))

    def test_valor_proc_calca_al_procesador_y_queda_vacio_cuando_no_hay_precio(self):
        con_precio = _valuacion_falsa("i5 10ma gen", "", "ThinkPad T14", 16, False, False, 2021, None)
        self.assertEqual(con_precio["procesador"]["valor_ref_ars"], con_precio["valor_proc"])
        self.assertIsNone(con_precio["generacion_anterior"])
        # Procesador relevado con menos avisos que CE min_muestras_mercado: sin precio propio.
        sin_precio = _valuacion_falsa("ryzen 7 5700u", "", "hp 250 g8", 8, False, False, 2021, None)
        self.assertIsNone(sin_precio["valor_proc"])
        self.assertIsNone(sin_precio["generacion_anterior"])
        self.assertEqual("procesador_sin_muestras", sin_precio["motivo_clave"])
        # Procesador que no está en la base de conocimiento: nada que tasar.
        desconocido = _valuacion_falsa("celeron xyz", "", "hp 250 g8", 8, False, False, 2021, None)
        self.assertIsNone(desconocido["procesador"])
        self.assertIsNone(desconocido["valor_proc"])
        self.assertEqual("ConocimientoFaltante", desconocido["estado"])


class AceptacionTest(unittest.TestCase):
    """Casos con expectativa de contrato: deben cumplirla con los fixtures."""

    def test_todos_los_casos_de_aceptacion_cumplen_su_espera(self):
        seleccion = [c for c in CORPUS["casos"] if c["clasificacion"] == "aceptacion"]
        self.assertGreaterEqual(len(seleccion), 40)
        for caso in seleccion:
            with self.subTest(caso=caso["id"]):
                resultado = _ejecutar(caso).resultado
                self.assertEqual([], _comprobar(resultado, caso["espera"]), caso["titulo"])
                if "espera_offline" in caso:
                    self.assertEqual([], _comprobar(resultado, caso["espera_offline"]), caso["titulo"])

    def test_los_casos_caracterizados_cumplen_el_comportamiento_documentado(self):
        for caso in (c for c in CORPUS["casos"] if c["clasificacion"] == "caracterizacion"):
            with self.subTest(caso=caso["id"]):
                resultado = _ejecutar(caso).resultado
                self.assertEqual([], _comprobar(resultado, caso["espera"]), caso["titulo"])
                if "espera_offline" in caso:
                    self.assertEqual([], _comprobar(resultado, caso["espera_offline"]), caso["titulo"])


class DefectosConocidosTest(unittest.TestCase):
    """Reporta el estado de cada defecto sin exigir que siga roto.

    Mientras la aceptación estricta falle, se documenta el comportamiento observado. Si el
    motor se repara, la expectativa estricta pasa y la suite no fija el bug (sin xfail).
    """

    def test_cada_defecto_informa_estado_abierto_o_reparado(self):
        for caso in (c for c in CORPUS["casos"] if c["clasificacion"] == "defecto_conocido"):
            resultado = _ejecutar(caso).resultado
            estricta = _comprobar(resultado, caso["espera"])
            estado = "abierto" if estricta else "reparado"
            with self.subTest(caso=caso["id"], estado=estado):
                if estricta:
                    self.assertEqual([], _comprobar(resultado, caso["observado_hoy"]), caso["titulo"])
                else:
                    self.assertEqual([], estricta, caso["titulo"])


class Sm3AdapterTest(unittest.TestCase):
    """SM3 delega la política en la inferencia del grafo y conserva su contrato público.

    Los dobles de Cypher de este archivo no prueban las consultas: la cobertura real de la
    inferencia está en test_sm3_neo4j.py. Acá se fija el cableado y la forma de la salida.
    """

    def _ejecutar(self, *caso):
        traza = oe.nueva_traza()
        with mock.patch.object(oe, "obtener_driver_neo4j", return_value=mock.Mock()), \
                mock.patch.object(oe, "inferir_sm3_crisp_cypher", side_effect=_sm3_crisp_falso), \
                mock.patch.object(oe, "resolver_decision_sm3_cypher", side_effect=_sm3_decision_falsa), \
                mock.patch.object(oe, "inferir_sm3_conv_cypher", side_effect=_sm3_conv_falso):
            return oe.ejecutar_motor_sm3(*caso, traza), traza

    def test_el_descarte_por_r37_conserva_decision_motivo_e_indicadores(self):
        resultado, traza = self._ejecutar(300000, 400000, 661000, 0, "Medio", "Media")
        self.assertEqual("DescartarPorRiesgo", resultado["decision"])
        self.assertEqual("R3.7", resultado["regla_aplicada"])
        self.assertEqual("La reparación ($400,000) supera el 50% del VMA ($661,000).", resultado["motivo"])
        self.assertEqual(["R3.7: costo / VMA > CE ratio_reparacion_max → DescartarPorRiesgo"], traza["reglas"])
        self.assertEqual({"precio_publicado", "costo_reparacion", "vma_tasado", "margen_neto_pct",
                          "ratio_reparacion"}, set(resultado["indicadores"]))

    def test_el_margen_requerido_llega_del_grafo_con_su_procedencia(self):
        # Criterios del fixture: margen_base 12 % y prima_fallas 5 pp con umbral 3 intervenciones.
        resultado, traza = self._ejecutar(400000, 0, 661000, 4, "Medio", "Media")
        self.assertEqual(17.0, resultado["indicadores"]["margen_requerido_pct"])
        self.assertIn("R3.6: intervenciones ≥ CE umbral_intervenciones → + CE prima_fallas", traza["reglas"])
        self.assertEqual(["ratio_reparacion_max", "margen_base", "umbral_intervenciones", "prima_fallas"],
                         list(traza["criterios_usados"]))
        self.assertEqual({"id", "valor", "unidad", "version", "estado"},
                         set(traza["criterios_usados"]["margen_base"]))

    def test_la_contraoferta_solo_se_informa_al_negociar(self):
        negociar, _ = self._ejecutar(850000, 0, 1000000, 0, "Medio", "Media")
        self.assertEqual("ComprarConOfertaMenor", negociar["decision"])
        # 1.000.000 − 12 % de margen requerido = 880.000, con descuento 0 sobre el precio pedido.
        self.assertEqual(880000, negociar["indicadores"]["contraoferta_sugerida_ars"])
        self.assertEqual(0.0, negociar["indicadores"]["descuento_requerido_pct"])
        comprar, _ = self._ejecutar(100000, 0, 1000000, 0, "Medio", "Media")
        self.assertEqual("Comprar", comprar["decision"])
        self.assertIsNone(comprar["indicadores"]["contraoferta_sugerida_ars"])

    def test_un_vma_cero_conserva_la_excepcion_de_la_politica_anterior(self):
        for vma in (0, 0.0, -0.0):
            with self.subTest(vma=vma):
                with self.assertRaises(ZeroDivisionError) as contexto:
                    self._ejecutar(1000, 0, vma, 0, "Bajo", "Alta")
                self.assertEqual("division by zero", str(contexto.exception))

    def test_un_vma_negativo_se_evalua_como_antes(self):
        resultado, _ = self._ejecutar(1000, 0, -661000, 0, "Medio", "Media")
        self.assertEqual(0.0, resultado["indicadores"]["ratio_reparacion"])
        self.assertIn(resultado["decision"], ("Comprar", "ComprarConOfertaMenor", "DescartarPorRiesgo"))

    def test_las_entradas_no_numericas_se_rechazan(self):
        for caso in ((("350000"), 0, 661000), (400000, "mucho", 661000), (400000, 0, None)):
            with self.subTest(caso=caso):
                with self.assertRaises(TypeError):
                    self._ejecutar(*caso, 0, "Medio", "Media")

    def test_los_booleanos_siguen_siendo_numeros_como_antes(self):
        # La política anterior operaba `True` como 1 en la aritmética.
        resultado, _ = self._ejecutar(True, False, 661000, 0, "Medio", "Media")
        self.assertEqual(1, resultado["indicadores"]["precio_publicado"])
        self.assertEqual(0, resultado["indicadores"]["costo_reparacion"])


class FronterasExternasTest(unittest.TestCase):
    """El LLM y el catálogo se usan solo donde el contrato lo permite."""

    def test_ejemplo_del_usuario_no_consulta_el_catalogo_ni_tasa(self):
        integral = _ejecutar(CASOS["PC-61"])
        self.assertIn("Entrada rechazada", integral.resultado["error"])
        self.assertEqual(0, integral.mercado.call_count)
        self.assertEqual(1, integral.llm.call_count)  # solo extracción: rechaza antes del dictamen
        enrutado = _ejecutar(CASOS["PC-01"])
        self.assertEqual(0, enrutado.mercado.call_count)
        self.assertNotIn("sm3_financiero", enrutado.resultado)

    def test_falla_catastrofica_no_se_tasa(self):
        ejecucion = _ejecutar(CASOS["PC-10"])
        self.assertEqual(0, ejecucion.mercado.call_count)
        self.assertEqual("Omitido_Por_Inviabilidad", ejecucion.resultado["sm2_comercial"]["estado"])

    def test_el_llm_solo_extrae_y_redacta_no_tasa(self):
        ejecucion = _ejecutar(CASOS["PC-15"])
        self.assertEqual(3, ejecucion.llm.call_count)  # enrutador + extracción + síntesis
        self.assertEqual("Comprar", ejecucion.resultado["sm3_financiero"]["decision"])


if __name__ == "__main__":
    unittest.main()
