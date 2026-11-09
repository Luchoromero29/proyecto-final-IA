@echo off
REM EvalTIC - levanta todo el entorno local (Neo4j + carga del grafo + app)
cd /d "%~dp0"

docker info >nul 2>&1
if errorlevel 1 (
  echo.
  echo  [ERROR] Docker Desktop no esta corriendo.
  echo  Abrilo desde el menu Inicio, espera a que diga "Engine running" y volve a ejecutar este archivo.
  echo.
  pause
  exit /b 1
)

docker compose up -d --build
if errorlevel 1 (
  echo.
  echo  [ERROR] Fallo docker compose. Revisa el mensaje de arriba.
  pause
  exit /b 1
)
echo.
echo  App:            http://localhost:8501
echo  Neo4j Browser:  http://localhost:7474   (usuario neo4j / clave evaltic2026)
echo.
echo  Estado de los contenedores:
docker compose ps
pause
