"""Representación P1 sobre el scratch marcado; cada mutación se revierte por transacción.

Reutiliza el aislamiento dotenv/driver explícito de test_sm3_neo4j. No conecta al original,
no llama al LLM y no modifica valores/categorías/validación experta existentes.
"""
from contextlib import contextmanager
from pathlib import Path
import unittest

import test_sm3_neo4j as base

setUpModule = base.setUpModule
tearDownModule = base.tearDownModule
SEMILLA = Path(__file__).resolve().parents[2] / "cypher/Grupo_20_PG3_politicas.cypher"
VERSION = "politicas-P1-v1"


class DriverTransaccion:
    """Las sesiones del consumidor público comparten la transacción que se revierte."""

    def __init__(self, tx):
        self.tx = tx

    @contextmanager
    def session(self, database=None):
        yield self.tx


class RepresentacionComercialTest(unittest.TestCase):
    def setUp(self):
        self.sesion = base._driver.session(database=base.BASE_PRUEBAS)
        self.addCleanup(self.sesion.close)
        self.tx = self.sesion.begin_transaction()
        self.addCleanup(self.tx.rollback)
        self.driver = DriverTransaccion(self.tx)

    def _configurar(self, decision="Comprar", habilitada=False):
        self.tx.run(
            "MATCH (c:ConjuntoDifuso {id:'Conveniencia.Comprar'}) "
            "SET c.resultado_decision=$decision, c.contraoferta_habilitada=$habilitada, "
            "c.representacion_version=$version",
            decision=decision, habilitada=habilitada, version=VERSION).consume()

    def _resolver(self):
        return base.ism3.resolver_decision_sm3_cypher(
            self.driver, base.BASE_PRUEBAS, "Comprar", 123000)

    def test_cambiar_resultado_en_grafo_cambia_la_decision_publica(self):
        self._configurar(decision="DescartarPorRiesgo")
        self.assertEqual({"decision": "DescartarPorRiesgo", "contraoferta_sugerida_ars": None},
                         self._resolver())

    def test_habilitacion_en_grafo_no_depende_del_nombre_de_categoria(self):
        self._configurar(habilitada=True)
        self.assertEqual({"decision": "Comprar", "contraoferta_sugerida_ars": 123000},
                         self._resolver())

    def test_sin_correspondencia_no_se_compra_por_un_default(self):
        self._configurar(decision=None)
        self.assertEqual({"decision": None, "contraoferta_sugerida_ars": None}, self._resolver())

    def test_configuracion_invalida_o_ambigua_no_produce_compra(self):
        for decision, habilitada in (("Inventada", False), ("Comprar", "true"), ("Comprar", None)):
            with self.subTest(decision=decision, habilitada=habilitada):
                self._configurar(decision, habilitada)
                self.assertEqual({"decision": None, "contraoferta_sugerida_ars": None},
                                 self._resolver())
        self._configurar()
        self.tx.run(
            "MATCH (v:VariableDifusa {nombre:'Conveniencia'})-[:TIENE_CONJUNTO]->"
            "(c:ConjuntoDifuso {id:'Conveniencia.Comprar'}) "
            "CREATE (v)-[:TIENE_CONJUNTO]->(c)").consume()
        self.assertEqual({"decision": None, "contraoferta_sugerida_ars": None}, self._resolver())

    def _proyeccion(self):
        return [dict(r) for r in self.tx.run(
            "MATCH (c:ConjuntoDifuso) WHERE c.id STARTS WITH 'Conveniencia.' "
            "RETURN c.id AS id, properties(c) AS propiedades ORDER BY id")]

    def _cargar(self):
        return self.tx.run(SEMILLA.read_text(encoding="utf-8")).single(strict=True)

    def test_segunda_carga_no_cambia_propiedades_ni_reporta_escrituras(self):
        self._cargar()
        antes = self._proyeccion()
        respuesta = self._cargar()
        self.assertEqual(3, respuesta["configuradas"])
        self.assertEqual(0, respuesta["actualizadas"])
        self.assertEqual([], respuesta["errores"])
        self.assertEqual(antes, self._proyeccion())

    def test_carga_conflictiva_no_sobrescribe_ni_actualiza_otros_conjuntos(self):
        self._configurar(decision="DescartarPorRiesgo")
        antes = self._proyeccion()
        respuesta = self._cargar()
        self.assertEqual(0, respuesta["configuradas"])
        self.assertEqual(0, respuesta["actualizadas"])
        self.assertTrue(respuesta["errores"])
        self.assertEqual(antes, self._proyeccion())

    def test_carga_incompleta_no_aplica_un_subconjunto(self):
        self.tx.run(
            "MATCH (v:VariableDifusa {nombre:'Conveniencia'})-[r:TIENE_CONJUNTO]->"
            "(c:ConjuntoDifuso {id:'Conveniencia.Comprar'}) DELETE r").consume()
        antes = self._proyeccion()
        respuesta = self._cargar()
        self.assertEqual(0, respuesta["configuradas"])
        self.assertEqual(0, respuesta["actualizadas"])
        self.assertTrue(respuesta["errores"])
        self.assertEqual(antes, self._proyeccion())


if __name__ == "__main__":
    unittest.main()
