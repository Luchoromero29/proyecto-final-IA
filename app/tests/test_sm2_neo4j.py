#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Valuación SM2 resuelta en Neo4j — pruebas contra un grafo real (S4, S9).

Estas pruebas comprueban que la valuación comercial de SM2 (procesador, línea, RAM
tasada, año, soporte de Windows 11, antigüedad, estado de la tasación y aplicación de
R2.4) la decide una consulta Cypher explícita, y que Python solo transporta hechos,
valida tipos y formatea. Los hechos son controlados; los valores esperados están
congelados a partir de la política vigente y del catálogo cargado, no de la salida.

Necesitan un grafo aislado y descartable (nunca el de trabajo):

    EVALTIC_NEO4J_PRUEBAS_URI=bolt://127.0.0.1:17687 \\
        python -m unittest discover -s app/tests -p test_sm2_neo4j.py -v

Sin esa variable las pruebas de grafo se omiten y solo corren las de contrato.
El grafo se usa en modo lectura; ninguna prueba escribe ni borra conocimiento.
"""

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

# Aislamiento previo a la importación del motor: sin red y sin leer el .env real.
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

URI_PRUEBAS = os.environ.get("EVALTIC_NEO4J_PRUEBAS_URI", "").strip()
MARCADOR = "mejoras-evaltic"
# Sin escrituras: el grafo de pruebas es compartido y debe quedar intacto.
SIN_ESCRITURAS = re.compile(r"\b(CREATE|MERGE|SET|DELETE|DETACH|REMOVE|DROP|LOAD\s+CSV)\b",
                            re.IGNORECASE)

_DRIVER = None
_PARCHE = None


class _RequerirGrafo:
    """Mixin: omite las pruebas de grafo cuando no hay URI aislado configurado."""

    @classmethod
    def setUpClass(cls):
        if _DRIVER is None:
            raise unittest.SkipTest("falta EVALTIC_NEO4J_PRUEBAS_URI: sin grafo aislado no hay prueba")


def setUpModule():
    global _DRIVER, _PARCHE
    if not URI_PRUEBAS:
        return
    import neo4j
    _DRIVER = neo4j.GraphDatabase.driver(URI_PRUEBAS, auth=None)
    _DRIVER.verify_connectivity()
    with _DRIVER.session(database=oe.NEO4J_DATABASE) as s:
        presentes = s.run("MATCH (e:EntornoPruebas {id: $id}) RETURN count(e) AS n",
                          id=MARCADOR).single()["n"]
    if not presentes:
        _DRIVER.close()
        _DRIVER = None
        raise unittest.SkipTest(f"el grafo en {URI_PRUEBAS} no tiene el marcador :EntornoPruebas {{{MARCADOR}}}")
    oe._CONOCIMIENTO = None
    _PARCHE = mock.patch.object(oe, "obtener_driver_neo4j", return_value=_DRIVER)
    _PARCHE.start()


def tearDownModule():
    global _DRIVER, _PARCHE
    if _PARCHE is not None:
        _PARCHE.stop()
        _PARCHE = None
    oe._CONOCIMIENTO = None
    if _DRIVER is not None:
        _DRIVER.close()
        _DRIVER = None


class CuantizacionRiesgoTest(_RequerirGrafo, unittest.TestCase):
    """El riesgo que alimenta demanda ya debe venir cuantizado desde Neo4j."""

    def test_no_redondea_en_python_antes_de_inferir_demanda(self):
        with mock.patch.object(oe, "round", create=True,
                               side_effect=AssertionError("cuantización fuera del grafo")):
            resultado = oe.inferir_sm2_rie_cypher(5, 6, True)
        self.assertEqual((0.25, "Bajo"), resultado)

    def test_conserva_el_riesgo_previo_y_la_categoria_del_grafo(self):
        casos = [((0, 9, True), (0.15, "Bajo")), ((5, 6, True), (0.25, "Bajo")),
                 ((12, 4, False), (0.84, "Alto")), ((3, 12, True), (0.2, "Bajo"))]
        for entrada, esperado in casos:
            with self.subTest(entrada=entrada):
                self.assertEqual(esperado, oe.inferir_sm2_rie_cypher(*entrada))


class _Apoyo:
    """Hechos controlados y ejecución de los puntos públicos de SM2."""

    TEXTO = "Vendo Lenovo ThinkPad T14 i5 10ma gen, 16GB RAM, SSD, año 2021, Windows 11."

    def hechos(self, **cambios):
        datos = {"marca": "Lenovo", "modelo": "ThinkPad T14", "procesador": "i5 10ma gen",
                 "anio_fabricacion": 2021, "ram_gb": 16, "tipo_disco": "SSD",
                 "soporte_windows_11": True, "fallas": []}
        datos.update(cambios)
        return datos

    def valuar(self, **cambios):
        """Ejecuta la consulta de valuación con los hechos indicados y devuelve el resultado."""
        hechos = self.hechos(**cambios)
        modelo = str(hechos.get("modelo") or "")
        texto = " ".join(str(x) for x in (hechos.get("marca"), modelo, self.TEXTO) if x)
        return oe.inferir_valuacion_sm2_cypher(
            procesador=str(hechos.get("procesador") or ""), modelo=modelo, texto=texto,
            ram_informada=hechos.get("ram_gb"), ram_ampliada=bool(cambios.get("ram_ampliada")),
            hdd_a_ssd=bool(cambios.get("hdd_a_ssd")),
            anio_informado=hechos.get("anio_fabricacion"),
            soporte_w11_informado=hechos.get("soporte_windows_11"),
            traza=cambios.get("traza"))

    def valuar(self, **cambios):
        """Devuelve el mapa resuelto directamente por la consulta, con los hechos indicados."""
        hechos = self.hechos(**cambios)
        modelo = str(hechos.get("modelo") or "")
        texto = " ".join(str(x) for x in (hechos.get("marca"), modelo, self.TEXTO) if x)
        return oe.inferir_valuacion_sm2_cypher(
            procesador=str(hechos.get("procesador") or ""), modelo=modelo, texto=texto,
            ram_informada=hechos.get("ram_gb"), ram_ampliada=bool(cambios.get("ram_ampliada")),
            hdd_a_ssd=bool(cambios.get("hdd_a_ssd")),
            anio_informado=hechos.get("anio_fabricacion"),
            soporte_w11_informado=hechos.get("soporte_windows_11"),
            traza=cambios.get("traza"))

    def motor(self, datos, upgrades=None, texto=None):
        """Ejecuta el motor SM2 completo (punto público del pipeline) y devuelve (resultado, traza)."""
        traza = oe.nueva_traza()
        with redirect_stdout(StringIO()):
            res = oe.ejecutar_motor_sm2(datos, {"upgrades": upgrades or {}},
                                        self.TEXTO if texto is None else texto, traza)
        return res, traza


class ValuacionEnGrafoTest(_RequerirGrafo, _Apoyo, unittest.TestCase):
    """La política de valuación se resuelve en Cypher con hechos controlados."""

    def test_la_consulta_resuelve_la_politica_sin_pasar_por_el_motor(self):
        ref = self.valuar(ram_gb=None)
        self.assertEqual("Tasado", ref["estado"])
        self.assertEqual(8, ref["ram_final"])
        self.assertEqual("referencia", ref["ram_origen"])
        self.assertEqual("aviso", ref["anio_origen"])
        self.assertEqual("aviso", ref["w11_origen"])
        self.assertEqual(5.0, ref["antiguedad"])
        self.assertEqual(661000, ref["vma"])
        self.assertEqual({"ram_objetivo", "anio_referencia", "anio_min_w11",
                          "min_muestras_mercado", "descuento_negociacion", "reval_ssd"},
                         set(ref["criterios"]))

    def test_tasa_con_los_hechos_del_aviso_y_congela_los_valores(self):
        datos = self.hechos()
        res, traza = self.motor(datos)
        self.assertEqual("Tasado", res["estado"])
        self.assertEqual("Core i5 10ma gen", res["procesador"])
        self.assertEqual("ThinkPad", res["linea"])
        self.assertEqual("Corporativa", res["grupo_linea"])
        self.assertEqual(683000, res["valor_ref_procesador_ars"])
        self.assertIsNone(res["valor_desde_generacion_anterior"])
        self.assertEqual(12, res["muestras_procesador"])
        self.assertEqual(16, res["ram_tasada_gb"])
        self.assertEqual(1.08, res["factor_ram"])
        self.assertEqual(1.075, res["factor_linea"])
        self.assertEqual(793000, res["valor_mercado_ars"])
        self.assertEqual(714000, res["vma_estimado_ars"])
        self.assertEqual(5.0, res["antiguedad_anios"])
        self.assertEqual(10, res["descuento_negociacion_pct"])
        self.assertEqual(0, res["revalorizaciones_ars"])
        self.assertEqual("Bajo", res["riesgo_obsolescencia"])
        self.assertEqual("Alta", res["demanda_comercial"])
        self.assertEqual([], [r for r in traza["reglas"] if r.startswith("R2.4")])

    def test_r24_usa_la_generacion_anterior_sin_anio_en_el_aviso(self):
        datos = self.hechos(procesador="i5 13va gen", anio_fabricacion=None,
                            soporte_windows_11=None, ram_gb=8)
        res, traza = self.motor(datos)
        self.assertEqual("Tasado", res["estado"])
        self.assertEqual(4, res["muestras_procesador"])  # < CE min_muestras_mercado
        self.assertEqual(824000, res["valor_ref_procesador_ars"])
        self.assertEqual("Core i5 12va gen", res["valor_desde_generacion_anterior"])
        self.assertEqual(797000, res["vma_estimado_ars"])
        self.assertEqual(3.0, res["antiguedad_anios"])
        self.assertEqual("Bajo", res["riesgo_obsolescencia"])
        self.assertEqual("Alta", res["demanda_comercial"])
        self.assertIn("R2.4: Core i5 13va gen sin muestras suficientes → valor de la generación "
                      "anterior Core i5 12va gen ($824,000, 10 avisos)", traza["reglas"])
        self.assertIn("Valor de Core i5 13va gen tomado de Core i5 12va gen (generación anterior, "
                      "supuesto conservador R2.4)", traza["datos_inferidos"])
        self.assertIn("Año estimado por el procesador Core i5 13va gen (Neo4j): 2023",
                      traza["datos_inferidos"])

    def test_el_anio_invalido_corta_en_vez_de_inferirse(self):
        # Un año que no es número corta la valuación, igual que antes: reemplazarlo por el año
        # del procesador habilitaría una tasación favorable con un dato que el aviso no dice.
        for valor, error in (("veinte", ValueError), ([], TypeError), ({"anio": 2020}, TypeError)):
            with self.subTest(valor=valor):
                with self.assertRaises(error):
                    self.motor(self.hechos(anio_fabricacion=valor))

    def test_la_ram_que_int_no_acepta_se_considera_no_informada(self):
        # Misma validación que antes: el texto decimal no se interpreta como capacidad.
        for valor in ("ocho", "16.0", []):
            with self.subTest(valor=valor):
                res, traza = self.motor(self.hechos(ram_gb=valor))
                self.assertEqual("Tasado", res["estado"])
                self.assertEqual(8, res["ram_tasada_gb"])
                self.assertEqual(661000, res["vma_estimado_ars"])
                self.assertIn("RAM no informada", " ".join(traza["datos_inferidos"]))

    def test_un_booleano_de_ram_conserva_el_error_de_conocimiento(self):
        with self.assertRaises(oe.ConocimientoFaltante) as ctx:
            self.motor(self.hechos(ram_gb=True))
        self.assertEqual("La capacidad de RAM informada (1 GB) no está en la base de conocimiento "
                         "(Neo4j :CapacidadRAM).", str(ctx.exception))

    def test_el_anio_numerico_textual_o_decimal_se_transporta_como_numero(self):
        for valor, esperado in (("2016", 10.0), ("2016.5", 9.5), (2016.5, 9.5)):
            with self.subTest(valor=valor):
                datos = self.hechos(anio_fabricacion=valor, soporte_windows_11=None)
                res, traza = self.motor(datos)
                self.assertEqual("Tasado", res["estado"])
                self.assertEqual(esperado, res["antiguedad_anios"])
                self.assertIn("Soporte de Windows 11 según el procesador",
                              " ".join(traza["datos_inferidos"]))

    def test_la_traza_registra_solo_los_criterios_que_la_consulta_aplico(self):
        casos = (
            (self.hechos(), "aviso completo",
             {"ram_objetivo", "min_muestras_mercado", "anio_referencia", "descuento_negociacion"}),
            (self.hechos(tipo_disco="HDD"), "con upgrade a SSD", None),
        )
        for datos, etiqueta, esperado in casos:
            with self.subTest(caso=etiqueta):
                upgrades = {"ssd": True} if esperado is None else {}
                _, traza = self.motor(datos, upgrades=upgrades)
                usados = set(traza["criterios_usados"])
                if esperado is not None:
                    self.assertEqual(esperado, usados)
                else:
                    self.assertEqual({"ram_objetivo", "min_muestras_mercado", "anio_referencia",
                                      "descuento_negociacion", "reval_ssd"}, usados)

    def test_el_criterio_de_w11_por_anio_se_registra_solo_cuando_aplica(self):
        datos = self.hechos(procesador="i5", modelo="15", marca="HP", anio_fabricacion=2016,
                            soporte_windows_11=None, ram_gb=8)
        _, traza = self.motor(datos, texto="HP 15 año 2016 i5, 8GB RAM, SSD.")
        self.assertIn("anio_min_w11", traza["criterios_usados"])
        _, por_procesador = self.motor(self.hechos())
        self.assertNotIn("anio_min_w11", por_procesador["criterios_usados"])

    def test_sin_generacion_anterior_con_datos_queda_pendiente(self):
        datos = self.hechos(procesador="Athlon Silver", modelo="ThinkPad", ram_gb=8)
        res, traza = self.motor(datos)
        self.assertEqual("Verificacion_pendiente", res["estado"])
        self.assertEqual(0, res["vma_estimado_ars"])
        self.assertEqual("Precio de mercado para Athlon Silver (hay 1 avisos relevados; "
                         "se necesitan 5)", res["dato_faltante"])
        self.assertIn("R3.3b: Athlon Silver con 1 avisos relevados (< CE min_muestras_mercado) "
                      "y sin generación anterior con datos → Verificacion_pendiente", traza["reglas"])
        self.assertNotIn("riesgo_obsolescencia", res)

    def test_anio_desconocido_queda_pendiente_y_no_se_inventa(self):
        datos = self.hechos(procesador="i5", modelo="15", marca="HP", anio_fabricacion=None,
                            soporte_windows_11=None, ram_gb=8)
        res, traza = self.motor(datos)
        self.assertEqual("Verificacion_pendiente", res["estado"])
        self.assertEqual(0, res["vma_estimado_ars"])
        self.assertEqual("Año de fabricación del equipo", res["dato_faltante"])
        self.assertIn("R3.3b: año de fabricación desconocido → Verificacion_pendiente", traza["reglas"])

    def test_procesador_ausente_queda_pendiente_sin_consultar_el_catalogo(self):
        datos = self.hechos(procesador=None, modelo=None, marca="Acer")
        res, traza = self.motor(datos)
        self.assertEqual("Verificacion_pendiente", res["estado"])
        self.assertEqual("Procesador del equipo (no figura en el aviso)", res["dato_faltante"])
        self.assertIn("R3.3b: procesador no informado → Verificacion_pendiente", traza["reglas"])
        self.assertIsNone(traza["referencia_mercado"])

    def test_procesador_deducido_del_modelo_se_registra_como_inferido(self):
        datos = self.hechos(procesador=None, modelo="MacBook Air M1", marca="Apple", ram_gb=8,
                            anio_fabricacion=None, soporte_windows_11=None)
        res, traza = self.motor(datos)
        self.assertEqual("Verificacion_pendiente", res["estado"])
        self.assertIn("Procesador tomado del modelo 'MacBook Air M1': Apple M1",
                      traza["datos_inferidos"])
        self.assertEqual("Apple M1", traza["referencia_mercado"]["procesador"]["nombre"])
        self.assertEqual(0, res["vma_estimado_ars"])

    def test_procesador_fuera_del_catalogo_da_error_de_conocimiento(self):
        datos = self.hechos(procesador="xyz 9999")
        with self.assertRaises(oe.ConocimientoFaltante) as ctx:
            self.motor(datos)
        self.assertEqual("El procesador 'xyz 9999' no está en la base de conocimiento "
                         "(Neo4j :Procesador).", str(ctx.exception))

    def test_linea_fuera_del_catalogo_da_error_de_conocimiento(self):
        datos = self.hechos(marca="Zzz", modelo="Book")
        with self.assertRaises(oe.ConocimientoFaltante) as ctx:
            self.motor(datos, texto="Notebook Zzz Book i5 10ma gen, 16GB RAM, SSD, año 2021.")
        self.assertEqual("La marca o línea del equipo ('Zzz Book') no está en la base de "
                         "conocimiento (Neo4j :Linea).", str(ctx.exception))

    def test_ram_informada_fuera_del_catalogo_da_error_de_conocimiento(self):
        datos = self.hechos(ram_gb=10)
        with self.assertRaises(oe.ConocimientoFaltante) as ctx:
            self.motor(datos)
        self.assertEqual("La capacidad de RAM informada (10 GB) no está en la base de conocimiento "
                         "(Neo4j :CapacidadRAM).", str(ctx.exception))

    def test_ram_no_informada_usa_el_criterio_ram_objetivo(self):
        datos = self.hechos(ram_gb=None)
        res, traza = self.motor(datos)
        self.assertEqual("Tasado", res["estado"])
        self.assertEqual(8, res["ram_tasada_gb"])
        self.assertEqual(1.0, res["factor_ram"])
        self.assertEqual(661000, res["vma_estimado_ars"])
        self.assertIn("RAM no informada: se tasa con la configuración de referencia (8 GB, "
                      "CE ram_objetivo)", traza["datos_inferidos"])

    def test_la_ampliacion_de_sm1_fija_la_ram_tasada(self):
        datos = self.hechos(ram_gb=4, tipo_disco="HDD")
        res, traza = self.motor(datos, upgrades={"ram": True, "ssd": True})
        self.assertEqual(8, res["ram_tasada_gb"])
        self.assertEqual(1.0, res["factor_ram"])
        self.assertEqual(706000, res["vma_estimado_ars"])
        self.assertEqual(45000, res["revalorizaciones_ars"])
        self.assertIn("R2.3: revalorización por upgrade a SSD (CE reval_ssd)", traza["reglas"])

    def test_sin_ampliacion_se_tasa_la_ram_del_aviso(self):
        datos = self.hechos(ram_gb=4, tipo_disco="SSD")
        res, _ = self.motor(datos)
        self.assertEqual(4, res["ram_tasada_gb"])
        self.assertEqual(0.9, res["factor_ram"])
        self.assertEqual(595000, res["vma_estimado_ars"])

    def test_w11_se_resuelve_contra_el_criterio_anio_min_w11(self):
        datos = self.hechos(procesador="i5", modelo="15", marca="HP", anio_fabricacion=2016,
                            soporte_windows_11=None, ram_gb=8)
        res, traza = self.motor(datos, texto="HP 15 año 2016 i5, 8GB RAM, SSD.")
        self.assertEqual("Tasado", res["estado"])
        self.assertEqual(591000, res["vma_estimado_ars"])
        self.assertEqual(10.0, res["antiguedad_anios"])
        self.assertEqual("Alto", res["riesgo_obsolescencia"])
        self.assertEqual("Baja", res["demanda_comercial"])
        self.assertIn("Soporte de Windows 11 inferido por el año (2016): False",
                      traza["datos_inferidos"])


class ContratoConsultaTest(_RequerirGrafo, _Apoyo, unittest.TestCase):
    """La consulta pública de componentes conserva su contrato y no escribe en el grafo."""

    CAMPOS = {"procesador", "generacion_anterior", "valor_proc", "linea", "grupo",
              "ram_informada_existe", "ram", "valor_mercado", "vma"}

    def test_la_consulta_de_componentes_devuelve_las_mismas_claves_y_valores(self):
        ref = oe.consultar_mercado_componentes("i5 10ma gen", "Lenovo ThinkPad T14", 8, 16, False)
        self.assertEqual(self.CAMPOS, set(ref))
        self.assertEqual("Core i5 10ma gen", ref["procesador"]["nombre"])
        self.assertEqual("ThinkPad", ref["linea"]["nombre"])
        self.assertEqual(16, ref["ram"]["gb"])
        self.assertEqual(792963.0, ref["valor_mercado"])
        self.assertEqual(714000, ref["vma"])

    def test_la_ram_final_explicita_manda_sobre_la_politica(self):
        con_16 = oe.consultar_mercado_componentes("i5 10ma gen", "Lenovo ThinkPad T14", 8, 16, False)
        con_8 = oe.consultar_mercado_componentes("i5 10ma gen", "Lenovo ThinkPad T14", 8, 8, False)
        self.assertEqual(792963.0, con_16["valor_mercado"])
        self.assertEqual(714000, con_16["vma"])
        self.assertEqual(734225.0, con_8["valor_mercado"])
        self.assertEqual(661000, con_8["vma"])
        self.assertTrue(con_8["ram_informada_existe"])

    def test_una_ram_final_sin_factor_no_inventa_mercado(self):
        ref = oe.consultar_mercado_componentes("i5 13va gen", "Acer Aspire 5", None, None, False)
        self.assertEqual("Core i5 12va gen", ref["generacion_anterior"]["nombre"])
        self.assertIsNone(ref["ram"])
        self.assertIsNone(ref["valor_mercado"])
        self.assertIsNone(ref["vma"])
        self.assertFalse(ref["ram_informada_existe"])

    def test_la_consulta_de_valuacion_no_escribe_en_el_grafo(self):
        self.assertIsNone(SIN_ESCRITURAS.search(oe._CONSULTA_VALUACION_SM2))
        with _DRIVER.session(database=oe.NEO4J_DATABASE) as s:
            self.assertEqual(1, s.run("MATCH (e:EntornoPruebas {id: $id}) RETURN count(e) AS n",
                                      id=MARCADOR).single()["n"])


class EstadoValidacionTest(_RequerirGrafo, _Apoyo, unittest.TestCase):
    """Metadatos de validación mezclados (mock): el estado Firme/Provisional sigue siendo verdadero."""

    TODOS = ("ram_objetivo", "anio_referencia", "anio_min_w11", "min_muestras_mercado",
             "descuento_negociacion", "reval_ssd")

    def conocimiento(self, estados):
        """Metadatos del grafo real con los estados pedidos; no se escribe en el grafo."""
        real = self.real
        criterios = {nombre: dict(meta) for nombre, meta in real["criterios"].items()}
        for nombre in self.TODOS:
            criterios[nombre]["estado"] = estados.get(nombre, "Validado")
        return {"criterios": criterios, "costos": real["costos"]}

    def evaluar(self, datos, estados, upgrades=None, texto=None):
        self.real = oe.cargar_conocimiento()
        with mock.patch.object(oe, "cargar_conocimiento",
                               lambda forzar=False: self.conocimiento(estados)):
            res, traza = self.motor(datos, upgrades=upgrades, texto=texto)
        return res, traza, oe._estado_decision(traza)

    def test_un_criterio_no_aplicado_no_vuelve_provisional_la_decision(self):
        # W11 viene del aviso y no hay upgrade: la política no evalúa esos dos criterios.
        res, traza, estado = self.evaluar(
            self.hechos(), {"anio_min_w11": "Provisional", "reval_ssd": "Provisional"})
        self.assertEqual("Tasado", res["estado"])
        self.assertNotIn("anio_min_w11", traza["criterios_usados"])
        self.assertNotIn("reval_ssd", traza["criterios_usados"])
        self.assertEqual("Firme", estado["estado_decision"])
        self.assertEqual([], estado["criterios_pendientes"])

    def test_un_criterio_aplicado_sin_validar_deja_la_decision_provisional(self):
        _, traza, estado = self.evaluar(self.hechos(), {"min_muestras_mercado": "Provisional"})
        self.assertIn("min_muestras_mercado", traza["criterios_usados"])
        self.assertEqual("Provisional", estado["estado_decision"])
        self.assertEqual(1, len(estado["criterios_pendientes"]))
        self.assertIn("min_muestras_mercado", estado["criterios_pendientes"][0])

    def test_la_revalorizacion_sin_validar_cuenta_solo_con_upgrade_a_ssd(self):
        datos = self.hechos(tipo_disco="HDD")
        sin_ssd = self.evaluar(datos, {"reval_ssd": "Provisional"}, upgrades={"ssd": False})[2]
        con_ssd = self.evaluar(datos, {"reval_ssd": "Provisional"}, upgrades={"ssd": True})[2]
        self.assertEqual("Firme", sin_ssd["estado_decision"])
        self.assertEqual("Provisional", con_ssd["estado_decision"])
        self.assertIn("reval_ssd", con_ssd["criterios_pendientes"][0])

    def test_el_criterio_del_anio_sin_validar_cuenta_solo_cuando_resuelve_w11(self):
        datos = self.hechos(procesador="i5", modelo="15", marca="HP", anio_fabricacion=2016,
                            soporte_windows_11=None, ram_gb=8)
        texto = "HP 15 año 2016 i5, 8GB RAM, SSD."
        estado = self.evaluar(datos, {"anio_min_w11": "Provisional"}, texto=texto)[2]
        self.assertEqual("Provisional", estado["estado_decision"])
        self.assertIn("anio_min_w11", estado["criterios_pendientes"][0])


class FronteraDecisionTest(_Apoyo, unittest.TestCase):
    """El motor no decide: transporta y formatea la clasificación que devuelve el grafo."""

    def valuacion_falsa(self, **cambios):
        valuacion = {
            "estado": "Tasado", "motivo_clave": None,
            "procesador": {"nombre": "Procesador de prueba", "familia": "Prueba", "gama": "media",
                           "anio": 2019, "soporte_w11": False, "valor_ref_ars": 111000,
                           "n_muestras": 7, "fuente_valor": "fixture", "estado_validacion": "Provisional"},
            "procesador_origen": "aviso",
            "generacion_anterior": None, "valor_origen": "propio", "valor_proc": 111000,
            "linea": {"nombre": "Línea de prueba", "marca": "Marca", "factor_precio": 1.5,
                      "origen_factor": "fixture", "estado_validacion": "Provisional"},
            "grupo": {"nombre": "Grupo de prueba", "dias_promedio_venta": 45, "indice_repuestos": 3},
            "ram_informada_existe": True, "ram": {"gb": 12, "factor": 1.04},
            "ram_final": 12, "ram_origen": "aviso",
            "anio": 2019, "anio_origen": "aviso", "soporte_w11": False, "w11_origen": "aviso",
            "antiguedad": 7.0, "valor_mercado": 173160.0, "vma": 999000,
            "revalorizacion_ssd": 0,
            "criterios": {"ram_objetivo": 8.0, "anio_referencia": 2026.0, "anio_min_w11": 2018.0,
                          "min_muestras_mercado": 5.0, "descuento_negociacion": 10.0,
                          "reval_ssd": 45000.0},
        }
        valuacion.update(cambios)
        return valuacion

    def test_los_numeros_del_motor_son_los_que_resolvio_el_grafo(self):
        datos = self.hechos()
        with mock.patch.object(oe, "inferir_valuacion_sm2_cypher",
                               return_value=self.valuacion_falsa()) as consulta, \
                mock.patch.object(oe, "inferir_sm2_rie_cypher", return_value=(0.42, "Medio")) as rie, \
                mock.patch.object(oe, "inferir_sm2_dem_cypher", return_value=(0.13, "Baja")):
            res, traza = self.motor(datos)
        self.assertEqual(1, consulta.call_count)
        self.assertEqual("Tasado", res["estado"])
        self.assertEqual(12, res["ram_tasada_gb"])
        self.assertEqual(1.04, res["factor_ram"])
        self.assertEqual(111000, res["valor_ref_procesador_ars"])
        self.assertEqual(173000, res["valor_mercado_ars"])
        self.assertEqual(999000, res["vma_estimado_ars"])
        self.assertEqual(7.0, res["antiguedad_anios"])
        self.assertEqual("Medio", res["riesgo_obsolescencia"])
        self.assertEqual("Baja", res["demanda_comercial"])
        # La difusa recibe la antigüedad del grafo (7), no un cálculo propio a partir del aviso.
        self.assertEqual((7.0, 3.0, False), rie.call_args[0])
        self.assertIn("RAM 12 GB (1.04)", " ".join(traza["reglas"]))

    def test_una_valuacion_pendiente_del_grafo_no_se_compensa_en_python(self):
        datos = self.hechos()
        pendiente = self.valuacion_falsa(estado="Verificacion_pendiente",
                                         motivo_clave="procesador_sin_muestras")
        with mock.patch.object(oe, "inferir_valuacion_sm2_cypher", return_value=pendiente), \
                mock.patch.object(oe, "inferir_sm2_rie_cypher") as rie:
            res, traza = self.motor(datos)
        self.assertEqual(0, rie.call_count)
        self.assertEqual("Verificacion_pendiente", res["estado"])
        self.assertEqual(0, res["vma_estimado_ars"])
        self.assertEqual("Precio de mercado para Procesador de prueba (hay 7 avisos relevados; "
                         "se necesitan 5)", res["dato_faltante"])
        self.assertNotIn("riesgo_obsolescencia", res)

    def test_el_conocimiento_faltante_del_grafo_corta_sin_tasar(self):
        datos = self.hechos()
        faltante = self.valuacion_falsa(estado="ConocimientoFaltante",
                                        motivo_clave="ram_tasada_desconocida", ram_final=99)
        with mock.patch.object(oe, "inferir_valuacion_sm2_cypher", return_value=faltante), \
                mock.patch.object(oe, "inferir_sm2_rie_cypher") as rie:
            with self.assertRaises(oe.ConocimientoFaltante) as ctx:
                self.motor(datos)
        self.assertEqual(0, rie.call_count)
        self.assertEqual("La capacidad de RAM 99 GB no está en la base de conocimiento "
                         "(Neo4j :CapacidadRAM).", str(ctx.exception))

    def test_la_extraccion_no_puede_elegir_riesgo_demanda_ni_vma(self):
        datos = self.hechos(vma_estimado_ars=1, riesgo_obsolescencia="Bajo",
                            demanda_comercial="Alta", decision="Comprar")
        with mock.patch.object(oe, "inferir_valuacion_sm2_cypher",
                               return_value=self.valuacion_falsa()), \
                mock.patch.object(oe, "inferir_sm2_rie_cypher", return_value=(0.85, "Alto")), \
                mock.patch.object(oe, "inferir_sm2_dem_cypher", return_value=(0.2, "Media")):
            res, _ = self.motor(datos)
        self.assertEqual(999000, res["vma_estimado_ars"])
        self.assertEqual("Alto", res["riesgo_obsolescencia"])
        self.assertEqual("Media", res["demanda_comercial"])


class FlujoPublicoTest(_RequerirGrafo, _Apoyo, unittest.TestCase):
    """El flujo SM2 suelto sigue funcionando sobre la consulta nueva."""

    def test_consultar_sm2_tasa_el_equipo_con_el_grafo(self):
        extraccion = {"marca": "Lenovo", "modelo": "ThinkPad T14", "procesador": "i5 10ma gen",
                      "anio_fabricacion": 2021, "ram_gb": 16, "tipo_disco": "SSD",
                      "soporte_windows_11": True, "fallas": []}
        with mock.patch.object(oe, "_llm_json", return_value=extraccion), \
                mock.patch.object(oe, "_explicar", return_value="explicación de prueba"):
            r = oe.consultar_sm2("Vendo ThinkPad T14 i5 10ma gen año 2021 16GB SSD $350.000",
                                 verbose=False)
        self.assertEqual("Tasado", r["sm2_comercial"]["estado"])
        self.assertEqual(714000, r["sm2_comercial"]["vma_estimado_ars"])
        self.assertEqual("Core i5 10ma gen", r["sm2_comercial"]["procesador"])
        self.assertIn("anio_referencia", r["traza"]["criterios_usados"])


if __name__ == "__main__":
    unittest.main()
