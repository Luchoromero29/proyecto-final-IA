// =============================================================================
// EvalTIC — Patrones de redacción del aviso (aditivo e idempotente)
//
// Diagnóstico de los 5 casos integrados del PG3: tres de ellos terminaban en
// VerificacionPendiente porque el extractor redacta las fallas con palabras que ningún
// patrón del grafo reconocía. Una sola falla sin patrón anula el plan completo y fuerza
// pendiente, así que el efecto era desproporcionado.
//
//   "batería dura 20 minutos"      -> no estaba en PT-INT-BATERIA (pide agotada/dañada)
//   "requiere service de limpieza" -> es la intervención térmica, no una falla nueva
//   "necesario upgrade de memoria" -> es el plan de RAM, que ya sale de los hechos
//   "necesario upgrade SSD"        -> es la intervención de disco
//   "falta de soporte para Windows 11" / "equipo antiguo" -> no son fallas: son riesgo,
//   y SM2 ya los toma de los hechos (soporte_windows_11, antigüedad)
//
// No agrega reglas, costos ni criterios: usa las intervenciones y costos que ya existen.
// No reemplaza R3.3c: un síntoma realmente desconocido sigue quedando pendiente.
// Se aplica después de Grupo_20_PG3_diagnostico.cypher.
// =============================================================================

// 1. Redacciones que declaran una intervención ya conocida.
UNWIND [
  {id:'PT-INT-BATERIA-DURACION', orden:1,
   descripcion:'Batería que dura poco o no retiene carga',
   patron:'.*bater[ií]a\\s+(?:(?:dura|aguanta|rinde)\\s+(?:poco|pocas|nada|ni\\s+media\\s+hora|\\d+\\s*(?:min|minutos|hs|horas))|se\\s+muere|poca\\s+autonom[ií]a|autonom[ií]a\\s+(?:muy\\s+)?(?:baja|corta)|no\\s+(?:retiene|aguanta|llega|dura)).*'},
  {id:'PT-INT-LIMPIEZA', orden:2,
   descripcion:'Service de limpieza o cambio de pasta térmica',
   patron:'.*(?:service\\s+(?:de\\s+limpieza|general|completo)|limpieza\\s+(?:interna|de\\s+fan|de\\s+cooler|de\\s+ventilador|de\\s+disipador|general)|pasta\\s+t[eé]rmica).*'},
  {id:'PT-INT-SSD-UPGRADE', orden:4,
   descripcion:'Upgrade o reemplazo de disco por SSD',
   patron:'.*(?:(?:upgrade|reemplazo|recambio)\\s+(?:de\\s+)?(?:disco\\s+)?(?:a\\s+)?ssd|(?:cambiar|cambiarse|cambiarle|reemplazar|reemplazarse|pasar|poner)\\s+(?:el\\s+|la\\s+)?(?:disco|hdd)(?:\\s+\\w+)?\\s+(?:por|a)\\s+(?:un\\s+)?ssd|(?:cambio|necesita\\s+cambio)\\s+(?:de\\s+)?disco\\s+(?:por|a)\\s+(?:un\\s+)?ssd).*'}
] AS fila
MERGE (pt:PatronTexto {id: fila.id})
SET pt.patron = fila.patron,
    pt.orden = fila.orden,
    pt.descripcion = fila.descripcion,
    pt.tratamiento = 'intervencion',
    pt.ambito = null
RETURN count(pt) AS patrones_intervencion;

// 2. Vínculo con la intervención y el costo que ya existen en el grafo.
UNWIND [
  {patron:'PT-INT-BATERIA-DURACION', intervencion:'INT-PT-BATERIA', tarea:'bateria'},
  {patron:'PT-INT-LIMPIEZA', intervencion:'INT-PT-TERMICO', tarea:'service_termico'},
  {patron:'PT-INT-SSD-UPGRADE', intervencion:'INT-PT-DISCO', tarea:'ssd_upgrade'}
] AS fila
MATCH (pt:PatronTexto {id: fila.patron}), (c:CostoReparacion {tarea: fila.tarea})
MERGE (i:Intervencion {id: fila.intervencion})
MERGE (pt)-[:APLICA_INTERVENCION]->(i)
MERGE (i)-[:SE_COSTEA_CON]->(c)
RETURN count(*) AS vinculos;

// 3. Redacciones que no describen una falla: se descartan como evidencia.
//    El riesgo de obsolescencia y el plan de RAM ya salen de los hechos estructurados.
UNWIND [
  {id:'PT-DESC-SIN-W11', orden:0,
   descripcion:'Falta de soporte de Windows 11 (lo evalúa SM2, no es una falla)',
   patron:'.*(?:(?:sin|falta\\s+de|no\\s+tiene)\\s+soporte\\s+(?:para\\s+)?windows\\s*11|no\\s+soporta\\s+windows\\s*11|sin\\s+windows\\s*11).*'},
  {id:'PT-DESC-EQUIPO-ANTIGUO', orden:0,
   descripcion:'Equipo antiguo (lo evalúa SM2 por antigüedad, no es una falla)',
   patron:'.*\\b(equipo|notebook|m[aá]quina|computadora)\\s+(?:antigu|viej)[oa]\\b.*'},
  {id:'PT-DESC-UPGRADE-RAM', orden:0,
   descripcion:'Upgrade de memoria declarado (lo resuelve el plan por hechos)',
   patron:'.*(?:upgrade|ampliaci[oó]n|ampliar(?:le|la)?|mejora)\s+(?:de\s+)?(?:memoria|ram).*'}
] AS fila
MERGE (pt:PatronTexto {id: fila.id})
SET pt.patron = fila.patron,
    pt.orden = fila.orden,
    pt.descripcion = fila.descripcion,
    pt.tratamiento = 'descartar',
    pt.ambito = null
RETURN count(pt) AS patrones_descarte;

// 4. Cargador faltante: el patrón base sólo cubre "sin cargador".
UNWIND [
  {id:'PT-INT-CARGADOR-FALTA', orden:7,
   descripcion:'Cargador no incluido',
   patron:'.*(?:falta\\s+(?:el\\s+)?cargador|no\\s+(?:tiene|incluye|viene\\s+con)\\s+cargador|cargador\\s+no\\s+incluido).*'}
] AS fila
MERGE (pt:PatronTexto {id: fila.id})
SET pt.patron = fila.patron, pt.orden = fila.orden,
    pt.descripcion = fila.descripcion, pt.tratamiento = 'intervencion', pt.ambito = null
WITH pt, fila
MATCH (c:CostoReparacion {tarea:'cargador'})
MERGE (i:Intervencion {id:'INT-PT-CARGADOR'})
MERGE (pt)-[:APLICA_INTERVENCION]->(i)
MERGE (i)-[:SE_COSTEA_CON]->(c)
RETURN count(pt) AS patrones_cargador;

// 5. "Levanta temperatura": otra redacción de la misma intervención térmica.
UNWIND [
  {id:'PT-INT-TEMPERATURA-LEVANTA', orden:2,
   descripcion:'Levanta temperatura',
   patron:'.*(?:levanta|sube|toma)\\s+(?:la\\s+)?temperatura.*'}
] AS fila
MERGE (pt:PatronTexto {id: fila.id})
SET pt.patron = fila.patron, pt.orden = fila.orden,
    pt.descripcion = fila.descripcion, pt.tratamiento = 'intervencion', pt.ambito = null
WITH pt
MATCH (c:CostoReparacion {tarea:'service_termico'})
MERGE (i:Intervencion {id:'INT-PT-TERMICO'})
MERGE (pt)-[:APLICA_INTERVENCION]->(i)
MERGE (i)-[:SE_COSTEA_CON]->(c)
RETURN count(pt) AS patrones_temperatura;
