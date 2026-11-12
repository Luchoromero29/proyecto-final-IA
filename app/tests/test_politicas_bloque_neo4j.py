#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TB — Políticas del bloque en el grafo: margen y cuantización financiera (SM3), valuación,
R2.4 y clasificación del estado comercial (SM2) y clasificación Firme/Provisional (SM0).

Cada prueba carga `cypher/Grupo_20_PG3_politicas_bloque.cypher` dentro de una transacción
que SIEMPRE se revierte y, sobre esos datos, cambia sólo la representación (operación del
efecto, exclusión, precisión de cuantización, escala del VMA, activación de R2.4, estado
resultante) y observa la salida pública. Si el motor siguiera decidiendo en Python o en un
`CASE` por identificador, el cambio de datos no alteraría el resultado y la prueba fallaría.

Reutiliza el aislamiento de `test_sm3_neo4j` (dotenv mockeado antes de importar, driver
explícito, grafo marcado `EntornoPruebas {id:'mejoras-evaltic'}`). No toca el grafo de
trabajo ni el original, no llama al LLM y no deja datos: todo se revierte.

    EVALTIC_NEO4J_PRUEBAS_URI=bolt://127.0.0.1:17687 \\
        PYTHONDONTWRITEBYTECODE=1 /home/alvaro/Universidad/IA/Proyecto/.venv/bin/python \\
        -m unittest discover -s app/tests -p test_politicas_bloque_neo4j.py -v
"""

import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import test_sm3_neo4j as base

setUpModule = base.setUpModule
tearDownModule = base.tearDownModule
SEMILLA = (Path(__file__).resolve().parents[2]
           / "cypher/Grupo_20_PG3_politicas_bloque.cypher")
PRECIO = 400000
VMA = 1000000


class DriverTransaccion:
    """Las sesiones del consumidor público comparten la transacción que se revierte."""

    def __init__(self, tx):
        self.tx = tx

    @contextmanager
    def session(self, database=None):
        yield self.tx


class BloqueEnGrafoTest(unittest.TestCase):
    """Base común: transacción revertida, semilla cargada y consumidores sobre el grafo."""

    def setUp(self):
        self.sesion = base._driver.session(database=base.BASE_PRUEBAS)
        self.addCleanup(self.sesion.close)
        self.tx = self.sesion.begin_transaction()
        self.addCleanup(self.tx.rollback)
        self.driver = DriverTransaccion(self.tx)
        self.criterios = base._criterios()
        self._cargar()

    def _cargar(self):
        return self.tx.run(SEMILLA.read_text(encoding="utf-8")).single(strict=True)

    @contextmanager
    def _en_la_transaccion(self):
        with mock.patch.object(base.oe, "obtener_driver_neo4j", lambda: self.driver):
            yield

    def _valor(self, nombre):
        return self.criterios[nombre]["valor"]

    def _margen(self, costo=0, riesgo="Medio", demanda="Media", intervenciones=0):
        return base.ism3.inferir_sm3_crisp_cypher(
            self.driver, base.BASE_PRUEBAS, PRECIO, costo, VMA, intervenciones, riesgo, demanda)

    def _valuacion(self, procesador="i5 10ma gen", modelo="ThinkPad T14", ram=16, anio=2021):
        with self._en_la_transaccion():
            return base.oe.inferir_valuacion_sm2_cypher(
                procesador=procesador, modelo=modelo,
                texto=f"Lenovo ThinkPad T14 {procesador} {ram}GB RAM",
                ram_informada=ram, ram_ampliada=False, hdd_a_ssd=False,
                anio_informado=anio, soporte_w11_informado=True)

    def _traza(self, **pendientes):
        traza = base.oe.nueva_traza()
        traza["criterios_usados"]["margen_base"] = {
            "id": "CE-05", "valor": self._valor("margen_base"), "unidad": "%",
            "version": "v1", "estado": "Validado"}
        traza["costos_usados"]["mano_de_obra"] = {
            "id": "CO-08", "costo": 30000, "version": "v1", "estado": "Validado"}
        for clave, valor in pendientes.items():
            traza[clave].extend(valor)
        return traza

    def _clasificar(self, traza):
        with self._en_la_transaccion():
            return base.oe._estado_decision(traza)


class MargenRequeridoTest(BloqueEnGrafoTest):
    """El margen y su cuantización se resuelven con los datos de la etapa SM3."""

    def test_politica_por_defecto_conserva_el_margen_base(self):
        fila = self._margen()
        self.assertEqual(self._valor("margen_base"), fila["margen_req"])
        self.assertEqual([], fila["reglas_activadas"])
        self.assertEqual(["ratio_reparacion_max", "margen_base", "umbral_intervenciones"],
                         [c["nombre"] for c in fila["criterios"]])

    def test_r34_asigna_la_alta_liquidez_y_ordena_la_traza(self):
        fila = self._margen(riesgo="Bajo", demanda="Alta")
        self.assertEqual(self._valor("margen_alta_liquidez"), fila["margen_req"])
        self.assertEqual(["R3.4: demanda Alta y riesgo Bajo → margen requerido = "
                          "CE margen_alta_liquidez"], fila["reglas_activadas"])
        self.assertEqual(["ratio_reparacion_max", "margen_base", "margen_alta_liquidez",
                          "umbral_intervenciones"],
                         [c["nombre"] for c in fila["criterios"]])

    def test_r35_toma_el_maximo_entre_el_margen_base_y_el_de_riesgo_alto(self):
        fila = self._margen(riesgo="Alto")
        esperado = max(self._valor("margen_base"), self._valor("margen_riesgo_alto"))
        self.assertEqual(esperado, fila["margen_req"])
        self.tx.run("MATCH (ce:CriterioExperto {nombre:'margen_riesgo_alto'}) "
                    "SET ce.valor = $valor", valor=self._valor("margen_base") + 5.0).consume()
        self.assertEqual(self._valor("margen_base") + 5.0,
                         self._margen(riesgo="Alto")["margen_req"])

    def test_r36_suma_la_prima_cuando_el_umbral_del_grafo_se_alcanza(self):
        umbral = self._valor("umbral_intervenciones")
        fila = self._margen(riesgo="Alto", intervenciones=int(umbral) + 1)
        esperado = (max(self._valor("margen_base"), self._valor("margen_riesgo_alto"))
                    + self._valor("prima_fallas"))
        self.assertEqual(esperado, fila["margen_req"])
        self.assertEqual(
            ["R3.5: riesgo Alto → margen requerido = máx(margen, CE margen_riesgo_alto)",
             "R3.6: intervenciones ≥ CE umbral_intervenciones → + CE prima_fallas"],
            fila["reglas_activadas"])
        self.assertEqual(self._margen(intervenciones=int(umbral) - 1)["margen_req"],
                         self._valor("margen_base"))

    def test_la_operacion_declarada_por_la_regla_decide_la_combinacion(self):
        umbral = self._valor("umbral_intervenciones")
        self.tx.run("MATCH (r:Regla {id:'R3.6'}) SET r.efecto_operacion = 'asignar'").consume()
        fila = self._margen(riesgo="Alto", intervenciones=int(umbral) + 1)
        self.assertEqual(self._valor("prima_fallas"), fila["margen_req"])

    def test_la_exclusion_entre_r34_y_r35_es_configuracion_invalida(self):
        self.tx.run("MATCH (c:Condicion {id:'CND-SM3-R35-RIESGO'}) SET c.valor = 'Bajo'").consume()
        self.assertIsNone(self._margen(riesgo="Bajo", demanda="Alta"))
        with self._en_la_transaccion():
            with self.assertRaises(RuntimeError):
                base.oe.ejecutar_motor_sm3(PRECIO, 0, VMA, 0, "Bajo", "Alta",
                                           base.oe.nueva_traza())

    def test_la_precision_de_cada_cuantizacion_es_un_dato_del_grafo(self):
        fila = base.ism3.inferir_sm3_crisp_cypher(
            self.driver, base.BASE_PRUEBAS, 333333, 0, VMA, 0, "Medio", "Media")
        self.assertEqual(66.7, fila["margen_neto"])
        self.tx.run("MATCH (pc:PasoCalculo {id:'PC-SM3-MARGEN-NETO'}) "
                    "SET pc.decimales = 2").consume()
        fila = base.ism3.inferir_sm3_crisp_cypher(
            self.driver, base.BASE_PRUEBAS, 333333, 0, VMA, 0, "Medio", "Media")
        self.assertEqual(66.67, fila["margen_neto"])

    def test_el_limite_no_negativo_de_la_contraoferta_es_un_dato(self):
        contraoferta = self._margen()["contraoferta"]
        self.assertGreater(contraoferta, 0.0)
        self.tx.run("MATCH (pc:PasoCalculo {id:'PC-SM3-CONTRATOFERTA'}) "
                    "SET pc.limite_inferior_ars = $limite",
                    limite=contraoferta + 100000.0).consume()
        self.assertEqual(contraoferta + 100000.0, self._margen()["contraoferta"])

    def test_r37_conserva_la_precedencia_sobre_el_margen(self):
        fila = self._margen(costo=int(VMA * (self._valor("ratio_reparacion_max") + 0.1)),
                            riesgo="Alto")
        self.assertEqual(("R3.7", "DescartarPorRiesgo"), (fila["regla"], fila["decision"]))
        self.assertIsNone(fila["margen_req"])
        self.assertEqual(["R3.7: costo / VMA > CE ratio_reparacion_max → DescartarPorRiesgo"],
                         fila["reglas_activadas"])


