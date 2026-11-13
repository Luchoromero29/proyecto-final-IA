#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pruebas del ejecutor real de publicaciones críticas (S2, S3, S4, S7).

Se ejerce `main(argv)` —la interfaz pública del ejecutor— con un módulo motor
ficticio inyectado en `sys.modules`: no hay LLM, ni Neo4j, ni red. Se verifica
conteo de resultados, separación de infraestructura, punto de entrada por caso,
privacidad de la salida y validación de expectativas.

Ejecutar desde la raíz del repositorio:
    python app/tests/test_probar_publicaciones.py -v
"""

import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scripts import probar_publicaciones as ejecutor  # noqa: E402  (módulo sin efectos de import)

RUIDO_SECRETO = "PROVEEDOR-SECRETO sk-live-NO-DEBE-SALIR"


class MotorFalso:
    """Frontera externa simulada: solo el motor y el grafo, con forma real."""

    LLM_PROVIDER = "openai"
    OPENAI_API_KEY = "clave-ficticia-de-prueba"
    OPENAI_BASE_URL = "https://usuario:secreto@api.ficticia.invalid/v1?token=oculto"
    OPENAI_MODEL = "modelo-ficticio"
    OLLAMA_MODEL = "modelo-ollama-ficticio"
    OLLAMA_URL = "http://ollama.ficticio.invalid/api/generate"
    NEO4J_URI = "bolt://usuario:clave-neo4j@neo4j.ficticio.invalid:7687"
    NEO4J_DATABASE = "neo4j"
    TIPO_INSTANCIA = "Local Offline (Docker)"

    def __init__(self, respuestas=None, catalogo=(83, 18, 45, 11), ruido=""):
        self.respuestas = respuestas or {}
        self.catalogo = catalogo
        self.ruido = ruido
        self.llamadas = []

    # --- grafo ---
    def obtener_driver_neo4j(self):
        return self

    def session(self, database=None):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *argumentos):
        return False

    def run(self, consulta, **parametros):
        return self

    def single(self):
        procesadores, calibrados, lineas, rams = self.catalogo
        return {"procesadores": procesadores, "calibrados": calibrados, "lineas": lineas, "rams": rams}

    def cargar_conocimiento(self, forzar=False):
        return {"criterios": {}, "costos": {}}

    # --- pipeline ---
    def _responder(self, punto_entrada, texto):
        self.llamadas.append((punto_entrada, texto))
        if self.ruido:
            print(self.ruido)
            print(self.ruido, file=sys.stderr)
        respuesta = self.respuestas.get(texto, {"sm3_financiero": {"decision": "Comprar"}})
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    def asistente_evaltic(self, texto, verbose=True):
        return self._responder("asistente", texto)

    def evaluar_publicacion_integral(self, texto, verbose=True):
        return self._responder("integral", texto)


def caso(ident):
    return next(c for c in ejecutor.cargar_corpus() if c["id"] == ident)


class EjecutorTest(unittest.TestCase):
    def _correr(self, motor, argv):
        salida, errores = StringIO(), StringIO()
        with mock.patch.dict(sys.modules, {"orquestador_evaltic": motor}), \
                redirect_stdout(salida), redirect_stderr(errores):
            codigo = ejecutor.main(argv)
        return codigo, salida.getvalue(), errores.getvalue()

    # --- interfaz pública ---
    def test_listado_por_defecto_no_importa_el_motor(self):
        salida, errores = StringIO(), StringIO()
        with mock.patch.dict(sys.modules, {"orquestador_evaltic": None}), \
                redirect_stdout(salida), redirect_stderr(errores):
            codigo = ejecutor.main([])
        texto = salida.getvalue()
        self.assertEqual(0, codigo)
        self.assertIn("falta --ejecutar", texto)
        self.assertEqual(61, len([l for l in texto.splitlines() if l.startswith("PC-")]))
        self.assertEqual("", errores.getvalue())

    def test_ayuda_documenta_servicios_y_banderas(self):
        salida = StringIO()
        with redirect_stdout(salida):
            with self.assertRaises(SystemExit) as contexto:
                ejecutor.main(["--help"])
        texto = salida.getvalue()
        self.assertEqual(0, contexto.exception.code)
        for fragmento in ("--ejecutar", "--caso", "--verificar", "Neo4j", "tokens"):
            self.assertIn(fragmento, texto)

    def test_id_desconocido_sale_con_codigo_dos(self):
        motor = MotorFalso()
        codigo, salida, _ = self._correr(motor, ["--caso", "PC-99", "--ejecutar"])
        self.assertEqual(2, codigo)
        self.assertIn("IDs desconocidos: PC-99", salida)
        self.assertIn("IDs válidos", salida)
        self.assertEqual([], motor.llamadas, "no debe llamar al motor con un ID inválido")

    # --- chequeo previo ---
    def test_verificar_informa_catalogo_sin_llamar_al_pipeline(self):
        motor = MotorFalso()
        codigo, salida, errores = self._correr(motor, ["--verificar"])
        self.assertEqual(0, codigo)
        self.assertIn("Procesador=83 (con precio=18) · Linea=45 · CapacidadRAM=11", salida)
        self.assertIn("No se ejecutó ningún caso", salida)
        self.assertEqual([], motor.llamadas)
        self.assertEqual("", errores)

    def test_verificar_sin_catalogo_no_sugiere_recargas_peligrosas(self):
        motor = MotorFalso(catalogo=(0, 0, 0, 0))
        codigo, salida, _ = self._correr(motor, ["--verificar"])
        self.assertEqual(2, codigo)
        self.assertIn("catálogo PG3", salida)
        self.assertIn("README", salida)
        self.assertNotIn("actualizar.bat", salida)
        self.assertNotIn("neo4j-init", salida)
        self.assertEqual([], motor.llamadas)

    def test_no_expone_credenciales_de_las_urls_configuradas(self):
        motor = MotorFalso()
        codigo, salida, errores = self._correr(motor, ["--verificar"])
        self.assertEqual(0, codigo)
        self.assertIn("api.ficticia.invalid", salida)
        self.assertIn("neo4j.ficticio.invalid", salida)
        for visible in (salida, errores):
            self.assertNotIn("secreto", visible)
            self.assertNotIn("token=oculto", visible)
            self.assertNotIn("clave-neo4j", visible)

    # --- conteo de resultados ---
    def test_conteo_separa_cumplidos_fallidos_e_infraestructura(self):
        motor = MotorFalso({
            caso("PC-02")["entrada"]: {"error": "Entrada rechazada: falta marca/modelo o precio comercial válido."},
            caso("PC-44")["entrada"]: {"sm1_tecnico": {"plan_reparacion": [], "costo_total": 0},
                                       "sm2_comercial": {"vma_estimado_ars": 100},
                                       "sm3_financiero": {"decision": "VerificacionPendiente",
                                                         "regla_aplicada": "R3.3c"}},
            caso("PC-07")["entrada"]: ConnectionError("falla de prueba"),
        })
        codigo, salida, errores = self._correr(
            motor, ["--ejecutar", "--caso", "PC-02", "--caso", "PC-44", "--caso", "PC-07"])
        self.assertEqual(2, codigo)
        self.assertIn("Casos intentados: 3 · completados: 2 · cumplen: 1 · fallan: 1 · "
                      "sondas: 0 · infra: 1", salida)
        self.assertIn("No cumplen la expectativa: PC-44", salida)
        self.assertIn("Casos con error de infraestructura: PC-07", salida)
        self.assertIn("[INFRA] No se pudo ejecutar el caso: ConnectionError", salida)
        self.assertEqual(1, salida.count("✔ cumple la expectativa"))
        self.assertEqual(1, salida.count("✘"))
        self.assertEqual("", errores)

    def test_infraestructura_nunca_cuenta_como_cumplido(self):
        motor = MotorFalso({caso("PC-02")["entrada"]: TimeoutError("sin respuesta")})
        codigo, salida, _ = self._correr(motor, ["--ejecutar", "--caso", "PC-02"])
        self.assertEqual(2, codigo)
        self.assertIn("cumplen: 0 · fallan: 0 · sondas: 0 · infra: 1", salida)
        self.assertNotIn("✔", salida)

    def test_falla_de_dominio_sale_con_codigo_uno(self):
        motor = MotorFalso({caso("PC-44")["entrada"]: {"sm1_tecnico": {"plan_reparacion": []},
                                                       "sm3_financiero": {"decision": "Comprar"}}})
        codigo, salida, _ = self._correr(motor, ["--ejecutar", "--caso", "PC-44"])
        self.assertEqual(1, codigo)
        self.assertIn("cumplen: 0 · fallan: 1 · sondas: 0 · infra: 0", salida)

    def test_caso_cumplido_sale_con_codigo_cero(self):
        motor = MotorFalso({caso("PC-02")["entrada"]: {
            "error": "Entrada rechazada: falta marca/modelo o precio comercial válido."}})
        codigo, salida, _ = self._correr(motor, ["--ejecutar", "--caso", "PC-02"])
        self.assertEqual(0, codigo)
        self.assertIn("cumplen: 1 · fallan: 0 · sondas: 0 · infra: 0", salida)

    def test_error_de_base_de_conocimiento_se_informa_como_infraestructura(self):
        motor = MotorFalso({caso("PC-02")["entrada"]: {
            "error": "Base de conocimiento incompleta: La marca o línea del equipo no está en Neo4j."}})
        codigo, salida, _ = self._correr(motor, ["--ejecutar", "--caso", "PC-02"])
        self.assertEqual(2, codigo)
        self.assertIn("[INFRA] El motor devolvió un error de base de conocimiento", salida)
        self.assertIn("cumplen: 0 · fallan: 0 · sondas: 0 · infra: 1", salida)

    # --- punto de entrada por caso ---
    def test_respeta_via_integral_igual_que_las_pruebas_offline(self):
        motor = MotorFalso({caso("PC-61")["entrada"]: {
            "error": "Entrada rechazada: falta marca/modelo o precio comercial válido."},
            caso("PC-15")["entrada"]: {"sm1_tecnico": {"plan_reparacion": [], "costo_total": 0},
                                       "sm3_financiero": {"decision": "Comprar", "estado_decision": "Firme"}}})
        codigo, _, _ = self._correr(motor, ["--ejecutar", "--caso", "PC-61", "--caso", "PC-15"])
        self.assertEqual(0, codigo)
        self.assertEqual(["integral", "asistente"], [punto for punto, _ in motor.llamadas])

    # --- privacidad ---
    def test_categoria_del_error_no_expone_el_cuerpo_privado(self):
        motor = MotorFalso({caso("PC-48")["entrada"]:
                            RuntimeError("[ERROR API REMOTA] sk-live SECRETO cuerpo privado")})
        codigo, salida, errores = self._correr(motor, ["--ejecutar", "--caso", "PC-48"])
        self.assertEqual(2, codigo)
        self.assertIn("categoría: API_REMOTA", salida)
        self.assertNotIn("SECRETO", salida + errores)
        self.assertNotIn("sk-live", salida + errores)
        self.assertIn("cumplen: 0", salida)

    def test_no_expone_la_salida_cruda_del_motor(self):
        motor = MotorFalso({caso("PC-02")["entrada"]: {
            "error": "Entrada rechazada: falta marca/modelo o precio comercial válido."}}, ruido=RUIDO_SECRETO)
        codigo, salida, errores = self._correr(motor, ["--ejecutar", "--caso", "PC-02"])
        self.assertEqual(0, codigo)
        for visible in (salida, errores):
            self.assertNotIn("PROVEEDOR-SECRETO", visible)
            self.assertNotIn("sk-live", visible)

    def test_expectativa_invalida_en_el_corpus_sale_con_codigo_dos_sin_llamar_al_motor(self):
        motor = MotorFalso()
        invalido = dict(caso("PC-02"), espera={"resultado": "flujo", "clave_inventada": 1})
        with mock.patch.object(ejecutor, "cargar_corpus", return_value=[invalido]):
            codigo, salida, _ = self._correr(motor, ["--ejecutar", "--caso", "PC-02"])
        self.assertEqual(2, codigo)
        self.assertIn("[USO] Expectativa inválida en PC-02", salida)
        self.assertEqual([], motor.llamadas)

    def test_sonda_se_registra_sin_contar_como_cumplida(self):
        motor = MotorFalso({caso("PC-27")["entrada"]: {"sm3_financiero": {"decision": "Comprar"}}})
        codigo, salida, _ = self._correr(motor, ["--ejecutar", "--caso", "PC-27"])
        self.assertEqual(0, codigo)
        self.assertIn("sondas: 1", salida)
        self.assertIn("SONDA (sin expectativa automática)", salida)
        self.assertNotIn("✔", salida)

    # --- validación de expectativas ---
    def test_expectativa_con_clave_desconocida_falla(self):
        with self.assertRaises(ValueError):
            ejecutor.validar_espera({"resultado": "flujo", "clave_inventada": 1})

    def test_expectativa_con_tipo_de_resultado_desconocido_falla(self):
        with self.assertRaises(ValueError):
            ejecutor.validar_espera({"resultado": "quizas"})

    def test_expectativa_valida_no_falla(self):
        ejecutor.validar_espera({"resultado": "decision", "decision_en": ["Comprar"]})
        ejecutor.validar_espera({"resultado": "flujo", "error_ausente": True})

    def test_comprobar_no_ignora_intencion_en(self):
        """Regresión: una ejecución fuera de dominio no puede cumplir una expectativa en dominio."""
        fallos = ejecutor._comprobar({"intencion": "fuera_de_dominio"},
                                    {"resultado": "flujo",
                                     "intencion_en": ["evaluacion_integral", "diagnostico_tecnico"]})
        self.assertNotEqual([], fallos)

    def test_decision_pendiente_solo_cuenta_si_esta_permitida(self):
        permitida = {"resultado": "decision", "decision_en": ["VerificacionPendiente"]}
        self.assertEqual([], ejecutor._comprobar({"sm3_financiero": {"decision": "VerificacionPendiente"}},
                                                permitida))
        self.assertNotEqual([], ejecutor._comprobar({"sm3_financiero": {"decision": "Comprar"}}, permitida))
        self.assertNotEqual([], ejecutor._comprobar({"sm3_financiero": {}}, {"resultado": "decision"}))


if __name__ == "__main__":
    unittest.main()
