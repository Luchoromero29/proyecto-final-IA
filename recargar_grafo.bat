@echo off
REM Borra el grafo y vuelve a ejecutar Grupo_20_PG2_U1_carga.cypher
cd /d "%~dp0"
docker compose run --rm -e RECARGAR=1 neo4j-init
pause
