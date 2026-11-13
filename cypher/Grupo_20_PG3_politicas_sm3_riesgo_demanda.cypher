// =============================================================================
// P3b — Categorías de riesgo y de demanda que disparan el descarte de R3.8, como
// datos de la Regla existente. Artefacto ADITIVO e IDEMPOTENTE, separado del seed
// diagnóstico, del mercado, de P1 y de P3a.
//
// Una sola consulta: primero valida la Regla y que las dos categorías estén
// declaradas por los conjuntos de sus variables difusas; sólo si no hay conflicto
// escribe. Ante conflicto no escribe ningún valor y la segunda aplicación devuelve
// actualizadas=0 sin reescribir propiedades.
//
// Qué agrega, y nada más:
//   - Regla('R3.8').filtro_riesgo  = 'Alto'
//   - Regla('R3.8').filtro_demanda = 'Baja'
// La igualdad de esas dos categorías y su conjunción son la condición completa de
// R3.8. No se representa todavía el resto de la política financiera: márgenes,
// fórmulas, contraoferta y precedencias conservan su forma actual.
// La categoría no introduce vocabulario nuevo: la declara el grafo en
// (:VariableDifusa)-[:TIENE_CONJUNTO]->(:ConjuntoDifuso).
// Pruebas: transacción explícita revertida. Activación: integración del padre sobre
// el scratch marcado, con protección del grafo completo antes del commit.
// =============================================================================
WITH 'Alto' AS riesgo, 'Baja' AS demanda
MATCH (r:Regla {id:'R3.8'})
WITH riesgo, demanda, collect(DISTINCT r) AS reglas
WITH riesgo, demanda, reglas, CASE WHEN size(reglas) = 1 THEN reglas[0] END AS r
// Precondición: las dos categorías existen en los conjuntos que declara el grafo.
WITH riesgo, demanda, r,
     r IS NOT NULL
     AND EXISTS { MATCH (:VariableDifusa {nombre:'Riesgo_Obsolescencia'})-[:TIENE_CONJUNTO]->(:ConjuntoDifuso {etiqueta: riesgo}) }
     AND EXISTS { MATCH (:VariableDifusa {nombre:'Demanda_Comercial'})-[:TIENE_CONJUNTO]->(:ConjuntoDifuso {etiqueta: demanda}) } AS soportada
// Configuración previa compatible: ausente o igual; cualquier otro valor es conflicto.
WITH riesgo, demanda, r, soportada,
     soportada AND coalesce(r.filtro_riesgo, riesgo) = riesgo
               AND coalesce(r.filtro_demanda, demanda) = demanda AS compatible
WITH riesgo, demanda, r, compatible,
     compatible AND (r.filtro_riesgo IS NULL OR r.filtro_demanda IS NULL) AS aplica
FOREACH (x IN CASE WHEN aplica THEN [1] ELSE [] END |
  SET r.filtro_riesgo = riesgo, r.filtro_demanda = demanda)
RETURN CASE WHEN compatible THEN 1 ELSE 0 END AS configuradas,
       CASE WHEN aplica THEN 1 ELSE 0 END AS actualizadas,
       CASE WHEN compatible THEN [] ELSE
         ['P3b: R3.8 ausente/duplicada, categoría no declarada por el grafo o configuración previa incompatible'] END AS errores
