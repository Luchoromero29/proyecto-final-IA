#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SM3 inferido en Neo4j — pruebas contra un grafo real y aislado (S9).

La política crisp de la operación, el margen requerido, la contraoferta y el mapeo de la
categoría difusa a la decisión son consultas Cypher (`app/inferencia_sm3.py`). Estas
pruebas las ejecutan sobre un Neo4j de pruebas, **sólo lectura**, y comprueban que:

  - la decisión, los indicadores y la procedencia de los criterios vienen del grafo;
  - ninguna lectura del conocimiento en Python puede cambiar el resultado (eso es lo que
    fallaba cuando la política estaba escrita en Python);
  - el texto que redacta el LLM no puede reemplazar la decisión ni los campos del grafo.

Se omiten si no se define `EVALTIC_NEO4J_PRUEBAS_URI`, para que la suite offline siga
corriendo sin Neo4j. Ejecución:

    EVALTIC_NEO4J_PRUEBAS_URI=bolt://127.0.0.1:17687 \
        python -m unittest discover -s app/tests -p test_sm3_neo4j.py -v

El grafo de pruebas debe llevar el marcador `(:EntornoPruebas {id:'mejoras-evaltic'})`:
sin él la ejecución se aborta en lugar de tocar un grafo ajeno. Nunca se escribe en el
grafo y nunca se llama al LLM ni a un proveedor externo.
"""

import os
import sys
import json
import math
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

# Aislamiento previo a la importación: mismo patrón que test_publicaciones_criticas.py.
# El .env real no se lee y ninguna configuración privada entra en las pruebas.
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
    import orquestador_evaltic as oe  # noqa: E402

import inferencia_sm3 as ism3  # noqa: E402

URI_PRUEBAS = os.environ.get("EVALTIC_NEO4J_PRUEBAS_URI", "").strip()
BASE_PRUEBAS = os.environ.get("EVALTIC_NEO4J_PRUEBAS_DATABASE", "neo4j").strip() or "neo4j"
MARCADOR = "mejoras-evaltic"
CRITERIOS_SM3 = ("ratio_reparacion_max", "margen_base", "margen_alta_liquidez",
                 "margen_riesgo_alto", "umbral_intervenciones", "prima_fallas")

_driver = None
_parches = []


def setUpModule():
    """Abre el Neo4j de pruebas, exige el marcador del entorno y lo inyecta en el motor."""
    global _driver
    if not URI_PRUEBAS:
        raise unittest.SkipTest(
            "Defina EVALTIC_NEO4J_PRUEBAS_URI (por ejemplo bolt://127.0.0.1:17687) para "
            "correr las pruebas de SM3 contra un Neo4j aislado.")
    import neo4j
    _driver = neo4j.GraphDatabase.driver(URI_PRUEBAS, auth=None)
    with _driver.session(database=BASE_PRUEBAS) as sesion:
        marcador = sesion.run("MATCH (e:EntornoPruebas {id: $id}) RETURN e.id AS id",
                              id=MARCADOR).single()
    if not marcador:
        _driver.close()
        raise RuntimeError(
            f"El Neo4j de {URI_PRUEBAS} no tiene el marcador (:EntornoPruebas {{id:'{MARCADOR}'}}). "
            "Estas pruebas sólo se ejecutan sobre el grafo aislado de pruebas, nunca sobre el de trabajo.")
    for objetivo, atributo, valor in ((oe, "obtener_driver_neo4j", lambda: _driver),
                                      (oe, "NEO4J_DATABASE", BASE_PRUEBAS)):
        parche = mock.patch.object(objetivo, atributo, valor)
        parche.start()
        _parches.append(parche)
    oe._CONOCIMIENTO = None


def tearDownModule():
    """Cierra el driver y restaura la configuración del motor."""
    for parche in reversed(_parches):
        parche.stop()
    _parches.clear()
    if _driver is not None:
        _driver.close()


def _criterios():
    """Criterios expertos del grafo de pruebas, en sólo lectura, para calcular expectativas."""
    with _driver.session(database=BASE_PRUEBAS) as sesion:
        return {r["nombre"]: dict(r) for r in sesion.run(
            "MATCH (c:CriterioExperto) RETURN c.nombre AS nombre, c.valor AS valor, c.id AS id, "
            "c.unidad AS unidad, c.version AS version, c.estado_validacion AS estado")}


def _conocimiento_alterado():
    """Conocimiento con umbrales cambiados: sólo sirve para probar que SM3 ya no lo lee."""
    criterios = {nombre: {"id": f"CE-FALSO-{i}", "valor": valor, "unidad": "falso",
                          "version": "falso", "estado": "Validado"}
                 for i, (nombre, valor) in enumerate(
                     {"ratio_reparacion_max": 0.01, "margen_base": 1, "margen_alta_liquidez": 1,
                      "margen_riesgo_alto": 1, "umbral_intervenciones": 0, "prima_fallas": 0}.items())}
    return {"criterios": criterios, "costos": {}}


class EntornoPruebasTest(unittest.TestCase):
    """El grafo usado es el de pruebas y tiene el conocimiento que SM3 necesita."""

    def test_el_grafo_de_pruebas_esta_marcado_y_tiene_los_criterios_de_sm3(self):
        criterios = _criterios()
        faltan = [nombre for nombre in CRITERIOS_SM3 if nombre not in criterios]
        self.assertEqual([], faltan, "faltan criterios expertos de SM3 en el grafo de pruebas")


class PoliticaCrispTest(unittest.TestCase):
    """R3.7, R3.8, margen requerido, contraoferta y procedencia, resueltos por el grafo."""

    def setUp(self):
        self.criterios = _criterios()
        self.ratio_max = self.criterios["ratio_reparacion_max"]["valor"]
        self.margen_base = self.criterios["margen_base"]["valor"]
        self.umbral = self.criterios["umbral_intervenciones"]["valor"]
        self.prima = self.criterios["prima_fallas"]["valor"]

    def _ejecutar(self, precio, costo, vma, intervenciones, riesgo, demanda):
        traza = oe.nueva_traza()
        resultado = oe.ejecutar_motor_sm3(precio, costo, vma, intervenciones, riesgo, demanda, traza)
        return resultado, traza

    def test_r37_descarta_cuando_el_ratio_supera_el_criterio(self):
        vma = 661000
        costo = int(vma * (self.ratio_max + 0.1))  # ratio claramente por encima del criterio
        resultado, traza = self._ejecutar(300000, costo, vma, 0, "Medio", "Media")
        self.assertEqual("DescartarPorRiesgo", resultado["decision"])
        self.assertEqual("R3.7", resultado["regla_aplicada"])
        self.assertEqual(f"La reparación (${costo:,.0f}) supera el {self.ratio_max:.0%} del VMA (${vma:,.0f}).",
                         resultado["motivo"])
        self.assertEqual([f"R3.7: costo / VMA > CE ratio_reparacion_max → DescartarPorRiesgo"],
                         traza["reglas"])
        # El descarte temprano no calcula margen requerido ni contraoferta.
        self.assertEqual({"precio_publicado", "costo_reparacion", "vma_tasado",
                          "margen_neto_pct", "ratio_reparacion"}, set(resultado["indicadores"]))

    def test_r37_no_descarta_en_el_umbral_ni_con_la_centesima_redondeada(self):
        vma = 1000000
        en_el_umbral = int(vma * self.ratio_max)
        resultado, _ = self._ejecutar(400000, en_el_umbral, vma, 0, "Medio", "Media")
        self.assertNotEqual("R3.7", resultado.get("regla_aplicada"))
        # 0,4995 se redondea a 0,5: igual al criterio, no lo supera.
        resultado, _ = self._ejecutar(400000, 499500, vma, 0, "Medio", "Media")
        self.assertEqual(self.ratio_max, resultado["indicadores"]["ratio_reparacion"])
        self.assertNotEqual("R3.7", resultado.get("regla_aplicada"))

    def test_r38_descarta_con_riesgo_alto_y_demanda_baja(self):
        resultado, traza = self._ejecutar(300000, 0, 582000, 0, "Alto", "Baja")
        self.assertEqual("DescartarPorRiesgo", resultado["decision"])
        self.assertEqual("R3.8", resultado["regla_aplicada"])
        self.assertEqual(["R3.8: riesgo Alto y demanda Baja → DescartarPorRiesgo"], traza["reglas"])

    def test_r38_no_descarta_si_la_demanda_no_es_baja(self):
        for demanda in ("Media", "Alta"):
            with self.subTest(demanda=demanda):
                resultado, _ = self._ejecutar(300000, 0, 582000, 0, "Alto", demanda)
                self.assertNotEqual("R3.8", resultado.get("regla_aplicada"))

    def test_r34_usa_el_margen_de_alta_liquidez(self):
        resultado, traza = self._ejecutar(400000, 0, 661000, 0, "Bajo", "Alta")
        self.assertEqual(self.criterios["margen_alta_liquidez"]["valor"],
                         resultado["indicadores"]["margen_requerido_pct"])
        self.assertIn("R3.4: demanda Alta y riesgo Bajo → margen requerido = CE margen_alta_liquidez",
                      traza["reglas"])
        self.assertNotIn("margen_riesgo_alto", traza["criterios_usados"])

    def test_r35_usa_el_mayor_entre_base_y_riesgo_alto(self):
        resultado, traza = self._ejecutar(300000, 0, 582000, 0, "Alto", "Media")
        esperado = max(self.margen_base, self.criterios["margen_riesgo_alto"]["valor"])
        self.assertEqual(esperado, resultado["indicadores"]["margen_requerido_pct"])
        self.assertIn("R3.5: riesgo Alto → margen requerido = máx(margen, CE margen_riesgo_alto)",
                      traza["reglas"])
        # R3.4 y R3.5 son excluyentes: con riesgo Alto no se usa el margen de alta liquidez.
        self.assertNotIn("margen_alta_liquidez", traza["criterios_usados"])

    def test_r36_suma_la_prima_desde_el_umbral_de_intervenciones(self):
        en_el_umbral, traza_umbral = self._ejecutar(400000, 0, 661000, int(self.umbral), "Medio", "Media")
        self.assertEqual(float(self.margen_base + self.prima),
                         en_el_umbral["indicadores"]["margen_requerido_pct"])
        self.assertIn("R3.6: intervenciones ≥ CE umbral_intervenciones → + CE prima_fallas",
                      traza_umbral["reglas"])
        debajo, traza_debajo = self._ejecutar(400000, 0, 661000, int(self.umbral) - 1, "Medio", "Media")
        self.assertEqual(float(self.margen_base), debajo["indicadores"]["margen_requerido_pct"])
        self.assertNotIn("prima_fallas", traza_debajo["criterios_usados"])

    def test_los_empates_decimales_conservan_la_decision_de_la_politica_anterior(self):
        # 101.000 / 200.000 = 0,505: el redondeo decimal nativo daría 0,50 (no descarta) y el
        # redondeo de la política anterior da 0,51, que dispara R3.7.
        descarte, _ = self._ejecutar(1000, 101000, 200000, 0, "Bajo", "Media")
        self.assertEqual(0.51, descarte["indicadores"]["ratio_reparacion"])
        self.assertEqual("R3.7", descarte["regla_aplicada"])
        # 100 · (200.000 − 186.900) / 200.000 = 6,55 %: la política anterior redondea 6,5 y el
        # redondeo decimal nativo daría 6,6.
        margen, _ = self._ejecutar(186900, 0, 200000, 0, "Medio", "Media")
        self.assertEqual(6.5, margen["indicadores"]["margen_neto_pct"])

    def test_la_cuantizacion_redondea_negativos_y_ceros_con_su_signo(self):
        # -0,0049999 redondea a -0,0 y -499 a -0,0: el signo del cero es parte del contrato.
        resultado, _ = self._ejecutar(1000, 0, 200000, 0, "Medio", "Media")
        self.assertEqual(0.0, resultado["indicadores"]["ratio_reparacion"])
        self.assertEqual(1.0, math.copysign(1.0, resultado["indicadores"]["ratio_reparacion"]))

    def test_contraoferta_redondea_a_miles_con_medio_al_par(self):
        # 1.000.000 − 499.500 − 20 % = 300.500 → empate exacto: 300.000 (no 301.000).
        resultado, _ = self._ejecutar(500000, 499500, 1000000, 0, "Medio", "Media")
        contraoferta = resultado["indicadores"]["contraoferta_sugerida_ars"]
        self.assertEqual(300000, contraoferta)
        self.assertEqual(0, contraoferta % 1000)

    def test_la_difusa_recibe_la_brecha_y_el_descuento_del_grafo(self):
        observado = {}

        def envoltura(brecha, descuento):
            observado["brecha"], observado["descuento"] = brecha, descuento
            return 0.5, "Negociar"

        with mock.patch.object(oe, "inferir_sm3_conv_cypher", side_effect=envoltura):
            resultado, traza = self._ejecutar(500000, 499500, 1000000, 0, "Medio", "Media")
        self.assertEqual((-19.9, 40.0), (observado["brecha"], observado["descuento"]))
        self.assertEqual("ComprarConOfertaMenor", resultado["decision"])
        self.assertIn("SM3-CONV difusa (brecha -19.9 pp, descuento 40.0 %) → Negociar (0.5)", traza["reglas"])

    def test_criterios_usados_conservan_la_procedencia_y_el_orden_del_grafo(self):
        _, traza = self._ejecutar(400000, 0, 661000, int(self.umbral), "Medio", "Media")
        self.assertEqual(["ratio_reparacion_max", "margen_base", "umbral_intervenciones", "prima_fallas"],
                         list(traza["criterios_usados"]))
        for nombre, usado in traza["criterios_usados"].items():
            with self.subTest(criterio=nombre):
                esperado = self.criterios[nombre]
                self.assertEqual({"id": esperado["id"], "valor": esperado["valor"],
                                  "unidad": esperado["unidad"], "version": esperado["version"],
                                  "estado": esperado["estado"]}, usado)

    def test_la_rama_de_descarte_solo_declara_el_criterio_que_uso(self):
        _, traza = self._ejecutar(300000, 400000, 661000, 0, "Medio", "Media")
        self.assertEqual(["ratio_reparacion_max"], list(traza["criterios_usados"]))


class CuantizacionDecimalTest(unittest.TestCase):
    """La cuantización del grafo reproduce el redondeo IEEE-754 de la política anterior.

    Usa la utilidad numérica del módulo (`_CUERPO_CUANTIZADOR`) porque es la que la consulta
    de SM3 aplica a los indicadores: no hay ningún redondeo equivalente en Python. El atajo de
    representación binaria (ulp >= cuanto → devolver el valor) se cubre con los bordes 2^45..2^49
    y con 10^300, que antes desbordaba la aritmética entera.
    """

    # Empates exactos e inexactos, ceros con signo, múltiplos de mil, valores diminutos,
    # magnitudes grandes, los dos valores que llegaron a fallar (123.456.789.012.345,67 con dos
    # decimales y 10^300 con miles) y los bordes del atajo de representación binaria: ulp justo
    # por debajo del cuanto (2^45 · 1,5 y 2^48 · 1,5) y justo por encima (2^46 · 1,5, 2^49 · 1,5).
    VALORES = (0.505, 0.515, 0.625, 0.495, 0.125, 6.55, 2.675, 0.065, 0.05, 0.005, 0.015,
               0.045, 29.65, 29.75, 12.35, 12.45, 12.55, 2500.0, 1500.0, 500.0, 499.0, 501.0,
               -499.0, -500.0, -501.0, 300500.0, 1234500.0, 0.0, -0.0, -0.0049999, 0.0049999,
               1.0, -1.0, 8.0, 1024.0, 0.5, 2.5, -2.5, -0.625, -6.55, 1e6, 1e9, 1e13, 9e13,
               1e-3, 1e-8, 0.001, 0.006, 999999.995,
               123456789012345.67, 123456789012345.75, 123456789012345.125, 9.1e13, 1e14,
               2.0 ** 45 * 1.5, 2.0 ** 46 * 1.5, 2.0 ** 48 * 1.5, 2.0 ** 49 * 1.5,
               1e15, 1e15 + 0.125, 1e16, 1e18, 2.0 ** 55 + 0.25, 1e100, 1e300, 1.7e308,
               5e-324, 1e-300)

    def test_la_cuantizacion_coincide_con_el_redondeo_de_la_politica_anterior(self):
        consulta = ("WITH $valor AS valor, $decimales AS decimales\n"
                    + ism3._CUERPO_CUANTIZADOR + "RETURN q AS q")
        with _driver.session(database=BASE_PRUEBAS) as sesion:
            for decimales in (1, 2, -3):
                for valor in self.VALORES:
                    with self.subTest(valor=valor, decimales=decimales):
                        obtenido = sesion.run(consulta, valor=valor, decimales=decimales).single()["q"]
                        esperado = round(valor, decimales)
                        self.assertEqual(esperado, obtenido)
                        self.assertEqual(math.copysign(1.0, esperado), math.copysign(1.0, obtenido))


class AutoridadDelGrafoTest(unittest.TestCase):
    """Ninguna lectura de conocimiento en Python puede cambiar la decisión de SM3."""

    CASO = (400000, 65000, 661000, 0, "Medio", "Media")

    def _ejecutar(self, precio, costo, vma, intervenciones, riesgo, demanda):
        traza = oe.nueva_traza()
        return oe.ejecutar_motor_sm3(precio, costo, vma, intervenciones, riesgo, demanda, traza), traza

    def test_la_decision_no_depende_de_lo_que_python_lea_del_conocimiento(self):
        esperado = oe.ejecutar_motor_sm3(*self.CASO, oe.nueva_traza())
        with mock.patch.object(oe, "cargar_conocimiento", return_value=_conocimiento_alterado()):
            traza = oe.nueva_traza()
            obtenido = oe.ejecutar_motor_sm3(*self.CASO, traza)
        self.assertEqual(esperado, obtenido)
        # La procedencia sigue siendo la del grafo, no la del conocimiento simulado en Python.
        criterios = _criterios()
        self.assertEqual(criterios["margen_base"]["id"], traza["criterios_usados"]["margen_base"]["id"])
        self.assertEqual(criterios["margen_base"]["valor"], traza["criterios_usados"]["margen_base"]["valor"])

    def test_el_mapeo_de_categoria_viene_del_grafo(self):
        for categoria, decision in (("Comprar", "Comprar"), ("Negociar", "ComprarConOfertaMenor"),
                                    ("Descartar", "DescartarPorRiesgo")):
            with self.subTest(categoria=categoria):
                resolucion = ism3.resolver_decision_sm3_cypher(_driver, BASE_PRUEBAS, categoria, 123000)
                self.assertEqual(decision, resolucion["decision"])
                self.assertEqual(123000 if categoria == "Negociar" else None,
                                 resolucion["contraoferta_sugerida_ars"])
        sin_categoria = ism3.resolver_decision_sm3_cypher(_driver, BASE_PRUEBAS, "Inexistente", 0)
        self.assertIsNone(sin_categoria["decision"])

    def test_un_vma_cero_conserva_la_excepcion_de_la_politica_anterior(self):
        for vma in (0, 0.0, -0.0):
            with self.subTest(vma=vma):
                traza = oe.nueva_traza()
                with self.assertRaises(ZeroDivisionError) as contexto:
                    oe.ejecutar_motor_sm3(1000, 0, vma, 0, "Bajo", "Alta", traza)
                self.assertEqual("division by zero", str(contexto.exception))
                # La política anterior dividía antes de leer criterios: la traza queda vacía.
                self.assertEqual({}, traza["criterios_usados"])
                self.assertEqual([], traza["reglas"])

    def test_un_vma_negativo_se_evalua_como_la_politica_anterior(self):
        resultado, traza = self._ejecutar(1000, 0, -661000, 0, "Medio", "Media")
        self.assertEqual(0.0, resultado["indicadores"]["ratio_reparacion"])
        self.assertEqual(100.2, resultado["indicadores"]["margen_neto_pct"])
        self.assertEqual(0.0, resultado["indicadores"]["contraoferta_sugerida_ars"] or 0.0)
        self.assertEqual(100.0, resultado["indicadores"]["descuento_requerido_pct"])
        self.assertIn("ratio_reparacion_max", traza["criterios_usados"])

    def test_los_booleanos_siguen_siendo_numeros_como_ante(self):
        resultado, _ = self._ejecutar(True, False, 661000, 0, "Medio", "Media")
        self.assertEqual(1, resultado["indicadores"]["precio_publicado"])
        self.assertEqual(0, resultado["indicadores"]["costo_reparacion"])

    def test_las_entradas_no_numericas_se_rechazan_antes_de_inferir(self):
        for caso in ((("350000"), 0, 661000), (400000, "mucho", 661000), (400000, 0, None)):
            with self.subTest(caso=caso):
                with self.assertRaises(TypeError):
                    oe.ejecutar_motor_sm3(*caso, 0, "Medio", "Media", oe.nueva_traza())


AVISO_T14 = ("Vendo Lenovo ThinkPad T14 año 2020 con Intel i5 10ma gen y Windows 11 oficial. "
             "Piden $400.000. Batería al 91% con 110 ciclos, temperatura bajo carga 68°C sin throttling. "
             "16GB de RAM y SSD de 512GB. Pantalla y teclado perfectos, con cargador original.")
EXTRACCION_T14 = {"marca": "Lenovo", "modelo": "ThinkPad T14", "procesador": "i5 10ma gen",
                  "anio_fabricacion": 2020, "ram_gb": 16, "tipo_disco": "SSD",
                  "salud_bateria_pct": 91, "ciclos_bateria": 110, "temperatura_cpu_c": 68,
                  "thermal_throttling": False, "pantalla_danada": False, "teclado_danado": False,
                  "cargador_incluido": True, "soporte_windows_11": True,
                  "precio_publicado": 400000, "fallas": []}


def _llm_controlado(dictamen):
    """Extractor y enrutador fijos; el redactor devuelve el dictamen que pida cada prueba."""
    def responder(system_prompt, user_content, json_mode=False, max_tokens=300):
        if system_prompt.startswith(oe.PROMPT_EXTRACTOR_INTEGRAL):
            return json.dumps(EXTRACCION_T14)
        if system_prompt.startswith(oe.PROMPT_MAESTRO_ENRUTAMIENTO):
            return json.dumps({"intencion": "evaluacion_integral", "motivo": "prueba"})
        return dictamen
    return responder


class RutaPublicaTest(unittest.TestCase):
    """La evaluación integral toma la decisión del grafo y el dictamen no la reemplaza."""

    def _evaluar(self, dictamen):
        with mock.patch.object(oe, "consultar_llm", side_effect=_llm_controlado(dictamen)):
            with redirect_stdout(StringIO()):
                return oe.evaluar_publicacion_integral(AVISO_T14, verbose=False)

    def _decision_del_grafo(self, resultado):
        """Recalcula SM3 con las mismas entradas que recibió el pipeline."""
        sm1, sm2 = resultado["sm1_tecnico"], resultado["sm2_comercial"]
        with redirect_stdout(StringIO()):
            return oe.ejecutar_motor_sm3(float(resultado["datos_extraidos"]["precio_publicado"]),
                                         float(sm1["costo_total"]), float(sm2["vma_estimado_ars"]),
                                         sm1["cantidad_intervenciones"],
                                         sm2["riesgo_obsolescencia"], sm2["demanda_comercial"],
                                         oe.nueva_traza())

    def test_el_redactor_adversario_con_cifras_inventadas_no_reemplaza_la_decision(self):
        resultado = self._evaluar("El veredicto es COMPRAR DIRECTO: el costo es 1 ARS y el VMA 999999 ARS.")
        del_grafo = self._decision_del_grafo(resultado)
        sm3 = resultado["sm3_financiero"]
        self.assertEqual(del_grafo["decision"], sm3["decision"])
        self.assertEqual(del_grafo["indicadores"], sm3["indicadores"])
        # El dictamen con cifras inventadas se descarta: queda el determinístico del grafo.
        self.assertTrue(resultado["dictamen_gerencial"].startswith("DICTAMEN EJECUTIVO EVALTIC"))

    def test_el_redactor_adversario_sin_cifras_no_cambia_los_campos_del_grafo(self):
        del_grafo = self._decision_del_grafo(self._evaluar(""))
        resultado = self._evaluar("Se recomienda descartar la compra y no pagar nada por el equipo.")
        sm3 = resultado["sm3_financiero"]
        self.assertEqual(del_grafo["decision"], sm3["decision"])
        self.assertEqual(del_grafo["indicadores"], sm3["indicadores"])
        self.assertEqual(del_grafo["categoria_difusa"], sm3["categoria_difusa"])
        # La prosa puede describir otra cosa, pero no reemplaza la decisión ni los montos.
        self.assertEqual("Se recomienda descartar la compra y no pagar nada por el equipo.",
                         resultado["dictamen_gerencial"])

    def test_la_evaluacion_integral_conserva_las_secciones_y_la_traza(self):
        resultado = self._evaluar("")
        for seccion in ("datos_extraidos", "sm1_tecnico", "sm2_comercial", "sm3_financiero",
                        "traza", "dictamen_gerencial"):
            self.assertIn(seccion, resultado)
        self.assertIn("criterios_usados", resultado["traza"])
        self.assertIn("ratio_reparacion_max", resultado["traza"]["criterios_usados"])
        self.assertIn(resultado["sm3_financiero"]["estado_decision"], ("Firme", "Provisional"))


if __name__ == "__main__":
    unittest.main()
