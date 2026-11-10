"""Regresiones de integridad del precio por el asistente público, sin red."""

import copy
import unittest

from app.tests.test_publicaciones_criticas import CASOS, _comprobar, _ejecutar


class IntegridadPrecioTest(unittest.TestCase):
    def _caso(self, ident="PC-29", precio_llm=115000):
        caso = copy.deepcopy(CASOS[ident])
        caso["extraccion_llm"]["precio_publicado"] = precio_llm
        return caso

    def _exigir_precio(self, caso, esperado):
        ejecucion = _ejecutar(caso)
        resultado = ejecucion.resultado
        self.assertNotIn("error", resultado)
        self.assertEqual(esperado, resultado["datos_extraidos"]["precio_publicado"])
        self.assertEqual(esperado, resultado["sm3_financiero"]["indicadores"]["precio_publicado"])
        self.assertEqual(1, ejecucion.mercado.call_count)

    def _exigir_rechazo(self, caso):
        ejecucion = _ejecutar(caso)
        self.assertEqual("Entrada rechazada: falta marca/modelo o precio comercial válido.",
                         ejecucion.resultado.get("error"))
        for seccion in ("sm1_tecnico", "sm2_comercial", "sm3_financiero", "dictamen_gerencial"):
            self.assertNotIn(seccion, ejecucion.resultado)
        self.assertEqual(0, ejecucion.mercado.call_count)
        self.assertEqual(2, ejecucion.llm.call_count)  # router y extracción; sin síntesis
        return ejecucion.resultado

    def test_un_peso_no_se_reemplaza_por_el_precio_inventado_del_llm(self):
        self._exigir_precio(self._caso(), 1)

    def test_los_montos_cortos_se_validan_igual_que_los_miles(self):
        for monto in (25, 999, 1500):
            with self.subTest(monto=monto):
                caso = self._caso()
                caso["entrada"] = caso["entrada"].replace("precio $1,", f"precio ${monto},")
                self._exigir_precio(caso, monto)

    def test_cero_no_se_convierte_en_una_compra_por_el_valor_del_llm(self):
        caso = self._caso("PC-30")
        resultado = self._exigir_rechazo(caso)
        self.assertEqual(0, resultado["datos_extraidos"]["precio_publicado"])

    def test_pesos_sin_simbolo_tienen_respaldo_aunque_el_llm_no_extraiga_precio(self):
        self._exigir_precio(self._caso("PC-26", None), 320000)

    def test_el_precio_literal_manda_sin_tolerancia_monetaria(self):
        self._exigir_precio(self._caso("PC-31", 300500), 300000)

    def test_un_tipo_incorrecto_del_llm_no_rompe_un_monto_explicito(self):
        self._exigir_precio(self._caso("PC-31", "inventado"), 300000)

    def test_sin_precio_en_el_texto_no_se_acepta_el_precio_inventado(self):
        caso = self._caso()
        caso["entrada"] = caso["entrada"].replace("precio $1, ", "")
        self._exigir_rechazo(caso)

    def test_los_formatos_ya_admitidos_conservan_su_contrato(self):
        for ident in ("PC-26", "PC-28", "PC-30", "PC-31"):
            with self.subTest(caso=ident):
                caso = copy.deepcopy(CASOS[ident])
                self.assertEqual([], _comprobar(_ejecutar(caso).resultado, caso["espera"]))


if __name__ == "__main__":
    unittest.main()
