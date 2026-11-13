// =============================================================================
// TB — BLOQUE DE POLÍTICAS: margen y cuantización financiera (SM3), valuación,
// R2.4 y clasificación del estado comercial (SM2) y Firme/Provisional (SM0).
//
// Artefacto ADITIVO e IDEMPOTENTE y separado de los seeds diagnóstico, mercado,
// P1, P2a, P2c, P3a y P3b. Una sola consulta: primero valida TODAS las
// precondiciones (objetos existentes, propiedades y relaciones declaradas
// ausentes o ya iguales, criterios de referencia presentes); sólo si no hay
// ningún conflicto escribe, y en ese caso escribe el bloque completo. Ante
// conflicto no escribe nada y la segunda aplicación devuelve actualizadas = 0.
//
// Qué agrega, y nada más (resumen en docs/ESTADO_CONSOLIDADO_MEJORAS.md;
// la declaración exacta se conserva en esta consulta):
//   - Cinco manifiestos técnicos VersionPoliticas (`SM3-margen`, `SM3-calculo`,
//     `SM2-valuacion`, `SM2-estado`, `SM0-clasificacion`) con INCLUYE a sus
//     reglas o pasos de cálculo.
//   - Propiedades de política en las Regla existentes R3.4, R3.5, R3.6 (etapa,
//     prioridad, destino y operación del efecto, exclusión y texto de traza) y
//     R2.4 (activación y familia).
//   - La Regla nueva SM3-MARGEN-BASE (paso 0 del margen) con su vínculo al CE
//     existente `margen_base`.
//   - Cuatro `Condicion` del margen (hechos riesgo/demanda/n_interv) con su
//     REQUIERE y el criterio `umbral_intervenciones` de R3.6.
//   - Cinco `PasoCalculo` con el destino y la precisión de cada cuantización, y
//     el límite no negativo de la contraoferta.
//   - La Regla nueva SM2-VALUACION (escala de redondeo del VMA y qué criterios
//     aplica) y ocho Regla + nueve Condicion del estado comercial.
//   - Dos Regla + cuatro Condicion de la clasificación Firme/Provisional.
//
// NO se modifican criterios, costos, catálogo de componentes, diagnósticos,
// patrones, conjuntos difusos, validaciones expertas, propiedades históricas ni
// reglas ajenas; ninguna propiedad o relación existente se reescribe con otro
// valor. `estado`, `estado_validacion` y `version` se conservan. Los valores son
// la política PROVISIONAL vigente del motor, no validación del experto.
// Pruebas: transacción explícita revertida. Activación: la integra el padre
// sobre el scratch marcado, con protección del grafo antes del commit.
// =============================================================================
WITH [
  // --- Reglas existentes: sólo propiedades nuevas de política -----------------
  {etiqueta:'Regla', id:'R3.4', existe:true, props:{
    etapa:'SM3-margen', prioridad_inferencia:20, efecto_destino:'margen_paso1',
    efecto_operacion:'asignar', grupo_exclusion:'SM3-MARGEN-PASO1',
    traza_texto:'R3.4: demanda Alta y riesgo Bajo → margen requerido = CE margen_alta_liquidez'}},
  {etiqueta:'Regla', id:'R3.5', existe:true, props:{
    etapa:'SM3-margen', prioridad_inferencia:30, efecto_destino:'margen_paso1',
    efecto_operacion:'maximo', grupo_exclusion:'SM3-MARGEN-PASO1',
    traza_texto:'R3.5: riesgo Alto → margen requerido = máx(margen, CE margen_riesgo_alto)'}},
  {etiqueta:'Regla', id:'R3.6', existe:true, props:{
    etapa:'SM3-margen', prioridad_inferencia:40, efecto_destino:'margen_req',
    efecto_operacion:'sumar',
    traza_texto:'R3.6: intervenciones ≥ CE umbral_intervenciones → + CE prima_fallas'}},
  {etiqueta:'Regla', id:'R2.4', existe:true, props:{
    rol:'r24', r24_activo:true, r24_misma_familia:true}},
  // --- Etapas (manifiestos técnicos de representación) ------------------------
  {etiqueta:'VersionPoliticas', id:'VP-SM3-MARGEN', existe:false, props:{
    version:'politicas-bloque-v1', representacion_version:'politicas-bloque-v1',
    etapa:'SM3-margen', activa:true,
    ids_requeridos:['SM3-MARGEN-BASE', 'R3.4', 'R3.5', 'R3.6']}},
  {etiqueta:'VersionPoliticas', id:'VP-SM3-CALCULO', existe:false, props:{
    version:'politicas-bloque-v1', representacion_version:'politicas-bloque-v1',
    etapa:'SM3-calculo', activa:true,
    ids_requeridos:['PC-SM3-MARGEN-NETO', 'PC-SM3-RATIO', 'PC-SM3-CONTRATOFERTA',
                    'PC-SM3-DESCUENTO', 'PC-SM3-BRECHA']}},
  {etiqueta:'VersionPoliticas', id:'VP-SM2-VALUACION', existe:false, props:{
    version:'politicas-bloque-v1', representacion_version:'politicas-bloque-v1',
    etapa:'SM2-valuacion', activa:true, ids_requeridos:['SM2-VALUACION', 'R2.4']}},
  {etiqueta:'VersionPoliticas', id:'VP-SM2-ESTADO', existe:false, props:{
    version:'politicas-bloque-v1', representacion_version:'politicas-bloque-v1',
    etapa:'SM2-estado', activa:true,
    ids_requeridos:['SM2-EST-01', 'SM2-EST-02', 'SM2-EST-03', 'SM2-EST-04',
                    'SM2-EST-05', 'SM2-EST-06', 'SM2-EST-07', 'SM2-EST-08']}},
  {etiqueta:'VersionPoliticas', id:'VP-SM0-CLASIFICACION', existe:false, props:{
    version:'politicas-bloque-v1', representacion_version:'politicas-bloque-v1',
    etapa:'SM0-clasificacion', activa:true, ids_requeridos:['SM0-CLAS-01', 'SM0-CLAS-02']}},
  // --- Regla nueva: paso 0 del margen requerido ------------------------------
  {etiqueta:'Regla', id:'SM3-MARGEN-BASE', existe:false, props:{
    texto:'(Paso 0) margen requerido := CE margen_base', tipo:'Heurística',
    implementada:true, estado:'Provisional', etapa:'SM3-margen',
    prioridad_inferencia:10, efecto_destino:'margen_paso1', efecto_operacion:'asignar',
    rol:'base'}},
  // --- Regla nueva: fórmula de valuación y qué criterios aplica ---------------
  {etiqueta:'Regla', id:'SM2-VALUACION', existe:false, props:{
    texto:'VMA = valor del procesador × factor de línea × factor de RAM − descuento de '
        + 'negociación + revalorización por upgrade, redondeado a miles',
    tipo:'Determinística', implementada:true, estado:'Provisional', etapa:'SM2-valuacion',
    rol:'formula', escala_redondeo_ars:1000, aplica_descuento_negociacion:true,
    aplica_revalorizacion_upgrade:true}},
  // --- Reglas nuevas: clasificación del estado comercial ---------------------
  {etiqueta:'Regla', id:'SM2-EST-01', existe:false, props:{
    texto:'SI el procesador no figura en el aviso y se tomó del modelo ENTONCES valuación pendiente',
    tipo:'Determinística', implementada:true, estado:'Provisional', etapa:'SM2-estado',
    prioridad_inferencia:10, estado_resultante:'Verificacion_pendiente',
    motivo_resultante:'procesador_no_informado'}},
  {etiqueta:'Regla', id:'SM2-EST-02', existe:false, props:{
    texto:'SI el procesador no está en la base de conocimiento ENTONCES ConocimientoFaltante',
    tipo:'Determinística', implementada:true, estado:'Provisional', etapa:'SM2-estado',
    prioridad_inferencia:20, estado_resultante:'ConocimientoFaltante',
    motivo_resultante:'procesador_desconocido'}},
  {etiqueta:'Regla', id:'SM2-EST-03', existe:false, props:{
    texto:'SI la línea del equipo no está en la base de conocimiento ENTONCES ConocimientoFaltante',
    tipo:'Determinística', implementada:true, estado:'Provisional', etapa:'SM2-estado',
    prioridad_inferencia:30, estado_resultante:'ConocimientoFaltante',
    motivo_resultante:'linea_desconocida'}},
  {etiqueta:'Regla', id:'SM2-EST-04', existe:false, props:{
    texto:'SI el aviso informa una RAM que no está en la base de conocimiento ENTONCES ConocimientoFaltante',
    tipo:'Determinística', implementada:true, estado:'Provisional', etapa:'SM2-estado',
    prioridad_inferencia:40, estado_resultante:'ConocimientoFaltante',
    motivo_resultante:'ram_informada_desconocida'}},
  {etiqueta:'Regla', id:'SM2-EST-05', existe:false, props:{
    texto:'SI la RAM tasada no está en la base de conocimiento ENTONCES ConocimientoFaltante',
    tipo:'Determinística', implementada:true, estado:'Provisional', etapa:'SM2-estado',
    prioridad_inferencia:50, estado_resultante:'ConocimientoFaltante',
    motivo_resultante:'ram_tasada_desconocida'}},
  {etiqueta:'Regla', id:'SM2-EST-06', existe:false, props:{
    texto:'SI el procesador no tiene valor de referencia ni generación anterior ENTONCES valuación pendiente',
    tipo:'Determinística', implementada:true, estado:'Provisional', etapa:'SM2-estado',
    prioridad_inferencia:60, estado_resultante:'Verificacion_pendiente',
    motivo_resultante:'procesador_sin_muestras'}},
  {etiqueta:'Regla', id:'SM2-EST-07', existe:false, props:{
    texto:'SI el año de fabricación no se puede determinar ENTONCES valuación pendiente',
    tipo:'Determinística', implementada:true, estado:'Provisional', etapa:'SM2-estado',
    prioridad_inferencia:70, estado_resultante:'Verificacion_pendiente',
    motivo_resultante:'anio_desconocido'}},
  {etiqueta:'Regla', id:'SM2-EST-08', existe:false, props:{
    texto:'Si no se cumple ninguna condición anterior ENTONCES la valuación queda tasada',
    tipo:'Determinística', implementada:true, estado:'Provisional', etapa:'SM2-estado',
    prioridad_inferencia:80, estado_resultante:'Tasado'}},
  // --- Reglas nuevas: clasificación Firme/Provisional ------------------------
  {etiqueta:'Regla', id:'SM0-CLAS-01', existe:false, props:{
    texto:'SI no hay criterios ni costos sin validar, ni datos inferidos ni datos pendientes '
        + 'ENTONCES la decisión es Firme',
    tipo:'Determinística', implementada:true, estado:'Provisional',
    etapa:'SM0-clasificacion', prioridad_inferencia:10, estado_resultante:'Firme'}},
  {etiqueta:'Regla', id:'SM0-CLAS-02', existe:false, props:{
    texto:'En cualquier otro caso la decisión es Provisional',
    tipo:'Determinística', implementada:true, estado:'Provisional',
    etapa:'SM0-clasificacion', prioridad_inferencia:20, estado_resultante:'Provisional'}},
  // --- Pasos de cálculo y cuantización de SM3 -------------------------------
  {etiqueta:'PasoCalculo', id:'PC-SM3-MARGEN-NETO', existe:false, props:{
    destino:'margen_neto', decimales:1}},
  {etiqueta:'PasoCalculo', id:'PC-SM3-RATIO', existe:false, props:{
    destino:'ratio_reparacion', decimales:2}},
  {etiqueta:'PasoCalculo', id:'PC-SM3-CONTRATOFERTA', existe:false, props:{
    destino:'contraoferta', decimales:-3, limite_inferior_ars:0.0}},
  {etiqueta:'PasoCalculo', id:'PC-SM3-DESCUENTO', existe:false, props:{
    destino:'descuento', decimales:1}},
  {etiqueta:'PasoCalculo', id:'PC-SM3-BRECHA', existe:false, props:{
    destino:'brecha', decimales:1}},
  // --- Condiciones del margen requerido (SM3) -------------------------------
  {etiqueta:'Condicion', id:'CND-SM3-R34-RIESGO', existe:false, props:{
    campo:'riesgo', operador:'=', valor:'Bajo',
    representacion_version:'politicas-bloque-v1'}},
  {etiqueta:'Condicion', id:'CND-SM3-R34-DEMANDA', existe:false, props:{
    campo:'demanda', operador:'=', valor:'Alta',
    representacion_version:'politicas-bloque-v1'}},
  {etiqueta:'Condicion', id:'CND-SM3-R35-RIESGO', existe:false, props:{
    campo:'riesgo', operador:'=', valor:'Alto',
    representacion_version:'politicas-bloque-v1'}},
  {etiqueta:'Condicion', id:'CND-SM3-R36-INTERV', existe:false, props:{
    campo:'n_interv', operador:'>=', representacion_version:'politicas-bloque-v1'}},
  // --- Condiciones del estado comercial (SM2) -------------------------------
  {etiqueta:'Condicion', id:'CND-SM2-EST-01-PROCESADOR', existe:false, props:{
    campo:'procesador', operador:'ausente', representacion_version:'politicas-bloque-v1'}},
  {etiqueta:'Condicion', id:'CND-SM2-EST-01-ORIGEN', existe:false, props:{
    campo:'procesador_origen', operador:'=', valor:'modelo',
    representacion_version:'politicas-bloque-v1'}},
  {etiqueta:'Condicion', id:'CND-SM2-EST-02-PROCESADOR', existe:false, props:{
    campo:'procesador', operador:'ausente', representacion_version:'politicas-bloque-v1'}},
  {etiqueta:'Condicion', id:'CND-SM2-EST-03-LINEA', existe:false, props:{
    campo:'linea', operador:'ausente', representacion_version:'politicas-bloque-v1'}},
  {etiqueta:'Condicion', id:'CND-SM2-EST-04-DECLARADA', existe:false, props:{
    campo:'ram_declarada', operador:'presente', representacion_version:'politicas-bloque-v1'}},
  {etiqueta:'Condicion', id:'CND-SM2-EST-04-INFORMADA', existe:false, props:{
    campo:'ram_informada', operador:'ausente', representacion_version:'politicas-bloque-v1'}},
  {etiqueta:'Condicion', id:'CND-SM2-EST-05-TASADA', existe:false, props:{
    campo:'ram_tasada', operador:'ausente', representacion_version:'politicas-bloque-v1'}},
  {etiqueta:'Condicion', id:'CND-SM2-EST-06-VALOR', existe:false, props:{
    campo:'valor_proc', operador:'ausente', representacion_version:'politicas-bloque-v1'}},
  {etiqueta:'Condicion', id:'CND-SM2-EST-07-ANIO', existe:false, props:{
    campo:'anio', operador:'ausente', representacion_version:'politicas-bloque-v1'}},
  // --- Condiciones de la clasificación Firme/Provisional (SM0) --------------
  {etiqueta:'Condicion', id:'CND-SM0-CRITERIOS', existe:false, props:{
    campo:'criterios_sin_validar', operador:'=', valor:0,
    representacion_version:'politicas-bloque-v1'}},
  {etiqueta:'Condicion', id:'CND-SM0-COSTOS', existe:false, props:{
    campo:'costos_sin_validar', operador:'=', valor:0,
    representacion_version:'politicas-bloque-v1'}},
  {etiqueta:'Condicion', id:'CND-SM0-INFERIDOS', existe:false, props:{
    campo:'datos_inferidos', operador:'=', valor:0,
    representacion_version:'politicas-bloque-v1'}},
  {etiqueta:'Condicion', id:'CND-SM0-PENDIENTES', existe:false, props:{
    campo:'datos_pendientes', operador:'=', valor:0,
    representacion_version:'politicas-bloque-v1'}}
] AS declarados
// Precondición por objeto: el existente está una sola vez; el nuevo no está
// duplicado. Toda propiedad declarada está ausente o ya tiene el mismo valor.
UNWIND declarados AS declarado
OPTIONAL MATCH (n) WHERE n.id = declarado.id
                      AND any(l IN labels(n) WHERE l = declarado.etiqueta)
WITH declarado, collect(DISTINCT n) AS hallados
WITH declarado, size(hallados) AS cantidad,
     CASE WHEN size(hallados) = 1 THEN hallados[0] END AS n
WITH declarado, n,
     CASE WHEN declarado.existe THEN cantidad = 1 ELSE cantidad <= 1 END AS presencia,
     (n IS NULL OR none(k IN keys(declarado.props)
                        WHERE n[k] IS NOT NULL AND n[k] <> declarado.props[k])) AS sin_choque,
     CASE WHEN n IS NULL THEN true
          ELSE any(k IN keys(declarado.props) WHERE n[k] IS NULL) END AS pendiente
WITH collect({etiqueta: declarado.etiqueta, id: declarado.id, props: declarado.props,
              n: n, presencia: presencia, sin_choque: sin_choque,
              pendiente: pendiente}) AS filas_nodos
// Los extremos externos (criterios y submódulos) se validan aparte, más abajo.
WITH filas_nodos, all(f IN filas_nodos WHERE f.presencia AND f.sin_choque) AS nodos_ok,
     [n IN filas_nodos | n.etiqueta + '|' + n.id]
     + ['CriterioExperto|margen_base', 'CriterioExperto|umbral_intervenciones',
        'Submodulo|SM2', 'Submodulo|SM3'] AS declarados_ids
// Precondición por relación: existe una sola vez con las mismas propiedades, o
// no existe; ambos extremos están declarados arriba.
WITH filas_nodos, nodos_ok, declarados_ids,
     {relaciones: [
  {desde:['VersionPoliticas', 'VP-SM3-MARGEN'], tipo:'INCLUYE', hacia:['Regla', 'SM3-MARGEN-BASE'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM3-MARGEN'], tipo:'INCLUYE', hacia:['Regla', 'R3.4'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM3-MARGEN'], tipo:'INCLUYE', hacia:['Regla', 'R3.5'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM3-MARGEN'], tipo:'INCLUYE', hacia:['Regla', 'R3.6'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM3-CALCULO'], tipo:'INCLUYE', hacia:['PasoCalculo', 'PC-SM3-MARGEN-NETO'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM3-CALCULO'], tipo:'INCLUYE', hacia:['PasoCalculo', 'PC-SM3-RATIO'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM3-CALCULO'], tipo:'INCLUYE', hacia:['PasoCalculo', 'PC-SM3-CONTRATOFERTA'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM3-CALCULO'], tipo:'INCLUYE', hacia:['PasoCalculo', 'PC-SM3-DESCUENTO'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM3-CALCULO'], tipo:'INCLUYE', hacia:['PasoCalculo', 'PC-SM3-BRECHA'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM2-VALUACION'], tipo:'INCLUYE', hacia:['Regla', 'SM2-VALUACION'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM2-VALUACION'], tipo:'INCLUYE', hacia:['Regla', 'R2.4'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM2-ESTADO'], tipo:'INCLUYE', hacia:['Regla', 'SM2-EST-01'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM2-ESTADO'], tipo:'INCLUYE', hacia:['Regla', 'SM2-EST-02'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM2-ESTADO'], tipo:'INCLUYE', hacia:['Regla', 'SM2-EST-03'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM2-ESTADO'], tipo:'INCLUYE', hacia:['Regla', 'SM2-EST-04'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM2-ESTADO'], tipo:'INCLUYE', hacia:['Regla', 'SM2-EST-05'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM2-ESTADO'], tipo:'INCLUYE', hacia:['Regla', 'SM2-EST-06'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM2-ESTADO'], tipo:'INCLUYE', hacia:['Regla', 'SM2-EST-07'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM2-ESTADO'], tipo:'INCLUYE', hacia:['Regla', 'SM2-EST-08'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM0-CLASIFICACION'], tipo:'INCLUYE', hacia:['Regla', 'SM0-CLAS-01'], props:{}},
  {desde:['VersionPoliticas', 'VP-SM0-CLASIFICACION'], tipo:'INCLUYE', hacia:['Regla', 'SM0-CLAS-02'], props:{}},
  {desde:['Regla', 'R3.4'], tipo:'REQUIERE', hacia:['Condicion', 'CND-SM3-R34-RIESGO'], props:{grupo:1}},
  {desde:['Regla', 'R3.4'], tipo:'REQUIERE', hacia:['Condicion', 'CND-SM3-R34-DEMANDA'], props:{grupo:2}},
  {desde:['Regla', 'R3.5'], tipo:'REQUIERE', hacia:['Condicion', 'CND-SM3-R35-RIESGO'], props:{grupo:1}},
  {desde:['Regla', 'R3.6'], tipo:'REQUIERE', hacia:['Condicion', 'CND-SM3-R36-INTERV'], props:{grupo:1}},
  {desde:['Condicion', 'CND-SM3-R36-INTERV'], tipo:'USA_CRITERIO', hacia:['CriterioExperto', 'umbral_intervenciones'], props:{}},
  {desde:['Regla', 'SM3-MARGEN-BASE'], tipo:'USA_CRITERIO', hacia:['CriterioExperto', 'margen_base'], props:{}},
  {desde:['Regla', 'SM2-EST-01'], tipo:'REQUIERE', hacia:['Condicion', 'CND-SM2-EST-01-PROCESADOR'], props:{grupo:1}},
  {desde:['Regla', 'SM2-EST-01'], tipo:'REQUIERE', hacia:['Condicion', 'CND-SM2-EST-01-ORIGEN'], props:{grupo:2}},
  {desde:['Regla', 'SM2-EST-02'], tipo:'REQUIERE', hacia:['Condicion', 'CND-SM2-EST-02-PROCESADOR'], props:{grupo:1}},
  {desde:['Regla', 'SM2-EST-03'], tipo:'REQUIERE', hacia:['Condicion', 'CND-SM2-EST-03-LINEA'], props:{grupo:1}},
  {desde:['Regla', 'SM2-EST-04'], tipo:'REQUIERE', hacia:['Condicion', 'CND-SM2-EST-04-DECLARADA'], props:{grupo:1}},
  {desde:['Regla', 'SM2-EST-04'], tipo:'REQUIERE', hacia:['Condicion', 'CND-SM2-EST-04-INFORMADA'], props:{grupo:2}},
  {desde:['Regla', 'SM2-EST-05'], tipo:'REQUIERE', hacia:['Condicion', 'CND-SM2-EST-05-TASADA'], props:{grupo:1}},
  {desde:['Regla', 'SM2-EST-06'], tipo:'REQUIERE', hacia:['Condicion', 'CND-SM2-EST-06-VALOR'], props:{grupo:1}},
  {desde:['Regla', 'SM2-EST-07'], tipo:'REQUIERE', hacia:['Condicion', 'CND-SM2-EST-07-ANIO'], props:{grupo:1}},
  {desde:['Regla', 'SM0-CLAS-01'], tipo:'REQUIERE', hacia:['Condicion', 'CND-SM0-CRITERIOS'], props:{grupo:1}},
  {desde:['Regla', 'SM0-CLAS-01'], tipo:'REQUIERE', hacia:['Condicion', 'CND-SM0-COSTOS'], props:{grupo:2}},
  {desde:['Regla', 'SM0-CLAS-01'], tipo:'REQUIERE', hacia:['Condicion', 'CND-SM0-INFERIDOS'], props:{grupo:3}},
  {desde:['Regla', 'SM0-CLAS-01'], tipo:'REQUIERE', hacia:['Condicion', 'CND-SM0-PENDIENTES'], props:{grupo:4}},
  {desde:['Regla', 'SM3-MARGEN-BASE'], tipo:'PERTENECE_A', hacia:['Submodulo', 'SM3'], props:{}},
  {desde:['Regla', 'SM2-VALUACION'], tipo:'PERTENECE_A', hacia:['Submodulo', 'SM2'], props:{}},
  {desde:['Regla', 'SM2-EST-01'], tipo:'PERTENECE_A', hacia:['Submodulo', 'SM2'], props:{}},
  {desde:['Regla', 'SM2-EST-02'], tipo:'PERTENECE_A', hacia:['Submodulo', 'SM2'], props:{}},
  {desde:['Regla', 'SM2-EST-03'], tipo:'PERTENECE_A', hacia:['Submodulo', 'SM2'], props:{}},
  {desde:['Regla', 'SM2-EST-04'], tipo:'PERTENECE_A', hacia:['Submodulo', 'SM2'], props:{}},
  {desde:['Regla', 'SM2-EST-05'], tipo:'PERTENECE_A', hacia:['Submodulo', 'SM2'], props:{}},
  {desde:['Regla', 'SM2-EST-06'], tipo:'PERTENECE_A', hacia:['Submodulo', 'SM2'], props:{}},
  {desde:['Regla', 'SM2-EST-07'], tipo:'PERTENECE_A', hacia:['Submodulo', 'SM2'], props:{}},
  {desde:['Regla', 'SM2-EST-08'], tipo:'PERTENECE_A', hacia:['Submodulo', 'SM2'], props:{}}
], declarados: declarados_ids} AS entrada_rel
CALL (entrada_rel) {
  UNWIND entrada_rel.relaciones AS rel
  OPTIONAL MATCH (a) WHERE (a.id = rel.desde[1] OR a.nombre = rel.desde[1])
                        AND any(l IN labels(a) WHERE l = rel.desde[0])
  OPTIONAL MATCH (b) WHERE (b.id = rel.hacia[1] OR b.nombre = rel.hacia[1])
                        AND any(l IN labels(b) WHERE l = rel.hacia[0])
  OPTIONAL MATCH (a)-[existente]->(b) WHERE type(existente) = rel.tipo
  WITH rel, collect(existente) AS halladas,
       any(x IN entrada_rel.declarados WHERE x = rel.desde[0] + '|' + rel.desde[1]) AS desde_ok,
       any(x IN entrada_rel.declarados WHERE x = rel.hacia[0] + '|' + rel.hacia[1]) AS hacia_ok
  WITH rel, size(halladas) AS cantidad,
       none(r IN halladas WHERE any(k IN keys(rel.props)
                                    WHERE r[k] IS NOT NULL AND r[k] <> rel.props[k])) AS sin_choque,
       desde_ok AND hacia_ok AS declarados_ok
  RETURN collect({compatible: cantidad <= 1 AND sin_choque AND declarados_ok,
                  pendiente: cantidad = 0}) AS filas_rel
}
// Referencias externas: criterios y submódulos que ya existen en el grafo.
OPTIONAL MATCH (ce_margen_base:CriterioExperto {nombre:'margen_base'})
OPTIONAL MATCH (ce_umbral:CriterioExperto {nombre:'umbral_intervenciones'})
OPTIONAL MATCH (sm2:Submodulo {id:'SM2'})
OPTIONAL MATCH (sm3:Submodulo {id:'SM3'})
WITH filas_nodos, filas_rel,
     nodos_ok AND all(f IN filas_rel WHERE f.compatible)
              AND ce_margen_base IS NOT NULL AND ce_umbral IS NOT NULL
              AND sm2 IS NOT NULL AND sm3 IS NOT NULL AS sin_conflicto,
     ce_margen_base, ce_umbral, sm2, sm3,
     [f IN filas_nodos WHERE f.pendiente] AS pendientes_nodos
// Escrituras: sólo si no hubo ningún conflicto (artefacto atómico).
FOREACH (f IN CASE WHEN sin_conflicto THEN [x IN pendientes_nodos WHERE x.etiqueta = 'Regla']
                   ELSE [] END |
  MERGE (n:Regla {id: f.id}) SET n += f.props)
FOREACH (f IN CASE WHEN sin_conflicto THEN [x IN pendientes_nodos WHERE x.etiqueta = 'VersionPoliticas']
                   ELSE [] END |
  MERGE (n:VersionPoliticas {id: f.id}) SET n += f.props)
FOREACH (f IN CASE WHEN sin_conflicto THEN [x IN pendientes_nodos WHERE x.etiqueta = 'Condicion']
                   ELSE [] END |
  MERGE (n:Condicion {id: f.id}) SET n += f.props)
FOREACH (f IN CASE WHEN sin_conflicto THEN [x IN pendientes_nodos WHERE x.etiqueta = 'PasoCalculo']
                   ELSE [] END |
  MERGE (n:PasoCalculo {id: f.id}) SET n += f.props)
// Relaciones: MERGE idempotente sobre los extremos ya existentes o creados arriba.
FOREACH (x IN CASE WHEN sin_conflicto THEN [1] ELSE [] END |
  MERGE (vpm:VersionPoliticas {id:'VP-SM3-MARGEN'})
  MERGE (vpc:VersionPoliticas {id:'VP-SM3-CALCULO'})
  MERGE (vpv:VersionPoliticas {id:'VP-SM2-VALUACION'})
  MERGE (vpe:VersionPoliticas {id:'VP-SM2-ESTADO'})
  MERGE (vpc2:VersionPoliticas {id:'VP-SM0-CLASIFICACION'})
  MERGE (rbase:Regla {id:'SM3-MARGEN-BASE'})
  MERGE (r34:Regla {id:'R3.4'})
  MERGE (r35:Regla {id:'R3.5'})
  MERGE (r36:Regla {id:'R3.6'})
  MERGE (rval:Regla {id:'SM2-VALUACION'})
  MERGE (r24:Regla {id:'R2.4'})
  MERGE (e1:Regla {id:'SM2-EST-01'})
  MERGE (e2:Regla {id:'SM2-EST-02'})
  MERGE (e3:Regla {id:'SM2-EST-03'})
  MERGE (e4:Regla {id:'SM2-EST-04'})
  MERGE (e5:Regla {id:'SM2-EST-05'})
  MERGE (e6:Regla {id:'SM2-EST-06'})
  MERGE (e7:Regla {id:'SM2-EST-07'})
  MERGE (e8:Regla {id:'SM2-EST-08'})
  MERGE (k1:Regla {id:'SM0-CLAS-01'})
  MERGE (k2:Regla {id:'SM0-CLAS-02'})
  MERGE (p1:PasoCalculo {id:'PC-SM3-MARGEN-NETO'})
  MERGE (p2:PasoCalculo {id:'PC-SM3-RATIO'})
  MERGE (p3:PasoCalculo {id:'PC-SM3-CONTRATOFERTA'})
  MERGE (p4:PasoCalculo {id:'PC-SM3-DESCUENTO'})
  MERGE (p5:PasoCalculo {id:'PC-SM3-BRECHA'})
  MERGE (c1:Condicion {id:'CND-SM3-R34-RIESGO'})
  MERGE (c2:Condicion {id:'CND-SM3-R34-DEMANDA'})
  MERGE (c3:Condicion {id:'CND-SM3-R35-RIESGO'})
  MERGE (c4:Condicion {id:'CND-SM3-R36-INTERV'})
  MERGE (m1:Condicion {id:'CND-SM2-EST-01-PROCESADOR'})
  MERGE (m2:Condicion {id:'CND-SM2-EST-01-ORIGEN'})
  MERGE (m3:Condicion {id:'CND-SM2-EST-02-PROCESADOR'})
  MERGE (m4:Condicion {id:'CND-SM2-EST-03-LINEA'})
  MERGE (m5:Condicion {id:'CND-SM2-EST-04-DECLARADA'})
  MERGE (m6:Condicion {id:'CND-SM2-EST-04-INFORMADA'})
  MERGE (m7:Condicion {id:'CND-SM2-EST-05-TASADA'})
  MERGE (m8:Condicion {id:'CND-SM2-EST-06-VALOR'})
  MERGE (m9:Condicion {id:'CND-SM2-EST-07-ANIO'})
  MERGE (s1:Condicion {id:'CND-SM0-CRITERIOS'})
  MERGE (s2:Condicion {id:'CND-SM0-COSTOS'})
  MERGE (s3:Condicion {id:'CND-SM0-INFERIDOS'})
  MERGE (s4:Condicion {id:'CND-SM0-PENDIENTES'})
  // Etapas de SM3
  MERGE (vpm)-[:INCLUYE]->(rbase)
  MERGE (vpm)-[:INCLUYE]->(r34)
  MERGE (vpm)-[:INCLUYE]->(r35)
  MERGE (vpm)-[:INCLUYE]->(r36)
  MERGE (vpc)-[:INCLUYE]->(p1)
  MERGE (vpc)-[:INCLUYE]->(p2)
  MERGE (vpc)-[:INCLUYE]->(p3)
  MERGE (vpc)-[:INCLUYE]->(p4)
  MERGE (vpc)-[:INCLUYE]->(p5)
  // Etapas de SM2 y SM0
  MERGE (vpv)-[:INCLUYE]->(rval)
  MERGE (vpv)-[:INCLUYE]->(r24)
  MERGE (vpe)-[:INCLUYE]->(e1)
  MERGE (vpe)-[:INCLUYE]->(e2)
  MERGE (vpe)-[:INCLUYE]->(e3)
  MERGE (vpe)-[:INCLUYE]->(e4)
  MERGE (vpe)-[:INCLUYE]->(e5)
  MERGE (vpe)-[:INCLUYE]->(e6)
  MERGE (vpe)-[:INCLUYE]->(e7)
  MERGE (vpe)-[:INCLUYE]->(e8)
  MERGE (vpc2)-[:INCLUYE]->(k1)
  MERGE (vpc2)-[:INCLUYE]->(k2)
  // Condiciones del margen y su criterio
  MERGE (r34)-[:REQUIERE {grupo:1}]->(c1)
  MERGE (r34)-[:REQUIERE {grupo:2}]->(c2)
  MERGE (r35)-[:REQUIERE {grupo:1}]->(c3)
  MERGE (r36)-[:REQUIERE {grupo:1}]->(c4)
  MERGE (c4)-[:USA_CRITERIO]->(ce_umbral)
  MERGE (rbase)-[:USA_CRITERIO]->(ce_margen_base)
  // Condiciones del estado comercial
  MERGE (e1)-[:REQUIERE {grupo:1}]->(m1)
  MERGE (e1)-[:REQUIERE {grupo:2}]->(m2)
  MERGE (e2)-[:REQUIERE {grupo:1}]->(m3)
  MERGE (e3)-[:REQUIERE {grupo:1}]->(m4)
  MERGE (e4)-[:REQUIERE {grupo:1}]->(m5)
  MERGE (e4)-[:REQUIERE {grupo:2}]->(m6)
  MERGE (e5)-[:REQUIERE {grupo:1}]->(m7)
  MERGE (e6)-[:REQUIERE {grupo:1}]->(m8)
  MERGE (e7)-[:REQUIERE {grupo:1}]->(m9)
  // Condiciones de la clasificación Firme/Provisional
  MERGE (k1)-[:REQUIERE {grupo:1}]->(s1)
  MERGE (k1)-[:REQUIERE {grupo:2}]->(s2)
  MERGE (k1)-[:REQUIERE {grupo:3}]->(s3)
  MERGE (k1)-[:REQUIERE {grupo:4}]->(s4)
  // Pertenencia al submódulo (misma convención que el PG2)
  MERGE (rbase)-[:PERTENECE_A]->(sm3)
  MERGE (rval)-[:PERTENECE_A]->(sm2)
  MERGE (e1)-[:PERTENECE_A]->(sm2)
  MERGE (e2)-[:PERTENECE_A]->(sm2)
  MERGE (e3)-[:PERTENECE_A]->(sm2)
  MERGE (e4)-[:PERTENECE_A]->(sm2)
  MERGE (e5)-[:PERTENECE_A]->(sm2)
  MERGE (e6)-[:PERTENECE_A]->(sm2)
  MERGE (e7)-[:PERTENECE_A]->(sm2)
  MERGE (e8)-[:PERTENECE_A]->(sm2)
)
RETURN CASE WHEN sin_conflicto THEN 0
            ELSE size([f IN filas_nodos WHERE NOT (f.presencia AND f.sin_choque)])
                 + size([f IN filas_rel WHERE NOT f.compatible]) END AS conflictos,
       CASE WHEN sin_conflicto
            THEN size(pendientes_nodos) + size([f IN filas_rel WHERE f.pendiente])
            ELSE 0 END AS actualizadas,
       CASE WHEN sin_conflicto THEN [] ELSE
         ['PoliticasBloque: algún objeto esperado falta o está duplicado, alguna propiedad o '
          + 'relación declarada ya tiene otro valor, o falta un criterio/submódulo de referencia'] END AS errores
