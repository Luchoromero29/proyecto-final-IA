// =============================================================================
// P2a — Acciones de SM1: condiciones de las reglas y vínculo de las categorías
// difusas. Artefacto ADITIVO e IDEMPOTENTE, separado del seed diagnóstico y del P1.
//
// Una sola consulta: primero valida la configuración prevista (identidades,
// cardinalidades y conflictos) y sólo si no hay conflicto escribe. La segunda
// aplicación no crea nodos ni relaciones, ni reescribe valores: la proyección no cambia.
//
// Qué agrega, y nada más:
//   - un manifiesto técnico VersionPoliticas de la etapa 'SM1-acciones' con INCLUYE a las
//     ocho reglas de acción y la cardinalidad declarada de condiciones y criterios;
//   - nodos Condicion con campo, ámbito, comparador y operando (literal o referencia
//     USA_CRITERIO), enlazados desde su regla por REQUIERE {grupo}. Un grupo se satisface
//     con cualquiera de sus condiciones (OR) y la regla con todos sus grupos (AND);
//   - en las relaciones OBLIGA existentes, la etapa y el hecho que vincula la categoría
//     difusa con la acción ('categoria_bat' / 'categoria_ter'). El seed diagnóstico vuelve
//     a SET sus propias propiedades y no borra éstas.
//
// No toca campo/valor/tarea/orden/requiere_plan/cuenta_como_intervencion de las Regla (el
// seed diagnóstico las reescribe), ni criterios, costos, conjuntos, diagnósticos ni la
// validación experta. La versión de representación no es validación del experto.
// Uso previsto: scripts/aplicar_politicas_sm1_pruebas.py sobre el grafo de pruebas.
// =============================================================================
WITH 'politicas-SM1-acciones-v1' AS version,
     'SM1-acciones' AS etapa,
     'VP-SM1-ACCIONES' AS id_manifiesto,
     ['SM1-BAT-CRISP', 'SM1-TER-CRISP', 'SM1-RAM-ACCION', 'SM1-DISCO-ACCION',
      'SM1-PANTALLA-ACCION', 'SM1-TECLADO-ACCION', 'SM1-CARGADOR-ACCION',
      'SM1-MANO-OBRA-ACCION'] AS ids_requeridos,
     [
       {id:'SM1-BAT-CRISP', condiciones:[
         {id:'CND-SM1-BAT-CRISP-SALUD', campo:'salud', ambito:'hechos', operador:'<', grupo:1, criterio:'CE-01'},
         {id:'CND-SM1-BAT-CRISP-CICLOS', campo:'ciclos', ambito:'hechos', operador:'ausente', grupo:2}]},
       {id:'SM1-TER-CRISP', condiciones:[
         {id:'CND-SM1-TER-CRISP-TEMP', campo:'temp', ambito:'hechos', operador:'ausente', grupo:1},
         {id:'CND-SM1-TER-CRISP-THROTTLING', campo:'throttling', ambito:'hechos', operador:'=', valor:true, grupo:2}]},
       {id:'SM1-RAM-ACCION', condiciones:[
         {id:'CND-SM1-RAM-ACCION-RAM', campo:'ram', ambito:'hechos', operador:'<', grupo:1, criterio:'CE-27'}]},
       {id:'SM1-DISCO-ACCION', condiciones:[
         {id:'CND-SM1-DISCO-ACCION-DISCO', campo:'disco', ambito:'hechos', operador:'=', valor:'HDD', grupo:1}]},
       {id:'SM1-PANTALLA-ACCION', condiciones:[
         {id:'CND-SM1-PANTALLA-ACCION', campo:'pantalla_danada', ambito:'campos', operador:'=', valor:true, grupo:1}]},
       {id:'SM1-TECLADO-ACCION', condiciones:[
         {id:'CND-SM1-TECLADO-ACCION', campo:'teclado_danado', ambito:'campos', operador:'=', valor:true, grupo:1}]},
       {id:'SM1-CARGADOR-ACCION', condiciones:[
         {id:'CND-SM1-CARGADOR-ACCION', campo:'cargador_incluido', ambito:'campos', operador:'=', valor:false, grupo:1}]},
       {id:'SM1-MANO-OBRA-ACCION', condiciones:[]}
     ] AS reglas,
     [{base:'SM1-BAT', campo:'categoria_bat', obligaciones:5},
      {base:'SM1-TER', campo:'categoria_ter', obligaciones:6}] AS difusas
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas,
     [e IN reglas | e.id] AS ids_reglas,
     reduce(pares = [], e IN reglas | pares + [c IN e.condiciones | {regla: e.id, cond: c}]) AS pares,
     reduce(total = 0, d IN difusas | total + d.obligaciones) AS obligaciones_requeridas
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, ids_reglas, pares,
     obligaciones_requeridas, [p IN pares | p.cond.id] AS ids_condiciones,
     // Identificadores estables: únicos y declarados en el manifiesto.
     size([i IN range(0, size(ids_reglas) - 1)
           WHERE i = 0 OR none(j IN range(0, i - 1) WHERE ids_reglas[j] = ids_reglas[i])]) = size(ids_reglas) AS reglas_unicas,
     size([i IN range(0, size(ids_requeridos) - 1)
           WHERE i = 0 OR none(j IN range(0, i - 1) WHERE ids_requeridos[j] = ids_requeridos[i])]) = size(ids_requeridos) AS ids_unicos,
     all(i IN ids_reglas WHERE i IN ids_requeridos) AS reglas_declaradas
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, ids_reglas, pares,
     obligaciones_requeridas, ids_condiciones, reglas_unicas, ids_unicos, reglas_declaradas,
     size([i IN range(0, size(ids_condiciones) - 1)
           WHERE i = 0 OR none(j IN range(0, i - 1) WHERE ids_condiciones[j] = ids_condiciones[i])]) = size(ids_condiciones) AS condiciones_unicas
// ---------------------------------------------------------------------------
// Manifiesto: identidad única, propiedades compatibles y ningún otro de la etapa.
// ---------------------------------------------------------------------------
OPTIONAL MATCH (vp:VersionPoliticas {id: id_manifiesto})
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, ids_reglas, pares,
     obligaciones_requeridas, ids_condiciones, reglas_unicas, ids_unicos, reglas_declaradas,
     condiciones_unicas, collect(DISTINCT vp) AS manifiestos
OPTIONAL MATCH (otro:VersionPoliticas {etapa: etapa})
WHERE otro.id IS NULL OR otro.id <> id_manifiesto
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, ids_reglas, pares,
     obligaciones_requeridas, ids_condiciones, reglas_unicas, ids_unicos, reglas_declaradas,
     condiciones_unicas, manifiestos,
     [o IN collect(DISTINCT otro) WHERE o IS NOT NULL] AS otros_manifiestos
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, ids_reglas, pares,
     obligaciones_requeridas, ids_condiciones, reglas_unicas, ids_unicos, reglas_declaradas,
     condiciones_unicas, manifiestos, otros_manifiestos,
     size(manifiestos) AS n_manifiestos,
     CASE WHEN size(manifiestos) = 1 THEN manifiestos[0] ELSE null END AS vp,
     any(m IN manifiestos WHERE
           coalesce(m.version, version) <> version OR coalesce(m.etapa, etapa) <> etapa OR
           coalesce(m.activa, true) <> true OR
           coalesce(m.representacion_version, version) <> version OR
           coalesce(m.ids_requeridos, ids_requeridos) <> ids_requeridos OR
           coalesce(m.obligaciones_requeridas, obligaciones_requeridas) <> obligaciones_requeridas) AS manifiesto_conflicto
// ---------------------------------------------------------------------------
// Consecuencias de las reglas: cada regla existe y ordena exactamente un costo.
// ---------------------------------------------------------------------------
UNWIND reglas AS e
OPTIONAL MATCH (r:Regla {id: e.id})-[:ORDENA]->(costo:CostoReparacion)
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, ids_reglas, pares,
     obligaciones_requeridas, ids_condiciones, reglas_unicas, ids_unicos, reglas_declaradas,
     condiciones_unicas, manifiestos, otros_manifiestos, n_manifiestos, vp, manifiesto_conflicto,
     e, r, collect(DISTINCT costo) AS costos
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, ids_reglas, pares,
     obligaciones_requeridas, ids_condiciones, reglas_unicas, ids_unicos, reglas_declaradas,
     condiciones_unicas, manifiestos, otros_manifiestos, n_manifiestos, vp, manifiesto_conflicto,
     collect({id: e.id, regla: r, condiciones: size(e.condiciones),
              criterios: size([c IN e.condiciones WHERE c.criterio IS NOT NULL]),
              costos: size(costos)}) AS reglas_estado
// ---------------------------------------------------------------------------
// Criterios referenciados: existen una vez y su valor es numérico.
// ---------------------------------------------------------------------------
UNWIND pares AS par
OPTIONAL MATCH (ce:CriterioExperto {id: par.cond.criterio})
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, ids_reglas, pares,
     obligaciones_requeridas, ids_condiciones, reglas_unicas, ids_unicos, reglas_declaradas,
     condiciones_unicas, manifiestos, otros_manifiestos, n_manifiestos, vp, manifiesto_conflicto,
     reglas_estado, par, collect(DISTINCT ce) AS criterios
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, ids_reglas, pares,
     obligaciones_requeridas, ids_condiciones, reglas_unicas, ids_unicos, reglas_declaradas,
     condiciones_unicas, manifiestos, otros_manifiestos, n_manifiestos, vp, manifiesto_conflicto,
     reglas_estado,
     collect({par: par, criterios: size(criterios),
              numerico: size([c IN criterios WHERE c.valor IS NOT NULL AND
                              (c.valor IS :: INTEGER OR c.valor IS :: FLOAT)]) = size(criterios)}) AS criterios_estado
// ---------------------------------------------------------------------------
// Condiciones existentes: propiedades, grupo declarado y vínculo con el criterio.
// ---------------------------------------------------------------------------
UNWIND pares AS par
OPTIONAL MATCH (cond:Condicion {id: par.cond.id})
OPTIONAL MATCH (cond)-[:USA_CRITERIO]->(ce_actual:CriterioExperto)
OPTIONAL MATCH (regla_actual:Regla)-[requiere_actual:REQUIERE]->(cond)
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, ids_reglas, pares,
     obligaciones_requeridas, ids_condiciones, reglas_unicas, ids_unicos, reglas_declaradas,
     condiciones_unicas, manifiestos, otros_manifiestos, n_manifiestos, vp, manifiesto_conflicto,
     reglas_estado, criterios_estado, par, cond,
     collect(DISTINCT ce_actual.id) AS criterios_actuales,
     [x IN collect(DISTINCT {regla: regla_actual.id, grupo: requiere_actual.grupo})
      WHERE x.regla IS NOT NULL] AS requieren_actuales
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, ids_reglas, pares,
     obligaciones_requeridas, ids_condiciones, reglas_unicas, ids_unicos, reglas_declaradas,
     condiciones_unicas, manifiestos, otros_manifiestos, n_manifiestos, vp, manifiesto_conflicto,
     reglas_estado, criterios_estado, par, cond, criterios_actuales, requieren_actuales,
     // Propiedades previas: ausentes o iguales; cualquier valor distinto es conflicto.
     cond IS NULL OR (
       coalesce(cond.campo, par.cond.campo) = par.cond.campo AND
       coalesce(cond.ambito, par.cond.ambito) = par.cond.ambito AND
       coalesce(cond.operador, par.cond.operador) = par.cond.operador AND
       coalesce(cond.representacion_version, version) = version AND
       (CASE WHEN par.cond.valor IS NULL THEN cond.valor IS NULL
             ELSE cond.valor IS NOT NULL AND cond.valor = par.cond.valor END)) AS condiciones_compatibles,
     // Vínculo con el criterio: exactamente el esperado, y ninguno si no corresponde.
     // Una condición que todavía no existe se completa después: no es un conflicto.
     cond IS NULL OR
       (CASE WHEN par.cond.criterio IS NULL THEN size(criterios_actuales) = 0
             ELSE size(criterios_actuales) = 1 AND criterios_actuales[0] = par.cond.criterio END) AS criterio_compatible,
     // Grupo declarado: una sola regla requiere la condición, con el grupo esperado.
     size(requieren_actuales) = 0 OR
       (size(requieren_actuales) = 1 AND requieren_actuales[0].regla = par.regla AND
        requieren_actuales[0].grupo = par.cond.grupo) AS grupo_compatible
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, ids_reglas, pares,
     obligaciones_requeridas, ids_condiciones, reglas_unicas, ids_unicos, reglas_declaradas,
     condiciones_unicas, manifiestos, otros_manifiestos, n_manifiestos, vp, manifiesto_conflicto,
     reglas_estado, criterios_estado,
     collect({par: par,
              conflicto: NOT (condiciones_compatibles AND criterio_compatible AND grupo_compatible),
              pendiente: cond IS NULL OR cond.campo IS NULL OR cond.ambito IS NULL OR
                         cond.operador IS NULL OR cond.representacion_version IS NULL OR
                         (par.cond.valor IS NOT NULL AND cond.valor IS NULL) OR
                         size(requieren_actuales) = 0 OR
                         (par.cond.criterio IS NOT NULL AND size(criterios_actuales) = 0)}) AS condiciones_estado
// ---------------------------------------------------------------------------
// Relaciones ajenas al alcance: no se toleran, tampoco se limpian.
// ---------------------------------------------------------------------------
OPTIONAL MATCH (regla_ajena:Regla)-[:REQUIERE]->(condicion_ajena:Condicion)
WHERE regla_ajena.id IN ids_reglas
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, ids_reglas, pares,
     obligaciones_requeridas, ids_condiciones, reglas_unicas, ids_unicos, reglas_declaradas,
     condiciones_unicas, manifiestos, otros_manifiestos, n_manifiestos, vp, manifiesto_conflicto,
     reglas_estado, criterios_estado, condiciones_estado,
     [x IN collect(DISTINCT {regla: regla_ajena.id, condicion: condicion_ajena.id})
      WHERE x.condicion IS NOT NULL AND NOT x.condicion IN ids_condiciones] AS requiere_ajenas
OPTIONAL MATCH (m:VersionPoliticas {id: id_manifiesto})-[inc_actual:INCLUYE]->(miembro)
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, ids_reglas, pares,
     obligaciones_requeridas, ids_condiciones, reglas_unicas, ids_unicos, reglas_declaradas,
     condiciones_unicas, manifiestos, otros_manifiestos, n_manifiestos, vp, manifiesto_conflicto,
     reglas_estado, criterios_estado, condiciones_estado, requiere_ajenas,
     [x IN collect(DISTINCT {id: miembro.id, es_regla: miembro:Regla,
                             condiciones: inc_actual.condiciones,
                             criterios: inc_actual.criterios}) WHERE x.id IS NOT NULL] AS incluye_estado
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, ids_reglas, pares,
     obligaciones_requeridas, ids_condiciones, reglas_unicas, ids_unicos, reglas_declaradas,
     condiciones_unicas, manifiestos, otros_manifiestos, n_manifiestos, vp, manifiesto_conflicto,
     reglas_estado, criterios_estado, condiciones_estado, requiere_ajenas, incluye_estado,
     [x IN incluye_estado WHERE NOT x.id IN ids_reglas OR NOT x.es_regla | x.id] AS incluye_ajenas
// ---------------------------------------------------------------------------
// Obligaciones difusas: cada base conserva sus OBLIGA y recibe etapa y hecho.
// ---------------------------------------------------------------------------
UNWIND difusas AS df
OPTIONAL MATCH (rd:ReglaDifusa {base: df.base})-[ob:OBLIGA]->(:CostoReparacion)
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, ids_reglas, pares,
     obligaciones_requeridas, ids_condiciones, reglas_unicas, ids_unicos, reglas_declaradas,
     condiciones_unicas, manifiestos, otros_manifiestos, n_manifiestos, vp, manifiesto_conflicto,
     reglas_estado, criterios_estado, condiciones_estado, requiere_ajenas, incluye_estado,
     incluye_ajenas, df,
     [x IN collect({rel: ob, base: df.base, campo: df.campo,
                    conflicto: ob IS NOT NULL AND
                               ((ob.etapa IS NOT NULL AND ob.etapa <> etapa) OR
                                (ob.campo IS NOT NULL AND ob.campo <> df.campo)),
                    pendiente: ob IS NOT NULL AND (ob.etapa IS NULL OR ob.campo IS NULL)})
      WHERE x.rel IS NOT NULL] AS obligaciones
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, ids_reglas, pares,
     obligaciones_requeridas, ids_condiciones, reglas_unicas, ids_unicos, reglas_declaradas,
     condiciones_unicas, manifiestos, otros_manifiestos, n_manifiestos, vp, manifiesto_conflicto,
     reglas_estado, criterios_estado, condiciones_estado, requiere_ajenas, incluye_estado,
     incluye_ajenas,
     collect({base: df.base, declaradas: df.obligaciones, total: size(obligaciones),
              conflicto: any(x IN obligaciones WHERE x.conflicto),
              pendientes: [x IN obligaciones WHERE x.pendiente]}) AS obligaciones_estado
// ---------------------------------------------------------------------------
// Compatibilidad: sin conflictos, identidades completas y cardinalidades exactas.
// ---------------------------------------------------------------------------
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, obligaciones_requeridas,
     vp, manifiesto_conflicto, manifiestos, otros_manifiestos, n_manifiestos, reglas_estado,
     criterios_estado, condiciones_estado, requiere_ajenas, incluye_estado, incluye_ajenas,
     obligaciones_estado, reglas_unicas, ids_unicos, reglas_declaradas, condiciones_unicas,
     reglas_unicas AND ids_unicos AND reglas_declaradas AND condiciones_unicas AND
     n_manifiestos <= 1 AND NOT manifiesto_conflicto AND size(otros_manifiestos) = 0 AND
     all(r IN reglas_estado WHERE r.costos = 1) AND
     all(c IN criterios_estado WHERE CASE WHEN c.par.cond.criterio IS NULL THEN c.criterios = 0
                                          ELSE c.criterios = 1 AND c.numerico END) AND
     all(c IN condiciones_estado WHERE NOT c.conflicto) AND
     size(requiere_ajenas) = 0 AND size(incluye_ajenas) = 0 AND
     all(o IN obligaciones_estado WHERE NOT o.conflicto AND o.total = o.declaradas) AS compatible
// Lo pendiente: piezas que todavía no están configuradas (nunca valores distintos).
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, obligaciones_requeridas,
     vp, compatible, reglas_estado, criterios_estado, condiciones_estado, incluye_estado,
     obligaciones_estado, manifiesto_conflicto, manifiestos, otros_manifiestos, n_manifiestos,
     requiere_ajenas, incluye_ajenas, reglas_unicas, ids_unicos, reglas_declaradas,
     condiciones_unicas,
     vp IS NULL OR vp.version IS NULL OR vp.etapa IS NULL OR vp.activa IS NULL OR
       vp.representacion_version IS NULL OR vp.ids_requeridos IS NULL OR
       vp.obligaciones_requeridas IS NULL AS manifiesto_pendiente,
     [r IN reglas_estado WHERE NOT any(i IN incluye_estado WHERE i.id = r.id AND
        i.condiciones = r.condiciones AND i.criterios = r.criterios) |
        {id: r.id, condiciones: r.condiciones, criterios: r.criterios}] AS incluye_pendientes,
     [c IN condiciones_estado WHERE c.pendiente | c.par] AS condiciones_pendientes,
     reduce(acc = [], o IN obligaciones_estado | acc + o.pendientes) AS obligaciones_pendientes
// Errores explícitos: si hay alguno, no se escribe nada.
WITH version, etapa, id_manifiesto, ids_requeridos, reglas, difusas, obligaciones_requeridas,
     vp, compatible, manifiesto_pendiente, incluye_pendientes, condiciones_pendientes,
     obligaciones_pendientes,
     CASE WHEN reglas_unicas THEN [] ELSE ['P2a: identificadores de regla repetidos en el artefacto'] END +
     CASE WHEN ids_unicos THEN [] ELSE ['P2a: ids_requeridos repetidos en el artefacto'] END +
     CASE WHEN reglas_declaradas THEN [] ELSE ['P2a: una regla del artefacto no está declarada en ids_requeridos'] END +
     CASE WHEN condiciones_unicas THEN [] ELSE ['P2a: identificadores de condición repetidos en el artefacto'] END +
     CASE WHEN n_manifiestos <= 1 THEN [] ELSE ['P2a: hay más de un manifiesto con el id de la etapa'] END +
     CASE WHEN NOT manifiesto_conflicto THEN [] ELSE ['P2a: el manifiesto previo tiene propiedades distintas'] END +
     CASE WHEN size(otros_manifiestos) = 0 THEN [] ELSE ['P2a: ya existe otro manifiesto para la etapa SM1-acciones'] END +
     [r IN reglas_estado WHERE r.costos <> 1 | 'P2a: la regla ' + r.id + ' no ordena exactamente un costo'] +
     [c IN criterios_estado WHERE CASE WHEN c.par.cond.criterio IS NULL THEN c.criterios <> 0
                                       ELSE c.criterios <> 1 OR NOT c.numerico END |
        'P2a: el criterio de la condición ' + c.par.cond.id + ' falta, se repite o no es numérico'] +
     [c IN condiciones_estado WHERE c.conflicto |
        'P2a: la condición ' + c.par.cond.id + ' tiene una configuración previa distinta'] +
     [x IN requiere_ajenas | 'P2a: la regla ' + x.regla + ' requiere una condición ajena: ' + x.condicion] +
     [x IN incluye_ajenas | 'P2a: el manifiesto incluye un miembro ajeno: ' + x] +
     [o IN obligaciones_estado WHERE o.total <> o.declaradas |
        'P2a: la base ' + o.base + ' tiene ' + toString(o.total) + ' obligaciones y se esperaban ' + toString(o.declaradas)] +
     [o IN obligaciones_estado WHERE o.conflicto |
        'P2a: una obligación de ' + o.base + ' tiene etapa o hecho distinto'] AS errores
// ---------------------------------------------------------------------------
// Escrituras: sólo con la configuración compatible. Identidad por clave estable.
// ---------------------------------------------------------------------------
FOREACH (ignorado IN CASE WHEN compatible AND manifiesto_pendiente THEN [1] ELSE [] END |
  MERGE (vp_nuevo:VersionPoliticas {id: id_manifiesto})
  SET vp_nuevo.version = version,
      vp_nuevo.etapa = etapa,
      vp_nuevo.activa = true,
      vp_nuevo.representacion_version = version,
      vp_nuevo.ids_requeridos = ids_requeridos,
      vp_nuevo.obligaciones_requeridas = obligaciones_requeridas)
FOREACH (item IN CASE WHEN compatible THEN incluye_pendientes ELSE [] END |
  MERGE (vp_miembro:VersionPoliticas {id: id_manifiesto})
  MERGE (regla_miembro:Regla {id: item.id})
  MERGE (vp_miembro)-[nuevo_incluye:INCLUYE]->(regla_miembro)
  SET nuevo_incluye.condiciones = item.condiciones,
      nuevo_incluye.criterios = item.criterios)
FOREACH (par IN CASE WHEN compatible THEN condiciones_pendientes ELSE [] END |
  MERGE (nueva:Condicion {id: par.cond.id})
  SET nueva.campo = par.cond.campo,
      nueva.ambito = par.cond.ambito,
      nueva.operador = par.cond.operador,
      nueva.valor = par.cond.valor,
      nueva.representacion_version = version
  MERGE (regla_origen:Regla {id: par.regla})
  MERGE (regla_origen)-[:REQUIERE {grupo: par.cond.grupo}]->(nueva)
  FOREACH (ignorado_criterio IN CASE WHEN par.cond.criterio IS NULL THEN [] ELSE [1] END |
    MERGE (criterio_usado:CriterioExperto {id: par.cond.criterio})
    MERGE (nueva)-[:USA_CRITERIO]->(criterio_usado)))
FOREACH (o IN CASE WHEN compatible THEN obligaciones_pendientes ELSE [] END |
  SET o.rel.etapa = etapa,
      o.rel.campo = o.campo)
// ---------------------------------------------------------------------------
// Resultado: deltas y errores. Una segunda aplicación devuelve ceros.
// ---------------------------------------------------------------------------
RETURN compatible,
       size(errores) AS errores_count,
       errores,
       CASE WHEN compatible AND manifiesto_pendiente THEN 1 ELSE 0 END AS manifiestos_creados,
       size(incluye_pendientes) AS incluye_creadas,
       size(condiciones_pendientes) AS condiciones_creadas,
       size([par IN condiciones_pendientes WHERE par.cond.criterio IS NOT NULL]) AS criterios_enlazados,
       size(obligaciones_pendientes) AS obligaciones_vinculadas,
       (CASE WHEN compatible AND manifiesto_pendiente THEN 1 ELSE 0 END) + size(incluye_pendientes) +
         size(condiciones_pendientes) + size(obligaciones_pendientes) AS cambios
