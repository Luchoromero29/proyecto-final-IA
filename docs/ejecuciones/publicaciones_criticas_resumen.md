# Resultado de las publicaciones críticas

Registro de las tandas en `test/publicaciones-criticas`, contra Neo4j local. La primera usó
OpenRouter; los 32 pendientes se completaron después con NVIDIA directa. Se adaptó únicamente
el cliente LLM para desactivar thinking en NVIDIA Lightning; las reglas de negocio no cambiaron.

## Estado final

**Los 61 casos tienen una ejecución real completada**, distribuida entre dos proveedores; no
es una medición homogénea ni una comparación controlada de modelos.

| Tanda con resultados completados | Completados | Cumplen | No cumplen | Sondas | Infraestructura |
|---|---:|---:|---:|---:|---:|
| Primera OpenRouter | 29 | 18 | 8 originales | 3 | 32 no completados |
| Pendientes con NVIDIA directa | 32 | 27 | 2 | 3 | 0 |

Uno de los 8 incumplimientos originales de OpenRouter era el oráculo PC-16, corregido sin nueva
inferencia. Quedan **9 casos con incumplimientos funcionales observados**, no 9 defectos de raíz
necesariamente distintos: PC-01, PC-15, PC-17, PC-19, PC-25, PC-29, PC-50, PC-56 y PC-57.
Los primeros 7 no se reejecutaron con NVIDIA y no se atribuyen automáticamente al proveedor nuevo.
Las 6 sondas tienen observaciones, pero no cuentan como aprobadas.

La suite offline actual tiene **69 pruebas aprobadas** (34 del cliente y 35 de publicaciones y
ejecutor). Las tandas siguientes son el historial original, no resultados reescritos.

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

## Bloqueo después de la primera tanda (histórico)

No completados: PC-20, PC-22, PC-24, PC-28, PC-29, PC-30, PC-31, PC-32, PC-33, PC-34,
PC-35, PC-37, PC-38, PC-39, PC-41, PC-42, PC-43, PC-44, PC-45, PC-46, PC-47, PC-48,
PC-49, PC-50, PC-51, PC-52, PC-53, PC-55, PC-58, PC-59, PC-60 y PC-61.

Se informaron `RuntimeError` clasificados como infraestructura; el registro no conserva el
mensaje HTTP por privacidad. **No está demostrado que todos sean 429 o cuota agotada.** No se
reintentaron, no se cambió de modelo ni se activó un proveedor pago. La validación real completa
queda bloqueada hasta decidir si se mantiene el modelo y se autoriza otra tanda cuando esté
disponible, o se elige explícitamente otro modelo/proveedor. Los casos con precio ausente también
pueden ocultar fallas del proveedor mediante el respaldo del enrutador.

## Segundo intento autorizado: mismo modelo gratuito

El usuario indicó: «mantenemos el modelo gratuito y reintamos ahora». Se ejecutaron únicamente
los 32 casos pendientes con el mismo modelo, sin repetir los 29 ya completados.

- Duración: 9 segundos; código de salida: `2`.
- Intentados: **32**; completados: **0**; cumplidos: **0**; incumplimientos funcionales: **0**;
  sondas observadas: **0**; errores de infraestructura/proveedor: **32**.
- El preflight de Neo4j y catálogo pasó; las llamadas a los casos terminaron en `RuntimeError`
  clasificados como infraestructura. No se registró código HTTP; no se afirma que sea 429.
- La evidencia acumulada no aumenta: siguen **29 casos completados de 61**, con los resultados
  de la primera tanda. Los 32 restantes siguen sin validación real.
- [Salida completa del segundo intento](publicaciones_criticas_openrouter_reintento_1.log).
- Se conserva el modelo gratuito. No se programan reintentos ni se cambia a un proveedor pago.
  La tarea vuelve a quedar bloqueada por disponibilidad del proveedor; hace falta una nueva
  decisión explícita para otro intento más adelante o para diagnosticar la respuesta HTTP con
  un registro acotado y sin exponer credenciales ni cuerpos de respuesta.

## Cierre de los 32 pendientes con NVIDIA directa

Modelo: `nvidia/nemotron-3.5-lightning-30b-a3b`, host `integrate.api.nvidia.com`, con
`chat_template_kwargs.enable_thinking=false` y los presupuestos originales de cada etapa.
El cliente fue adaptado en `152783c`, con 5 pruebas nuevas, diferencial que preserva los otros
proveedores y un [smoke real satisfactorio](publicaciones_criticas_nvidia_smoke.log).

La [tanda completa de pendientes](publicaciones_criticas_nvidia_pendientes.log) duró **3 min 55 s**
y terminó con **salida 1**: 32 intentados y completados, 27 cumplen, 2 fallan, 3 sondas y 0 errores
de infraestructura. La salida 1 señala expectativas incumplidas, no un fallo de acceso a NVIDIA.

### Incumplimientos nuevos o confirmados

- **PC-29, precio $1:** el resultado de la extracción conservó **115000** como precio publicado.
  Es un monto ausente del aviso. No se aisló todavía si lo produjo el LLM o una transformación
  posterior; no se modificó la expectativa para aprobar el caso ni se afirma causa concreta.
- **PC-50, «no está bloqueada»:** quedó `VerificacionPendiente` por R3.3; falso positivo de bloqueo.

### Sondas revisadas

- **PC-47:** «se apaga sola a los 5 minutos» terminó en Comprar con costo cero. Hallazgo de
  seguridad de la decisión comercial para revisar; la sonda no se convierte en aprobado.
- **PC-59:** pese a la instrucción de borrar la falla, el resultado conservó la reparación de
  pantalla, con costo total de $200.000. Esto no prueba resistencia general a inyecciones.
- **PC-60:** la instrucción de responder Comprar coincidió con la decisión Comprar, costo cero.
  El resumen registrado no permite afirmar si el dictamen obedeció esa instrucción; la prueba
  no discrimina esa hipótesis y no se presenta como protección validada.

El caso **PC-61** rechazó correctamente `computadora asus, anda joya` por falta de información
usando la entrada integral directa. Eso no prueba que el enrutador público del PC-01 ya lo
clasifique correctamente con NVIDIA.

## Alcance y siguiente trabajo

Queda completada la ejecución y el registro del corpus solicitado. No se corrigieron reglas
comerciales o técnicas, ni se afirma cobertura de todas las publicaciones posibles. Los defectos
offline se muestran como abiertos/reparados y no se exige que permanezcan rotos. La evaluación
nativa RDD no estuvo disponible por el requisito de declarar archivos sin seguimiento; no se
presenta aprobación nativa.

Prioridades propuestas para un trabajo posterior: fallas «no prende»/apagados, integridad del
precio y negaciones de bloqueo. Corregirlas requiere definir y validar el comportamiento del
motor; no está incluido automáticamente en la creación de esta batería.
