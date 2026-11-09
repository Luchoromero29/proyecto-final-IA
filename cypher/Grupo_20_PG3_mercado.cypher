// =====================================================================
// EvalTIC — Grupo 20 (5K09) — PG3
// Script 3: CATÁLOGO DE MERCADO, COSTOS DE REPARACIÓN Y CRITERIOS v2
//
// Se ejecuta DESPUÉS de Grupo_20_PG2_U1_carga.cypher. Es idempotente
// (usa MERGE): se puede correr las veces que haga falta sin duplicar nodos.
//
// Objetivo: que el orquestador no tenga ningún precio, costo ni umbral
// escrito en el código Python. Todo se lee de estos nodos:
//   (:SegmentoMercado)   precio de un equipo nuevo equivalente, rotación y repuestos
//   (:ModeloReferencia)  año de lanzamiento, soporte de Windows 11, rotación y repuestos
//   (:CostoReparacion)   costo de cada intervención de SM1
//   (:CriterioExperto)   umbrales (se agregan CE-21 a CE-28 y se versionan CE-04, CE-09, CE-10)
//
// Todos los valores son PROVISIONALES. Fuente de precios de equipos nuevos:
// relevamiento web del 5/11/2026 (Mercado Libre / tiendas, guía CuálDura).
// Los costos de reparación son estimaciones del grupo a validar con el
// experto (M. Romero). Ninguno está validado todavía.
// =====================================================================


// ---------------------------------------------------------------------
// 21. RESTRICCIONES
// ---------------------------------------------------------------------
CREATE CONSTRAINT segmento_id IF NOT EXISTS FOR (n:SegmentoMercado) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT modelo_ref_id IF NOT EXISTS FOR (n:ModeloReferencia) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT costo_rep_tarea IF NOT EXISTS FOR (n:CostoReparacion) REQUIRE n.tarea IS UNIQUE;


// ---------------------------------------------------------------------
// 22. SEGMENTOS DE MERCADO
//   patron: expresión regular sobre el texto del aviso en minúsculas
//           (marca + modelo + procesador + texto completo).
//   prioridad: si coinciden varios, gana el de mayor prioridad
//              (línea específica > gama por procesador).
//   precio_nuevo_ref_ars: precio de un equipo NUEVO equivalente hoy;
//              SM2 lo deprecia según la antigüedad.
// ---------------------------------------------------------------------
UNWIND [
  {id:'SEG-APPLE',       nombre:'Apple MacBook',              prioridad:90, precio:2300000, dias:15, rep:3,
   patron:'(?s).*\\b(macbook|apple)\\b.*'},
  {id:'SEG-GAMER',       nombre:'Gamer (GPU dedicada)',       prioridad:80, precio:2000000, dias:15, rep:6,
   patron:'(?s).*\\b(rtx|gtx|tuf|nitro|legion|loq|rog|omen|victus|predator|katana|gamer)\\b.*'},
  {id:'SEG-CORPORATIVA', nombre:'Línea corporativa',          prioridad:70, precio:1500000, dias:12, rep:9,
   patron:'(?s).*\\b(thinkpad|latitude|elitebook|probook|vostro|expertbook|travelmate)\\b.*'},
  {id:'SEG-ALTA',        nombre:'Gama alta (i7/i9, Ryzen 7/9)', prioridad:40, precio:1600000, dias:20, rep:6,
   patron:'(?s).*\\b(i7|i9|core\\s*i7|core\\s*i9|ryzen\\s*7|ryzen\\s*9|r7|r9|ultra\\s*7|ultra\\s*9)\\b.*'},
  {id:'SEG-MEDIA',       nombre:'Gama media (i5, Ryzen 5)',   prioridad:30, precio:1150000, dias:15, rep:7,
   patron:'(?s).*\\b(i5|core\\s*i5|ryzen\\s*5|r5|ultra\\s*5)\\b.*'},
  {id:'SEG-ENTRADA',     nombre:'Gama de entrada (i3, Ryzen 3)', prioridad:20, precio:850000, dias:20, rep:7,
   patron:'(?s).*\\b(i3|core\\s*i3|ryzen\\s*3|r3)\\b.*'},
  {id:'SEG-BASICA',      nombre:'Básica (Celeron, Pentium, Athlon, N-series)', prioridad:10, precio:650000, dias:30, rep:6,
   patron:'(?s).*\\b(celeron|pentium|athlon|n4020|n4500|n100|n200|i3-n305|atom)\\b.*'}
] AS s
MERGE (sg:SegmentoMercado {id: s.id})
SET sg.nombre = s.nombre, sg.prioridad = s.prioridad, sg.patron = s.patron,
    sg.precio_nuevo_ref_ars = s.precio, sg.dias_promedio_venta = s.dias, sg.indice_repuestos = s.rep,
    sg.fuente = 'Relevamiento web 5/11/2026 (Mercado Libre, tiendas, CuálDura)',
    sg.estado_validacion = 'Provisional', sg.version = 'v1';


// ---------------------------------------------------------------------
// 23. MODELOS DE REFERENCIA
//   Aportan datos del modelo que el vendedor no suele poner en el aviso
//   (año de lanzamiento, soporte de Windows 11, rotación, repuestos).
//   seg = null → el segmento (y el precio) lo decide el procesador.
// ---------------------------------------------------------------------
UNWIND [
  {id:'MOD-T440P',  marca:'Lenovo', nombre:'ThinkPad T440p',     seg:'SEG-CORPORATIVA', anio:2014, w11:false, dias:65, rep:2, pri:60, patron:'(?s).*\\bt440p?\\b.*'},
  {id:'MOD-T480',   marca:'Lenovo', nombre:'ThinkPad T480',      seg:'SEG-CORPORATIVA', anio:2018, w11:true,  dias:12, rep:9, pri:60, patron:'(?s).*\\bt480s?\\b.*'},
  {id:'MOD-T490',   marca:'Lenovo', nombre:'ThinkPad T490',      seg:'SEG-CORPORATIVA', anio:2019, w11:true,  dias:10, rep:9, pri:60, patron:'(?s).*\\bt490s?\\b.*'},
  {id:'MOD-L380',   marca:'Lenovo', nombre:'ThinkPad L380',      seg:'SEG-CORPORATIVA', anio:2018, w11:true,  dias:15, rep:8, pri:60, patron:'(?s).*\\bl380\\b.*'},
  {id:'MOD-IDEA1',  marca:'Lenovo', nombre:'IdeaPad 1',          seg:'SEG-BASICA',      anio:2022, w11:true,  dias:30, rep:6, pri:50, patron:'(?s).*\\bideapad\\s*1\\b.*'},
  {id:'MOD-IDEA3',  marca:'Lenovo', nombre:'IdeaPad 3 / Slim 3', seg:null,              anio:2021, w11:true,  dias:15, rep:7, pri:40, patron:'(?s).*\\bideapad\\s*(slim\\s*)?3\\b.*'},
  {id:'MOD-IDEA5',  marca:'Lenovo', nombre:'IdeaPad 5 / Slim 5', seg:null,              anio:2021, w11:true,  dias:15, rep:7, pri:40, patron:'(?s).*\\bideapad\\s*(slim\\s*)?5\\b.*'},
  {id:'MOD-ASP5',   marca:'Acer',   nombre:'Aspire 5',           seg:null,              anio:2020, w11:true,  dias:20, rep:6, pri:40, patron:'(?s).*\\baspire\\s*5\\b.*'},
  {id:'MOD-ASP3',   marca:'Acer',   nombre:'Aspire 3',           seg:null,              anio:2021, w11:true,  dias:20, rep:6, pri:40, patron:'(?s).*\\baspire\\s*3\\b.*'},
  {id:'MOD-INSP15', marca:'Dell',   nombre:'Inspiron 15',        seg:null,              anio:2020, w11:true,  dias:25, rep:6, pri:40, patron:'(?s).*\\binspiron\\s*15\\b.*'},
  {id:'MOD-PAV15',  marca:'HP',     nombre:'Pavilion 15',        seg:null,              anio:2020, w11:true,  dias:25, rep:6, pri:45, patron:'(?s).*\\bpavilion\\b.*'},
  {id:'MOD-HP15',   marca:'HP',     nombre:'HP 15 / 240 / 250',  seg:null,              anio:2021, w11:true,  dias:25, rep:6, pri:35, patron:'(?s).*\\bhp\\b.*\\b(15|240|250)\\b.*'},
  {id:'MOD-VIVO',   marca:'Asus',   nombre:'VivoBook',           seg:null,              anio:2022, w11:true,  dias:20, rep:6, pri:40, patron:'(?s).*\\bvivobook\\b.*'},
  {id:'MOD-MBA17',  marca:'Apple',  nombre:'MacBook Air 2017',   seg:'SEG-APPLE',       anio:2017, w11:false, dias:40, rep:3, pri:60, patron:'(?s).*\\bmacbook\\s*air\\b.*\\b2017\\b.*'},
  {id:'MOD-MBAM1',  marca:'Apple',  nombre:'MacBook Air M1',     seg:'SEG-APPLE',       anio:2020, w11:true,  dias:12, rep:3, pri:60, patron:'(?s).*\\bmacbook\\s*air\\b.*\\bm1\\b.*'},
  {id:'MOD-MBP15',  marca:'Apple',  nombre:'MacBook Pro 2015',   seg:'SEG-APPLE',       anio:2015, w11:false, dias:45, rep:2, pri:60, patron:'(?s).*\\bmacbook\\s*pro\\b.*\\b2015\\b.*'}
] AS m
MERGE (mr:ModeloReferencia {id: m.id})
SET mr.marca = m.marca, mr.nombre = m.nombre, mr.patron = m.patron, mr.prioridad = m.pri,
    mr.anio_lanzamiento = m.anio, mr.soporte_w11 = m.w11,
    mr.dias_promedio_venta = m.dias, mr.indice_repuestos = m.rep,
    mr.estado_validacion = 'Provisional', mr.version = 'v1'
WITH mr, m
OPTIONAL MATCH (mr)-[old:PERTENECE_A_SEGMENTO]->()
DELETE old
WITH mr, m
OPTIONAL MATCH (sg:SegmentoMercado {id: m.seg})
FOREACH (_ IN CASE WHEN sg IS NULL THEN [] ELSE [1] END | MERGE (mr)-[:PERTENECE_A_SEGMENTO]->(sg));


// ---------------------------------------------------------------------
// 24. COSTOS DE REPARACIÓN (SM1)
// ---------------------------------------------------------------------
UNWIND [
  {id:'COS-BAT', tarea:'bateria',          desc:'Reemplazo de batería',                         costo:75000},
  {id:'COS-PAN', tarea:'pantalla',         desc:'Reemplazo de módulo de pantalla',              costo:160000},
  {id:'COS-TEC', tarea:'teclado',          desc:'Reemplazo de teclado',                         costo:55000},
  {id:'COS-SSD', tarea:'ssd_upgrade',      desc:'Reemplazo de HDD por SSD 480 GB',              costo:45000},
  {id:'COS-RAM', tarea:'ram_upgrade',      desc:'Ampliación de RAM a 8 GB',                     costo:40000},
  {id:'COS-TER', tarea:'service_termico',  desc:'Service térmico (pasta térmica y limpieza)',   costo:30000},
  {id:'COS-CAR', tarea:'cargador',         desc:'Cargador compatible',                          costo:35000},
  {id:'COS-MO',  tarea:'mano_de_obra',     desc:'Mano de obra y control de calidad',            costo:40000}
] AS c
MERGE (cr:CostoReparacion {tarea: c.tarea})
SET cr.id = c.id, cr.descripcion = c.desc, cr.costo_ars = c.costo,
    cr.fuente = 'Estimación del grupo, noviembre de 2026 (a validar con M. Romero)',
    cr.estado_validacion = 'Provisional', cr.version = 'v1'
WITH cr
MATCH (sm:Submodulo {id:'SM1'})
MERGE (cr)-[:PERTENECE_A]->(sm);


// ---------------------------------------------------------------------
// 25. CRITERIOS EXPERTOS NUEVOS (CE-21 a CE-28)
// ---------------------------------------------------------------------
UNWIND [
  {id:'CE-21', modulo:'SM2', nombre:'deprec_anual_inicial',  valor:10,   unidad:'%'},
  {id:'CE-22', modulo:'SM2', nombre:'deprec_anual_posterior', valor:8,   unidad:'%'},
  {id:'CE-23', modulo:'SM2', nombre:'anios_deprec_inicial',  valor:3,    unidad:'años'},
  {id:'CE-24', modulo:'SM2', nombre:'valor_residual_min',    valor:20,   unidad:'%'},
  {id:'CE-25', modulo:'SM2', nombre:'factor_riesgo_medio',   valor:90,   unidad:'%'},
  {id:'CE-26', modulo:'SM2', nombre:'factor_riesgo_alto',    valor:75,   unidad:'%'},
  {id:'CE-27', modulo:'SM1', nombre:'ram_objetivo',          valor:8,    unidad:'GB'},
  {id:'CE-28', modulo:'SM2', nombre:'anio_min_w11',          valor:2018, unidad:'año'}
] AS c
MERGE (ce:CriterioExperto {nombre: c.nombre})
ON CREATE SET ce.id = c.id, ce.valor = c.valor, ce.unidad = c.unidad, ce.version = 'v1',
              ce.vigente_desde = date('2026-11-09'), ce.estado_validacion = 'Provisional',
              ce.fuente = 'PG3: parámetros que estaban escritos en el código'
WITH ce, c
MATCH (sm:Submodulo {id: c.modulo})
MERGE (ce)-[:PERTENECE_A]->(sm);


// ---------------------------------------------------------------------
// 26. CRITERIOS VERSIONADOS (v2): valores llevados a precios de noviembre de 2026
//     Se conserva el valor anterior para la trazabilidad.
// ---------------------------------------------------------------------
UNWIND [
  {nombre:'costo_service_termico', valor:30000},
  {nombre:'reval_ssd',             valor:45000},
  {nombre:'reval_ram',             valor:35000}
] AS c
MATCH (ce:CriterioExperto {nombre: c.nombre})
WHERE ce.version = 'v1'
SET ce.valor_anterior = ce.valor, ce.valor = c.valor, ce.version = 'v2',
    ce.vigente_desde = date('2026-11-09'),
    ce.fuente = 'Actualización de precios, noviembre de 2026 (provisional)';
