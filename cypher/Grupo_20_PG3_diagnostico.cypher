// =============================================================================
// EvalTIC — B2: diagnóstico técnico y decisiones de SM1 en el grafo.
//
// Script ADITIVO e IDEMPOTENTE. No borra nada y NO reescribe criterios, costos ni
// reglas existentes: sólo crea conocimiento nuevo con identificadores propios
// (FS-, PT-, DIA-, SM1-*, R3.3c, CE-31, CE-32) y enlaces nuevos desde esos nodos.
//
// Qué resuelve: los síntomas afirmados en el aviso ("no prende", "no carga",
// "se apaga sola") se reconocen con patrones del grafo y quedan en verificación
// pendiente hasta que el operador aporte un diagnóstico confirmado. Las fallas sin
// tratamiento conocido tampoco pueden terminar en una compra favorable. Todas las
// reparaciones, sus costos y las decisiones de SM1 salen de estas consultas.
//
// Todo el conocimiento nuevo es PROVISIONAL: no está validado por el experto
// (Matías Romero) y la fuente queda declarada en cada nodo.
// =============================================================================

// 0. Marco del síntoma: misma jerarquía Frame/INSTANCIA_DE que el resto del grafo.
MERGE (marco:Frame {nombre:'FallaSintoma'})
ON CREATE SET marco.descripcion = 'Síntoma de falla que exige diagnóstico técnico antes de decidir',
              marco.estado_validacion = 'Provisional',
              marco.version = 'v1',
              marco.fuente = 'Política Provisional B2 acordada para los tres síntomas · a validar con el experto'
WITH marco
MATCH (falla:Frame {nombre:'Falla'})
MERGE (marco)-[:ES_UN]->(falla);

// 1. Regla de verificación pendiente y reglas de acción de SM1.
//    Las reglas de acción llevan el campo o el criterio que las dispara y el costo
//    que ordenan: la decisión y el monto viven acá, no en Python.
MERGE (r:Regla {id:'R3.3c'})
SET r.texto = 'SI el aviso afirma un síntoma de falla relevante Y no hay diagnóstico confirmado por el operador ENTONCES DictamenTecnico = Verificacion_pendiente (SolicitarVerificacion)',
    r.estado = 'Provisional',
    r.tipo = 'Contextual',
    r.implementada = true,
    r.estado_validacion = 'Provisional',
    r.version = 'v1',
    r.fuente = 'Política Provisional B2 · el carácter exhaustivo del catálogo de síntomas queda a validar con el experto';

UNWIND [
  {id:'SM1-BAT-CRISP', tarea:'bateria', orden:1, campo:null, valor:null, requiere_plan:false, cuenta:true,
   texto:'SI salud de batería < CE bateria_reemplazo Y no hay ciclos informados ENTONCES reemplazo de batería'},
  {id:'SM1-TER-CRISP', tarea:'service_termico', orden:2, campo:null, valor:null, requiere_plan:false, cuenta:true,
   texto:'SI se informa throttling térmico Y no hay temperatura ENTONCES service térmico'},
  {id:'SM1-RAM-ACCION', tarea:'ram_upgrade', orden:3, campo:null, valor:null, requiere_plan:false, cuenta:true,
   texto:'SI RAM informada < CE ram_objetivo ENTONCES ampliación de RAM'},
  {id:'SM1-DISCO-ACCION', tarea:'ssd_upgrade', orden:4, campo:null, valor:null, requiere_plan:false, cuenta:true,
   texto:'SI el disco informado es HDD ENTONCES reemplazo por SSD'},
  {id:'SM1-PANTALLA-ACCION', tarea:'pantalla', orden:5, campo:'pantalla_danada', valor:true, requiere_plan:false, cuenta:true,
   texto:'SI el aviso informa pantalla dañada ENTONCES reemplazo de pantalla'},
  {id:'SM1-TECLADO-ACCION', tarea:'teclado', orden:6, campo:'teclado_danado', valor:true, requiere_plan:false, cuenta:true,
   texto:'SI el aviso informa teclado dañado ENTONCES reemplazo de teclado'},
  {id:'SM1-CARGADOR-ACCION', tarea:'cargador', orden:7, campo:'cargador_incluido', valor:false, requiere_plan:false, cuenta:true,
   texto:'SI el aviso informa que no incluye cargador ENTONCES reposición de cargador'},
  {id:'SM1-MANO-OBRA-ACCION', tarea:'mano_de_obra', orden:9, campo:null, valor:null, requiere_plan:true, cuenta:false,
   texto:'SI el plan tiene intervenciones ENTONCES mano de obra y control de calidad (no cuenta como intervención, R3.6)'}
] AS fila
MERGE (r:Regla {id: fila.id})
SET r.tarea = fila.tarea,
    r.orden = fila.orden,
    r.campo = fila.campo,
    r.valor = fila.valor,
    r.requiere_plan = fila.requiere_plan,
    r.cuenta_como_intervencion = fila.cuenta,
    r.texto = fila.texto,
    r.estado = 'Provisional',
    r.tipo = 'Heurística',
    r.implementada = true,
    r.estado_validacion = 'Provisional',
    r.version = 'v1',
    r.fuente = 'Migración B2 de las políticas que decidía Python · umbrales y costos se leen de CriterioExperto y CostoReparacion'
WITH r, fila
MATCH (c:CostoReparacion {tarea: fila.tarea})
MERGE (r)-[:ORDENA]->(c)
RETURN count(*) AS reglas_de_accion;

// 2. Categorías difusas que obligan a intervenir, con su costo (misma política vigente).
UNWIND [
  {base:'SM1-BAT', categorias:['Obligatoria'], tarea:'bateria', orden:1},
  {base:'SM1-TER', categorias:['Obligatoria','Recomendada'], tarea:'service_termico', orden:2}
] AS fila
MATCH (rd:ReglaDifusa {base: fila.base}), (c:CostoReparacion {tarea: fila.tarea})
MERGE (rd)-[ob:OBLIGA]->(c)
SET ob.categorias = fila.categorias,
    ob.orden = fila.orden,
    ob.estado_validacion = 'Provisional',
    ob.version = 'v1',
    ob.fuente = 'Migración B2: la categoría que ordena la intervención estaba en Python'
RETURN count(*) AS acciones_difusas;

// 3. Caídas de frecuencia sintéticas: pasan de constantes de Python a criterios del grafo.
MERGE (c31:CriterioExperto {id:'CE-31'})
SET c31.nombre = 'caida_termica_sin_throttling',
    c31.valor = 5,
    c31.unidad = 'pp',
    c31.estado_validacion = 'Provisional',
    c31.version = 'v1',
    c31.en_uso = true,
    c31.fuente = 'Valor sintético usado por SM1-TER cuando el aviso no informa caída de frecuencia · reemplazar por una medición acordada con el experto';

MERGE (c32:CriterioExperto {id:'CE-32'})
SET c32.nombre = 'caida_termica_con_throttling',
    c32.valor = 20,
    c32.unidad = 'pp',
    c32.estado_validacion = 'Provisional',
    c32.version = 'v1',
    c32.en_uso = true,
    c32.fuente = 'Valor sintético usado por SM1-TER cuando el aviso informa throttling · reemplazar por una medición acordada con el experto';

// 4. Síntomas acordados (política Provisional). No es un catálogo exhaustivo.
UNWIND [
  {id:'FS-NO-PRENDE', descripcion:'No prende'},
  {id:'FS-NO-CARGA', descripcion:'No carga'},
  {id:'FS-SE-APAGA-SOLA', descripcion:'Se apaga sola'}
] AS fila
MERGE (s:Falla:FallaSintoma {id: fila.id})
SET s.descripcion = fila.descripcion,
    s.requiere_diagnostico = true,
    s.estado_validacion = 'Provisional',
    s.version = 'v1',
    s.fuente = 'Política Provisional B2 (no prende / no carga / se apaga sola) · el síntoma no prueba por sí solo daño irreparable ni equipo sano'
WITH s
MATCH (marco:Frame {nombre:'FallaSintoma'}), (falla:Frame {nombre:'Falla'})
MERGE (s)-[:INSTANCIA_DE]->(marco)
MERGE (s)-[:INSTANCIA_DE]->(falla)
RETURN count(*) AS sintomas;

// 5. Diagnósticos que puede confirmar el operador y la reparación que el grafo conoce.
UNWIND [
  {id:'DIA-BATERIA', nombre:'bateria', orden:1, descripcion:'Batería agotada o sin retención de carga',
   reparable:true, tarea:'bateria',
   motivo:'Batería sin retención de carga confirmada en la verificación técnica'},
  {id:'DIA-CARGADOR', nombre:'cargador', orden:7, descripcion:'Cargador o fuente defectuosa',
   reparable:true, tarea:'cargador',
   motivo:'Cargador defectuoso confirmado en la verificación técnica'},
  {id:'DIA-PANTALLA', nombre:'pantalla', orden:5, descripcion:'Módulo de pantalla dañado',
   reparable:true, tarea:'pantalla',
   motivo:'Pantalla dañada confirmada en la verificación técnica'},
  {id:'DIA-TECLADO', nombre:'teclado', orden:6, descripcion:'Teclado dañado',
   reparable:true, tarea:'teclado',
   motivo:'Teclado dañado confirmado en la verificación técnica'},
  {id:'DIA-TERMICO', nombre:'termico', orden:2, descripcion:'Sobrecalentamiento con cuelgues',
   reparable:true, tarea:'service_termico',
   motivo:'Falla térmica confirmada en la verificación técnica'},
  {id:'DIA-ALMACENAMIENTO', nombre:'almacenamiento', orden:4, descripcion:'Disco mecánico lento o con fallas',
   reparable:true, tarea:'ssd_upgrade',
   motivo:'Falla de almacenamiento confirmada en la verificación técnica'},
  {id:'DIA-PLACA', nombre:'placa', descripcion:'Daño irreparable de placa',
   reparable:false, tarea:null,
   motivo:'Daño de placa irreparable confirmado en la verificación técnica'}
] AS fila
MERGE (d:Diagnostico {id: fila.id})
SET d.orden = fila.orden,
    d.nombre = fila.nombre,
    d.descripcion = fila.descripcion,
    d.reparable = fila.reparable,
    d.motivo = fila.motivo,
    d.estado_validacion = 'Provisional',
    d.version = 'v1',
    d.fuente = 'Migración B2 de las reparaciones ya vigentes · el diagnóstico lo confirma el operador, no el aviso ni el LLM'
RETURN count(*) AS diagnosticos;

UNWIND [
  {diagnostico:'DIA-BATERIA', tarea:'bateria'},
  {diagnostico:'DIA-CARGADOR', tarea:'cargador'},
  {diagnostico:'DIA-PANTALLA', tarea:'pantalla'},
  {diagnostico:'DIA-TECLADO', tarea:'teclado'},
  {diagnostico:'DIA-TERMICO', tarea:'service_termico'},
  {diagnostico:'DIA-ALMACENAMIENTO', tarea:'ssd_upgrade'}
] AS fila
MATCH (d:Diagnostico {id: fila.diagnostico}), (c:CostoReparacion {tarea: fila.tarea})
MERGE (d)-[:SE_REPARA_CON]->(c)
RETURN count(*) AS diagnosticos_con_reparacion;

MATCH (d:Diagnostico {id:'DIA-PLACA'}), (r:Regla {id:'R1.1'})
MERGE (d)-[:ACTIVA]->(r);

// 6. Patrones de texto del aviso. Toda palabra clave que decidía el negocio en Python
//    pasa acá: así se reconoce el síntoma por la evidencia del aviso aunque el LLM lo
//    omita o lo clasifique mal.
//    Tratamientos: inviable (R1.1), verificar (diagnóstico pendiente),
//    intervencion (reparación conocida con costo del grafo) y descartar (no es una falla).
UNWIND [
  {id:'PT-CAT-QUEMADO', orden:1, descripcion:'Componente quemado', tratamiento:'inviable', patron:'.*quemad.*'},
  {id:'PT-CAT-CORTO', orden:1, descripcion:'Componente en cortocircuito', tratamiento:'inviable', patron:'.*\\ben\\s+corto\\b.*'},
  {id:'PT-CAT-CORTOCIRCUITO', orden:1, descripcion:'Cortocircuito', tratamiento:'inviable', patron:'.*cortocircuito.*'},
  {id:'PT-CAT-NO-VIDEO', orden:1, descripcion:'No da video', tratamiento:'inviable', patron:'.*no\\s+da\\s+video.*'},
  {id:'PT-CAT-PERFORADO', orden:1, descripcion:'Placa perforada', tratamiento:'inviable', patron:'.*perforad.*'},
  {id:'PT-CAT-PISTA-ROTA', orden:1, descripcion:'Pista de placa rota', tratamiento:'inviable', patron:'.*pista\\s+rota.*'},
  {id:'PT-CAT-SULFATACION', orden:1, descripcion:'Sulfatación por derrame', tratamiento:'inviable', patron:'.*sulfataci.*'},
  {id:'PT-CAT-INSALVABLE', orden:1, descripcion:'Falla declarada insalvable', tratamiento:'inviable', patron:'.*insalvable.*'},

  {id:'PT-SIN-NO-PRENDE', orden:1, descripcion:'No prende', tratamiento:'verificar', patron:'.*\\bno\\s+prende\\b.*'},
  {id:'PT-SIN-NO-CARGA', orden:1, descripcion:'No carga', tratamiento:'verificar', patron:'.*\\bno\\s+carga\\b.*'},
  {id:'PT-SIN-SE-APAGA', orden:1, descripcion:'Se apaga sola', tratamiento:'verificar', patron:'.*\\bse\\s+apaga(\\s+sola|\\s+solo)?\\b.*'},

  {id:'PT-INT-PANTALLA', orden:5, descripcion:'Pantalla dañada', tratamiento:'intervencion', patron:'.*\\b(pantalla|display|rayas?)\\b.*'},
  {id:'PT-INT-TECLADO', orden:6, descripcion:'Teclado dañado', tratamiento:'intervencion', patron:'.*\\b(teclado|tecla|teclas)\\b.*'},
  {id:'PT-INT-CARGADOR', orden:7, descripcion:'Sin cargador', tratamiento:'intervencion', patron:'.*sin\\s+cargador.*'},
  {id:'PT-INT-BATERIA', orden:1, descripcion:'Batería agotada o degradada', tratamiento:'intervencion', patron:'.*bater[ií]a\\s+(agotad|agotada|muert|dañad|dañada|hinchad|hinchada|inflad|baja|no\\s+retiene).*'},
  {id:'PT-INT-DISCO', orden:4, descripcion:'Disco mecánico', tratamiento:'intervencion', patron:'.*(\\bhdd\\b|disco\\s+(r[ií]gido|mec[aá]nico)).*'},
  {id:'PT-INT-TERMICO', orden:2, descripcion:'Sobrecalentamiento', tratamiento:'intervencion', patron:'.*\\b(calienta|sobrecalienta|t[eé]rmicos?)\\b.*'},

  {id:'PT-DESC-BATERIA-MEDIDA', orden:0, descripcion:'Nivel de batería medido en el aviso (lo evalúa SM1-BAT)',
   tratamiento:'descartar', patron:'.*bater[ií]a\\s+(al\\s+)?\\d{1,3}\\s*%.*'},
  {id:'PT-DESC-POSITIVO', orden:0, descripcion:'Descripción positiva del componente', tratamiento:'descartar',
   patron:'.*\\b(perfect[oa]s?|impecables?|excelentes?|funciona|funcionando)\\b.*'},
  {id:'PT-DESC-SIN-DETALLES', orden:0, descripcion:'Sin detalles ni rayas', tratamiento:'descartar', patron:'.*\\bsin\\s+(detalles?|rayas?)\\b.*'},
  {id:'PT-DESC-NUEVO', orden:0, descripcion:'Componente nuevo', tratamiento:'descartar', patron:'.*\\bnuev[oa]s?\\b.*'},
  {id:'PT-DESC-CONFORME', orden:0, descripcion:'Estado conforme', tratamiento:'descartar', patron:'.*\\b(ok|bien)\\b.*'},
  {id:'PT-DESC-SIN-FALLAS', orden:0, descripcion:'El aviso declara que no hay fallas', tratamiento:'descartar',
   patron:'.*(no\\s+tiene\\s+fallas|sin\\s+fallas|ninguna\\s+falla).*'}
] AS fila
MERGE (pt:PatronTexto {id: fila.id})
SET pt.orden = fila.orden,
    pt.descripcion = fila.descripcion,
    pt.tratamiento = fila.tratamiento,
    pt.patron = fila.patron,
    pt.estado_validacion = 'Provisional',
    pt.version = 'v1',
    pt.fuente = 'Migración B2 de las palabras clave que decidían en Python y de la política Provisional de los tres síntomas'
RETURN count(*) AS patrones;

// 6.1 Patrones irreversibles: activan R1.1 (se conserva la semántica vigente, no se reinterpreta).
UNWIND ['PT-CAT-QUEMADO','PT-CAT-CORTO','PT-CAT-CORTOCIRCUITO','PT-CAT-NO-VIDEO',
        'PT-CAT-PERFORADO','PT-CAT-PISTA-ROTA','PT-CAT-SULFATACION','PT-CAT-INSALVABLE'] AS patron
MATCH (pt:PatronTexto {id: patron}), (r:Regla {id:'R1.1'})
MERGE (pt)-[:ACTIVA]->(r)
RETURN count(*) AS patrones_irreversibles;

// 6.2 Patrones de síntoma: evidencia del síntoma y regla de verificación pendiente.
UNWIND [
  {patron:'PT-SIN-NO-PRENDE', sintoma:'FS-NO-PRENDE'},
  {patron:'PT-SIN-NO-CARGA', sintoma:'FS-NO-CARGA'},
  {patron:'PT-SIN-SE-APAGA', sintoma:'FS-SE-APAGA-SOLA'}
] AS fila
MATCH (pt:PatronTexto {id: fila.patron}), (s:FallaSintoma {id: fila.sintoma}), (r:Regla {id:'R3.3c'})
MERGE (pt)-[:EVIDENCIA_DE]->(s)
MERGE (s)-[:ACTIVA]->(r)
RETURN count(*) AS patrones_de_sintoma;

// 6.3 Patrones de reparación conocida: intervención y costo del grafo (con el campo que manda).
UNWIND [
  {patron:'PT-INT-PANTALLA', intervencion:'INT-PT-PANTALLA', tarea:'pantalla'},
  {patron:'PT-INT-TECLADO', intervencion:'INT-PT-TECLADO', tarea:'teclado'},
  {patron:'PT-INT-CARGADOR', intervencion:'INT-PT-CARGADOR', tarea:'cargador'},
  {patron:'PT-INT-BATERIA', intervencion:'INT-PT-BATERIA', tarea:'bateria'},
  {patron:'PT-INT-DISCO', intervencion:'INT-PT-DISCO', tarea:'ssd_upgrade'},
  {patron:'PT-INT-TERMICO', intervencion:'INT-PT-TERMICO', tarea:'service_termico'}
] AS fila
MATCH (pt:PatronTexto {id: fila.patron}), (c:CostoReparacion {tarea: fila.tarea})
MERGE (i:Intervencion {id: fila.intervencion})
SET i.tipo_tarea = c.descripcion,
    i.origen = fila.patron,
    i.es_mandatoria = true,
    i.estado_validacion = 'Provisional',
    i.version = 'v1',
    i.fuente = 'Migración B2: el costo se lee de CostoReparacion, no se duplica en la intervención'
MERGE (pt)-[:APLICA_INTERVENCION]->(i)
MERGE (i)-[:SE_COSTEA_CON]->(c)
RETURN count(*) AS patrones_con_reparacion;

// 6.4 El campo estructurado manda sobre el texto: "sin cargador" no aplica si el aviso
//     informa que el cargador está incluido (misma política que ya tenía el motor).
MATCH (pt:PatronTexto {id:'PT-INT-CARGADOR'})
SET pt.campo = 'cargador_incluido';
