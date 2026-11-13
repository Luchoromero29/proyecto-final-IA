#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ejecutor real de los casos críticos de publicaciones EvalTIC (S2, S3, S4, S7).

Sin `--ejecutar` solo lista el corpus: no importa el motor, no lee el `.env`, no usa
la red ni Neo4j. Con `--ejecutar` llama de verdad al pipeline (LLM del `.env` + Neo4j)
para cada caso elegido, en serie y sin reintentos de transporte, y compara lo
observado con la expectativa de contrato del corpus.

Antes de gastar tokens corré `--verificar`: comprueba el proveedor LLM configurado,
la conexión a Neo4j, los criterios y costos, y el catálogo PG3. No comprueba que el
proveedor remoto responda.

Uso, desde la raíz del repositorio:
    python scripts/probar_publicaciones.py                      # lista los casos
    python scripts/probar_publicaciones.py --verificar          # chequeo previo
    python scripts/probar_publicaciones.py --caso PC-01 --ejecutar
    python scripts/probar_publicaciones.py --ejecutar           # todos (consume tokens)

Códigos de salida: 0 sin fallas, 1 algún caso no cumple, 2 infraestructura o uso.

Privacidad: la salida y el error del motor se capturan y se descartan (pueden traer
texto del proveedor) y de las URLs configuradas solo se muestra el host. Este módulo
es también la única fuente del verificador de expectativas que usan las pruebas.
"""

import argparse
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from urllib.parse import urlparse

RAIZ = Path(__file__).resolve().parents[1]
APP_DIR = RAIZ / "app"
CORPUS_PATH = APP_DIR / "tests" / "casos_publicaciones.json"
FALTA_CATALOGO = "Base de conocimiento incompleta"
MARCAS_INFRA = ("[ERROR CONFIGURACIÓN]", "[ERROR CRÍTICO", "[ERROR API REMOTA]",
                "[ERROR OLLAMA]", "[ERROR INFERENCIA NEO4J]", "[ERROR BASE DE CONOCIMIENTO]")
TIPOS_RESULTADO = ("error", "pendiente", "decision", "fuera_de_dominio", "flujo")
EN_DOMINIO = ("Comprar", "ComprarConOfertaMenor", "DescartarPorRiesgo", "DescartarPorInviabilidad")
CLAVES_ESPERA = frozenset({
    "resultado", "error_contiene", "error_ausente", "decision", "decision_en", "regla",
    "motivo_contiene", "estado_decision", "plan_incluye", "plan_excluye", "costo_total",
    "vma", "ram_tasada_gb", "sm2_estado", "sm2_procesador", "dato_faltante_contiene",
    "datos_inferidos_contiene", "datos_pendientes_contiene", "precio_extraido",
    "procesador_extraido", "anio_extraido", "fallas", "sin_secciones", "intencion",
    "intencion_en", "respuesta_contiene", "enrutamiento_origen_contiene",
    "si_tasado_procesador_contiene",
})


def cargar_corpus():
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["casos"]


def validar_espera(espera):
    """Rechaza claves y tipos desconocidos: una expectativa no puede ignorarse en silencio."""
    if not isinstance(espera, dict):
        raise ValueError("la expectativa debe ser un objeto")
    desconocidas = sorted(set(espera) - CLAVES_ESPERA)
    if desconocidas:
        raise ValueError(f"claves de expectativa desconocidas: {', '.join(desconocidas)}")
    tipo = espera.get("resultado")
    if tipo is not None and tipo not in TIPOS_RESULTADO:
        raise ValueError(f"tipo de resultado desconocido: {tipo!r}")
    for clave in ("plan_incluye", "plan_excluye", "sin_secciones", "decision_en", "intencion_en"):
        if clave in espera and not isinstance(espera[clave], list):
            raise ValueError(f"'{clave}' debe ser una lista")


def _comprobar(resultado, espera):
    """Verifica una expectativa completa; única fuente para el ejecutor y las pruebas."""
    validar_espera(espera)
    sm1 = resultado.get("sm1_tecnico") or (resultado if resultado.get("submodulo") == "SM1" else {})
    sm2 = resultado.get("sm2_comercial") or (resultado if resultado.get("submodulo") == "SM2" else {})
    sm3 = resultado.get("sm3_financiero") or {}
    datos = resultado.get("datos_extraidos") or {}
    traza = resultado.get("traza") or {}
    tareas = " ".join(str(p.get("tarea", "")) for p in sm1.get("plan_reparacion") or []).lower()
    decision = sm3.get("decision")
    fallos = []

    def exigir(condicion, detalle):
        if not condicion:
            fallos.append(detalle)

    tipo = espera.get("resultado")
    if tipo == "error":
        exigir(bool(resultado.get("error")), "se esperaba un rechazo en la clave 'error'")
    elif tipo == "pendiente":
        exigir(decision == "VerificacionPendiente", f"se esperaba VerificacionPendiente y fue {decision!r}")
    elif tipo == "fuera_de_dominio":
        exigir(resultado.get("intencion") == "fuera_de_dominio", f"intención {resultado.get('intencion')!r}")
    if tipo == "decision":
        exigir(bool(decision), "se esperaba una decisión de SM3 y no hubo")
        if "decision" not in espera and "decision_en" not in espera:
            exigir(decision in EN_DOMINIO, f"se esperaba una decisión del dominio y fue {decision!r}")
    if "decision" in espera:
        exigir(decision == espera["decision"], f"decisión {decision!r} != {espera['decision']!r}")
    elif "decision_en" in espera:
        exigir(decision in espera["decision_en"], f"decisión {decision!r} fuera de {espera['decision_en']}")
    if "error_contiene" in espera:
        exigir(espera["error_contiene"] in str(resultado.get("error") or ""),
               f"el error no contiene {espera['error_contiene']!r}")
    if espera.get("error_ausente"):
        exigir(not resultado.get("error"), "no se esperaba un rechazo de entrada")
    if "regla" in espera:
        exigir(sm3.get("regla_aplicada") == espera["regla"], f"regla {sm3.get('regla_aplicada')!r}")
    if "motivo_contiene" in espera:
        exigir(espera["motivo_contiene"].lower() in str(sm3.get("motivo") or "").lower(),
               f"el motivo no menciona {espera['motivo_contiene']!r}")
    if "estado_decision" in espera:
        exigir(sm3.get("estado_decision") == espera["estado_decision"], f"estado {sm3.get('estado_decision')!r}")
    for tarea in espera.get("plan_incluye", []):
        exigir(tarea.lower() in tareas, f"el plan no incluye {tarea!r}")
    for tarea in espera.get("plan_excluye", []):
        exigir(tarea.lower() not in tareas, f"el plan incluye {tarea!r} y no debía")
    if "costo_total" in espera:
        exigir(sm1.get("costo_total") == espera["costo_total"], f"costo {sm1.get('costo_total')!r}")
    if "vma" in espera:
        exigir(sm2.get("vma_estimado_ars") == espera["vma"], f"VMA {sm2.get('vma_estimado_ars')!r}")
    if "ram_tasada_gb" in espera:
        exigir(sm2.get("ram_tasada_gb") == espera["ram_tasada_gb"], f"RAM tasada {sm2.get('ram_tasada_gb')!r}")
    if "sm2_estado" in espera:
        exigir(sm2.get("estado") == espera["sm2_estado"], f"estado SM2 {sm2.get('estado')!r}")
    if "sm2_procesador" in espera:
        exigir(sm2.get("procesador") == espera["sm2_procesador"], f"procesador tasado {sm2.get('procesador')!r}")
    if "si_tasado_procesador_contiene" in espera and sm2.get("estado") == "Tasado":
        exigir(espera["si_tasado_procesador_contiene"].lower() in str(sm2.get("procesador") or "").lower(),
               f"se tasó {sm2.get('procesador')!r} y no el componente del aviso")
    if "dato_faltante_contiene" in espera:
        exigir(espera["dato_faltante_contiene"] in str(sm2.get("dato_faltante") or ""),
               f"dato faltante {sm2.get('dato_faltante')!r}")
    if "datos_inferidos_contiene" in espera:
        exigir(any(espera["datos_inferidos_contiene"] in str(d) for d in traza.get("datos_inferidos") or []),
               "no se registró el dato inferido esperado")
    if "datos_pendientes_contiene" in espera:
        exigir(any(espera["datos_pendientes_contiene"] in str(d) for d in traza.get("datos_pendientes") or []),
               "no se registró el dato pendiente esperado")
    if "precio_extraido" in espera:
        exigir(datos.get("precio_publicado") == espera["precio_extraido"],
               f"precio extraído {datos.get('precio_publicado')!r}")
    if "procesador_extraido" in espera:
        exigir(datos.get("procesador") == espera["procesador_extraido"],
               f"procesador extraído {datos.get('procesador')!r}")
    if "anio_extraido" in espera:
        exigir(datos.get("anio_fabricacion") == espera["anio_extraido"],
               f"año extraído {datos.get('anio_fabricacion')!r}")
    if "fallas" in espera:
        exigir(resultado.get("fallas_detectadas") == espera["fallas"],
               f"fallas {resultado.get('fallas_detectadas')!r}")
    for seccion in espera.get("sin_secciones", []):
        exigir(seccion not in resultado, f"no debía existir la sección {seccion!r}")
    if "intencion" in espera:
        exigir(resultado.get("intencion") == espera["intencion"], f"intención {resultado.get('intencion')!r}")
    if "intencion_en" in espera:
        exigir(resultado.get("intencion") in espera["intencion_en"],
               f"intención {resultado.get('intencion')!r} fuera de {espera['intencion_en']}")
    if "respuesta_contiene" in espera:
        exigir(espera["respuesta_contiene"].lower() in str(resultado.get("respuesta") or "").lower(),
               "la respuesta no contiene el texto esperado")
    if "enrutamiento_origen_contiene" in espera:
        origen = str((resultado.get("enrutamiento") or {}).get("origen") or "")
        exigir(espera["enrutamiento_origen_contiene"].lower() in origen.lower(),
               f"origen de enrutamiento {origen!r}")
    return fallos


def _resumen(resultado):
    """Resumen estructurado y acotado de lo observado (sin texto libre del proveedor)."""
    if resultado.get("error"):
        return f"rechazo: {str(resultado['error'])[:150]}"
    if resultado.get("intencion") == "fuera_de_dominio":
        return "fuera_de_dominio"
    sm1 = resultado.get("sm1_tecnico") or resultado
    sm2 = resultado.get("sm2_comercial") or resultado
    sm3 = resultado.get("sm3_financiero") or {}
    return (f"decisión={sm3.get('decision')} regla={sm3.get('regla_aplicada')} "
            f"estado={sm3.get('estado_decision')} costo={sm1.get('costo_total')} "
            f"vma={sm2.get('vma_estimado_ars')}")


def _host(valor):
    """Solo el host: las URLs configuradas pueden llevar usuario, clave o query."""
    host = urlparse(str(valor or "")).hostname
    return host or "host-no-configurado"


def listar(casos):
    print("Casos críticos de publicaciones (no se ejecutó nada: falta --ejecutar)\n")
    print(f"{'ID':<7}{'GRUPO':<13}{'CLASIFICACIÓN':<18}TÍTULO")
    for caso in casos:
        print(f"{caso['id']:<7}{caso['grupo']:<13}{caso['clasificacion']:<18}{caso['titulo']}")
    pruebas = [c for c in casos if c["clasificacion"] != "sonda"]
    print(f"\nTotal: {len(casos)} casos ({len(pruebas)} con expectativa automática, "
          f"{len(casos) - len(pruebas)} sondas de observación).")
    print(f"Empezá por uno solo: python scripts/probar_publicaciones.py --caso {casos[0]['id']} --ejecutar")


def _preflight(oe):
    """Verifica configuración, Neo4j y catálogo PG3 una sola vez. Devuelve 0 o 2."""
    if oe.LLM_PROVIDER not in ("ollama", "openai"):
        print(f"[INFRA] Proveedor LLM desconocido en el .env: {oe.LLM_PROVIDER!r}")
        return 2
    if oe.LLM_PROVIDER == "openai" and not oe.OPENAI_API_KEY:
        print("[INFRA] Falta la clave del proveedor openai en el .env.")
        return 2
    try:
        driver = oe.obtener_driver_neo4j()
        oe.cargar_conocimiento(forzar=True)
    except Exception as exc:  # solo la clase: el mensaje puede traer datos del entorno
        print(f"[INFRA] Neo4j o base de conocimiento no disponibles: {type(exc).__name__}")
        print("Revisá que Neo4j esté levantado y que la base tenga criterios y costos.")
        return 2
    try:
        with driver.session(database=oe.NEO4J_DATABASE) as sesion:
            fila = sesion.run(
                "OPTIONAL MATCH (p:Procesador) "
                "WITH count(p) AS procesadores, count(p.valor_ref_ars) AS calibrados "
                "OPTIONAL MATCH (l:Linea) WITH procesadores, calibrados, count(l) AS lineas "
                "OPTIONAL MATCH (r:CapacidadRAM) "
                "RETURN procesadores, calibrados, lineas, count(r) AS rams"
            ).single()
    except Exception as exc:
        print(f"[INFRA] No se pudo consultar el catálogo del grafo: {type(exc).__name__}")
        return 2
    procesadores, calibrados = int(fila["procesadores"]), int(fila["calibrados"])
    lineas, rams = int(fila["lineas"]), int(fila["rams"])
    print(f"Catálogo PG3: Procesador={procesadores} (con precio={calibrados}) · "
          f"Linea={lineas} · CapacidadRAM={rams}")
    if procesadores == 0 or lineas == 0 or rams == 0 or calibrados == 0:
        print("[INFRA] Falta el catálogo PG3 calibrado: sin él toda publicación termina en")
        print("        ConocimientoFaltante y no tiene sentido gastar tokens.")
        print("        No cargues el grafo automáticamente: mirá la sección «Carga del grafo»")
        print("        del README y usá una base dedicada con respaldo, porque el script de")
        print("        carga del PG2 borra los datos existentes.")
        print("        No se ejecutó ningún caso.")
        return 2
    return 0


def _ejecutar_caso(oe, caso):
    """Llama al punto de entrada público del caso, descartando stdout y stderr del motor."""
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        if caso.get("via") == "integral":
            return oe.evaluar_publicacion_integral(caso["entrada"], verbose=False)
        return oe.asistente_evaltic(caso["entrada"], verbose=False)


def _es_infra_excepcion(exc):
    if isinstance(exc, (ConnectionError, TimeoutError, ImportError)):
        return True
    return any(marca in str(exc) for marca in MARCAS_INFRA)


def _categoria_excepcion(exc):
    """Etiqueta de una lista cerrada; nunca imprime el mensaje ni el cuerpo privado."""
    marcas = MARCAS_INFRA + ("[ERROR RESPUESTA LLM]", "[ERROR PARSEO]")
    for marca in marcas:
        if marca in str(exc):
            return marca.strip("[]").replace("ERROR ", "").replace(" ", "_")
    return "CONEXION" if isinstance(exc, (ConnectionError, TimeoutError)) else "SIN_MARCA"


def _es_infra_conocimiento(resultado, espera):
    """Un error de base de conocimiento es infraestructura salvo que el caso lo prevea."""
    error = str(resultado.get("error") or "")
    if FALTA_CATALOGO not in error:
        return False
    esperado = str(espera.get("error_contiene") or "")
    return not (esperado and esperado in error)


def ejecutar(seleccion, solo_verificar):
    sys.path.insert(0, str(APP_DIR))
    import orquestador_evaltic as oe

    if oe.LLM_PROVIDER == "openai":
        llm = f"LLM configurado: openai · modelo {oe.OPENAI_MODEL} · host {_host(oe.OPENAI_BASE_URL)}"
    else:
        llm = f"LLM configurado: {oe.LLM_PROVIDER} · modelo {oe.OLLAMA_MODEL} · host {_host(oe.OLLAMA_URL)}"
    print("EvalTIC · casos críticos de publicaciones")
    print(llm)
    print(f"Neo4j: {oe.TIPO_INSTANCIA} · host {_host(oe.NEO4J_URI)}")
    print("El chequeo previo valida la configuración, no la disponibilidad remota del proveedor.\n")

    for caso in seleccion:
        if caso["clasificacion"] == "sonda":
            continue
        try:
            validar_espera(caso["espera"])
        except (KeyError, ValueError) as exc:
            print(f"[USO] Expectativa inválida en {caso.get('id')}: {exc}")
            return 2

    codigo = _preflight(oe)
    if codigo != 0:
        return codigo
    if solo_verificar:
        print("\nServicios listos. No se ejecutó ningún caso (--verificar).")
        return 0

    cumplidos, fallidos, infra, sondas, completados = [], [], [], [], 0
    for caso in seleccion:
        print(f"\n[{caso['id']}] {caso['titulo']}  ({caso['grupo']} · {caso['clasificacion']})")
        print(f"  entrada: {caso['entrada']}")
        try:
            resultado = _ejecutar_caso(oe, caso)
        except Exception as exc:  # clase solamente: el texto puede traer datos del proveedor
            if _es_infra_excepcion(exc):
                print(f"  [INFRA] No se pudo ejecutar el caso: {type(exc).__name__} "
                      f"(categoría: {_categoria_excepcion(exc)})")
                infra.append(caso["id"])
            else:
                print(f"  [FALLO] Excepción inesperada: {type(exc).__name__} "
                      f"(categoría: {_categoria_excepcion(exc)})")
                fallidos.append(caso["id"])
            continue
        if _es_infra_conocimiento(resultado, caso.get("espera") or {}):
            print("  [INFRA] El motor devolvió un error de base de conocimiento; no cuenta como rechazo.")
            infra.append(caso["id"])
            continue
        completados += 1
        print(f"  observado: {_resumen(resultado)}")
        if caso["clasificacion"] == "sonda":
            print(f"  SONDA (sin expectativa automática): {caso['sonda']}")
            sondas.append(caso["id"])
            continue
        print(f"  esperado: {json.dumps(caso['espera'], ensure_ascii=False)}")
        incumplimientos = _comprobar(resultado, caso["espera"])
        if incumplimientos:
            for detalle in incumplimientos:
                print(f"  ✘ {detalle}")
            fallidos.append(caso["id"])
        else:
            print("  ✔ cumple la expectativa")
            cumplidos.append(caso["id"])

    print("\n" + "=" * 72)
    print(f"Casos intentados: {len(seleccion)} · completados: {completados} · "
          f"cumplen: {len(cumplidos)} · fallan: {len(fallidos)} · sondas: {len(sondas)} · "
          f"infra: {len(infra)}")
    if fallidos:
        print("No cumplen la expectativa: " + ", ".join(fallidos))
    if sondas:
        print("Sondas para revisar a mano: " + ", ".join(sondas))
    if infra:
        print("Casos con error de infraestructura: " + ", ".join(infra))
    print("Las sondas y los errores de infraestructura no se marcan como aprobados.")
    return 2 if infra else (1 if fallidos else 0)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Corre los casos críticos de publicaciones de EvalTIC. Sin --ejecutar solo lista el corpus.",
        epilog=("Servicios necesarios para --ejecutar: Neo4j con el catálogo PG3 cargado (Procesador, Linea, "
                "CapacidadRAM) y el proveedor LLM configurado en el .env. --verificar comprueba la configuración "
                "y el grafo, no que el proveedor remoto responda. Cada caso puede hacer varias llamadas al modelo "
                "(enrutador y extracción con reintentos de parseo, redacción), en serie. Los errores muestran "
                "sólo clase y categoría, nunca el cuerpo privado. Sin reintentos de "
                "transporte: 61 casos consumen cuota real del proveedor. Empezá por --verificar y por un --caso."))
    parser.add_argument("--ejecutar", action="store_true",
                        help="llama de verdad al pipeline (LLM + Neo4j); consume tokens y tiempo")
    parser.add_argument("--caso", action="append", default=[], metavar="ID",
                        help="restringe la ejecución a este caso; se puede repetir (ej. --caso PC-01)")
    parser.add_argument("--verificar", action="store_true",
                        help="solo verifica configuración, Neo4j y catálogo PG3; no llama al LLM")
    args = parser.parse_args(argv)

    casos = cargar_corpus()
    por_id = {caso["id"]: caso for caso in casos}
    desconocidos = [ident for ident in args.caso if ident not in por_id]
    if desconocidos:
        print(f"[USO] IDs desconocidos: {', '.join(desconocidos)}")
        print("IDs válidos: " + ", ".join(por_id))
        return 2
    seleccion = [por_id[ident] for ident in args.caso] or casos
    if not args.ejecutar and not args.verificar:
        listar(casos)
        return 0
    return ejecutar(seleccion, solo_verificar=args.verificar)


if __name__ == "__main__":
    sys.exit(main())
