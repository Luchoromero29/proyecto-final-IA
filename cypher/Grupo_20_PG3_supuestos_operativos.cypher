// =============================================================================
// EvalTIC — Supuestos operativos del motor experto (aditivo e idempotente)
//
// Declara, como DATO del grafo, qué asume el sistema cuando un aviso no informa un
// valor que participa de una regla. No crea reglas ni costos: sólo nombra el supuesto,
// lo justifica y lo vincula a la condición que lo usa, para que el motor pueda informarlo
// en la respuesta en lugar de aplicarlo en silencio.
//
// Devolución de la cátedra (PI4 SM1): "los valores por defecto solamente pueden utilizarse
// si están definidos como supuestos operativos en la base de conocimiento y la explicación
// informa esa condición".
//
// Alcance: un solo supuesto.
//   SUP-SM1-BAT-CICLOS — si el aviso informa la salud de la batería pero no los ciclos de
//   carga, y la salud está por debajo de CE-01 (bateria_reemplazo), la regla crisp
//   SM1-BAT-CRISP reemplaza la batería. El motor NO inventa un número de ciclos: asume el
//   reemplazo y debe decirlo.
// La temperatura ausente no es un supuesto: queda como dato pendiente (ver
// Grupo_20_PG3_correcciones_minimas.cypher, CE-31/CE-32).
//
// No se aplica a la base con el loader: se aplica con scripts/base_mejoras.sh, después de
// Grupo_20_PG3_politicas_sm1_acciones.cypher, que es quien crea la condición.
// =============================================================================

MERGE (s:SupuestoOperativo {id:'SUP-SM1-BAT-CICLOS'})
SET s.campo = 'ciclos',
    s.texto = 'Ciclos de batería no informados: se asume el reemplazo de la batería (R1.2, supuesto conservador)',
    s.justificacion = 'Sin ciclos no se puede distinguir desgaste por uso de batería sana; el sistema elige la opción conservadora y no inventa un número de ciclos.',
    s.efecto = 'SM1-BAT-CRISP reemplaza la batería cuando la salud está por debajo de CE-01 (bateria_reemplazo)',
    s.version = 'v1',
    s.estado_validacion = 'Provisional',
    s.fuente = 'Devolución de la cátedra (PI4 SM1) · a validar con el experto M. Romero',
    s.representacion_version = 'supuestos-operativos-v1'
WITH s
OPTIONAL MATCH (c:Condicion {id:'CND-SM1-BAT-CRISP-CICLOS'})
FOREACH (cond IN CASE WHEN c IS NULL THEN [] ELSE [c] END |
  MERGE (cond)-[:ASUME]->(s))
RETURN s.id AS supuesto,
       s.campo AS campo,
       s.estado_validacion AS estado,
       [(c:Condicion)-[:ASUME]->(s) | c.id] AS condiciones_vinculadas;
