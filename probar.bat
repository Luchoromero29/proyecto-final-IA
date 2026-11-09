@echo off
REM Corre la bateria de pruebas E2E (5 casos oficiales) dentro del contenedor de la app
cd /d "%~dp0"
docker compose exec app python orquestador_evaltic.py --test
pause
