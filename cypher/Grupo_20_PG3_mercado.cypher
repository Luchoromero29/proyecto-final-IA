// =====================================================================
// EvalTIC — Grupo 20 (5K09) — PG3
// Script 3: MERCADO POR COMPONENTES, COSTOS DE REPARACIÓN Y CRITERIOS v2
//
// Se ejecuta DESPUÉS de Grupo_20_PG2_U1_carga.cypher. Es idempotente:
// se puede correr las veces que haga falta sin duplicar nodos.
//
// Objetivo: que el orquestador no tenga ningún precio, costo ni umbral
// escrito en el código Python. Todo se lee de estos nodos:
//   (:Procesador)        familia + generación: año, soporte de Windows 11 y valor de referencia
//   (:Linea)             línea o marca (ThinkPad, VivoBook, Bangho...): factor de precio
//   (:GrupoLinea)        corporativa / consumo / gamer / premium / nacional: rotación y repuestos
//   (:CapacidadRAM)      factor de precio por cantidad de memoria
//   (:AvisoMercado)      avisos reales relevados (datos/relevamiento_mercado.csv)
//   (:CostoReparacion)   costo de cada intervención de SM1
//   (:CriterioExperto)   umbrales (CE-21 a CE-30; se versionan CE-04, CE-09, CE-10)
//
// Valuación por componentes (precios hedónicos): el valor de un equipo usado
// se explica por sus componentes y su línea, no por el modelo exacto.
//   valor de referencia = valor del procesador × factor de la línea × factor de la RAM
// El valor del procesador y el factor de cada línea se CALIBRAN en este mismo
// script con medianas sobre los avisos relevados (sección 31).
//
// Todos los valores son PROVISIONALES. Precios: relevamiento de Mercado Libre
// del 9/11/2026 (289 avisos de equipos usados). Costos de reparación y
// factores de RAM: estimación del grupo, a validar con el experto (M. Romero).
// =====================================================================


// ---------------------------------------------------------------------
// 21. RESTRICCIONES Y LIMPIEZA DEL CATÁLOGO ANTERIOR
//   El catálogo v1 (segmentos de mercado, modelos de referencia y
//   generaciones de procesador) se reemplaza por el modelo de componentes.
// ---------------------------------------------------------------------
MATCH (n) WHERE n:SegmentoMercado OR n:ModeloReferencia OR n:GeneracionProcesador
DETACH DELETE n;
DROP CONSTRAINT segmento_id IF EXISTS;
DROP CONSTRAINT modelo_ref_id IF EXISTS;
DROP CONSTRAINT gen_proc_id IF EXISTS;

CREATE CONSTRAINT procesador_nombre IF NOT EXISTS FOR (n:Procesador) REQUIRE n.nombre IS UNIQUE;
CREATE CONSTRAINT linea_nombre IF NOT EXISTS FOR (n:Linea) REQUIRE n.nombre IS UNIQUE;
CREATE CONSTRAINT grupo_linea_id IF NOT EXISTS FOR (n:GrupoLinea) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT ram_gb IF NOT EXISTS FOR (n:CapacidadRAM) REQUIRE n.gb IS UNIQUE;
CREATE CONSTRAINT aviso_id IF NOT EXISTS FOR (n:AvisoMercado) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT costo_rep_tarea IF NOT EXISTS FOR (n:CostoReparacion) REQUIRE n.tarea IS UNIQUE;


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


// ---------------------------------------------------------------------
// 27. PROCESADORES (familia + generación)
//   patron: regex sobre el campo "procesador" que extrae el LLM, en minúsculas.
//   prioridad: si coinciden varios gana el más específico
//              (Apple > Ryzen por serie > Intel por generación > familia sola).
//   Los nodos "familia sola" (ej. 'Core i5') cubren avisos que no dicen la
//   generación: no tienen año, así que el año tiene que venir del aviso.
//   valor_ref_ars se calcula en la sección 31 a partir de los avisos.
// ---------------------------------------------------------------------
UNWIND [
  {num:'2',  suf:'da', anio:2011, w11:false, mod:'2\\d{3}(m|qm)'},
  {num:'3',  suf:'ra', anio:2012, w11:false, mod:'3\\d{3}(m|qm|u)'},
  {num:'4',  suf:'ta', anio:2013, w11:false, mod:'4\\d{3}(m|mq|hq|u)'},
  {num:'5',  suf:'ta', anio:2015, w11:false, mod:'5\\d{3}u'},
  {num:'6',  suf:'ta', anio:2015, w11:false, mod:'6\\d{3}(u|hq)'},
  {num:'7',  suf:'ma', anio:2017, w11:false, mod:'7\\d{3}(u|hq|h)'},
  {num:'8',  suf:'va', anio:2018, w11:true,  mod:'8\\d{3}(u|h|hq|y)'},
  {num:'9',  suf:'na', anio:2019, w11:true,  mod:'9\\d{3}(h|hk)'},
  {num:'10', suf:'ma', anio:2020, w11:true,  mod:'10\\d{3}(u|h|g\\d)'},
  {num:'11', suf:'va', anio:2021, w11:true,  mod:'11\\d{2}(g\\d|h)'},
  {num:'12', suf:'va', anio:2022, w11:true,  mod:'12\\d{2}(u|h|p)'},
  {num:'13', suf:'va', anio:2023, w11:true,  mod:'13\\d{2}(u|h|p|hx)'},
  {num:'14', suf:'va', anio:2024, w11:true,  mod:'14\\d{3}(hx|h)'}
] AS g
UNWIND [{t:'3', gama:'entrada'}, {t:'5', gama:'media'}, {t:'7', gama:'alta'}] AS f
MERGE (p:Procesador {nombre: 'Core i' + f.t + ' ' + g.num + g.suf + ' gen'})
SET p.familia = 'Core i' + f.t, p.gama = f.gama, p.anio = g.anio, p.soporte_w11 = g.w11,
    p.prioridad = 40,
    p.patron = '(?s)(?=.*i' + f.t + '\\b)(?=.*\\b' + g.num + '\\s*[a-z°º.]{0,3}\\s*(gen|generaci)).*'
             + '|(?s).*i' + f.t + '[\\s-]*' + g.mod + '\\b.*';

UNWIND [
  {s:'3000', anio:2019, mod:'3\\d{2}0u'},
  {s:'4000', anio:2020, mod:'4\\d{2}0(u|h|hs)'},
  {s:'5000', anio:2021, mod:'5\\d{2}[05](u|h|hs)'},
  {s:'7020', anio:2022, mod:'7\\d20u'},
  {s:'7030', anio:2023, mod:'7\\d30u'},
  {s:'7035', anio:2023, mod:'7\\d35(u|hs|h)'}
] AS g
UNWIND [{t:'3', gama:'entrada'}, {t:'5', gama:'media'}, {t:'7', gama:'alta'}] AS f
MERGE (p:Procesador {nombre: 'Ryzen ' + f.t + ' ' + g.s})
SET p.familia = 'Ryzen ' + f.t, p.gama = f.gama, p.anio = g.anio, p.soporte_w11 = true,
    p.prioridad = 45,
    p.patron = '(?s).*(ryzen|\\br)\\s*' + f.t + '\\b.*' + g.mod + '\\b.*';

UNWIND [
  {n:'Apple M1',      fam:'Apple M',     gama:'apple',   anio:2020, w11:true,  pri:60, p:'(?s).*\\bm1\\b.*'},
  {n:'Apple M2',      fam:'Apple M',     gama:'apple',   anio:2022, w11:true,  pri:60, p:'(?s).*\\bm2\\b.*'},
  {n:'Apple M3',      fam:'Apple M',     gama:'apple',   anio:2024, w11:true,  pri:60, p:'(?s).*\\bm3\\b.*'},
  {n:'Celeron N4000', fam:'Celeron',     gama:'basica',  anio:2017, w11:true,  pri:50, p:'(?s).*n4000.*'},
  {n:'Celeron N4020', fam:'Celeron',     gama:'basica',  anio:2019, w11:true,  pri:50, p:'(?s).*n4020.*'},
  {n:'Celeron N4120', fam:'Celeron',     gama:'basica',  anio:2019, w11:true,  pri:50, p:'(?s).*n4120.*'},
  {n:'Pentium N5030', fam:'Pentium',     gama:'basica',  anio:2019, w11:true,  pri:50, p:'(?s).*n5030.*'},
  {n:'Intel N100',    fam:'Intel N',     gama:'basica',  anio:2023, w11:true,  pri:50, p:'(?s).*\\bn100\\b.*'},
  {n:'Core i3 N305',  fam:'Core i3',     gama:'entrada', anio:2023, w11:true,  pri:50, p:'(?s).*n305.*'},
  {n:'Core 3',        fam:'Core',        gama:'entrada', anio:2024, w11:true,  pri:50, p:'(?s).*\\bcore\\s+3\\b.*'},
  {n:'Core Ultra 5',  fam:'Core Ultra',  gama:'media',   anio:2023, w11:true,  pri:50, p:'(?s).*ultra\\s*5.*'},
  {n:'Core Ultra 7',  fam:'Core Ultra',  gama:'alta',    anio:2023, w11:true,  pri:50, p:'(?s).*ultra\\s*7.*'},
  {n:'Athlon Silver', fam:'Athlon',      gama:'basica',  anio:2020, w11:true,  pri:50, p:'(?s).*athlon\\s*silver.*'},
  {n:'Athlon 3150U',  fam:'Athlon',      gama:'basica',  anio:2020, w11:true,  pri:50, p:'(?s).*3150u.*'},
  {n:'AMD A9',        fam:'AMD A',       gama:'basica',  anio:2016, w11:false, pri:50, p:'(?s).*\\ba9[\\s-]*9\\d{3}.*|(?s).*amd\\s*a9\\b.*'},
  {n:'AMD A12',       fam:'AMD A',       gama:'basica',  anio:2016, w11:false, pri:50, p:'(?s).*\\ba12[\\s-]*9\\d{3}.*|(?s).*amd\\s*a12\\b.*'},
  {n:'Intel Atom',    fam:'Atom',        gama:'basica',  anio:2010, w11:false, pri:50, p:'(?s).*\\batom\\b.*'},
  {n:'Snapdragon X',  fam:'Snapdragon',  gama:'media',   anio:2024, w11:true,  pri:50, p:'(?s).*snapdragon.*'},
  // Familia sola (sin generación): no aportan año ni soporte de Windows 11
  {n:'Celeron',       fam:'Celeron',     gama:'basica',  anio:null, w11:null,  pri:10, p:'(?s).*celeron.*'},
  {n:'Pentium',       fam:'Pentium',     gama:'basica',  anio:null, w11:null,  pri:10, p:'(?s).*pentium.*'},
  {n:'Core i3',       fam:'Core i3',     gama:'entrada', anio:null, w11:null,  pri:10, p:'(?s).*i3\\b.*'},
  {n:'Core i5',       fam:'Core i5',     gama:'media',   anio:null, w11:null,  pri:10, p:'(?s).*i5\\b.*'},
  {n:'Core i7',       fam:'Core i7',     gama:'alta',    anio:null, w11:null,  pri:10, p:'(?s).*i7\\b.*'},
  {n:'Ryzen 3',       fam:'Ryzen 3',     gama:'entrada', anio:null, w11:null,  pri:10, p:'(?s).*(ryzen|\\br)\\s*3\\b.*'},
  {n:'Ryzen 5',       fam:'Ryzen 5',     gama:'media',   anio:null, w11:null,  pri:10, p:'(?s).*(ryzen|\\br)\\s*5\\b.*'},
  {n:'Ryzen 7',       fam:'Ryzen 7',     gama:'alta',    anio:null, w11:null,  pri:10, p:'(?s).*(ryzen|\\br)\\s*7\\b.*'}
] AS x
MERGE (p:Procesador {nombre: x.n})
SET p.familia = x.fam, p.gama = x.gama, p.anio = x.anio, p.soporte_w11 = x.w11,
    p.prioridad = x.pri, p.patron = x.p;

MATCH (p:Procesador)
SET p.estado_validacion = 'Provisional', p.version = 'v1',
    p.fuente_anio = 'Fechas de lanzamiento de los fabricantes (aprox.)';


// ---------------------------------------------------------------------
// 28. GRUPOS DE LÍNEA Y LÍNEAS
//   El grupo aporta rotación (días promedio de venta) e índice de repuestos
//   para la lógica difusa de SM2, y un factor de precio de respaldo cuando
//   la línea tiene pocos avisos relevados.
//   patron: regex sobre marca + modelo + texto del aviso, en minúsculas.
//   Las líneas "<Marca> (otras)" atrapan equipos de marcas conocidas cuya
//   línea no está registrada (prioridad baja).
// ---------------------------------------------------------------------
UNWIND [
  {id:'GRP-CORP',     nombre:'Corporativa', dias:12, rep:9},
  {id:'GRP-CONSUMO',  nombre:'Consumo',     dias:20, rep:7},
  {id:'GRP-GAMER',    nombre:'Gamer',       dias:15, rep:6},
  {id:'GRP-PREMIUM',  nombre:'Premium',     dias:15, rep:4},
  {id:'GRP-NACIONAL', nombre:'Nacional / genérica', dias:30, rep:5}
] AS g
MERGE (gl:GrupoLinea {id: g.id})
SET gl.nombre = g.nombre, gl.dias_promedio_venta = g.dias, gl.indice_repuestos = g.rep,
    gl.estado_validacion = 'Provisional', gl.version = 'v1',
    gl.fuente = 'Estimación del grupo (rotación y repuestos), noviembre de 2026';

MATCH (l:Linea) DETACH DELETE l;

UNWIND [
  // Lenovo
  {n:'ThinkPad',       m:'Lenovo',  g:'GRP-CORP',     pri:60, p:'(?s).*(thinkpad|\\bt4[4-9]0[ps]?\\b|\\bt14s?\\b|x1\\s*carbon).*'},
  {n:'ThinkBook',      m:'Lenovo',  g:'GRP-CORP',     pri:60, p:'(?s).*thinkbook.*'},
  {n:'IdeaPad Gaming', m:'Lenovo',  g:'GRP-GAMER',    pri:65, p:'(?s).*ideapad\\s*gaming.*'},
  {n:'IdeaPad',        m:'Lenovo',  g:'GRP-CONSUMO',  pri:55, p:'(?s).*(ideapad|\\bslim\\s*[357]i?\\b|\\bip[135]\\b).*'},
  {n:'Legion',         m:'Lenovo',  g:'GRP-GAMER',    pri:60, p:'(?s).*(legion|\\bloq\\b).*'},
  {n:'Yoga',           m:'Lenovo',  g:'GRP-PREMIUM',  pri:60, p:'(?s).*\\byoga\\b.*'},
  {n:'Lenovo V',       m:'Lenovo',  g:'GRP-CONSUMO',  pri:55, p:'(?s).*lenovo.*\\bv(14|15|130|330|340)\\b.*'},
  // Dell
  {n:'Latitude',       m:'Dell',    g:'GRP-CORP',     pri:60, p:'(?s).*latitude.*'},
  {n:'Vostro',         m:'Dell',    g:'GRP-CORP',     pri:60, p:'(?s).*vostro.*'},
  {n:'Inspiron',       m:'Dell',    g:'GRP-CONSUMO',  pri:60, p:'(?s).*inspiron.*'},
  // HP
  {n:'ProBook',        m:'HP',      g:'GRP-CORP',     pri:60, p:'(?s).*(probook|pro\\s*book|\\b4[34]0\\s*g\\d).*'},
  {n:'EliteBook',      m:'HP',      g:'GRP-CORP',     pri:60, p:'(?s).*elitebook.*'},
  {n:'Pavilion',       m:'HP',      g:'GRP-CONSUMO',  pri:60, p:'(?s).*pavilion.*'},
  {n:'Envy',           m:'HP',      g:'GRP-PREMIUM',  pri:60, p:'(?s).*\\benvy\\b.*'},
  {n:'Victus',         m:'HP',      g:'GRP-GAMER',    pri:60, p:'(?s).*(victus|\\bomen\\b).*'},
  {n:'HP 15/240/250',  m:'HP',      g:'GRP-CONSUMO',  pri:40, p:'(?s).*\\bhp\\b.*\\b(14|15|17|240|245|250|255)\\b.*'},
  // Asus
  {n:'VivoBook',       m:'Asus',    g:'GRP-CONSUMO',  pri:60, p:'(?s).*(vivobook|\\bx5\\d\\d[a-z]*\\b|\\bx1[0-9]0\\d[a-z]*\\b).*'},
  {n:'ZenBook',        m:'Asus',    g:'GRP-PREMIUM',  pri:60, p:'(?s).*zenbook.*'},
  {n:'TUF',            m:'Asus',    g:'GRP-GAMER',    pri:60, p:'(?s).*(\\btuf\\b|\\brog\\b).*'},
  // Acer
  {n:'Aspire',         m:'Acer',    g:'GRP-CONSUMO',  pri:60, p:'(?s).*aspire.*'},
  {n:'Nitro',          m:'Acer',    g:'GRP-GAMER',    pri:60, p:'(?s).*(nitro|predator).*'},
  // Apple, Samsung, Huawei, MSI
  {n:'MacBook Air',    m:'Apple',   g:'GRP-PREMIUM',  pri:60, p:'(?s).*mac\\s*book\\s*air.*'},
  {n:'MacBook Pro',    m:'Apple',   g:'GRP-PREMIUM',  pri:60, p:'(?s).*mac\\s*book\\s*pro.*'},
  {n:'Galaxy Book',    m:'Samsung', g:'GRP-CONSUMO',  pri:60, p:'(?s).*(galaxy\\s*book|samsung).*'},
  {n:'MateBook',       m:'Huawei',  g:'GRP-PREMIUM',  pri:60, p:'(?s).*(matebook|huawei).*'},
  {n:'MSI',            m:'MSI',     g:'GRP-GAMER',    pri:60, p:'(?s).*\\bmsi\\b.*'},
  // Marcas nacionales y genéricas
  {n:'Bangho',         m:'Bangho',  g:'GRP-NACIONAL', pri:60, p:'(?s).*bangh[oó].*'},
  {n:'Exo',            m:'Exo',     g:'GRP-NACIONAL', pri:60, p:'(?s).*\\bexo\\b.*'},
  {n:'Enova',          m:'Enova',   g:'GRP-NACIONAL', pri:60, p:'(?s).*enova.*'},
  {n:'CX',             m:'CX',      g:'GRP-NACIONAL', pri:60, p:'(?s).*\\bcx\\b.*'},
  {n:'Gadnic',         m:'Gadnic',  g:'GRP-NACIONAL', pri:60, p:'(?s).*gadnic.*'},
  {n:'Aiwa',           m:'Aiwa',    g:'GRP-NACIONAL', pri:60, p:'(?s).*aiwa.*'},
  {n:'Haier',          m:'Haier',   g:'GRP-NACIONAL', pri:60, p:'(?s).*haier.*'},
  {n:'HDC',            m:'HDC',     g:'GRP-NACIONAL', pri:60, p:'(?s).*\\bhdc\\b.*'},
  {n:'Philco',         m:'Philco',  g:'GRP-NACIONAL', pri:60, p:'(?s).*philco.*'},
  {n:'Hyundai',        m:'Hyundai', g:'GRP-NACIONAL', pri:60, p:'(?s).*hyundai.*'},
  {n:'Noblex',         m:'Noblex',  g:'GRP-NACIONAL', pri:60, p:'(?s).*noblex.*'},
  {n:'BGH / Positivo', m:'BGH',     g:'GRP-NACIONAL', pri:60, p:'(?s).*(positivo|\\bbgh\\b).*'},
  {n:'Juana Manso',    m:'Juana Manso', g:'GRP-NACIONAL', pri:60, p:'(?s).*juana\\s*manso.*'},
  {n:'Generica',       m:'Generica', g:'GRP-NACIONAL', pri:50, p:'(?s).*(compatible\\s*con|gen[eé]ric).*'},
  // Marcas conocidas con línea no registrada
  {n:'Lenovo (otras)', m:'Lenovo',  g:'GRP-CONSUMO',  pri:10, p:'(?s).*lenovo.*'},
  {n:'HP (otras)',     m:'HP',      g:'GRP-CONSUMO',  pri:10, p:'(?s).*\\bhp\\b.*'},
  {n:'Dell (otras)',   m:'Dell',    g:'GRP-CONSUMO',  pri:10, p:'(?s).*\\bdell\\b.*'},
  {n:'Asus (otras)',   m:'Asus',    g:'GRP-CONSUMO',  pri:10, p:'(?s).*\\basus\\b.*'},
  {n:'Acer (otras)',   m:'Acer',    g:'GRP-CONSUMO',  pri:10, p:'(?s).*\\bacer\\b.*'}
] AS x
MATCH (gl:GrupoLinea {id: x.g})
MERGE (l:Linea {nombre: x.n})
SET l.marca = x.m, l.prioridad = x.pri, l.patron = x.p,
    l.estado_validacion = 'Provisional', l.version = 'v1'
MERGE (l)-[:PERTENECE_A_GRUPO]->(gl);


// ---------------------------------------------------------------------
// 29. CAPACIDADES DE RAM
//   factor: precio relativo a la configuración de referencia (8 GB = 1,00).
//   Estimación del grupo; una capacidad que no esté acá da error.
// ---------------------------------------------------------------------
UNWIND [
  {gb:2, f:0.80}, {gb:4, f:0.90}, {gb:6, f:0.93}, {gb:8, f:1.00}, {gb:12, f:1.04},
  {gb:16, f:1.08}, {gb:20, f:1.10}, {gb:24, f:1.12}, {gb:32, f:1.15}, {gb:40, f:1.17}, {gb:64, f:1.20}
] AS r
MERGE (c:CapacidadRAM {gb: r.gb})
SET c.factor = r.f, c.estado_validacion = 'Provisional', c.version = 'v1',
    c.fuente = 'Estimación del grupo, noviembre de 2026';


// ---------------------------------------------------------------------
// 30. AVISOS DE MERCADO RELEVADOS (seed versionado en el repo)
//   Archivo: datos/relevamiento_mercado.csv (montado en /import de Neo4j).
//   Se borran y se recargan en cada ejecución para reflejar el CSV.
// ---------------------------------------------------------------------
MATCH (a:AvisoMercado) DETACH DELETE a;

LOAD CSV WITH HEADERS FROM 'file:///relevamiento_mercado.csv' AS f
CREATE (:AvisoMercado {
  id: trim(f.id), fuente: f.fuente, fecha: date(f.fecha), busqueda: f.busqueda,
  titulo: f.titulo, marca: f.marca,
  linea: CASE WHEN trim(coalesce(f.linea, '')) = '' THEN null ELSE f.linea END,
  procesador: f.procesador,
  ram_gb: toIntegerOrNull(f.ram_gb),
  disco_tipo: CASE WHEN trim(coalesce(f.disco_tipo, '')) = '' THEN null ELSE f.disco_tipo END,
  disco_gb: toIntegerOrNull(f.disco_gb),
  gpu: CASE WHEN trim(coalesce(f.gpu, '')) = '' THEN null ELSE f.gpu END,
  precio_ars: toInteger(trim(f.precio_ars))
});

MATCH (a:AvisoMercado)
MATCH (p:Procesador {nombre: a.procesador})
MERGE (a)-[:TIENE_PROCESADOR]->(p);

MATCH (a:AvisoMercado)
MATCH (l:Linea {nombre: coalesce(a.linea, a.marca + ' (otras)')})
MERGE (a)-[:DE_LINEA]->(l);

MATCH (a:AvisoMercado) WHERE a.ram_gb IS NOT NULL
MATCH (r:CapacidadRAM {gb: a.ram_gb})
MERGE (a)-[:TIENE_RAM]->(r);


// ---------------------------------------------------------------------
// 31. CRITERIOS NUEVOS (CE-29, CE-30) Y CALIBRACIÓN CON LOS AVISOS
// ---------------------------------------------------------------------
UNWIND [
  {id:'CE-29', modulo:'SM2', nombre:'min_muestras_mercado',  valor:3,  unidad:'avisos'},
  {id:'CE-30', modulo:'SM2', nombre:'descuento_negociacion', valor:10, unidad:'%'}
] AS c
MERGE (ce:CriterioExperto {nombre: c.nombre})
ON CREATE SET ce.id = c.id, ce.valor = c.valor, ce.unidad = c.unidad, ce.version = 'v1',
              ce.vigente_desde = date('2026-11-09'), ce.estado_validacion = 'Provisional',
              ce.fuente = 'PG3: valuación por componentes'
WITH ce, c
MATCH (sm:Submodulo {id: c.modulo})
MERGE (ce)-[:PERTENECE_A]->(sm);

// CE-29 v2: con 3 avisos una sola publicación cara movía la mediana (ej. Ryzen 5 5000 → $1.177.000);
// se exige un mínimo de 5 para que un procesador tenga valor de referencia.
MATCH (ce:CriterioExperto {nombre: 'min_muestras_mercado'})
WHERE ce.version = 'v1'
SET ce.valor_anterior = ce.valor, ce.valor = 5, ce.version = 'v2',
    ce.vigente_desde = date('2026-11-09'),
    ce.fuente = 'Ajuste del grupo tras probar avisos reales (provisional)';

// Criterios del catálogo v1 que dejan de usarse: quedan en el grafo para la trazabilidad
MATCH (ce:CriterioExperto)
WHERE ce.nombre IN ['deprec_anual_inicial', 'deprec_anual_posterior', 'anios_deprec_inicial',
                    'valor_residual_min', 'factor_riesgo_medio', 'factor_riesgo_alto', 'reval_ram']
SET ce.en_uso = false,
    ce.observacion = 'Reemplazado por la valuación por componentes (PG3, 9/11/2026): la depreciación y el '
                   + 'riesgo ya están reflejados en los precios de mercado de cada generación, y la RAM en CapacidadRAM.';

// 31.a Mediana bruta de precio por procesador (sin normalizar)
MATCH (p:Procesador)
SET p.n_muestras = 0, p.mediana_bruta_ars = null, p.valor_ref_ars = null;

MATCH (ce:CriterioExperto {nombre:'min_muestras_mercado'})
MATCH (p:Procesador)<-[:TIENE_PROCESADOR]-(a:AvisoMercado)
WITH ce, p, percentileCont(a.precio_ars, 0.5) AS med, count(a) AS n
SET p.n_muestras = n, p.mediana_bruta_ars = CASE WHEN n >= ce.valor THEN med END;

// 31.b Factor de precio de cada línea y de cada grupo:
//      mediana de (precio del aviso / (mediana del procesador × factor de RAM))
MATCH (l:Linea) SET l.n_muestras = 0, l.factor_calibrado = null;

MATCH (l:Linea)<-[:DE_LINEA]-(a:AvisoMercado)-[:TIENE_PROCESADOR]->(p:Procesador)
WHERE p.mediana_bruta_ars IS NOT NULL
OPTIONAL MATCH (a)-[:TIENE_RAM]->(r:CapacidadRAM)
WITH l, percentileCont(a.precio_ars / (p.mediana_bruta_ars * coalesce(r.factor, 1.0)), 0.5) AS f, count(a) AS n
SET l.n_muestras = n, l.factor_calibrado = f;

MATCH (g:GrupoLinea)<-[:PERTENECE_A_GRUPO]-(:Linea)<-[:DE_LINEA]-(a:AvisoMercado)-[:TIENE_PROCESADOR]->(p:Procesador)
WHERE p.mediana_bruta_ars IS NOT NULL
OPTIONAL MATCH (a)-[:TIENE_RAM]->(r:CapacidadRAM)
WITH g, percentileCont(a.precio_ars / (p.mediana_bruta_ars * coalesce(r.factor, 1.0)), 0.5) AS f, count(a) AS n
SET g.n_muestras = n, g.factor_calibrado = f;

// Factor efectivo: el de la línea si tiene muestras suficientes; si no, el de su grupo
MATCH (ce:CriterioExperto {nombre:'min_muestras_mercado'})
MATCH (l:Linea)-[:PERTENECE_A_GRUPO]->(g:GrupoLinea)
SET l.factor_precio = round(CASE WHEN l.n_muestras >= ce.valor THEN l.factor_calibrado ELSE g.factor_calibrado END, 3),
    l.origen_factor = CASE WHEN l.n_muestras >= ce.valor
                           THEN 'Línea (' + toString(l.n_muestras) + ' avisos)'
                           ELSE 'Grupo ' + g.nombre + ' (la línea tiene ' + toString(l.n_muestras) + ' avisos)' END;

// 31.c Valor de referencia del procesador: equivalente a 8 GB y a una línea de factor 1,00
MATCH (ce:CriterioExperto {nombre:'min_muestras_mercado'})
MATCH (p:Procesador)<-[:TIENE_PROCESADOR]-(a:AvisoMercado)-[:DE_LINEA]->(l:Linea)
OPTIONAL MATCH (a)-[:TIENE_RAM]->(r:CapacidadRAM)
WITH ce, p, percentileCont(a.precio_ars / (l.factor_precio * coalesce(r.factor, 1.0)), 0.5) AS v, count(a) AS n
SET p.valor_ref_ars = CASE WHEN n >= ce.valor THEN toInteger(round(v / 1000.0)) * 1000 END,
    p.fuente_valor = 'Mediana de ' + toString(n) + ' avisos de Mercado Libre (9/11/2026), normalizada por línea y RAM';
