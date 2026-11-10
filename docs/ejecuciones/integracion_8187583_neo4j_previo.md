# Estado del grafo antes de actualizar la integración

Rama: `integracion/mejoras-con-pruebas`. Fixture actualizado en `3f94304`.
**El grafo está accesible pero todavía contiene el catálogo anterior. No se ejecutó la recarga.**

## Comprobaciones realizadas

- Contenedor existente `neo4j-evaltic`, volumen confirmado `proyecto-ia-final_neo4j_data`.
- Arranque mediante `docker start neo4j-evaltic`, sin ejecutar `neo4j-init` ni recrear contenedores/volúmenes.
- Espera de health con límite de 90 segundos: salida 0 en 19 segundos, healthy.
- Inventario con consultas `MATCH` vía `cypher-shell`: salida 0. Sin modificaciones del grafo.

| Dato observado | Valor |
|---|---:|
| AvisoMercado | 289 |
| ML-333 | 0 |
| Avisos con ID ajeno al prefijo ML- | 0 |
| Procesador | 83 |
| Procesadores con valor de referencia | 18 |
| Linea | 45 |
| Linea XPS | 0 |
| CapacidadRAM | 11 |
| Criterio min_muestras_mercado | 5, v2 |
| Regla R2.4 | 1 |
| Catálogo legacy SegmentoMercado/ModeloReferencia/GeneracionProcesador | 0 |

Que exista R2.4 no prueba que la ampliación del catálogo esté aplicada. El CSV del código integrado
contiene 333 avisos; faltan los nuevos en la base. No se demuestra ausencia de ediciones manuales
solo porque todos los IDs presentes empiecen por ML-.

También se comprobó conectividad por la interfaz del ejecutor:

```text
PYTHONDONTWRITEBYTECODE=1 /home/alvaro/Universidad/IA/Proyecto/.venv/bin/python scripts/probar_publicaciones.py --verificar
LLM: openai / nvidia/nemotron-3.5-lightning-30b-a3b / integrate.api.nvidia.com
Catálogo PG3: Procesador=83 (con precio=18), Linea=45, CapacidadRAM=11
Servicios listos. No se ejecutó ningún caso (--verificar).
Salida: 0
```

Este preflight no prueba disponibilidad remota del proveedor ni vigencia del catálogo.

## Operación destructiva detectada — no ejecutada

`cypher/Grupo_20_PG3_mercado.cypher` no es una migración aditiva:

- Borra todas las `Linea` con sus relaciones y reconstruye las del script (aproximadamente línea 222).
- Borra todos los `AvisoMercado` y los vuelve a cargar desde el CSV (aproximadamente línea 306).
- Reinicia/recalibra precios de procesadores y factores de líneas/grupos.
- Sobrescribe costos y atributos del catálogo; puede reemplazar ajustes manuales.
- También contiene eliminación de catálogo legacy, aunque actualmente el conteo observado es cero.

**`RECARGAR=1` no es la forma de cargar solo PG3:** el loader ejecuta antes PG2 con un borrado
total. Incluso sin esa opción puede ejecutar PG2 si no encuentra reglas difusas. Por eso no se
invocó el loader. Tampoco se ejecutó un `docker compose up` general, que puede disparar init,
ni se importó el dump versionado.

## Decisión pendiente

El usuario autorizó actualizar y pidió detenerse antes de cualquier operación destructiva.
Se solicita autorización específica para respaldar/verificar el estado actual y ejecutar
únicamente PG3, aceptando la reconstrucción de líneas/avisos y sus recalibraciones/sobrescrituras.
El reset PG2 y la importación del dump seguirían excluidos.

Suite offline: 71/71 aprobadas (informe del fixture separado). Corpus real: **no ejecutado**;
se espera resolver la actualización para evitar presentar resultados del grafo anterior como
si correspondieran al código y conocimiento más recientes. Los logs originales se preservan.

## Incidente de permisos resuelto

Al arrancar, la imagen cambió `datos/` y su CSV a propietario `7474:7474`, modo `700`, causando
`Permission denied` en Git. Se restauraron exclusivamente esas dos rutas al usuario local
`1000:1000`, directorio `755` y CSV `644`, sin cambios de contenido ni operaciones recursivas.
`stat`, `git diff --check` y `git status` confirmaron la recuperación; solo quedó el archivo
ajeno sin seguimiento. La recarga de PG3 sigue sin ejecutarse.
