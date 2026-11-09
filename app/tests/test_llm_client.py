#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pruebas offline de la capa LLM de EvalTIC (adaptación acotada).

Cubren la función pública `consultar_llm` con transporte mockeado, la validación
de respuestas, los presupuestos de los llamadores y la selección del archivo de
configuración. No llaman a ninguna API, no consultan Neo4j y no leen el `.env`
real: antes de importar el orquestador se fijan variables ficticias y se
desactiva `dotenv.load_dotenv`.

Ejecutar desde la raíz del repositorio:
    python -m unittest discover -s app/tests -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# ------------------------------------------------------------------------------
# Aislamiento previo a la importación del módulo bajo prueba
# ------------------------------------------------------------------------------
ENTORNO_PRUEBA = {
    "LLM_PROVIDER": "ollama",
    "OLLAMA_URL": "http://ollama.invalid/api/generate",
    "OLLAMA_MODEL": "modelo-ollama-de-prueba",
    "OPENAI_API_KEY": "clave-ficticia-de-prueba",
    "OPENAI_BASE_URL": "https://api.openai.com/v1",
    "OPENAI_MODEL": "modelo-openai-de-prueba",
    "NEO4J_TARGET": "local",
    "NEO4J_LOCAL_URI": "bolt://neo4j.invalid:7687",
    "NEO4J_LOCAL_USERNAME": "usuario-de-prueba",
    "NEO4J_LOCAL_PASSWORD": "clave-ficticia-neo4j",
    "NEO4J_LOCAL_DATABASE": "neo4j",
}

for _clave, _valor in ENTORNO_PRUEBA.items():
    os.environ[_clave] = _valor

# Se importa el orquestador con `load_dotenv` neutralizado: la configuración de
# la máquina no debe filtrarse a las pruebas.
with mock.patch("dotenv.load_dotenv", return_value=False):
    import orquestador_evaltic as oe

from dotenv import load_dotenv as load_dotenv_real  # noqa: E402  (después del aislamiento)

MODELO_NEMOTRON = "nvidia/nemotron-3.5-lightning:free"
URL_OPENROUTER = "https://openrouter.ai/api/v1"
URL_GROQ = "https://api.groq.com/openai/v1"


# ------------------------------------------------------------------------------
# Utilidades de prueba
# ------------------------------------------------------------------------------
def respuesta_falsa(payload=None, status_code=200, texto=""):
    """Respuesta HTTP simulada de `requests.post`."""
    resp = mock.Mock()
    resp.status_code = status_code
    resp.text = texto
    resp.json.return_value = {} if payload is None else payload
    return resp


def respuesta_chat(content="texto de respuesta", finish_reason="stop", usage=None, razonamiento=None):
    """Cuerpo compatible OpenAI/Ollama-API de chat completions."""
    mensaje = {"role": "assistant", "content": content}
    if razonamiento is not None:
        mensaje["reasoning"] = razonamiento
    datos = {"choices": [{"message": mensaje, "finish_reason": finish_reason}]}
    if usage is not None:
        datos["usage"] = usage
    return datos


def _existe_solo(existentes):
    """Patch de `Path.exists` limitado al conjunto de rutas indicado."""
    rutas = {str(Path(r)) for r in existentes}
    return mock.patch.object(Path, "exists", lambda self: str(self) in rutas)


RESUMEN_PRUEBA = {
    "equipo": "Equipo ficticio de prueba",
    "decision": "Comprar",
    "estado_decision": "Provisional",
    "motivo": "motivo de prueba",
    "fallas": ["pantalla con rayas"],
    "sm1": {"viable": True, "reparaciones": ["pantalla"], "costo_reparacion_ars": 1000},
    "sm2": {"vma_ars": 2000, "riesgo": "Medio", "demanda": "Media"},
    "sm3": {"precio_publicado": 1000, "margen_neto_pct": 10, "margen_requerido_pct": 5},
}


class ClienteOllamaTest(unittest.TestCase):
    """Ollama conserva exactamente el payload y el presupuesto previos."""

    def setUp(self):
        for objetivo, valor in (
            ("LLM_PROVIDER", "ollama"),
            ("OLLAMA_URL", "http://ollama.invalid/api/generate"),
            ("OLLAMA_MODEL", "modelo-ollama-de-prueba"),
        ):
            parche = mock.patch.object(oe, objetivo, valor)
            parche.start()
            self.addCleanup(parche.stop)

    def test_payload_y_presupuesto_de_ollama_se_conservan(self):
        with mock.patch.object(oe.requests, "post",
                               return_value=respuesta_falsa({"response": "  texto ollama  "})) as post:
            resultado = oe.consultar_llm("sistema", "usuario", json_mode=True, max_tokens=1024)
        self.assertEqual("texto ollama", resultado)
        payload = post.call_args.kwargs["json"]
        self.assertEqual("modelo-ollama-de-prueba", payload["model"])
        self.assertEqual("sistema\n\nEntrada del usuario:\nusuario", payload["prompt"])
        self.assertFalse(payload["stream"])
        self.assertEqual({"temperature": 0.1, "num_predict": 1024}, payload["options"])
        self.assertNotIn("format", payload)
        self.assertNotIn("reasoning", payload)
        self.assertEqual("http://ollama.invalid/api/generate", post.call_args.args[0])
        self.assertEqual(120, post.call_args.kwargs["timeout"])

    def test_error_http_de_ollama_se_conserva(self):
        with mock.patch.object(oe.requests, "post",
                               return_value=respuesta_falsa(status_code=500, texto="falla interna")):
            with self.assertRaises(RuntimeError) as ctx:
                oe.consultar_llm("sistema", "usuario")
        self.assertIn("[ERROR OLLAMA]", str(ctx.exception))
        self.assertIn("500", str(ctx.exception))


class PresupuestosLlamadoresTest(unittest.TestCase):
    """Los llamadores piden presupuestos mayores y conservan sus límites previos."""

    def test_extraccion_usa_1024_tokens_sin_json_mode(self):
        with mock.patch.object(oe, "consultar_llm", return_value='{"marca": "Acer", "fallas": []}') as llamada:
            datos = oe.extraer_datos_llm("aviso de prueba")
        self.assertEqual("Acer", datos["marca"])
        self.assertEqual(1, llamada.call_count)
        args, kwargs = llamada.call_args
        self.assertEqual(oe.PROMPT_EXTRACTOR_INTEGRAL, args[0])
        self.assertEqual("aviso de prueba", args[1])
        self.assertFalse(kwargs["json_mode"])
        self.assertEqual(1024, kwargs["max_tokens"])

    def test_extraccion_reintenta_una_vez_con_el_mismo_presupuesto(self):
        with mock.patch.object(oe, "consultar_llm",
                               side_effect=["texto sin json", '{"marca": "Acer", "fallas": []}']) as llamada:
            datos = oe.extraer_datos_llm("aviso de prueba")
        self.assertEqual("Acer", datos["marca"])
        self.assertEqual(2, llamada.call_count)
        primer, segundo = llamada.call_args_list
        self.assertEqual(1024, primer.kwargs["max_tokens"])
        self.assertEqual(1024, segundo.kwargs["max_tokens"])
        self.assertFalse(primer.kwargs["json_mode"])
        self.assertFalse(segundo.kwargs["json_mode"])
        self.assertTrue(segundo.args[0].startswith(oe.PROMPT_EXTRACTOR_INTEGRAL))
        self.assertIn("IMPORTANTE", segundo.args[0])

    def test_extraccion_falla_tras_dos_intentos(self):
        with mock.patch.object(oe, "consultar_llm", side_effect=["nada", "tampoco"]) as llamada:
            with self.assertRaises(ValueError) as ctx:
                oe.extraer_datos_llm("aviso de prueba")
        self.assertEqual(2, llamada.call_count)
        self.assertIn("[ERROR PARSEO]", str(ctx.exception))

    def test_sintesis_usa_768_tokens_sin_json_mode(self):
        with mock.patch.object(oe, "consultar_llm",
                               return_value="  Dictamen ejecutivo ficticio suficientemente largo.  ") as llamada:
            dictamen = oe.generar_sintesis_gerencial_llm(RESUMEN_PRUEBA)
        self.assertEqual("Dictamen ejecutivo ficticio suficientemente largo.", dictamen)
        args, kwargs = llamada.call_args
        self.assertEqual(oe.PROMPT_SINTESIS_GERENCIAL, args[0])
        self.assertIn("Equipo ficticio de prueba", args[1])
        self.assertFalse(kwargs["json_mode"])
        self.assertEqual(768, kwargs["max_tokens"])

    def test_sintesis_conserva_el_respaldo_deterministico_con_aviso(self):
        esperado = oe.generar_dictamen_sintesis(RESUMEN_PRUEBA)
        salida = StringIO()
        with mock.patch.object(oe, "consultar_llm", side_effect=RuntimeError("[ERROR RESPUESTA LLM] truncada")):
            with redirect_stdout(salida):
                dictamen = oe.generar_sintesis_gerencial_llm(RESUMEN_PRUEBA)
        self.assertEqual(esperado, dictamen)
        self.assertIn("[Aviso Síntesis LLM]", salida.getvalue())


class ConfiguracionEntornoTest(unittest.TestCase):
    """Precedencia del .env y respeto por las variables ya exportadas."""

    def test_candidatos_en_orden_app_raiz_pi4(self):
        esperado = [
            APP_DIR / ".env",
            APP_DIR.parent / ".env",
            APP_DIR.parent / "PI4" / ".env",
        ]
        self.assertEqual(esperado, [Path(c) for c in oe.ENV_PATH_CANDIDATOS])

    def test_precedencia_app_sobre_raiz_y_pi4(self):
        app, raiz, pi4 = (APP_DIR / ".env", APP_DIR.parent / ".env", APP_DIR.parent / "PI4" / ".env")
        with _existe_solo([app, raiz, pi4]):
            self.assertEqual(app, oe._resolver_env_path())
        with _existe_solo([raiz, pi4]):
            self.assertEqual(raiz, oe._resolver_env_path())
        with _existe_solo([pi4]):
            self.assertEqual(pi4, oe._resolver_env_path())

    def test_sin_archivos_devuelve_none(self):
        with _existe_solo([]):
            self.assertIsNone(oe._resolver_env_path())

    def test_carga_el_archivo_elegido_sin_override(self):
        elegido = Path("/ruta/ficticia/.env")
        with mock.patch.object(oe, "_resolver_env_path", return_value=elegido), \
                mock.patch.object(oe, "load_dotenv") as cargador:
            resultado = oe._cargar_configuracion_entorno()
        self.assertEqual(elegido, resultado)
        cargador.assert_called_once_with(elegido)
        self.assertNotIn("override", cargador.call_args.kwargs)

    def test_sin_archivo_usa_la_busqueda_preexistente_sin_override(self):
        with mock.patch.object(oe, "_resolver_env_path", return_value=None), \
                mock.patch.object(oe, "load_dotenv") as cargador:
            resultado = oe._cargar_configuracion_entorno()
        self.assertIsNone(resultado)
        cargador.assert_called_once_with()
        self.assertNotIn("override", cargador.call_args.kwargs)

    def test_variables_exportadas_no_se_pisan(self):
        directorio = tempfile.mkdtemp(prefix="evaltic-config-")
        self.addCleanup(shutil.rmtree, directorio, ignore_errors=True)
        archivo = Path(directorio) / ".env"
        archivo.write_text("EVALTIC_PRUEBA_VARIABLE=desde_archivo\n", encoding="utf-8")
        os.environ["EVALTIC_PRUEBA_VARIABLE"] = "exportada"
        self.addCleanup(os.environ.pop, "EVALTIC_PRUEBA_VARIABLE", None)
        with mock.patch.object(oe, "_resolver_env_path", return_value=archivo), \
                mock.patch.object(oe, "load_dotenv", load_dotenv_real):
            oe._cargar_configuracion_entorno()
        self.assertEqual("exportada", os.environ["EVALTIC_PRUEBA_VARIABLE"])


if __name__ == "__main__":
    unittest.main()
