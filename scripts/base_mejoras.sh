#!/bin/sh
# Copia la base de trabajo de EvalTIC y aplica SÓLO las mejoras aditivas sobre la copia.
#
#   sh scripts/base_mejoras.sh respaldo     # tar del volumen original + sha256 (detiene el original unos segundos)
#   sh scripts/base_mejoras.sh copiar       # restaura el respaldo en un volumen nuevo y levanta la copia (7688/7475)
#   sh scripts/base_mejoras.sh actualizar   # aplica las 8 semillas aditivas en orden sobre la copia
#   sh scripts/base_mejoras.sh verificar    # compara original vs copia e informa el conocimiento aplicado
#   sh scripts/base_mejoras.sh detener      # baja el contenedor de la copia (conserva el volumen)
#
# La base ORIGINAL nunca recibe semillas: sólo se lee y se le toma el respaldo.
# No se ejecutan PG2 (bloque 0 borra todo) ni Grupo_20_PG3_mercado.cypher (borra Línea/AvisoMercado
# y recalibra): la copia ya trae el catálogo de 333 avisos. Ver docs/ESTADO_CONSOLIDADO_MEJORAS.md.
set -eu

AQUI=$(cd "$(dirname "$0")/.." && pwd)
IMAGEN="neo4j:5.26-community"
CLAVE="${NEO4J_PASSWORD:-evaltic2026}"

ORIGEN_CONT="neo4j-evaltic"
ORIGEN_VOL="proyecto-ia-final_neo4j_data"

COPIA_CONT="evaltic-neo4j-mejoras"
COPIA_VOL="proyecto-ia-final_neo4j_mejoras"
COPIA_URI="bolt://127.0.0.1:7688"
COPIA_HTTP="127.0.0.1:7475"

FECHA=$(date +%Y%m%d-%H%M)
RESPALDO_DIR="$AQUI/_respaldo_original/$FECHA"
RESPALDO_TAR="neo4j_data.tar.gz"
LOGS="$AQUI/docs/ejecuciones"

# Orden de aplicación: cada semilla depende de las anteriores y del catálogo que ya trae la copia.
# PG2 y mercado quedan excluidos a propósito.
SEMILLAS="
Grupo_20_PG3_diagnostico.cypher
Grupo_20_PG3_correcciones_minimas.cypher
Grupo_20_PG3_politicas.cypher
Grupo_20_PG3_politicas_sm1_acciones.cypher
Grupo_20_PG3_politicas_sm1_estado.cypher
Grupo_20_PG3_politicas_sm3_filtro.cypher
Grupo_20_PG3_politicas_sm3_riesgo_demanda.cypher
Grupo_20_PG3_politicas_bloque.cypher
"

log() { echo "[base_mejoras] $*"; }
err() { echo "[base_mejoras] ERROR: $*" >&2; exit 1; }

# El entrypoint de la imagen baja privilegios al usuario neo4j; los contenedores
# auxiliares de tar corren como root para poder leer/escribir los volúmenes.
tar_container() { # args del contenedor; el comando tar va aparte
  docker run --rm --user 0 --entrypoint sh "$@"
}

# Si algo falla después de detener el original, se lo vuelve a levantar.
PROTEGER_ORIGEN=0
restaurar_original() {
  if [ "$PROTEGER_ORIGEN" = "1" ]; then
    echo "[base_mejoras] falló el respaldo: reiniciando $ORIGEN_CONT" >&2
    docker start "$ORIGEN_CONT" >/dev/null 2>&1 || true
  fi
}


esperar_neo4j() { # contenedor
  i=0
  until docker exec "$1" cypher-shell -a bolt://127.0.0.1:7687 -u neo4j -p "$CLAVE" "RETURN 1;" >/dev/null 2>&1; do
    i=$((i + 1))
    [ "$i" -le 60 ] || err "Neo4j no respondió en $1 tras 60 intentos"
    sleep 2
  done
}

consulta() { # contenedor, cypher
  docker exec "$1" cypher-shell -a bolt://127.0.0.1:7687 -u neo4j -p "$CLAVE" --format plain "$2"
}

inventario() { # contenedor -> huella canónica por stdout
  {
    consulta "$1" "MATCH (n) RETURN count(n) AS nodos;"
    consulta "$1" "MATCH ()-[r]->() RETURN count(r) AS relaciones;"
    consulta "$1" "MATCH (n) WITH labels(n) AS etiqueta, count(*) AS cantidad RETURN etiqueta, cantidad ORDER BY etiqueta;"
    consulta "$1" "MATCH ()-[r]->() RETURN type(r) AS tipo, count(*) AS cantidad ORDER BY tipo;"
    consulta "$1" "SHOW CONSTRAINTS YIELD name RETURN name ORDER BY name;"
  } 2>/dev/null
}

huella() { # contenedor -> sha256 del inventario
  inventario "$1" | sha256sum | cut -d' ' -f1
}

resumen() { # contenedor
  consulta "$1" "MATCH (n) RETURN count(n) AS nodos;" | tail -n 1 | tr '\n' ' '
  consulta "$1" "MATCH ()-[r]->() RETURN count(r) AS relaciones;" | tail -n 1
}

# ---------------------------------------------------------------- respaldo
cmd_respaldo() {
  if [ -f "$RESPALDO_DIR/$RESPALDO_TAR" ]; then
    [ "${FORZAR:-0}" = "1" ] || err "ya existe $RESPALDO_DIR/$RESPALDO_TAR (usá FORZAR=1 para reemplazarlo)"
  fi
  log "deteniendo $ORIGEN_CONT para copiar el volumen sin riesgo de archivos a medio escribir"
  PROTEGER_ORIGEN=1
  trap restaurar_original EXIT
  docker stop "$ORIGEN_CONT" >/dev/null
  mkdir -p "$RESPALDO_DIR"
  log "respaldando volumen $ORIGEN_VOL en $RESPALDO_DIR/$RESPALDO_TAR"
  tar_container -v "$ORIGEN_VOL":/datos:ro -v "$RESPALDO_DIR":/salida "$IMAGEN" \
    -c "tar czf /salida/$RESPALDO_TAR -C /datos ." >/dev/null
  log "reiniciando $ORIGEN_CONT"
  docker start "$ORIGEN_CONT" >/dev/null
  PROTEGER_ORIGEN=0
  esperar_neo4j "$ORIGEN_CONT"
  SHA=$(sha256sum "$RESPALDO_DIR/$RESPALDO_TAR" | cut -d' ' -f1)
  TAM=$(du -h "$RESPALDO_DIR/$RESPALDO_TAR" | cut -f1)
  log "respaldo listo: $TAM  sha256=$SHA"
  log "original tras reiniciar: $(resumen "$ORIGEN_CONT")"
  echo "$SHA  $RESPALDO_TAR" > "$RESPALDO_DIR/neo4j_data.tar.gz.sha256"
  echo "$RESPALDO_DIR"
}

# ------------------------------------------------------------------ copiar
cmd_copiar() {
  [ -n "${RESPALDO_FUENTE:-}" ] || err "indicá el respaldo a restaurar: RESPALDO_FUENTE=_respaldo_original/<fecha>"
  TAR="$AQUI/$RESPALDO_FUENTE/$RESPALDO_TAR"
  [ -f "$TAR" ] || err "no existe $TAR"
  [ -f "$AQUI/$RESPALDO_FUENTE/neo4j_data.tar.gz.sha256" ] || err "falta el .sha256 del respaldo: no se certifica la restauración"
  ( cd "$AQUI/$RESPALDO_FUENTE" && sha256sum -c neo4j_data.tar.gz.sha256 ) || err "el respaldo no coincide con su sha256"

  ORIGEN_HUELLA=$(huella "$ORIGEN_CONT")
  log "huella original: $ORIGEN_HUELLA"

  if docker volume inspect "$COPIA_VOL" >/dev/null 2>&1; then
    err "el volumen $COPIA_VOL ya existe; borralo a mano si querés rehacer la copia (docker volume rm)"
  fi
  docker volume create "$COPIA_VOL" >/dev/null
  log "restaurando el respaldo en el volumen nuevo $COPIA_VOL (esto verifica que el respaldo sirve)"
  tar_container -v "$COPIA_VOL":/datos -v "$AQUI/$RESPALDO_FUENTE":/respaldo:ro "$IMAGEN" \
    -c "tar xzf /respaldo/$RESPALDO_TAR -C /datos" >/dev/null

  log "levantando $COPIA_CONT en $COPIA_URI (browser http://$COPIA_HTTP)"
  docker run -d --name "$COPIA_CONT" \
    -p "127.0.0.1:7688:7687" -p "$COPIA_HTTP:7474" \
    -v "$COPIA_VOL":/data \
    -v "$AQUI/cypher":/cypher:ro \
    -e NEO4J_AUTH="neo4j/$CLAVE" \
    -e NEO4J_server_memory_heap_max__size=1G \
    -e NEO4J_server_memory_pagecache_size=512M \
    "$IMAGEN" >/dev/null
  esperar_neo4j "$COPIA_CONT"

  COPIA_HUELLA=$(huella "$COPIA_CONT")
  log "huella copia:    $COPIA_HUELLA"
  log "copia: $(resumen "$COPIA_CONT")"
  if [ "$ORIGEN_HUELLA" != "$COPIA_HUELLA" ]; then
    err "la copia NO coincide con el original; no se aplican mejoras"
  fi
  log "OK: la copia es idéntica al original (nodos, relaciones, etiquetas, tipos y restricciones)"
}

# -------------------------------------------------------------- actualizar
cmd_actualizar() {
  docker inspect "$COPIA_CONT" >/dev/null 2>&1 || err "no existe el contenedor $COPIA_CONT (corré 'copiar' primero)"
  mkdir -p "$LOGS"
  INICIO=$(huella "$COPIA_CONT")
  log "huella inicial de la copia: $INICIO"
  for SEMILLA in $SEMILLAS; do
    [ -f "$AQUI/cypher/$SEMILLA" ] || err "falta cypher/$SEMILLA"
    ANTES=$(resumen "$COPIA_CONT")
    log "aplicando $SEMILLA ..."
    if ! docker exec "$COPIA_CONT" cypher-shell -a bolt://127.0.0.1:7687 -u neo4j -p "$CLAVE" \
        -f "/cypher/$SEMILLA" > "$LOGS/${PREFIJO_LOG:-mejoras_copia}_$SEMILLA.log" 2>&1; then
      err "falló $SEMILLA (ver docs/ejecuciones/${PREFIJO_LOG:-mejoras_copia}_$SEMILLA.log)"
    fi
    DESPUES=$(resumen "$COPIA_CONT")
    log "  antes: $ANTES | después: $DESPUES"
  done
  log "huella final: $(huella "$COPIA_CONT")"
  log "OK: semillas aplicadas. Corré 'verificar' y después la segunda aplicación para probar idempotencia."
}

# --------------------------------------------------------------- verificar
cmd_verificar() {
  echo "--- original ($ORIGEN_CONT) ---"
  huella "$ORIGEN_CONT"; echo "nodos/relaciones: $(resumen "$ORIGEN_CONT")"
  echo "--- copia ($COPIA_CONT) ---"
  huella "$COPIA_CONT"; echo "nodos/relaciones: $(resumen "$COPIA_CONT")"
  echo "--- conocimiento esperado en la copia ---"
  consulta "$COPIA_CONT" "RETURN 'Diagnostico' AS tipo, count { MATCH (n:Diagnostico) } AS n
UNION ALL RETURN 'FallaSintoma' AS tipo, count { MATCH (n:FallaSintoma) } AS n
UNION ALL RETURN 'PatronTexto' AS tipo, count { MATCH (n:PatronTexto) } AS n
UNION ALL RETURN 'Intervencion' AS tipo, count { MATCH (n:Intervencion) } AS n
UNION ALL RETURN 'Condicion' AS tipo, count { MATCH (n:Condicion) } AS n
UNION ALL RETURN 'VersionPoliticas' AS tipo, count { MATCH (n:VersionPoliticas) } AS n
UNION ALL RETURN 'PasoCalculo' AS tipo, count { MATCH (n:PasoCalculo) } AS n
UNION ALL RETURN 'CriterioExperto' AS tipo, count { MATCH (n:CriterioExperto) } AS n
UNION ALL RETURN 'Regla' AS tipo, count { MATCH (n:Regla) } AS n
UNION ALL RETURN 'AvisoMercado' AS tipo, count { MATCH (n:AvisoMercado) } AS n
UNION ALL RETURN 'Procesador' AS tipo, count { MATCH (n:Procesador) } AS n
UNION ALL RETURN 'Linea' AS tipo, count { MATCH (n:Linea) } AS n
UNION ALL RETURN 'EntornoPruebas' AS tipo, count { MATCH (n:EntornoPruebas) } AS n;"
  echo "--- reglas clave ---"
  consulta "$COPIA_CONT" "MATCH (r:Regla) WHERE r.id IN ['R3.3c','R3.7','R3.8','R2.4','SM3-MARGEN-BASE','SM2-VALUACION']
RETURN r.id AS regla, keys(r) AS propiedades ORDER BY regla;"
}

# ----------------------------------------------------------------- detener
cmd_detener() {
  docker stop "$COPIA_CONT" >/dev/null 2>&1 && log "copia detenida (el volumen $COPIA_VOL se conserva)" || log "la copia ya estaba detenida"
}

case "${1:-}" in
  respaldo)   cmd_respaldo ;;
  copiar)     cmd_copiar ;;
  actualizar) cmd_actualizar ;;
  verificar)  cmd_verificar ;;
  detener)    cmd_detener ;;
  *) echo "uso: sh scripts/base_mejoras.sh {respaldo|copiar|actualizar|verificar|detener}" >&2; exit 2 ;;
esac
