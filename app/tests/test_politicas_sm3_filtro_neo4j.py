"""P3a — la condición del filtro R3.7 se lee de la Regla existente y de su criterio enlazado.

Cada prueba abre una transacción sobre el scratch marcado y la revierte: el seed P3a se
aplica dentro de esa transacción (la activación en el grafo de trabajo la integra el padre
después) y ninguna mutación queda persistida. Reutiliza el aislamiento dotenv/driver
explícito de test_sm3_neo4j y su adaptador público; no llama al LLM ni al grafo original.
"""
from contextlib import contextmanager
from pathlib import Path
import unittest
from unittest import mock

import test_sm3_neo4j as base

setUpModule = base.setUpModule
tearDownModule = base.tearDownModule
SEMILLA = Path(__file__).resolve().parents[2] / "cypher/Grupo_20_PG3_politicas_sm3_filtro.cypher"
PRECIO = 400000


class DriverTransaccion:
    """Las sesiones del consumidor público comparten la transacción que se revierte."""

    def __init__(self, tx):
        self.tx = tx

    @contextmanager
    def session(self, database=None):
        yield self.tx


class FiltroR37EnGrafoTest(unittest.TestCase):
    def setUp(self):
        self.sesion = base._driver.session(database=base.BASE_PRUEBAS)
        self.addCleanup(self.sesion.close)
        self.tx = self.sesion.begin_transaction()
        self.addCleanup(self.tx.rollback)
        self.driver = DriverTransaccion(self.tx)

    def _cargar(self):
        return self.tx.run(SEMILLA.read_text(encoding="utf-8")).single(strict=True)

    def _proyeccion(self):
        return [dict(r) for r in self.tx.run(
            "MATCH (r:Regla {id:'R3.7'}) RETURN properties(r) AS propiedades")]

    def _criterio(self, nombre):
        return self.tx.run(
            "MATCH (:Regla {id:'R3.7'})-[:USA_CRITERIO]->(ce:CriterioExperto {nombre:$nombre}) "
            "RETURN ce.valor AS valor", nombre=nombre).single()["valor"]

    def _inferir(self, costo, vma=1000000):
        return base.ism3.inferir_sm3_crisp_cypher(
            self.driver, base.BASE_PRUEBAS, PRECIO, costo, vma, 0, "Medio", "Media")

    def test_politica_por_defecto_conserva_el_umbral_y_la_traza(self):
        self._cargar()
        ratio_max = self._criterio("ratio_reparacion_max")
        en_el_umbral = self._inferir(int(1000000 * ratio_max))
        self.assertEqual(ratio_max, en_el_umbral["ratio_reparacion"])
        self.assertIsNone(en_el_umbral["regla"])
        self.assertIsNone(en_el_umbral["decision"])
        encima = self._inferir(int(1000000 * (ratio_max + 0.1)))
        self.assertEqual(("R3.7", "DescartarPorRiesgo"), (encima["regla"], encima["decision"]))
        self.assertEqual(["R3.7: costo / VMA > CE ratio_reparacion_max → DescartarPorRiesgo"],
                         encima["reglas_activadas"])

    def test_el_comparador_guardado_en_el_grafo_cambia_el_filtro_publico(self):
        self._cargar()
        self.assertIsNone(self._inferir(int(1000000 * 0.4))["regla"])
        self.tx.run("MATCH (r:Regla {id:'R3.7'}) SET r.filtro_comparador='<'").consume()
        fila = self._inferir(int(1000000 * 0.4))
        self.assertEqual(("R3.7", "DescartarPorRiesgo"), (fila["regla"], fila["decision"]))

    def test_el_criterio_enlazado_es_la_autoridad_del_umbral(self):
        self._cargar()
        self.tx.run(
            "MATCH (:Regla {id:'R3.7'})-[u:USA_CRITERIO]->(:CriterioExperto) DELETE u").consume()
        self.tx.run(
            "MATCH (r:Regla {id:'R3.7'}), (ce:CriterioExperto {nombre:'margen_base'}) "
            "CREATE (r)-[:USA_CRITERIO]->(ce)").consume()
        umbral = self._criterio("margen_base")
        fila = self._inferir(int(1000000 * (umbral + 0.01)))
        self.assertEqual(("R3.7", umbral), (fila["regla"], fila["ratio_max"]))

    def test_configuracion_invalida_falla_con_el_error_existente(self):
        self._cargar()
        for propiedades in ({"filtro_campo": "margen_neto"}, {"filtro_comparador": "="}):
            with self.subTest(propiedades=propiedades):
                self.tx.run("MATCH (r:Regla {id:'R3.7'}) SET r += $propiedades",
                            propiedades=propiedades).consume()
                self.assertIsNone(self._inferir(int(1000000 * 0.6)))
                with mock.patch.object(base.oe, "obtener_driver_neo4j", lambda: self.driver):
                    with self.assertRaises(RuntimeError):
                        base.oe.ejecutar_motor_sm3(PRECIO, 600000, 1000000, 0, "Medio", "Media",
                                                   base.oe.nueva_traza())

    def test_seed_es_idempotente_y_un_conflicto_no_escribe(self):
        self._cargar()
        antes = self._proyeccion()
        segunda = self._cargar()
        self.assertEqual((1, 0, []), (segunda["configuradas"], segunda["actualizadas"],
                                      segunda["errores"]))
        self.assertEqual(antes, self._proyeccion())
        self.tx.run("MATCH (r:Regla {id:'R3.7'}) SET r.filtro_comparador='<'").consume()
        antes = self._proyeccion()
        conflicto = self._cargar()
        self.assertEqual((0, 0), (conflicto["configuradas"], conflicto["actualizadas"]))
        self.assertTrue(conflicto["errores"])
        self.assertEqual(antes, self._proyeccion())


if __name__ == "__main__":
    unittest.main()
