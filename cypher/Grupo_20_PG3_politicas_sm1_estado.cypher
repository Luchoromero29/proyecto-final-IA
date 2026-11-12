// =============================================================================
// P2c — Estado resultante de las consecuencias de bloqueo de SM1, como dato de la
// Regla existente que las aplica. Artefacto ADITIVO e IDEMPOTENTE, separado del seed
// diagnóstico, del mercado, de P1, de P2a y de P3.
//
// Una sola consulta: primero valida que las dos reglas existan y que su estado previo
// sea compatible (ausente o igual); sólo si no hay conflicto escribe. Ante conflicto no
// escribe ningún valor y la segunda aplicación devuelve actualizadas=0 sin reescribir.
//
// Qué agrega, y nada más:
//   - Regla('R1.1').estado_resultante   = 'Inviable'
//   - Regla('R3.3c').estado_resultante = 'VerificacionPendiente'
// El vocabulario es el que ya publica el motor (Viable, Inviable, VerificacionPendiente,
// ConocimientoFaltante): es contrato de salida, no política experta nueva. No se tocan
// `estado`, `estado_validacion`, `version` ni las propiedades históricas de las reglas.
// Tampoco se representan todavía precedencias, plan, costos ni el canal del operador:
// eso sigue en la consulta explícita, y el resto de P2 no se declara migrado.
// Pruebas: transacción explícita revertida. Activación: integración del padre sobre el
// scratch marcado, con protección del grafo completo antes del commit.
// =============================================================================
UNWIND [{id: 'R1.1', estado: 'Inviable'}, {id: 'R3.3c', estado: 'VerificacionPendiente'}] AS fila
OPTIONAL MATCH (r:Regla {id: fila.id})
WITH fila, collect(DISTINCT r) AS reglas
WITH fila, CASE WHEN size(reglas) = 1 THEN reglas[0] END AS r
// Precondición: la regla existe una sola vez y el estado es uno de los que el motor publica.
WITH fila, r,
     r IS NOT NULL AND fila.estado IN ['Viable', 'Inviable', 'VerificacionPendiente', 'ConocimientoFaltante'] AS soportada
// Configuración previa compatible: ausente o igual; cualquier otro valor es conflicto.
WITH fila, r, soportada,
     soportada AND coalesce(r.estado_resultante, fila.estado) = fila.estado AS compatible
WITH collect({id: fila.id, estado: fila.estado, regla: r, compatible: compatible}) AS filas
// Un conflicto en cualquier fila bloquea las dos escrituras: el artefacto es atómico.
WITH filas, all(x IN filas WHERE x.compatible) AS sin_conflicto
UNWIND filas AS x
WITH sin_conflicto, x, x.regla AS r, sin_conflicto AND x.regla.estado_resultante IS NULL AS aplica
FOREACH (valor IN CASE WHEN aplica THEN [x.estado] ELSE [] END | SET r.estado_resultante = valor)
WITH collect({compatible: x.compatible, aplica: aplica, id: x.id}) AS resultado
RETURN size([x IN resultado WHERE x.compatible]) AS configuradas,
       size([x IN resultado WHERE x.aplica]) AS actualizadas,
       [x IN resultado WHERE NOT x.compatible |
         'P2c: la regla ' + x.id + ' falta, está duplicada o ya declara otro estado resultante'] AS errores
