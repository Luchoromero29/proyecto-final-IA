#!/bin/sh
# Carga la base de conocimiento en Neo4j (bootstrap de base nueva o refresco completo):
#   1) Grupo_20_PG2_U1_carga.cypher       (solo si la base está vacía, o con RECARGAR=1)
#   2) Grupo_20_PG3_mercado.cypher         (siempre; recrea el catálogo de mercado)
#   3) Grupo_20_PG3_diagnostico.cypher     (siempre; sólo agrega conocimiento de diagnóstico SM1)
# OJO: este loader NO es una migración aditiva. Para aplicar sólo el diagnóstico sobre datos de
# trabajo hace falta un procedimiento operador-safe con respaldo verificado (ver
# docs/DIAGNOSTICO_TECNICO.md).
set -e
URI="bolt://neo4j:7687"
AUTH="-u neo4j -p ${NEO4J_PASSWORD:-evaltic2026}"

echo "[init] Esperando a Neo4j en $URI ..."
until cypher-shell -a "$URI" $AUTH "RETURN 1;" >/dev/null 2>&1; do sleep 3; done

CANT=$(cypher-shell -a "$URI" $AUTH --format plain "MATCH (r:ReglaDifusa) RETURN count(r);" | tail -n 1)
if [ "${RECARGAR:-0}" = "1" ] || [ "$CANT" = "0" ]; then
  echo "[init] Cargando Grupo_20_PG2_U1_carga.cypher (reglas difusas actuales: $CANT) ..."
  cypher-shell -a "$URI" $AUTH -f /cypher/Grupo_20_PG2_U1_carga.cypher
else
  echo "[init] La base del PG2 ya está cargada ($CANT reglas difusas); no se recarga (RECARGAR=1 para forzar)."
fi

echo "[init] Cargando/actualizando Grupo_20_PG3_mercado.cypher ..."
cypher-shell -a "$URI" $AUTH -f /cypher/Grupo_20_PG3_mercado.cypher

echo "[init] Cargando/actualizando Grupo_20_PG3_diagnostico.cypher (aditivo, Provisional) ..."
cypher-shell -a "$URI" $AUTH -f /cypher/Grupo_20_PG3_diagnostico.cypher

echo "[init] Contenido del grafo:"
cypher-shell -a "$URI" $AUTH --format plain "MATCH (n) RETURN labels(n)[0] AS tipo, count(*) AS cantidad ORDER BY cantidad DESC LIMIT 15;"
cypher-shell -a "$URI" $AUTH --format plain "MATCH (s:SegmentoMercado) RETURN count(s) AS segmentos; MATCH (m:ModeloReferencia) RETURN count(m) AS modelos; MATCH (c:CostoReparacion) RETURN count(c) AS costos; MATCH (c:CriterioExperto) RETURN count(c) AS criterios; MATCH (p:PatronTexto) RETURN count(p) AS patrones_diagnostico; MATCH (d:Diagnostico) RETURN count(d) AS diagnosticos;"
echo "[init] Listo."
