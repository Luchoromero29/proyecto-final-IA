// P1: completar los tres conjuntos existentes, sin recrear/calibrar el grafo.
// Una consulta, dentro de una transacción explícita: confirmar sólo si configuradas=3.
// Si falta identidad/enlace o hay conflicto previo, no se escribe ningún conjunto.
// La segunda aplicación devuelve actualizadas=0. No altera validación experta.
WITH [
  {id:'Conveniencia.Comprar', etiqueta:'Comprar', decision:'Comprar', oferta:false},
  {id:'Conveniencia.Negociar', etiqueta:'Negociar', decision:'ComprarConOfertaMenor', oferta:true},
  {id:'Conveniencia.Descartar', etiqueta:'Descartar', decision:'DescartarPorRiesgo', oferta:false}
] AS configuracion, 'politicas-P1-v1' AS version
UNWIND configuracion AS esperado
OPTIONAL MATCH (:VariableDifusa {nombre:'Conveniencia'})-[:TIENE_CONJUNTO]->
               (c:ConjuntoDifuso {id:esperado.id})
WITH version, esperado, collect(c) AS encontrados
WITH version, collect({esperado:esperado, nodos:encontrados}) AS entradas
WITH version, entradas, all(e IN entradas WHERE size(e.nodos)=1 AND
  all(n IN e.nodos WHERE n.etiqueta=e.esperado.etiqueta AND
    (n.resultado_decision IS NULL OR n.resultado_decision=e.esperado.decision) AND
    (n.contraoferta_habilitada IS NULL OR n.contraoferta_habilitada=e.esperado.oferta) AND
    (n.representacion_version IS NULL OR n.representacion_version=version))) AS compatible
WITH version, compatible, CASE WHEN compatible THEN
  [e IN entradas WHERE any(n IN e.nodos WHERE n.resultado_decision IS NULL OR
    n.contraoferta_habilitada IS NULL OR n.representacion_version IS NULL)] ELSE [] END AS cambios
FOREACH (e IN cambios |
  FOREACH (n IN e.nodos |
    SET n.resultado_decision=e.esperado.decision,
        n.contraoferta_habilitada=e.esperado.oferta,
        n.representacion_version=version))
RETURN CASE WHEN compatible THEN 3 ELSE 0 END AS configuradas,
       size(cambios) AS actualizadas,
       CASE WHEN compatible THEN [] ELSE
         ['P1: identidad/enlaces incompletos, duplicados o configuración previa incompatible'] END AS errores
