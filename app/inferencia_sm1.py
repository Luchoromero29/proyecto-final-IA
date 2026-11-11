#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inferencia de diagnóstico de SM1 en Neo4j (B2).

Toda la resolución del dictamen técnico —precedencia entre evidencia irreversible, síntomas,
descripciones positivas e intervenciones; detección de fallas sin tratamiento; liberación por
verificación del operador; irreparabilidad; selección del estado final; armado del plan con sus
costos, total, cantidad de intervenciones y upgrades— ocurre en una consulta Cypher explícita
sobre el conocimiento del grafo (`cypher/Grupo_20_PG3_diagnostico.cypher`).

Python sólo valida y normaliza la entrada (tipos, evidencia del operador), transporta los hechos,
traduce los errores de conocimiento faltante y arma el texto de salida con lo que devolvió el grafo.
No elige entre alternativas ni vuelve a decidir el plan, el costo ni el estado.
"""

from typing import Any, Dict, List, Optional

# ------------------------------------------------------------------------------
# Resolución completa del dictamen técnico de SM1 (una sola consulta explícita).
#   A. Intervenciones que ordenan los hechos estructurados y los campos del aviso.
#   B. Evidencia textual con precedencia y fallas sin tratamiento conocido.
#   C. Diagnósticos confirmados por el operador y su reparación/costo del grafo.
#   D. Estado final, plan único, total, cantidad de intervenciones y upgrades.
# ------------------------------------------------------------------------------
CONSULTA_RESOLUCION = """
CALL () {
  // A. Intervenciones que ordenan los hechos estructurados del aviso.
  CALL () {
    CALL () {
      MATCH (rd:ReglaDifusa {base:'SM1-BAT'})-[ob:OBLIGA]->(c:CostoReparacion)
      WHERE $hechos.categoria_bat IN ob.categorias
      RETURN c AS costo, rd.base AS origen, null AS criterio, coalesce(ob.orden, 50) AS orden
    UNION
      MATCH (ce:CriterioExperto {nombre:'bateria_reemplazo'}),
            (r:Regla {id:'SM1-BAT-CRISP'})-[:ORDENA]->(c:CostoReparacion)
      WHERE $hechos.salud IS NOT NULL AND $hechos.ciclos IS NULL AND $hechos.salud < ce.valor
      RETURN c AS costo, r.id AS origen, ce AS criterio, r.orden AS orden
    UNION
      MATCH (rd:ReglaDifusa {base:'SM1-TER'})-[ob:OBLIGA]->(c:CostoReparacion)
      WHERE $hechos.categoria_ter IN ob.categorias
      RETURN c AS costo, rd.base AS origen, null AS criterio, coalesce(ob.orden, 50) AS orden
    UNION
      MATCH (r:Regla {id:'SM1-TER-CRISP'})-[:ORDENA]->(c:CostoReparacion)
      WHERE $hechos.temp IS NULL AND $hechos.throttling = true
      RETURN c AS costo, r.id AS origen, null AS criterio, r.orden AS orden
    UNION
      MATCH (ce:CriterioExperto {nombre:'ram_objetivo'}),
            (r:Regla {id:'SM1-RAM-ACCION'})-[:ORDENA]->(c:CostoReparacion)
      WHERE $hechos.ram IS NOT NULL AND $hechos.ram < ce.valor
      RETURN c AS costo, r.id AS origen, ce AS criterio, r.orden AS orden
    UNION
      MATCH (r:Regla {id:'SM1-DISCO-ACCION'})-[:ORDENA]->(c:CostoReparacion)
      WHERE $hechos.disco = 'HDD'
      RETURN c AS costo, r.id AS origen, null AS criterio, r.orden AS orden
    }
    RETURN costo, origen, criterio, orden
  UNION
    // Campos del aviso: la regla declara el campo y el valor que la disparan.
    MATCH (r:Regla)-[:ORDENA]->(c:CostoReparacion)
    WHERE r.campo IS NOT NULL AND $hechos.campos[r.campo] IS NOT NULL AND $hechos.campos[r.campo] = r.valor
    RETURN c AS costo, r.id AS origen, null AS criterio, r.orden AS orden
  UNION
    // Mano de obra: se agrega al final y sólo si el plan tiene intervenciones.
    MATCH (r:Regla {id:'SM1-MANO-OBRA-ACCION'})-[:ORDENA]->(c:CostoReparacion)
    RETURN c AS costo, r.id AS origen, null AS criterio, r.orden AS orden
  }
  WITH costo, origen, criterio, orden
  OPTIONAL MATCH (regla:Regla {id: origen})
  RETURN collect({
    tarea: costo.tarea, descripcion_costo: costo.descripcion, costo_ars: costo.costo_ars,
    costo_id: costo.id, costo_version: costo.version, costo_estado: costo.estado_validacion,
    regla: origen, orden: orden,
    requiere_plan: coalesce(regla.requiere_plan, false),
    cuenta_como_intervencion: coalesce(regla.cuenta_como_intervencion, true),
    criterio_nombre: criterio.nombre, criterio_id: criterio.id, criterio_valor: criterio.valor,
    criterio_unidad: criterio.unidad, criterio_version: criterio.version,
    criterio_estado: criterio.estado_validacion}) AS reglas
}
CALL () {
  // B. Evidencia del aviso: patrones del grafo, precedencia por declaración y fallas sin tratar.
  CALL () {
    UNWIND $evidencias AS ev
    MATCH (pt:PatronTexto)
    WHERE ev.texto =~ pt.patron
      AND (ev.origen = 'falla' OR pt.tratamiento IN ['inviable', 'verificar'])
    OPTIONAL MATCH (pt)-[:ACTIVA]->(r:Regla)
    OPTIONAL MATCH (pt)-[:APLICA_INTERVENCION]->(:Intervencion)-[:SE_COSTEA_CON]->(c:CostoReparacion)
    OPTIONAL MATCH (pt)-[:EVIDENCIA_DE]->(s:FallaSintoma)
    RETURN ev.texto AS texto, pt.id AS patron, pt.tratamiento AS tratamiento,
           pt.descripcion AS descripcion, s.id AS sintoma, s.descripcion AS sintoma_descripcion,
           r.id AS regla, c.tarea AS tarea, c.descripcion AS descripcion_costo, c.costo_ars AS costo_ars,
           c.id AS costo_id, c.version AS costo_version, c.estado_validacion AS costo_estado,
           CASE WHEN pt.campo IS NULL THEN true ELSE coalesce($hechos.campos[pt.campo], false) = false END AS aplicable,
           coalesce(pt.orden, 50) AS orden
  UNION
    // Una falla catastrófica registrada activa R1.1 por su propia descripción (política vigente).
    UNWIND $evidencias AS ev
    MATCH (f:FallaCatastrofica)
    WHERE ev.texto CONTAINS f.descripcion
    MATCH (r:Regla {id:'R1.1'})
    RETURN ev.texto AS texto, f.id AS patron, 'inviable' AS tratamiento,
           f.descripcion AS descripcion, null AS sintoma, null AS sintoma_descripcion,
           r.id AS regla, null AS tarea, null AS descripcion_costo, null AS costo_ars,
           null AS costo_id, null AS costo_version, null AS costo_estado, true AS aplicable, 1 AS orden
  }
  WITH texto, collect({
      patron: patron, tratamiento: tratamiento, descripcion: descripcion, sintoma: sintoma,
      sintoma_descripcion: sintoma_descripcion, regla: regla, tarea: tarea,
      descripcion_costo: descripcion_costo, costo_ars: costo_ars, costo_id: costo_id,
      costo_version: costo_version, costo_estado: costo_estado, aplicable: aplicable,
      orden: orden}) AS filas
  WITH texto, filas,
       [f IN filas WHERE f.tratamiento = 'inviable' AND f.aplicable] AS inviables,
       [f IN filas WHERE f.tratamiento = 'verificar' AND f.aplicable] AS sintomas,
       [f IN filas WHERE f.tratamiento = 'intervencion' AND f.aplicable] AS intervenciones,
       [f IN filas WHERE f.aplicable] AS aplicables
  WITH texto, inviables, sintomas, intervenciones,
       CASE WHEN size(inviables) > 0 THEN 'inviable'
            WHEN size(sintomas) > 0 THEN 'verificar'
            WHEN size(aplicables) = 0 OR any(f IN filas WHERE f.tratamiento = 'descartar') THEN 'descartado'
            WHEN size(intervenciones) > 0 THEN 'intervencion'
            ELSE 'descartado' END AS clase
  WITH collect({texto: texto, clase: clase, inviables: inviables, sintomas: sintomas,
                intervenciones: intervenciones}) AS grupos
  WITH grupos,
       reduce(acc = [], g IN grupos | acc + CASE WHEN g.clase = 'inviable' THEN g.inviables ELSE [] END) AS inviables,
       reduce(acc = [], g IN grupos | acc + CASE WHEN g.clase = 'verificar' THEN g.sintomas ELSE [] END) AS sintomas,
       reduce(acc = [], g IN grupos | acc + CASE WHEN g.clase = 'intervencion' THEN g.intervenciones ELSE [] END) AS intervenciones,
       [t IN $fallas WHERE NOT t IN [g IN grupos | g.texto]] AS sin_tratamiento
  WITH inviables, sin_tratamiento, intervenciones,
       CASE WHEN size(sintomas) = 0 THEN [] ELSE
         [i IN range(0, size(sintomas) - 1)
          WHERE i = 0 OR none(j IN range(0, i - 1) WHERE sintomas[j].sintoma = sintomas[i].sintoma) | sintomas[i]]
       END AS sintomas
  RETURN inviables, sintomas, intervenciones, sin_tratamiento
}
CALL () {
  // C. Diagnósticos confirmados por el operador: el grafo aporta la reparación y el costo.
  UNWIND $diagnosticos AS solicitado
  OPTIONAL MATCH (d:Diagnostico)
  WHERE toLower(d.nombre) = toLower(solicitado) OR toLower(d.id) = toLower(solicitado)
  OPTIONAL MATCH (d)-[:SE_REPARA_CON]->(c:CostoReparacion)
  OPTIONAL MATCH (d)-[:ACTIVA]->(r:Regla)
  RETURN collect({
    solicitado: solicitado, id: d.id, nombre: d.nombre, descripcion: d.descripcion,
    reparable: d.reparable, motivo: d.motivo, regla: r.id, orden: coalesce(d.orden, 50),
    tarea: c.tarea, descripcion_costo: c.descripcion, costo_ars: c.costo_ars,
    costo_id: c.id, costo_version: c.version, costo_estado: c.estado_validacion}) AS diagnosticos
}
WITH reglas, inviables, sintomas, intervenciones, sin_tratamiento, diagnosticos,
     [d IN diagnosticos WHERE d.id IS NULL | d.solicitado] AS desconocidos_crudos,
     [d IN diagnosticos WHERE d.reparable = true AND (d.tarea IS NULL OR d.costo_ars IS NULL) | d.solicitado] AS incompletos_crudos,
     [d IN diagnosticos WHERE d.reparable = false] AS irreparables,
     [d IN diagnosticos WHERE d.reparable = true AND d.tarea IS NOT NULL AND d.costo_ars IS NOT NULL] AS reparaciones,
     [d IN diagnosticos WHERE d.nombre IS NOT NULL | d.nombre] AS confirmados
// Se descartan los diagnósticos repetidos antes de decidir el estado.
WITH reglas, inviables, sintomas, intervenciones, sin_tratamiento, irreparables, reparaciones, confirmados,
     CASE WHEN size(desconocidos_crudos) = 0 THEN [] ELSE
       [i IN range(0, size(desconocidos_crudos) - 1)
        WHERE i = 0 OR none(j IN range(0, i - 1) WHERE desconocidos_crudos[j] = desconocidos_crudos[i])
        | desconocidos_crudos[i]] END AS desconocidos,
     CASE WHEN size(incompletos_crudos) = 0 THEN [] ELSE
       [i IN range(0, size(incompletos_crudos) - 1)
        WHERE i = 0 OR none(j IN range(0, i - 1) WHERE incompletos_crudos[j] = incompletos_crudos[i])
        | incompletos_crudos[i]] END AS incompletos
WITH reglas, inviables, intervenciones, sin_tratamiento, irreparables, reparaciones, confirmados,
     desconocidos, incompletos,
     [s IN sintomas | {sintoma: s.sintoma, descripcion: s.sintoma_descripcion, regla: s.regla}] AS sintomas_detectados
WITH reglas, inviables, intervenciones, sin_tratamiento, irreparables, reparaciones, confirmados,
     desconocidos, incompletos, sintomas_detectados,
     (CASE WHEN $confirmado THEN 0 ELSE size(sintomas_detectados) END) + size(sin_tratamiento) AS pendientes,
     CASE WHEN size(inviables) > 0 THEN inviables[0].regla
          WHEN size(irreparables) > 0 THEN coalesce(irreparables[0].regla, 'R1.1')
          ELSE coalesce([s IN sintomas_detectados WHERE s.regla IS NOT NULL][0].regla, 'R3.3c') END AS regla_aplicada,
     CASE WHEN size(inviables) > 0 THEN inviables[0].descripcion
          WHEN size(irreparables) > 0 THEN irreparables[0].motivo
          ELSE null END AS causa,
     CASE WHEN size(inviables) > 0 THEN 'aviso'
          WHEN size(irreparables) > 0 THEN 'verificacion'
          ELSE null END AS causa_origen
// Estado final: evidencia irreversible, conocimiento faltante, irreparabilidad confirmada,
// verificación pendiente o viabilidad. La decisión queda en el grafo.
WITH reglas, inviables, intervenciones, sin_tratamiento, irreparables, reparaciones, confirmados,
     desconocidos, incompletos, sintomas_detectados, pendientes, regla_aplicada, causa, causa_origen,
     CASE WHEN size(inviables) > 0 THEN 'Inviable'
          WHEN size(desconocidos) > 0 OR size(incompletos) > 0 THEN 'ConocimientoFaltante'
          WHEN size(irreparables) > 0 THEN 'Inviable'
          WHEN pendientes > 0 THEN 'VerificacionPendiente'
          ELSE 'Viable' END AS estado
// Plan único y ordenado, sólo si el estado es viable: reglas estructuradas, intervenciones
// del aviso y reparaciones confirmadas, sin repetir tarea.
WITH reglas, desconocidos, incompletos, sintomas_detectados, sin_tratamiento, confirmados,
     estado, regla_aplicada, causa, causa_origen, pendientes,
     CASE WHEN estado = 'Viable' THEN
       // La mano de obra se agrega al final y una sola vez, si hubo intervenciones.
       [r IN reglas WHERE NOT r.requiere_plan]
       + [f IN intervenciones | {
           tarea: f.tarea, descripcion_costo: f.descripcion_costo, costo_ars: f.costo_ars,
           costo_id: f.costo_id, costo_version: f.costo_version, costo_estado: f.costo_estado,
           regla: coalesce(f.regla, f.patron), orden: f.orden, requiere_plan: false,
           cuenta_como_intervencion: true, criterio_nombre: null, criterio_id: null,
           criterio_valor: null, criterio_unidad: null, criterio_version: null, criterio_estado: null}]
       + [d IN reparaciones | {
           tarea: d.tarea, descripcion_costo: d.descripcion_costo, costo_ars: d.costo_ars,
           costo_id: d.costo_id, costo_version: d.costo_version, costo_estado: d.costo_estado,
           regla: coalesce(d.regla, 'Verificación del operador'), orden: d.orden, requiere_plan: false,
           cuenta_como_intervencion: true, criterio_nombre: null, criterio_id: null,
           criterio_valor: null, criterio_unidad: null, criterio_version: null, criterio_estado: null}]
     ELSE [] END AS candidatas
CALL (candidatas) {
  UNWIND candidatas AS fila
  WITH fila ORDER BY fila.orden, fila.tarea
  RETURN collect(fila) AS ordenadas
}
WITH reglas, desconocidos, incompletos, sintomas_detectados, sin_tratamiento, confirmados,
     estado, regla_aplicada, causa, causa_origen, pendientes, ordenadas,
     [m IN reglas WHERE m.requiere_plan] AS mano_de_obra
WITH desconocidos, incompletos, sintomas_detectados, sin_tratamiento, confirmados,
     estado, regla_aplicada, causa, causa_origen, pendientes,
     CASE WHEN size(ordenadas) = 0 THEN [] ELSE
       [i IN range(0, size(ordenadas) - 1)
        WHERE i = 0 OR none(j IN range(0, i - 1) WHERE ordenadas[j].tarea = ordenadas[i].tarea)
        | ordenadas[i]] END AS unicas,
     mano_de_obra
WITH desconocidos, incompletos, sintomas_detectados, sin_tratamiento, confirmados,
     estado, regla_aplicada, causa, causa_origen, pendientes,
     CASE WHEN size(unicas) > 0 AND size(mano_de_obra) > 0 THEN unicas + [mano_de_obra[0]] ELSE unicas END AS plan
RETURN estado, regla_aplicada, causa, causa_origen, pendientes,
       [f IN plan | {tarea: f.tarea, descripcion_costo: f.descripcion_costo, costo_ars: f.costo_ars,
                     costo_id: f.costo_id, costo_version: f.costo_version, costo_estado: f.costo_estado,
                     regla: f.regla, cuenta_como_intervencion: f.cuenta_como_intervencion,
                     criterio_nombre: f.criterio_nombre, criterio_id: f.criterio_id,
                     criterio_valor: f.criterio_valor, criterio_unidad: f.criterio_unidad,
                     criterio_version: f.criterio_version, criterio_estado: f.criterio_estado}] AS plan,
       reduce(total = 0, f IN plan | total + coalesce(f.costo_ars, 0)) AS costo_total,
       size([f IN plan WHERE coalesce(f.cuenta_como_intervencion, true)]) AS cantidad_intervenciones,
       {ssd: any(f IN plan WHERE f.tarea = 'ssd_upgrade'), ram: any(f IN plan WHERE f.tarea = 'ram_upgrade')} AS upgrades,
       sintomas_detectados, sin_tratamiento, desconocidos, incompletos, confirmados
"""


def _sesion():
    """Sesión de Neo4j del motor (importada en la llamada para no duplicar configuración)."""
    from orquestador_evaltic import NEO4J_DATABASE, obtener_driver_neo4j
    return obtener_driver_neo4j(), NEO4J_DATABASE


def _filas(consulta: str, **parametros) -> List[Dict[str, Any]]:
    driver, base = _sesion()
    with driver.session(database=base) as sesion:
        return [dict(fila) for fila in sesion.run(consulta, **parametros)]


def normalizar_texto(texto: Any) -> str:
    """Normaliza una declaración para compararla con los patrones del grafo (transporte)."""
    return " ".join(str(texto or "").lower().split())


def normalizar_verificacion(verificacion: Optional[dict]) -> Optional[dict]:
    """
    Valida la evidencia técnica que aporta el operador. Sólo una declaración con fuente
    (dónde/cómo se verificó) y al menos un diagnóstico puede liberar la guarda; lo que
    venga del aviso o del LLM nunca se toma como verificación.
    """
    if not isinstance(verificacion, dict):
        return None
    fuente = str(verificacion.get("fuente") or "").strip()
    diagnosticos = [str(d).strip() for d in (verificacion.get("diagnosticos") or []) if str(d).strip()]
    if not fuente or not diagnosticos:
        return None
    return {"fuente": fuente, "diagnosticos": diagnosticos}


def preparar_evidencias(fallas: List[Any], texto: str = ""):
    """
    Prepara las declaraciones que se envían al grafo: las fallas informadas y el texto
    completo del aviso (así un síntoma no queda tapado porque el extractor lo omitió).
    Devuelve la evidencia y las fallas ya normalizadas.
    """
    evidencias = [{"texto": normalizar_texto(falla), "origen": "falla"} for falla in fallas]
    if texto:
        evidencias.append({"texto": normalizar_texto(texto), "origen": "publicacion"})
    return evidencias, [normalizar_texto(falla) for falla in fallas]


def consultar_resolucion_sm1(hechos: dict, evidencias: List[dict], fallas: List[str],
                             verificacion: Optional[dict]) -> dict:
    """
    Ejecuta la resolución del dictamen técnico en Neo4j y devuelve, tal cual, lo que el
    grafo decidió: estado, plan, costo total, cantidad de intervenciones y upgrades.
    """
    evidencia_operador = normalizar_verificacion(verificacion)
    fila = _filas(
        CONSULTA_RESOLUCION,
        hechos=hechos,
        evidencias=evidencias,
        fallas=fallas,
        confirmado=evidencia_operador is not None,
        diagnosticos=evidencia_operador["diagnosticos"] if evidencia_operador else [],
    )
    if not fila:
        # Sin conocimiento de diagnóstico cargado no se puede planificar en silencio.
        from orquestador_evaltic import ConocimientoFaltante
        raise ConocimientoFaltante(
            "falta el conocimiento de diagnóstico de SM1 en Neo4j: hay que aplicar "
            "cypher/Grupo_20_PG3_diagnostico.cypher con un procedimiento aditivo aprobado por el operador.")
    return fila[0]
