# Verificación acotada — condiciones SM1 y filtro R3.7

## Resultado

Verificador independiente `mwcnh8dp-5-zffj`: **PASS técnico**, sin bloqueantes en P2a/P3a.
Proceso histórico **PARTIAL**, sin aprobación nativa: no se borran los desvíos del primer
trabajador ni se reconstruye su registro sobrescrito de primera carga P2a.

## Evidencia reportada

- Copia de fuentes en TMPDIR propio del verificador; no se modificó el repositorio.
- Comando focalizado `unittest discover -s app/tests -p 'test_politicas_sm[13]*neo4j.py' -v`:
  exit 0, 15 pruebas en 2,653 s (10 SM1 y 5 R3.7). No suite de 200.
- Diferencial único contra `e7854e0`: exit 0, cuatro rutas realmente ejercitadas,
  resultados/trazas/stdout/excepciones iguales: `consultar_sm1` (cargador),
  `ejecutar_motor_sm3` (R3.7), evaluación integral y `asistente_evaltic` (fixture P0 T14,
  extracción/enrutamiento/redacción controlados, sin llamadas al LLM).
- Inspección de consultas y sus contadores confirmó ambos consumidores nuevos. No se
  acredita una invocación CLI separada. La captura `stdout_integral` de P0 es parcial:
  su línea SM2 aparece literalmente en la salida, no representa toda la salida.
- Sondas revertidas: condición ajena no altera SM1; operador propio inválido conserva
  `ErrorConocimiento`; literal del cargador y comparador/CE de R3.7 cambian la inferencia.
- R3.7: igualdad con umbral no activa el filtro; conflicto del seed no escribe; segunda
  aplicación 0; configuración inválida conserva RuntimeError público y VMA cero conserva
  `ZeroDivisionError("division by zero")`.
- Estado antes/después/tercero idéntico reportado: 876 nodos, 1983 relaciones,
  19 restricciones, marcador 1, 9 Condicion y 1 VersionPoliticas. Sólo transacciones revertidas.
- La activación previa del padre se registra en `politicas_p3a_activacion.log`: dos altas
  en R3.7, protección de grafo completo dentro de transacción antes del commit, primera 1,
  segunda 0. No se volvió a aplicar persistentemente el artefacto en verificación.

## Integridad y alcance

SHA-256 de fuentes cotejados otra vez por el padre después del informe:

| Fuente | SHA-256 |
| --- | --- |
| orquestador_evaltic.py | 17d748050d5018becfede2cb7765096dcd597823f406e933ae878e1658cc6f25 |
| inferencia_sm1.py | d461ee61953b3d1d5ee354883959aa887c71cbec4778d8ea94d0f8f37416624e |
| inferencia_sm3.py | a03bc000966f5d296b60af04ef7cf15231214a5df2a71ea1b910b7c167f78995 |

El padre también observó 15/15 en 4,554 s y `git diff --check` exit 0. S1–S8 se
cumplen sólo para estos cortes; no se probaron P2b/P2c, resto de finanzas, R2.4 ni B3–B5.
No hubo nueva tanda de 61 publicaciones, validación del experto ni acceso a la base original.
Las dos pruebas durables sugeridas son opcionales; no agregan criterios de aceptación.
No se autoriza la limpieza del scratch del verificador por mencionarlo en su informe.
