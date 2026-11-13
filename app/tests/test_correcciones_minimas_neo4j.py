#!/usr/bin/env python3
"""Regresiones públicas del bloque mínimo sobre transacciones que se revierten.

Sólo scratch marcado; sin .env ni proveedor real. El LLM se simula para separar
extracción de inferencia, pero las reglas y consultas usan Neo4j de verdad.
La corrida real de61es otro proceso de la misma fase final, no estos dobles.
"""
import copy
import json
import unittest
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from io import StringIO
from unittest import mock

import test_sm3_neo4j as base
import test_publicaciones_criticas as corpus
from scripts.probar_publicaciones import _comprobar

setUpModule = base.setUpModule
tearDownModule = base.tearDownModule


class DriverTransaccion:
    def __init__(self, tx):
        self.tx = tx

    @contextmanager
    def session(self, database=None):
        yield self.tx


class CorreccionesMinimasTest(unittest.TestCase):
    def setUp(self):
        self.sesion = base._driver.session(database=base.BASE_PRUEBAS)
        self.addCleanup(self.sesion.close)
        self.tx = self.sesion.begin_transaction()
        self.addCleanup(self.tx.rollback)
        self.parche = mock.patch.object(base.oe, "obtener_driver_neo4j",
                                        lambda: DriverTransaccion(self.tx))
        self.parche.start()
        self.addCleanup(self.parche.stop)
        base.oe._CONOCIMIENTO = None

    def _publico(self, ident, texto=None, datos=None, verificacion=None):
        caso = corpus.CASOS[ident]
        extraccion = copy.deepcopy(datos if datos is not None else caso["extraccion_llm"])
        llm = corpus._llm_falso(extraccion, caso.get("intencion_router", "evaluacion_integral"))
        salida, errores = StringIO(), StringIO()
        with mock.patch.object(base.oe, "consultar_llm", side_effect=llm), \
                redirect_stdout(salida), redirect_stderr(errores):
            resultado = base.oe.asistente_evaltic(texto or caso["entrada"], verbose=False,
                                                verificacion_tecnica=verificacion)
        self.assertEqual("", errores.getvalue())
        return resultado

    def test_fallos_reportados_cumplen_su_contrato_acordado(self):
        for ident in ("PC-01", "PC-15", "PC-17", "PC-44", "PC-48", "PC-50"):
            with self.subTest(caso=ident):
                resultado = self._publico(ident)
                self.assertEqual([], _comprobar(resultado, corpus.CASOS[ident]["espera"]))
                if ident == "PC-44":
                    self.assertEqual(0, resultado["sm1_tecnico"]["costo_total"])
                    self.assertEqual([], resultado["sm1_tecnico"]["plan_reparacion"])

    def test_supuesto_de_ciclos_se_informa_cuando_falta_el_dato(self):
        """Devolución de la cátedra: el supuesto está en el grafo y la explicación lo informa.

        Con salud por debajo de CE-01 y sin ciclos, la regla crisp cobra el reemplazo: el
        motor no inventa un número de ciclos, lo declara como supuesto operativo del grafo.
        Con los ciclos informados no hay supuesto que informar.
        """
        hechos = {"salud_bateria_pct": 60, "ciclos_bateria": None, "ram_gb": 8, "tipo_disco": "SSD",
                  "pantalla_danada": False, "teclado_danado": False, "cargador_incluido": True,
                  "temperatura_cpu_c": None, "thermal_throttling": None, "fallas": []}
        resultado = self._publico("PC-15", texto="Batería al 60%, 8GB y SSD. ¿Qué hay que reparar?",
                                  datos=hechos, verificacion=None)
        claves = [t["clave"] for t in resultado["sm1_tecnico"].get("plan_reparacion", [])]
        self.assertIn("bateria", claves)
        asumidos = resultado["traza"].get("datos_asumidos", [])
        self.assertTrue(asumidos, "el supuesto declarado en el grafo no llegó a la traza")
        self.assertIn("SUP-SM1-BAT-CICLOS", asumidos[0])
        self.assertEqual(1, resultado["respuesta"].count("Datos asumidos"),
                         "el supuesto se informa una sola vez, no duplicado")

        con_ciclos = dict(hechos, ciclos_bateria=900)
        resultado2 = self._publico("PC-15", texto="Batería al 60% con 900 ciclos, 8GB y SSD. ¿Qué reparar?",
                                   datos=con_ciclos, verificacion=None)
        self.assertEqual([], resultado2["traza"].get("datos_asumidos", []))
        self.assertNotIn("Datos asumidos", resultado2["respuesta"])

        # Salud por encima de CE-01: la regla crisp no dispara, así que no hay supuesto que
        # informar ni batería que cobrar aunque los ciclos falten.
        sobre_umbral = dict(hechos, salud_bateria_pct=80)
        resultado3 = self._publico("PC-15", texto="Batería al 80%, 8GB y SSD. ¿Qué hay que reparar?",
                                   datos=sobre_umbral, verificacion=None)
        claves3 = [t["clave"] for t in resultado3["sm1_tecnico"].get("plan_reparacion", [])]
        self.assertNotIn("bateria", claves3)
        self.assertEqual([], resultado3["traza"].get("datos_asumidos", []))
        self.assertNotIn("Datos asumidos", resultado3["respuesta"])

    def test_supuesto_ilegible_degrada_sin_abortar(self):
        """Si el supuesto no se puede leer, el dictamen sale igual y el dato queda pendiente.

        Revisión nativa: quitar el silencio no puede costar la degradación elegante. El
        fallo de una consulta auxiliar no aborta la evaluación técnica completa.
        """
        hechos = {"salud_bateria_pct": 60, "ciclos_bateria": None, "ram_gb": 8, "tipo_disco": "SSD",
                  "pantalla_danada": False, "teclado_danado": False, "cargador_incluido": True,
                  "temperatura_cpu_c": None, "thermal_throttling": None, "fallas": []}
        llm = lambda sp, uc, *a, **k: json.dumps(hechos) if "json" in sp.lower() else "reemplazo de bateria."
        with mock.patch.object(base.oe, "consultar_llm", side_effect=llm), \
                mock.patch.object(base.oe, "inferir_supuesto_cypher",
                                  side_effect=base.oe.SupuestoNoVerificado("falló la consulta")):
            resultado = base.oe.consultar_sm1(
                "Batería al 60% y sin ciclos informados. ¿Qué hay que reparar?", verbose=False)
        claves = [t["clave"] for t in resultado["sm1_tecnico"].get("plan_reparacion", [])]
        self.assertIn("bateria", claves, "el dictamen tiene que salir aunque el supuesto no se lea")
        self.assertEqual([], resultado["traza"]["datos_asumidos"])
        self.assertTrue(resultado["traza"]["supuesto_no_verificado"])
        self.assertIn("No se pudo verificar el supuesto de ciclos", resultado["respuesta"])

    def test_conserva_positivos_precio_y_procesador(self):
        for ident in ("PC-07", "PC-14", "PC-19", "PC-20", "PC-29", "PC-30", "PC-49"):
            with self.subTest(caso=ident):
                resultado = self._publico(ident)
                self.assertEqual([], _comprobar(resultado, corpus.CASOS[ident]["espera"]))

    def test_marca_de_impresora_no_basta_y_error_remoto_no_es_fuera_de_dominio(self):
        with mock.patch.object(base.oe, "_llm_json", return_value={"intencion": "fuera_de_dominio"}):
            self.assertEqual("fuera_de_dominio",
                             base.oe.enrutar_consulta("Vendo impresora HP")["intencion"])
        with mock.patch.object(base.oe, "_llm_json",
                               side_effect=RuntimeError("[ERROR API REMOTA] respuesta privada")):
            with self.assertRaises(RuntimeError):
                base.oe.enrutar_consulta("computadora asus, anda joya")

    def test_error_de_consulta_no_se_oculta_como_falta_de_dominio(self):
        with mock.patch.object(base.oe, "_llm_json", return_value={"intencion": "fuera_de_dominio"}), \
                mock.patch.object(base.oe, "obtener_driver_neo4j", side_effect=ConnectionError("privado")):
            with self.assertRaisesRegex(RuntimeError, r"\[ERROR INFERENCIA NEO4J\]"):
                base.oe.enrutar_consulta("computadora asus, anda joya")

    def test_precio_y_submodulos_sueltos_conservan_el_enrutamiento(self):
        with mock.patch.object(base.oe, "_llm_json", return_value={"intencion": "diagnostico_tecnico"}):
            self.assertEqual("evaluacion_integral",
                             base.oe.enrutar_consulta(corpus.CASOS["PC-15"]["entrada"])["intencion"])
            self.assertEqual("diagnostico_tecnico",
                             base.oe.enrutar_consulta("Mi notebook no prende")["intencion"])
        with mock.patch.object(base.oe, "_llm_json", return_value={"intencion": "valuacion_comercial"}):
            self.assertEqual("valuacion_comercial", base.oe.enrutar_consulta(
                "Cuánto vale una ThinkPad i5 10ma gen")["intencion"])

    def test_el_mapeo_termico_se_consume_del_grafo_sin_confundir_ausencia(self):
        for hecho, esperado in ((False, 0), (True, 20), (None, 5)):
            with self.subTest(hecho=hecho):
                self.assertEqual(esperado, base.oe.inferir_caida_termica_cypher(
                    hecho, base.oe.nueva_traza()))
        datos = copy.deepcopy(corpus.CASOS["PC-15"]["extraccion_llm"])
        datos["thermal_throttling"] = True
        resultado = self._publico("PC-15", datos=datos)
        self.assertIs(False, resultado["datos_extraidos"]["thermal_throttling"])
        self.assertEqual(0, resultado["sm1_tecnico"]["costo_total"])
        self.tx.run("MATCH(r:Regla {id:'R-SM1-TER-NEGADA'}) SET r.caida_pp=5").consume()
        resultado = self._publico("PC-15")
        self.assertTrue(any(p["clave"] == "service_termico"
                            for p in resultado["sm1_tecnico"]["plan_reparacion"]))

    def test_consecuencia_de_bloqueo_sale_del_grafo_y_negacion_no_oculta_otra_senal(self):
        self.tx.run("MATCH(r:Regla {id:'R-SM0-BLOQUEO'}) SET r.regla_publica='R3.3-prueba'").consume()
        resultado = self._publico("PC-49")
        self.assertEqual("R3.3-prueba", resultado["sm3_financiero"]["regla_aplicada"])
        self.assertTrue(resultado["sm3_financiero"]["motivo"].endswith("(R3.3-prueba)."))
        resultado = self._publico("PC-50", corpus.CASOS["PC-50"]["entrada"]
                                   + " Pero queda la cuenta de Apple del dueño anterior.")
        self.assertEqual("VerificacionPendiente", resultado["sm3_financiero"]["decision"])

    def test_sintoma_solo_se_libera_con_evidencia_separada_del_operador(self):
        datos = copy.deepcopy(corpus.CASOS["PC-17"]["extraccion_llm"])
        datos["fallas"] = ["se apaga sola"]
        texto = "Acer Aspire 5 año 2020 i5 10ma gen, $150.000, 8GB RAM, SSD, se apaga sola."
        resultado = self._publico("PC-17", texto, datos)
        self.assertEqual("R3.3c", resultado["sm3_financiero"]["regla_aplicada"])
        self.assertEqual([], resultado["sm1_tecnico"]["plan_reparacion"])
        self.assertEqual(0, resultado["sm1_tecnico"]["costo_total"])
        resultado = self._publico("PC-17", texto, datos,
                                  {"fuente": "verificación presencial", "diagnosticos": ["bateria"]})
        self.assertEqual("Viable", resultado["sm1_tecnico"]["estado"])
        self.assertTrue(any(p["clave"] == "bateria"
                            for p in resultado["sm1_tecnico"]["plan_reparacion"]))

    def test_falta_de_politica_no_se_oculta_con_vocabulario_python(self):
        self.tx.run("MATCH(:PatronTexto {ambito:'SM0-dominio'})-[r:ACTIVA]->() DELETE r").consume()
        with mock.patch.object(base.oe, "_llm_json", return_value={"intencion": "fuera_de_dominio"}):
            with self.assertRaises(base.oe.ConocimientoFaltante):
                base.oe.enrutar_consulta("computadora asus, anda joya")


if __name__ == "__main__":
    unittest.main()
