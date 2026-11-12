# Valuación SM2 resuelta en Neo4j

La valuación comercial de SM2 ya no decide en Python: una consulta Cypher explícita resuelve el
componente, la RAM tasada, el año, el soporte de Windows 11, la antigüedad, la caída a la
generación anterior (R2.4) y el estado de la tasación. Python valida tipos, compone la entrada y
redacta mensajes; el LLM solo extrae hechos. Responde al límite S9: «el LLM no tiene que tomar
ninguna decisión de negocio, si no que todo lo debe hacer la inferencia de Neo4j».

No cambia ninguna política de valuación ni la calibración: la misma consulta que antes valuaba
con factores del grafo ahora también decide con esos factores.

El riesgo de `SM2-RIE` que alimenta `SM2-DEM` también sale cuantizado desde Neo4j. Se conserva
la secuencia previa —centroide a cuatro decimales en Cypher y cuantización IEEE-754 a dos—,
pero ya no se ejecuta el segundo redondeo en Python. Se reutiliza la utilidad numérica Cypher
de `inferencia_sm3.py`, sin incorporar criterios nuevos ni cambiar la categoría de riesgo.
El redondeo del valor de mercado que sólo se muestra al usuario sigue siendo formato de salida.

## Camino rápido

```bash
# 1. Valuación contra un grafo aislado (nunca el de trabajo)
EVALTIC_NEO4J_PRUEBAS_URI=bolt://127.0.0.1:17687 PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -m unittest discover -s app/tests -p test_sm2_neo4j.py -v

# 2. Regresión offline completa (sin red ni grafo)
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s app/tests -v
```

Sin `EVALTIC_NEO4J_PRUEBAS_URI` las pruebas de grafo se omiten; nunca se conectan al Neo4j de
trabajo. El grafo de pruebas se lee, no se modifica.

## Qué resolvía Python y dónde vive ahora

| Decisión de negocio | Antes | Ahora |
|---|---|---|
| Qué `:Procesador` corresponde | Cypher | Cypher (sin cambios) |
| Qué `:Linea` y `:GrupoLinea` | Cypher | Cypher (sin cambios) |
| RAM que se tasa (aviso → ampliación de SM1 → CE `ram_objetivo`) | Python | Cypher (`ram_final`, `ram_origen`) |
| Año del equipo (aviso → año del procesador) | Python | Cypher (`anio`, `anio_origen`) |
| Soporte de Windows 11 (aviso → procesador → año ≥ CE `anio_min_w11`) | Python | Cypher (`soporte_w11`, `w11_origen`) |
| Antigüedad contra CE `anio_referencia` | Python | Cypher (`antiguedad`) |
| R2.4: valor de la generación anterior | valor en Cypher, decisión en Python | Cypher (`valor_origen`, `generacion_anterior`) |
| Valor de mercado y VMA | Cypher | Cypher (sin cambios de fórmula) |
| Estado: `Tasado` / `Verificacion_pendiente` / `ConocimientoFaltante` | Python | Cypher (`estado`, `motivo_clave`) |

## Qué sigue en Python, y por qué

| Responsabilidad | Dónde | Motivo |
|---|---|---|
| Validar tipos y formatos de los hechos (RAM, año, booleano de W11) | `_ram_informada_para_grafo`, `_anio_informado_para_grafo`, `_hechos_procesador_sm2` | Es la capa que el plan asigna a Python: no cambia el hecho, detecta que falta o está mal tipado, con el mismo contrato que la versión anterior. |
| Normalizar escritura del procesador (`5500 U` → `5500u`, `13ª` → `13a`) | `_normalizar_texto_procesador` | Variante de escritura del aviso, no conocimiento experto. |
| Componer el texto de búsqueda (marca + modelo + aviso) | `ejecutar_motor_sm2` | Transporte de hechos, sin valor de negocio. |
| Redactar mensajes y traza a partir de la causa que devolvió el grafo | `_pendiente_valuacion_sm2`, `_mensaje_conocimiento_faltante_sm2` | Formato: el grafo elige la causa (`motivo_clave`), Python la escribe en español. |
| Encadenar las difusas SM2-RIE y SM2-DEM | `ejecutar_motor_sm2` | Las reglas, conjuntos y centroides viven en Cypher; Python solo pasa los valores resueltos. |

## Contrato de la consulta

- `inferir_valuacion_sm2_cypher(procesador, modelo, texto, ram_informada, ram_ampliada,
  hdd_a_ssd, anio_informado, soporte_w11_informado, traza=None, ram_final_fijada=None,
  aplicar_politica_ram=True)` ejecuta `_CONSULTA_VALUACION_SM2` y devuelve el mapa resuelto con
  la procedencia de cada dato, los valores de los criterios (`criterios`) y `criterios_usados`.
- `consultar_mercado_componentes(procesador, texto, ram_informada, ram_final, hdd_a_ssd)` conserva
  la firma y las nueve claves de siempre; fija el factor de RAM con `ram_final` y no decide estado.
- `motivo_clave` es una enumeración estable: `procesador_no_informado`, `procesador_desconocido`,
  `linea_desconocida`, `ram_informada_desconocida`, `ram_tasada_desconocida`,
  `procesador_sin_muestras`, `anio_desconocido`.
- La consulta solo lee: no crea, modifica ni borra nodos ni relaciones. Una prueba falla si
  aparece una cláusula de escritura en su texto.

### Procedencia de criterios: solo lo aplicado

La consulta informa en `criterios_usados` únicamente los criterios que la política evaluó, y el
adaptador copia a `traza["criterios_usados"]` solo esos, con la forma que produce `CE()`:

| Criterio | Se registra cuando |
|---|---|
| `ram_objetivo` | El aviso trae procesador o modelo consultable (la RAM tasada depende de él). |
| `min_muestras_mercado` | Hay conocimiento completo y se evalúa el precio de referencia del procesador. |
| `anio_referencia` | La valuación queda tasada (hay año para la antigüedad). |
| `descuento_negociacion` | La valuación queda tasada (entra en el VMA). |
| `reval_ssd` | La valuación queda tasada y SM1 planifica el cambio a SSD. |
| `anio_min_w11` | La valuación queda tasada y el soporte de Windows 11 se resuelve por año. |

Registrar un criterio que la política no evaluó inflaría `criterios_pendientes` y podría convertir
una decisión `Firme` en `Provisional` cuando el experto valide solo una parte del conocimiento. Las
pruebas `EstadoValidacionTest` mezclan metadatos de validación con `mock` (el grafo no se modifica)
para comprobar que un criterio no aplicado no cambia el estado y que uno aplicado sin validar sí
lo deja provisional.

### Hechos inválidos: mismo contrato que antes

| Hecho | Comportamiento |
|---|---|
| Año ilegible (`'veinte'`, lista, diccionario) | Corta con el mismo error de antes (`ValueError`/`TypeError`): no se reemplaza por el año del procesador. |
| Año numérico textual o decimal (`'2016'`, `2016.5`) | Se transporta como número; la antigüedad sale de la resta contra CE `anio_referencia`. |
| RAM que `int()` no acepta (`'16.0'`, `'ocho'`, lista) | Se considera no informada: RAM de referencia y dato inferido, nunca una capacidad redondeada. |
| RAM booleana (`True`) | Se convierte como antes (`1 GB`) y da error de conocimiento, igual que la versión anterior. |

En una entrada con año inválido la valuación corta antes de consultar el catálogo, así que la
traza queda más corta que en la versión anterior (que consultaba y después fallaba). El error
público es el mismo y no se emite tasación ni recomendación.

## Invariantes conservadas y su evidencia

Las pruebas de `app/tests/test_sm2_neo4j.py` usan hechos controlados y valores esperados
congelados: VMA `714000` (16 GB), `661000` (RAM de referencia), `595000` (4 GB sin ampliar),
`706000` (ampliación + SSD), `797000` (R2.4 a la generación anterior) y `591000` (W11 falso por
año). Los estados cubren tasación, pendiente por año, pendiente por muestras, procesador no
informado, procesador deducido del modelo y los tres errores de conocimiento.

El diferencial contra la base anterior (mismos hechos controlados sobre el mismo grafo, comparando
resultado, error, stdout, stderr y código de salida) es idéntico en resultados, trazas, reglas,
criterios registrados y en la consulta pública de componentes: cero diferencias. También coinciden
con la base los 19 casos de hechos inválidos (año y RAM como `None`, texto inválido, lista,
diccionario, texto decimal, decimal y booleano) y siete escenarios de validación mezclada
(`Firme`/`Provisional` y `criterios_pendientes`).

## Qué no cambia

Políticas, umbrales, calibración, corpus, prompts y el contrato del LLM de entrada. No se agrega
ontología ni motor de reglas: se reutilizan `:Procesador`, `:Linea`, `:GrupoLinea`,
`:CapacidadRAM`, `:CriterioExperto`, `:ReglaDifusa` y la regla `R2.4` ya cargada. Los valores
siguen siendo provisionales hasta la validación experta.

La ejecución real del corpus de 61 publicaciones y la actualización del grafo de trabajo quedan a
cargo de la integración; esta unidad no las ejecuta ni las reemplaza.

## Actualización TB: fórmula, R2.4 y estado comercial como datos

La etapa `SM2-valuacion` del artefacto
[Grupo_20_PG3_politicas_bloque.cypher](../cypher/Grupo_20_PG3_politicas_bloque.cypher) declara
dos reglas que la valuación consume:

- `SM2-VALUACION` (`rol='formula'`): `escala_redondeo_ars=1000` — la escala a la que se redondea
  el VMA — y qué criterios aplica (`aplica_descuento_negociacion`, `aplica_revalorizacion_upgrade`).
  La consulta los recibe como parámetros; cambiar la escala o desactivar una aplicación cambia el
  VMA sin editar Python.
- `R2.4` (`rol='r24'`): `r24_activo` y `r24_misma_familia`. Con la activación apagada, un
  procesador sin muestras propias ya no toma el valor de la generación anterior y la valuación
  queda `Verificacion_pendiente` por `procesador_sin_muestras`, como corresponde a falta de dato.

La **clasificación del estado** también es una etapa (`SM2-estado`): ocho reglas ordenadas por
`prioridad_inferencia` con su `estado_resultante` y `motivo_resultante`, y nueve condiciones
sobre los hechos que la consulta ya resolvía (procesador, su origen, línea, las tres lecturas de
RAM, valor del procesador y año). La consulta evalúa esos grupos con los mismos comparadores
finitos del resto del bloque y elige la primera regla que se cumple. Cambiar el `campo`, el
operador, la prioridad o el estado resultante en el grafo cambia el estado público; una condición
con un hecho no declarado, dos reglas con la misma prioridad o un manifiesto incompleto cortan la
consulta sin fila y el motor falla con error explícito, nunca con una tasación favorable.

Los valores por defecto reproducen exactamente los siete estados/motivos anteriores y el contrato
de nueve campos del wrapper. La procedencia (`criterios_usados`) sigue derivándose de los hechos
resueltos: registrar la correspondencia hecho→criterio como datos habría sido un agregado
decorativo, así que el conjunto aplicado no cambia. La cuantización de RIE (centroide crudo →
cuatro decimales → IEEE a dos → DEM) conserva su ruta y precisión literales. Detalle, allowlist y
activación en [ejecuciones/politicas_bloque_implementacion.md](ejecuciones/politicas_bloque_implementacion.md).
