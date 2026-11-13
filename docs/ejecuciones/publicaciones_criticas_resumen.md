# Resultado de las publicaciones críticas

Primera tanda real en `test/publicaciones-criticas`, contra Neo4j local y OpenRouter con
`nvidia/nemotron-3.5-lightning:free`. El motor de producción no se modificó.

## Evidencia

```bash
python -m unittest discover -s app/tests -v
# 64 pruebas, OK, salida 0 (29 existentes y 35 nuevas).
python -u scripts/probar_publicaciones.py --ejecutar
# Salida 2, duración 2 min 47 s. Sin reintentos de transporte.
```

Intérprete usado: `/home/alvaro/Universidad/IA/Proyecto/.venv/bin/python`.
Catálogo consultado: 83 procesadores (18 con precio), 45 líneas, 11 capacidades de RAM y
289 avisos. La carga PG3 fue autorizada expresamente; no se ejecutó el reset PG2.

| Resultado original del ejecutor | Cantidad |
|---|---:|
| Intentados | 61 |
| Completados | 29 |
| Cumplen expectativa automática | 18 |
| No cumplen expectativa automática | 8 |
| Sondas observadas, sin aprobación automática | 3 |
| No completados por infraestructura/proveedor | 32 |

La [salida original](publicaciones_criticas_openrouter.log) conserva los resultados de esa
corrida, incluidos sus incumplimientos. No se reescribe como si hubiera sido una corrida nueva.

## Interpretación de los incumplimientos

| Caso | Observado | Interpretación |
|---|---|---|
| PC-01 | `computadora asus, anda joya` → fuera de dominio | Confunde aviso insuficiente con consulta ajena al dominio; no inventó una tasación. |
| PC-15 | Aviso sano, 68 °C y sin throttling → servicio térmico, costo total $70.000 | Reparación inesperada. No se aisló si la causa fue extracción o inferencia; no atribuirla todavía a una regla concreta. |
| PC-16 | Evaluación integral correcta con origen `LLM` | Error del oráculo, **no del producto**. Se movió la exigencia de origen `regla` a `espera_offline`, donde se simula un router incorrecto. La observación original satisface el contrato corregido; sin nueva llamada al proveedor. |
| PC-17 | `Cuenta con batería nueva` → verificación por bloqueo | Falso positivo por subcadena, reproducido también offline. |
| PC-19 | `No prende y no carga` → Comprar, costo cero | Incumplimiento crítico de evaluación técnica, confirmado con servicios reales. |
| PC-25 | Aviso con emojis sin datos → fuera de dominio | No devuelve el rechazo explícito esperado. |
| PC-56 | Consulta técnica de batería → fuera de dominio | Resultado incorrecto observado. El router puede ocultar un error del proveedor y usar su respaldo: no se demostró causalidad del LLM. |
| PC-57 | Consulta de valuación → fuera de dominio | Misma limitación de causalidad que PC-56. |

Hay **7 incumplimientos de expectativas funcionales y 1 error del oráculo corregido** dentro de
los 8 originales. Eso no constituye una segunda corrida ni una tasa de exactitud general.

## Sondas revisadas

- PC-27: aviso en dólares terminó fuera de dominio; no se observó conversión ni valuación.
- PC-36: MacBook sin CPU explícita quedó `VerificacionPendiente` por R3.3b, VMA cero.
- PC-40: batería 88 % y 1.200 ciclos terminó en Comprar, costo cero. Es observación para
  contrastar con el experto, no un aprobado automático ni un umbral nuevo.

## Prueba pendiente y decisión necesaria

No completados: PC-20, PC-22, PC-24, PC-28, PC-29, PC-30, PC-31, PC-32, PC-33, PC-34,
PC-35, PC-37, PC-38, PC-39, PC-41, PC-42, PC-43, PC-44, PC-45, PC-46, PC-47, PC-48,
PC-49, PC-50, PC-51, PC-52, PC-53, PC-55, PC-58, PC-59, PC-60 y PC-61.

Se informaron `RuntimeError` clasificados como infraestructura; el registro no conserva el
mensaje HTTP por privacidad. **No está demostrado que todos sean 429 o cuota agotada.** No se
reintentaron, no se cambió de modelo ni se activó un proveedor pago. La validación real completa
queda bloqueada hasta decidir si se mantiene el modelo y se autoriza otra tanda cuando esté
disponible, o se elige explícitamente otro modelo/proveedor. Los casos con precio ausente también
pueden ocultar fallas del proveedor mediante el respaldo del enrutador.

El alcance entregado es la batería y la evidencia: no se corrigió el motor ni se afirma cobertura
de todas las publicaciones posibles. Los defectos offline se muestran como abiertos/reparados y
no se exige que permanezcan rotos.
