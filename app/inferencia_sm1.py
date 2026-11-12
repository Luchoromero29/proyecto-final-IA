#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inferencia de diagnóstico de SM1 en Neo4j (B2).

Toda la resolución del dictamen técnico —qué acciones de reacondicionamiento ordena el aviso,
qué evidencia es irreversible, cómo se combinan el plan, el costo y el estado— ocurre en una
consulta Cypher explícita sobre el conocimiento del grafo. Las condiciones de las acciones
(campo, ámbito, comparador, operando literal o criterio enlazado, grupo y categoría difusa)
son DATOS del grafo (`cypher/Grupo_20_PG3_politicas_sm1_acciones.cypher`), no ramas por
identificador de regla: cambiar una condición cambia el plan sin editar este archivo. Los
comparadores finitos y su aritmética son el mecanismo de evaluación; el conocimiento está en
los datos.

Una configuración incompleta, ambigua o inválida se informa como error de conocimiento
(`ConocimientoFaltante`) con su motivo, nunca como un plan vacío que parezca favorable.

Python sólo valida y normaliza la entrada (tipos, evidencia del operador), transporta los
hechos, traduce los errores de conocimiento faltante y arma el texto de salida con lo que
devolvió el grafo. No elige entre alternativas ni vuelve a decidir el plan, el costo ni el
estado.
"""

from typing import Any, Dict, List, Optional

# ------------------------------------------------------------------------------
# Resolución completa del dictamen técnico de SM1 (una sola consulta explícita).
#   A. Acciones que ordena la etapa: condiciones y categorías difusas del grafo.
#   B. Evidencia textual con precedencia y fallas sin tratamiento conocido.
#   C. Diagnósticos confirmados por el operador y su reparación/costo del grafo.
#   D. Estado final, plan único, total, cantidad de intervenciones y upgrades.
# ------------------------------------------------------------------------------
CONSULTA_RESOLUCION = """
CALL () {
  // A. Acciones de SM1: el grafo declara el manifiesto de la etapa, los hechos, los
  //    comparadores y las consecuencias; acá sólo se evalúan de forma finita. Un grupo se
  //    satisface con cualquiera de sus condiciones (OR) y la regla con todos sus grupos (AND);
  //    una regla sin condiciones (mano de obra) se agrega al final del plan.
  CALL () {
    MATCH (:VersionPoliticas {etapa:'SM1-acciones', activa:true})-[:INCLUYE]->
          (r:Regla)-[:ORDENA]->(costo:CostoReparacion)
    OPTIONAL MATCH (r)-[requiere:REQUIERE]->(cond:Condicion)
    OPTIONAL MATCH (cond)-[:USA_CRITERIO]->(criterio:CriterioExperto)
    WITH r, costo, requiere, cond, criterio,
         CASE WHEN cond.ambito = 'campos' THEN $hechos.campos[cond.campo]
              WHEN cond.ambito = 'hechos' THEN $hechos[cond.campo] END AS valor
    WITH r, costo, requiere, cond, criterio, valor,
         CASE WHEN cond.valor IS NOT NULL AND (cond.valor IS :: INTEGER OR cond.valor IS :: FLOAT)
              THEN toFloat(cond.valor) END AS literal,
         CASE WHEN criterio.valor IS NOT NULL AND
                   (criterio.valor IS :: INTEGER OR criterio.valor IS :: FLOAT)
              THEN toFloat(criterio.valor) END AS operando
    WITH r, costo, requiere, cond, criterio, valor, literal, operando,
         CASE WHEN valor IS NULL THEN null
              WHEN valor IS :: INTEGER OR valor IS :: FLOAT THEN toFloat(valor) END AS numero
    WITH r, costo, requiere, cond, criterio, valor,
         CASE WHEN cond IS NULL THEN null
              WHEN cond.operador = 'ausente' THEN valor IS NULL
              WHEN cond.operador = 'presente' THEN valor IS NOT NULL
              WHEN cond.operador = '=' THEN valor IS NOT NULL AND valor = cond.valor
              WHEN cond.operador = '<' THEN coalesce(
                     numero < CASE WHEN literal IS NOT NULL THEN literal ELSE operando END, false)
              END AS cumple
    WITH r, costo,
         collect(CASE WHEN cond IS NULL THEN null ELSE
                   {grupo: requiere.grupo, cumplida: cumple, criterio: criterio} END) AS condiciones
    WITH r, costo, condiciones, [c IN condiciones | c.grupo] AS grupos
    WHERE all(grupo IN grupos WHERE any(c IN condiciones WHERE c.grupo = grupo AND c.cumplida))
    RETURN costo, r.id AS origen,
           [c IN condiciones WHERE c.criterio IS NOT NULL AND c.cumplida][0].criterio AS criterio,
           r.orden AS orden
  UNION
    // Categorías difusas: la relación OBLIGA declara la etapa y el hecho que la vincula.
    MATCH (rd:ReglaDifusa)-[obliga:OBLIGA {etapa:'SM1-acciones'}]->(costo:CostoReparacion)
    WITH rd, obliga, costo, $hechos[obliga.campo] AS categoria
    WHERE categoria IS NOT NULL AND categoria IN obliga.categorias
    RETURN costo, rd.base AS origen, null AS criterio, coalesce(obliga.orden, 50) AS orden
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
// Consecuencias de bloqueo: inviable, irreparable o verificación pendiente. El estado
// resultante lo declara en el grafo la regla que lo aplica (`estado_resultante`), no un
// literal acá: cambiar ese dato cambia el estado público sin editar este archivo.
WITH reglas, inviables, intervenciones, sin_tratamiento, irreparables, reparaciones, confirmados,
     desconocidos, incompletos, sintomas_detectados, pendientes, regla_aplicada, causa, causa_origen,
     size(inviables) > 0 OR size(irreparables) > 0 OR pendientes > 0 AS decide_grafo
OPTIONAL MATCH (rp:Regla {id: regla_aplicada})
WITH reglas, inviables, intervenciones, sin_tratamiento, irreparables, reparaciones, confirmados,
     desconocidos, incompletos, sintomas_detectados, pendientes, regla_aplicada, causa, causa_origen,
     rp.estado_resultante AS estado_resultante,
     CASE WHEN decide_grafo AND NOT coalesce(rp.estado_resultante, '') IN
                   ['Inviable', 'ConocimientoFaltante', 'VerificacionPendiente', 'Viable']
          THEN ['configuración de políticas de SM1: la regla ' + coalesce(regla_aplicada, 'sin id') +
                ' no declara un estado resultante válido'] ELSE [] END AS problemas_estado
// Estado final: evidencia irreversible, conocimiento faltante, irreparabilidad confirmada,
// verificación pendiente o viabilidad. La decisión queda en el grafo.
WITH reglas, inviables, intervenciones, sin_tratamiento, irreparables, reparaciones, confirmados,
     desconocidos, incompletos, sintomas_detectados, pendientes, regla_aplicada, causa, causa_origen,
     problemas_estado,
     CASE WHEN size(inviables) > 0 THEN estado_resultante
          WHEN size(desconocidos) > 0 OR size(incompletos) > 0 THEN 'ConocimientoFaltante'
          WHEN size(irreparables) > 0 THEN estado_resultante
          WHEN pendientes > 0 THEN estado_resultante
          ELSE 'Viable' END AS estado
// Plan único y ordenado, sólo si el estado es viable: reglas estructuradas, intervenciones
// del aviso y reparaciones confirmadas, sin repetir tarea.
WITH reglas, desconocidos, incompletos, sintomas_detectados, sin_tratamiento, confirmados,
     estado, regla_aplicada, causa, causa_origen, pendientes, problemas_estado,
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
     estado, regla_aplicada, causa, causa_origen, pendientes, problemas_estado, ordenadas,
     [m IN reglas WHERE m.requiere_plan] AS mano_de_obra
WITH desconocidos, incompletos, sintomas_detectados, sin_tratamiento, confirmados,
     estado, regla_aplicada, causa, causa_origen, pendientes, problemas_estado,
     CASE WHEN size(ordenadas) = 0 THEN [] ELSE
       [i IN range(0, size(ordenadas) - 1)
        WHERE i = 0 OR none(j IN range(0, i - 1) WHERE ordenadas[j].tarea = ordenadas[i].tarea)
        | ordenadas[i]] END AS unicas,
     mano_de_obra
WITH desconocidos, incompletos, sintomas_detectados, sin_tratamiento, confirmados,
     estado, regla_aplicada, causa, causa_origen, pendientes, problemas_estado,
     CASE WHEN size(unicas) > 0 AND size(mano_de_obra) > 0 THEN unicas + [mano_de_obra[0]] ELSE unicas END AS plan
CALL () {
  // A.0 Guarda de configuración de la etapa: manifiesto único y completo, condiciones
  //     íntegras y obligaciones vinculadas. Se informa como error explícito; nunca se
  //     convierte en un plan vacío que parezca favorable.
  CALL () {
    OPTIONAL MATCH (vp:VersionPoliticas {etapa:'SM1-acciones', activa:true})
    WITH collect(DISTINCT vp) AS manifiestos
    WITH size(manifiestos) AS n,
         CASE WHEN size(manifiestos) = 1 THEN manifiestos[0] ELSE null END AS vp
    OPTIONAL MATCH (vp)-[:INCLUYE]->(miembro)
    WITH n, vp,
         collect(CASE WHEN miembro IS NULL THEN null ELSE
                   {id: miembro.id, es_regla: miembro:Regla} END) AS crudos
    WITH n, [m IN crudos WHERE m IS NOT NULL] AS miembros, coalesce(vp.ids_requeridos, []) AS requeridos
    WITH n, miembros, requeridos,
         [m IN miembros WHERE NOT m.es_regla] AS no_reglas,
         [m IN miembros WHERE NOT m.id IN requeridos] AS no_declarados,
         size([i IN range(0, size(requeridos) - 1)
               WHERE i = 0 OR none(j IN range(0, i - 1) WHERE requeridos[j] = requeridos[i])]) AS unicos
    RETURN
      CASE WHEN n = 0 THEN ['configuración de políticas de SM1: falta el manifiesto técnico ' +
        'VersionPoliticas activo de la etapa SM1-acciones en Neo4j'] ELSE [] END +
      CASE WHEN n > 1 THEN ['configuración de políticas de SM1: más de un manifiesto ' +
        'VersionPoliticas activo para la etapa SM1-acciones'] ELSE [] END +
      CASE WHEN n = 1 AND size(requeridos) = 0 THEN ['configuración de políticas de SM1: ' +
        'el manifiesto de la etapa no declara ids_requeridos'] ELSE [] END +
      CASE WHEN n = 1 AND unicos <> size(requeridos) THEN ['configuración de políticas de SM1: ' +
        'ids_requeridos repetidos en el manifiesto'] ELSE [] END +
      CASE WHEN n = 1 AND (size(miembros) <> size(requeridos) OR size(no_declarados) > 0) THEN
        ['configuración de políticas de SM1: las reglas incluidas no coinciden con ids_requeridos'] ELSE [] END +
      [m IN no_reglas | 'configuración de políticas de SM1: el manifiesto incluye un miembro que ' +
        'no es una regla: ' + coalesce(m.id, 'sin id')] AS problemas_manifiesto
  }
  CALL () {
    OPTIONAL MATCH (:VersionPoliticas {etapa:'SM1-acciones', activa:true})-[incluye:INCLUYE]->(r:Regla)
    OPTIONAL MATCH (r)-[:ORDENA]->(costo:CostoReparacion)
    WITH r, incluye, collect(DISTINCT costo) AS costos
    OPTIONAL MATCH (r)-[requiere:REQUIERE]->(cond:Condicion)
    WITH r, incluye, costos, requiere, cond
    OPTIONAL MATCH (cond)-[:USA_CRITERIO]->(criterio:CriterioExperto)
    WITH r, incluye, costos, cond, requiere, collect(DISTINCT criterio) AS criterios
    WITH r, incluye, costos,
         collect(CASE WHEN cond IS NULL THEN null ELSE
                   {id: cond.id, campo: cond.campo, ambito: cond.ambito, operador: cond.operador,
                    valor: cond.valor, grupo: requiere.grupo, criterios: criterios} END) AS condiciones
    WITH collect(CASE WHEN r IS NULL THEN null ELSE
                 {id: r.id, declaradas: incluye.condiciones, declarados: incluye.criterios,
                  costos: size(costos),
                  condiciones: [c IN condiciones WHERE c IS NOT NULL]} END) AS crudos
    WITH [e IN crudos WHERE e IS NOT NULL] AS reglas
    WITH reglas,
         reduce(acc = [], e IN reglas |
                acc + [c IN e.condiciones | c {.*, declarados: e.declarados}]) AS condiciones
    RETURN
      [e IN reglas WHERE e.costos <> 1 |
        'configuración de políticas de SM1: la regla ' + e.id + ' no ordena exactamente un costo'] +
      [e IN reglas WHERE e.declaradas IS NULL OR NOT e.declaradas IS :: INTEGER |
        'configuración de políticas de SM1: el manifiesto no declara las condiciones de la regla ' + e.id] +
      [e IN reglas WHERE e.declaradas IS :: INTEGER AND size(e.condiciones) <> e.declaradas |
        'configuración de políticas de SM1: las condiciones de la regla ' + e.id + ' no coinciden con las declaradas'] +
      [e IN reglas WHERE e.declarados IS NULL OR NOT e.declarados IS :: INTEGER |
        'configuración de políticas de SM1: el manifiesto no declara los criterios de la regla ' + e.id] +
      [e IN reglas WHERE e.declarados IS :: INTEGER AND
        size([c IN e.condiciones WHERE size(c.criterios) > 0]) <> e.declarados |
        'configuración de políticas de SM1: los criterios de la regla ' + e.id + ' no coinciden con los declarados'] +
      [c IN condiciones WHERE c.campo IS NULL OR NOT c.campo IS :: STRING |
        'configuración de políticas de SM1: la condición ' + coalesce(c.id, 'sin id') + ' no declara un campo'] +
      [c IN condiciones WHERE NOT coalesce(c.ambito, '') IN ['hechos', 'campos'] |
        'configuración de políticas de SM1: la condición ' + coalesce(c.id, 'sin id') + ' no declara un ámbito válido'] +
      [c IN condiciones WHERE NOT coalesce(c.operador, '') IN ['=', '<', 'ausente', 'presente'] |
        'configuración de políticas de SM1: operador no admitido en la condición ' + coalesce(c.id, 'sin id')] +
      [c IN condiciones WHERE c.operador = '=' AND c.valor IS NULL |
        'configuración de políticas de SM1: la condición ' + coalesce(c.id, 'sin id') +
        ' no declara el valor de comparación'] +
      [c IN condiciones WHERE c.operador = '<' AND c.valor IS NULL AND size(c.criterios) = 0 |
        'configuración de políticas de SM1: la condición ' + coalesce(c.id, 'sin id') + ' no declara operando'] +
      [c IN condiciones WHERE c.operador IN ['ausente', 'presente'] AND
        (c.valor IS NOT NULL OR size(c.criterios) > 0) |
        'configuración de políticas de SM1: la condición ' + coalesce(c.id, 'sin id') + ' no admite operando'] +
      [c IN condiciones WHERE size(c.criterios) > 1 |
        'configuración de políticas de SM1: la condición ' + coalesce(c.id, 'sin id') +
        ' tiene más de un criterio vinculado'] +
      [c IN condiciones WHERE c.declarados IS :: INTEGER AND c.declarados > 0 AND
        c.operador = '<' AND size(c.criterios) = 0 |
        'configuración de políticas de SM1: la condición ' + coalesce(c.id, 'sin id') + ' no tiene criterio vinculado'] +
      [c IN condiciones WHERE any(ce IN c.criterios WHERE ce.valor IS NULL OR
        NOT (ce.valor IS :: INTEGER OR ce.valor IS :: FLOAT)) |
        'configuración de políticas de SM1: el criterio de la condición ' + coalesce(c.id, 'sin id') + ' no es numérico'] AS problemas_reglas
  }
  CALL () {
    // Identidad de las condiciones de la ETAPA: las que requieren sus reglas y las que
    // declara su versión de representación. Una condición de otra etapa no es asunto de
    // SM1: no se informa como error ni se cuenta como duplicada.
    OPTIONAL MATCH (vp:VersionPoliticas {etapa:'SM1-acciones', activa:true})
    WITH coalesce(vp.version, '') AS version
    OPTIONAL MATCH (:VersionPoliticas {etapa:'SM1-acciones', activa:true})-[:INCLUYE]->(:Regla)
                  -[:REQUIERE]->(requerida:Condicion)
    WITH version, collect(DISTINCT requerida) AS requeridas_nodos
    OPTIONAL MATCH (cond:Condicion)
    WHERE cond IN requeridas_nodos OR (version <> '' AND cond.representacion_version = version)
    WITH collect(DISTINCT cond) AS nodos
    WITH [n IN nodos WHERE n IS NOT NULL | n.id] AS ids
    WITH ids, [i IN range(0, size(ids) - 1)
               WHERE i > 0 AND any(j IN range(0, i - 1) WHERE ids[j] = ids[i]) | ids[i]] AS repetidos
    OPTIONAL MATCH (:VersionPoliticas {etapa:'SM1-acciones', activa:true})-[:INCLUYE]->(:Regla)
                  -[:REQUIERE]->(requerida:Condicion)
    WITH ids, repetidos, [r IN collect(DISTINCT requerida.id) WHERE r IS NOT NULL] AS requeridas
    RETURN
      [i IN ids WHERE i IS NULL |
        'configuración de políticas de SM1: una condición no declara identificador'] +
      CASE WHEN size(repetidos) = 0 THEN [] ELSE
        ['configuración de políticas de SM1: identificador de condición repetido:' +
         reduce(txt = '', repetido IN repetidos | txt + ' ' + toString(repetido))] END +
      [i IN ids WHERE i IS NOT NULL AND NOT i IN requeridas |
        'configuración de políticas de SM1: la condición ' + i +
        ' no está requerida por ninguna regla de la etapa'] AS problemas_duplicados
  }
  CALL () {
    OPTIONAL MATCH (vp:VersionPoliticas {etapa:'SM1-acciones', activa:true})
    WITH coalesce(vp.obligaciones_requeridas, -1) AS requeridas
    OPTIONAL MATCH (:ReglaDifusa)-[obliga:OBLIGA {etapa:'SM1-acciones'}]->(costo:CostoReparacion)
    WITH requeridas, collect(CASE WHEN obliga IS NULL THEN null ELSE
             {campo: obliga.campo, categorias: obliga.categorias, orden: obliga.orden,
              tarea: costo.tarea} END) AS crudos
    WITH requeridas, [o IN crudos WHERE o IS NOT NULL] AS obligaciones
    RETURN
      CASE WHEN size(obligaciones) = requeridas THEN [] ELSE
        ['configuración de políticas de SM1: las obligaciones de la etapa son ' +
         toString(size(obligaciones)) + ' y el manifiesto declara ' + toString(requeridas)] END +
      [o IN obligaciones WHERE o.campo IS NULL OR NOT o.campo IS :: STRING |
        'configuración de políticas de SM1: la obligación de la tarea ' + coalesce(o.tarea, 'sin tarea') +
        ' no declara el hecho de la categoría'] +
      [o IN obligaciones WHERE o.categorias IS NULL OR size(o.categorias) = 0 OR
        any(x IN coalesce(o.categorias, []) WHERE NOT x IS :: STRING) |
        'configuración de políticas de SM1: la obligación de la tarea ' + coalesce(o.tarea, 'sin tarea') +
        ' no declara categorías'] +
      [o IN obligaciones WHERE o.orden IS NULL OR NOT o.orden IS :: INTEGER |
        'configuración de políticas de SM1: la obligación de la tarea ' + coalesce(o.tarea, 'sin tarea') +
        ' no declara orden'] AS problemas_obligaciones
  }
  RETURN problemas_manifiesto + problemas_reglas + problemas_duplicados +
         problemas_obligaciones AS configuracion_invalida
}
RETURN estado, regla_aplicada, causa, causa_origen, pendientes,
       configuracion_invalida + problemas_estado AS configuracion_invalida,
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

    La consulta transporta además `configuracion_invalida`, la lista de problemas que el
    propio grafo detectó en la representación de sus políticas. Esa lista no se puede
    colapsar en un plan vacío: se traduce al error de conocimiento existente, con el motivo
    concreto, para que ni una configuración rota ni un conjunto `collect` más corto
    terminen en un plan gratuito o en una viabilidad aparente.
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
    if fila[0].get("configuracion_invalida"):
        from orquestador_evaltic import ConocimientoFaltante
        motivos = "; ".join(sorted(set(fila[0]["configuracion_invalida"])))
        raise ConocimientoFaltante(
            "la configuración de políticas de SM1 en Neo4j está incompleta o es inválida: "
            f"{motivos}. Hay que aplicar cypher/Grupo_20_PG3_politicas_sm1_acciones.cypher "
            "con un procedimiento aditivo aprobado por el operador.")
    return fila[0]
