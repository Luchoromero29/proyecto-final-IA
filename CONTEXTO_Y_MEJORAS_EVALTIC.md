# EvalTIC: contexto del proyecto y mejoras para portar a otro repositorio

> **Documento histórico (9/11/2026).** Nació como handoff para portar la adaptación del cliente
> LLM —OpenRouter/Nemotron, presupuesto de salida, validación de respuesta y razonamiento
> desactivado— a otra versión del proyecto. Las secciones 8 a 12 son el núcleo vigente, con las
> correcciones marcadas *[actualizado 13/11/2026]* donde el código cambió después.
> Resumen de esos cambios: el cliente hoy también desactiva el razonamiento por la vía propia de
> NVIDIA (`chat_template_kwargs.enable_thinking=false`), usa `temperature 0.1` y
> `app/tests/test_llm_client.py` tiene **34** pruebas, no 10.
> Lo que se hizo después y **este documento no refleja**:
>
> - el diagnóstico B2 en el grafo, con criterios expertos **CE-01 a CE-32** (acá se mencionan CE-01 a CE-20);
> - las políticas representadas en Neo4j: márgenes, R3.7, R3.8, valuación SM2 y clasificación SM0;
> - las correcciones mínimas: dominio y precio, bloqueo contextual, temperatura y síntoma sin diagnóstico;
> - el corpus de 61 casos críticos y su ejecutor: 55 expectativas automáticas y 6 sondas;
> - `scripts/base_mejoras.sh` (respaldo, copia y promoción de la base) y `scripts/reporte_casos.py`.
>
> **Estado vigente:** `docs/ESTADO_CONSOLIDADO_MEJORAS.md`. **Resultado por caso:**
> `docs/PRUEBAS_PUBLICACIONES.md`. **Puesta en marcha:** `README.md` y `LEVANTAR.md`.

Este documento reúne la exploración de los entregables académicos, las contradicciones encontradas y las mejoras implementadas en una copia de PG3. Su destinatario es un agente que trabajará sobre **otra versión de la aplicación**, creada por los compañeros del grupo.

**Objetivo del traspaso:** adaptar la conexión con OpenRouter, los presupuestos de salida, las validaciones de respuesta y la desactivación del razonamiento. **No sobrescribir la otra versión ni cambiar las reglas del sistema experto.**

> Estado comprobado: 10 pruebas offline correctas; extracción y síntesis probadas contra Nemotron con cero tokens de razonamiento. No se verificó una corrida completa de Streamlit + Neo4j + todos los motores desde esta sesión.

## 1. Inicio rápido para el agente del nuevo repositorio

1. Leer este documento, en especial las secciones 8 a 12.
2. Explorar la arquitectura real del nuevo repositorio y localizar sus equivalentes.
3. Separar lo ya implementado acá de las propuestas de generalización.
4. Portar cambios mínimos con pruebas primero; conservar las reglas financieras.
5. Informar qué se verificó offline, qué se probó con servicios reales y qué sigue sin verificar.

### Prompt sugerido para acompañar este archivo

```text
Trabajás en otra versión de EvalTIC. Leé CONTEXTO_Y_MEJORAS_EVALTIC.md.
Primero explorá este repositorio: entrypoints, cliente LLM, configuración, prompts,
pipeline, reglas/motores, Neo4j, UI y tests. Presentá un mapa de equivalencias.

Adaptá las mejoras realmente implementadas en la copia documentada:
- Conexión OpenRouter mediante el protocolo compatible con OpenAI y configuración.
- Presupuesto suficiente de salida; contemplar extracción, estimación y síntesis.
- Desactivación explícita del razonamiento en modelos/proveedores compatibles.
- Validación de respuestas vacías, incompletas y con estructura inválida.

No copies los archivos del otro proyecto sobre este. No cambies reglas de negocio,
umbrales, catálogos ni fórmulas financieras para hacer coincidir un ejemplo.
Conservá el comportamiento de los proveedores y modelos que no son objetivo.

Escribí pruebas offline sobre el cliente público antes de corregirlo. No inventes
JSON, no uses reasoning como respuesta y no agregues reintentos silenciosos ni
fallbacks pagos. No leas ni publiques credenciales innecesariamente.

Las opciones genéricas de configuración sugeridas en el documento NO existen aún
en la copia de referencia: no las describas como implementadas. Si proponés una
configuración más general, explicá su alcance y su compatibilidad real.

Las llamadas a APIs reales y las pruebas que carguen o modifiquen Neo4j requieren
la autorización vigente del operador en esta sesión; este archivo no la concede.
Entregá cambios revisables, resultados de pruebas y límites de la verificación.
```

## 2. Fuentes y criterio de versiones

### Directorios de referencia

- **Documentación académica original, no modificada:**
  `/home/alvaro/Documents/Universidad/5to Año/Inteligencia Artificial/Proyecto`
- **Copia de ejecución con las mejoras de esta sesión:**
  `/home/alvaro/Universidad/IA/Proyecto`
- **Repositorio de los compañeros:** otra versión; su ruta y arquitectura deben determinarse en la nueva sesión. No se exploró desde acá.

Estas rutas son contexto de esta máquina, no una garantía de que existan en otro entorno. Si faltan, trabajar con los archivos proporcionados y declarar esa limitación.

### Prioridad indicada por el usuario

- Los **PI** son trabajos individuales que desarrollan módulos del sistema.
- Los **PG** integran el sistema completo.
- Los entregables de mayor numeración incorporan correcciones y prevalecen sobre los anteriores.
- **PG3 es la entrega final.**

Esta prioridad también se aplica al interpretar requisitos y cifras. Sin embargo, **no resuelve contradicciones dentro de PG3**, por ejemplo entre su informe, su README y su código. No elegir silenciosamente una de esas fuentes como verdad ni corregir el dominio de oficio.

### Cobertura real de la exploración

| Material | Alcance observado |
|---|---|
| `PG0/`, `PG1/`, `PG2/`, `PG3/` | Informes, fuentes y resultados textuales revisados; PDF/DOCX mediante extracción de texto. |
| `PI0/` a `PI4/` | Informes individuales, consignas y fuentes disponibles revisados por vía textual/extraída. |
| `Ejemplo_Clase/` | Plantillas y ejemplos DOCX revisados mediante extracción. Son material de referencia, no requisitos propios de EvalTIC. |
| `.py`, `.cypher`, `.md`, `.json`, `.dot`, `.sh`, requisitos | Lectura textual; una primera lectura parcial de algunos JSON se completó con el volcado posterior. |
| SVG | Etiquetas extraídas; `PI1/diagrama_proceso.svg` estaba malformado. Se leyó el equivalente Mermaid en `PI1/Tapia_Alvaro_PI1_U2.md`. |
| PNG | Se inspeccionó una parte, no todas las imágenes. No se afirma cobertura visual completa. |
| `PG3/Grupo_20_PG3_ProyectoFinal.zip` | Solo inventario de nombres/tamaños, no contenido completo. No se leyó el `.env` del archivo comprimido. |

La extracción de PDF se hizo con `pdftotext -layout`; la de DOCX, leyendo texto de sus XML. Eso no garantiza conservar todos los detalles de diagramas o capturas embebidas.

El PDF y DOCX finales de PG3 se reportaron textualmente equivalentes. La contradicción principal no es PDF frente a Word, sino **informe frente a código y cifras inconsistentes dentro del informe**.

La primera exploración tenía lagunas y conclusiones provisionales. Este documento consolida la segunda lectura y las comprobaciones posteriores, sin presentar aquellas lagunas como lectura completa.

## 3. Qué hace EvalTIC

EvalTIC evalúa **la compra de equipos usados para reacondicionamiento y reventa**. No es simplemente un recomendador de computadoras para uso personal.

Pregunta de negocio: ¿conviene comprar este equipo al precio pedido, negociar una oferta menor, descartarlo o solicitar más información?

| Módulo | Responsable | Función | Salidas principales |
|---|---|---|---|
| SM1 | Álvaro Tapia | Diagnóstico técnico y plan de reacondicionamiento | Viabilidad, tareas, costo e intervenciones. |
| SM2 | Leonel Navarta | Valuación comercial, obsolescencia y demanda | VMA, riesgo y demanda. |
| SM3 | Luciano Romero | Evaluación financiera de la operación | Decisión, indicadores y contraoferta. |
| SM0, transversal | Grupo / capa LLM | Interpretar entrada y redactar explicación | JSON extraído y dictamen narrado. |

SM0 no cambia el acuerdo de **tres módulos expertos**: es una capa transversal. El grafo declara también un nodo de submódulo para esa capa.

### Flujo general: patrón sándwich neuro-simbólico

```text
Aviso en lenguaje natural
  → LLM extractor: JSON
  → SM1: viabilidad y reacondicionamiento
      → cortocircuito si existe inviabilidad física
  → SM2: mercado, riesgo y demanda
  → SM3: márgenes, filtros y conveniencia
  → LLM: narración del dictamen ya calculado
```

**Invariante:** el LLM no debe sustituir el motor de decisión ni inventar cifras. La extracción también debe verificarse: una cifra mal extraída contamina un cálculo posterior correcto.

En PG3, las consultas de inferencia difusa se ejecutan obligatoriamente mediante **Neo4j/Cypher**. También existen reglas, frames y resultados en el grafo. Pero **no toda la lógica corre en Neo4j**: Python arma planes, suma costos, calcula VMA y aplica filtros y fórmulas financieras. Hay funciones/constantes auxiliares en Python que no implican un fallback operativo sin grafo.

Salidas presentes en el modelo/documentación: `Comprar`, `ComprarConOfertaMenor`, `DescartarPorInviabilidad`, `DescartarPorRiesgo` y `Verificacion_pendiente`. No asumir que todos esos estados se alcanzan correctamente por todos los caminos del código actual.

## 4. Conocimiento formal y reglas

### Frames y red semántica

Se modelan equipos/componentes, publicaciones, mediciones y fallas; planes, intervenciones y repuestos; dictámenes técnicos/comerciales; valor de mercado, riesgo, demanda, bloqueos, evaluación y decisión.

Ejemplos de frames: `Equipo`, `Notebook`, `PC_Escritorio`, `Bateria`, `Almacenamiento`, `MemoriaRAM`, `PlacaMadre`, `PlanReacondicionamiento`, `CostoReacondicionamiento`, `DictamenTecnico`, `ValorMercadoAjustado`, `RiesgoObsolescencia`, `DemandaComercial`, `DictamenComercial`, `Bloqueo`, `IndicadoresEconomicos`, `Evaluacion`, `Decision`.

La red conecta publicación con equipo, equipo con componentes/mediciones/fallas, fallas con dictámenes, intervenciones con planes/costos y mercado con riesgo/demanda. SM3 consume resultados técnicos y comerciales, no solamente el precio pedido.

### Criterios expertos: CE-01 a CE-20

En la carga están versionados como `v1`, estado **Provisional**, con referencia a una entrevista pendiente con el experto; no son parámetros empíricamente validados por esta sesión.

| ID | Nombre | Valor documentado |
|---|---|---:|
| CE-01 | bateria_reemplazo | 75 % |
| CE-02 | ram_soldada_min | 4 GB |
| CE-03 | temperatura_service | 85 °C |
| CE-04 | costo_service_termico | $8.000 |
| CE-05 | bateria_depreciacion | 80 % |
| CE-06 | bateria_factor | 10 % |
| CE-07 | deprec_danado | 15 % |
| CE-08 | deprec_detalles | 5 % |
| CE-09 | reval_ssd | $30.000 |
| CE-10 | reval_ram | $15.000 |
| CE-11 | penal_repuestos | $50.000 |
| CE-12 | antiguedad_obsoleta | 6 años |
| CE-13 | anio_referencia | 2026 |
| CE-14 | margen_base | 20 % |
| CE-15 | margen_alta_liquidez | 12 % |
| CE-16 | margen_riesgo_alto | 30 % |
| CE-17 | umbral_intervenciones | 4 |
| CE-18 | prima_fallas | 5 puntos porcentuales |
| CE-19 | ratio_reparacion_max | 0,50 |
| CE-20 | descuento_max | 35 % |

No asumir que Python consulta dinámicamente todos estos valores: en PG3 hay literales y catálogos que difieren de los CE. Tampoco actualizar automáticamente el año a la fecha del sistema: **2026 está fijado en el material**.

### Reglas determinísticas: separar declaración y ejecución

| Regla / grupo | Significado y estado identificado |
|---|---|
| R1.1 | Falla catastrófica → inviabilidad física. Activa. |
| R1.2 | Batería por debajo del umbral o deformada. Sustituida en parte por SM1-BAT; el caso de batería hinchada sigue siendo una guarda documental, no implementada por completo en PG3. |
| R1.3 | HDD → modernización a SSD. Implementada en el plan Python. |
| R1.4 | RAM soldada de hasta 4 GB y sin posibilidad de expansión → inviabilidad. Declarada, no ejecutada en el camino PG3 revisado. |
| R1.5 | Repuesto mandatorio discontinuado → inviabilidad. Declarada, no ejecutada. |
| R1.6 | Derrame más sulfatación → falla catastrófica. Declarada; no equivale a una implementación completa de esa regla en el pipeline. |
| R1.7 | Umbral térmico, reemplazado por SM1-TER. |
| R2.1–R2.4 / R2.7 | Depreciaciones, revalorizaciones, repuestos y rechazo comercial: formalizados, pero no todos ejecutados en PG3. |
| R2.5 / R2.6 | Riesgo y demanda, reemplazados por SM2-RIE/SM2-DEM. |
| R2.8 | VMA = base − depreciaciones + revalorizaciones − penalizaciones. El cálculo Python PG3 usa en cambio depreciación cronológica. |
| R3.1 / R3.1b / R3.2 | Bloqueos no remediables, rechazo comercial o inviabilidad → descarte según modelo/grafo. No asumir ejecución idéntica en la UI. |
| R3.3 / R3.3b | Bloqueo desconocido o datos faltantes → verificación/dato pendiente según modelo/grafo. |
| R3.4 / R3.5 / R3.6 | Margen por liquidez, riesgo y cantidad de intervenciones. Activas en el cálculo Python. |
| R3.7 / R3.8 | Reparación/VMA excesivo; riesgo Alto más demanda Baja. Activas antes de conveniencia difusa. |
| R3.9 / R3.10 / R3.11 | Decisión final crisp reemplazada por SM3-CONV. |

La primera devolución del explorador mezcló algunos estados del grafo con ejecución efectiva. La tabla anterior evita atribuir a Python la ejecución completa de todas las reglas declaradas.

### Motor difuso y conjuntos

Cinco bases: batería, térmica, riesgo, demanda y conveniencia. Total: **27 reglas difusas**.

- Pertenencia gaussiana: `mu(x) = exp(-0.5 * ((x - c) / sigma)^2)`; conjuntos crisp por igualdad.
- Se ignoran activaciones menores que 0,01.
- OR = **MAX dentro de cada grupo**; AND = **MIN entre grupos**.
- Implicación MIN; agregación MAX; centroide discreto sobre **101 puntos**.
- La categoría se obtiene por pertenencia dominante en el centroide. No interpretar el centroide como probabilidad de éxito.

| Variable | Conjuntos `(centro, sigma)` |
|---|---|
| Salud_Bateria | Agotada (35,12), Degradada (64,8), Aceptable (82,6), Optima (95,5) |
| Ciclos_Carga | Pocos (0,250), Moderados (600,180), Excesivos (1100,180) |
| Temperatura_CPU | Fresca (50,8), Moderada (68,6), Elevada (80,4), Critica (92,5) |
| Caida_Frecuencia | Nula (0,4), Leve (10,5), Severa (25,7) |
| Necesidad_Intervencion | No_Requerida (0.1,0.12), Recomendada (0.5,0.12), Obligatoria (0.9,0.12) |
| Antiguedad_Hardware | Reciente (1.5,1.5), Intermedia (4.5,1.3), Antigua (7.5,1.3), Obsoleta (10.5,1.3) |
| Disponibilidad_Repuestos | Escasa (1,1.8), Regular (5,1.5), Amplia (9,1.5) |
| Soporte_W11 | Crisp: Sí/No |
| Riesgo_Obsolescencia | Bajo (0.1,0.12), Medio (0.5,0.12), Alto (0.9,0.12) |
| Rotacion_Mercado | Muy_Rapida (7,6), Moderada (30,9), Lenta (62,12) |
| Demanda_Comercial | Baja (0.1,0.12), Media (0.5,0.12), Alta (0.9,0.12) |
| Brecha_Margen | Insuficiente (-40,12), Escasa (-12,7), Suficiente (3,6), Holgada (25,10) |
| Descuento_Requerido | Razonable (0,12), Agresivo (30,8), Irreal (55,10) |
| Conveniencia | Descartar (0.1,0.12), Negociar (0.5,0.12), Comprar (0.9,0.12) |

**SM1-BAT (5):** RB1 Agotada → Obligatoria; RB2 Degradada → Obligatoria; RB3 Aceptable y Excesivos → Recomendada; RB4 Aceptable y (Pocos o Moderados) → No_Requerida; RB5 Optima → No_Requerida.

**SM1-TER (6):** RT1 Critica → Obligatoria; RT2 Elevada y (Leve o Severa) → Obligatoria; RT3 Elevada y Nula → Recomendada; RT4 Moderada y (Leve o Severa) → Recomendada; RT5 Moderada y Nula → No_Requerida; RT6 Fresca → No_Requerida.

**SM2-RIE (7):** RO1 W11=No y (Antigua u Obsoleta) → Alto; RO2 Obsoleta → Alto; RO3 Escasa y (Antigua u Obsoleta) → Alto; RO4 W11=Sí y Antigua y (Regular o Amplia) → Medio; RO5 Escasa y (Reciente o Intermedia) → Medio; RO6 W11=No y (Reciente o Intermedia) → Medio; RO7 W11=Sí y (Reciente o Intermedia) y (Regular o Amplia) → Bajo.

**SM2-DEM (4):** RM1 Alto → Baja; RM2 Lenta → Baja; RM3 Muy_Rapida y (Bajo o Medio) → Alta; RM4 Moderada y (Bajo o Medio) → Media. Consume el **centroide continuo de riesgo**, no solamente su etiqueta.

**SM3-CONV (5):** RD1 Suficiente u Holgada → Comprar; RD2 Escasa y Razonable → Negociar; RD3 Escasa y Agresivo → Negociar; RD4 Irreal → Descartar; RD5 Insuficiente y (Agresivo o Irreal) → Descartar.

Versiones formales: `FIS-SM1-v1`, `FIS-SM2-v1`, `FIS-SM3-v2`. SM3-v2 usa salidas 0.1/0.5/0.9 con sigma 0.12. El informe PI4/SM3 describe además una formulación normalizada con 9 reglas/cortes; no confundirla con las 5 reglas de la base Cypher integrada. Al portar, identificar la base real de esa versión.

## 5. Cálculos económicos y catálogos de PG3

### Fórmulas conceptuales

```text
antigüedad = max(0, 2026 - año)
factor = max(0.20, 1 - (min(antigüedad,3)*0.10 + max(0,antigüedad-3)*0.08))
factor *= 0.75 si riesgo Alto; 0.90 si Medio; sin penalización si Bajo
VMA = precio_base * factor

margen_neto = 100 * (VMA - precio - reparación) / VMA
ratio_rep = reparación / VMA
requerido = 12 si demanda Alta y riesgo Bajo; 30 si Alto; 20 en otro caso
requerido += 5 si intervenciones >= 4
contraoferta = max(0, VMA - reparación - VMA * requerido/100)
brecha = margen_neto - requerido
descuento = 100 * (precio - contraoferta) / precio si contraoferta < precio; si no 0
```

Detalles que importan para reproducir **el código**, no solo las fórmulas:

- SM2 redondea `VMA = round(precio_base * factor, -3)` y lo convierte a entero.
- SM3 sustituye VMA no positivo por `max(precio, 100000)`; no interpretar eso como un dato de mercado real.
- SM3 redondea margen a 1 decimal y ratio a 2 decimales **antes** de evaluar el descarte por ratio > 0,50.
- Contraoferta se redondea y limita a cero; brecha y descuento se redondean a 1 decimal.
- Primero R3.7; después R3.8; finalmente conveniencia difusa. No cambiar esos detalles en este port.
- Python asigna rotación 45/25/12 días según riesgo Alto/Medio/Bajo antes de inferir demanda; no confundirla con una medición de mercado extraída del aviso.

Catálogo de referencias de equipo nuevo en PG3: Aspire 5 $450.000; T490 $700.000; T440p $380.000; Inspiron 15 $520.000; HP 15 Ryzen 3 $480.000; Pavilion 15 $490.000; MacBook Air 2017 $550.000. Para equipos fuera de catálogo existe búsqueda web y un respaldo de $450.000 si falla; no es una tasación real verificada.

Costos Python PG3: pantalla $60.000; batería $35.000; teclado $25.000; SSD 240 del catálogo $32.000 pero upgrade HDD→SSD $22.000; RAM a 8 GB $18.000; service térmico $15.000; cargador $18.000; mano de obra general $20.000 cuando hay intervenciones. Confirmar las claves efectivamente utilizadas, no solo los valores declarados.

## 6. Ejemplo documentado y contradicciones sin resolver

### Caso publicado NB-101, Acer Aspire 5

Datos del grafo PG2: precio $115.000; salud 60%; 780 ciclos; temperatura 87 °C; caída de frecuencia 18%; repuestos 6; rotación 25 días; año 2020; Windows 11 sí.

Plan publicado: batería $30.000 + térmico $8.000 + SSD $22.000 + RAM $10.000 + teclado $20.000 = **$90.000**, 5 intervenciones. VMA **$220.000**.

Traza publicada: batería Obligatoria; térmico Obligatorio; riesgo Medio (~0.36); demanda Media (~0.50); margen 6,8%; ratio 0,41; requerido 25%; brecha -18,2 pp; descuento 34,8%; contraoferta **$75.000**; conveniencia ~0.44 → Negociar → `ComprarConOfertaMenor`.

La aritmética del ejemplo se recalculó y cierra. Los centroides/activaciones se tomaron de artefactos publicados, que presentan algunas inconsistencias; no fueron recalculados por una corrida completa del grafo en esta sesión.

Fuentes: `PG2/D1.json`, `A2.json`, `A3.json`, `C3_Detalle.json`, `C_General.json`, informe PG3 secciones g/j. El aviso que aparece en la UI es otra variante: salud 42%, 92 °C, 4 GB y pantalla dañada. **No mezclar las entradas de ambas variantes.**

| Tema | Contradicción / hallazgo | Tratamiento |
|---|---|---|
| RAM | PG3 usa `ram < 8`; PI4/Tapia usaba `ram <= 8`. Una máquina de 8 GB no recibe upgrade en PG3. | Priorizar PG3; no cambiarlo para ajustar un ejemplo. |
| Identificadores de reglas | PG3 llama R1.2 al upgrade RAM y R1.4 a pantalla, aunque en el modelo formal R1.2 es batería y R1.4 es RAM soldada sin expansión. | Documentar discrepancia, no renumerar reglas en este port. |
| Pantalla/MO | PG3 enumera 6 partidas: 35+15+18+22+60+20 mil = **170 mil**, pero declara 90 mil y 5 intervenciones. | El código sí suma pantalla y MO; el total del informe no cierra. |
| VMA Acer | Grafo/informe: 220 mil; texto sobre depreciación 48% de base450mil daría216mil; código:450000×0.46×0.90=186300, redondeado a **186000**. | Son ramas distintas; cálculo derivado, no corrida completa. |
| Decisión Acer | Grafo negocia75mil; con reparación170mil/VMA186mil el ratio0.91 activa R3.7 descarte. | No prometer que el programa reproduce el resultado del README. |
| T440p | Grafo reparación25mil y R3.8; informe55mil y R3.8; código con55mil y VMA57mil activa primero R3.7. | La etiqueta final puede coincidir aunque cambie la causa. |
| T490 | PG3 anuncia requerido12%; PG2 describe riesgoMedio0.46, por lo que no aplica alta liquidez12% sino20%. El térmico/MO puede alterar también costo cero. | Contrastar entradas concretas antes de afirmar un resultado. |
| HP15 | Informe usa37.750 de PI4; catálogo PG3 produce60mil con MO y VMA~259mil, no las cifras publicadas. | No importar tablas de otra etapa de forma silenciosa. |
| Activaciones del grafo | A2 da mu_Degradada(60)~0.88 y mu_Excesivos(780)~0.21; otros dumps publican1.00/0.61 y centroides algo distintos. | Tratar como evidencia documental contradictoria, no resultado reproducido. |
| Grafo descrito | Informe menciona solo SM1/2/3 y frame Laptop; carga incluyeSM0 y usa Equipo/Notebook. | Leer el esquema real. |
| Concordancia/rendimiento | Informe declara100% concordancia y20–35s en CPU. | No verificado por esta sesión; no convertirlo en garantía. |

Otros puntos observados, **no corregidos**:

- PI0/Tapia comenzó con un asesor metacognitivo de estudio, no EvalTIC; no incorporar aquel dominio a la especificación final.
- R1.4 requiere RAM **soldada y sin expansión**: 4 GB por sí solos no prueban inviabilidad. Una conclusión provisional del explorador omitía esa condición y se descarta.
- PG3 deriva caída de frecuencia como20% si `thermal_throttling=True`, y5% si no; no usa una medición porcentual real del extractor como lo hacía PI4/SM1.
- El cambio de batería en el código PG3 usa la categoría Obligatoria; no asumir que cualquier categoría Recomendada agrega reemplazo, como en descripciones anteriores.
- Nulos de Windows11 y valores por defecto requieren atención; los PI y PG3 no los resuelven necesariamente igual.
- Empates de pertenencia/categoría y orden de desempate no están completamente documentados.
- El carácter provisional de criterios/conjuntos y la incertidumbre no se propagan de manera completa al dictamen visible.
- Las copias Cypher incluidas en PG3 fueron reportadas equivalentes a las de PG2. Los catálogos Python no son equivalentes.

## 7. Preparación de la copia de ejecución

Se copiaron inicialmente estos **7 archivos byte a byte**, con verificación SHA-256, desde PG3 a la copia de trabajo:

```text
app_web.py
orquestador_evaltic.py
requirements.txt
iniciar_web.sh
README.md
Grupo_20_PG2_U1_carga.cypher
Grupo_20_PG2_U1_consultas.cypher
```

No se copiaron informes, ZIP ni credenciales. La carpeta `.atl/` preexistente no se modificó. Después se modificaron el cliente y README y se agregó `tests/test_llm_client.py`; el origen académico permaneció intacto.

### Entorno local y comandos

Existe `.venv` con Streamlit. La sesión comprobó su presencia, pero **no instaló** el entorno por cuenta propia. El error inicial `/usr/bin/python: No module named streamlit` se resolvió indicando el intérprete correcto:

```bash
cd "/home/alvaro/Universidad/IA/Proyecto"
./.venv/bin/python -m streamlit run app_web.py --server.address 127.0.0.1
```

El `requirements.txt` original omite `neo4j` y `beautifulsoup4`, aunque el código los utiliza. Se indicaron al usuario los comandos de instalación, sin afirmar que esta sesión los ejecutara. No copiar `.venv` a otro repositorio: recrear su entorno con los requisitos de esa versión.

Neo4j se recomendó en contenedor local dedicado, volumen propio y puertos ligados solo a `127.0.0.1`:7474/7687. Esa fue una guía de preparación, no una instalación realizada por esta sesión.

**PELIGRO:** la carga Cypher comienza con `MATCH (n) DETACH DELETE n`. No ejecutarla sobre una base con otros datos. Usar instancia/base aislada y autorización explícita para la carga.

Se encontraron credenciales en claro en archivos originales de configuración: `PI4/env.example`, un archivo de credenciales de Neo4j dentro de `PG2/` y materiales de configuración del ZIP. No se reproducen sus valores. No reutilizarlos ni incluirlos en commits, capturas o documentación. Si son reales y siguen vigentes, el responsable debe evaluar su rotación.

## 8. Conexión OpenRouter: qué ya existía y qué se configuró

El código **ya tenía** un adaptador OpenAI-compatible seleccionado por `LLM_PROVIDER=openai`. No se implementó desde cero otro SDK: se aprovechó esa compatibilidad y se documentó su configuración.

Ejemplo **sin secretos reales**, para un `.env` local excluido del control de versiones:

```env
LLM_PROVIDER=openai
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=YOUR_OPENROUTER_API_KEY
OPENAI_MODEL=nvidia/nemotron-3.5-lightning:free

NEO4J_TARGET=local
NEO4J_LOCAL_URI=bolt://localhost:7687
NEO4J_LOCAL_USERNAME=neo4j
NEO4J_LOCAL_PASSWORD=YOUR_LOCAL_DATABASE_PASSWORD
NEO4J_LOCAL_DATABASE=neo4j
```

`openai` identifica el protocolo, no el proveedor de facturación. `consultar_llm` envía POST a `base_url.rstrip('/') + '/chat/completions'`, con mensajes system/user, temperature 0.1 y autenticación Bearer. *[actualizado 13/11/2026: el documento decía `temperature0.2`; el código usa 0.1]*. Para extracción agrega `response_format: {"type":"json_object"}`.

La carga de configuración intenta `.env` junto al orquestador y, en la estructura original, el de `PI4/` como alternativa. No depender de ese fallback en otro repositorio. Reiniciar Streamlit al cambiar la configuración.

La sesión solo cambió la selección de modelo del `.env` de trabajo al volver a Nemotron; no imprimió ni modificó su clave. La conexión remota envía el texto al proveedor: usar avisos ficticios o anonimizados para pruebas.

## 9. Incidente de tokens y cambios implementados

### 9.1 Reproducción antes de corregir

El código original hacía:

```python
return data["choices"][0]["message"]["content"].strip()
```

La entrada del usuario no estaba vacía. Lo nulo era **el texto de respuesta del modelo**.

| Sonda real | Resultado observado |
|---|---|
| Consulta mínima a Nemotron con350tokens | HTTP200, stop, texto correcto;205tokens de salida,198 de razonamiento. |
| Prompt extractor real + aviso Acer,350tokens | HTTP200, length, contentnull;350tokens de salida y350 de razonamiento. |

El razonamiento consumió todo el presupuesto antes de producir JSON. El `.strip()` sin validación generó `AttributeError`.

Presupuestos solicitados por los llamadores originales:150 para estimación de precio,350 para extracción y300 para síntesis. Los tokens de razonamiento pueden contar dentro de ese mismo límite.

### 9.2 Presupuesto mínimo en el cliente

Cambio implementado, únicamente para hostname `openrouter.ai`:

```python
"max_tokens": (
    max(max_tokens, 4096)
    if urlparse(OPENAI_BASE_URL).hostname == "openrouter.ai"
    else max_tokens
)
```

- Conserva presupuestos mayores a4096 pedidos por el llamador.
- Otros proveedores y Ollama conservan su presupuesto anterior.
- Es un techo de generación, no consumo fijo.
- **No es** una configuración por etapa ni una variable de entorno de tokens.

El primer arreglo permitió una extracción real correcta. Después el usuario reportó que la **síntesis** agotó también4096tokens, todos en razonamiento. Por tanto,4096 **no es una solución universal** ni motivo para seguir aumentando el límite a ciegas.

La síntesis final sin razonamiento consumió399tokens; volver sin más al límite300 tampoco reproduciría esa respuesta completa.

### 9.3 Validación de la respuesta

El cliente ahora valida:

- `choices`: lista no vacía y primer elemento objeto.
- `message`: objeto.
- `content`: string con texto no blanco.
- `finish_reason=length`: se rechaza siempre, incluso con texto parcial o aparentemente completo.

En lugar de `AttributeError`, produce `RuntimeError` con una explicación. Incluye solo metadatos seleccionados: motivo de finalización de un conjunto conocido y conteos de completion/reasoning enteros no negativos, o `unknown`.

No convierte `None` en cadena vacía, no fabrica JSON y no utiliza el razonamiento como respuesta. No agrega reintentos ni fallback a modelos pagos.

**Límite importante:** la protección nueva de metadatos corresponde a estas respuestas200. El manejo preexistente de HTTP no200 todavía agrega `resp.text` al error, como se vio con429. Tampoco se agregó un manejo dedicado de cuerpos HTTP200 que no sean JSON. No afirmar que todo el cliente ya sanea todos los errores.

### 9.4 Razonamiento desactivado: implementación exacta actual

```python
if (urlparse(OPENAI_BASE_URL).hostname == "openrouter.ai"
        and OPENAI_MODEL == "nvidia/nemotron-3.5-lightning:free"):
    payload["reasoning"] = {"enabled": False}
```

Aplica al cliente compartido: extracción JSON, síntesis de texto y cualquier otra llamada dirigida a ese modelo. No altera otros modelos/proveedores.

*[actualizado 13/11/2026]* Existe además una **segunda vía, para NVIDIA directo**, que es la que
usa la corrida real de los 61 casos. Aplica al host `integrate.api.nvidia.com` con el modelo
`nvidia/nemotron-3.5-lightning-30b-a3b`:

```python
if host == NVIDIA_HOST and OPENAI_MODEL == NVIDIA_MODELO_SIN_RAZONAMIENTO:
    payload["chat_template_kwargs"] = {"enable_thinking": False}
```

NVIDIA recibe el interruptor dentro de la plantilla de chat y **conserva el presupuesto del
llamador**: no se aplica el piso de 4096 ni se toca `max_tokens`. Las dos condiciones son
host+modelo exactos; el nombre del modelo no alcanza por sí solo en ninguno de los dos casos.

**No existe todavía una opción genérica** `LLM_REASONING`, `OPENROUTER_REASONING` ni equivalente en el `.env` de esta copia. Tampoco se desactiva automáticamente el razonamiento de cualquier modelo por contener la palabra Nemotron.

`reasoning.enabled=false` solicita desactivación real. `reasoning.exclude=true` o `include_reasoning=false` solo ocultan el razonamiento y **no equivalen** a desactivarlo. Verificar siempre la compatibilidad del modelo/proveedor; algunos tienen razonamiento obligatorio.

### 9.5 Por qué volvimos a Nemotron

Se probaron por el usuario Gemma4 26B y31B gratuitos, anunciados con razonamiento apagado por defecto. Ambos devolvieron429 con límite de **pool compartido upstream** de Google AI Studio. No era un error de Neo4j ni evidencia de una clave inválida.

Se eligió Nemotron Lightning porque el catálogo indicaba razonamiento opcional y ya había respondido con la cuenta configurada. No asumir disponibilidad futura de esos modelos, cuotas ni proveedores: los endpoints gratuitos cambian y pueden saturarse.

## 10. Pruebas y evidencia

### Tests offline: `app/tests/test_llm_client.py`

*[actualizado 13/11/2026: el documento decía `tests/test_llm_client.py` con 10 pruebas; hoy el
archivo vive en `app/tests/` y tiene 34 métodos de prueba. Los 10 casos de abajo siguen siendo los
que documenta este bloque.]*

Invocan la función pública `consultar_llm`, con transporte mockeado y configuración de prueba, sin llamadas a API ni a Neo4j.

Casos cubiertos:

1. Razonamiento desactivado para Nemotron tanto en extracción como en síntesis.
2. Ausencia de ese override para otros modelos/proveedores.
3. Null con `length` produce error accionable y metadatos seguros.
4. Presupuesto mínimo OpenRouter y conservación de límites mayores.
5. Respuesta válida sigue siendo recortada y el payload conserva mensajes/formato JSON.
6. Texto parcial con `length` no se acepta.
7. Contenido nulo, blanco o no textual se rechaza.
8. Estructura inválida se rechaza de forma controlada.
9. Otros proveedores compatibles conservan su presupuesto.
10. Ollama conserva payload y presupuesto previos.

```bash
python -m unittest discover -s app/tests -v
python -m py_compile app/orquestador_evaltic.py app/app_web.py
```

*[actualizado 13/11/2026: se corre desde la raíz del repositorio. El documento original decía
`./.venv/bin/python -m unittest discover -s tests`, con `tests/` al mismo nivel que
`orquestador_evaltic.py`. Acá los módulos viven en `app/` y varios importan `app.tests.*` y
`scripts.*`: ejecutarlo con `cd app` falla con cuatro errores de importación.]*

Evidencia observada:

- Primer arreglo: RED exit1,7tests con 6 fallos y 12 errores contando subtests; después GREEN: 8 tests, exit 0.
- Desactivación de razonamiento: RED exit1 con2subtests fallidos (JSON y texto); después GREEN: 10 tests, exit 0.
- Compilación y último spot check: exit0,10tests correctos.
- Dos verificaciones independientes: PASS sin bloqueos; incluyeron comprobaciones de aislamiento, preservación de payload/proveedores y ausencia de reintentos.
- La última verificación no tenía una copia baseline independiente de todo el archivo: reconstruyó las4líneas del último ajuste para confirmar RED. No presentarlo como prueba independiente de un diff global histórico.
- La evaluación nativa del harness no produjo un candidato evaluable en esta carpeta. No hubo aprobación/recibo de review nativa, commits, push ni inicialización de Git por esta sesión.

### Última validación real: dos consultas, sin razonamiento

| Prueba | Resultado | Duración observada | Completion | Reasoning |
|---|---|---:|---:|---:|
| Extractor real + aviso ficticio Acer | HTTP200, stop, JSON válido |3,12s|186|0|
| Síntesis real + contexto financiero fijo de prueba | HTTP200, stop, texto final |6,78s|399|0|

Extracción: se comprobaron 7 campos: precio115000; RAM4; batería42%; temperatura92°C; pantalla dañada true; teclado dañado false; cargador incluido true.

Síntesis: se usó el prompt real y un contexto **sintético** que indicaba descarte, reparación170000, VMA186000 y precio115000. Llegaron1245caracteres y se confirmó una expresión de rechazo. No fue una auditoría semántica exhaustiva de toda la redacción.

**No se consultó Neo4j ni se ejecutaron los motores financieros en esas dos pruebas.** Los tiempos son observaciones puntuales, no garantías de disponibilidad o rendimiento.

## 11. Implementado frente a propuesto

| Tema | Estado en esta copia |
|---|---|
| Adaptador compatible OpenAI | Preexistente; aprovechado para OpenRouter. |
| Configuración/documentación OpenRouter | Realizada. |
| Piso4096 para OpenRouter, límites mayores preservados | Implementado y probado. |
| Validación de estructura/texto y rechazo de length | Implementada y probada. |
| Desactivar razonamiento de Nemotron Lightning en OpenRouter | Implementado con condición específica host+modelo, probado offline y real. |
| Desactivar razonamiento de Nemotron en NVIDIA directo | *[actualizado 13/11/2026]* Implementado con `chat_template_kwargs.enable_thinking=false` y sin piso de tokens; es la vía de la corrida real de los 61 casos. |
| Presupuestos configurables separados por etapa | **Propuesta**, no implementada. |
| Toggle genérico de razonamiento por proveedor/modelo | **Propuesta**, no implementada. |
| Error amigable específico para429 o saneamiento de todos los errores HTTP | **Propuesta**, no implementada. |
| Reintentos automáticos / fallback pago | No implementados; no agregarlos silenciosamente. |
| E2E completo UI+Neo4j+reglas+ambas llamadas | No verificado por esta sesión. |

Si el repositorio de los compañeros ya tiene presupuestos separados o selección de proveedores, reutilizarlos. No trasladar obligatoriamente el literal4096 a todos los modelos ni sobreescribir una configuración mejor existente.

Una generalización razonable podría permitir controlar el razonamiento y los presupuestos por etapa, pero debe validarse contra capacidades reales. Definir variables nuevas, sus valores por defecto y su alcance es trabajo adicional, no algo que este documento prueba como existente.

## 12. Checklist de portado y aceptación

### Antes de modificar

- [ ] Identificar entrypoints, cliente, prompts, configuración y motores reales del otro repo.
- [ ] Revisar sus tests y convenciones; mapear equivalencias, no asumir los mismos nombres.
- [ ] Registrar diferencias de la versión y preservar cambios de los compañeros.
- [ ] Confirmar el alcance autorizado y separar mejoras LLM de contradicciones académicas.

### Implementación mínima

- [ ] OpenRouter configurable con clave solo en entorno/local, nunca en código o tests.
- [ ] Presupuestos adecuados para todas las etapas; preservar límites mayores y proveedores ajenos.
- [ ] Desactivación explícita de razonamiento solo cuando modelo/proveedor la admiten.
- [ ] Null/blanco/estructura inválida y truncamiento generan error claro, no evaluación fabricada.
- [ ] No usar razonamiento como salida ni esconder que la respuesta quedó incompleta.
- [ ] No introducir reintentos silenciosos, tormentas de requests ni fallback pago.
- [ ] No cambiar reglas, umbrales, catálogos, redondeos ni orden de filtros financieros.

### Verificación

- [ ] Tests primero sobre la interfaz pública y observación RED/GREEN.
- [ ] Casos válidos previos siguen funcionando y proveedores no afectados se conservan.
- [ ] Probar extracción y síntesis, no dar por validado todo el flujo con una sola llamada.
- [ ] Requests reales solo con autorización vigente, contenido ficticio/anonimizado y cantidad acotada.
- [ ] Medir tokens de razonamiento cuando el proveedor los reporte; no deducir cero solo porque no se muestra el texto.
- [ ] E2E con Neo4j como prueba explícita y aislada; jamás cargar el script destructivo en una base compartida.
- [ ] Informar checks fallidos, no ejecutados o indisponibles, además de los correctos.
- [ ] Documentar cómo reiniciar la app y cómo reconocer límites429 sin mostrar datos sensibles.

## 13. Referencias para localizar la implementación

En la copia de trabajo, buscar **símbolos**, no depender de números de línea que cambian:

- `consultar_llm`: transporte, payload, presupuesto, override reasoning y validaciones.
- `PROMPT_EXTRACTOR_INTEGRAL` y `PROMPT_SINTESIS_GERENCIAL`: roles lingüísticos del LLM.
- `evaluar_publicacion_integral`: llamados de extracción/síntesis y coordinación de módulos.
- `ejecutar_motor_sm1`, `ejecutar_motor_sm2`, `ejecutar_motor_sm3`: lógica de dominio.
- `inferir_sm1_bat_cypher`, `inferir_sm1_ter_cypher`, `inferir_sm2_rie_cypher`, `inferir_sm2_dem_cypher`, `inferir_sm3_conv_cypher`: consultas difusas.
- `PRECIOS_REFERENCIA_NUEVO`, `COSTOS_COMPONENTES`: catálogos Python.
- `app/tests/test_llm_client.py`: 34 pruebas del cliente *[actualizado 13/11/2026: antes decía 10]*.
- `README.md`: arranque y sección OpenRouter.
- Ambos archivos `Grupo_20_PG2_U1_*.cypher`: esquema, carga/reglas y consultas.

Fuentes externas consultadas; volver a comprobar capacidades/disponibilidad antes de elegir otro modelo:

- Catálogo: https://openrouter.ai/api/v1/models
- Endpoint Nemotron: https://openrouter.ai/api/v1/models/nvidia/nemotron-3.5-lightning:free/endpoints
- Control de razonamiento: https://openrouter.ai/docs/guides/best-practices/reasoning-tokens
- Variantes gratuitas: https://openrouter.ai/docs/guides/routing/model-variants/free

**Principio final:** preservar el sistema experto como árbitro, usar al LLM para extraer y narrar, y portar comportamiento probado en lugar de copiar una versión de la aplicación sobre otra.
