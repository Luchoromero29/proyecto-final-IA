// =====================================================================
// EvalTIC — Grupo 20 (5K09) — Actividad PG2, Unidad 1
// Script 2 de 2: CONSULTAS SOBRE LA BASE DE CONOCIMIENTO
//
// Requiere haber ejecutado antes Grupo_20_PG2_U1_carga.cypher.
// Todas las consultas son de lectura. Conviene ejecutarlas de a una para
// sacar la captura de cada resultado (tabla o grafo).
//
//   0. Esquema del grafo (para la captura de la sección c)
//   A. Las tres consultas de inferencia exigidas (sección d)
//        A1. Inferencia crisp
//        A2. Fuzzificación
//        A3. Inferencia cruzada entre submódulos
//   B. Consultas del punto 5 de la consigna
//   C. Casos de prueba: esperado vs. obtenido
//   D. Preparación para la integración con el LLM (sección e)
// =====================================================================


// =====================================================================
// 0. ESQUEMA DEL GRAFO
// =====================================================================
CALL db.schema.visualization();

// Conteo de nodos por etiqueta (documentación del esquema)
MATCH (n)
UNWIND labels(n) AS etiqueta
RETURN etiqueta, count(*) AS nodos
ORDER BY nodos DESC;

// Conocimiento difuso cargado: variables, conjuntos y parámetros
MATCH (sm:Submodulo)<-[:PERTENECE_A]-(v:VariableDifusa)-[:TIENE_CONJUNTO]->(cj:ConjuntoDifuso)
RETURN sm.id AS submodulo, v.nombre AS variable, v.rol AS rol,
       CASE WHEN v.min IS NULL THEN 'crisp' ELSE '[' + toString(v.min) + ', ' + toString(v.max) + '] ' + v.unidad END AS universo,
       collect(cj.etiqueta + CASE cj.tipo WHEN 'crisp' THEN ' (crisp)'
                             ELSE ' (c=' + toString(cj.c) + ', σ=' + toString(cj.sigma) + ')' END) AS conjuntos
ORDER BY submodulo, variable;


// =====================================================================
// A1. INFERENCIA CRISP
// ¿Qué publicaciones descarta o deja en espera el sistema por reglas
// determinísticas, qué regla lo decidió y en qué evidencia se apoyó?
// (incluye R3.8, que es crisp pero consume riesgo y demanda difusos de SM2)
// =====================================================================
MATCH (op:Operacion)-[:EVALUA]->(e:Equipo)
OPTIONAL MATCH (e)-[:RECIBE_DECISION]->(dec:Decision)-[:APLICA_REGLA]->(rd:Regla)
OPTIONAL MATCH (op)-[:APLICA_REGLA]->(rp:Regla)
WITH op, e, dec, coalesce(rd, rp) AS regla
WHERE regla IS NOT NULL AND regla.id IN ['R3.1', 'R3.1b', 'R3.2', 'R3.3', 'R3.3b', 'R3.7', 'R3.8']
OPTIONAL MATCH (dec)-[:SE_BASA_EN]->(evDec)
OPTIONAL MATCH (op)-[:SE_BASA_EN]->(evOp)
WITH op, e, dec, regla, collect(DISTINCT coalesce(evDec, evOp)) AS evidencias
RETURN e.marca + ' ' + e.modelo        AS equipo,
       regla.id                        AS regla,
       regla.texto                     AS condicion,
       coalesce(dec.tipo, op.estado)   AS conclusion,
       coalesce(dec.motivo, op.dato_solicitado) AS motivo,
       [x IN evidencias | labels(x)[0] + ' ' + x.id +
          CASE WHEN x.nivel IS NOT NULL THEN ' = ' + x.nivel ELSE '' END +
          CASE WHEN x.resultado IS NOT NULL THEN ' = ' + x.resultado ELSE '' END] AS evidencia
ORDER BY equipo;

// A1 (versión gráfica): recorrido del descarte del Inspiron (SM1 → SM3)
MATCH p = (:Publicacion)-[:OFRECE]->(:Equipo {id:'NB-103'})-[:PRESENTA]->(:FallaCatastrofica)
          -[:DETERMINA]->(dt:DictamenTecnico)<-[:SE_BASA_EN]-(dec:Decision)-[:APLICA_REGLA]->(:Regla)
MATCH q = (dt)-[:INFERIDO_POR]->(:Regla)
RETURN p, q;


// =====================================================================
// A2. FUZZIFICACIÓN
// ¿Con qué grado pertenece cada dato del Acer Aspire 5 a cada etiqueta
// lingüística, en los tres submódulos?
// μ(x) = exp(−(x − c)² / (2·σ²)), con c y σ leídos del grafo.
// Los conjuntos crisp valen 1 si el dato coincide y 0 si no.
// =====================================================================
MATCH (op:Operacion)-[:EVALUA]->(e:Equipo {id:'NB-101'}),
      (op)-[:TIENE_EVALUACION]->(ev:Evaluacion)-[en:ENTRADA]->(var:VariableDifusa)-[:TIENE_CONJUNTO]->(cj:ConjuntoDifuso),
      (var)-[:PERTENECE_A]->(sm:Submodulo)
WITH sm, ev, var, en.valor AS x, cj,
     CASE cj.tipo
       WHEN 'crisp' THEN CASE WHEN en.valor = cj.valor THEN 1.0 ELSE 0.0 END
       ELSE exp(-1.0 * (en.valor - cj.c)^2 / (2.0 * cj.sigma^2))
     END AS mu
RETURN sm.id AS submodulo, ev.base AS base, var.nombre AS variable, x AS valor_observado,
       cj.etiqueta AS etiqueta, cj.c AS centro, cj.sigma AS sigma, round(mu, 2) AS pertenencia
ORDER BY submodulo, base, variable, pertenencia DESC;

// A2 (operadores difusos): fuerza de cada regla del Acer.
// O = máximo dentro de un grupo de antecedentes; Y = mínimo entre grupos.
MATCH (op:Operacion)-[:EVALUA]->(:Equipo {id:'NB-101'}),
      (op)-[:TIENE_EVALUACION]->(ev:Evaluacion)
MATCH (r:ReglaDifusa {base: ev.base})-[a:ANTECEDENTE]->(cj:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(var:VariableDifusa)<-[en:ENTRADA]-(ev)
WITH ev, r, a.grupo AS grupo,
     collect(cj.etiqueta) AS etiquetas,
     max(CASE cj.tipo WHEN 'crisp' THEN CASE WHEN en.valor = cj.valor THEN 1.0 ELSE 0.0 END
                      ELSE exp(-0.5 * ((en.valor - cj.c) / cj.sigma)^2) END) AS mu_grupo
ORDER BY grupo
WITH ev, r, collect(reduce(s = '', x IN etiquetas | s + CASE WHEN s = '' THEN '' ELSE ' O ' END + x)
                    + '=' + toString(round(mu_grupo, 2))) AS grupos, min(mu_grupo) AS fuerza
WHERE fuerza >= 0.01
MATCH (r)-[:CONSECUENTE]->(sal:ConjuntoDifuso)
RETURN ev.base AS base, r.id AS regla, grupos AS antecedentes_Y, round(fuerza, 2) AS fuerza, sal.etiqueta AS conclusion
ORDER BY base, fuerza DESC;


// =====================================================================
// A3. INFERENCIA CRUZADA ENTRE SUBMÓDULOS
// ¿Por qué el sistema recomienda negociar el Acer Aspire 5 y de qué
// submódulo sale cada dato que usó? (SM1 difuso → SM2 difuso → SM3)
// =====================================================================
MATCH (op:Operacion)-[:EVALUA]->(e:Equipo {id:'NB-101'})<-[:OFRECE]-(p:Publicacion),
      (e)-[:TIENE_PLAN]->(pl:PlanReacondicionamiento)-[:GENERA]->(c:CostoReacondicionamiento),
      (e)-[:TIENE_VALUACION]->(vma:ValorMercadoAjustado),
      (e)-[:TIENE_RIESGO]->(rie:RiesgoObsolescencia),
      (e)-[:TIENE_DEMANDA]->(dem:DemandaComercial),
      (op)-[:TIENE_INDICADORES]->(ind:IndicadoresEconomicos),
      (op)-[:TIENE_EVALUACION]->(evB:Evaluacion {base:'SM1-BAT'}),
      (op)-[:TIENE_EVALUACION]->(evT:Evaluacion {base:'SM1-TER'}),
      (op)-[:TIENE_EVALUACION]->(evR:Evaluacion {base:'SM2-RIE'}),
      (op)-[:TIENE_EVALUACION]->(evD:Evaluacion {base:'SM2-DEM'}),
      (op)-[:TIENE_EVALUACION]->(evC:Evaluacion {base:'SM3-CONV'}),
      (e)-[:RECIBE_DECISION]->(dec:Decision)
WITH e, p, pl, c, vma, rie, dem, ind, evB, evT, evR, evD, evC, dec,
     [(ind)-[:APLICA_REGLA]->(r:Regla) | r.id] AS ajustes,
     [(evC)-[a:ACTIVO]->(rd:ReglaDifusa) | rd.id + '=' + toString(a.fuerza)] AS activadas
UNWIND [
  {o:1,  sm:'SM1', dato:'Batería (salud / ciclos) → necesidad de reemplazo', valor: evB.categoria + ' (' + toString(evB.centroide) + ')'},
  {o:2,  sm:'SM1', dato:'Prueba de estrés (temperatura / throttling) → service', valor: evT.categoria + ' (' + toString(evT.centroide) + ')'},
  {o:3,  sm:'SM1', dato:'Plan de reacondicionamiento', valor: toString(pl.cantidad_intervenciones) + ' intervenciones, costo $' + toString(c.monto_total)},
  {o:4,  sm:'SM2', dato:'Antigüedad, repuestos, Windows 11 → riesgo', valor: rie.nivel + ' (' + toString(rie.indice) + ')'},
  {o:5,  sm:'SM2', dato:'Rotación y riesgo → demanda', valor: dem.nivel + ' (' + toString(dem.indice) + ')'},
  {o:6,  sm:'SM2', dato:'Valor de mercado ajustado', valor: '$' + toString(vma.monto_tasado_ars)},
  {o:7,  sm:'SM3', dato:'Precio publicado', valor: '$' + toString(p.precio)},
  {o:8,  sm:'SM3', dato:'Margen neto', valor: toString(ind.margen_neto) + ' %'},
  {o:9,  sm:'SM3', dato:'Margen requerido (reglas aplicadas)', valor: toString(ind.margen_requerido) + ' % (base 20 %' + reduce(s = '', x IN ajustes | s + ', ' + x) + ')'},
  {o:10, sm:'SM3', dato:'Entradas difusas: brecha / descuento', valor: reduce(s = '', x IN [(evC)-[en:ENTRADA]->(v) | v.nombre + ' = ' + toString(en.valor)] | s + x + '  ')},
  {o:11, sm:'SM3', dato:'Reglas difusas activadas', valor: reduce(s = '', x IN activadas | s + x + ' ')},
  {o:12, sm:'SM3', dato:'Conveniencia (centroide → categoría)', valor: toString(evC.centroide) + ' → ' + evC.categoria},
  {o:13, sm:'SM3', dato:'Decisión', valor: dec.tipo + coalesce(' — contraoferta $' + toString(dec.contraoferta), '')}
] AS t
RETURN t.sm AS submodulo, t.dato AS dato, t.valor AS valor
ORDER BY t.o;

// A3 (versión gráfica, para la captura del recorrido)
MATCH (op:Operacion)-[:EVALUA]->(e:Equipo {id:'NB-101'})
MATCH p1 = (op)-[:TIENE_EVALUACION]->(ev:Evaluacion)-[:JUSTIFICA|DETERMINA]->()
MATCH p2 = (e)-[:TIENE_PLAN]->()-[:GENERA]->()
MATCH p3 = (e)-[:RECIBE_DECISION]->()-[:SE_JUSTIFICA_EN]->()-[:CONCLUYE]->()
MATCH p4 = (op)-[:TIENE_INDICADORES]->()-[:APLICA_REGLA]->()
RETURN p1, p2, p3, p4;


// =====================================================================
// B. CONSULTAS DEL PUNTO 5 DE LA CONSIGNA
// =====================================================================

// B1. Recuperar conceptos relacionados
// ¿Con qué conceptos se relaciona el riesgo de obsolescencia y de qué
// submódulo es cada uno?
MATCH (f:Frame {nombre:'RiesgoObsolescencia'})-[r]-(otro:Frame)
OPTIONAL MATCH (otro)-[:PERTENECE_A]->(sm:Submodulo)
RETURN type(r) AS relacion,
       CASE WHEN startNode(r) = f THEN 'RiesgoObsolescencia → ' + otro.nombre
            ELSE otro.nombre + ' → RiesgoObsolescencia' END AS sentido,
       coalesce(sm.id, 'Común') AS submodulo;

// B2. Recorrer relaciones entre entidades
// ¿Qué cadena de conceptos conecta una medición del taller con la decisión?
MATCH p = shortestPath((:Frame {nombre:'Medicion'})-[*..8]-(:Frame {nombre:'Decision'}))
RETURN [n IN nodes(p) | n.nombre] AS conceptos,
       [r IN relationships(p) | type(r)] AS relaciones;

// B2 (instancias): cascada SM2 del T440p hasta el descarte
MATCH p = (:Equipo {id:'NB-104'})<-[:SOBRE]-(:Evaluacion {base:'SM2-RIE'})-[:ALIMENTA]->(:Evaluacion {base:'SM2-DEM'})
          -[:DETERMINA]->(:DemandaComercial)<-[:SE_BASA_EN]-(:Decision)-[:APLICA_REGLA]->(:Regla)
RETURN p;

// B3. Identificar evidencias asociadas a una conclusión
// ¿Qué reglas (crisp y difusas) y qué evidencias sostienen cada decisión?
MATCH (e:Equipo)-[:RECIBE_DECISION]->(dec:Decision)
OPTIONAL MATCH (dec)-[:APLICA_REGLA]->(r:Regla)
OPTIONAL MATCH (dec)-[:SE_BASA_EN]->(evid)
OPTIONAL MATCH (dec)-[:SE_JUSTIFICA_EN]->(ev:Evaluacion)-[a:ACTIVO]->(rd:ReglaDifusa)
RETURN e.marca + ' ' + e.modelo AS equipo,
       dec.tipo AS decision,
       collect(DISTINCT r.id) AS reglas_crisp,
       collect(DISTINCT rd.id + '=' + toString(a.fuerza)) AS reglas_difusas,
       collect(DISTINCT labels(evid)[0] + ' ' + evid.id) AS evidencias,
       dec.motivo AS motivo
ORDER BY equipo;

// B4. Obtener información proveniente de distintos submódulos
// ¿Qué parámetros de cada submódulo están todavía sin validar con el experto?
MATCH (sm:Submodulo)<-[:PERTENECE_A]-(ce:CriterioExperto {estado_validacion:'Provisional'})
WITH sm, collect(ce.nombre + ' = ' + toString(ce.valor) + ' ' + ce.unidad) AS criterios
OPTIONAL MATCH (sm)<-[:PERTENECE_A]-(:VariableDifusa)-[:TIENE_CONJUNTO]->(cj:ConjuntoDifuso {estado_validacion:'Provisional'})
RETURN sm.id AS submodulo, sm.responsable AS responsable,
       size(criterios) AS criterios_provisionales, criterios,
       count(cj) AS conjuntos_difusos_provisionales
ORDER BY submodulo;


// =====================================================================
// C. CASOS DE PRUEBA: RESULTADO ESPERADO vs. OBTENIDO
// =====================================================================
MATCH (op:Operacion)-[:EVALUA]->(e:Equipo)
OPTIONAL MATCH (e)-[:RECIBE_DECISION]->(dec:Decision)
OPTIONAL MATCH (op)-[:TIENE_EVALUACION]->(ev:Evaluacion {base:'SM3-CONV'})
WITH op, e, dec, ev, coalesce(dec.tipo, op.estado) AS obtenido
RETURN op.tipo_caso              AS caso,
       e.marca + ' ' + e.modelo  AS equipo,
       op.resultado_esperado     AS esperado,
       obtenido,
       CASE WHEN obtenido = op.resultado_esperado THEN 'OK' ELSE 'DIFIERE' END AS verificacion,
       ev.centroide              AS conveniencia,
       coalesce('Contraoferta $' + toString(dec.contraoferta), dec.observacion,
                dec.motivo, op.dato_solicitado) AS detalle
ORDER BY op.id;

// C (detalle): resultado de cada base difusa por caso
MATCH (op:Operacion)-[:EVALUA]->(e:Equipo), (op)-[:TIENE_EVALUACION]->(ev:Evaluacion)
RETURN e.marca + ' ' + e.modelo AS equipo, ev.base AS base,
       [(ev)-[en:ENTRADA]->(v) | v.nombre + '=' + toString(en.valor)] AS entradas,
       [(ev)-[a:ACTIVO]->(r) | r.id + '=' + toString(a.fuerza)] AS reglas_activadas,
       ev.centroide AS centroide, ev.categoria AS categoria
ORDER BY op.id, base;


// =====================================================================
// D. PREPARACIÓN PARA LA INTEGRACIÓN CON EL LLM (PI4)
// =====================================================================

// D1. Contexto completo de una operación para que el LLM redacte la
//     justificación. Parámetro de entrada: id del equipo.
//     En la integración real, 'NB-101' se reemplaza por $equipoId.
WITH 'NB-101' AS equipoId
MATCH (op:Operacion)-[:EVALUA]->(e:Equipo {id: equipoId})<-[:OFRECE]-(p:Publicacion)
OPTIONAL MATCH (e)-[:RECIBE_DECISION]->(dec:Decision)
OPTIONAL MATCH (op)-[:TIENE_INDICADORES]->(ind:IndicadoresEconomicos)
RETURN {
  equipo:           e.marca + ' ' + e.modelo,
  precio_publicado: p.precio,
  estado_operacion: op.estado,
  sm1: {
    dictamen:       head([(e)-[:TIENE_DICTAMEN]->(d) | d.resultado]),
    causa:          head([(e)-[:TIENE_DICTAMEN]->(d) | d.causa_inviabilidad]),
    intervenciones: [(e)-[:TIENE_PLAN]->()<-[:FORMA_PARTE_DE]-(i) | {tarea: i.tipo_tarea, costo: i.costo_ars, mandatoria: i.es_mandatoria, origen: i.origen}],
    costo_total:    head([(e)-[:TIENE_PLAN]->()-[:GENERA]->(x) | x.monto_total])
  },
  sm2: {
    vma:      head([(e)-[:TIENE_VALUACION]->(x) | x.monto_tasado_ars]),
    riesgo:   head([(e)-[:TIENE_RIESGO]->(x) | {nivel: x.nivel, indice: x.indice}]),
    demanda:  head([(e)-[:TIENE_DEMANDA]->(x) | {nivel: x.nivel, indice: x.indice}]),
    dictamen: head([(e)-[:TIENE_DICTAMEN_COMERCIAL]->(x) | x.veredicto])
  },
  indicadores: ind {.margen_neto, .margen_requerido, .ratio_reparacion, .contraoferta},
  reglas_crisp: CASE WHEN dec IS NULL THEN [] ELSE [(dec)-[:APLICA_REGLA]->(r) | r.id + ': ' + r.texto] END
              + CASE WHEN ind IS NULL THEN [] ELSE [(ind)-[:APLICA_REGLA]->(r) | r.id + ': ' + r.texto] END,
  criterios: CASE WHEN ind IS NULL THEN [] ELSE
             [(ind)-[:USA_CRITERIO]->(ce) | {nombre: ce.nombre, valor: ce.valor, unidad: ce.unidad,
                                             version: ce.version, estado: ce.estado_validacion}] END,
  evaluaciones_difusas: [(op)-[:TIENE_EVALUACION]->(ev) | {
            base:             ev.base,
            entradas:         [(ev)-[en:ENTRADA]->(v) | {variable: v.nombre, valor: en.valor}],
            grados:           [(ev)-[g:TIENE_GRADO]->(cj) | {conjunto: cj.id, mu: g.mu}],
            reglas_activadas: [(ev)-[a:ACTIVO]->(rd) | {regla: rd.id, fuerza: a.fuerza, texto: rd.texto}],
            centroide:        ev.centroide,
            categoria:        ev.categoria,
            version:          head([(ev)-[:USA_VERSION]->(vp) | vp.id])
          }],
  decision:  dec {.tipo, .motivo, .contraoferta, .observacion},
  pendiente: CASE WHEN op.estado = 'Verificacion_pendiente'
                  THEN {accion: op.accion_pendiente, dato: op.dato_solicitado} END
} AS contexto_llm;

// D2. Simulación «¿qué pasaría si…?» de SM3, sin escribir en la base.
//     Parámetros: brecha (pp) y descuento (%). En la integración real
//     serían $brecha y $descuento (por ejemplo: «¿y si me lo deja a $90.000?»).
WITH -18.2 AS brecha, 34.8 AS descuento
MATCH (r:ReglaDifusa {base:'SM3-CONV'})-[a:ANTECEDENTE]->(cj:ConjuntoDifuso)<-[:TIENE_CONJUNTO]-(var:VariableDifusa)
WITH brecha, descuento, r, a.grupo AS grupo,
     max(exp(-0.5 * (((CASE var.nombre WHEN 'Brecha_Margen' THEN brecha ELSE descuento END)
                      - cj.c) / cj.sigma)^2)) AS mu_grupo
WITH brecha, descuento, r, min(mu_grupo) AS fuerza
MATCH (r)-[:CONSECUENTE]->(sal:ConjuntoDifuso)
WITH brecha, descuento, collect({regla: r.id, fuerza: fuerza, c: sal.c, sigma: sal.sigma}) AS reglas
UNWIND range(0, 100) AS i
WITH brecha, descuento, reglas, i / 100.0 AS y
UNWIND reglas AS rg
WITH brecha, descuento, reglas, y, rg, exp(-0.5 * ((y - rg.c) / rg.sigma)^2) AS mu_sal
WITH brecha, descuento, reglas, y,
     max(CASE WHEN rg.fuerza < mu_sal THEN rg.fuerza ELSE mu_sal END) AS altura
WITH brecha, descuento, reglas, sum(y * altura) / sum(altura) AS centroide
MATCH (:VariableDifusa {nombre:'Conveniencia'})-[:TIENE_CONJUNTO]->(s:ConjuntoDifuso)
WITH brecha, descuento, reglas, centroide, s,
     exp(-0.5 * ((centroide - s.c) / s.sigma)^2) AS mu
ORDER BY mu DESC
WITH brecha, descuento, reglas, centroide, collect(s.etiqueta)[0] AS categoria
RETURN brecha, descuento,
       [x IN reglas WHERE x.fuerza >= 0.01 | x.regla + '=' + toString(round(x.fuerza, 2))] AS reglas_activadas,
       round(centroide, 2) AS conveniencia,
       categoria;

// D3. Explicación de un cambio de parámetros (trazabilidad pedida en la
//     devolución del PI3): qué versión de parámetros usó cada evaluación
//     y qué conjuntos de esa versión siguen sin validar.
MATCH (ev:Evaluacion)-[:USA_VERSION]->(vp:VersionParametros)
OPTIONAL MATCH (vp)-[:INCLUYE]->(:VariableDifusa)-[:TIENE_CONJUNTO]->(cj:ConjuntoDifuso {estado_validacion:'Provisional'})
RETURN vp.id AS version, vp.descripcion AS descripcion, vp.politica_categoria AS politica,
       count(DISTINCT ev) AS evaluaciones, count(DISTINCT cj) AS conjuntos_provisionales
ORDER BY version;
