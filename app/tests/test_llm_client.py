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
URL_NVIDIA = "https://integrate.api.nvidia.com/v1"
MODELO_NVIDIA = "nvidia/nemotron-3.5-lightning-30b-a3b"


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


class ClienteOpenRouterTest(unittest.TestCase):
    """Piso de presupuesto, razonamiento desactivado y validación de respuesta."""

    def setUp(self):
        for objetivo, valor in (
            ("LLM_PROVIDER", "openai"),
            ("OPENAI_API_KEY", "clave-ficticia-de-prueba"),
            ("OPENAI_BASE_URL", URL_OPENROUTER),
            ("OPENAI_MODEL", MODELO_NEMOTRON),
        ):
            parche = mock.patch.object(oe, objetivo, valor)
            parche.start()
            self.addCleanup(parche.stop)

    def _consultar(self, payload=None, **kwargs):
        with mock.patch.object(oe.requests, "post", return_value=respuesta_falsa(payload)) as post:
            resultado = oe.consultar_llm("system de prueba", "contenido de usuario", **kwargs)
        return resultado, post.call_args

    # --- presupuesto -----------------------------------------------------------
    def test_presupuesto_minimo_openrouter_eleva_limites_chicos(self):
        for pedido in (1, 260, 768, 1024):
            with self.subTest(pedido=pedido):
                _, llamada = self._consultar(respuesta_chat(), max_tokens=pedido)
                self.assertEqual(4096, llamada.kwargs["json"]["max_tokens"])

    def test_presupuesto_minimo_openrouter_conserva_limites_mayores(self):
        for pedido in (4096, 5000, 8000):
            with self.subTest(pedido=pedido):
                _, llamada = self._consultar(respuesta_chat(), max_tokens=pedido)
                self.assertEqual(pedido, llamada.kwargs["json"]["max_tokens"])

    # --- razonamiento ----------------------------------------------------------
    def test_razonamiento_desactivado_para_nemotron_en_extraccion_y_sintesis(self):
        for json_mode in (False, True):
            with self.subTest(json_mode=json_mode):
                _, llamada = self._consultar(respuesta_chat(), json_mode=json_mode, max_tokens=1024)
                self.assertEqual({"enabled": False}, llamada.kwargs["json"]["reasoning"])

    # --- respuesta válida ------------------------------------------------------
    def test_respuesta_valida_se_recorta_y_conserva_mensajes_y_formato_json(self):
        resultado, llamada = self._consultar(
            respuesta_chat(content="  {\"marca\": \"Acer\"}  \n"), json_mode=True, max_tokens=1024)
        self.assertEqual('{"marca": "Acer"}', resultado)
        payload = llamada.kwargs["json"]
        self.assertEqual(MODELO_NEMOTRON, payload["model"])
        self.assertEqual(0.1, payload["temperature"])
        self.assertEqual({"type": "json_object"}, payload["response_format"])
        self.assertEqual([
            {"role": "system", "content": "system de prueba"},
            {"role": "user", "content": "contenido de usuario"},
        ], payload["messages"])
        self.assertTrue(llamada.kwargs["headers"]["Authorization"].startswith("Bearer "))
        self.assertEqual(URL_OPENROUTER + "/chat/completions", llamada.args[0])

    def test_respuesta_valida_sin_json_mode_no_agrega_response_format(self):
        _, llamada = self._consultar(respuesta_chat(content="dictamen"), json_mode=False)
        self.assertNotIn("response_format", llamada.kwargs["json"])

    # --- rechazo por truncamiento ---------------------------------------------
    def test_longitud_con_contenido_nulo_produce_error_con_metadatos_seguros(self):
        payload = respuesta_chat(
            content=None,
            finish_reason="length",
            usage={"completion_tokens": 4096, "completion_tokens_details": {"reasoning_tokens": 4096}},
            razonamiento="RAZONAMIENTO-INTERNO-NO-EXPUESTO",
        )
        with self.assertRaises(RuntimeError) as ctx:
            self._consultar(payload, max_tokens=4096)
        mensaje = str(ctx.exception)
        self.assertIn("finish_reason=length", mensaje)
        self.assertIn("completion_tokens=4096", mensaje)
        self.assertIn("reasoning_tokens=4096", mensaje)
        self.assertNotIn("RAZONAMIENTO-INTERNO-NO-EXPUESTO", mensaje)

    def test_longitud_con_texto_parcial_no_se_acepta(self):
        payload = respuesta_chat(content='{"marca": "Acer", "mode', finish_reason="length")
        with self.assertRaises(RuntimeError) as ctx:
            self._consultar(payload, max_tokens=4096)
        self.assertIn("finish_reason=length", str(ctx.exception))

    def test_metadatos_desconocidos_se_informan_como_unknown(self):
        payload = {
            "choices": [{"message": {"content": None}, "finish_reason": "motivo-raro"}],
            "usage": {"completion_tokens": -3, "completion_tokens_details": {"reasoning_tokens": "muchos"}},
        }
        with self.assertRaises(RuntimeError) as ctx:
            self._consultar(payload)
        mensaje = str(ctx.exception)
        self.assertIn("finish_reason=unknown", mensaje)
        self.assertIn("completion_tokens=unknown", mensaje)
        self.assertIn("reasoning_tokens=unknown", mensaje)

    def test_metadatos_sin_usage_se_informan_como_unknown(self):
        payload = respuesta_chat(content=None, finish_reason="length")
        with self.assertRaises(RuntimeError) as ctx:
            self._consultar(payload)
        self.assertIn("completion_tokens=unknown", str(ctx.exception))
        self.assertIn("reasoning_tokens=unknown", str(ctx.exception))

    def test_finish_reason_no_textual_no_rompe_el_error_controlado(self):
        """Un finish_reason malformado (lista, dict, número) debe dar RuntimeError, no TypeError."""
        for finish_reason in (["length"], {"motivo": "length"}, 123, True, None):
            with self.subTest(finish_reason=finish_reason):
                payload = respuesta_chat(
                    content=None,
                    finish_reason=finish_reason,
                    razonamiento="RAZONAMIENTO-INTERNO-NO-EXPUESTO",
                )
                with mock.patch.object(oe.requests, "post", return_value=respuesta_falsa(payload)) as post:
                    with self.assertRaises(RuntimeError) as ctx:
                        oe.consultar_llm("sistema", "usuario")
                mensaje = str(ctx.exception)
                self.assertIn("[ERROR RESPUESTA LLM]", mensaje)
                self.assertIn("finish_reason=unknown", mensaje)
                self.assertNotIn("RAZONAMIENTO-INTERNO-NO-EXPUESTO", mensaje)
                self.assertNotIn("['length']", mensaje)
                self.assertNotIn("{'motivo'", mensaje)
                self.assertEqual(1, post.call_count)

    # --- rechazo de contenido ------------------------------------------------
    def test_contenido_nulo_blanco_o_no_textual_se_rechaza(self):
        for contenido in (None, "", "   \n\t", 123, ["texto"], {"texto": "x"}, True):
            with self.subTest(contenido=contenido):
                with self.assertRaises(RuntimeError):
                    self._consultar(respuesta_chat(content=contenido))

    # --- rechazo de estructura ----------------------------------------------
    def test_estructura_invalida_se_rechaza_de_forma_controlada(self):
        casos = {
            "cuerpo_no_objeto": ["no", "es", "un", "objeto"],
            "sin_choices": {"usage": {"completion_tokens": 1}},
            "choices_no_lista": {"choices": "texto"},
            "choices_vacio": {"choices": []},
            "choice_no_objeto": {"choices": ["texto"]},
            "sin_message": {"choices": [{"finish_reason": "stop"}]},
            "message_no_objeto": {"choices": [{"message": "texto", "finish_reason": "stop"}]},
        }
        for nombre, payload in casos.items():
            with self.subTest(caso=nombre):
                with self.assertRaises(RuntimeError) as ctx:
                    self._consultar(payload)
                self.assertIn("[ERROR RESPUESTA LLM]", str(ctx.exception))

    def test_error_http_previo_se_conserva(self):
        with mock.patch.object(oe.requests, "post", return_value=respuesta_falsa(status_code=429, texto="limite")) as post:
            with self.assertRaises(RuntimeError) as ctx:
                oe.consultar_llm("sistema", "usuario")
        self.assertIn("[ERROR API REMOTA]", str(ctx.exception))
        self.assertIn("429", str(ctx.exception))
        self.assertEqual(60, post.call_args.kwargs["timeout"])


class AlcanceRazonamientoTest(unittest.TestCase):
    """El override de razonamiento no se generaliza a otros modelos ni proveedores."""

    def _payload(self, base_url, modelo):
        with mock.patch.object(oe, "LLM_PROVIDER", "openai"), \
                mock.patch.object(oe, "OPENAI_API_KEY", "clave-ficticia-de-prueba"), \
                mock.patch.object(oe, "OPENAI_BASE_URL", base_url), \
                mock.patch.object(oe, "OPENAI_MODEL", modelo):
            with mock.patch.object(oe.requests, "post", return_value=respuesta_falsa(respuesta_chat())) as post:
                oe.consultar_llm("sistema", "usuario", json_mode=False, max_tokens=260)
        return post.call_args.kwargs["json"]

    def test_otro_modelo_en_openrouter_conserva_presupuesto_y_no_desactiva_razonamiento(self):
        payload = self._payload(URL_OPENROUTER, "otro/modelo:free")
        self.assertNotIn("reasoning", payload)
        self.assertEqual(4096, payload["max_tokens"])

    def test_nemotron_fuera_de_openrouter_no_recibe_override_de_razonamiento(self):
        for base_url in (URL_GROQ, "https://api.openai.com/v1", "http://localhost:1234/v1"):
            with self.subTest(base_url=base_url):
                payload = self._payload(base_url, MODELO_NEMOTRON)
                self.assertNotIn("reasoning", payload)
                self.assertEqual(260, payload["max_tokens"])

    def test_otro_proveedor_compatible_conserva_payload_y_presupuesto(self):
        with mock.patch.object(oe, "LLM_PROVIDER", "openai"), \
                mock.patch.object(oe, "OPENAI_API_KEY", "clave-ficticia-de-prueba"), \
                mock.patch.object(oe, "OPENAI_BASE_URL", URL_GROQ), \
                mock.patch.object(oe, "OPENAI_MODEL", "llama-3.1-8b-instant"):
            with mock.patch.object(oe.requests, "post", return_value=respuesta_falsa(respuesta_chat())) as post:
                resultado = oe.consultar_llm("sistema", "usuario", json_mode=True, max_tokens=768)
        payload = post.call_args.kwargs["json"]
        self.assertEqual("texto de respuesta", resultado)
        self.assertEqual(768, payload["max_tokens"])
        self.assertEqual("llama-3.1-8b-instant", payload["model"])
        self.assertEqual(0.1, payload["temperature"])
        self.assertEqual({"type": "json_object"}, payload["response_format"])
        self.assertNotIn("reasoning", payload)
        self.assertEqual(URL_GROQ + "/chat/completions", post.call_args.args[0])
        self.assertEqual(60, post.call_args.kwargs["timeout"])


class ClienteNvidiaTest(unittest.TestCase):
    """El razonamiento de NVIDIA se apaga solo con host y modelo exactos."""

    def _consultar(self, base_url=URL_NVIDIA, modelo=MODELO_NVIDIA, **kwargs):
        with mock.patch.object(oe, "LLM_PROVIDER", "openai"), \
                mock.patch.object(oe, "OPENAI_API_KEY", "clave-ficticia-de-prueba"), \
                mock.patch.object(oe, "OPENAI_BASE_URL", base_url), \
                mock.patch.object(oe, "OPENAI_MODEL", modelo):
            with mock.patch.object(oe.requests, "post",
                                   return_value=respuesta_falsa(respuesta_chat(content="  dictamen  "))) as post:
                resultado = oe.consultar_llm("sistema de prueba", "contenido de usuario", **kwargs)
        return resultado, post.call_args

    def test_nemotron_nvidia_desactiva_razonamiento_con_chat_template_kwargs(self):
        resultado, llamada = self._consultar(json_mode=False, max_tokens=1024)
        self.assertEqual("dictamen", resultado)
        payload = llamada.kwargs["json"]
        self.assertEqual(MODELO_NVIDIA, payload["model"])
        self.assertEqual(0.1, payload["temperature"])
        self.assertEqual(1024, payload["max_tokens"])
        self.assertEqual({"enable_thinking": False}, payload["chat_template_kwargs"])
        self.assertNotIn("reasoning", payload)
        self.assertNotIn("response_format", payload)
        self.assertEqual([
            {"role": "system", "content": "sistema de prueba"},
            {"role": "user", "content": "contenido de usuario"},
        ], payload["messages"])
        self.assertTrue(llamada.kwargs["headers"]["Authorization"].startswith("Bearer "))
        self.assertEqual(URL_NVIDIA + "/chat/completions", llamada.args[0])
        self.assertEqual(60, llamada.kwargs["timeout"])

    def test_nemotron_nvidia_conserva_los_presupuestos_de_los_llamadores(self):
        for pedido in (220, 300, 768, 1024, 4096):
            with self.subTest(pedido=pedido):
                _, llamada = self._consultar(max_tokens=pedido)
                self.assertEqual(pedido, llamada.kwargs["json"]["max_tokens"])

    def test_otro_modelo_en_nvidia_no_recibe_chat_template_kwargs(self):
        for modelo in (MODELO_NEMOTRON, "meta/llama-3.1-70b-instruct", MODELO_NVIDIA + "-otro"):
            with self.subTest(modelo=modelo):
                _, llamada = self._consultar(modelo=modelo)
                self.assertNotIn("chat_template_kwargs", llamada.kwargs["json"])

    def test_nemotron_nvidia_fuera_del_host_nvidia_no_recibe_chat_template_kwargs(self):
        for base_url in (URL_OPENROUTER, URL_GROQ, "https://api.openai.com/v1", "http://localhost:1234/v1"):
            with self.subTest(base_url=base_url):
                _, llamada = self._consultar(base_url=base_url)
                payload = llamada.kwargs["json"]
                self.assertNotIn("chat_template_kwargs", payload)
                self.assertNotIn("reasoning", payload)

    def test_host_enganoso_con_sufijo_o_prefijo_no_coincide(self):
        for base_url in ("https://integrate.api.nvidia.com.invalid/v1",
                         "https://integrate.api.nvidia.com.evil.example/v1",
                         "https://evil.example/integrate.api.nvidia.com/v1",
                         "https://api.nvidia.com/v1"):
            with self.subTest(base_url=base_url):
                _, llamada = self._consultar(base_url=base_url)
                self.assertNotIn("chat_template_kwargs", llamada.kwargs["json"])


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
