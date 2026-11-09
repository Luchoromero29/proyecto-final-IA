@echo off
REM Aplica cambios: recarga el grafo (PG2 + catalogo PG3) y reconstruye la app
cd /d "%~dp0"
docker info >/dev/null 2>&1
if errorlevel 1 (
  echo  [ERROR] Abri Docker Desktop y espera a que diga "Engine running".
  pause
  exit /b 1
)
docker compose up -d neo4j
docker compose run --rm -e RECARGAR=1 neo4j-init
docker compose up -d --build app
echo.
echo  Listo. App: http://localhost:8501
pause
