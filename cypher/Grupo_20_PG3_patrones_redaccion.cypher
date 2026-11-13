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
   patron:'.*bater[ií]a\\s+(?:(?:dura|aguanta|rinde)\\s+(?:poco|pocas|\\d+\\s*(?:min|minutos|hs|horas))|poca\\s+autonom[ií]a|no\\s+retiene).*'},
  {id:'PT-INT-LIMPIEZA', orden:2,
   descripcion:'Service de limpieza o cambio de pasta térmica',
   patron:'.*(service\\s+de\\s+limpieza|limpieza\\s+(?:interna|de\\s+fan|general)|pasta\\s+t[eé]rmica).*'},
  {id:'PT-INT-SSD-UPGRADE', orden:4,
   descripcion:'Upgrade o reemplazo de disco por SSD',
   patron:'.*(?:upgrade|reemplazo|cambio)\\s+(?:de\\s+)?(?:disco\\s+)?(?:a\\s+)?ssd.*'}
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
   patron:'.*(?:(?:sin|falta\\s+de)\\s+soporte\\s+(?:para\\s+)?windows\\s*11|no\\s+soporta\\s+windows\\s*11|sin\\s+windows\\s*11).*'},
  {id:'PT-DESC-EQUIPO-ANTIGUO', orden:0,
   descripcion:'Equipo antiguo (lo evalúa SM2 por antigüedad, no es una falla)',
   patron:'.*\\b(equipo|notebook|m[aá]quina|computadora)\\s+antigu[oa]\\b.*'},
  {id:'PT-DESC-UPGRADE-RAM', orden:0,
   descripcion:'Upgrade de memoria declarado (lo resuelve el plan por hechos)',
   patron:'.*(?:upgrade|ampliaci[oó]n|mejora)\\s+(?:de\\s+)?(?:memoria|ram).*'}
] AS fila
MERGE (pt:PatronTexto {id: fila.id})
SET pt.patron = fila.patron,
    pt.orden = fila.orden,
    pt.descripcion = fila.descripcion,
    pt.tratamiento = 'descartar',
    pt.ambito = null
RETURN count(pt) AS patrones_descarte;
