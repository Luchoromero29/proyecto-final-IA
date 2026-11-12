"""P3a/P3b — la condición del filtro R3.7 y las categorías de R3.8 se leen de la Regla.

Cada prueba abre una transacción sobre el scratch marcado y la revierte: los seeds P3a y P3b
(riesgo y demanda de R3.8) se aplican dentro de esa transacción (la activación en el grafo de
trabajo la integra el padre después) y ninguna mutación queda persistida. Reutiliza el
aislamiento dotenv/driver explícito de test_sm3_neo4j y su adaptador público; no llama al LLM
ni al grafo original.
"""
from contextlib import contextmanager
from pathlib import Path
import unittest
from unittest import mock

import test_sm3_neo4j as base

setUpModule = base.setUpModule
tearDownModule = base.tearDownModule
SEMILLA = Path(__file__).resolve().parents[2] / "cypher/Grupo_20_PG3_politicas_sm3_filtro.cypher"
SEMILLA_RIESGO_DEMANDA = (Path(__file__).resolve().parents[2]
                          / "cypher/Grupo_20_PG3_politicas_sm3_riesgo_demanda.cypher")
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
        # Datos antes del consumidor: R3.7 y R3.8 configuradas dentro de la transacción.
        self._cargar()
        self._cargar_riesgo_demanda()

    def _cargar(self):
        return self.tx.run(SEMILLA.read_text(encoding="utf-8")).single(strict=True)

    def _cargar_riesgo_demanda(self):
        return self.tx.run(SEMILLA_RIESGO_DEMANDA.read_text(encoding="utf-8")).single(strict=True)

    def _proyeccion(self, regla="R3.7"):
        return [dict(r) for r in self.tx.run(
            "MATCH (r:Regla {id:$regla}) RETURN properties(r) AS propiedades", regla=regla)]

    def _criterio(self, nombre):
        return self.tx.run(
            "MATCH (:Regla {id:'R3.7'})-[:USA_CRITERIO]->(ce:CriterioExperto {nombre:$nombre}) "
            "RETURN ce.valor AS valor", nombre=nombre).single()["valor"]

    def _inferir(self, costo, vma=1000000, riesgo="Medio", demanda="Media"):
        return base.ism3.inferir_sm3_crisp_cypher(
            self.driver, base.BASE_PRUEBAS, PRECIO, costo, vma, 0, riesgo, demanda)

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

    def test_el_motivo_de_r38_sigue_las_categorias_del_grafo(self):
        with mock.patch.object(base.oe, "obtener_driver_neo4j", lambda: self.driver):
            resultado = base.oe.ejecutar_motor_sm3(PRECIO, 0, 1000000, 0, "Alto", "Baja",
                                                   base.oe.nueva_traza())
        self.assertEqual("Riesgo de obsolescencia Alto con demanda comercial Baja (inmovilización de capital).",
                         resultado["motivo"])
        self.tx.run("MATCH (r:Regla {id:'R3.8'}) SET r.filtro_demanda='Media'").consume()
        traza = base.oe.nueva_traza()
        with mock.patch.object(base.oe, "obtener_driver_neo4j", lambda: self.driver):
            resultado = base.oe.ejecutar_motor_sm3(PRECIO, 0, 1000000, 0, "Alto", "Media", traza)
        self.assertEqual(("R3.8", "DescartarPorRiesgo"),
                         (resultado["regla_aplicada"], resultado["decision"]))
        self.assertEqual("Riesgo de obsolescencia Alto con demanda comercial Media (inmovilización de capital).",
                         resultado["motivo"])
        self.assertEqual(["R3.8: riesgo Alto y demanda Media → DescartarPorRiesgo"], traza["reglas"])

    def test_r38_descarta_con_las_categorias_guardadas_en_la_regla(self):
        fila = self._inferir(0, riesgo="Alto", demanda="Baja")
        self.assertEqual(("R3.8", "DescartarPorRiesgo"), (fila["regla"], fila["decision"]))
        self.assertEqual(["R3.8: riesgo Alto y demanda Baja → DescartarPorRiesgo"],
                         fila["reglas_activadas"])

    def test_las_categorias_guardadas_cambian_el_filtro_publico(self):
        self.tx.run("MATCH (r:Regla {id:'R3.8'}) SET r.filtro_demanda='Media'").consume()
        self.assertIsNone(self._inferir(0, riesgo="Alto", demanda="Baja")["regla"])
        fila = self._inferir(0, riesgo="Alto", demanda="Media")
        self.assertEqual(("R3.8", "DescartarPorRiesgo"), (fila["regla"], fila["decision"]))
        self.assertEqual(["R3.8: riesgo Alto y demanda Media → DescartarPorRiesgo"],
                         fila["reglas_activadas"])

    def test_r37_conserva_la_precedencia_sobre_r38(self):
        ratio_max = self._criterio("ratio_reparacion_max")
        fila = self._inferir(int(1000000 * (ratio_max + 0.1)), riesgo="Alto", demanda="Baja")
        self.assertEqual(("R3.7", "DescartarPorRiesgo"), (fila["regla"], fila["decision"]))
        self.assertEqual(["R3.7: costo / VMA > CE ratio_reparacion_max → DescartarPorRiesgo"],
                         fila["reglas_activadas"])

    def test_configuracion_invalida_de_r38_falla_con_el_error_existente(self):
        for propiedades in ({"filtro_demanda": "MuyBaja"}, {"filtro_riesgo": None}):
            with self.subTest(propiedades=propiedades):
                self.tx.run("MATCH (r:Regla {id:'R3.8'}) SET r += $propiedades",
                            propiedades=propiedades).consume()
                self.assertIsNone(self._inferir(0, riesgo="Alto", demanda="Baja"))
                with mock.patch.object(base.oe, "obtener_driver_neo4j", lambda: self.driver):
                    with self.assertRaises(RuntimeError):
                        base.oe.ejecutar_motor_sm3(PRECIO, 0, 1000000, 0, "Alto", "Baja",
                                                   base.oe.nueva_traza())

    def test_seed_riesgo_demanda_es_idempotente_y_un_conflicto_no_escribe(self):
        antes = self._proyeccion("R3.8")
        segunda = self._cargar_riesgo_demanda()
        self.assertEqual((1, 0, []), (segunda["configuradas"], segunda["actualizadas"],
                                      segunda["errores"]))
        self.assertEqual(antes, self._proyeccion("R3.8"))
        self.tx.run("MATCH (r:Regla {id:'R3.8'}) SET r.filtro_riesgo='Medio'").consume()
        antes = self._proyeccion("R3.8")
        conflicto = self._cargar_riesgo_demanda()
        self.assertEqual((0, 0), (conflicto["configuradas"], conflicto["actualizadas"]))
        self.assertTrue(conflicto["errores"])
        self.assertEqual(antes, self._proyeccion("R3.8"))

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
