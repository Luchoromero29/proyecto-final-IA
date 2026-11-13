#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pruebas aisladas de SM1 (B2) — las políticas que antes decidía Python, ejercitadas por
las funciones públicas del motor contra un Neo4j NUEVO y reconstruible.

Cubre la equivalencia de comportamiento migrada al grafo: batería difusa y crisp,
temperatura difusa y crisp, RAM, disco, pantalla/teclado/cargador, mano de obra,
intervenciones únicas y fallas irreparables. La extracción del LLM es controlada y la
redacción está desactivada, así que sólo se observa la inferencia simbólica.

Preparación (el grafo de pruebas ya debe existir; este archivo NO lo crea ni lo borra):

    EVALTIC_NEO4J_PRUEBAS_URI=bolt://127.0.0.1:17687 \\
    PYTHONDONTWRITEBYTECODE=1 /home/alvaro/Universidad/IA/Proyecto/.venv/bin/python \\
        -m unittest discover -s app/tests -p test_sm1_neo4j.py -v
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

URI_PRUEBAS = os.environ.get("EVALTIC_NEO4J_PRUEBAS_URI", "").strip()
for _clave, _valor in {
    "LLM_PROVIDER": "ollama",
    "OLLAMA_URL": "http://ollama.invalid/api/generate",
    "OLLAMA_MODEL": "modelo-ollama-de-prueba",
    "NEO4J_TARGET": "local",
    "NEO4J_LOCAL_URI": URI_PRUEBAS or "bolt://neo4j.invalid:7687",
    "NEO4J_LOCAL_USERNAME": "",
    "NEO4J_LOCAL_PASSWORD": "",
    "NEO4J_LOCAL_DATABASE": "neo4j",
}.items():
    os.environ[_clave] = _valor

with mock.patch("dotenv.load_dotenv", return_value=False):
    import orquestador_evaltic as oe

MARCADOR = "mejoras-evaltic"
HOSTS_PRUEBA = {"127.0.0.1", "localhost"}


def _driver_aislado():
    """Conecta al Neo4j de pruebas declarado; rechaza cualquier otro destino."""
    if not URI_PRUEBAS:
        raise unittest.SkipTest(
            "falta EVALTIC_NEO4J_PRUEBAS_URI (Neo4j aislado de pruebas); no se ejecuta contra el grafo de trabajo")
    host = URI_PRUEBAS.split("://", 1)[-1].rsplit(":", 1)[0]
    if host not in HOSTS_PRUEBA:
        raise AssertionError(f"EVALTIC_NEO4J_PRUEBAS_URI debe ser local ({URI_PRUEBAS}); "
                             f"las pruebas no tocan el grafo de trabajo")
    import neo4j
    driver = neo4j.GraphDatabase.driver(URI_PRUEBAS, auth=None)
    with driver.session(database="neo4j") as s:
        if s.run("MATCH (m:EntornoPruebas {id:$id}) RETURN count(m) AS n", id=MARCADOR).single()["n"] != 1:
            raise unittest.SkipTest(f"el Neo4j de pruebas no tiene el marcador EntornoPruebas '{MARCADOR}'")
    return driver


class BaseSm1Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.driver = _driver_aislado()

    @classmethod
    def tearDownClass(cls):
        cls.driver.close()

    def _diagnostico(self, texto, datos):
        """Ejecuta el diagnóstico SM1 público con extracción controlada y sin LLM."""
        with mock.patch.object(oe, "obtener_driver_neo4j", return_value=self.driver), \
                mock.patch.object(oe, "consultar_llm", side_effect=ConnectionError("sin LLM en pruebas")), \
                mock.patch.object(oe, "_llm_json", side_effect=lambda _p, _t: json.loads(json.dumps(datos))):
            with redirect_stdout(StringIO()):
                return oe.consultar_sm1(texto, verbose=False)


class PoliticasMigradasTest(BaseSm1Test):
    """Las decisiones vigentes de SM1 se conservan, ahora inferidas en Cypher."""

    def _tareas(self, resultado):
        return [t["tarea"] for t in resultado["sm1_tecnico"]["plan_reparacion"]]

    def test_bateria_difusa_obligatoria_agrega_el_reemplazo_del_grafo(self):
        resultado = self._diagnostico("Batería al 40% con 900 ciclos.",
                                      {"salud_bateria_pct": 40, "ciclos_bateria": 900})
        self.assertIn("Reemplazo de batería", self._tareas(resultado))
        costo = resultado["traza"]["costos_usados"]["bateria"]
        self.assertEqual(("COS-BAT", 75000, "Provisional"), (costo["id"], costo["costo"], costo["estado"]))

    def test_bateria_crisp_usa_el_criterio_del_grafo_cuando_faltan_los_ciclos(self):
        resultado = self._diagnostico("Batería al 50%.", {"salud_bateria_pct": 50})
        self.assertIn("Reemplazo de batería", self._tareas(resultado))
        criterio = resultado["traza"]["criterios_usados"]["bateria_reemplazo"]
        self.assertEqual(("CE-01", 75), (criterio["id"], criterio["valor"]))

    def test_bateria_sana_no_genera_reemplazo(self):
        resultado = self._diagnostico("Batería al 95% con 120 ciclos.",
                                      {"salud_bateria_pct": 95, "ciclos_bateria": 120})
        self.assertNotIn("Reemplazo de batería", self._tareas(resultado))

    def test_temperatura_con_throttling_usa_la_caida_sintetica_del_grafo(self):
        resultado = self._diagnostico("Calienta a 95°C con cuelgues.",
                                      {"temperatura_cpu_c": 95, "thermal_throttling": True})
        self.assertIn("Service térmico (pasta térmica y limpieza)", self._tareas(resultado))
        caida = resultado["traza"]["criterios_usados"]["caida_termica_con_throttling"]
        self.assertEqual(("CE-32", 20), (caida["id"], caida["valor"]))

    def test_temperatura_sin_dato_de_throttling_usa_la_caida_leve_y_lo_declara(self):
        resultado = self._diagnostico("Calienta a 95°C.", {"temperatura_cpu_c": 95})
        self.assertIn("Service térmico (pasta térmica y limpieza)", self._tareas(resultado))
        caida = resultado["traza"]["criterios_usados"]["caida_termica_sin_throttling"]
        self.assertEqual(("CE-31", 5), (caida["id"], caida["valor"]))
        self.assertIn("caida_termica_sin_throttling", " ".join(resultado["traza"]["datos_inferidos"]))

    def test_temperatura_fresca_no_pide_service_termico(self):
        resultado = self._diagnostico("Temperatura 50°C sin throttling.",
                                      {"temperatura_cpu_c": 50, "thermal_throttling": False})
        self.assertNotIn("Service térmico (pasta térmica y limpieza)", self._tareas(resultado))

    def test_ram_bajo_el_objetivo_se_amplia_y_supera_el_objetivo_no(self):
        bajo = self._diagnostico("Tiene 4GB de RAM.", {"ram_gb": 4})
        self.assertIn("Ampliación de RAM a 8 GB", self._tareas(bajo))
        self.assertTrue(bajo["sm1_tecnico"]["upgrades"]["ram"])
        suficiente = self._diagnostico("Tiene 16GB de RAM.", {"ram_gb": 16})
        self.assertNotIn("Ampliación de RAM a 8 GB", self._tareas(suficiente))
        self.assertFalse(suficiente["sm1_tecnico"]["upgrades"]["ram"])

    def test_hdd_se_reemplaza_por_ssd_y_el_ssd_no(self):
        hdd = self._diagnostico("Disco HDD de 1TB.", {"tipo_disco": "HDD"})
        self.assertIn("Reemplazo de HDD por SSD 480 GB", self._tareas(hdd))
        self.assertTrue(hdd["sm1_tecnico"]["upgrades"]["ssd"])
        ssd = self._diagnostico("Disco SSD de 512GB.", {"tipo_disco": "SSD"})
        self.assertNotIn("Reemplazo de HDD por SSD 480 GB", self._tareas(ssd))
        self.assertFalse(ssd["sm1_tecnico"]["upgrades"]["ssd"])

    def test_cargador_ausente_se_repone_y_el_campo_que_lo_incluye_manda(self):
        sin_cargador = self._diagnostico("Viene sin cargador.", {"cargador_incluido": False})
        self.assertIn("Cargador compatible", self._tareas(sin_cargador))
        incluido = self._diagnostico("Incluye cargador original.", {"cargador_incluido": True,
                                                                    "fallas": ["sin cargador"]})
        self.assertNotIn("Cargador compatible", self._tareas(incluido))

    def test_la_mano_de_obra_se_cobra_una_vez_y_no_cuenta_como_intervencion(self):
        resultado = self._diagnostico("Pantalla rota.", {"pantalla_danada": True})
        tareas = self._tareas(resultado)
        self.assertEqual(1, tareas.count("Mano de obra y control de calidad"))
        self.assertEqual(1, resultado["sm1_tecnico"]["cantidad_intervenciones"])
        # Pantalla (COS-PAN) + mano de obra (COS-MO), ambos del grafo de pruebas.
        self.assertEqual(160000 + 40000, resultado["sm1_tecnico"]["costo_total"])

    def test_una_misma_intervencion_no_se_repite(self):
        resultado = self._diagnostico("Pantalla con rayas y pantalla rota.",
                                      {"pantalla_danada": True, "fallas": ["pantalla con rayas"]})
        tareas = self._tareas(resultado)
        self.assertEqual(1, tareas.count("Reemplazo de módulo de pantalla"))
        self.assertEqual(1, resultado["sm1_tecnico"]["cantidad_intervenciones"])

    def test_un_equipo_sin_fallas_ni_datos_faltantes_no_tiene_plan(self):
        resultado = self._diagnostico("Notebook sana, 8GB de RAM y SSD, batería al 95% con 100 ciclos.",
                                      {"salud_bateria_pct": 95, "ciclos_bateria": 100, "temperatura_cpu_c": 50,
                                       "thermal_throttling": False, "ram_gb": 8, "tipo_disco": "SSD"})
        self.assertEqual("Viable", resultado["sm1_tecnico"]["estado"])
        self.assertEqual([], self._tareas(resultado))
        self.assertEqual(0, resultado["sm1_tecnico"]["costo_total"])

    def test_los_datos_faltantes_quedan_como_pendientes_de_verificacion(self):
        resultado = self._diagnostico("Notebook usada, anda bien.", {})
        pendientes = " ".join(resultado["traza"]["datos_pendientes"]).lower()
        for dato in ("batería", "temperatura", "memoria ram", "tipo de disco"):
            self.assertIn(dato, pendientes)
        self.assertEqual("Viable", resultado["sm1_tecnico"]["estado"])


class FallaIrreparableTest(BaseSm1Test):
    """La semántica de las fallas irreparables se conserva, con los patrones en el grafo."""

    def test_las_fallas_irreparables_conservan_el_descarte(self):
        for falla in ("no da video", "cpu quemada", "pista de placa perforada", "sulfatación por derrame"):
            with self.subTest(falla=falla):
                resultado = self._diagnostico(f"Falla: {falla}.", {"fallas": [falla]})
                self.assertEqual("Inviable", resultado["sm1_tecnico"]["estado"])
                self.assertFalse(resultado["sm1_tecnico"]["es_viable"])
                self.assertEqual([], resultado["sm1_tecnico"]["plan_reparacion"])
                self.assertEqual(0, resultado["sm1_tecnico"]["costo_total"])

    def test_una_falla_modular_con_reparacion_conocida_no_es_inviable(self):
        resultado = self._diagnostico("Teclado roto.", {"teclado_danado": True, "fallas": ["teclado roto"]})
        self.assertEqual("Viable", resultado["sm1_tecnico"]["estado"])
        self.assertIn("Reemplazo de teclado",
                      [t["tarea"] for t in resultado["sm1_tecnico"]["plan_reparacion"]])


if __name__ == "__main__":
    unittest.main()
