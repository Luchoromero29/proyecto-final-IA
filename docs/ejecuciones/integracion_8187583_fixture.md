# Adaptación del fixture de mercado de la integración

Base: `8187583`, rama `integracion/mejoras-con-pruebas`. El resultado anterior de 69 pruebas con
31 errores se conserva en [el informe inicial](integracion_8187583_verificacion.md).

## Cambio y alcance

El fixture de `app/tests/test_publicaciones_criticas.py` ahora expone `valor_proc` y
`generacion_anterior`, como la consulta incorporada por el merge. Conserva precios propios y
`None` cuando no hay referencia. No simula la nueva inferencia R2.4. Se agregaron dos pruebas
para fijar la forma del resultado y los casos de valor propio, precio ausente y CPU desconocida.

No cambiaron código de producción, casos, expectativas ni precios de prueba.

## Evidencia RED/GREEN

Resultados informados por el worker `mwb02gc3-3-rv0r`; este archivo es un resumen, no stdout crudo.
Intérprete: `/home/alvaro/Universidad/IA/Proyecto/.venv/bin/python`, con `PYTHONDONTWRITEBYTECODE=1`.

| Comando | Resultado | Salida |
|---|---|---:|
| `app/tests/test_publicaciones_criticas.py ContratoMercadoTest -v`, antes del arreglo | 2 pruebas; 3 fallos y 1 error, por claves ausentes | 1 |
| Mismo comando, después del arreglo | 2/2 aprobadas | 0 |
| `-m unittest discover -s app/tests -v` | 71/71 aprobadas, 0,285 s | 0 |

El padre revisó el diff y `git diff --check` sin errores. No se repitió la suite para enumerar
resultados. La evaluación nativa devolvió `nativeRisk=unassessable` por archivos sin seguimiento;
el plan conserva la autoverificación del writer y no exige un verificador independiente para
este cambio de fixture. No hubo aprobación nativa.

## Límites

Las pruebas offline no prueban la carga actual de Neo4j ni el comportamiento del LLM real.
La cobertura del fixture no valida el fallback de generación anterior de R2.4. El corpus real
se ejecutará con evidencia separada después de resolver los prerrequisitos del grafo.

Risk: none — modificación acotada a fixture y pruebas, sin contratos de producción alterados.
