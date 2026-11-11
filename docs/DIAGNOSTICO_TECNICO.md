# Diagnóstico técnico de SM1 inferido en Neo4j (B2)

Un aviso que afirma **no prende**, **no carga** o **se apaga sola** ya no termina en una compra
favorable ni en un descarte por inviabilidad: queda **en verificación técnica pendiente** hasta que
un operador aporte un diagnóstico confirmado. Las reparaciones, los umbrales y los costos de SM1 se
infieren en consultas Cypher; Python sólo valida los hechos, coordina el flujo y muestra la traza.

Estado del conocimiento: **Provisional**. No está validado por el experto (Matías Romero) y cada
nodo declara su fuente. El catálogo de tres síntomas no es exhaustivo: ampliarlo es una decisión
experta pendiente, no una lista improvisada en Python.

## Ruta rápida

1. Comprobar la inferencia en el Neo4j aislado de pruebas (no usa el grafo de trabajo ni lee `.env`):

   ```bash
   EVALTIC_NEO4J_PRUEBAS_URI=bolt://127.0.0.1:17687 PYTHONDONTWRITEBYTECODE=1 \
     /home/alvaro/Universidad/IA/Proyecto/.venv/bin/python -m unittest discover -s app/tests \
     -p test_diagnostico_neo4j.py -v
   ```

   Las pruebas aplican `cypher/Grupo_20_PG3_diagnostico.cypher` una vez con `MERGE` (sólo sus
   identificadores nuevos) y lo verifican contra un grafo reconstruible, nunca contra la base de
   trabajo.

2. Aportar la verificación del operador cuando exista (ver más abajo).

3. Para que el motor funcione sobre una base, el conocimiento nuevo tiene que estar cargado. Cómo
   aplicarlo depende del tipo de base: ver la sección siguiente.

## Cómo se aplica el conocimiento nuevo (migración)

`cypher/Grupo_20_PG3_diagnostico.cypher` es **aditivo e idempotente** (`MERGE`, sin borrar nada),
pero **el loader completo no es aditivo**: `scripts/cargar_grafo.sh` (lo que ejecutan
`actualizar.bat` y `docker compose run --rm neo4j-init`) también vuelve a correr
`Grupo_20_PG3_mercado.cypher`, que **recrea el catálogo de mercado** (líneas, procesadores, RAM,
avisos y sus relaciones). Por eso no sirve como migración de sólo B2 sobre datos de trabajo.

| Base | Procedimiento | Efecto |
|---|---|---|
| Nueva o reconstruible (pruebas, CI, contenedor desechable) | bootstrap completo del entorno aislado, en el orden PG2 → PG3 mercado → diagnóstico | Deja la base lista desde cero; es el camino usado en la preparación aislada de B2. |
| Datos de trabajo, refresco completo | `actualizar.bat` / `docker compose run --rm neo4j-init` | **No es aditivo**: rehace el catálogo de mercado. Es una carga sobre datos de trabajo y requiere autorización específica y respaldo verificado. |
| Datos de trabajo, sólo B2 | **pendiente de un procedimiento operador-safe** | El archivo aditivo es `cypher/Grupo_20_PG3_diagnostico.cypher`; su aplicación a la base de trabajo la decide y ejecuta el operador con respaldo previo. Este documento no incluye credenciales ni comandos de conexión para agentes. |

Si el conocimiento nuevo falta, el motor se detiene con un error de base de conocimiento al
diagnosticar: no planifica reparaciones de menos ni convierte el silencio en costo cero.

## Qué hace el motor con cada situación

| Situación en el aviso | Tratamiento inferido en el grafo |
|---|---|
| Síntoma afirmado sin diagnóstico (`no prende`, `no carga`, `se apaga sola`) | `VerificacionPendiente` (regla `R3.3c`): no se tasa, no se decide, no se asume reparación cero. |
| Falla informada que ningún patrón del grafo reconoce | `VerificacionPendiente`: se pide verificar y completar el conocimiento. |
| Síntoma reconocido con reparación conocida (pantalla, teclado, batería, disco, térmico, cargador) | Se aplica su intervención y el costo de `:CostoReparacion`. |
| Descripción positiva o aviso sin fallas (`pantalla impecable`, `no tiene fallas`) | No genera falla ni reparación. |
| Daño irreversible (`no da video`, quemado, en corto, perforado, sulfatación) | `R1.1` → `DescartarPorInviabilidad` (`R3.2`), con la semántica que ya tenía el motor. |
| Diagnóstico irreparable confirmado por el operador | `R1.1` → `DescartarPorInviabilidad`. |
| Diagnóstico desconocido para el grafo | Error explícito de conocimiento faltante; no se inventa una reparación. |

Los hechos estructurados conservan sus políticas: salud y ciclos de batería (difusa `SM1-BAT` o
crisp `R1.2`), temperatura y throttling (difusa `SM1-TER`), RAM bajo `CE ram_objetivo`, HDD → SSD,
pantalla/teclado dañados, cargador ausente y mano de obra (no cuenta como intervención). Las caídas
de frecuencia sintéticas pasaron de constantes de Python a criterios del grafo (`CE-31` 5 %,
`CE-32` 20 %), ambos Provisionales y con fuente; la política térmica en sí la revisa B5.

La consulta SM1 con su salida detallada por defecto también distingue un costo desconocido de
un costo conocido en cero: muestra `Plan: pendiente de verificación | Costo: sin determinar`
o `Plan: no disponible por conocimiento faltante | Costo: sin determinar`, según el estado ya
inferido. Un equipo viable sin intervenciones conserva `Plan: ninguna reparación | Costo: $0 ARS`.

## Verificación del operador

La guarda sólo se libera con evidencia **del operador**, separada del aviso y de lo que produzca el
LLM. La forma es un objeto con fuente declarada y diagnósticos confirmados:

```python
evaluar_publicacion_integral(texto, verbose=False, verificacion_tecnica={
    "fuente": "Revisión en persona en el taller, 12/11/2026",
    "diagnosticos": ["bateria"],
})
```

- **API pública**: `evaluar_publicacion_integral`, `consultar_sm1` y `asistente_evaltic` aceptan
  el argumento opcional `verificacion_tecnica`. Sin fuente, o sin diagnósticos, no libera nada.
- **Interfaz web** (`app/app_web.py`): bloque "Verificación técnica del operador", con fuente y
  diagnósticos separados por coma.
- **CLI**:

  ```bash
  python app/orquestador_evaltic.py --verificacion "revisión en persona en el taller" \
    --diagnostico bateria "Notebook HP 15, $100.000, no carga."
  ```

Un campo del aviso o del LLM (`diagnostico_confirmado`, `aprobado`, `decision`, `verificacion_tecnica`
dentro de la extracción) **nunca** levanta la guarda: sólo se lee el argumento del operador.

Con evidencia válida, la reparación y el costo salen del grafo: `:Diagnostico -[:SE_REPARA_CON]->
:CostoReparacion`. No se deduce cargador ni batería a partir de `no carga`.

## Conocimiento nuevo en el grafo

`cypher/Grupo_20_PG3_diagnostico.cypher` es aditivo e idempotente (`MERGE`) y no reescribe criterios,
costos ni reglas existentes. Crea:

| Nodos / enlaces | Para qué |
|---|---|
| `(:Falla:FallaSintoma)` `FS-NO-PRENDE`, `FS-NO-CARGA`, `FS-SE-APAGA-SOLA` | Síntomas acordados, con `ACTIVA`→`R3.3c`. |
| `(:PatronTexto)` `PT-CAT-*`, `PT-SIN-*`, `PT-INT-*`, `PT-DESC-*` | Palabras clave que antes decidían en Python: inviabilidad, síntomas, reparaciones y descripciones positivas. |
| `(:Diagnostico)` `DIA-*` | Diagnósticos que puede confirmar el operador, con su reparación y costo. |
| `(:Regla)` `R3.3c`, `SM1-*-ACCION` | Política de verificación pendiente y acciones de SM1 con su orden. |
| `(:ReglaDifusa)-[:OBLIGA]->(:CostoReparacion)` | Categoría difusa que obliga a intervenir (batería `Obligatoria`, térmico `Obligatoria`/`Recomendada`). |
| `(:CriterioExperto)` `CE-31`, `CE-32` | Caídas de frecuencia sintéticas, Provisionales y con fuente. |

## Límites conocidos

- El catálogo de síntomas y los protocolos de verificación siguen pendientes de validación experta.
- El reconocimiento de texto no interpreta negaciones generales (eso es B3): sólo descarta
  descripciones positivas explícitas.
- La política térmica no se recalibró (B5) y las sondas del corpus no se convierten en aceptación.
- El corpus y los logs históricos no se modificaron.

## Checklist

- [ ] La base donde se evalúa tiene cargado `Grupo_20_PG3_diagnostico.cypher` con el procedimiento que corresponda a su tipo (aparecen `patrones_diagnostico` y `diagnosticos`).
- [ ] `test_diagnostico_neo4j.py` y `test_sm1_neo4j.py` pasan contra el Neo4j aislado.
- [ ] La suite offline completa pasa.
- [ ] Una publicación con `no prende` queda en `VerificacionPendiente` y su dictamen dice VERIFICAR.

## Siguiente paso

Revisar con el experto el catálogo de síntomas y los protocolos de verificación antes de convertir
estas reglas Provisionales en aceptación (ver B2 y B5 en [el plan](PLAN_MEJORAS_EVALTIC.md)).
