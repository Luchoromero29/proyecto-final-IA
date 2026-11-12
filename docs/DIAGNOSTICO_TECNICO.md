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
| Nueva o reconstruible (pruebas, CI, contenedor desechable) | bootstrap completo del entorno aislado, en el orden PG2 → PG3 mercado → diagnóstico → políticas SM1 | Deja la base lista desde cero; es el camino usado en la preparación aislada de B2 y de P2a. |
| Datos de trabajo, refresco completo | `actualizar.bat` / `docker compose run --rm neo4j-init` | **No es aditivo**: rehace el catálogo de mercado. Es una carga sobre datos de trabajo y requiere autorización específica y respaldo verificado. |
| Datos de trabajo, sólo B2 y condiciones de SM1 | **pendiente de un procedimiento operador-safe** | Los archivos aditivos son `cypher/Grupo_20_PG3_diagnostico.cypher` y `cypher/Grupo_20_PG3_politicas_sm1_acciones.cypher`; su aplicación a la base de trabajo la decide y ejecuta el operador con respaldo previo. Este documento no incluye credenciales ni comandos de conexión para agentes. |
| Grafo aislado de pruebas | `scripts/aplicar_politicas_sm1_pruebas.py` | Cargador **sólo para el scratch** marcado `EntornoPruebas {id:'mejoras-evaltic'}`: compara la proyección protegida, valida el delta exacto y exige segunda aplicación sin cambios. No es el procedimiento de despliegue. |

Si el conocimiento nuevo falta, el motor se detiene con un error de base de conocimiento al
diagnosticar: no planifica reparaciones de menos ni convierte el silencio en costo cero. Esa
misma guarda cubre la representación de las políticas: si el manifiesto de la etapa de acciones
falta, se repite, o una condición quedó incompleta, el grafo devuelve el motivo concreto y el
motor lo informa como `ErrorConocimiento`; nunca como un plan vacío.

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
pantalla/teclado dañados, cargador ausente y mano de obra (no cuenta como intervención). Cada
una de esas condiciones —campo, ámbito, comparador, operando literal o criterio enlazado, grupo
y categoría difusa— es **dato del grafo**: `Regla-[:REQUIERE {grupo}]->Condicion`, con `=`, `<`,
`ausente` y `presente` como comparadores finitos, OR dentro de un grupo y AND entre grupos. Las
reglas de la etapa están declaradas en `(:VersionPoliticas {etapa:'SM1-acciones'})`, así que
cambiar una condición (o su vínculo `OBLIGA`) cambia el plan sin editar Python. Las caídas
de frecuencia sintéticas también son criterios del grafo (`CE-31` 5 %, `CE-32` 20 %), ambos
Provisionales y con fuente; la política térmica en sí la revisa B5.

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

`cypher/Grupo_20_PG3_politicas_sm1_acciones.cypher` (P2a) es otro artefacto aditivo e idempotente,
separado del anterior. Agrega la representación de las condiciones de las acciones de SM1:

| Nodos / enlaces | Para qué |
|---|---|
| `(:VersionPoliticas {id:'VP-SM1-ACCIONES', etapa:'SM1-acciones', activa:true})` | Manifiesto técnico de la etapa: `ids_requeridos`, `INCLUYE` a las ocho reglas de acción y cardinalidad declarada (`condiciones`, `criterios`, `obligaciones_requeridas`). No es validación experta. |
| `(:Condicion {id, campo, ambito, operador, valor})` | 9 condiciones (`CND-SM1-*`); `ambito` es `hechos` o `campos`, y el comparador es `=`, `<`, `ausente` o `presente`. |
| `(:Regla)-[:REQUIERE {grupo}]->(:Condicion)` | 9 enlaces; batería y temperatura usan dos grupos (AND), el resto uno. |
| `(:Condicion)-[:USA_CRITERIO]->(:CriterioExperto)` | 2 vínculos: `CND-SM1-BAT-CRISP-SALUD`→`CE-01` y `CND-SM1-RAM-ACCION-RAM`→`CE-27`. |
| `(:ReglaDifusa)-[:OBLIGA {etapa, campo}]->(:CostoReparacion)` | 11 relaciones existentes que reciben su etapa y el hecho de la categoría (`categoria_bat` / `categoria_ter`), sin tocar `categorias` ni `orden`. |

`cypher/Grupo_20_PG3_politicas_sm1_estado.cypher` (P2c) es otro artefacto aditivo e idempotente,
separado de los anteriores. Agrega la consecuencia de estado de las tres situaciones de bloqueo de
SM1 sobre las reglas que ya las aplican, sin tocar `estado`, `estado_validacion` ni `version`:

| Propiedad | Para qué |
|---|---|
| `(:Regla {id:'R1.1'}).estado_resultante = 'Inviable'` | Estado de la falla física insalvable (aviso o diagnóstico irreparable confirmado). |
| `(:Regla {id:'R3.3c'}).estado_resultante = 'VerificacionPendiente'` | Estado de la evidencia que exige verificación del operador. |

El vocabulario es el que ya publica el motor (`Viable`, `Inviable`, `VerificacionPendiente`,
`ConocimientoFaltante`): es contrato de salida, no política experta nueva. La consulta lee esas dos
propiedades sólo para la regla que aplica y conserva la precedencia del `CASE` (inviable →
conocimiento faltante → irreparable → pendiente → viable); si la propiedad falta o no es uno de los
cuatro estados publicados, la configuración se informa como conocimiento faltante, nunca como
viabilidad. Ni el seed diagnóstico ni P1 ni P2a se modifican, y la segunda aplicación devuelve cero
cambios.

Ni el seed diagnóstico ni P1 se modifican: el primero vuelve a `SET` sus propias propiedades de
`Regla`, y las que P2a no usa (`campo`, `valor`, `tarea`, `orden`) siguen protegidas. La segunda
aplicación del artefacto devuelve cero cambios.

## Límites conocidos

- El catálogo de síntomas y los protocolos de verificación siguen pendientes de validación experta.
- El reconocimiento de texto no interpreta negaciones generales (eso es B3): sólo descarta
  descripciones positivas explícitas.
- La política térmica no se recalibró (B5) y las sondas del corpus no se convierten en aceptación.
- P2a representa **sólo** las condiciones de las acciones y su vínculo con las categorías difusas.
  P2c representa **sólo** el estado resultante de R1.1 y R3.3c. Las precedencias de evidencia (P2b),
  la construcción del plan, la selección de costos, el canal del operador y el resto de la selección
  de estado siguen en la consulta; los importes se leen del grafo. No se declara terminada SM1.
- Una configuración de políticas inválida se informa como error de conocimiento con su motivo; no
  hay caché ni plan de respaldo en Python.
- El corpus y los logs históricos no se modificaron.

## Checklist

- [ ] La base donde se evalúa tiene cargado `Grupo_20_PG3_diagnostico.cypher` y, con el procedimiento que corresponda a su tipo, `Grupo_20_PG3_politicas_sm1_acciones.cypher` (aparecen `patrones_diagnostico`, `diagnosticos` y el manifiesto `VP-SM1-ACCIONES`) y `Grupo_20_PG3_politicas_sm1_estado.cypher` (`estado_resultante` en `R1.1` y `R3.3c`).
- [ ] La misma base tiene aplicado `Grupo_20_PG3_politicas_bloque.cypher` (manifiestos `VP-SM3-MARGEN`, `VP-SM3-CALCULO`, `VP-SM2-VALUACION`, `VP-SM2-ESTADO`, `VP-SM0-CLASIFICACION`). Sin esa etapa, SM3, la valuación SM2 y la clasificación Firme/Provisional fallan con error explícito en lugar de usar valores del código.
- [ ] `test_diagnostico_neo4j.py`, `test_sm1_neo4j.py` y `test_politicas_sm1_neo4j.py` pasan contra el Neo4j aislado.
- [ ] La suite offline completa pasa.
- [ ] Una publicación con `no prende` queda en `VerificacionPendiente` y su dictamen dice VERIFICAR.

## Siguiente paso

Revisar con el experto el catálogo de síntomas y los protocolos de verificación antes de convertir
estas reglas Provisionales en aceptación (ver B2 y B5 en [el plan](PLAN_MEJORAS_EVALTIC.md)).
