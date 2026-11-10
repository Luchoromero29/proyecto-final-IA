# Verificación de la rama integrada — 8187583

Rama: `integracion/mejoras-con-pruebas`. Referencia anterior: `59026ec`.
Alcance: revisar integración y ejecutar pruebas; sin corregir código ni cargar Neo4j.

## Integridad del merge

- HEAD integra `59026ec` y `d231ccd` (`origin/main` al verificar).
- Corpus de 61 casos, tres archivos de tests, ejecutor, guía, resumen y logs originales: idénticos a `59026ec`.
- La adaptación NVIDIA que desactiva thinking solo para el host/modelo exactos sigue presente.
- El archivo ajeno `CONTEXTO_Y_MEJORAS_EVALTIC.md` sigue sin seguimiento, sin modificar.
- Las mejoras incluyen R2.4 (referencia de generación anterior), extracción de RAM/procesador y ampliación del catálogo/CSV (333 avisos).

## Suite offline

Comando informado por el verificador:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/alvaro/Universidad/IA/Proyecto/.venv/bin/python -m unittest discover -s app/tests -v
```

Resultado en HEAD: **69 pruebas ejecutadas, 31 errores, salida 1**, 0,328 s.
Este documento resume el handoff del verificador; no es una transcripción de stdout/stderr.

Todos los errores informados son `KeyError: 'valor_proc'`, al ejecutar SM2.
El helper `_mercado_falso` en `app/tests/test_publicaciones_criticas.py` conserva la forma anterior de la consulta, sin `valor_proc` ni `generacion_anterior`. La consulta Cypher real ahora devuelve ambas claves y SM2 consume `valor_proc`.

Esto demuestra una incompatibilidad del fixture con el nuevo contrato de consulta; no demuestra 31 defectos funcionales distintos ni valida la nueva inferencia R2.4. No se modificaron expectativas ni código para ocultar errores.

El verificador informó 69/69 aprobadas con el baseline `59026ec` en scratch y, en otra copia scratch, 69/69 con las dos claves agregadas al fixture. Esa sonda apoya la causa identificada, pero **no es un arreglo aplicado ni una aprobación de HEAD**. El padre confirmó la ausencia de las claves en el fixture y el contrato nuevo en el diff. No repitió la suite.

## Neo4j y corpus real

El contenedor `neo4j-evaltic` está detenido (`Exited (255)`); el verificador informó rechazo de conexión a localhost:7687. El padre confirmó el estado detenido.

- Contenido y vigencia del grafo: **no verificados**. No se afirma que esté desactualizado solo porque cambió el seed del repositorio.
- Preflight conectado y ejecución de los 61 casos reales: **no realizados**.
- No se arrancaron servicios, no se cargó PG3 y no se ejecutó el reset PG2 ni se importó el dump nuevo.
- Los resultados reales anteriores permanecen como baseline histórico; no se atribuyen a este commit.

Para continuar se requiere acordar la adaptación del fixture, levantar Neo4j, comprobar el catálogo y aplicar la carga PG3 solo si resulta necesaria. Una nueva tanda debe tener su propio log y distinguir fallos del producto, expectativas desactualizadas e infraestructura.

## Límites y desvíos del verificador

El verificador informó haber repetido la suite del workspace para enumerar los errores pese a la instrucción de no repetir después de un fallo. Se conserva el fallo; no se justifica ni se reinicia su presupuesto automáticamente.

También informó escrituras temporales fuera del repositorio (`/tmp/pre_probe_hashes.txt` y scratch `/tmp/gpMHe2dP/galwKld9/tmp.p9UyFHR1n4`). No forman parte de la evidencia versionada, y el padre no las leyó ni eliminó. No hubo cambios de fuente, Git, configuración o base de datos por parte del verificador según su handoff, confirmado en el worktree para los archivos del repositorio.

## Estado de cierre

Integración e integridad de la batería comprobadas. Suite offline **no aprobada** y ejecución real **pendiente por los prerrequisitos indicados**. Este informe no constituye aprobación funcional ni revisión nativa. No se hicieron commits ni publicaciones durante esta verificación.
