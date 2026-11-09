// =====================================================================
// EvalTIC — Grupo 20 (5K09) — Actividad PG2, Unidad 1
// Script 1 de 2: CARGA DE LA BASE DE CONOCIMIENTO E INFERENCIA
//
// Integra el modelo consolidado del PG1 (SM1 Tapia, SM2 Navarta, SM3 Romero)
// con la lógica difusa de los tres PI3.
//
// Cómo usarlo:
//   - Pegar el archivo completo en Neo4j Aura (Query) y ejecutar. Si el editor
//     no acepta varias sentencias juntas, ejecutar bloque por bloque.
//   - El bloque 0 BORRA TODA LA BASE. Usar una instancia propia.
//   - Es reproducible: se puede correr desde cero las veces que haga falta.
//
// Bloques:
//    0. Limpieza                       10. SM1: falla catastrófica (R1.1) y R3.2
//    1. Restricciones                  11. SM1 difuso: batería y service térmico
//    2. Submódulos                     12. SM1: plan y costo de reacondicionamiento
//    3. Frames, herencia y slots       13. SM2: rechazo comercial (R3.1b)
//    4. Red semántica entre frames     14. SM2 difuso: riesgo de obsolescencia
//    5. Criterios expertos             15. SM2 difuso: demanda comercial
//    6. Reglas crisp (PG1)             16. SM3: completitud de datos (R3.3b)
//    7. Conocimiento difuso (3 PI3)    17. SM3: indicadores, R3.7 y R3.8
//    8. Casos de prueba                18. SM3 difuso: conveniencia de compra
//    9. SM3: filtros de bloqueo        19. Decisión final
//                                      20. Vinculación instancia → frame
//
// El motor difuso (M1, M2, M3) es genérico: sirve para cualquier base de
// reglas. Se repite igual en los bloques 11, 14, 15 y 18.
// =====================================================================


// =====================================================================
// 0. LIMPIEZA
// =====================================================================
MATCH (n) DETACH DELETE n;


// =====================================================================
// 1. RESTRICCIONES
// =====================================================================
CREATE CONSTRAINT submodulo_id IF NOT EXISTS FOR (n:Submodulo) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT frame_nombre IF NOT EXISTS FOR (n:Frame) REQUIRE n.nombre IS UNIQUE;
CREATE CONSTRAINT slot_id IF NOT EXISTS FOR (n:Slot) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT criterio_nombre IF NOT EXISTS FOR (n:CriterioExperto) REQUIRE n.nombre IS UNIQUE;
CREATE CONSTRAINT regla_id IF NOT EXISTS FOR (n:Regla) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT regla_difusa_id IF NOT EXISTS FOR (n:ReglaDifusa) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT variable_nombre IF NOT EXISTS FOR (n:VariableDifusa) REQUIRE n.nombre IS UNIQUE;
CREATE CONSTRAINT conjunto_id IF NOT EXISTS FOR (n:ConjuntoDifuso) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT version_id IF NOT EXISTS FOR (n:VersionParametros) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT equipo_id IF NOT EXISTS FOR (n:Equipo) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT operacion_id IF NOT EXISTS FOR (n:Operacion) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT evaluacion_id IF NOT EXISTS FOR (n:Evaluacion) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT decision_id IF NOT EXISTS FOR (n:Decision) REQUIRE n.id IS UNIQUE;


// =====================================================================
// 2. SUBMÓDULOS
// =====================================================================
UNWIND [
  {id:'SM0', nombre:'Ingesta y normalización (transversal)', responsable:'Grupo'},
  {id:'SM1', nombre:'Diagnóstico Técnico y Reacondicionamiento', responsable:'Tapia, Álvaro'},
  {id:'SM2', nombre:'Valuación Comercial y Demanda', responsable:'Navarta, Leonel'},
  {id:'SM3', nombre:'Evaluación de la Operación y Decisión', responsable:'Romero, Luciano'}
] AS s
CREATE (:Submodulo {id: s.id, nombre: s.nombre, responsable: s.responsable});


// =====================================================================
// 3. FRAMES, HERENCIA Y SLOTS (diccionario de frames del PG1, sección f,
//    ampliado con los slots que usan las variables difusas de los PI3)
// =====================================================================
UNWIND [
  {nombre:'Equipo',                   sm:null,  descripcion:'Computadora ofrecida (común a todos los módulos)'},
  {nombre:'Notebook',                 sm:null,  descripcion:'Equipo portátil'},
  {nombre:'PC_Escritorio',            sm:null,  descripcion:'Equipo de escritorio'},
  {nombre:'Publicacion',              sm:'SM3', descripcion:'Aviso del vendedor con el precio pedido'},
  {nombre:'Componente',               sm:'SM1', descripcion:'Pieza de hardware del equipo'},
  {nombre:'Bateria',                  sm:'SM1', descripcion:'Acumulador de litio — entrada de la base difusa SM1-BAT'},
  {nombre:'Medicion',                 sm:'SM1', descripcion:'Dato medido en el taller (prueba de estrés)'},
  {nombre:'Falla',                    sm:'SM1', descripcion:'Problema detectado en el equipo'},
  {nombre:'FallaModular',             sm:'SM1', descripcion:'Falla subsanable con recambio estándar'},
  {nombre:'FallaCatastrofica',        sm:'SM1', descripcion:'Daño estructural irreparable o sin repuesto'},
  {nombre:'Intervencion',             sm:'SM1', descripcion:'Tarea de reacondicionamiento'},
  {nombre:'Repuesto',                 sm:'SM1', descripcion:'Pieza necesaria (compartida con SM2)'},
  {nombre:'PlanReacondicionamiento',  sm:'SM1', descripcion:'Conjunto de intervenciones planificadas'},
  {nombre:'CostoReacondicionamiento', sm:'SM1', descripcion:'Repuestos + mano de obra del plan'},
  {nombre:'DictamenTecnico',          sm:'SM1', descripcion:'Fisicamente_Reparable | Inviabilidad_Fisica_Insalvable'},
  {nombre:'IndicadorMercado',         sm:'SM2', descripcion:'Rotación y disponibilidad de repuestos del modelo'},
  {nombre:'ValorMercadoAjustado',     sm:'SM2', descripcion:'Precio de reventa en el estado final reacondicionado'},
  {nombre:'DemandaComercial',         sm:'SM2', descripcion:'Liquidez del modelo (inferida por la base SM2-DEM)'},
  {nombre:'RiesgoObsolescencia',      sm:'SM2', descripcion:'Riesgo de pérdida de valor (inferido por la base SM2-RIE)'},
  {nombre:'DictamenComercial',        sm:'SM2', descripcion:'Veredicto comercial de SM2'},
  {nombre:'Bloqueo',                  sm:'SM3', descripcion:'Bloqueo de cuenta, firmware o institucional'},
  {nombre:'Operacion',                sm:'SM3', descripcion:'Evaluación de SM3 sobre una publicación'},
  {nombre:'IndicadoresEconomicos',    sm:'SM3', descripcion:'Margen neto, margen requerido, ratio de reparación'},
  {nombre:'CriterioExperto',          sm:null,  descripcion:'Umbral versionado que consultan las reglas'},
  {nombre:'Evaluacion',               sm:null,  descripcion:'Resultado de una inferencia difusa con su traza'},
  {nombre:'Decision',                 sm:'SM3', descripcion:'Salida única del sistema'}
] AS f
CREATE (fr:Frame {nombre: f.nombre, descripcion: f.descripcion})
WITH fr, f
OPTIONAL MATCH (sm:Submodulo {id: f.sm})
FOREACH (x IN CASE WHEN sm IS NULL THEN [] ELSE [sm] END | MERGE (fr)-[:PERTENECE_A]->(x));

UNWIND [
  ['Notebook','Equipo'], ['PC_Escritorio','Equipo'], ['Bateria','Componente'],
  ['FallaModular','Falla'], ['FallaCatastrofica','Falla']
] AS h
MATCH (sub:Frame {nombre: h[0]}), (sup:Frame {nombre: h[1]})
MERGE (sub)-[:ES_UN]->(sup);

UNWIND [
  {f:'Equipo', n:'marca', t:'Cadena', fa:'Obligatorio, 1..1', d:null, dm:null},
  {f:'Equipo', n:'modelo', t:'Cadena', fa:'Obligatorio, 1..1', d:null, dm:null},
  {f:'Equipo', n:'anio_fabricacion', t:'Entero', fa:'2010–2026', d:null, dm:'Entrada de Antiguedad_Hardware (SM2-RIE)'},
  {f:'Equipo', n:'estado_estetico', t:'Enumerado', fa:'Excelente, Bueno, Con_Detalles, Dañado', d:'Bueno', dm:'Escala única SM1/SM2'},
  {f:'Equipo', n:'soporta_windows11', t:'Booleano', fa:'true | false', d:null, dm:'Entrada crisp Soporte_W11 (SM2-RIE)'},
  {f:'Bateria', n:'salud_pct', t:'Real (%)', fa:'[0, 100]', d:null, dm:'Entrada de Salud_Bateria (SM1-BAT)'},
  {f:'Bateria', n:'ciclos_carga', t:'Entero', fa:'>= 0', d:'0', dm:'Entrada de Ciclos_Carga (SM1-BAT)'},
  {f:'Bateria', n:'hinchada', t:'Booleano', fa:'true | false', d:'false', dm:'if-added (true): reemplazo obligatorio crisp, sin pasar por la base difusa'},
  {f:'Bateria', n:'costo_reemplazo_ars', t:'Real (ARS)', fa:'>= 0', d:null, dm:'Costo de la intervención si se agrega al plan'},
  {f:'Medicion', n:'temperatura_c', t:'Real (°C)', fa:'[35, 105]', d:null, dm:'Entrada de Temperatura_CPU (SM1-TER)'},
  {f:'Medicion', n:'caida_frecuencia_pct', t:'Real (%)', fa:'[0, 50]', d:'0', dm:'Entrada de Caida_Frecuencia (SM1-TER)'},
  {f:'DictamenTecnico', n:'resultado', t:'Enumerado', fa:'Fisicamente_Reparable, Inviabilidad_Fisica_Insalvable', d:null, dm:'if-added (Insalvable): activar R3.2'},
  {f:'DictamenTecnico', n:'causa_inviabilidad', t:'Cadena', fa:'Obligatoria si es Insalvable', d:null, dm:'Se copia a la traza'},
  {f:'Intervencion', n:'tipo_tarea', t:'Cadena', fa:'Obligatorio', d:null, dm:null},
  {f:'Intervencion', n:'costo_ars', t:'Real (ARS)', fa:'>= 0', d:'0', dm:null},
  {f:'Intervencion', n:'es_mandatoria', t:'Booleano', fa:'true | false', d:'true', dm:'Obligatoria → true — Recomendada → false (bases SM1-BAT y SM1-TER)'},
  {f:'Intervencion', n:'origen', t:'Cadena', fa:'Regla crisp o base difusa que la generó', d:null, dm:'Trazabilidad'},
  {f:'PlanReacondicionamiento', n:'cantidad_intervenciones', t:'Entero', fa:'>= 0', d:'0', dm:'if-needed: contar intervenciones — lo usa SM3 en R3.6'},
  {f:'CostoReacondicionamiento', n:'monto_total', t:'Real (ARS)', fa:'>= 0', d:'0', dm:'if-needed: suma de costo_ars del plan'},
  {f:'Repuesto', n:'disponibilidad', t:'Enumerado', fa:'Disponible, Bajo_Pedido, Discontinuado', d:'Disponible', dm:'Discontinuado y mandatorio → R1.5 — alimenta el índice de repuestos'},
  {f:'IndicadorMercado', n:'dias_promedio_venta', t:'Entero (días)', fa:'[0, 90]', d:null, dm:'Entrada de Rotacion_Mercado (SM2-DEM)'},
  {f:'IndicadorMercado', n:'indice_repuestos', t:'Real', fa:'[0, 10]', d:null, dm:'Entrada de Disponibilidad_Repuestos (SM2-RIE)'},
  {f:'ValorMercadoAjustado', n:'monto_tasado_ars', t:'Real (ARS)', fa:'>= 0', d:null, dm:'if-needed: base − depreciaciones + revalorizaciones − penalizaciones (R2.8)'},
  {f:'DemandaComercial', n:'nivel', t:'Enumerado', fa:'Alta, Media, Baja', d:'Media', dm:'Categoría de la base SM2-DEM — la usa SM3 en R3.4 y R3.8'},
  {f:'DemandaComercial', n:'indice', t:'Real', fa:'[0, 1]', d:null, dm:'Centroide de la base SM2-DEM'},
  {f:'RiesgoObsolescencia', n:'nivel', t:'Enumerado', fa:'Bajo, Medio, Alto', d:'Bajo', dm:'Categoría de la base SM2-RIE — la usa SM3 en R3.4, R3.5 y R3.8'},
  {f:'RiesgoObsolescencia', n:'indice', t:'Real', fa:'[0, 1]', d:null, dm:'Centroide de la base SM2-RIE'},
  {f:'DictamenComercial', n:'veredicto', t:'Enumerado', fa:'Tasable_Comercialmente, Tasable_Con_Advertencia_Riesgo, Rechazo_Comercial_Directo', d:'Tasable_Comercialmente', dm:'if-added (Rechazo): activar R3.1b'},
  {f:'Bloqueo', n:'estado', t:'Enumerado', fa:'Activo, Desconocido, Inactivo', d:null, dm:'Activo y no remediable → R3.1 — Desconocido → R3.3'},
  {f:'Bloqueo', n:'remediable', t:'Booleano', fa:'true | false', d:null, dm:null},
  {f:'Publicacion', n:'precio', t:'Real (ARS)', fa:'> 0', d:null, dm:null},
  {f:'Operacion', n:'estado', t:'Enumerado', fa:'Recibida, Filtrada, Evaluacion_difusa, Verificacion_pendiente, Resuelta', d:'Recibida', dm:null},
  {f:'IndicadoresEconomicos', n:'margen_neto', t:'Real (%)', fa:'(−∞, 100]', d:null, dm:'if-needed: (VMA − precio − costo) / VMA'},
  {f:'IndicadoresEconomicos', n:'margen_requerido', t:'Real (%)', fa:'[0, 100]', d:'CE margen_base', dm:'if-needed: base → R3.4 o R3.5 → R3.6'},
  {f:'IndicadoresEconomicos', n:'ratio_reparacion', t:'Real', fa:'>= 0', d:null, dm:'if-needed: costo / VMA'},
  {f:'IndicadoresEconomicos', n:'contraoferta', t:'Real (ARS)', fa:'>= 0', d:null, dm:'if-needed: VMA − costo − VMA × margen_requerido'},
  {f:'CriterioExperto', n:'valor', t:'Real', fa:'Según unidad', d:null, dm:'if-added: nueva versión'},
  {f:'CriterioExperto', n:'estado_validacion', t:'Enumerado', fa:'Provisional, Validado, Documental', d:'Provisional', dm:'Si es Provisional se advierte en la decisión'},
  {f:'Evaluacion', n:'base', t:'Enumerado', fa:'SM1-BAT, SM1-TER, SM2-RIE, SM2-DEM, SM3-CONV', d:null, dm:'Determina qué reglas difusas se evalúan'},
  {f:'Evaluacion', n:'centroide', t:'Real', fa:'[0, 1]', d:null, dm:'Defuzzificación por centroide'},
  {f:'Evaluacion', n:'categoria', t:'Cadena', fa:'Etiqueta de la variable de salida', d:null, dm:'Conjunto de salida dominante en el centroide'},
  {f:'Decision', n:'tipo', t:'Enumerado', fa:'Comprar, ComprarConOfertaMenor, DescartarPorInviabilidad, DescartarPorRiesgo', d:null, dm:'Exactamente una por operación'},
  {f:'Decision', n:'contraoferta', t:'Real (ARS)', fa:'Solo si es ComprarConOfertaMenor', d:null, dm:null}
] AS s
MATCH (fr:Frame {nombre: s.f})
CREATE (fr)-[:TIENE_SLOT]->(:Slot {id: s.f + '.' + s.n, nombre: s.n, tipo: s.t, faceta: s.fa,
                                   default: s.d, demonio: s.dm});


// =====================================================================
// 4. RED SEMÁNTICA ENTRE FRAMES (PG1, sección e)
// =====================================================================
UNWIND [
  ['Publicacion','OFRECE','Equipo'],
  ['Equipo','TIENE_COMPONENTE','Componente'],
  ['Equipo','TIENE_MEDICION','Medicion'],
  ['Equipo','PRESENTA','Falla'],
  ['Falla','AFECTA_A','Componente'],
  ['Falla','REQUIERE','Intervencion'],
  ['Intervencion','CONSUME','Repuesto'],
  ['Intervencion','FORMA_PARTE_DE','PlanReacondicionamiento'],
  ['PlanReacondicionamiento','GENERA','CostoReacondicionamiento'],
  ['Falla','DETERMINA','DictamenTecnico'],
  ['PlanReacondicionamiento','INFORMA_ESTADO_A','ValorMercadoAjustado'],
  ['Repuesto','INFLUYE_EN','IndicadorMercado'],
  ['IndicadorMercado','INFLUYE_EN','RiesgoObsolescencia'],
  ['IndicadorMercado','INFLUYE_EN','DemandaComercial'],
  ['RiesgoObsolescencia','INFLUYE_EN','DemandaComercial'],
  ['DictamenTecnico','SE_USA_EN','Operacion'],
  ['DictamenComercial','SE_USA_EN','Operacion'],
  ['Bloqueo','SE_USA_EN','Operacion'],
  ['CostoReacondicionamiento','SE_USA_EN','IndicadoresEconomicos'],
  ['ValorMercadoAjustado','SE_USA_EN','IndicadoresEconomicos'],
  ['DemandaComercial','AJUSTA','CriterioExperto'],
  ['RiesgoObsolescencia','AJUSTA','CriterioExperto'],
  ['Operacion','CALCULA','IndicadoresEconomicos'],
  ['IndicadoresEconomicos','SE_COMPARA_CON','CriterioExperto'],
  ['Evaluacion','JUSTIFICA','Intervencion'],
  ['Evaluacion','DETERMINA','RiesgoObsolescencia'],
  ['Evaluacion','DETERMINA','DemandaComercial'],
  ['IndicadoresEconomicos','DETERMINA','Evaluacion'],
  ['Evaluacion','DETERMINA','Decision']
] AS t
MATCH (a:Frame {nombre: t[0]}), (b:Frame {nombre: t[2]})
FOREACH (_ IN CASE WHEN t[1] = 'OFRECE' THEN [1] ELSE [] END | MERGE (a)-[:OFRECE]->(b))
FOREACH (_ IN CASE WHEN t[1] = 'TIENE_COMPONENTE' THEN [1] ELSE [] END | MERGE (a)-[:TIENE_COMPONENTE]->(b))
FOREACH (_ IN CASE WHEN t[1] = 'TIENE_MEDICION' THEN [1] ELSE [] END | MERGE (a)-[:TIENE_MEDICION]->(b))
FOREACH (_ IN CASE WHEN t[1] = 'PRESENTA' THEN [1] ELSE [] END | MERGE (a)-[:PRESENTA]->(b))
FOREACH (_ IN CASE WHEN t[1] = 'AFECTA_A' THEN [1] ELSE [] END | MERGE (a)-[:AFECTA_A]->(b))
FOREACH (_ IN CASE WHEN t[1] = 'REQUIERE' THEN [1] ELSE [] END | MERGE (a)-[:REQUIERE]->(b))
FOREACH (_ IN CASE WHEN t[1] = 'CONSUME' THEN [1] ELSE [] END | MERGE (a)-[:CONSUME]->(b))
FOREACH (_ IN CASE WHEN t[1] = 'FORMA_PARTE_DE' THEN [1] ELSE [] END | MERGE (a)-[:FORMA_PARTE_DE]->(b))
FOREACH (_ IN CASE WHEN t[1] = 'GENERA' THEN [1] ELSE [] END | MERGE (a)-[:GENERA]->(b))
FOREACH (_ IN CASE WHEN t[1] = 'DETERMINA' THEN [1] ELSE [] END | MERGE (a)-[:DETERMINA]->(b))
FOREACH (_ IN CASE WHEN t[1] = 'INFORMA_ESTADO_A' THEN [1] ELSE [] END | MERGE (a)-[:INFORMA_ESTADO_A]->(b))
FOREACH (_ IN CASE WHEN t[1] = 'INFLUYE_EN' THEN [1] ELSE [] END | MERGE (a)-[:INFLUYE_EN]->(b))
FOREACH (_ IN CASE WHEN t[1] = 'SE_USA_EN' THEN [1] ELSE [] END | MERGE (a)-[:SE_USA_EN]->(b))
FOREACH (_ IN CASE WHEN t[1] = 'AJUSTA' THEN [1] ELSE [] END | MERGE (a)-[:AJUSTA]->(b))
FOREACH (_ IN CASE WHEN t[1] = 'CALCULA' THEN [1] ELSE [] END | MERGE (a)-[:CALCULA]->(b))
FOREACH (_ IN CASE WHEN t[1] = 'SE_COMPARA_CON' THEN [1] ELSE [] END | MERGE (a)-[:SE_COMPARA_CON]->(b))
FOREACH (_ IN CASE WHEN t[1] = 'JUSTIFICA' THEN [1] ELSE [] END | MERGE (a)-[:JUSTIFICA]->(b));


// =====================================================================
// 5. CRITERIOS EXPERTOS (PG1, sección f) — versión v1, todos Provisionales
// =====================================================================
UNWIND [
  {id:'CE-01', modulo:'SM1', nombre:'bateria_reemplazo',     valor:75,    unidad:'%'},
  {id:'CE-02', modulo:'SM1', nombre:'ram_soldada_min',       valor:4,     unidad:'GB'},
  {id:'CE-03', modulo:'SM1', nombre:'temperatura_service',   valor:85,    unidad:'°C'},
  {id:'CE-04', modulo:'SM1', nombre:'costo_service_termico', valor:8000,  unidad:'ARS'},
  {id:'CE-05', modulo:'SM2', nombre:'bateria_depreciacion',  valor:80,    unidad:'%'},
  {id:'CE-06', modulo:'SM2', nombre:'bateria_factor',        valor:10,    unidad:'%'},
  {id:'CE-07', modulo:'SM2', nombre:'deprec_danado',         valor:15,    unidad:'%'},
  {id:'CE-08', modulo:'SM2', nombre:'deprec_detalles',       valor:5,     unidad:'%'},
  {id:'CE-09', modulo:'SM2', nombre:'reval_ssd',             valor:30000, unidad:'ARS'},
  {id:'CE-10', modulo:'SM2', nombre:'reval_ram',             valor:15000, unidad:'ARS'},
  {id:'CE-11', modulo:'SM2', nombre:'penal_repuestos',       valor:50000, unidad:'ARS'},
  {id:'CE-12', modulo:'SM2', nombre:'antiguedad_obsoleta',   valor:6,     unidad:'años'},
  {id:'CE-13', modulo:'SM2', nombre:'anio_referencia',       valor:2026,  unidad:'año'},
  {id:'CE-14', modulo:'SM3', nombre:'margen_base',           valor:20,    unidad:'%'},
  {id:'CE-15', modulo:'SM3', nombre:'margen_alta_liquidez',  valor:12,    unidad:'%'},
  {id:'CE-16', modulo:'SM3', nombre:'margen_riesgo_alto',    valor:30,    unidad:'%'},
  {id:'CE-17', modulo:'SM3', nombre:'umbral_intervenciones', valor:4,     unidad:'intervenciones'},
  {id:'CE-18', modulo:'SM3', nombre:'prima_fallas',          valor:5,     unidad:'pp'},
  {id:'CE-19', modulo:'SM3', nombre:'ratio_reparacion_max',  valor:0.5,   unidad:'adimensional'},
  {id:'CE-20', modulo:'SM3', nombre:'descuento_max',         valor:35,    unidad:'%'}
] AS c
CREATE (ce:CriterioExperto {id: c.id, nombre: c.nombre, valor: c.valor, unidad: c.unidad,
                            version:'v1', vigente_desde: date('2026-10-01'),
                            estado_validacion:'Provisional', fuente:'Entrevista pendiente con M. Romero'})
WITH ce, c
MATCH (sm:Submodulo {id: c.modulo})
CREATE (ce)-[:PERTENECE_A]->(sm);


// =====================================================================
// 6. REGLAS CRISP CONSOLIDADAS (PG1, sección g + R1.7 incorporada en PG2)
//    implementada = true  → se ejecuta como consulta en los bloques 9 a 19
//    estado = 'Reemplazada…' → la reemplaza una base de reglas difusas
// =====================================================================
UNWIND [
  {id:'R1.1', sm:'SM1', tipo:'Determinística', impl:true,  est:'Vigente', crit:[], texto:'SI existe una FallaCatastrofica ENTONCES DictamenTecnico = Inviabilidad_Fisica_Insalvable'},
  {id:'R1.2', sm:'SM1', tipo:'Heurística',     impl:false, est:'Reemplazada por la base difusa SM1-BAT (salvo batería hinchada, que sigue crisp)', crit:['bateria_reemplazo'], texto:'SI Bateria.salud < bateria_reemplazo O está deformada ENTONCES reemplazo obligatorio'},
  {id:'R1.3', sm:'SM1', tipo:'Heurística',     impl:false, est:'Vigente', crit:[], texto:'SI Almacenamiento = HDD ENTONCES upgrade a SSD'},
  {id:'R1.4', sm:'SM1', tipo:'Determinística', impl:false, est:'Vigente', crit:['ram_soldada_min'], texto:'SI RAM soldada <= ram_soldada_min y sin zócalo ENTONCES Inviabilidad'},
  {id:'R1.5', sm:'SM1', tipo:'Contextual',     impl:false, est:'Vigente', crit:[], texto:'SI un repuesto de una intervención mandatoria está Discontinuado ENTONCES Inviabilidad'},
  {id:'R1.6', sm:'SM1', tipo:'Empírica',       impl:false, est:'Vigente', crit:[], texto:'SI hay derrame de líquido Y sulfatación ENTONCES FallaCatastrofica'},
  {id:'R1.7', sm:'SM1', tipo:'Heurística',     impl:false, est:'Reemplazada por la base difusa SM1-TER', crit:['temperatura_service'], texto:'SI temperatura de CPU bajo estrés >= temperatura_service ENTONCES service térmico (R9 del PI2 de Tapia, incorporada en PG2)'},
  {id:'R2.1', sm:'SM2', tipo:'Heurística',     impl:false, est:'Vigente', crit:['bateria_depreciacion','bateria_factor'], texto:'SI Reparable Y 75 % <= salud de batería < bateria_depreciacion Y sin reemplazo ENTONCES depreciación bateria_factor'},
  {id:'R2.2', sm:'SM2', tipo:'Heurística',     impl:false, est:'Vigente', crit:['deprec_danado','deprec_detalles'], texto:'SI estado_estetico = Dañado ENTONCES deprec_danado — SI = Con_Detalles ENTONCES deprec_detalles'},
  {id:'R2.3', sm:'SM2', tipo:'Heurística',     impl:false, est:'Vigente', crit:['reval_ssd','reval_ram'], texto:'SI tenía HDD Y el plan incluye SSD ENTONCES +reval_ssd — SI RAM <= 4 GB Y se amplía ENTONCES +reval_ram'},
  {id:'R2.4', sm:'SM2', tipo:'Empírica',       impl:false, est:'Vigente', crit:['penal_repuestos'], texto:'SI disponibilidad de repuestos = Escasa o Nula ENTONCES penalización penal_repuestos'},
  {id:'R2.5', sm:'SM2', tipo:'Documental',     impl:false, est:'Reemplazada por la base difusa SM2-RIE', crit:['antiguedad_obsoleta'], texto:'SI antigüedad >= antiguedad_obsoleta Y sin soporte de Windows 11 ENTONCES riesgo = Alto'},
  {id:'R2.6', sm:'SM2', tipo:'Empírica',       impl:false, est:'Reemplazada por la base difusa SM2-DEM', crit:[], texto:'SI rotación Rápida Y línea corporativa ENTONCES demanda = Alta — SI riesgo Alto O rotación Lenta ENTONCES demanda = Baja'},
  {id:'R2.7', sm:'SM2', tipo:'Heurística',     impl:false, est:'Vigente', crit:[], texto:'SI modificaciones no estándar O arquitectura propietaria abandonada ENTONCES DictamenComercial = Rechazo_Comercial_Directo'},
  {id:'R2.8', sm:'SM2', tipo:'Determinística', impl:false, est:'Vigente', crit:[], texto:'VMA = precio_base − depreciaciones + revalorizaciones − penalizaciones'},
  {id:'R3.1', sm:'SM3', tipo:'Documental',     impl:true,  est:'Vigente', crit:[], texto:'SI Bloqueo.estado = Activo Y remediable = Falso ENTONCES Descartar por inviabilidad'},
  {id:'R3.1b',sm:'SM3', tipo:'Determinística', impl:true,  est:'Vigente', crit:[], texto:'SI DictamenComercial = Rechazo_Comercial_Directo ENTONCES Descartar por inviabilidad'},
  {id:'R3.2', sm:'SM3', tipo:'Determinística', impl:true,  est:'Vigente', crit:[], texto:'SI DictamenTecnico = Inviabilidad ENTONCES Descartar por inviabilidad'},
  {id:'R3.3', sm:'SM3', tipo:'Contextual',     impl:true,  est:'Vigente', crit:[], texto:'SI el bloqueo es Desconocido ENTONCES Operacion = Verificacion_pendiente (SolicitarVerificacion)'},
  {id:'R3.3b',sm:'SM3', tipo:'Determinística', impl:true,  est:'Vigente', crit:[], texto:'SI falta precio, VMA, costo, intervenciones, demanda o riesgo ENTONCES Operacion = Verificacion_pendiente (SolicitarDato)'},
  {id:'R3.4', sm:'SM3', tipo:'Heurística',     impl:true,  est:'Vigente', crit:['margen_alta_liquidez'], texto:'(Paso 1) SI demanda = Alta Y riesgo = Bajo ENTONCES margen requerido := margen_alta_liquidez'},
  {id:'R3.5', sm:'SM3', tipo:'Heurística',     impl:true,  est:'Vigente', crit:['margen_riesgo_alto'], texto:'(Paso 1) SI riesgo = Alto ENTONCES margen requerido := máx(margen requerido, margen_riesgo_alto)'},
  {id:'R3.6', sm:'SM3', tipo:'Heurística',     impl:true,  est:'Vigente', crit:['umbral_intervenciones','prima_fallas'], texto:'(Paso 2) SI intervenciones >= umbral_intervenciones ENTONCES margen requerido += prima_fallas'},
  {id:'R3.7', sm:'SM3', tipo:'Heurística',     impl:true,  est:'Vigente', crit:['ratio_reparacion_max'], texto:'SI costo / VMA > ratio_reparacion_max ENTONCES Descartar por riesgo'},
  {id:'R3.8', sm:'SM3', tipo:'Contextual',     impl:true,  est:'Vigente', crit:[], texto:'SI riesgo = Alto Y demanda = Baja ENTONCES Descartar por riesgo'},
  {id:'R3.9', sm:'SM3', tipo:'Determinística', impl:false, est:'Reemplazada por la base difusa SM3-CONV', crit:[], texto:'SI margen neto >= margen requerido ENTONCES Comprar'},
  {id:'R3.10',sm:'SM3', tipo:'Heurística',     impl:false, est:'Reemplazada por la base difusa SM3-CONV', crit:['descuento_max'], texto:'SI margen neto < requerido Y demanda != Baja Y descuento <= descuento_max ENTONCES Comprar con oferta menor'},
  {id:'R3.11',sm:'SM3', tipo:'Heurística',     impl:false, est:'Reemplazada por la base difusa SM3-CONV', crit:['descuento_max'], texto:'SI margen neto < requerido Y (demanda = Baja O descuento > descuento_max) ENTONCES Descartar por riesgo'}
] AS r
CREATE (rg:Regla {id: r.id, texto: r.texto, tipo: r.tipo, implementada: r.impl, estado: r.est})
WITH rg, r
MATCH (sm:Submodulo {id: r.sm})
CREATE (rg)-[:PERTENECE_A]->(sm)
WITH rg, r
UNWIND r.crit AS nombreCriterio
MATCH (ce:CriterioExperto {nombre: nombreCriterio})
MERGE (rg)-[:USA_CRITERIO]->(ce);


// =====================================================================
// 7. CONOCIMIENTO DIFUSO (consenso de los tres PI3)
//    Entradas en sus unidades físicas; todas las salidas en [0, 1] con la
//    misma escala: conjuntos en 0,1 / 0,5 / 0,9 y sigma 0,12.
//    Gaussiana: mu(x) = exp(-0.5 * ((x - c) / sigma)^2). Crisp: 0 o 1.
//    ANTECEDENTE {grupo}: mismo grupo → O (máx); grupos distintos → Y (mín).
//    Categoría final = conjunto de salida dominante en el centroide.
// =====================================================================
UNWIND [
  {n:'Salud_Bateria',          sm:'SM1', min:0,   max:100,  u:'%',      rol:'Entrada', d:'Capacidad actual / capacidad de diseño (Bateria.salud_pct)'},
  {n:'Ciclos_Carga',           sm:'SM1', min:0,   max:1500, u:'ciclos', rol:'Entrada', d:'Ciclos de carga de la batería (Bateria.ciclos_carga)'},
  {n:'Temperatura_CPU',        sm:'SM1', min:35,  max:105,  u:'°C',     rol:'Entrada', d:'Temperatura sostenida en la prueba de estrés de 10 minutos'},
  {n:'Caida_Frecuencia',       sm:'SM1', min:0,   max:50,   u:'%',      rol:'Entrada', d:'Caída de la frecuencia sostenida respecto de la base (throttling)'},
  {n:'Necesidad_Intervencion', sm:'SM1', min:0,   max:1,    u:'',       rol:'Salida',  d:'Necesidad de agregar la intervención al plan'},
  {n:'Antiguedad_Hardware',    sm:'SM2', min:0,   max:12,   u:'años',   rol:'Entrada', d:'anio_referencia − Equipo.anio_fabricacion'},
  {n:'Disponibilidad_Repuestos', sm:'SM2', min:0, max:10,   u:'índice', rol:'Entrada', d:'Repuestos críticos disponibles en plaza (0 a 10)'},
  {n:'Soporte_W11',            sm:'SM2', min:null, max:null, u:'crisp', rol:'Entrada', d:'Procesador en la lista oficial de Windows 11 (hecho documental)'},
  {n:'Riesgo_Obsolescencia',   sm:'SM2', min:0,   max:1,    u:'',       rol:'Salida y entrada', d:'Salida de SM2-RIE y entrada de SM2-DEM'},
  {n:'Rotacion_Mercado',       sm:'SM2', min:0,   max:90,   u:'días',   rol:'Entrada', d:'Días promedio de venta (IndicadorMercado)'},
  {n:'Demanda_Comercial',      sm:'SM2', min:0,   max:1,    u:'',       rol:'Salida',  d:'Liquidez del modelo'},
  {n:'Brecha_Margen',          sm:'SM3', min:-60, max:40,   u:'pp',     rol:'Entrada', d:'Margen neto − margen requerido'},
  {n:'Descuento_Requerido',    sm:'SM3', min:0,   max:60,   u:'%',      rol:'Entrada', d:'Rebaja necesaria para alcanzar el margen requerido'},
  {n:'Conveniencia',           sm:'SM3', min:0,   max:1,    u:'',       rol:'Salida',  d:'Conveniencia de compra'}
] AS v
CREATE (vd:VariableDifusa {nombre: v.n, min: v.min, max: v.max, unidad: v.u, rol: v.rol, descripcion: v.d})
WITH vd, v
MATCH (sm:Submodulo {id: v.sm})
CREATE (vd)-[:PERTENECE_A]->(sm);

UNWIND [
  {v:'Salud_Bateria', e:'Agotada', c:35, s:12},       {v:'Salud_Bateria', e:'Degradada', c:64, s:8},
  {v:'Salud_Bateria', e:'Aceptable', c:82, s:6},      {v:'Salud_Bateria', e:'Optima', c:95, s:5},
  {v:'Ciclos_Carga', e:'Pocos', c:0, s:250},          {v:'Ciclos_Carga', e:'Moderados', c:600, s:180},
  {v:'Ciclos_Carga', e:'Excesivos', c:1100, s:180},
  {v:'Temperatura_CPU', e:'Fresca', c:50, s:8},       {v:'Temperatura_CPU', e:'Moderada', c:68, s:6},
  {v:'Temperatura_CPU', e:'Elevada', c:80, s:4},      {v:'Temperatura_CPU', e:'Critica', c:92, s:5},
  {v:'Caida_Frecuencia', e:'Nula', c:0, s:4},         {v:'Caida_Frecuencia', e:'Leve', c:10, s:5},
  {v:'Caida_Frecuencia', e:'Severa', c:25, s:7},
  {v:'Necesidad_Intervencion', e:'No_Requerida', c:0.1, s:0.12},
  {v:'Necesidad_Intervencion', e:'Recomendada', c:0.5, s:0.12},
  {v:'Necesidad_Intervencion', e:'Obligatoria', c:0.9, s:0.12},
  {v:'Antiguedad_Hardware', e:'Reciente', c:1.5, s:1.5},  {v:'Antiguedad_Hardware', e:'Intermedia', c:4.5, s:1.3},
  {v:'Antiguedad_Hardware', e:'Antigua', c:7.5, s:1.3},   {v:'Antiguedad_Hardware', e:'Obsoleta', c:10.5, s:1.3},
  {v:'Disponibilidad_Repuestos', e:'Escasa', c:1, s:1.8}, {v:'Disponibilidad_Repuestos', e:'Regular', c:5, s:1.5},
  {v:'Disponibilidad_Repuestos', e:'Amplia', c:9, s:1.5},
  {v:'Riesgo_Obsolescencia', e:'Bajo', c:0.1, s:0.12},    {v:'Riesgo_Obsolescencia', e:'Medio', c:0.5, s:0.12},
  {v:'Riesgo_Obsolescencia', e:'Alto', c:0.9, s:0.12},
  {v:'Rotacion_Mercado', e:'Muy_Rapida', c:7, s:6},       {v:'Rotacion_Mercado', e:'Moderada', c:30, s:9},
  {v:'Rotacion_Mercado', e:'Lenta', c:62, s:12},
  {v:'Demanda_Comercial', e:'Baja', c:0.1, s:0.12},       {v:'Demanda_Comercial', e:'Media', c:0.5, s:0.12},
  {v:'Demanda_Comercial', e:'Alta', c:0.9, s:0.12},
  {v:'Brecha_Margen', e:'Insuficiente', c:-40, s:12},     {v:'Brecha_Margen', e:'Escasa', c:-12, s:7},
  {v:'Brecha_Margen', e:'Suficiente', c:3, s:6},          {v:'Brecha_Margen', e:'Holgada', c:25, s:10},
  {v:'Descuento_Requerido', e:'Razonable', c:0, s:12},    {v:'Descuento_Requerido', e:'Agresivo', c:30, s:8},
  {v:'Descuento_Requerido', e:'Irreal', c:55, s:10},
  {v:'Conveniencia', e:'Descartar', c:0.1, s:0.12},       {v:'Conveniencia', e:'Negociar', c:0.5, s:0.12},
  {v:'Conveniencia', e:'Comprar', c:0.9, s:0.12}
] AS cj
MATCH (vd:VariableDifusa {nombre: cj.v})
CREATE (vd)-[:TIENE_CONJUNTO]->(:ConjuntoDifuso {id: cj.v + '.' + cj.e, etiqueta: cj.e, tipo:'gaussiana',
                                                 c: cj.c, sigma: cj.s, estado_validacion:'Provisional'});

// Conjuntos crisp (hecho documental: no se suaviza)
MATCH (vd:VariableDifusa {nombre:'Soporte_W11'})
CREATE (vd)-[:TIENE_CONJUNTO]->(:ConjuntoDifuso {id:'Soporte_W11.Si', etiqueta:'Si', tipo:'crisp', valor:true, estado_validacion:'Documental'})
CREATE (vd)-[:TIENE_CONJUNTO]->(:ConjuntoDifuso {id:'Soporte_W11.No', etiqueta:'No', tipo:'crisp', valor:false, estado_validacion:'Documental'});

// Reglas difusas de las cinco bases
UNWIND [
  // SM1 (Tapia) — reemplazo de batería
  {id:'RB1', base:'SM1-BAT', crisp:'R1.2', cons:'Necesidad_Intervencion.Obligatoria',  texto:'SI Salud ES Agotada ENTONCES Necesidad ES Obligatoria',
   ant:[['Salud_Bateria.Agotada',1]]},
  {id:'RB2', base:'SM1-BAT', crisp:'R1.2', cons:'Necesidad_Intervencion.Obligatoria',  texto:'SI Salud ES Degradada ENTONCES Necesidad ES Obligatoria',
   ant:[['Salud_Bateria.Degradada',1]]},
  {id:'RB3', base:'SM1-BAT', crisp:'R1.2', cons:'Necesidad_Intervencion.Recomendada',  texto:'SI Salud ES Aceptable Y Ciclos ES Excesivos ENTONCES Necesidad ES Recomendada',
   ant:[['Salud_Bateria.Aceptable',1], ['Ciclos_Carga.Excesivos',2]]},
  {id:'RB4', base:'SM1-BAT', crisp:'R1.2', cons:'Necesidad_Intervencion.No_Requerida', texto:'SI Salud ES Aceptable Y (Ciclos ES Pocos O Ciclos ES Moderados) ENTONCES Necesidad ES No_Requerida',
   ant:[['Salud_Bateria.Aceptable',1], ['Ciclos_Carga.Pocos',2], ['Ciclos_Carga.Moderados',2]]},
  {id:'RB5', base:'SM1-BAT', crisp:'R1.2', cons:'Necesidad_Intervencion.No_Requerida', texto:'SI Salud ES Optima ENTONCES Necesidad ES No_Requerida',
   ant:[['Salud_Bateria.Optima',1]]},
  // SM1 (Tapia) — service térmico
  {id:'RT1', base:'SM1-TER', crisp:'R1.7', cons:'Necesidad_Intervencion.Obligatoria',  texto:'SI Temperatura ES Critica ENTONCES Necesidad ES Obligatoria',
   ant:[['Temperatura_CPU.Critica',1]]},
  {id:'RT2', base:'SM1-TER', crisp:'R1.7', cons:'Necesidad_Intervencion.Obligatoria',  texto:'SI Temperatura ES Elevada Y (Caída ES Leve O Caída ES Severa) ENTONCES Necesidad ES Obligatoria',
   ant:[['Temperatura_CPU.Elevada',1], ['Caida_Frecuencia.Leve',2], ['Caida_Frecuencia.Severa',2]]},
  {id:'RT3', base:'SM1-TER', crisp:'R1.7', cons:'Necesidad_Intervencion.Recomendada',  texto:'SI Temperatura ES Elevada Y Caída ES Nula ENTONCES Necesidad ES Recomendada',
   ant:[['Temperatura_CPU.Elevada',1], ['Caida_Frecuencia.Nula',2]]},
  {id:'RT4', base:'SM1-TER', crisp:'R1.7', cons:'Necesidad_Intervencion.Recomendada',  texto:'SI Temperatura ES Moderada Y (Caída ES Leve O Caída ES Severa) ENTONCES Necesidad ES Recomendada',
   ant:[['Temperatura_CPU.Moderada',1], ['Caida_Frecuencia.Leve',2], ['Caida_Frecuencia.Severa',2]]},
  {id:'RT5', base:'SM1-TER', crisp:'R1.7', cons:'Necesidad_Intervencion.No_Requerida', texto:'SI Temperatura ES Moderada Y Caída ES Nula ENTONCES Necesidad ES No_Requerida',
   ant:[['Temperatura_CPU.Moderada',1], ['Caida_Frecuencia.Nula',2]]},
  {id:'RT6', base:'SM1-TER', crisp:'R1.7', cons:'Necesidad_Intervencion.No_Requerida', texto:'SI Temperatura ES Fresca ENTONCES Necesidad ES No_Requerida',
   ant:[['Temperatura_CPU.Fresca',1]]},
  // SM2 (Navarta) — riesgo de obsolescencia
  {id:'RO1', base:'SM2-RIE', crisp:'R2.5', cons:'Riesgo_Obsolescencia.Alto',  texto:'SI Soporte_W11 ES No Y (Antigüedad ES Antigua O Antigüedad ES Obsoleta) ENTONCES Riesgo ES Alto',
   ant:[['Soporte_W11.No',1], ['Antiguedad_Hardware.Antigua',2], ['Antiguedad_Hardware.Obsoleta',2]]},
  {id:'RO2', base:'SM2-RIE', crisp:'R2.5', cons:'Riesgo_Obsolescencia.Alto',  texto:'SI Antigüedad ES Obsoleta ENTONCES Riesgo ES Alto',
   ant:[['Antiguedad_Hardware.Obsoleta',1]]},
  {id:'RO3', base:'SM2-RIE', crisp:'R2.5', cons:'Riesgo_Obsolescencia.Alto',  texto:'SI Repuestos ES Escasa Y (Antigüedad ES Antigua O Antigüedad ES Obsoleta) ENTONCES Riesgo ES Alto',
   ant:[['Disponibilidad_Repuestos.Escasa',1], ['Antiguedad_Hardware.Antigua',2], ['Antiguedad_Hardware.Obsoleta',2]]},
  {id:'RO4', base:'SM2-RIE', crisp:'R2.5', cons:'Riesgo_Obsolescencia.Medio', texto:'SI Soporte_W11 ES Si Y Antigüedad ES Antigua Y (Repuestos ES Regular O Repuestos ES Amplia) ENTONCES Riesgo ES Medio',
   ant:[['Soporte_W11.Si',1], ['Antiguedad_Hardware.Antigua',2], ['Disponibilidad_Repuestos.Regular',3], ['Disponibilidad_Repuestos.Amplia',3]]},
  {id:'RO5', base:'SM2-RIE', crisp:'R2.5', cons:'Riesgo_Obsolescencia.Medio', texto:'SI Repuestos ES Escasa Y (Antigüedad ES Reciente O Antigüedad ES Intermedia) ENTONCES Riesgo ES Medio',
   ant:[['Disponibilidad_Repuestos.Escasa',1], ['Antiguedad_Hardware.Reciente',2], ['Antiguedad_Hardware.Intermedia',2]]},
  {id:'RO6', base:'SM2-RIE', crisp:'R2.5', cons:'Riesgo_Obsolescencia.Medio', texto:'SI Soporte_W11 ES No Y (Antigüedad ES Reciente O Antigüedad ES Intermedia) ENTONCES Riesgo ES Medio',
   ant:[['Soporte_W11.No',1], ['Antiguedad_Hardware.Reciente',2], ['Antiguedad_Hardware.Intermedia',2]]},
  {id:'RO7', base:'SM2-RIE', crisp:'R2.5', cons:'Riesgo_Obsolescencia.Bajo',  texto:'SI Soporte_W11 ES Si Y (Antigüedad ES Reciente O Antigüedad ES Intermedia) Y (Repuestos ES Regular O Repuestos ES Amplia) ENTONCES Riesgo ES Bajo',
   ant:[['Soporte_W11.Si',1], ['Antiguedad_Hardware.Reciente',2], ['Antiguedad_Hardware.Intermedia',2], ['Disponibilidad_Repuestos.Regular',3], ['Disponibilidad_Repuestos.Amplia',3]]},
  // SM2 (Navarta) — demanda comercial
  {id:'RM1', base:'SM2-DEM', crisp:'R2.6', cons:'Demanda_Comercial.Baja',  texto:'SI Riesgo ES Alto ENTONCES Demanda ES Baja',
   ant:[['Riesgo_Obsolescencia.Alto',1]]},
  {id:'RM2', base:'SM2-DEM', crisp:'R2.6', cons:'Demanda_Comercial.Baja',  texto:'SI Rotación ES Lenta ENTONCES Demanda ES Baja',
   ant:[['Rotacion_Mercado.Lenta',1]]},
  {id:'RM3', base:'SM2-DEM', crisp:'R2.6', cons:'Demanda_Comercial.Alta',  texto:'SI Rotación ES Muy_Rapida Y (Riesgo ES Bajo O Riesgo ES Medio) ENTONCES Demanda ES Alta',
   ant:[['Rotacion_Mercado.Muy_Rapida',1], ['Riesgo_Obsolescencia.Bajo',2], ['Riesgo_Obsolescencia.Medio',2]]},
  {id:'RM4', base:'SM2-DEM', crisp:'R2.6', cons:'Demanda_Comercial.Media', texto:'SI Rotación ES Moderada Y (Riesgo ES Bajo O Riesgo ES Medio) ENTONCES Demanda ES Media',
   ant:[['Rotacion_Mercado.Moderada',1], ['Riesgo_Obsolescencia.Bajo',2], ['Riesgo_Obsolescencia.Medio',2]]},
  // SM3 (Romero) — conveniencia de compra
  {id:'RD1', base:'SM3-CONV', crisp:'R3.9',  cons:'Conveniencia.Comprar',   texto:'SI Brecha ES Suficiente O Brecha ES Holgada ENTONCES Conveniencia ES Comprar',
   ant:[['Brecha_Margen.Suficiente',1], ['Brecha_Margen.Holgada',1]]},
  {id:'RD2', base:'SM3-CONV', crisp:'R3.10', cons:'Conveniencia.Negociar',  texto:'SI Brecha ES Escasa Y Descuento ES Razonable ENTONCES Conveniencia ES Negociar',
   ant:[['Brecha_Margen.Escasa',1], ['Descuento_Requerido.Razonable',2]]},
  {id:'RD3', base:'SM3-CONV', crisp:'R3.10', cons:'Conveniencia.Negociar',  texto:'SI Brecha ES Escasa Y Descuento ES Agresivo ENTONCES Conveniencia ES Negociar',
   ant:[['Brecha_Margen.Escasa',1], ['Descuento_Requerido.Agresivo',2]]},
  {id:'RD4', base:'SM3-CONV', crisp:'R3.11', cons:'Conveniencia.Descartar', texto:'SI Descuento ES Irreal ENTONCES Conveniencia ES Descartar',
   ant:[['Descuento_Requerido.Irreal',1]]},
  {id:'RD5', base:'SM3-CONV', crisp:'R3.11', cons:'Conveniencia.Descartar', texto:'SI Brecha ES Insuficiente Y (Descuento ES Agresivo O Descuento ES Irreal) ENTONCES Conveniencia ES Descartar',
   ant:[['Brecha_Margen.Insuficiente',1], ['Descuento_Requerido.Agresivo',2], ['Descuento_Requerido.Irreal',2]]}
] AS rd
CREATE (r:ReglaDifusa {id: rd.id, base: rd.base, texto: rd.texto, operador_y:'MIN', operador_o:'MAX',
                       implicacion:'MIN', agregacion:'MAX'})
WITH r, rd
MATCH (sal:ConjuntoDifuso {id: rd.cons}), (crisp:Regla {id: rd.crisp})
CREATE (r)-[:CONSECUENTE]->(sal)
CREATE (r)-[:REEMPLAZA_A]->(crisp)
WITH r, rd
UNWIND rd.ant AS a
MATCH (cj:ConjuntoDifuso {id: a[0]})
CREATE (r)-[:ANTECEDENTE {grupo: a[1]}]->(cj);

// Versiones de parámetros (una por submódulo)
UNWIND [
  {id:'FIS-SM1-v1', sm:'SM1', bases:['SM1-BAT','SM1-TER'], d:'PI3 de Tapia. Escala común de salida.'},
  {id:'FIS-SM2-v1', sm:'SM2', bases:['SM2-RIE','SM2-DEM'], d:'PI3 de Navarta. Escala común de salida — Soporte_W11 crisp.'},
  {id:'FIS-SM3-v2', sm:'SM3', bases:['SM3-CONV'], d:'PI3 de Romero ajustado en PG2: salida llevada a la escala común (v1 usaba 0 / 0,5 / 1 con sigma 0,15 y cortes 0,35 / 0,65).'}
] AS v
CREATE (vp:VersionParametros {id: v.id, fecha: date('2026-11-05'), estado:'Provisional', bases: v.bases,
                              politica_categoria:'Conjunto de salida dominante en el centroide', descripcion: v.d})
WITH vp, v
MATCH (sm:Submodulo {id: v.sm})
CREATE (vp)-[:PERTENECE_A]->(sm)
WITH vp
MATCH (r:ReglaDifusa) WHERE r.base IN vp.bases
CREATE (vp)-[:INCLUYE]->(r)
WITH DISTINCT vp
MATCH (vp)-[:INCLUYE]->(:ReglaDifusa)-[:ANTECEDENTE|CONSECUENTE]->(:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(vd:VariableDifusa)
WITH DISTINCT vp, vd
CREATE (vp)-[:INCLUYE]->(vd);


// =====================================================================
// 8. CASOS DE PRUEBA (casos del PG1 y de los PI3)
//    Cada operación guarda el resultado esperado para compararlo después.
//      NB-101 Acer Aspire 5    → difuso   (atraviesa SM1, SM2 y SM3)
//      NB-102 ThinkPad T490    → positivo
//      NB-103 Dell Inspiron 15 → negativo técnico (falla catastrófica)
//      NB-104 ThinkPad T440p   → negativo por riesgo (SM2 → SM3)
//      NB-105 MacBook Air 2017 → excepción (bloqueo dudoso)
//      NB-106 HP 15 Ryzen 3    → frontera (margen apenas suficiente)
//    Las intervenciones de batería y service térmico NO se cargan: las
//    infiere SM1. Riesgo y demanda NO se cargan: los infiere SM2.
// =====================================================================

// --- NB-101 Acer Aspire 5 (caso difuso) ---
CREATE (e:Equipo:Notebook {id:'NB-101', marca:'Acer', modelo:'Aspire 5', anio_fabricacion:2020,
                           estado_estetico:'Con_Detalles', soporta_windows11:true})
CREATE (p:Publicacion {id:'PUB-101', precio:115000, plataforma:'Marketplace'})
CREATE (p)-[:OFRECE]->(e)
CREATE (b:Componente:Bateria {id:'BAT-101', salud_pct:60, ciclos_carga:780, hinchada:false, costo_reemplazo_ars:30000})
CREATE (m:Medicion {id:'MED-101', tipo:'Prueba_estres', temperatura_c:87, caida_frecuencia_pct:18})
CREATE (e)-[:TIENE_COMPONENTE]->(b)
CREATE (e)-[:TIENE_MEDICION]->(m)
CREATE (f:Falla:FallaModular {id:'F-101', descripcion:'Teclado con teclas que no responden'})
CREATE (e)-[:PRESENTA]->(f)
CREATE (dt:DictamenTecnico {id:'DICT-NB-101', resultado:'Fisicamente_Reparable'})
CREATE (e)-[:TIENE_DICTAMEN]->(dt)
CREATE (pl:PlanReacondicionamiento {id:'PLAN-NB-101'})
CREATE (e)-[:TIENE_PLAN]->(pl)
CREATE (:Intervencion {id:'INT-101-1', tipo_tarea:'Reemplazo de teclado', costo_ars:20000, es_mandatoria:true, origen:'Diagnóstico (F-101)'})-[:FORMA_PARTE_DE]->(pl)
CREATE (:Intervencion {id:'INT-101-2', tipo_tarea:'Upgrade a SSD', costo_ars:22000, es_mandatoria:true, origen:'R1.3'})-[:FORMA_PARTE_DE]->(pl)
CREATE (:Intervencion {id:'INT-101-3', tipo_tarea:'Ampliación de RAM', costo_ars:10000, es_mandatoria:true, origen:'Plan de upgrade'})-[:FORMA_PARTE_DE]->(pl)
CREATE (im:IndicadorMercado {id:'IND-MER-101', dias_promedio_venta:25, indice_repuestos:6})
CREATE (e)-[:TIENE_INDICADOR]->(im)
CREATE (vma:ValorMercadoAjustado {id:'VMA-NB-101', monto_tasado_ars:220000})
CREATE (dc:DictamenComercial {id:'DCOM-NB-101', veredicto:'Tasable_Comercialmente'})
CREATE (e)-[:TIENE_VALUACION]->(vma)
CREATE (e)-[:TIENE_DICTAMEN_COMERCIAL]->(dc)
CREATE (pl)-[:INFORMA_ESTADO_A]->(vma)
CREATE (op:Operacion {id:'OP-101', estado:'Recibida', tipo_caso:'Difuso', resultado_esperado:'ComprarConOfertaMenor'})
CREATE (op)-[:EVALUA]->(e);

// --- NB-102 ThinkPad T490 (caso positivo) ---
CREATE (e:Equipo:Notebook {id:'NB-102', marca:'Lenovo', modelo:'ThinkPad T490', anio_fabricacion:2019,
                           estado_estetico:'Bueno', soporta_windows11:true})
CREATE (p:Publicacion {id:'PUB-102', precio:230000, plataforma:'Mercado Libre'})
CREATE (p)-[:OFRECE]->(e)
CREATE (b:Componente:Bateria {id:'BAT-102', salud_pct:90, ciclos_carga:300, hinchada:false, costo_reemplazo_ars:35000})
CREATE (m:Medicion {id:'MED-102', tipo:'Prueba_estres', temperatura_c:65, caida_frecuencia_pct:0})
CREATE (e)-[:TIENE_COMPONENTE]->(b)
CREATE (e)-[:TIENE_MEDICION]->(m)
CREATE (dt:DictamenTecnico {id:'DICT-NB-102', resultado:'Fisicamente_Reparable'})
CREATE (e)-[:TIENE_DICTAMEN]->(dt)
CREATE (pl:PlanReacondicionamiento {id:'PLAN-NB-102'})
CREATE (e)-[:TIENE_PLAN]->(pl)
CREATE (im:IndicadorMercado {id:'IND-MER-102', dias_promedio_venta:10, indice_repuestos:9})
CREATE (e)-[:TIENE_INDICADOR]->(im)
CREATE (vma:ValorMercadoAjustado {id:'VMA-NB-102', monto_tasado_ars:350000})
CREATE (dc:DictamenComercial {id:'DCOM-NB-102', veredicto:'Tasable_Comercialmente'})
CREATE (e)-[:TIENE_VALUACION]->(vma)
CREATE (e)-[:TIENE_DICTAMEN_COMERCIAL]->(dc)
CREATE (pl)-[:INFORMA_ESTADO_A]->(vma)
CREATE (op:Operacion {id:'OP-102', estado:'Recibida', tipo_caso:'Positivo', resultado_esperado:'Comprar'})
CREATE (op)-[:EVALUA]->(e);

// --- NB-103 Dell Inspiron 15 (caso negativo técnico) ---
//     El dictamen no se carga: lo infiere R1.1 (bloque 10).
CREATE (e:Equipo:Notebook {id:'NB-103', marca:'Dell', modelo:'Inspiron 15', anio_fabricacion:2018,
                           estado_estetico:'Bueno', soporta_windows11:true})
CREATE (p:Publicacion {id:'PUB-103', precio:60000, plataforma:'Marketplace'})
CREATE (p)-[:OFRECE]->(e)
CREATE (f:Falla:FallaCatastrofica {id:'F-103', descripcion:'CPU soldada en cortocircuito'})
CREATE (e)-[:PRESENTA]->(f)
CREATE (op:Operacion {id:'OP-103', estado:'Recibida', tipo_caso:'Negativo', resultado_esperado:'DescartarPorInviabilidad'})
CREATE (op)-[:EVALUA]->(e);

// --- NB-104 ThinkPad T440p (caso negativo por riesgo) ---
CREATE (e:Equipo:Notebook {id:'NB-104', marca:'Lenovo', modelo:'ThinkPad T440p', anio_fabricacion:2014,
                           estado_estetico:'Bueno', soporta_windows11:false})
CREATE (p:Publicacion {id:'PUB-104', precio:95000, plataforma:'Marketplace'})
CREATE (p)-[:OFRECE]->(e)
CREATE (b:Componente:Bateria {id:'BAT-104', salud_pct:55, ciclos_carga:900, hinchada:false, costo_reemplazo_ars:25000})
CREATE (m:Medicion {id:'MED-104', tipo:'Prueba_estres', temperatura_c:70, caida_frecuencia_pct:0})
CREATE (e)-[:TIENE_COMPONENTE]->(b)
CREATE (e)-[:TIENE_MEDICION]->(m)
CREATE (dt:DictamenTecnico {id:'DICT-NB-104', resultado:'Fisicamente_Reparable'})
CREATE (e)-[:TIENE_DICTAMEN]->(dt)
CREATE (pl:PlanReacondicionamiento {id:'PLAN-NB-104'})
CREATE (e)-[:TIENE_PLAN]->(pl)
CREATE (im:IndicadorMercado {id:'IND-MER-104', dias_promedio_venta:65, indice_repuestos:2})
CREATE (e)-[:TIENE_INDICADOR]->(im)
CREATE (vma:ValorMercadoAjustado {id:'VMA-NB-104', monto_tasado_ars:110000, precio_base_origen:160000,
        ajustes:['Penalización por repuestos escasos: −$50.000 (R2.4)']})
CREATE (dc:DictamenComercial {id:'DCOM-NB-104', veredicto:'Tasable_Con_Advertencia_Riesgo'})
CREATE (e)-[:TIENE_VALUACION]->(vma)
CREATE (e)-[:TIENE_DICTAMEN_COMERCIAL]->(dc)
CREATE (pl)-[:INFORMA_ESTADO_A]->(vma)
CREATE (op:Operacion {id:'OP-104', estado:'Recibida', tipo_caso:'Negativo', resultado_esperado:'DescartarPorRiesgo'})
CREATE (op)-[:EVALUA]->(e);

// --- NB-105 MacBook Air 2017 (excepción: bloqueo dudoso) ---
CREATE (e:Equipo:Notebook {id:'NB-105', marca:'Apple', modelo:'MacBook Air 2017', anio_fabricacion:2017,
                           estado_estetico:'Bueno', soporta_windows11:false})
CREATE (p:Publicacion {id:'PUB-105', precio:180000, plataforma:'Marketplace',
                       texto:'Anda perfecto, no recuerdo la cuenta de Apple'})
CREATE (p)-[:OFRECE]->(e)
CREATE (bl:Bloqueo {id:'BLQ-NB-105', tipo:'Cuenta', estado:'Desconocido'})
CREATE (e)-[:TIENE_BLOQUEO]->(bl)
CREATE (op:Operacion {id:'OP-105', estado:'Recibida', tipo_caso:'Excepción', resultado_esperado:'Verificacion_pendiente'})
CREATE (op)-[:EVALUA]->(e);

// --- NB-106 HP 15 Ryzen 3 (caso frontera) ---
CREATE (e:Equipo:Notebook {id:'NB-106', marca:'HP', modelo:'15 Ryzen 3', anio_fabricacion:2021,
                           estado_estetico:'Bueno', soporta_windows11:true})
CREATE (p:Publicacion {id:'PUB-106', precio:140000, plataforma:'Marketplace'})
CREATE (p)-[:OFRECE]->(e)
CREATE (b:Componente:Bateria {id:'BAT-106', salud_pct:88, ciclos_carga:250, hinchada:false, costo_reemplazo_ars:28000})
CREATE (m:Medicion {id:'MED-106', tipo:'Prueba_estres', temperatura_c:70, caida_frecuencia_pct:0})
CREATE (e)-[:TIENE_COMPONENTE]->(b)
CREATE (e)-[:TIENE_MEDICION]->(m)
CREATE (dt:DictamenTecnico {id:'DICT-NB-106', resultado:'Fisicamente_Reparable'})
CREATE (e)-[:TIENE_DICTAMEN]->(dt)
CREATE (pl:PlanReacondicionamiento {id:'PLAN-NB-106'})
CREATE (e)-[:TIENE_PLAN]->(pl)
CREATE (:Intervencion {id:'INT-106-1', tipo_tarea:'Upgrade a SSD', costo_ars:25000, es_mandatoria:true, origen:'R1.3'})-[:FORMA_PARTE_DE]->(pl)
CREATE (:Intervencion {id:'INT-106-2', tipo_tarea:'Ampliación de RAM', costo_ars:12750, es_mandatoria:true, origen:'Plan de upgrade'})-[:FORMA_PARTE_DE]->(pl)
CREATE (im:IndicadorMercado {id:'IND-MER-106', dias_promedio_venta:25, indice_repuestos:6})
CREATE (e)-[:TIENE_INDICADOR]->(im)
CREATE (vma:ValorMercadoAjustado {id:'VMA-NB-106', monto_tasado_ars:225000, precio_base_origen:180000,
        ajustes:['Upgrade a SSD: +$30.000 (R2.3)', 'Ampliación de RAM: +$15.000 (R2.3)']})
CREATE (dc:DictamenComercial {id:'DCOM-NB-106', veredicto:'Tasable_Comercialmente'})
CREATE (e)-[:TIENE_VALUACION]->(vma)
CREATE (e)-[:TIENE_DICTAMEN_COMERCIAL]->(dc)
CREATE (pl)-[:INFORMA_ESTADO_A]->(vma)
CREATE (op:Operacion {id:'OP-106', estado:'Recibida', tipo_caso:'Frontera', resultado_esperado:'Comprar'})
CREATE (op)-[:EVALUA]->(e);


// =====================================================================
// 9. SM3 — FILTROS DE BLOQUEO (lo más barato de verificar va primero)
//    Cada filtro actúa solo sobre operaciones en estado 'Recibida'.
// =====================================================================

// R3.1: bloqueo activo y no remediable
MATCH (op:Operacion {estado:'Recibida'})-[:EVALUA]->(e:Equipo)-[:TIENE_BLOQUEO]->(bl:Bloqueo),
      (r:Regla {id:'R3.1'})
WHERE bl.estado = 'Activo' AND bl.remediable = false
MERGE (dec:Decision {id:'DEC-' + e.id})
SET dec.tipo = 'DescartarPorInviabilidad',
    dec.motivo = 'Bloqueo de ' + bl.tipo + ' activo y no remediable'
MERGE (e)-[:RECIBE_DECISION]->(dec)
MERGE (dec)-[:APLICA_REGLA]->(r)
MERGE (dec)-[:SE_BASA_EN]->(bl)
SET op.estado = 'Resuelta';

// R3.3: bloqueo dudoso → verificación pendiente (no se genera Decision)
MATCH (op:Operacion {estado:'Recibida'})-[:EVALUA]->(e:Equipo)-[:TIENE_BLOQUEO]->(bl:Bloqueo {estado:'Desconocido'}),
      (r:Regla {id:'R3.3'})
SET op.estado = 'Verificacion_pendiente',
    op.accion_pendiente = 'SolicitarVerificacion',
    op.dato_solicitado = 'Estado real del bloqueo de ' + bl.tipo
MERGE (op)-[:APLICA_REGLA]->(r)
MERGE (op)-[:SE_BASA_EN]->(bl);


// =====================================================================
// 10. SM1 — FALLA CATASTRÓFICA (R1.1) Y CONSUMO EN SM3 (R3.2)
// =====================================================================

// R1.1 (SM1): una falla catastrófica determina la inviabilidad física
MATCH (op:Operacion {estado:'Recibida'})-[:EVALUA]->(e:Equipo)-[:PRESENTA]->(f:FallaCatastrofica),
      (r:Regla {id:'R1.1'})
MERGE (dt:DictamenTecnico {id:'DICT-' + e.id})
SET dt.resultado = 'Inviabilidad_Fisica_Insalvable',
    dt.causa_inviabilidad = f.descripcion
MERGE (e)-[:TIENE_DICTAMEN]->(dt)
MERGE (f)-[:DETERMINA]->(dt)
MERGE (dt)-[:INFERIDO_POR]->(r);

// R3.2 (SM3): consume el dictamen de inviabilidad de SM1
MATCH (op:Operacion {estado:'Recibida'})-[:EVALUA]->(e:Equipo)-[:TIENE_DICTAMEN]->(dt:DictamenTecnico),
      (r:Regla {id:'R3.2'})
WHERE dt.resultado = 'Inviabilidad_Fisica_Insalvable'
MERGE (dec:Decision {id:'DEC-' + e.id})
SET dec.tipo = 'DescartarPorInviabilidad',
    dec.motivo = 'Inviabilidad técnica: ' + dt.causa_inviabilidad
MERGE (e)-[:RECIBE_DECISION]->(dec)
MERGE (dec)-[:APLICA_REGLA]->(r)
MERGE (dec)-[:SE_BASA_EN]->(dt)
SET op.estado = 'Resuelta';


// =====================================================================
// 11. SM1 DIFUSO — NECESIDAD DE REEMPLAZO DE BATERÍA Y DE SERVICE TÉRMICO
//     (PI3 de Tapia). La batería hinchada no pasa por acá: es crisp.
// =====================================================================

// Evaluación SM1-BAT: entradas salud y ciclos del frame Bateria
MATCH (op:Operacion {estado:'Recibida'})-[:EVALUA]->(e:Equipo)-[:TIENE_COMPONENTE]->(b:Bateria),
      (vS:VariableDifusa {nombre:'Salud_Bateria'}), (vC:VariableDifusa {nombre:'Ciclos_Carga'}),
      (vp:VersionParametros {id:'FIS-SM1-v1'})
WHERE b.hinchada = false
CREATE (ev:Evaluacion {id:'EV-' + e.id + '-BAT', base:'SM1-BAT', estado:'Pendiente', fecha: datetime()})
CREATE (op)-[:TIENE_EVALUACION]->(ev)
CREATE (ev)-[:SOBRE]->(b)
CREATE (ev)-[:ENTRADA {valor: b.salud_pct}]->(vS)
CREATE (ev)-[:ENTRADA {valor: b.ciclos_carga}]->(vC)
CREATE (ev)-[:USA_VERSION]->(vp);

// Evaluación SM1-TER: entradas de la prueba de estrés
MATCH (op:Operacion {estado:'Recibida'})-[:EVALUA]->(e:Equipo)-[:TIENE_MEDICION]->(m:Medicion {tipo:'Prueba_estres'}),
      (vT:VariableDifusa {nombre:'Temperatura_CPU'}), (vF:VariableDifusa {nombre:'Caida_Frecuencia'}),
      (vp:VersionParametros {id:'FIS-SM1-v1'})
CREATE (ev:Evaluacion {id:'EV-' + e.id + '-TER', base:'SM1-TER', estado:'Pendiente', fecha: datetime()})
CREATE (op)-[:TIENE_EVALUACION]->(ev)
CREATE (ev)-[:SOBRE]->(m)
CREATE (ev)-[:ENTRADA {valor: m.temperatura_c}]->(vT)
CREATE (ev)-[:ENTRADA {valor: m.caida_frecuencia_pct}]->(vF)
CREATE (ev)-[:USA_VERSION]->(vp);

// ---- Motor difuso genérico (mismo código en cada etapa) ----
// M1. Fuzzificación: grado de cada entrada en cada conjunto de su variable.
//     Gaussiana: exp(-0.5 * ((x - c) / sigma)^2). Crisp: 1 si coincide, 0 si no.
MATCH (ev:Evaluacion {estado:'Pendiente'})-[en:ENTRADA]->(var:VariableDifusa)-[:TIENE_CONJUNTO]->(cj:ConjuntoDifuso)
WITH ev, cj,
     CASE cj.tipo
       WHEN 'crisp' THEN CASE WHEN en.valor = cj.valor THEN 1.0 ELSE 0.0 END
       ELSE exp(-0.5 * ((en.valor - cj.c) / cj.sigma)^2)
     END AS mu
WHERE mu >= 0.01
CREATE (ev)-[:TIENE_GRADO {mu: round(mu, 2)}]->(cj);

MATCH (ev:Evaluacion {estado:'Pendiente'}) SET ev.estado = 'Fuzzificada';

// M2. Fuerza de cada regla de la base: máx dentro de cada grupo (O), mín entre grupos (Y).
MATCH (ev:Evaluacion {estado:'Fuzzificada'})
MATCH (r:ReglaDifusa {base: ev.base})-[a:ANTECEDENTE]->(cj:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(var:VariableDifusa)<-[en:ENTRADA]-(ev)
WITH ev, r, a.grupo AS grupo,
     max(CASE cj.tipo
           WHEN 'crisp' THEN CASE WHEN en.valor = cj.valor THEN 1.0 ELSE 0.0 END
           ELSE exp(-0.5 * ((en.valor - cj.c) / cj.sigma)^2)
         END) AS mu_grupo
WITH ev, r, min(mu_grupo) AS fuerza
WHERE fuerza >= 0.01
CREATE (ev)-[:ACTIVO {fuerza: round(fuerza, 2)}]->(r);

MATCH (ev:Evaluacion {estado:'Fuzzificada'}) SET ev.estado = 'Inferida';

// M3. Implicación MIN + agregación MAX sobre 101 puntos del universo de salida,
//     centroide y categoría = conjunto de salida dominante en el centroide.
MATCH (ev:Evaluacion {estado:'Inferida'})-[act:ACTIVO]->(:ReglaDifusa)-[:CONSECUENTE]->(sal:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(vs:VariableDifusa)
WITH ev, vs, collect({fuerza: act.fuerza, c: sal.c, sigma: sal.sigma}) AS reglas
UNWIND range(0, 100) AS i
WITH ev, vs, reglas, vs.min + (vs.max - vs.min) * i / 100.0 AS y
UNWIND reglas AS rg
WITH ev, vs, y, rg, exp(-0.5 * ((y - rg.c) / rg.sigma)^2) AS mu_sal
WITH ev, vs, y, max(CASE WHEN rg.fuerza < mu_sal THEN rg.fuerza ELSE mu_sal END) AS altura
WITH ev, vs, sum(y * altura) / sum(altura) AS centroide
MATCH (vs)-[:TIENE_CONJUNTO]->(s:ConjuntoDifuso)
WITH ev, centroide, s, exp(-0.5 * ((centroide - s.c) / s.sigma)^2) AS mu
ORDER BY mu DESC
WITH ev, centroide, collect(s)[0] AS dominante, collect(mu)[0] AS mu_dominante
SET ev.centroide = round(centroide, 2),
    ev.categoria = dominante.etiqueta,
    ev.mu_categoria = round(mu_dominante, 2),
    ev.estado = 'Resuelta'
CREATE (ev)-[:CONCLUYE]->(dominante);
// ---- fin del motor ----


// =====================================================================
// 12. SM1 — PLAN Y COSTO DE REACONDICIONAMIENTO
//     Obligatoria → intervención mandatoria; Recomendada → no mandatoria;
//     No_Requerida → no se agrega.
// =====================================================================
MATCH (op:Operacion {estado:'Recibida'})-[:TIENE_EVALUACION]->(ev:Evaluacion),
      (op)-[:EVALUA]->(e:Equipo)-[:TIENE_PLAN]->(pl:PlanReacondicionamiento),
      (svc:CriterioExperto {nombre:'costo_service_termico'})
WHERE ev.base IN ['SM1-BAT', 'SM1-TER'] AND ev.categoria IN ['Obligatoria', 'Recomendada']
OPTIONAL MATCH (e)-[:TIENE_COMPONENTE]->(b:Bateria)
CREATE (i:Intervencion {id:'INT-' + e.id + '-' + ev.base,
                        tipo_tarea: CASE ev.base WHEN 'SM1-BAT' THEN 'Reemplazo de batería' ELSE 'Service térmico' END,
                        costo_ars: CASE ev.base WHEN 'SM1-BAT' THEN b.costo_reemplazo_ars ELSE svc.valor END,
                        es_mandatoria: ev.categoria = 'Obligatoria',
                        origen: 'Base difusa ' + ev.base + ' (' + ev.categoria + ')'})
CREATE (i)-[:FORMA_PARTE_DE]->(pl)
CREATE (ev)-[:JUSTIFICA]->(i);

MATCH (op:Operacion {estado:'Recibida'})-[:EVALUA]->(e:Equipo)-[:TIENE_PLAN]->(pl:PlanReacondicionamiento)
OPTIONAL MATCH (i:Intervencion)-[:FORMA_PARTE_DE]->(pl)
WITH e, pl, count(i) AS n, sum(coalesce(i.costo_ars, 0)) AS total, collect(i.tipo_tarea) AS tareas
SET pl.cantidad_intervenciones = n, pl.intervenciones = tareas
MERGE (c:CostoReacondicionamiento {id:'COSTO-' + e.id})
SET c.monto_total = total
MERGE (pl)-[:GENERA]->(c);


// =====================================================================
// 13. SM2 — RECHAZO COMERCIAL DIRECTO (R3.1b consume el dictamen de SM2)
// =====================================================================
MATCH (op:Operacion {estado:'Recibida'})-[:EVALUA]->(e:Equipo)-[:TIENE_DICTAMEN_COMERCIAL]->(dc:DictamenComercial),
      (r:Regla {id:'R3.1b'})
WHERE dc.veredicto = 'Rechazo_Comercial_Directo'
MERGE (dec:Decision {id:'DEC-' + e.id})
SET dec.tipo = 'DescartarPorInviabilidad',
    dec.motivo = 'Rechazo comercial directo de SM2'
MERGE (e)-[:RECIBE_DECISION]->(dec)
MERGE (dec)-[:APLICA_REGLA]->(r)
MERGE (dec)-[:SE_BASA_EN]->(dc)
SET op.estado = 'Resuelta';


// =====================================================================
// 14. SM2 DIFUSO — RIESGO DE OBSOLESCENCIA (PI3 de Navarta)
// =====================================================================
MATCH (op:Operacion {estado:'Recibida'})-[:EVALUA]->(e:Equipo)-[:TIENE_INDICADOR]->(im:IndicadorMercado),
      (ref:CriterioExperto {nombre:'anio_referencia'}),
      (vA:VariableDifusa {nombre:'Antiguedad_Hardware'}), (vR:VariableDifusa {nombre:'Disponibilidad_Repuestos'}),
      (vW:VariableDifusa {nombre:'Soporte_W11'}), (vp:VersionParametros {id:'FIS-SM2-v1'})
CREATE (ev:Evaluacion {id:'EV-' + e.id + '-RIE', base:'SM2-RIE', estado:'Pendiente', fecha: datetime()})
CREATE (op)-[:TIENE_EVALUACION]->(ev)
CREATE (ev)-[:SOBRE]->(e)
CREATE (ev)-[:ENTRADA {valor: ref.valor - e.anio_fabricacion}]->(vA)
CREATE (ev)-[:ENTRADA {valor: im.indice_repuestos}]->(vR)
CREATE (ev)-[:ENTRADA {valor: e.soporta_windows11}]->(vW)
CREATE (ev)-[:USA_VERSION]->(vp);

// ---- Motor difuso genérico (mismo código en cada etapa) ----
// M1. Fuzzificación: grado de cada entrada en cada conjunto de su variable.
//     Gaussiana: exp(-0.5 * ((x - c) / sigma)^2). Crisp: 1 si coincide, 0 si no.
MATCH (ev:Evaluacion {estado:'Pendiente'})-[en:ENTRADA]->(var:VariableDifusa)-[:TIENE_CONJUNTO]->(cj:ConjuntoDifuso)
WITH ev, cj,
     CASE cj.tipo
       WHEN 'crisp' THEN CASE WHEN en.valor = cj.valor THEN 1.0 ELSE 0.0 END
       ELSE exp(-0.5 * ((en.valor - cj.c) / cj.sigma)^2)
     END AS mu
WHERE mu >= 0.01
CREATE (ev)-[:TIENE_GRADO {mu: round(mu, 2)}]->(cj);

MATCH (ev:Evaluacion {estado:'Pendiente'}) SET ev.estado = 'Fuzzificada';

// M2. Fuerza de cada regla de la base: máx dentro de cada grupo (O), mín entre grupos (Y).
MATCH (ev:Evaluacion {estado:'Fuzzificada'})
MATCH (r:ReglaDifusa {base: ev.base})-[a:ANTECEDENTE]->(cj:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(var:VariableDifusa)<-[en:ENTRADA]-(ev)
WITH ev, r, a.grupo AS grupo,
     max(CASE cj.tipo
           WHEN 'crisp' THEN CASE WHEN en.valor = cj.valor THEN 1.0 ELSE 0.0 END
           ELSE exp(-0.5 * ((en.valor - cj.c) / cj.sigma)^2)
         END) AS mu_grupo
WITH ev, r, min(mu_grupo) AS fuerza
WHERE fuerza >= 0.01
CREATE (ev)-[:ACTIVO {fuerza: round(fuerza, 2)}]->(r);

MATCH (ev:Evaluacion {estado:'Fuzzificada'}) SET ev.estado = 'Inferida';

// M3. Implicación MIN + agregación MAX sobre 101 puntos del universo de salida,
//     centroide y categoría = conjunto de salida dominante en el centroide.
MATCH (ev:Evaluacion {estado:'Inferida'})-[act:ACTIVO]->(:ReglaDifusa)-[:CONSECUENTE]->(sal:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(vs:VariableDifusa)
WITH ev, vs, collect({fuerza: act.fuerza, c: sal.c, sigma: sal.sigma}) AS reglas
UNWIND range(0, 100) AS i
WITH ev, vs, reglas, vs.min + (vs.max - vs.min) * i / 100.0 AS y
UNWIND reglas AS rg
WITH ev, vs, y, rg, exp(-0.5 * ((y - rg.c) / rg.sigma)^2) AS mu_sal
WITH ev, vs, y, max(CASE WHEN rg.fuerza < mu_sal THEN rg.fuerza ELSE mu_sal END) AS altura
WITH ev, vs, sum(y * altura) / sum(altura) AS centroide
MATCH (vs)-[:TIENE_CONJUNTO]->(s:ConjuntoDifuso)
WITH ev, centroide, s, exp(-0.5 * ((centroide - s.c) / s.sigma)^2) AS mu
ORDER BY mu DESC
WITH ev, centroide, collect(s)[0] AS dominante, collect(mu)[0] AS mu_dominante
SET ev.centroide = round(centroide, 2),
    ev.categoria = dominante.etiqueta,
    ev.mu_categoria = round(mu_dominante, 2),
    ev.estado = 'Resuelta'
CREATE (ev)-[:CONCLUYE]->(dominante);
// ---- fin del motor ----

MATCH (op:Operacion {estado:'Recibida'})-[:TIENE_EVALUACION]->(ev:Evaluacion {base:'SM2-RIE', estado:'Resuelta'}),
      (op)-[:EVALUA]->(e:Equipo)
CREATE (ri:RiesgoObsolescencia {id:'RIE-' + e.id, nivel: ev.categoria, indice: ev.centroide})
CREATE (e)-[:TIENE_RIESGO]->(ri)
CREATE (ev)-[:DETERMINA]->(ri);


// =====================================================================
// 15. SM2 DIFUSO — DEMANDA COMERCIAL (encadenada: usa el riesgo inferido)
// =====================================================================
MATCH (op:Operacion {estado:'Recibida'})-[:TIENE_EVALUACION]->(er:Evaluacion {base:'SM2-RIE', estado:'Resuelta'}),
      (op)-[:EVALUA]->(e:Equipo)-[:TIENE_INDICADOR]->(im:IndicadorMercado),
      (vRi:VariableDifusa {nombre:'Riesgo_Obsolescencia'}), (vRo:VariableDifusa {nombre:'Rotacion_Mercado'}),
      (vp:VersionParametros {id:'FIS-SM2-v1'})
CREATE (ev:Evaluacion {id:'EV-' + e.id + '-DEM', base:'SM2-DEM', estado:'Pendiente', fecha: datetime()})
CREATE (op)-[:TIENE_EVALUACION]->(ev)
CREATE (ev)-[:SOBRE]->(e)
CREATE (er)-[:ALIMENTA]->(ev)
CREATE (ev)-[:ENTRADA {valor: er.centroide}]->(vRi)
CREATE (ev)-[:ENTRADA {valor: im.dias_promedio_venta}]->(vRo)
CREATE (ev)-[:USA_VERSION]->(vp);

// ---- Motor difuso genérico (mismo código en cada etapa) ----
// M1. Fuzzificación: grado de cada entrada en cada conjunto de su variable.
//     Gaussiana: exp(-0.5 * ((x - c) / sigma)^2). Crisp: 1 si coincide, 0 si no.
MATCH (ev:Evaluacion {estado:'Pendiente'})-[en:ENTRADA]->(var:VariableDifusa)-[:TIENE_CONJUNTO]->(cj:ConjuntoDifuso)
WITH ev, cj,
     CASE cj.tipo
       WHEN 'crisp' THEN CASE WHEN en.valor = cj.valor THEN 1.0 ELSE 0.0 END
       ELSE exp(-0.5 * ((en.valor - cj.c) / cj.sigma)^2)
     END AS mu
WHERE mu >= 0.01
CREATE (ev)-[:TIENE_GRADO {mu: round(mu, 2)}]->(cj);

MATCH (ev:Evaluacion {estado:'Pendiente'}) SET ev.estado = 'Fuzzificada';

// M2. Fuerza de cada regla de la base: máx dentro de cada grupo (O), mín entre grupos (Y).
MATCH (ev:Evaluacion {estado:'Fuzzificada'})
MATCH (r:ReglaDifusa {base: ev.base})-[a:ANTECEDENTE]->(cj:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(var:VariableDifusa)<-[en:ENTRADA]-(ev)
WITH ev, r, a.grupo AS grupo,
     max(CASE cj.tipo
           WHEN 'crisp' THEN CASE WHEN en.valor = cj.valor THEN 1.0 ELSE 0.0 END
           ELSE exp(-0.5 * ((en.valor - cj.c) / cj.sigma)^2)
         END) AS mu_grupo
WITH ev, r, min(mu_grupo) AS fuerza
WHERE fuerza >= 0.01
CREATE (ev)-[:ACTIVO {fuerza: round(fuerza, 2)}]->(r);

MATCH (ev:Evaluacion {estado:'Fuzzificada'}) SET ev.estado = 'Inferida';

// M3. Implicación MIN + agregación MAX sobre 101 puntos del universo de salida,
//     centroide y categoría = conjunto de salida dominante en el centroide.
MATCH (ev:Evaluacion {estado:'Inferida'})-[act:ACTIVO]->(:ReglaDifusa)-[:CONSECUENTE]->(sal:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(vs:VariableDifusa)
WITH ev, vs, collect({fuerza: act.fuerza, c: sal.c, sigma: sal.sigma}) AS reglas
UNWIND range(0, 100) AS i
WITH ev, vs, reglas, vs.min + (vs.max - vs.min) * i / 100.0 AS y
UNWIND reglas AS rg
WITH ev, vs, y, rg, exp(-0.5 * ((y - rg.c) / rg.sigma)^2) AS mu_sal
WITH ev, vs, y, max(CASE WHEN rg.fuerza < mu_sal THEN rg.fuerza ELSE mu_sal END) AS altura
WITH ev, vs, sum(y * altura) / sum(altura) AS centroide
MATCH (vs)-[:TIENE_CONJUNTO]->(s:ConjuntoDifuso)
WITH ev, centroide, s, exp(-0.5 * ((centroide - s.c) / s.sigma)^2) AS mu
ORDER BY mu DESC
WITH ev, centroide, collect(s)[0] AS dominante, collect(mu)[0] AS mu_dominante
SET ev.centroide = round(centroide, 2),
    ev.categoria = dominante.etiqueta,
    ev.mu_categoria = round(mu_dominante, 2),
    ev.estado = 'Resuelta'
CREATE (ev)-[:CONCLUYE]->(dominante);
// ---- fin del motor ----

MATCH (op:Operacion {estado:'Recibida'})-[:TIENE_EVALUACION]->(ev:Evaluacion {base:'SM2-DEM', estado:'Resuelta'}),
      (op)-[:EVALUA]->(e:Equipo)
CREATE (dem:DemandaComercial {id:'DEM-' + e.id, nivel: ev.categoria, indice: ev.centroide})
CREATE (e)-[:TIENE_DEMANDA]->(dem)
CREATE (ev)-[:DETERMINA]->(dem);


// =====================================================================
// 16. SM3 — COMPLETITUD DE DATOS (R3.3b)
// =====================================================================
MATCH (op:Operacion {estado:'Recibida'})-[:EVALUA]->(e:Equipo), (r:Regla {id:'R3.3b'})
WITH op, e, r,
     [x IN [
        CASE WHEN NOT EXISTS { (e)<-[:OFRECE]-(:Publicacion) } THEN 'precio' END,
        CASE WHEN NOT EXISTS { (e)-[:TIENE_VALUACION]->(:ValorMercadoAjustado) } THEN 'VMA' END,
        CASE WHEN NOT EXISTS { (e)-[:TIENE_PLAN]->(:PlanReacondicionamiento)-[:GENERA]->(:CostoReacondicionamiento) } THEN 'costo y cantidad de intervenciones' END,
        CASE WHEN NOT EXISTS { (e)-[:TIENE_DEMANDA]->(:DemandaComercial) } THEN 'demanda' END,
        CASE WHEN NOT EXISTS { (e)-[:TIENE_RIESGO]->(:RiesgoObsolescencia) } THEN 'riesgo' END
     ] WHERE x IS NOT NULL] AS faltantes
WHERE size(faltantes) > 0
SET op.estado = 'Verificacion_pendiente',
    op.accion_pendiente = 'SolicitarDato',
    op.dato_solicitado = reduce(s = '', x IN faltantes | s + CASE WHEN s = '' THEN '' ELSE ', ' END + x)
MERGE (op)-[:APLICA_REGLA]->(r);

MATCH (op:Operacion {estado:'Recibida'})
SET op.estado = 'Filtrada';


// =====================================================================
// 17. SM3 — INDICADORES ECONÓMICOS Y REGLAS DE RIESGO (R3.4 a R3.8)
// =====================================================================
MATCH (op:Operacion {estado:'Filtrada'})-[:EVALUA]->(e:Equipo)<-[:OFRECE]-(p:Publicacion),
      (e)-[:TIENE_VALUACION]->(vma:ValorMercadoAjustado),
      (e)-[:TIENE_PLAN]->(pl:PlanReacondicionamiento)-[:GENERA]->(c:CostoReacondicionamiento),
      (e)-[:TIENE_DEMANDA]->(dem:DemandaComercial),
      (e)-[:TIENE_RIESGO]->(rie:RiesgoObsolescencia)
MATCH (base:CriterioExperto {nombre:'margen_base'}),
      (liq:CriterioExperto {nombre:'margen_alta_liquidez'}),
      (ralto:CriterioExperto {nombre:'margen_riesgo_alto'}),
      (umb:CriterioExperto {nombre:'umbral_intervenciones'}),
      (prima:CriterioExperto {nombre:'prima_fallas'}),
      (r34:Regla {id:'R3.4'}), (r35:Regla {id:'R3.5'}), (r36:Regla {id:'R3.6'})
WITH op, e, p, vma, pl, c, base, liq, ralto, umb, prima, r34, r35, r36,
     (dem.nivel = 'Alta' AND rie.nivel = 'Bajo') AS aplica34,
     (rie.nivel = 'Alto') AS aplica35,
     (pl.cantidad_intervenciones >= umb.valor) AS aplica36
WITH op, e, p, vma, pl, c, base, liq, ralto, umb, prima, r34, r35, r36, aplica34, aplica35, aplica36,
     CASE WHEN aplica34 THEN liq.valor
          WHEN aplica35 THEN CASE WHEN ralto.valor > base.valor THEN ralto.valor ELSE base.valor END
          ELSE base.valor END
     + CASE WHEN aplica36 THEN prima.valor ELSE 0 END AS requerido
WITH op, e, p, vma, c, base, liq, ralto, umb, prima, r34, r35, r36, aplica34, aplica35, aplica36, requerido,
     100.0 * (vma.monto_tasado_ars - p.precio - c.monto_total) / vma.monto_tasado_ars AS margen,
     toFloat(c.monto_total) / vma.monto_tasado_ars AS ratio,
     vma.monto_tasado_ars - c.monto_total - vma.monto_tasado_ars * requerido / 100.0 AS contraoferta
CREATE (ind:IndicadoresEconomicos {id:'IND-' + e.id, margen_neto: round(margen, 1),
        margen_requerido: requerido, ratio_reparacion: round(ratio, 2),
        contraoferta: toInteger(round(contraoferta))})
CREATE (op)-[:TIENE_INDICADORES]->(ind)
MERGE (ind)-[:USA_CRITERIO]->(base)
FOREACH (x IN CASE WHEN aplica34 THEN [1] ELSE [] END |
         MERGE (ind)-[:USA_CRITERIO]->(liq) MERGE (ind)-[:APLICA_REGLA]->(r34))
FOREACH (x IN CASE WHEN aplica35 AND NOT aplica34 THEN [1] ELSE [] END |
         MERGE (ind)-[:USA_CRITERIO]->(ralto) MERGE (ind)-[:APLICA_REGLA]->(r35))
FOREACH (x IN CASE WHEN aplica36 THEN [1] ELSE [] END |
         MERGE (ind)-[:USA_CRITERIO]->(umb) MERGE (ind)-[:USA_CRITERIO]->(prima)
         MERGE (ind)-[:APLICA_REGLA]->(r36));

// R3.7: reparación antieconómica
MATCH (op:Operacion {estado:'Filtrada'})-[:EVALUA]->(e:Equipo),
      (op)-[:TIENE_INDICADORES]->(ind:IndicadoresEconomicos),
      (ce:CriterioExperto {nombre:'ratio_reparacion_max'}), (r:Regla {id:'R3.7'})
WHERE ind.ratio_reparacion > ce.valor
MERGE (dec:Decision {id:'DEC-' + e.id})
SET dec.tipo = 'DescartarPorRiesgo',
    dec.motivo = 'Reparación antieconómica: costo / VMA = ' + toString(ind.ratio_reparacion)
MERGE (e)-[:RECIBE_DECISION]->(dec)
MERGE (dec)-[:APLICA_REGLA]->(r)
MERGE (dec)-[:SE_BASA_EN]->(ind)
SET op.estado = 'Resuelta';

// R3.8: inmovilización de capital (riesgo Alto y demanda Baja, ambos inferidos por SM2)
MATCH (op:Operacion {estado:'Filtrada'})-[:EVALUA]->(e:Equipo),
      (e)-[:TIENE_RIESGO]->(rie:RiesgoObsolescencia {nivel:'Alto'}),
      (e)-[:TIENE_DEMANDA]->(dem:DemandaComercial {nivel:'Baja'}),
      (r:Regla {id:'R3.8'})
MERGE (dec:Decision {id:'DEC-' + e.id})
SET dec.tipo = 'DescartarPorRiesgo',
    dec.motivo = 'Riesgo de obsolescencia Alto (' + toString(rie.indice) + ') y demanda Baja (' + toString(dem.indice) + '): inmovilización de capital'
MERGE (e)-[:RECIBE_DECISION]->(dec)
MERGE (dec)-[:APLICA_REGLA]->(r)
MERGE (dec)-[:SE_BASA_EN]->(rie)
MERGE (dec)-[:SE_BASA_EN]->(dem)
SET op.estado = 'Resuelta';


// =====================================================================
// 18. SM3 DIFUSO — CONVENIENCIA DE COMPRA (PI3 de Romero, v2)
//     Reemplaza a R3.9–R3.11. Solo actúa sobre lo que pasó los filtros.
// =====================================================================
MATCH (op:Operacion {estado:'Filtrada'})-[:EVALUA]->(e:Equipo)<-[:OFRECE]-(p:Publicacion),
      (op)-[:TIENE_INDICADORES]->(ind:IndicadoresEconomicos)
SET op.brecha = round(ind.margen_neto - ind.margen_requerido, 1),
    op.descuento = CASE WHEN ind.contraoferta < p.precio
                        THEN round(100.0 * (p.precio - ind.contraoferta) / p.precio, 1)
                        ELSE 0.0 END,
    op.estado = 'Evaluacion_difusa';

MATCH (op:Operacion {estado:'Evaluacion_difusa'})-[:EVALUA]->(e:Equipo),
      (op)-[:TIENE_INDICADORES]->(ind:IndicadoresEconomicos),
      (vB:VariableDifusa {nombre:'Brecha_Margen'}), (vD:VariableDifusa {nombre:'Descuento_Requerido'}),
      (vp:VersionParametros {id:'FIS-SM3-v2'})
CREATE (ev:Evaluacion {id:'EV-' + e.id + '-CONV', base:'SM3-CONV', estado:'Pendiente', fecha: datetime()})
CREATE (op)-[:TIENE_EVALUACION]->(ev)
CREATE (ev)-[:SOBRE]->(op)
CREATE (ind)-[:DETERMINA]->(ev)
CREATE (ev)-[:ENTRADA {valor: op.brecha}]->(vB)
CREATE (ev)-[:ENTRADA {valor: op.descuento}]->(vD)
CREATE (ev)-[:USA_VERSION]->(vp);

// ---- Motor difuso genérico (mismo código en cada etapa) ----
// M1. Fuzzificación: grado de cada entrada en cada conjunto de su variable.
//     Gaussiana: exp(-0.5 * ((x - c) / sigma)^2). Crisp: 1 si coincide, 0 si no.
MATCH (ev:Evaluacion {estado:'Pendiente'})-[en:ENTRADA]->(var:VariableDifusa)-[:TIENE_CONJUNTO]->(cj:ConjuntoDifuso)
WITH ev, cj,
     CASE cj.tipo
       WHEN 'crisp' THEN CASE WHEN en.valor = cj.valor THEN 1.0 ELSE 0.0 END
       ELSE exp(-0.5 * ((en.valor - cj.c) / cj.sigma)^2)
     END AS mu
WHERE mu >= 0.01
CREATE (ev)-[:TIENE_GRADO {mu: round(mu, 2)}]->(cj);

MATCH (ev:Evaluacion {estado:'Pendiente'}) SET ev.estado = 'Fuzzificada';

// M2. Fuerza de cada regla de la base: máx dentro de cada grupo (O), mín entre grupos (Y).
MATCH (ev:Evaluacion {estado:'Fuzzificada'})
MATCH (r:ReglaDifusa {base: ev.base})-[a:ANTECEDENTE]->(cj:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(var:VariableDifusa)<-[en:ENTRADA]-(ev)
WITH ev, r, a.grupo AS grupo,
     max(CASE cj.tipo
           WHEN 'crisp' THEN CASE WHEN en.valor = cj.valor THEN 1.0 ELSE 0.0 END
           ELSE exp(-0.5 * ((en.valor - cj.c) / cj.sigma)^2)
         END) AS mu_grupo
WITH ev, r, min(mu_grupo) AS fuerza
WHERE fuerza >= 0.01
CREATE (ev)-[:ACTIVO {fuerza: round(fuerza, 2)}]->(r);

MATCH (ev:Evaluacion {estado:'Fuzzificada'}) SET ev.estado = 'Inferida';

// M3. Implicación MIN + agregación MAX sobre 101 puntos del universo de salida,
//     centroide y categoría = conjunto de salida dominante en el centroide.
MATCH (ev:Evaluacion {estado:'Inferida'})-[act:ACTIVO]->(:ReglaDifusa)-[:CONSECUENTE]->(sal:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(vs:VariableDifusa)
WITH ev, vs, collect({fuerza: act.fuerza, c: sal.c, sigma: sal.sigma}) AS reglas
UNWIND range(0, 100) AS i
WITH ev, vs, reglas, vs.min + (vs.max - vs.min) * i / 100.0 AS y
UNWIND reglas AS rg
WITH ev, vs, y, rg, exp(-0.5 * ((y - rg.c) / rg.sigma)^2) AS mu_sal
WITH ev, vs, y, max(CASE WHEN rg.fuerza < mu_sal THEN rg.fuerza ELSE mu_sal END) AS altura
WITH ev, vs, sum(y * altura) / sum(altura) AS centroide
MATCH (vs)-[:TIENE_CONJUNTO]->(s:ConjuntoDifuso)
WITH ev, centroide, s, exp(-0.5 * ((centroide - s.c) / s.sigma)^2) AS mu
ORDER BY mu DESC
WITH ev, centroide, collect(s)[0] AS dominante, collect(mu)[0] AS mu_dominante
SET ev.centroide = round(centroide, 2),
    ev.categoria = dominante.etiqueta,
    ev.mu_categoria = round(mu_dominante, 2),
    ev.estado = 'Resuelta'
CREATE (ev)-[:CONCLUYE]->(dominante);
// ---- fin del motor ----


// =====================================================================
// 19. DECISIÓN FINAL A PARTIR DE LA CATEGORÍA DIFUSA
// =====================================================================
MATCH (op:Operacion {estado:'Evaluacion_difusa'})-[:TIENE_EVALUACION]->(ev:Evaluacion {base:'SM3-CONV'}),
      (op)-[:EVALUA]->(e:Equipo),
      (op)-[:TIENE_INDICADORES]->(ind:IndicadoresEconomicos)
WITH op, e, ev, ind,
     CASE ev.categoria WHEN 'Comprar'  THEN 'Comprar'
                       WHEN 'Negociar' THEN 'ComprarConOfertaMenor'
                       ELSE 'DescartarPorRiesgo' END AS tipo
MERGE (dec:Decision {id:'DEC-' + e.id})
SET dec.tipo = tipo,
    dec.motivo = 'Inferencia difusa SM3: conveniencia ' + toString(ev.centroide) + ' → ' + ev.categoria,
    dec.contraoferta = CASE WHEN tipo = 'ComprarConOfertaMenor' AND op.descuento > 0
                            THEN ind.contraoferta END,
    dec.observacion = CASE WHEN tipo = 'ComprarConOfertaMenor' AND op.descuento = 0
                           THEN 'El precio pedido ya cumple el margen requerido: no hay descuento que pedir' END
MERGE (e)-[:RECIBE_DECISION]->(dec)
MERGE (dec)-[:SE_JUSTIFICA_EN]->(ev)
SET op.estado = 'Resuelta';


// =====================================================================
// 20. VINCULACIÓN INSTANCIA → FRAME
// =====================================================================
MATCH (f:Frame), (n)
WHERE NOT n:Frame AND NOT n:Slot AND f.nombre IN labels(n)
MERGE (n)-[:INSTANCIA_DE]->(f);
