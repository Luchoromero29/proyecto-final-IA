// =============================================================================
// P3a — Condición del filtro R3.7 (ratio de reparación frente a su criterio) como
// datos de la Regla existente. Artefacto ADITIVO e IDEMPOTENTE, separado del seed
// diagnóstico, del mercado y de P1.
//
// Una sola consulta: primero valida la Regla y su vínculo USA_CRITERIO y sólo si no
// hay conflicto escribe. Ante conflicto no escribe ningún valor y la segunda
// aplicación devuelve actualizadas=0 sin reescribir propiedades.
//
// Qué agrega, y nada más:
//   - Regla('R3.7').filtro_campo = 'ratio_reparacion' (campo comparado)
//   - Regla('R3.7').filtro_comparador = '>' (comparador; la consulta admite '>' y '<')
// El criterio de comparación sigue siendo el nodo enlazado por USA_CRITERIO
// (ratio_reparacion_max): no se crea otro criterio y no se toca su valor, su unidad
// ni su validación experta. No representa todavía las consecuencias de R3.7 ni el
// resto de la política financiera.
// Uso previsto: transacción explícita sobre el grafo de pruebas, revertida al final.
// =============================================================================
WITH 'ratio_reparacion' AS campo, '>' AS comparador, 'ratio_reparacion_max' AS criterio
MATCH (r:Regla {id:'R3.7'})
OPTIONAL MATCH (r)-[:USA_CRITERIO]->(ce:CriterioExperto)
WITH campo, comparador, criterio, collect(DISTINCT r) AS reglas,
     [c IN collect(DISTINCT ce) WHERE c IS NOT NULL] AS criterios
WITH campo, comparador, criterio, reglas, criterios,
     CASE WHEN size(reglas) = 1 AND size(criterios) = 1
            AND criterios[0].nombre = criterio AND criterios[0].valor IS NOT NULL
          THEN reglas[0] END AS r
// Configuración previa compatible: ausente o igual; cualquier otro valor es conflicto.
WITH campo, comparador, r,
     r IS NOT NULL AND coalesce(r.filtro_campo, campo) = campo
                    AND coalesce(r.filtro_comparador, comparador) = comparador AS compatible
WITH campo, comparador, r, compatible,
     compatible AND (r.filtro_campo IS NULL OR r.filtro_comparador IS NULL) AS aplica
FOREACH (x IN CASE WHEN aplica THEN [1] ELSE [] END |
  SET r.filtro_campo = campo, r.filtro_comparador = comparador)
RETURN CASE WHEN compatible THEN 1 ELSE 0 END AS configuradas,
       CASE WHEN aplica THEN 1 ELSE 0 END AS actualizadas,
       CASE WHEN compatible THEN [] ELSE
         ['P3a: R3.7 ausente/duplicada, criterio enlazado no único o configuración previa incompatible'] END AS errores
