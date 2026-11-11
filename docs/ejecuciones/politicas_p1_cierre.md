# P1 — correspondencia comercial representada en Neo4j

Unidad I8 del plan de migración; no cierre de B2 ni de P2–P6. Base `c46164f`, rama encadenada
`mejoras/politicas-p1-correspondencia`. Sólo scratch marcado, sin acceso original, `.env` o LLM.

## Resultado y evidencia

- Tres `ConjuntoDifuso` existentes conservados; nueve propiedades nuevas en total. No nuevos
  nodos/relaciones, parámetros Mamdani, precios, costos ni validaciones expertas.
- `CONSULTA_DECISION` lee resultado y habilitación; no elige por nombre de categoría.
  Firma, claves y fila nula desconocida conservadas; configuración inválida falla cerrada.
- RED: 3 fallos esperados sobre el CASE anterior. GREEN: 7 nuevas; suite 191 sin omisiones.
  Las 7 están incluidas en las 191, no son 198 pruebas distintas. Offline: 90, skipped=16.
- Diferencial padre único: 12 entradas/rutas públicas contra copia comprometida `c46164f`,
  todas ejercitadas sin excepción, resultados/stdout/stderr/exit codes idénticos.
- Primera carga real padre: 3 actualizaciones; segunda: 0. Se conservaron todas las
  propiedades/relaciones anteriores y la proyección completa salvo las nueve altas permitidas.
- Primer intento de carga: exit 1 por comparar Date/DateTime con strings JSON. Rollback
  confirmado con digest P0 idéntico; corregida comparación canónica, sin ampliar allowlist.
  No se oculta el intento: `politicas_p1_carga_intento1.log`.

## Verificación independiente: separar producto y ejecución

`mwbtsguz-o-qnlw` observó 7/7 y 191/191 (0 skips), delta exacto, protección y rollback.
Su sonda inicial de ambigüedad usó un nodo no enlazado: falsa alarma del arnés, no defecto;
con un segundo conjunto enlazado comprobó fail-closed. El spotcheck posterior padre: 7/7.

El informe original fue **PARTIAL**. La aclaración `mwbu2s3a-p-e22m`, sin herramientas ni
nuevas pruebas, precisó: **veredicto técnico acotado P1/I8 PASS; proceso global PARTIAL**.
No identificó aceptación P1 incumplida ni prueba obligatoria pendiente. No se reemplaza el
veredicto histórico, no se exige repetir la matriz que debía omitir ni añadir pruebas duplicadas.
Primera aplicación real y matriz de 12 rutas son evidencia padre, no se atribuyen al verificador.

Desvío de ejecución declarado: el hijo creó y borró `/tmp/.p1_scratch_path` y `/tmp/_st.txt`
fuera de su scratch asignado. No estaba autorizado por el padre, aunque fueran archivos
propios. Se conserva la declaración y el límite de sus observaciones; no se infiere permiso
retroactivo ni ausencia de efectos no comprobados. Su scratch restante se preserva: el hijo
no puede autorizar al padre a leerlo o borrarlo. No hubo cambios de producto para resolver
este incidente ni nueva corrida de verificación. Los advisories no abrieron correcciones.

## Límites y continuación

ASSESS directo: high por escalación de riesgo 3; native unassessable por untracked sin declarar,
candidate=null, resultado nativo unknown. No START, linaje ni aprobación nativa; el fallo de
assessment no se convierte en permiso ni en prueba. Autoverificación e independiente técnico
están registradas, con la salvedad de proceso anterior.

P1 técnico completo. Continuar P2 por cortes de acciones, precedencias y estado/plan.
Instalar datos antes de desplegar el consumidor; original/P6 espera conexión permitida,
inventario/respaldo vigente y recuperación. P5 debe acordar el cambio del fallback de bloqueo.

Risk: item 3 — consulta compartida por evaluación integral, asistente y CLI.
