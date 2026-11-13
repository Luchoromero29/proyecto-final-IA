#!/bin/sh
# Copia la base de trabajo de EvalTIC y aplica SÓLO las mejoras aditivas.
#
#   sh scripts/base_mejoras.sh respaldo     # tar del volumen original + sha256
#   sh scripts/base_mejoras.sh copiar       # restaura el respaldo en un volumen nuevo y levanta la copia
#   sh scripts/base_mejoras.sh actualizar   # aplica las 8 semillas aditivas, en orden, sobre la copia
#   sh scripts/base_mejoras.sh verificar    # compara original vs copia e informa el conocimiento aplicado
#   sh scripts/base_mejoras.sh promover     # respalda y aplica las 8 semillas sobre la base ORIGINAL
#   sh scripts/base_mejoras.sh detener      # baja el contenedor de la copia (conserva el volumen)
#
# Para otro integrante del grupo: se cambian los destinos por variable de entorno, por ejemplo
#   COPIA_CONT=evaltic-mejoras-luciano COPIA_VOL=luciano_mejoras \
#   COPIA_PUERTO_BOLT=7698 COPIA_PUERTO_HTTP=7485 sh scripts/base_mejoras.sh copiar
# El volumen del original se detecta solo desde el contenedor (ORIGEN_VOL lo puede forzar) y la
# contraseña sale de NEO4J_PASSWORD, con `evaltic2026` por defecto.
#
# La base ORIGINAL no recibe nada salvo que corras `promover`, que primero toma respaldo y aborta
# si no puede. No se ejecutan PG2 (el bloque 0 borra todo) ni Grupo_20_PG3_mercado.cypher (borra
# Línea/AvisoMercado y recalibra): la base ya trae el catálogo de 333 avisos.
# Ver docs/ESTADO_CONSOLIDADO_MEJORAS.md.
set -eu

AQUI=$(cd "$(dirname "$0")/.." && pwd)
IMAGEN="neo4j:5.26-community"
CLAVE="${NEO4J_PASSWORD:-evaltic2026}"

ORIGEN_CONT="${ORIGEN_CONT:-neo4j-evaltic}"
ORIGEN_VOL="${ORIGEN_VOL:-}"              # vacío: se detecta desde el contenedor

COPIA_CONT="${COPIA_CONT:-evaltic-neo4j-mejoras}"
COPIA_VOL="${COPIA_VOL:-proyecto-ia-final_neo4j_mejoras}"
COPIA_PUERTO_BOLT="${COPIA_PUERTO_BOLT:-7688}"
COPIA_PUERTO_HTTP="${COPIA_PUERTO_HTTP:-7475}"

RESPALDO_RAIZ="$AQUI/_respaldo_original"
RESPALDO_TAR="neo4j_data.tar.gz"
LOGS="$AQUI/docs/ejecuciones"

# Orden de aplicación: cada semilla depende de las anteriores y del catálogo que ya trae la base.
# PG2 y mercado quedan excluidos a propósito.
SEMILLAS="
Grupo_20_PG3_diagnostico.cypher
Grupo_20_PG3_correcciones_minimas.cypher
Grupo_20_PG3_politicas.cypher
Grupo_20_PG3_politicas_sm1_acciones.cypher
Grupo_20_PG3_supuestos_operativos.cypher
Grupo_20_PG3_politicas_sm1_estado.cypher
Grupo_20_PG3_politicas_sm3_filtro.cypher
Grupo_20_PG3_politicas_sm3_riesgo_demanda.cypher
Grupo_20_PG3_politicas_bloque.cypher
"

log() { echo "[base_mejoras] $*" >&2; }
err() { echo "[base_mejoras] ERROR: $*" >&2; exit 1; }

# El entrypoint de la imagen baja privilegios al usuario neo4j; los contenedores auxiliares de
# tar corren como root para poder leer y escribir los volúmenes.
tar_container() {
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

volumen_de() { # contenedor -> nombre del volumen montado en /data
  docker inspect "$1" --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}'
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

tomar_respaldo() { # sufijo -> imprime la ruta del respaldo
  DEST="$RESPALDO_RAIZ/$(date +%Y%m%d-%H%M)${1:-}"
  if [ -f "$DEST/$RESPALDO_TAR" ]; then
    [ "${FORZAR:-0}" = "1" ] || err "ya existe $DEST/$RESPALDO_TAR (usá FORZAR=1 para reemplazarlo)"
  fi
  mkdir -p "$DEST"
  log "respaldando volumen $VOL_ORIGEN en $DEST/$RESPALDO_TAR"
  tar_container -v "$VOL_ORIGEN":/datos:ro -v "$DEST":/salida "$IMAGEN" \
    -c "tar czf /salida/$RESPALDO_TAR -C /datos ." >/dev/null
  SHA=$(sha256sum "$DEST/$RESPALDO_TAR" | cut -d' ' -f1)
  echo "$SHA  $RESPALDO_TAR" > "$DEST/neo4j_data.tar.gz.sha256"
  log "respaldo listo: $(du -h "$DEST/$RESPALDO_TAR" | cut -f1)  sha256=$SHA"
  echo "$DEST"
}

aplicar_semillas() { # contenedor, prefijo de log
  mkdir -p "$LOGS"
  for SEMILLA in $SEMILLAS; do
    [ -f "$AQUI/cypher/$SEMILLA" ] || err "falta cypher/$SEMILLA"
    ANTES=$(resumen "$1")
    log "  $SEMILLA ..."
    if ! docker exec -i "$1" cypher-shell -a bolt://127.0.0.1:7687 -u neo4j -p "$CLAVE" \
        < "$AQUI/cypher/$SEMILLA" > "$LOGS/${2}_$SEMILLA.log" 2>&1; then
      err "falló $SEMILLA (ver docs/ejecuciones/${2}_$SEMILLA.log)"
    fi
    log "    antes: $ANTES | después: $(resumen "$1")"
  done
}

comprobar_conocimiento() { # contenedor
  consulta "$1" "RETURN 'Diagnostico' AS tipo, count { MATCH (n:Diagnostico) } AS n
UNION ALL RETURN 'FallaSintoma' AS tipo, count { MATCH (n:FallaSintoma) } AS n
UNION ALL RETURN 'PatronTexto' AS tipo, count { MATCH (n:PatronTexto) } AS n
UNION ALL RETURN 'Condicion' AS tipo, count { MATCH (n:Condicion) } AS n
UNION ALL RETURN 'VersionPoliticas' AS tipo, count { MATCH (n:VersionPoliticas) } AS n
UNION ALL RETURN 'PasoCalculo' AS tipo, count { MATCH (n:PasoCalculo) } AS n
UNION ALL RETURN 'CriterioExperto' AS tipo, count { MATCH (n:CriterioExperto) } AS n
UNION ALL RETURN 'Regla' AS tipo, count { MATCH (n:Regla) } AS n
UNION ALL RETURN 'AvisoMercado' AS tipo, count { MATCH (n:AvisoMercado) } AS n
UNION ALL RETURN 'Procesador' AS tipo, count { MATCH (n:Procesador) } AS n
UNION ALL RETURN 'Linea' AS tipo, count { MATCH (n:Linea) } AS n
UNION ALL RETURN 'EntornoPruebas' AS tipo, count { MATCH (n:EntornoPruebas) } AS n;"
}

# ---------------------------------------------------------------- respaldo
cmd_respaldo() {
  docker inspect "$ORIGEN_CONT" >/dev/null 2>&1 || err "no existe el contenedor $ORIGEN_CONT"
  VOL_ORIGEN="${ORIGEN_VOL:-$(volumen_de "$ORIGEN_CONT")}"
  [ -n "$VOL_ORIGEN" ] || err "no pude detectar el volumen /data de $ORIGEN_CONT; pasá ORIGEN_VOL"
  log "deteniendo $ORIGEN_CONT para copiar el volumen sin archivos a medio escribir"
  PROTEGER_ORIGEN=1
  trap restaurar_original EXIT
  docker stop "$ORIGEN_CONT" >/dev/null
  DESTINO=$(tomar_respaldo)
  log "reiniciando $ORIGEN_CONT"
  docker start "$ORIGEN_CONT" >/dev/null
  PROTEGER_ORIGEN=0
  esperar_neo4j "$ORIGEN_CONT"
  log "original tras reiniciar: $(resumen "$ORIGEN_CONT")"
  echo "$DESTINO"
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

  log "levantando $COPIA_CONT en bolt://127.0.0.1:$COPIA_PUERTO_BOLT (browser http://127.0.0.1:$COPIA_PUERTO_HTTP)"
  docker rm -f "$COPIA_CONT" >/dev/null 2>&1 || true
  docker run -d --name "$COPIA_CONT" \
    -p "127.0.0.1:$COPIA_PUERTO_BOLT:7687" -p "127.0.0.1:$COPIA_PUERTO_HTTP:7474" \
    -v "$COPIA_VOL":/data \
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
  log "huella inicial de la copia: $(huella "$COPIA_CONT")"
  aplicar_semillas "$COPIA_CONT" "${PREFIJO_LOG:-mejoras_copia}"
  log "huella final: $(huella "$COPIA_CONT")"
  log "OK: semillas aplicadas. Volvé a correr 'actualizar' para confirmar que la segunda pasada no cambia nada."
}

# ---------------------------------------------------------------- promover
# Aplica las mejoras a la base ORIGINAL. Es la única orden que escribe en ella.
cmd_promover() {
  docker inspect "$ORIGEN_CONT" >/dev/null 2>&1 || err "no existe el contenedor $ORIGEN_CONT"
  VOL_ORIGEN="${ORIGEN_VOL:-$(volumen_de "$ORIGEN_CONT")}"
  [ -n "$VOL_ORIGEN" ] || err "no pude detectar el volumen /data de $ORIGEN_CONT; pasá ORIGEN_VOL"

  log "1/3 respaldo obligatorio antes de escribir en $ORIGEN_CONT"
  PROTEGER_ORIGEN=1
  trap restaurar_original EXIT
  docker stop "$ORIGEN_CONT" >/dev/null
  DESTINO=$(tomar_respaldo "-pre-promocion")
  docker start "$ORIGEN_CONT" >/dev/null
  PROTEGER_ORIGEN=0
  esperar_neo4j "$ORIGEN_CONT"

  ANTES=$(huella "$ORIGEN_CONT")
  log "2/3 aplicando las 8 semillas sobre el original (huella antes: $ANTES)"
  aplicar_semillas "$ORIGEN_CONT" "${PREFIJO_LOG:-mejoras_original}"

  log "3/3 verificación"
  log "huella después: $(huella "$ORIGEN_CONT")  |  $(resumen "$ORIGEN_CONT")"
  comprobar_conocimiento "$ORIGEN_CONT"
  log "respaldo previo en: $DESTINO"
}

# --------------------------------------------------------------- verificar
cmd_verificar() {
  echo "--- original ($ORIGEN_CONT) ---"
  huella "$ORIGEN_CONT"; echo "nodos/relaciones: $(resumen "$ORIGEN_CONT")"
  echo "--- copia ($COPIA_CONT) ---"
  huella "$COPIA_CONT"; echo "nodos/relaciones: $(resumen "$COPIA_CONT")"
  echo "--- conocimiento en la copia ---"
  comprobar_conocimiento "$COPIA_CONT"
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
  promover)   cmd_promover ;;
  verificar)  cmd_verificar ;;
  detener)    cmd_detener ;;
  *) echo "uso: sh scripts/base_mejoras.sh {respaldo|copiar|actualizar|promover|verificar|detener}" >&2; exit 2 ;;
esac
