#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aplicación controlada de P2a (acciones de SM1) sobre el Neo4j AISLADO de pruebas.

Este cargador NO es el procedimiento de despliegue ni migra la base original: sólo aplica
`cypher/Grupo_20_PG3_politicas_sm1_acciones.cypher` al scratch marcado
`(:EntornoPruebas {id:'mejoras-evaltic'})` en bolt://127.0.0.1:17687, base `neo4j`, sin
autenticación y sin leer `.env` ni importar la aplicación.

Guarda, en este orden y sin escribir nada hasta pasar todas:
  1. endpoint/base/marcador exactos (una sola instancia del marcador);
  2. proyección protegida vigente: la foto P0 guardada más las nueve propiedades de P1;
  3. identidades y cardinalidades esperadas (reglas, costos, criterios y OBLIGA) y ninguna
     configuración ajena ni conflictiva;
  4. aplicación del artefacto en una transacción explícita y validación del delta EXACTO
     permitido antes de confirmar;
  5. segunda aplicación: cero delta, y nada cambia en la proyección.

La vista protegida se obtiene retirando SÓLO las piezas que este corte posee (manifiesto,
condiciones, sus relaciones y las dos propiedades nuevas de OBLIGA); no se ignora metadato
ajeno. Evidencia en `docs/ejecuciones/politicas_p2a_carga.json` y `..._carga.log`.

Uso:  PYTHONDONTWRITEBYTECODE=1 /home/alvaro/Universidad/IA/Proyecto/.venv/bin/python \
          scripts/aplicar_politicas_sm1_pruebas.py
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import neo4j

RAIZ = Path(__file__).resolve().parents[1]
ARTEFACTO = RAIZ / "cypher/Grupo_20_PG3_politicas_sm1_acciones.cypher"
PROTEGIDO = RAIZ / "_respaldo_original/politicas-p0-80654c9/grafo_protegido.json"
SHA_PROTEGIDO = "d3bff60e62990562ccca493ce95840d731f788b4a606f5412d9bff0dd23d6fc4"
EVIDENCIA_JSON = RAIZ / "docs/ejecuciones/politicas_p2a_carga.json"
EVIDENCIA_LOG = RAIZ / "docs/ejecuciones/politicas_p2a_carga.log"

URI = "bolt://127.0.0.1:17687"
BASE_DATOS = "neo4j"
MARCADOR = "mejoras-evaltic"

VERSION = "politicas-SM1-acciones-v1"
ETAPA = "SM1-acciones"
ID_MANIFIESTO = "VP-SM1-ACCIONES"
REGLAS = ["SM1-BAT-CRISP", "SM1-TER-CRISP", "SM1-RAM-ACCION", "SM1-DISCO-ACCION",
          "SM1-PANTALLA-ACCION", "SM1-TECLADO-ACCION", "SM1-CARGADOR-ACCION",
          "SM1-MANO-OBRA-ACCION"]
# Condiciones poseídas por este corte: (regla, condición, grupo, propiedades, criterio).
CONDICIONES = [
    ("SM1-BAT-CRISP", "CND-SM1-BAT-CRISP-SALUD", 1,
     {"campo": "salud", "ambito": "hechos", "operador": "<"}, "CE-01"),
    ("SM1-BAT-CRISP", "CND-SM1-BAT-CRISP-CICLOS", 2,
     {"campo": "ciclos", "ambito": "hechos", "operador": "ausente"}, None),
    ("SM1-TER-CRISP", "CND-SM1-TER-CRISP-TEMP", 1,
     {"campo": "temp", "ambito": "hechos", "operador": "ausente"}, None),
    ("SM1-TER-CRISP", "CND-SM1-TER-CRISP-THROTTLING", 2,
     {"campo": "throttling", "ambito": "hechos", "operador": "=", "valor": True}, None),
    ("SM1-RAM-ACCION", "CND-SM1-RAM-ACCION-RAM", 1,
     {"campo": "ram", "ambito": "hechos", "operador": "<"}, "CE-27"),
    ("SM1-DISCO-ACCION", "CND-SM1-DISCO-ACCION-DISCO", 1,
     {"campo": "disco", "ambito": "hechos", "operador": "=", "valor": "HDD"}, None),
    ("SM1-PANTALLA-ACCION", "CND-SM1-PANTALLA-ACCION", 1,
     {"campo": "pantalla_danada", "ambito": "campos", "operador": "=", "valor": True}, None),
    ("SM1-TECLADO-ACCION", "CND-SM1-TECLADO-ACCION", 1,
     {"campo": "teclado_danado", "ambito": "campos", "operador": "=", "valor": True}, None),
    ("SM1-CARGADOR-ACCION", "CND-SM1-CARGADOR-ACCION", 1,
     {"campo": "cargador_incluido", "ambito": "campos", "operador": "=", "valor": False}, None),
]
OBLIGA = {"SM1-BAT": ("categoria_bat", 5), "SM1-TER": ("categoria_ter", 6)}
P1 = {"Conveniencia.Comprar": ("Comprar", False),
      "Conveniencia.Negociar": ("ComprarConOfertaMenor", True),
      "Conveniencia.Descartar": ("DescartarPorRiesgo", False)}

CONSULTA_PROYECCION = """
CALL () {
  MATCH (n) RETURN collect({id: elementId(n), etiquetas: labels(n),
                            propiedades: properties(n)}) AS nodos
}
CALL () {
  MATCH ()-[r]->() RETURN collect({id: elementId(r), tipo: type(r), propiedades: properties(r),
                                   origen: elementId(startNode(r)),
                                   destino: elementId(endNode(r))}) AS relaciones
}
RETURN nodos, relaciones
"""


class CargaRechazada(Exception):
    """La precondición no se cumple: no se escribe nada."""


def canonico(valor) -> str:
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def proyeccion(sesion):
    """Proyección completa y ordenada del grafo: nodos, relaciones y restricciones."""
    fila = sesion.run(CONSULTA_PROYECCION).single(strict=True)
    nodos = sorted(({"etiquetas": sorted(n["etiquetas"]), "id": n["id"],
                     "propiedades": n["propiedades"]} for n in fila["nodos"]), key=lambda n: n["id"])
    relaciones = sorted(({"destino": r["destino"], "id": r["id"], "origen": r["origen"],
                          "propiedades": r["propiedades"], "tipo": r["tipo"]}
                         for r in fila["relaciones"]), key=lambda r: r["id"])
    restricciones = sorted(({"entityType": r["entityType"], "labelsOrTypes": r["labelsOrTypes"],
                             "name": r["name"], "properties": r["properties"], "type": r["type"]}
                            for r in sesion.run("SHOW CONSTRAINTS")), key=lambda r: r["name"])
    return {"nodos": nodos, "relaciones": relaciones, "restricciones": restricciones}


def _ids_protegidos():
    return {condicion for _, condicion, _, _, _ in CONDICIONES}


def vista_protegida(proy, obligas):
    """Retira SÓLO lo que posee P2a; el resto de la proyección se compara tal cual."""
    poseidos = _ids_protegidos() | {ID_MANIFIESTO}
    elementos_poseidos = {n["id"] for n in proy["nodos"] if n["propiedades"].get("id") in poseidos}
    nodos = [{"etiquetas": n["etiquetas"], "id": n["id"], "propiedades": n["propiedades"]}
             for n in proy["nodos"] if n["propiedades"].get("id") not in poseidos]
    relaciones = []
    for r in proy["relaciones"]:
        if r["origen"] in elementos_poseidos or r["destino"] in elementos_poseidos:
            continue
        propiedades = r["propiedades"]
        if r["id"] in obligas:
            propiedades = {k: v for k, v in propiedades.items() if k not in ("etapa", "campo")}
        relaciones.append({**r, "propiedades": propiedades})
    return {"nodos": nodos, "relaciones": relaciones, "restricciones": proy["restricciones"]}


def proyeccion_esperada(protegido):
    """Foto P0 guardada más las nueve propiedades que agregó P1 (P1, no P2a)."""
    esperado = json.loads(json.dumps(protegido))
    for nodo in esperado["nodos"]:
        clave = nodo["propiedades"].get("id")
        if clave in P1:
            nodo["propiedades"]["resultado_decision"] = P1[clave][0]
            nodo["propiedades"]["contraoferta_habilitada"] = P1[clave][1]
            nodo["propiedades"]["representacion_version"] = "politicas-P1-v1"
    esperado["restricciones"] = sorted(
        ({k: r[k] for k in ("entityType", "labelsOrTypes", "name", "properties", "type")}
         for r in esperado["restricciones"]), key=lambda r: r["name"])
    return esperado


def _obligas(sesion):
    """Relaciones OBLIGA de las bases de SM1: son las únicas que este corte vincula."""
    filas = [dict(f) for f in sesion.run(
        "MATCH (rd:ReglaDifusa)-[ob:OBLIGA]->(c:CostoReparacion) "
        "RETURN elementId(ob) AS id, rd.base AS base, rd.id AS regla, c.tarea AS tarea, "
        "properties(ob) AS propiedades ORDER BY id")]
    return filas


def preflight(sesion, obligas_antes):
    """Identidades, cardinalidades y conflictos esperados; sólo lectura."""
    problemas = []
    marcador = sesion.run("MATCH (m:EntornoPruebas {id: $id}) RETURN count(m) AS n", id=MARCADOR).single(strict=True)
    if marcador["n"] != 1:
        problemas.append(f"el grafo de {URI} no tiene exactamente un marcador EntornoPruebas '{MARCADOR}'")
    for id_regla in REGLAS:
        fila = sesion.run(
            "MATCH (r:Regla {id: $id}) OPTIONAL MATCH (r)-[:ORDENA]->(c:CostoReparacion) "
            "RETURN count(DISTINCT r) AS reglas, count(DISTINCT c) AS costos",
            id=id_regla).single(strict=True)
        if (fila["reglas"], fila["costos"]) != (1, 1):
            problemas.append(f"la regla {id_regla} debe existir una vez y ordenar un costo "
                             f"(encontradas {fila['reglas']} reglas, {fila['costos']} costos)")
    for id_condicion, id_criterio in [(c[1], c[4]) for c in CONDICIONES if c[4]]:
        fila = sesion.run(
            "MATCH (ce:CriterioExperto {id: $id}) RETURN count(ce) AS n, collect(ce.valor) AS valores",
            id=id_criterio).single(strict=True)
        if fila["n"] != 1 or not fila["valores"] or not isinstance(fila["valores"][0], (int, float)):
            problemas.append(f"la condición {id_condicion} referencia un criterio ausente o no numérico: {id_criterio}")
    bases = {}
    for fila in obligas_antes:
        bases.setdefault(fila["base"], []).append(fila)
        if not fila["propiedades"].get("categorias"):
            problemas.append(f"la obligación {fila['id']} no declara categorías")
    for base, (campo, esperadas) in OBLIGA.items():
        encontradas = bases.get(base, [])
        if len(encontradas) != esperadas:
            problemas.append(f"la base {base} tiene {len(encontradas)} obligaciones y se esperaban {esperadas}")
        for fila in encontradas:
            etapa, previo = fila["propiedades"].get("etapa"), fila["propiedades"].get("campo")
            if etapa not in (None, ETAPA) or previo not in (None, campo):
                problemas.append(f"la obligación {fila['id']} de {base} ya tiene etapa/campo distintos")
    ajenas = sorted(fila["id"] for fila in obligas_antes if fila["base"] not in OBLIGA)
    if ajenas:
        problemas.append(f"hay obligaciones fuera de las bases de SM1: {ajenas}")
    versiones = [dict(f) for f in sesion.run(
        "MATCH (v:VersionPoliticas) RETURN v.id AS id, properties(v) AS propiedades")]
    if any(v["id"] != ID_MANIFIESTO for v in versiones):
        problemas.append(f"hay manifiestos ajenos a P2a: {[v['id'] for v in versiones]}")
    condiciones = [dict(f) for f in sesion.run(
        "MATCH (c:Condicion) RETURN c.id AS id, properties(c) AS propiedades")]
    poseidas = {condicion for _, condicion, _, _, _ in CONDICIONES}
    if any(c["id"] not in poseidas for c in condiciones):
        problemas.append(f"hay condiciones ajenas a P2a: {[c['id'] for c in condiciones if c['id'] not in poseidas]}")
    requs = [dict(f) for f in sesion.run(
        "MATCH (r:Regla)-[:REQUIERE]->(c:Condicion) RETURN r.id AS regla, c.id AS condicion")]
    if any(f["regla"] not in REGLAS or f["condicion"] not in poseidas for f in requs):
        problemas.append(f"hay relaciones REQUIERE ajenas: {requs}")
    return problemas


def delta(nodos_antes, rels_antes, proy_despues, obligas_antes, respuesta):
    """Delta exacto permitido: lo que el artefacto declara como pendiente, y nada más."""
    antes_nodos = {n["id"] for n in nodos_antes}
    antes_rels = {r["id"] for r in rels_antes}
    nuevos_nodos = [n for n in proy_despues["nodos"] if n["id"] not in antes_nodos]
    nuevos_rels = [r for r in proy_despues["relaciones"] if r["id"] not in antes_rels]
    esperados_nodos_nuevos = respuesta["manifiestos_creados"] + respuesta["condiciones_creadas"]
    esperados_rels_nuevas = (respuesta["incluye_creadas"] + respuesta["condiciones_creadas"] +
                             respuesta["criterios_enlazados"])

    def identidad(proy, element_id):
        for nodo in proy["nodos"]:
            if nodo["id"] == element_id:
                return nodo["propiedades"].get("id")
        return None

    problemas = []
    for nodo in nuevos_nodos:
        etiqueta = nodo["etiquetas"]
        clave = nodo["propiedades"].get("id")
        if etiqueta == ["Condicion"]:
            esperado = next((c for c in CONDICIONES if c[1] == clave), None)
            if esperado is None:
                problemas.append(f"condición no autorizada: {clave}")
                continue
            _, _, grupo, props, criterio = esperado
            requerido = {**props, "id": clave, "representacion_version": VERSION}
            if nodo["propiedades"] != requerido:
                problemas.append(f"la condición {clave} no coincide con lo autorizado: {nodo['propiedades']}")
        elif etiqueta == ["VersionPoliticas"]:
            if clave != ID_MANIFIESTO:
                problemas.append(f"manifiesto no autorizado: {clave}")
            else:
                requerido = {"id": ID_MANIFIESTO, "version": VERSION, "etapa": ETAPA, "activa": True,
                             "representacion_version": VERSION, "ids_requeridos": REGLAS,
                             "obligaciones_requeridas": sum(v[1] for v in OBLIGA.values())}
                if nodo["propiedades"] != requerido:
                    problemas.append(f"el manifiesto no coincide con lo autorizado: {nodo['propiedades']}")
        else:
            problemas.append(f"nodo nuevo no autorizado: {nodo['etiquetas']} {nodo['propiedades']}")
    if len(nuevos_nodos) != esperados_nodos_nuevos:
        problemas.append(f"se crearon {len(nuevos_nodos)} nodos y se esperaban {esperados_nodos_nuevos}")

    esperados_rels = {(regla, "INCLUYE", ID_MANIFIESTO) for regla in REGLAS}
    esperados_rels |= {(c[0], "REQUIERE", c[1]) for c in CONDICIONES}
    esperados_rels |= {(c[1], "USA_CRITERIO", c[4]) for c in CONDICIONES if c[4]}
    vistas = set()
    for rel in nuevos_rels:
        origen, destino = identidad(proy_despues, rel["origen"]), identidad(proy_despues, rel["destino"])
        # El manifiesto INCLUYE a la regla: se compara en el sentido declarado.
        par = (destino, rel["tipo"], origen) if rel["tipo"] == "INCLUYE" else (origen, rel["tipo"], destino)
        vistas.add(par)
        if par not in esperados_rels:
            problemas.append(f"relación nueva no autorizada: {par}")
    if len(vistas) != len(nuevos_rels):
        problemas.append("hay relaciones nuevas duplicadas")
    if len(nuevos_rels) != esperados_rels_nuevas:
        problemas.append(f"se crearon {len(nuevos_rels)} relaciones y se esperaban {esperados_rels_nuevas}")

    # Fuera de las dos propiedades de OBLIGA, ninguna entidad previa cambia.
    antes_por_id = {n["id"]: n for n in nodos_antes}
    for nodo in proy_despues["nodos"]:
        previo = antes_por_id.get(nodo["id"])
        if previo is not None and canonico(previo) != canonico(nodo):
            problemas.append(f"un nodo previo cambió: {nodo['id']}")
    rels_antes_por_id = {r["id"]: r for r in rels_antes}
    base_por_obliga = {o["id"]: o["base"] for o in obligas_antes}
    for rel in proy_despues["relaciones"]:
        previo = rels_antes_por_id.get(rel["id"])
        if previo is None:
            continue
        if rel["id"] in base_por_obliga:
            esperado = dict(previo["propiedades"])
            esperado["etapa"] = ETAPA
            esperado["campo"] = OBLIGA[base_por_obliga[rel["id"]]][0]
            if canonico(rel["propiedades"]) != canonico(esperado):
                problemas.append(f"la obligación {rel['id']} cambió fuera de etapa/campo")
        elif canonico(previo) != canonico(rel):
            problemas.append(f"una relación previa cambió: {rel['id']}")
    return problemas, {"nodos": len(nuevos_nodos), "relaciones": len(nuevos_rels),
                       "obligaciones_vinculadas": respuesta["obligaciones_vinculadas"]}


def configuracion_aplicada(sesion):
    """Lee la configuración de P2a ya aplicada y la compara con lo declarado."""
    problemas = []
    manifiesto = sesion.run("MATCH (v:VersionPoliticas {id: $id}) RETURN properties(v) AS p",
                            id=ID_MANIFIESTO).single(strict=True)
    esperado_manifiesto = {"id": ID_MANIFIESTO, "version": VERSION, "etapa": ETAPA, "activa": True,
                           "representacion_version": VERSION, "ids_requeridos": REGLAS,
                           "obligaciones_requeridas": sum(v[1] for v in OBLIGA.values())}
    if manifiesto is None or manifiesto["p"] != esperado_manifiesto:
        problemas.append("el manifiesto aplicado no coincide con lo declarado")
    condiciones = {f["id"]: f["propiedades"] for f in sesion.run(
        "MATCH (c:Condicion) RETURN c.id AS id, properties(c) AS propiedades")}
    incluye = {f["regla"]: [f["condiciones"], f["criterios"]] for f in sesion.run(
        "MATCH (:VersionPoliticas {id: $id})-[i:INCLUYE]->(r:Regla) "
        "RETURN r.id AS regla, i.condiciones AS condiciones, i.criterios AS criterios",
        id=ID_MANIFIESTO)}
    requiere = {(f["regla"], f["condicion"], f["grupo"]) for f in sesion.run(
        "MATCH (r:Regla)-[q:REQUIERE]->(c:Condicion) "
        "RETURN r.id AS regla, c.id AS condicion, q.grupo AS grupo")}
    criterios = {(f["condicion"], f["criterio"]) for f in sesion.run(
        "MATCH (c:Condicion)-[:USA_CRITERIO]->(ce:CriterioExperto) "
        "RETURN c.id AS condicion, ce.id AS criterio")}
    obligas = _obligas(sesion)
    esperadas_condiciones = {c[1]: {**c[3], "id": c[1], "representacion_version": VERSION}
                             for c in CONDICIONES}
    if condiciones != esperadas_condiciones:
        problemas.append("las condiciones aplicadas no coinciden con las declaradas")
    esperado_incluye = {regla: [sum(1 for c in CONDICIONES if c[0] == regla),
                                sum(1 for c in CONDICIONES if c[0] == regla and c[4])]
                        for regla in REGLAS}
    if incluye != esperado_incluye:
        problemas.append("las relaciones INCLUYE aplicadas no coinciden con las declaradas")
    esperado_requiere = {(c[0], c[1], c[2]) for c in CONDICIONES}
    if requiere != esperado_requiere:
        problemas.append("las relaciones REQUIERE aplicadas no coinciden con las declaradas")
    esperados_criterios = {(c[1], c[4]) for c in CONDICIONES if c[4]}
    if criterios != esperados_criterios:
        problemas.append("los vínculos USA_CRITERIO aplicados no coinciden con los declarados")
    esperadas_obligas = {o["id"]: OBLIGA[o["base"]][0] for o in obligas if o["base"] in OBLIGA}
    for obliga in obligas:
        if obliga["base"] not in OBLIGA:
            problemas.append(f"obligación fuera de las bases de SM1: {obliga['id']}")
        elif (obliga["propiedades"].get("etapa"), obliga["propiedades"].get("campo")) != (
                ETAPA, esperadas_obligas[obliga["id"]]):
            problemas.append(f"la obligación {obliga['id']} no tiene la etapa o el hecho declarados")
    return {"valida": not problemas, "problemas": problemas,
            "manifiestos": 1 if manifiesto else 0, "condiciones": len(condiciones),
            "incluye": len(incluye), "requiere": len(requiere), "criterios": len(criterios),
            "obligaciones": len(obligas), "obligaciones_vinculadas": len(esperadas_obligas)}


def _registrar(texto):
    """Agrega la corrida al log de evidencia (no borra corridas anteriores)."""
    with EVIDENCIA_LOG.open("a", encoding="utf-8") as archivo:
        archivo.write(texto + "\n")


def main() -> int:
    evidencia = {"fecha_utc": datetime.now(timezone.utc).isoformat(), "uri": URI,
                 "base_datos": BASE_DATOS, "artefacto": str(ARTEFACTO.relative_to(RAIZ)),
                 "operacion": "aplicacion_controlada_scratch"}
    try:
        if not ARTEFACTO.is_file():
            raise CargaRechazada(f"falta el artefacto {ARTEFACTO}")
        consulta = ARTEFACTO.read_text(encoding="utf-8")
        if not PROTEGIDO.is_file():
            raise CargaRechazada(f"falta la proyección protegida {PROTEGIDO}")
        texto_protegido = PROTEGIDO.read_text(encoding="utf-8")
        if sha256(texto_protegido) != SHA_PROTEGIDO:
            raise CargaRechazada("la proyección protegida no coincide con el SHA256 registrado")
        protegido = json.loads(texto_protegido)
        driver = neo4j.GraphDatabase.driver(URI, auth=None)
    except CargaRechazada as error:
        print(f"RECHAZADO: {error}")
        return 2
    try:
        driver.verify_connectivity()
    except Exception as error:  # conexión no disponible: se preserva el fallo, sin otro destino
        driver.close()
        print(f"RECHAZADO: no se pudo conectar a {URI} ({error})")
        return 3
    try:
        with driver.session(database=BASE_DATOS) as sesion:
            obligas_antes = _obligas(sesion)
            problemas = preflight(sesion, obligas_antes)
            antes = proyeccion(sesion)
            vista = vista_protegida(antes, {o["id"] for o in obligas_antes})
            esperado = proyeccion_esperada(protegido)
            evidencia.update({
                "antes": {"nodos": len(antes["nodos"]), "relaciones": len(antes["relaciones"]),
                          "restricciones": len(antes["restricciones"]),
                          "sha256_proyeccion": sha256(canonico(antes)),
                          "sha256_vista_protegida": sha256(canonico(vista))},
                "esperado": {"sha256_vista_protegida": sha256(canonico(esperado)),
                             "sha256_proteccion_p0": sha256(canonico(protegido)),
                             "p1": {clave: list(valor) for clave, valor in P1.items()}},
            })
            if canonico(vista) != canonico(esperado):
                evidencia["resultado"] = "rechazado_vista_protegida"
                raise CargaRechazada(
                    "la vista protegida del grafo no es la foto P0 más las nueve propiedades de P1")
            if problemas:
                evidencia["resultado"] = "rechazado_preflight"
                raise CargaRechazada("preflight: " + " | ".join(problemas))
            evidencia["preflight"] = "ok"

            # Aplicación 1: escritura + validación del delta dentro de la transacción.
            tx = sesion.begin_transaction()
            try:
                respuesta = dict(tx.run(consulta).single(strict=True))
                despues = proyeccion(tx)
                problemas_delta, conteo = delta(antes["nodos"], antes["relaciones"], despues,
                                                obligas_antes, respuesta)
                evidencia["aplicacion_1"] = {"respuesta": respuesta, "delta": conteo,
                                             "sha256_proyeccion": sha256(canonico(despues))}
                if not respuesta["compatible"] or respuesta["errores"]:
                    raise CargaRechazada(f"artefacto incompatible: {respuesta['errores']}")
                if problemas_delta:
                    raise CargaRechazada("delta no autorizado: " + " | ".join(problemas_delta))
                if canonico(despues["restricciones"]) != canonico(antes["restricciones"]):
                    raise CargaRechazada("las restricciones cambiaron")
                tx.commit()
            except Exception:
                tx.rollback()
                raise
            despues_confirmado = proyeccion(sesion)

            # Aplicación 2: cero delta, sin cambios en la proyección.
            tx = sesion.begin_transaction()
            try:
                segunda = dict(tx.run(consulta).single(strict=True))
                despues_segunda = proyeccion(tx)
                evidencia["aplicacion_2"] = {"respuesta": segunda,
                                             "sha256_proyeccion": sha256(canonico(despues_segunda))}
                if segunda["cambios"] != 0 or segunda["errores"] or not segunda["compatible"]:
                    raise CargaRechazada(f"la segunda aplicación no fue nula: {segunda}")
                if canonico(despues_segunda) != canonico(despues_confirmado):
                    raise CargaRechazada("la segunda aplicación cambió la proyección")
                tx.rollback()
            except Exception:
                tx.rollback()
                raise

            obligas_despues = _obligas(sesion)
            aplicada = configuracion_aplicada(sesion)
            evidencia.update({
                "resultado": "aplicado" if evidencia["aplicacion_1"]["respuesta"]["cambios"] else "ya_aplicado",
                "configuracion_aplicada": aplicada,
                "despues": {"nodos": len(despues_confirmado["nodos"]),
                            "relaciones": len(despues_confirmado["relaciones"]),
                            "restricciones": len(despues_confirmado["restricciones"]),
                            "sha256_proyeccion": sha256(canonico(despues_confirmado))},
                "obligas": {"antes": len(obligas_antes), "despues": len(obligas_despues),
                            "campos": sorted({o["propiedades"].get("campo") for o in obligas_despues})},
            })
            if not aplicada["valida"]:
                raise CargaRechazada("la configuración aplicada no coincide con la declarada: "
                                     + " | ".join(aplicada["problemas"]))
    except CargaRechazada as error:
        evidencia["resultado"] = "rechazado"
        evidencia["motivo"] = str(error)
        EVIDENCIA_JSON.write_text(json.dumps(evidencia, indent=2, ensure_ascii=False, default=str) + "\n",
                                  encoding="utf-8")
        _registrar(f"{evidencia['fecha_utc']} RECHAZADA: {error}")
        print(f"RECHAZADO: {error}")
        return 2
    finally:
        driver.close()

    EVIDENCIA_JSON.write_text(json.dumps(evidencia, indent=2, ensure_ascii=False, default=str) + "\n",
                              encoding="utf-8")
    uno = evidencia["aplicacion_1"]["respuesta"]
    _registrar(
        f"{evidencia['fecha_utc']} P2a sobre el grafo de pruebas (scratch, marcador mejoras-evaltic): "
        f"resultado={evidencia['resultado']}.\n"
        f"  Vista protegida: P0 {evidencia['esperado']['sha256_proteccion_p0']} + P1; "
        f"antes {evidencia['antes']['sha256_vista_protegida']} == "
        f"esperado {evidencia['esperado']['sha256_vista_protegida']}.\n"
        f"  Proyección antes: {evidencia['antes']['nodos']} nodos / {evidencia['antes']['relaciones']} "
        f"relaciones / {evidencia['antes']['restricciones']} restricciones.\n"
        f"  Aplicación 1: manifiestos={uno['manifiestos_creados']} incluye={uno['incluye_creadas']} "
        f"condiciones={uno['condiciones_creadas']} criterios={uno['criterios_enlazados']} "
        f"obligaciones={uno['obligaciones_vinculadas']} cambios={uno['cambios']}.\n"
        f"  Proyección después: {evidencia['despues']['nodos']} nodos / "
        f"{evidencia['despues']['relaciones']} relaciones / "
        f"{evidencia['despues']['restricciones']} restricciones; "
        f"delta nodos={evidencia['aplicacion_1']['delta']['nodos']} "
        f"relaciones={evidencia['aplicacion_1']['delta']['relaciones']}; "
        f"segunda aplicación cambios={evidencia['aplicacion_2']['respuesta']['cambios']}.\n"
        f"  Configuración aplicada: valida={evidencia['configuracion_aplicada']['valida']} "
        f"condiciones={evidencia['configuracion_aplicada']['condiciones']} "
        f"incluye={evidencia['configuracion_aplicada']['incluye']} "
        f"requiere={evidencia['configuracion_aplicada']['requiere']} "
        f"criterios={evidencia['configuracion_aplicada']['criterios']} "
        f"obligaciones={evidencia['configuracion_aplicada']['obligaciones']}.")
    print("aplicado:", json.dumps({"cambios": uno["cambios"],
                                   "delta": evidencia["aplicacion_1"]["delta"],
                                   "segunda_aplicacion": evidencia["aplicacion_2"]["respuesta"]["cambios"],
                                   "configuracion_aplicada": evidencia["configuracion_aplicada"]},
                                  ensure_ascii=False))
    return 0
    print("aplicado:", json.dumps({"cambios": uno["cambios"],
                                   "delta": evidencia["aplicacion_1"]["delta"],
                                   "segunda_aplicacion": evidencia["aplicacion_2"]["respuesta"]["cambios"]},
                                  ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
