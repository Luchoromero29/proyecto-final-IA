# R3.8: cierre técnico del corte de categorías

## Resultado

**PASS técnico acotado; proceso PARTIAL.** El corte representa `filtro_riesgo` y
`filtro_demanda` en la `Regla` R3.8 existente. Cypher valida las categorías contra
los conjuntos declarados y las consume; traza y motivo reflejan los datos. No se
migraron márgenes, fórmulas, consecuencias ni precedencias restantes de SM3.
No hay aprobación nativa de revisión, push ni PR.

## Evidencia funcional

- Trabajador: RED de 11 pruebas con un único fallo de motivo Media/Baja; una
  corrección de una línea; GREEN 11/11, sin errores ni omisiones, salida 0.
- Verificador independiente `mwd0dul0-3-z21j`: módulo focalizado 11/11, salida 0,
  sin omisiones, 5,255 s. Incluye autoridad de datos, configuración inválida,
  precedencia de R3.7 e idempotencia/conflicto sin escrituras.
- Un diferencial, dos entradas del motor público `ejecutar_motor_sm3`, contra
  fuentes de `8d485eb`: R3.8 por defecto y R3.7 cuando ambos filtros se cumplen.
  Objetos completos, trazas y excepciones idénticos; stdout y stderr vacíos;
  ambos procesos salida 0. No se acredita aquí una matriz integral/asistente/CLI.
- Motivo por defecto idéntico: «Riesgo de obsolescencia Alto con demanda comercial
  Baja (inmovilización de capital).». Mutar demanda a Media dentro de una
  transacción revertida cambia el filtro, la traza y el motivo públicos.

## Activación y protección

Activación del padre **únicamente en `bolt://127.0.0.1:17687`**, authNone, base
`neo4j`, marcador único `mejoras-evaltic`. Primera aplicación 1; segunda 0.
Comparación del grafo completo dentro de la transacción antes del commit:
solamente dos propiedades nuevas de R3.8; 876 nodos, 1983 relaciones y 19
restricciones intactos. Registro: `politicas_p3b_activacion.log`.
El verificador informó digest y conteos idénticos antes/después de sus pruebas.
La base original no recibió esta migración; el MCP sigue en modo sólo lectura.

## Integridad y límites

Payload preparado por el padre: nueve archivos, 263077 bytes y tres fuentes
anteriores. El verificador declaró los hashes del manifiesto iguales antes y
al finalizar. El padre confirmó después las tres fuentes de producción:

- Orquestador: `9827d46ccd71249f5a7e3a1bc1033c87157da1c072f1e7a75aac406e910ef185`.
- SM1: `d461ee61953b3d1d5ee354883959aa887c71cbec4778d8ea94d0f8f37416624e`.
- SM3: `fa837a2c911baca07a92ed5ff17d8c5b868fcf2f13425b6adbe22c4dc4e7429c`.

Desvíos preservados: el verificador corrigió una sonda inicial de snapshot que
falló con `22N27` pese al límite de parada; además reportó scratch en
`/tmp/verif-p3b.bjIElM` y escribió `/tmp/.verif_p3b_path`, fuera de las superficies
autorizadas. El padre no leyó ni borró esos archivos y no autoriza el desvío
retroactivamente. Eso impide declarar PASS de proceso; no se ocultan los
resultados técnicos observados. No se relanza la verificación ni se agrega la
prueba adicional sugerida: el módulo existente ya cubre el comportamiento.

Los dos fallos de preparación anteriores, con cero pruebas por scratch apagado,
quedan en sus logs. Se recuperó sólo esa instancia con permiso del humano y el
nuevo intento fue autorizado después. No se ejecutó la suite de 200 ni se
modificaron CSV, credenciales, versiones expertas o permisos ajenos de `datos/`.
El chequeo global de whitespace del índice devolvió salida 2 por un espacio final
original de `politicas_p3b_red.log:1`. Se conserva el log crudo sin alterarlo;
el chequeo de código y documentación authored devolvió salida 0. No se declara
que el chequeo global haya pasado ni se modifica su configuración.
ASSESS: riesgo alto por contrato compartido; evaluación nativa no disponible por
archivos sin seguimiento, candidato nulo/resultado unknown. No equivale a aprobación.
