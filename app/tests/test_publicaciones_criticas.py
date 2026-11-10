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
del LLM y funciones de consulta al grafo). Las reglas crisp, el encadenamiento
SM1 → SM2 → SM3, las validaciones defensivas y el enrutamiento se ejecutan de verdad.
La ejecución real está en `scripts/probar_publicaciones.py`.

Ejecutar desde la raíz del repositorio:
    python app/tests/test_publicaciones_criticas.py -v
"""

import json
import os
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
}
CONOCIMIENTO_FALSO = {
    "criterios": {nombre: {"id": f"CE-{i:02d}", "valor": valor, "unidad": "fixture",
                           "version": "prueba", "estado": "Validado"}
                  for i, (nombre, valor) in enumerate(CRITERIOS_PRUEBA.items(), start=1)},
    "costos": {tarea: {"id": f"COS-{tarea[:3].upper()}", "costo": COSTOS_PRUEBA[tarea],
                       "descripcion": DESCRIPCIONES[tarea], "version": "prueba", "estado": "Validado"}
               for tarea in COSTOS_PRUEBA},
}
FALLAS_CATASTROFICAS_FALSAS = ["no da video", "quemad", "perforad", "en corto"]
SENALES_BLOQUEO_FALSAS = ["icloud", "bloqueada", "bloqueado", "cuenta", "clave de bios", "mdm"]
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


def _mercado_falso(procesador, texto, ram_informada, ram_final, hdd_a_ssd):
    """Devuelve la misma forma que la consulta Cypher de componentes, con fixtures."""
    proc = CATALOGO_PROCESADORES.get(str(procesador or "").strip().lower())
    linea = next((l for l in LINEAS_FALSAS if l[0] in str(texto or "").lower()), None)
    factor_ram = FACTORES_RAM.get(ram_final)
    # Igual que el Cypher: coalesce(p.valor_ref_ars, generación anterior). Acá no se simula R2.4.
    valor_proc = proc["valor_ref_ars"] if proc else None
    valor = None
    if valor_proc is not None and linea and factor_ram:
        valor = valor_proc * linea[2] * factor_ram
    vma = None
    if valor is not None:
        vma = int(round((valor * 0.9 + (CRITERIOS_PRUEBA["reval_ssd"] if hdd_a_ssd else 0)) / 1000.0)) * 1000
    return {
        "procesador": dict(proc) if proc else None,
        "generacion_anterior": None,
        "valor_proc": valor_proc,
        "linea": {"nombre": linea[1], "marca": linea[0], "factor_precio": linea[2],
                  "origen_factor": "fixture", "estado_validacion": "Provisional"} if linea else None,
        "grupo": {"nombre": linea[3], "dias_promedio_venta": linea[4], "indice_repuestos": linea[5]}
        if linea else None,
        "ram_informada_existe": ram_informada in FACTORES_RAM,
        "ram": {"gb": ram_final, "factor": factor_ram} if factor_ram else None,
        "valor_mercado": valor,
        "vma": vma,
    }


# Campos que devuelve la consulta Cypher de componentes (contrato público de SM2).
CAMPOS_MERCADO = {"procesador", "generacion_anterior", "valor_proc", "linea", "grupo",
                  "ram_informada_existe", "ram", "valor_mercado", "vma"}


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


class Ejecucion:
    def __init__(self, resultado, mercado, llm):
        self.resultado = resultado
        self.mercado = mercado
        self.llm = llm


def _ejecutar(caso):
    """Ejecuta el pipeline público con las fronteras externas simuladas."""
    with mock.patch.object(oe, "obtener_driver_neo4j", return_value=mock.Mock()), \
            mock.patch.object(oe, "cargar_conocimiento", return_value=CONOCIMIENTO_FALSO), \
            mock.patch.object(oe, "consultar_fallas_catastroficas_en_grafo", return_value=FALLAS_CATASTROFICAS_FALSAS), \
            mock.patch.object(oe, "consultar_senales_bloqueo_en_grafo", return_value=SENALES_BLOQUEO_FALSAS), \
            mock.patch.object(oe, "consultar_mercado_componentes", side_effect=_mercado_falso) as mercado, \
            mock.patch.object(oe, "inferir_sm1_bat_cypher", side_effect=_sm1_bat_falso), \
            mock.patch.object(oe, "inferir_sm1_ter_cypher", side_effect=_sm1_ter_falso), \
            mock.patch.object(oe, "inferir_sm2_rie_cypher", side_effect=_sm2_rie_falso), \
            mock.patch.object(oe, "inferir_sm2_dem_cypher", side_effect=_sm2_dem_falso), \
            mock.patch.object(oe, "inferir_sm3_conv_cypher", side_effect=_sm3_conv_falso), \
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
    """El fixture de mercado expone la misma forma que la consulta Cypher del motor."""

    def test_el_fixture_devuelve_los_campos_de_la_consulta_publica(self):
        for procesador, texto in (("i5 10ma gen", "ThinkPad T14"), ("ryzen 7 5700u", "hp 250 g8"),
                                  ("celeron n4020", "sin marca")):
            with self.subTest(procesador=procesador):
                self.assertEqual(CAMPOS_MERCADO, set(_mercado_falso(procesador, texto, 8, 8, False)))

    def test_valor_proc_calca_al_procesador_y_queda_vacio_cuando_no_hay_precio(self):
        con_precio = _mercado_falso("i5 10ma gen", "ThinkPad T14", 16, 16, False)
        self.assertEqual(con_precio["procesador"]["valor_ref_ars"], con_precio["valor_proc"])
        self.assertIsNone(con_precio["generacion_anterior"])
        # Procesador relevado con menos avisos que CE min_muestras_mercado: sin precio propio.
        sin_precio = _mercado_falso("ryzen 7 5700u", "hp 250 g8", 8, 8, False)
        self.assertIsNone(sin_precio["valor_proc"])
        self.assertIsNone(sin_precio["generacion_anterior"])
        # Procesador que no está en la base de conocimiento: nada que tasar.
        desconocido = _mercado_falso("celeron n4020", "hp 250 g8", 8, 8, False)
        self.assertIsNone(desconocido["procesador"])
        self.assertIsNone(desconocido["valor_proc"])


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
