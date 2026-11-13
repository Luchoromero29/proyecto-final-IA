// Correcciones mínimas: conocimiento aditivo, sin modificar criterios ni conjuntos difusos.
// Una transacción sobre el scratch marcado; validar contra correcciones_minimas_delta.json.
// ON CREATE preserva datos existentes: rechazar conflictos antes de confirmar.

CALL () {
  UNWIND [
  {
    id: "R-SM0-DOMINIO-NOTEBOOK",
    decision: "evaluacion_integral",
    requiere_catalogo: true,
    version: "correcciones-minimas-v1",
    estado_validacion: "Provisional",
    fuente: "Correcciones mínimas aprobadas por el operador; política Provisional, pendiente de validación experta"
  },
  {
    id: "R-SM0-BLOQUEO",
    decision: "VerificacionPendiente",
    regla_publica: "R3.3",
    requiere_catalogo: false,
    version: "correcciones-minimas-v1",
    estado_validacion: "Provisional",
    fuente: "Correcciones mínimas aprobadas por el operador; política Provisional, pendiente de validación experta"
  },
  {
    id: "R-SM1-TER-NEGADA",
    etapa: "SM1-TER-entrada",
    caida_pp: 0,
    inferido: false,
    motivo: "Evidencia de throttling informada",
    version: "correcciones-minimas-v1",
    estado_validacion: "Provisional",
    fuente: "Correcciones mínimas aprobadas por el operador; política Provisional, pendiente de validación experta",
    valor_hecho: false,
    requiere_catalogo: false
  },
  {
    id: "R-SM1-TER-AFIRMADA",
    etapa: "SM1-TER-entrada",
    inferido: false,
    motivo: "Evidencia de throttling informada",
    version: "correcciones-minimas-v1",
    estado_validacion: "Provisional",
    fuente: "Correcciones mínimas aprobadas por el operador; política Provisional, pendiente de validación experta",
    valor_hecho: true,
    requiere_catalogo: false
  },
  {
    id: "R-SM1-TER-AUSENTE",
    etapa: "SM1-TER-entrada",
    inferido: true,
    motivo: "Caída de frecuencia no informada: se toma la leve (CE caida_termica_sin_throttling)",
    version: "correcciones-minimas-v1",
    estado_validacion: "Provisional",
    fuente: "Correcciones mínimas aprobadas por el operador; política Provisional, pendiente de validación experta",
    requiere_catalogo: false
  },
  {
    id: "R-SM0-PRECIO",
    decision: "evaluacion_integral",
    requiere_catalogo: false,
    version: "correcciones-minimas-v1",
    estado_validacion: "Provisional",
    fuente: "Correcciones mínimas aprobadas por el operador; política Provisional, pendiente de validación experta"
  }
] AS fila
  MERGE (n:Regla {id:fila.id})
  ON CREATE SET n += fila
  RETURN count(*) AS nodos_Regla
}
CALL () {
  UNWIND [
  {
    id: "PT-SM0-DOMINIO-NOTEBOOK",
    ambito: "SM0-dominio",
    patron: ".*\\b(notebook|laptop|computadora|port[aá]til)\\b.*",
    descripcion: "Aviso de computadora o notebook del catálogo",
    version: "correcciones-minimas-v1",
    estado_validacion: "Provisional",
    fuente: "Correcciones mínimas aprobadas por el operador; política Provisional, pendiente de validación experta"
  },
  {
    id: "PT-SM0-BLOQUEADA",
    ambito: "SM0-bloqueo",
    patron: ".*(?<!sin )(?<!no )(?<!no est[aá] )(?<!no tiene )(?<!no hay )\\bbloquead[oa]\\b.*",
    descripcion: "equipo bloqueado",
    version: "correcciones-minimas-v1",
    estado_validacion: "Provisional",
    fuente: "Correcciones mínimas aprobadas por el operador; política Provisional, pendiente de validación experta"
  },
  {
    id: "PT-SM0-CUENTA",
    ambito: "SM0-bloqueo",
    patron: ".*(?<!sin )(?<!no )(?<!no est[aá] )(?<!no tiene )(?<!no hay )\\bcuenta\\s+(?:de\\s+(?:apple|icloud|google|microsoft)|(?:del?\\s+)?(?:dueño|propietario|anterior))\\b.*",
    descripcion: "cuenta de otro propietario",
    version: "correcciones-minimas-v1",
    estado_validacion: "Provisional",
    fuente: "Correcciones mínimas aprobadas por el operador; política Provisional, pendiente de validación experta"
  },
  {
    id: "PT-SM0-CLAVE",
    ambito: "SM0-bloqueo",
    patron: ".*(?<!sin )(?<!no )(?<!no est[aá] )(?<!no tiene )(?<!no hay )\\b(?:clave\\s+de\\s+bios|bios\\s+con\\s+clave|contrase[nñ]a|icloud|mdm)\\b.*",
    descripcion: "clave o vinculación de seguridad",
    version: "correcciones-minimas-v1",
    estado_validacion: "Provisional",
    fuente: "Correcciones mínimas aprobadas por el operador; política Provisional, pendiente de validación experta"
  },
  {
    id: "PT-SM1-TER-NEGADA",
    ambito: "SM1-TER-hechos",
    patron: ".*\\b(?:sin\\s+(?:thermal\\s+)?throttling|no\\s+(?:(?:tiene|presenta|hay)\\s+)?(?:thermal\\s+)?throttling)\\b.*",
    descripcion: "El texto niega explícitamente el throttling",
    version: "correcciones-minimas-v1",
    estado_validacion: "Provisional",
    fuente: "Correcciones mínimas aprobadas por el operador; política Provisional, pendiente de validación experta"
  },
  {
    id: "PT-SIN-RECALENTAMIENTO",
    ambito: "SM1-diagnostico",
    tratamiento: "verificar",
    orden: 1,
    patron: ".*\\b(?<!no )(?:se\\s+recalienta|baja\\s+la\\s+frecuencia)\\b.*",
    descripcion: "Recalentamiento o baja de frecuencia sin diagnóstico",
    version: "correcciones-minimas-v1",
    estado_validacion: "Provisional",
    fuente: "Correcciones mínimas aprobadas por el operador; política Provisional, pendiente de validación experta"
  },
  {
    id: "PT-SM0-PRECIO",
    ambito: "SM0-precio",
    patron: ".*(\\$\\s*\\d|\\d{3}\\.\\d{3}|\\bpiden\\b|\\bprecio\\b).*",
    descripcion: "El mensaje contiene precio",
    version: "correcciones-minimas-v1",
    estado_validacion: "Provisional",
    fuente: "Correcciones mínimas aprobadas por el operador; política Provisional, pendiente de validación experta"
  }
] AS fila
  MERGE (n:PatronTexto {id:fila.id})
  ON CREATE SET n += fila
  RETURN count(*) AS nodos_PatronTexto
}
CALL () {
  UNWIND [
  {
    id: "CND-SM1-TER-NEGADA",
    campo: "throttling",
    operador: "=",
    valor: false,
    version: "correcciones-minimas-v1",
    estado_validacion: "Provisional",
    fuente: "Correcciones mínimas aprobadas por el operador; política Provisional, pendiente de validación experta"
  },
  {
    id: "CND-SM1-TER-AFIRMADA",
    campo: "throttling",
    operador: "=",
    valor: true,
    version: "correcciones-minimas-v1",
    estado_validacion: "Provisional",
    fuente: "Correcciones mínimas aprobadas por el operador; política Provisional, pendiente de validación experta"
  },
  {
    id: "CND-SM1-TER-AUSENTE",
    campo: "throttling",
    operador: "ausente",
    version: "correcciones-minimas-v1",
    estado_validacion: "Provisional",
    fuente: "Correcciones mínimas aprobadas por el operador; política Provisional, pendiente de validación experta"
  }
] AS fila
  MERGE (n:Condicion {id:fila.id})
  ON CREATE SET n += fila
  RETURN count(*) AS nodos_Condicion
}
CALL () {
  UNWIND [
  {
    id: "FS-RECALENTAMIENTO-SIN-DIAGNOSTICO",
    descripcion: "Recalentamiento o baja de frecuencia sin diagnóstico",
    version: "correcciones-minimas-v1",
    estado_validacion: "Provisional",
    fuente: "Correcciones mínimas aprobadas por el operador; política Provisional, pendiente de validación experta"
  }
] AS fila
  MERGE (n:FallaSintoma {id:fila.id})
  ON CREATE SET n += fila
  RETURN count(*) AS nodos_FallaSintoma
}
CALL () {
  UNWIND [
  {
    origen: "PT-SM0-DOMINIO-NOTEBOOK",
    destino: "R-SM0-DOMINIO-NOTEBOOK"
  },
  {
    origen: "PT-SM0-BLOQUEADA",
    destino: "R-SM0-BLOQUEO"
  },
  {
    origen: "PT-SM0-CUENTA",
    destino: "R-SM0-BLOQUEO"
  },
  {
    origen: "PT-SM0-CLAVE",
    destino: "R-SM0-BLOQUEO"
  },
  {
    origen: "PT-SM1-TER-NEGADA",
    destino: "R-SM1-TER-NEGADA"
  },
  {
    origen: "FS-RECALENTAMIENTO-SIN-DIAGNOSTICO",
    destino: "R3.3c"
  },
  {
    origen: "PT-SM0-PRECIO",
    destino: "R-SM0-PRECIO"
  }
] AS fila
  MATCH (a {id:fila.origen}), (b {id:fila.destino})
  MERGE (a)-[r:ACTIVA]->(b)
  RETURN count(*) AS relaciones_ACTIVA
}
CALL () {
  UNWIND [
  {
    origen: "R-SM1-TER-NEGADA",
    destino: "CND-SM1-TER-NEGADA"
  },
  {
    origen: "R-SM1-TER-AFIRMADA",
    destino: "CND-SM1-TER-AFIRMADA"
  },
  {
    origen: "R-SM1-TER-AUSENTE",
    destino: "CND-SM1-TER-AUSENTE"
  }
] AS fila
  MATCH (a {id:fila.origen}), (b {id:fila.destino})
  MERGE (a)-[r:REQUIERE]->(b)
  RETURN count(*) AS relaciones_REQUIERE
}
CALL () {
  UNWIND [
  {
    origen: "R-SM1-TER-AFIRMADA",
    destino: "CE-32"
  },
  {
    origen: "R-SM1-TER-AUSENTE",
    destino: "CE-31"
  }
] AS fila
  MATCH (a {id:fila.origen}), (b {id:fila.destino})
  MERGE (a)-[r:USA_CRITERIO]->(b)
  RETURN count(*) AS relaciones_USA_CRITERIO
}
CALL () {
  UNWIND [
  {
    origen: "PT-SIN-RECALENTAMIENTO",
    destino: "FS-RECALENTAMIENTO-SIN-DIAGNOSTICO"
  }
] AS fila
  MATCH (a {id:fila.origen}), (b {id:fila.destino})
  MERGE (a)-[r:EVIDENCIA_DE]->(b)
  RETURN count(*) AS relaciones_EVIDENCIA_DE
}
RETURN nodos_Regla + nodos_PatronTexto + nodos_Condicion + nodos_FallaSintoma AS nodos_declarados,
       relaciones_ACTIVA + relaciones_REQUIERE + relaciones_USA_CRITERIO + relaciones_EVIDENCIA_DE AS relaciones_declaradas
