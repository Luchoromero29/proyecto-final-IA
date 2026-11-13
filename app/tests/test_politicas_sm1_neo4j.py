#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P2a/P2c — Las condiciones de las acciones de SM1, el vínculo de las categorías difusas y el
estado resultante de las consecuencias de bloqueo viven en el grafo (Neo4j), no en el código.

Cada prueba cambia SÓLO datos de representación (comparador, operando, campo, ámbito,
grupo o categoría difusa) dentro de una transacción que se revierte siempre, y observa la
salida pública de SM1. Si el motor sigue decidiendo en Python o en un `CASE` por ID, el
cambio de datos no altera el plan y la prueba falla.

Reutiliza el aislamiento de `test_sm1_neo4j` (dotenv mockeado antes de importar, driver
explícito, grafo marcado `EntornoPruebas {id:'mejoras-evaltic'}`). No toca el grafo de
trabajo ni el original, no llama al LLM y no deja datos: todo se revierte.

    EVALTIC_NEO4J_PRUEBAS_URI=bolt://127.0.0.1:17687 \
        PYTHONDONTWRITEBYTECODE=1 /home/alvaro/Universidad/IA/Proyecto/.venv/bin/python \
        -m unittest discover -s app/tests -p test_politicas_sm1_neo4j.py -v
"""

import json
import unittest
from contextlib import contextmanager
from pathlib import Path

import test_sm1_neo4j as base

SEMILLA = Path(__file__).resolve().parents[2] / "cypher/Grupo_20_PG3_politicas_sm1_acciones.cypher"
SEMILLA_ESTADO = Path(__file__).resolve().parents[2] / "cypher/Grupo_20_PG3_politicas_sm1_estado.cypher"
PERFORADA = "Placa perforada."
NO_PRENDE = "La notebook no prende."
BASE_PRUEBAS = "neo4j"
CARGADOR = "Cargador compatible"
RAM = "Ampliación de RAM a 8 GB"
TERMICO = "Service térmico (pasta térmica y limpieza)"


class DriverTransaccion:
    """Las sesiones del consumidor público comparten la transacción que se revierte."""

    def __init__(self, tx):
        self.tx = tx

    @contextmanager
    def session(self, database=None):
        yield self.tx


class AccionesRepresentadasTest(base.BaseSm1Test):
    """Cambiar la representación en el grafo cambia el plan público, sin editar Python."""

    @classmethod
    def setUpClass(cls):
        # Opt-in explícito: si se pidió el grafo de pruebas, la falta del marcador es un
        # error, no una omisión silenciosa (el fixture base omitiría la clase).
        if base.URI_PRUEBAS:
            import neo4j
            control = neo4j.GraphDatabase.driver(base.URI_PRUEBAS, auth=None)
            try:
                with control.session(database=BASE_PRUEBAS) as sesion:
                    marcador = sesion.run("MATCH (m:EntornoPruebas {id:$id}) RETURN count(m) AS n",
                                          id=base.MARCADOR).single()["n"]
            finally:
                control.close()
            if marcador != 1:
                raise RuntimeError(
                    f"el Neo4j de {base.URI_PRUEBAS} no tiene el marcador "
                    f"(:EntornoPruebas {{id:'{base.MARCADOR}'}}): no se ejecuta sobre un grafo ajeno")
        super().setUpClass()

    def setUp(self):
        self.sesion = self.__class__.driver.session(database=BASE_PRUEBAS)
        self.addCleanup(self.sesion.close)
        self.tx = self.sesion.begin_transaction()
        self.addCleanup(self.tx.rollback)
        # Los datos de la etapa se cargan antes del consumidor, dentro de la transacción
        # que se revierte: la segunda aplicación de este artefacto no cambia nada.
        self.tx.run(SEMILLA_ESTADO.read_text(encoding="utf-8")).consume()
        self.driver = DriverTransaccion(self.tx)

    def _diagnostico(self, texto="", datos=None):
        return super()._diagnostico(texto, datos or {})

    def _tareas(self, resultado):
        return [t["tarea"] for t in resultado["sm1_tecnico"]["plan_reparacion"]]

    def _aplicar(self):
        return dict(self.tx.run(SEMILLA.read_text(encoding="utf-8")).single(strict=True))

    def _proyeccion(self):
        """Proyección canónica de todo el grafo de la transacción (nodos y relaciones)."""
        fila = self.tx.run(
            "CALL () { MATCH (n) RETURN collect({id: elementId(n), etiquetas: labels(n), "
            "propiedades: properties(n)}) AS nodos } "
            "CALL () { MATCH ()-[r]->() RETURN collect({id: elementId(r), tipo: type(r), "
            "propiedades: properties(r)}) AS relaciones } "
            "RETURN nodos, relaciones").single(strict=True)
        return json.dumps(fila.data(), ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), default=str)

    # -- Cambiar el comparador almacenado -------------------------------------
    def test_el_comparador_almacenado_decide_la_intervencion(self):
        datos = {"cargador_incluido": False}
        self.assertIn(CARGADOR, self._tareas(self._diagnostico("", datos)))
        self.tx.run("MATCH (c:Condicion {id:'CND-SM1-CARGADOR-ACCION'}) "
                    "SET c.operador = 'ausente' REMOVE c.valor").consume()
        self.assertNotIn(CARGADOR, self._tareas(self._diagnostico("", datos)))

    # -- Cambiar el operando: referencia a un criterio del grafo ---------------
    def test_el_operando_por_criterio_sale_del_grafo(self):
        datos = {"ram_gb": 8}
        self.assertNotIn(RAM, self._tareas(self._diagnostico("", datos)))
        self.tx.run("MATCH (c:Condicion {id:'CND-SM1-RAM-ACCION-RAM'})-[usado:USA_CRITERIO]->(:CriterioExperto) "
                    "MATCH (nuevo:CriterioExperto {id:'CE-01'}) "
                    "DELETE usado MERGE (c)-[:USA_CRITERIO]->(nuevo)").consume()
        resultado = self._diagnostico("", datos)
        self.assertIn(RAM, self._tareas(resultado))
        criterio = resultado["traza"]["criterios_usados"]["bateria_reemplazo"]
        self.assertEqual(("CE-01", 75), (criterio["id"], criterio["valor"]))

    # -- Cambiar el hecho y su ámbito -----------------------------------------
    def test_el_campo_de_la_condicion_manda(self):
        datos = {"cargador_incluido": False}
        self.assertIn(CARGADOR, self._tareas(self._diagnostico("", datos)))
        self.tx.run("MATCH (c:Condicion {id:'CND-SM1-CARGADOR-ACCION'}) "
                    "SET c.campo = 'pantalla_danada'").consume()
        self.assertNotIn(CARGADOR, self._tareas(self._diagnostico("", datos)))

    def test_el_ambito_de_la_condicion_manda(self):
        datos = {"cargador_incluido": False}
        self.assertIn(CARGADOR, self._tareas(self._diagnostico("", datos)))
        self.tx.run("MATCH (c:Condicion {id:'CND-SM1-CARGADOR-ACCION'}) "
                    "SET c.ambito = 'hechos'").consume()
        self.assertNotIn(CARGADOR, self._tareas(self._diagnostico("", datos)))

    # -- Agrupamiento: OR dentro del grupo y AND entre grupos -----------------
    def test_los_grupos_combinan_or_dentro_y_and_entre_grupos(self):
        datos = {"cargador_incluido": False, "pantalla_danada": False}
        self.assertIn(CARGADOR, self._tareas(self._diagnostico("", datos)))
        self.tx.run(
            "MATCH (r:Regla {id:'SM1-CARGADOR-ACCION'}), "
            "(vp:VersionPoliticas {id:'VP-SM1-ACCIONES'})-[incluye:INCLUYE]->(r) "
            "CREATE (r)-[:REQUIERE {grupo: 2}]->(:Condicion {id:'CND-PRUEBA-CARGADOR-PANTALLA', "
            "campo:'pantalla_danada', ambito:'campos', operador:'=', valor:true, "
            "representacion_version:'politicas-SM1-acciones-v1'}) "
            "SET incluye.condiciones = incluye.condiciones + 1").consume()
        # Grupo nuevo insatisfecho: la regla exige todos sus grupos (AND).
        self.assertNotIn(CARGADOR, self._tareas(self._diagnostico("", datos)))
        self.tx.run("MATCH (:Regla {id:'SM1-CARGADOR-ACCION'})-[requiere:REQUIERE]->"
                    "(:Condicion {id:'CND-PRUEBA-CARGADOR-PANTALLA'}) "
                    "SET requiere.grupo = 1").consume()
        # Mismo grupo: alcanza una condición (OR).
        self.assertIn(CARGADOR, self._tareas(self._diagnostico("", datos)))

    # -- Alcance de la guarda: una condición de otra etapa no interviene ------
    def test_una_condicion_de_otra_etapa_no_cambia_el_resultado_de_sm1(self):
        datos = {"cargador_incluido": False}
        antes = self._diagnostico("", datos)
        self.assertIn(CARGADOR, self._tareas(antes))
        self.tx.run("CREATE (:Condicion {id:'CND-PRUEBA-AJENA', "
                    "campo:'ratio_ingreso_venta', ambito:'hechos', operador:'<', valor:0.15, "
                    "representacion_version:'politicas-SM3-politicas-v1'})").consume()
        despues = self._diagnostico("", datos)
        self.assertEqual(antes["sm1_tecnico"], despues["sm1_tecnico"])

    # -- Vínculo de la categoría difusa con el hecho --------------------------
    def test_el_vinculo_de_la_categoria_difusa_es_dato(self):
        datos = {"temperatura_cpu_c": 70}
        self.assertIn(TERMICO, self._tareas(self._diagnostico("", datos)))
        self.tx.run("MATCH (:ReglaDifusa {base:'SM1-TER'})-[obliga:OBLIGA]->(:CostoReparacion) "
                    "SET obliga.campo = 'categoria_bat'").consume()
        self.assertNotIn(TERMICO, self._tareas(self._diagnostico("", datos)))

    # -- Migración aditiva: sin delta en la segunda aplicación ----------------
    def test_la_segunda_aplicacion_no_cambia_la_proyeccion(self):
        antes = self._proyeccion()
        respuesta = self._aplicar()
        self.assertTrue(respuesta["compatible"], respuesta["errores"])
        self.assertEqual(0, respuesta["cambios"])
        self.assertEqual([], respuesta["errores"])
        self.assertEqual(antes, self._proyeccion())

    def test_el_artefacto_rechaza_una_configuracion_previa_distinta(self):
        self.tx.run("MATCH (c:Condicion {id:'CND-SM1-DISCO-ACCION-DISCO'}) "
                    "SET c.campo = 'otro_campo'").consume()
        antes = self._proyeccion()
        respuesta = self._aplicar()
        self.assertFalse(respuesta["compatible"])
        self.assertEqual(0, respuesta["cambios"])
        self.assertTrue(respuesta["errores"])
        self.assertEqual(antes, self._proyeccion())

    # -- P2c: el estado resultante de las consecuencias de bloqueo es dato ---------
    def test_el_estado_resultante_del_inviable_lo_declara_la_regla(self):
        self.assertEqual("Inviable", self._diagnostico(PERFORADA, {})["sm1_tecnico"]["estado"])
        self.tx.run("MATCH (r:Regla {id:'R1.1'}) SET r.estado_resultante = 'VerificacionPendiente'").consume()
        self.assertEqual("VerificacionPendiente",
                         self._diagnostico(PERFORADA, {})["sm1_tecnico"]["estado"])

    def test_el_estado_resultante_del_pendiente_lo_declara_la_regla(self):
        self.assertEqual("VerificacionPendiente", self._diagnostico(NO_PRENDE, {})["sm1_tecnico"]["estado"])
        self.tx.run("MATCH (r:Regla {id:'R3.3c'}) SET r.estado_resultante = 'Inviable'").consume()
        self.assertEqual("Inviable", self._diagnostico(NO_PRENDE, {})["sm1_tecnico"]["estado"])

    def test_el_estado_resultante_ausente_falla_cerrado(self):
        self.tx.run("MATCH (r:Regla {id:'R1.1'}) REMOVE r.estado_resultante").consume()
        detalle = self._diagnostico(PERFORADA, {})["sm1_tecnico"]
        self.assertEqual("ErrorConocimiento", detalle.get("estado"))
        self.assertIn("no declara un estado resultante válido", detalle.get("error") or "")
        self.assertEqual([], detalle.get("plan_reparacion") or [])

    def test_el_estado_resultante_invalido_falla_cerrado(self):
        self.tx.run("MATCH (r:Regla {id:'R3.3c'}) SET r.estado_resultante = 'Aprobado'").consume()
        detalle = self._diagnostico(NO_PRENDE, {})["sm1_tecnico"]
        self.assertEqual("ErrorConocimiento", detalle.get("estado"))
        self.assertIn("no declara un estado resultante válido", detalle.get("error") or "")

    def test_el_estado_resultante_no_se_reescribe_en_la_segunda_aplicacion(self):
        def aplicar():
            return dict(self.tx.run(SEMILLA_ESTADO.read_text(encoding="utf-8")).single(strict=True))
        antes = self._proyeccion()
        respuesta = aplicar()
        self.assertEqual((0, []), (respuesta["actualizadas"], respuesta["errores"]))
        self.assertEqual(antes, self._proyeccion())
        self.tx.run("MATCH (r:Regla {id:'R1.1'}) SET r.estado_resultante = 'Viable'").consume()
        antes = self._proyeccion()
        respuesta = aplicar()
        self.assertEqual((0, True), (respuesta["actualizadas"], bool(respuesta["errores"])))
        self.assertEqual(antes, self._proyeccion())

    # -- Configuración inválida o incompleta: error explícito, nunca plan barato
    def _error_con(self, mutacion, fragmento):
        with self.subTest(fragmento=fragmento):
            sesion = self.__class__.driver.session(database=BASE_PRUEBAS)
            tx = sesion.begin_transaction()
            driver_previo = self.driver
            self.driver = DriverTransaccion(tx)
            try:
                tx.run(mutacion).consume()
                detalle = self._diagnostico("", {"cargador_incluido": False})["sm1_tecnico"]
                self.assertEqual("ErrorConocimiento", detalle.get("estado"))
                self.assertIn(fragmento, detalle.get("error") or "")
                self.assertEqual([], detalle.get("plan_reparacion") or [])
            finally:
                self.driver = driver_previo
                tx.rollback()
                sesion.close()

    def test_la_configuracion_invalida_no_produce_un_plan_favorable(self):
        self._error_con("MATCH (v:VersionPoliticas {id:'VP-SM1-ACCIONES'}) DETACH DELETE v",
                        "falta el manifiesto")
        self._error_con("CREATE (:VersionPoliticas {id:'VP-SM1-ACCIONES-DUPLICADO', "
                        "etapa:'SM1-acciones', activa:true})", "más de un manifiesto")
        self._error_con("MATCH (c:Condicion {id:'CND-SM1-DISCO-ACCION-DISCO'}) "
                        "SET c.operador = '~'", "operador no admitido")
        self._error_con("MATCH (:Condicion {id:'CND-SM1-RAM-ACCION-RAM'})-[usado:USA_CRITERIO]->() "
                        "DELETE usado", "no tiene criterio")
        self._error_con("MATCH (condicion:Condicion {id:'CND-SM1-RAM-ACCION-RAM'}), "
                        "(otro:CriterioExperto {id:'CE-01'}) "
                        "MERGE (condicion)-[:USA_CRITERIO]->(otro)",
                        "más de un criterio")
        self._error_con("MATCH (r:Regla {id:'SM1-TECLADO-ACCION'}) "
                        "CREATE (r)-[:REQUIERE {grupo: 1}]->(:Condicion {id:'CND-PRUEBA-SIN-DECLARAR', "
                        "campo:'teclado_danado', ambito:'campos', operador:'=', valor:true})",
                        "no coinciden con las declaradas")


if __name__ == "__main__":
    unittest.main()
