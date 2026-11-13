#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pruebas aisladas de B2 — síntomas relevantes, fallas sin tratamiento y verificación del
operador, ejecutadas contra un Neo4j NUEVO y reconstruible (nunca el de trabajo).

La inferencia se prueba por las funciones públicas del motor:
`evaluar_publicacion_integral` y `consultar_sm1`. La extracción del LLM es controlada
(se reemplaza `extraer_datos_llm`) y la redacción también, así que lo único que se observa
es la inferencia simbólica sobre el grafo. Las expectativas describen la política
Provisional adoptada en B2: un síntoma afirmado sin diagnóstico confirmado no puede terminar
en una compra favorable ni en un descarte por inviabilidad.

Preparación (el grafo de pruebas ya debe existir; este archivo NO lo crea ni lo borra):

    EVALTIC_NEO4J_PRUEBAS_URI=bolt://127.0.0.1:17687 \\
    PYTHONDONTWRITEBYTECODE=1 /home/alvaro/Universidad/IA/Proyecto/.venv/bin/python \\
        -m unittest discover -s app/tests -p test_diagnostico_neo4j.py -v

Antes de ejecutar, el archivo de conocimiento aditivo `cypher/Grupo_20_PG3_diagnostico.cypher`
se aplica una vez con MERGE (sólo identificadores nuevos). Si el marcador
`(:EntornoPruebas {id:'mejoras-evaltic'})` no está presente, las pruebas se omiten con el
motivo explícito en vez de aprobar en falso.
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
# Aislamiento previo a la importación del motor: sin red, sin .env real
# ------------------------------------------------------------------------------
URI_PRUEBAS = os.environ.get("EVALTIC_NEO4J_PRUEBAS_URI", "").strip()
ENTORNO_PRUEBA = {
    "LLM_PROVIDER": "ollama",
    "OLLAMA_URL": "http://ollama.invalid/api/generate",
    "OLLAMA_MODEL": "modelo-ollama-de-prueba",
    "NEO4J_TARGET": "local",
    "NEO4J_LOCAL_URI": URI_PRUEBAS or "bolt://neo4j.invalid:7687",
    "NEO4J_LOCAL_USERNAME": "",
    "NEO4J_LOCAL_PASSWORD": "",
    "NEO4J_LOCAL_DATABASE": "neo4j",
}
for _clave, _valor in ENTORNO_PRUEBA.items():
    os.environ[_clave] = _valor

with mock.patch("dotenv.load_dotenv", return_value=False):
    import orquestador_evaltic as oe

MARCADOR = "mejoras-evaltic"
ARCHIVO_CONOCIMIENTO = RAIZ / "cypher" / "Grupo_20_PG3_diagnostico.cypher"
HOSTS_PRUEBA = {"127.0.0.1", "localhost"}

# Hechos de un aviso sano de control (mismos valores que PC-15 del corpus).
AVISO_SANO = ("Lenovo ThinkPad T490 año 2019 i5 10ma gen, Windows 11 oficial, piden $220.000. "
              "Batería 91% con 110 ciclos, temperatura 50°C sin throttling, 16GB RAM y SSD 512GB, "
              "pantalla y teclado perfectos, cargador original.")
EXTRACCION_SANA = {
    "marca": "Lenovo", "modelo": "ThinkPad T490", "procesador": "i5 10ma gen",
    "precio_publicado": 220000, "anio_fabricacion": 2019, "ram_gb": 16, "tipo_disco": "SSD",
    "salud_bateria_pct": 91, "ciclos_bateria": 110, "temperatura_cpu_c": 50,
    "thermal_throttling": False, "pantalla_danada": False, "teclado_danado": False,
    "cargador_incluido": True, "soporte_windows_11": True, "fallas": [],
}


def _sentencias_cypher(texto: str) -> list:
    """Divide el archivo Cypher en sentencias y descarta las líneas de comentario."""
    sentencias = []
    for bloque in texto.split(";"):
        lineas = [l for l in bloque.splitlines() if l.strip() and not l.strip().startswith("//")]
        if lineas:
            sentencias.append("\n".join(lineas))
    return sentencias


def _driver_aislado():
    """Conecta al Neo4j de pruebas declarado; rechaza cualquier otro destino."""
    if not URI_PRUEBAS:
        raise unittest.SkipTest(
            "falta EVALTIC_NEO4J_PRUEBAS_URI (Neo4j aislado de pruebas); no se ejecuta contra el grafo de trabajo")
    host_puerto = URI_PRUEBAS.split("://", 1)[-1]
    host = host_puerto.rsplit(":", 1)[0]
    if host not in HOSTS_PRUEBA:
        raise AssertionError(f"EVALTIC_NEO4J_PRUEBAS_URI debe ser local ({host_puerto}); "
                             f"las pruebas no tocan el grafo de trabajo")
    import neo4j
    driver = neo4j.GraphDatabase.driver(URI_PRUEBAS, auth=None)
    with driver.session(database="neo4j") as s:
        if s.run("MATCH (m:EntornoPruebas {id:$id}) RETURN count(m) AS n", id=MARCADOR).single()["n"] != 1:
            raise unittest.SkipTest(f"el Neo4j de pruebas no tiene el marcador EntornoPruebas '{MARCADOR}'")
    return driver


def _aplicar_conocimiento(driver):
    """Aplica el conocimiento aditivo de B2 (MERGE idempotente, sólo identificadores nuevos)."""
    sentencias = _sentencias_cypher(ARCHIVO_CONOCIMIENTO.read_text(encoding="utf-8"))
    with driver.session(database="neo4j") as s:
        for sentencia in sentencias:
            s.run(sentencia)
    return len(sentencias)


class BaseNeo4jAislado(unittest.TestCase):
    """Base con el driver aislado, la extracción controlada y la redacción desactivada."""

    @classmethod
    def setUpClass(cls):
        cls.driver = _driver_aislado()
        cls.sentencias = _aplicar_conocimiento(cls.driver)

    @classmethod
    def tearDownClass(cls):
        cls.driver.close()

    def _ejecutar(self, funcion, *args, extraccion=None, salida=None, **kwargs):
        """Ejecuta una función pública con las fronteras externas simuladas."""
        parches = [
            mock.patch.object(oe, "obtener_driver_neo4j", return_value=self.driver),
            mock.patch.object(oe, "consultar_llm", side_effect=ConnectionError("sin LLM en pruebas")),
        ]
        if extraccion is not None:
            # Extracción controlada: cubre la evaluación integral y las consultas sueltas de SM1.
            parches.append(mock.patch.object(
                oe, "extraer_datos_llm", side_effect=lambda _texto: json.loads(json.dumps(extraccion))))
            parches.append(mock.patch.object(
                oe, "_llm_json", side_effect=lambda _prompt, _texto: json.loads(json.dumps(extraccion))))
        with redirect_stdout(salida if salida is not None else StringIO()):
            for parche in parches:
                parche.start()
            try:
                return funcion(*args, **kwargs)
            finally:
                for parche in reversed(parches):
                    parche.stop()

    def crear_nodos_prueba(self, *consultas):
        """Crea nodos de prueba con identificadores propios y los limpia al terminar la prueba."""
        with self.driver.session(database="neo4j") as s:
            for consulta in consultas:
                s.run(consulta)
        self.addCleanup(self.limpiar_nodos_prueba)

    def limpiar_nodos_prueba(self):
        """Borra SÓLO los nodos de prueba de esta unidad (prefijos DIA-PRUEBA-B2- / COS-PRUEBA-B2-)."""
        with self.driver.session(database="neo4j") as s:
            s.run("MATCH (d:Diagnostico) WHERE d.id STARTS WITH 'DIA-PRUEBA-B2-' DETACH DELETE d")
            s.run("MATCH (c:CostoReparacion) WHERE c.id STARTS WITH 'COS-PRUEBA-B2-' DETACH DELETE c")

    def _integral(self, texto, extraccion, verificacion=None):
        return self._ejecutar(oe.evaluar_publicacion_integral, texto, verbose=False,
                              extraccion=extraccion, verificacion_tecnica=verificacion)


class SintomaSinDiagnosticoTest(BaseNeo4jAislado):
    """Un síntoma afirmado sin diagnóstico no puede producir una compra favorable."""

    def _aviso(self):
        return ("Notebook HP 15 año 2020 i5 10ma gen, $100.000, 8GB RAM y SSD de 256GB. "
                "No prende y no carga.")

    def _extraccion(self, fallas):
        return {"marca": "HP", "modelo": "15", "procesador": "i5 10ma gen", "precio_publicado": 100000,
                "anio_fabricacion": 2020, "ram_gb": 8, "tipo_disco": "SSD", "fallas": fallas}

    def test_no_prende_y_no_carga_exigen_verificacion_y_no_aprueban_la_compra(self):
        resultado = self._integral(self._aviso(), self._extraccion(["no prende", "no carga"]))
        sm1, sm3 = resultado["sm1_tecnico"], resultado["sm3_financiero"]

        self.assertEqual("VerificacionPendiente", sm3["decision"])
        self.assertEqual("R3.3c", sm3["regla_aplicada"])
        self.assertEqual("VerificacionPendiente", sm1["estado"])
        self.assertIsNone(sm1["es_viable"], "sin diagnóstico no es ni viable ni inviable")
        self.assertEqual(0, sm1["costo_total"])
        self.assertEqual([], sm1["plan_reparacion"])
        self.assertIn("no prende", " ".join(sm1["verificacion_requerida"]).lower())
        self.assertIn("no carga", " ".join(sm1["verificacion_requerida"]).lower())
        self.assertEqual({}, resultado["traza"]["costos_usados"],
                         "no se puede afirmar una reparación con costo cero")
        self.assertNotIn("Comprar", sm3["decision"])

    def test_no_se_tasa_ni_se_decide_sobre_un_equipo_sin_diagnostico(self):
        resultado = self._integral(self._aviso(), self._extraccion(["no prende", "no carga"]))
        self.assertEqual("Sin_evaluar", resultado["sm2_comercial"]["estado"])
        self.assertEqual(0, resultado["sm2_comercial"]["vma_estimado_ars"])

    def test_la_evidencia_del_aviso_alcanza_aunque_la_extraccion_omita_los_sintomas(self):
        resultado = self._integral(self._aviso(), self._extraccion([]))
        self.assertEqual("VerificacionPendiente", resultado["sm3_financiero"]["decision"])
        self.assertIn("no prende", " ".join(resultado["sm1_tecnico"]["verificacion_requerida"]).lower())

    def test_una_marca_del_modelo_no_levanta_la_guarda_de_verificacion(self):
        extraccion = self._extraccion([])
        # Campos que un extractor podría inventar: ninguno es evidencia del operador.
        extraccion.update({"diagnostico_confirmado": True, "verificacion_tecnica": "aprobada",
                           "aprobado": True, "decision": "Comprar", "reparable": True})
        resultado = self._integral(self._aviso(), extraccion)
        self.assertEqual("VerificacionPendiente", resultado["sm3_financiero"]["decision"])
        self.assertEqual([], resultado["sm1_tecnico"]["plan_reparacion"])

    def test_se_apaga_sola_tambien_requiere_verificacion(self):
        aviso = ("Acer Aspire 5 año 2020 i5 10ma gen, $150.000, 8GB RAM, SSD, se apaga sola a los "
                 "5 minutos de uso.")
        extraccion = {"marca": "Acer", "modelo": "Aspire 5", "procesador": "i5 10ma gen",
                      "precio_publicado": 150000, "anio_fabricacion": 2020, "ram_gb": 8,
                      "tipo_disco": "SSD", "fallas": ["se apaga sola"]}
        resultado = self._integral(aviso, extraccion)
        self.assertEqual("VerificacionPendiente", resultado["sm3_financiero"]["decision"])
        self.assertIn("se apaga sola", " ".join(resultado["sm1_tecnico"]["verificacion_requerida"]).lower())

    def test_una_falla_sin_tratamiento_conocido_no_se_convierte_en_viabilidad(self):
        extraccion = self._extraccion(["puerto hdmi roto"])
        resultado = self._integral(self._aviso().replace("No prende y no carga.", "El puerto HDMI está roto."),
                                   extraccion)
        sm1 = resultado["sm1_tecnico"]
        self.assertEqual("VerificacionPendiente", resultado["sm3_financiero"]["decision"])
        self.assertEqual([], sm1["plan_reparacion"], "no se inventa una reparación para una falla desconocida")
        self.assertIn("puerto hdmi roto", [f.lower() for f in sm1["fallas_sin_tratamiento"]])
        self.assertIsNone(sm1["es_viable"])

    def test_consulta_sm1_suelta_propaga_la_verificacion_pendiente(self):
        resultado = self._ejecutar(
            oe.consultar_sm1, "Mi notebook no prende y no carga, ¿qué reviso?",
            verbose=False, extraccion={"fallas": ["no prende", "no carga"]})
        sm1 = resultado["sm1_tecnico"]
        self.assertEqual("VerificacionPendiente", sm1["estado"])
        self.assertIsNone(sm1["es_viable"], "None nunca se interpreta como inviabilidad")
        self.assertIn("verificaci", resultado["respuesta"].lower())
        self.assertNotIn("reparable", resultado["respuesta"].lower())


class ConsultaSM1VerboseTest(BaseNeo4jAislado):
    """La salida pública distingue un plan desconocido de un equipo sin reparaciones."""

    def test_pendiente_con_verbose_por_defecto(self):
        salida = StringIO()
        resultado = self._ejecutar(
            oe.consultar_sm1, "Mi notebook no prende y no carga, ¿qué reviso?",
            extraccion={"fallas": ["no prende", "no carga"]}, salida=salida)
        self.assertEqual("VerificacionPendiente", resultado["sm1_tecnico"]["estado"])
        self.assertIn("verificaci", resultado["respuesta"].lower())
        self.assertTrue(salida.getvalue().endswith(
            "      Plan: pendiente de verificación | Costo: sin determinar\n"), salida.getvalue())

    def test_error_con_verbose_por_defecto(self):
        salida = StringIO()
        resultado = self._ejecutar(
            oe.consultar_sm1, "Mi notebook no prende, el taller dijo motor roto",
            extraccion={"fallas": ["no prende"]}, salida=salida,
            verificacion_tecnica={"fuente": "Taller", "diagnosticos": ["motor"]})
        self.assertEqual("ErrorConocimiento", resultado["sm1_tecnico"]["estado"])
        self.assertIn("motor", resultado["sm1_tecnico"]["error"])
        self.assertTrue(salida.getvalue().endswith(
            "      Plan: no disponible por conocimiento faltante | Costo: sin determinar\n"),
            salida.getvalue())

    def test_viable_conserva_su_salida_verbose(self):
        salida = StringIO()
        resultado = self._ejecutar(oe.consultar_sm1, "Mi notebook funciona bien",
                                  extraccion={"fallas": []}, salida=salida)
        self.assertEqual("Viable", resultado["sm1_tecnico"]["estado"])
        self.assertEqual([], resultado["sm1_tecnico"]["plan_reparacion"])
        self.assertEqual(0, resultado["sm1_tecnico"]["costo_total"])
        self.assertTrue(salida.getvalue().endswith(
            "      Plan: ninguna reparación | Costo: $0 ARS\n"), salida.getvalue())


class VerificacionDelOperadorTest(BaseNeo4jAislado):
    """La verificación técnica del operador libera la guarda y aporta reparación y costo."""

    def _aviso(self):
        return ("Notebook HP 15 año 2020 i5 10ma gen, $100.000, 8GB RAM y SSD de 256GB. "
                "No carga.")

    def _extraccion(self):
        return {"marca": "HP", "modelo": "15", "procesador": "i5 10ma gen", "precio_publicado": 100000,
                "anio_fabricacion": 2020, "ram_gb": 8, "tipo_disco": "SSD", "fallas": ["no carga"]}

    def test_la_verificacion_aporta_la_reparacion_y_el_costo_del_grafo(self):
        resultado = self._integral(self._aviso(), self._extraccion(), verificacion={
            "fuente": "Revisión en persona del operador, taller propio",
            "diagnosticos": ["bateria"]})
        sm1 = resultado["sm1_tecnico"]
        self.assertEqual("Viable", sm1["estado"])
        self.assertTrue(sm1["es_viable"])
        tareas = {t["tarea"]: t["costo"] for t in sm1["plan_reparacion"]}
        self.assertEqual(75000, tareas.get("Reemplazo de batería"))
        # Procedencia y validación siguen visibles: el costo usado es Provisional y versionado.
        usado = resultado["traza"]["costos_usados"]["bateria"]
        self.assertEqual(("COS-BAT", "Provisional", "v1"),
                         (usado["id"], usado["estado"], usado["version"]))
        self.assertEqual("Provisional", resultado["sm3_financiero"]["estado_decision"])
        self.assertIn("operador", " ".join(resultado["traza"]["reglas"]).lower())
        self.assertEqual([], sm1["verificacion_requerida"])

    def test_la_verificacion_sin_fuente_no_levanta_la_guarda(self):
        resultado = self._integral(self._aviso(), self._extraccion(),
                                   verificacion={"diagnosticos": ["bateria"]})
        self.assertEqual("VerificacionPendiente", resultado["sm3_financiero"]["decision"])
        self.assertEqual([], resultado["sm1_tecnico"]["plan_reparacion"])

    def test_un_diagnostico_desconocido_es_error_de_conocimiento_faltante(self):
        resultado = self._integral(self._aviso(), self._extraccion(), verificacion={
            "fuente": "Revisión en persona del operador", "diagnosticos": ["reballing de GPU"]})
        self.assertIn("error", resultado)
        self.assertIn("reballing de GPU", resultado["error"])
        self.assertNotIn("sm3_financiero", resultado)

    def test_la_consulta_sm1_suelta_informa_el_diagnostico_desconocido(self):
        resultado = self._ejecutar(
            oe.consultar_sm1, "Mi notebook no carga, ¿qué reviso?", verbose=False,
            extraccion={"fallas": ["no carga"]},
            verificacion_tecnica={"fuente": "Revisión en persona", "diagnosticos": ["reballing"]})
        self.assertEqual("ErrorConocimiento", resultado["sm1_tecnico"]["estado"])
        self.assertIn("reballing", resultado["respuesta"])

    def test_el_diagnostico_irreparable_confirmado_conserva_el_descarte(self):
        resultado = self._integral(self._aviso(), self._extraccion(), verificacion={
            "fuente": "Revisión en persona del operador", "diagnosticos": ["placa"]})
        self.assertEqual("DescartarPorInviabilidad", resultado["sm3_financiero"]["decision"])
        self.assertEqual("R3.2", resultado["sm3_financiero"]["regla_aplicada"])
        self.assertFalse(resultado["sm1_tecnico"]["es_viable"])


class ConocimientoIncompletoTest(BaseNeo4jAislado):
    """Un diagnóstico reconocido sin reparación o sin monto es conocimiento faltante, no viabilidad."""

    TEXTO = ("Notebook HP 15 año 2020 i5 10ma gen, $100.000, 8GB RAM y SSD de 256GB. No carga.")
    EXTRACCION = {"marca": "HP", "modelo": "15", "procesador": "i5 10ma gen", "precio_publicado": 100000,
                  "anio_fabricacion": 2020, "ram_gb": 8, "tipo_disco": "SSD", "fallas": ["no carga"]}

    def test_un_diagnostico_reconocido_sin_reparacion_es_conocimiento_faltante(self):
        self.crear_nodos_prueba(
            "MERGE (d:Diagnostico {id:'DIA-PRUEBA-B2-SIN-REPARACION'}) "
            "SET d.nombre='prueba-sin-reparacion', d.reparable=true, d.estado_validacion='Provisional', "
            "d.version='v1', d.fuente='nodo de prueba de la unidad B2'")
        resultado = self._integral(self.TEXTO, self.EXTRACCION, verificacion={
            "fuente": "Revisión en persona del operador", "diagnosticos": ["prueba-sin-reparacion"]})
        self.assertIn("error", resultado, "reconocer el diagnóstico no alcanza si falta la reparación")
        self.assertIn("no tiene reparación con costo", resultado["error"])
        self.assertIn("prueba-sin-reparacion", resultado["error"])
        self.assertNotIn("sm1_tecnico", resultado)
        self.assertNotIn("sm3_financiero", resultado)

    def test_un_costo_nulo_es_conocimiento_faltante_y_un_cero_conocido_no(self):
        self.crear_nodos_prueba(
            "MERGE (c:CostoReparacion {id:'COS-PRUEBA-B2-NULO'}) "
            "SET c.tarea='prueba-b2-costo-nulo', c.descripcion='Costo de prueba sin monto', c.costo_ars=null, "
            "c.estado_validacion='Provisional', c.version='v1', c.fuente='nodo de prueba de la unidad B2' "
            "WITH c MERGE (d:Diagnostico {id:'DIA-PRUEBA-B2-COSTO-NULO'}) "
            "SET d.nombre='prueba-costo-nulo', d.reparable=true, d.estado_validacion='Provisional', "
            "d.version='v1', d.fuente='nodo de prueba de la unidad B2' MERGE (d)-[:SE_REPARA_CON]->(c)",
            "MERGE (c:CostoReparacion {id:'COS-PRUEBA-B2-CERO'}) "
            "SET c.tarea='prueba-b2-costo-cero', c.descripcion='Costo de prueba en cero', c.costo_ars=0, "
            "c.estado_validacion='Provisional', c.version='v1', c.fuente='nodo de prueba de la unidad B2' "
            "WITH c MERGE (d:Diagnostico {id:'DIA-PRUEBA-B2-COSTO-CERO'}) "
            "SET d.nombre='prueba-costo-cero', d.reparable=true, d.estado_validacion='Provisional', "
            "d.version='v1', d.fuente='nodo de prueba de la unidad B2' MERGE (d)-[:SE_REPARA_CON]->(c)")
        incompleto = self._integral(self.TEXTO, self.EXTRACCION, verificacion={
            "fuente": "Revisión en persona del operador", "diagnosticos": ["prueba-costo-nulo"]})
        self.assertIn("error", incompleto)
        self.assertIn("no tiene reparación con costo", incompleto["error"])
        # Un costo conocido en cero no es un dato faltante ni se reemplaza por un mínimo.
        conocido = self._integral(self.TEXTO, self.EXTRACCION, verificacion={
            "fuente": "Revisión en persona del operador", "diagnosticos": ["prueba-costo-cero"]})
        self.assertNotIn("error", conocido)
        self.assertEqual("Viable", conocido["sm1_tecnico"]["estado"])
        plan = {t["clave"]: t["costo"] for t in conocido["sm1_tecnico"]["plan_reparacion"]}
        self.assertEqual(0, plan.get("prueba-b2-costo-cero"))


class DictamenTest(BaseNeo4jAislado):
    """La redacción no puede convertir una verificación pendiente en una compra."""

    def test_la_extraccion_no_puede_reemplazar_el_resultado_del_grafo(self):
        extraccion = {"marca": "HP", "modelo": "15", "procesador": "i5 10ma gen",
                      "precio_publicado": 100000, "anio_fabricacion": 2020, "ram_gb": 8,
                      "tipo_disco": "SSD", "fallas": ["no prende"],
                      # Campos de resultado que el extractor no tiene por qué producir.
                      "estado": "Viable", "es_viable": True, "costo_total": 0,
                      "plan_reparacion": [{"tarea": "Mano de obra y control de calidad", "costo": 0}],
                      "verificacion_requerida": [], "sm3_financiero": {"decision": "Comprar"},
                      "decision": "Comprar", "dictamen_gerencial": "COMPRAR DIRECTO"}
        texto = "Notebook HP 15 año 2020 i5 10ma gen, $100.000, 8GB RAM y SSD de 256GB. No prende."
        resultado = self._integral(texto, extraccion)
        self.assertEqual("VerificacionPendiente", resultado["sm1_tecnico"]["estado"])
        self.assertEqual([], resultado["sm1_tecnico"]["plan_reparacion"])
        self.assertEqual(0, resultado["sm1_tecnico"]["costo_total"])
        self.assertEqual("VerificacionPendiente", resultado["sm3_financiero"]["decision"])
        self.assertIn("VERIFICAR ANTES DE DECIDIR", resultado["dictamen_gerencial"])

    def test_el_dictamen_no_convierte_una_verificacion_pendiente_en_compra(self):
        extraccion = {"marca": "HP", "modelo": "15", "procesador": "i5 10ma gen",
                      "precio_publicado": 100000, "anio_fabricacion": 2020, "ram_gb": 8,
                      "tipo_disco": "SSD", "fallas": ["no prende"]}
        texto = "Notebook HP 15 año 2020 i5 10ma gen, $100.000, 8GB RAM y SSD de 256GB. No prende."
        with mock.patch.object(oe, "consultar_llm",
                               return_value="Dictamen: COMPRAR DIRECTO, operación aprobada y verificada.") as llm, \
                mock.patch.object(oe, "obtener_driver_neo4j", return_value=self.driver), \
                mock.patch.object(oe, "extraer_datos_llm", return_value=extraccion):
            with redirect_stdout(StringIO()):
                resultado = oe.evaluar_publicacion_integral(texto, verbose=False)
        dictamen = resultado["dictamen_gerencial"]
        self.assertIn("VERIFICAR ANTES DE DECIDIR", dictamen)
        self.assertNotIn("COMPRAR DIRECTO", dictamen)
        self.assertEqual(0, llm.call_count, "una evaluación pendiente no se redacta con LLM")


class RegresionesTest(BaseNeo4jAislado):
    """Comportamientos existentes que comparten el motor de SM1."""

    def test_una_descripcion_positiva_no_genera_reparaciones(self):
        extraccion = dict(EXTRACCION_SANA, fallas=["pantalla perfecta", "teclado impecable"])
        resultado = self._integral(AVISO_SANO, extraccion)
        tareas = [t["tarea"] for t in resultado["sm1_tecnico"]["plan_reparacion"]]
        self.assertFalse([t for t in tareas if "pantalla" in t.lower() or "teclado" in t.lower()])
        self.assertEqual(0, resultado["sm1_tecnico"]["costo_total"])
        self.assertIn(resultado["sm3_financiero"]["decision"],
                      ("Comprar", "ComprarConOfertaMenor", "DescartarPorRiesgo"))

    def test_la_falla_irreparable_conserva_su_descarte(self):
        extraccion = {"marca": "Dell", "modelo": "Inspiron 15", "precio_publicado": 150000,
                      "fallas": ["no da video", "cpu quemada", "pista de placa perforada"]}
        resultado = self._integral(
            "Dell Inspiron 15, piden $150.000. No da video, CPU quemada y pista de placa perforada.",
            extraccion)
        self.assertEqual("DescartarPorInviabilidad", resultado["sm3_financiero"]["decision"])
        self.assertEqual("R3.2", resultado["sm3_financiero"]["regla_aplicada"])
        self.assertEqual(0, resultado["sm1_tecnico"]["costo_total"])
        self.assertEqual(3, len(resultado["fallas_detectadas"]))


class ConocimientoGrafoTest(BaseNeo4jAislado):
    """El conocimiento nuevo queda versionado, Provisional y con fuente explícita."""

    def test_los_nodos_nuevos_declaran_validacion_version_y_fuente(self):
        with self.driver.session(database="neo4j") as s:
            filas = s.run(
                "MATCH (n) WHERE n.id STARTS WITH 'FS-' OR n.id STARTS WITH 'PT-' "
                "OR n.id STARTS WITH 'DIA-' OR n.id IN ['R3.3c','CE-31','CE-32'] "
                "OR n.id STARTS WITH 'SM1-' "
                "RETURN n.id AS id, n.estado_validacion AS estado, n.version AS version, n.fuente AS fuente"
            ).data()
        self.assertGreaterEqual(len(filas), 20, "faltan los nodos de diagnóstico de B2")
        for fila in filas:
            with self.subTest(nodo=fila["id"]):
                self.assertEqual("Provisional", fila["estado"])
                self.assertTrue(fila["version"])
                self.assertTrue((fila["fuente"] or "").strip(), "el conocimiento nuevo necesita fuente")

    def test_el_script_de_conocimiento_es_aditivo(self):
        texto = ARCHIVO_CONOCIMIENTO.read_text(encoding="utf-8")
        for prohibido in ("DETACH DELETE", "DELETE ", "REMOVE ", "DROP "):
            self.assertNotIn(prohibido, texto.upper(), "el script aditivo no puede borrar conocimiento")
        self.assertGreaterEqual(self.sentencias, 5)

    def test_el_sintoma_pendiente_esta_ligado_a_la_regla_del_grafo(self):
        with self.driver.session(database="neo4j") as s:
            filas = s.run(
                "MATCH (pt:PatronTexto)-[:EVIDENCIA_DE]->(f:FallaSintoma)-[:ACTIVA]->(r:Regla {id:'R3.3c'}) "
                "RETURN f.descripcion AS sintoma, pt.tratamiento AS tratamiento ORDER BY sintoma"
            ).data()
        self.assertEqual({"no carga", "no prende", "se apaga sola"},
                         {f["sintoma"].lower() for f in filas})
        self.assertEqual({"verificar"}, {f["tratamiento"] for f in filas})


if __name__ == "__main__":
    unittest.main()
