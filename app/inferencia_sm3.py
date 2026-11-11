#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SM3 — Inferencia de la operación en Neo4j (S9).

La aritmética financiera, la cuantización decimal, la política crisp de la operación, el
margen requerido, la contraoferta sugerida y el mapeo de la categoría difusa al tipo de
decisión se resuelven en consultas Cypher explícitas. Este módulo NO decide ni calcula
nada de negocio: no lee criterios para condicionar un resultado, no evalúa umbrales y no
redondea. Devuelve lo que el grafo resolvió.

Consultas:
  - `inferir_sm3_crisp_cypher`: R3.7 y R3.8 (en ese orden), pasos 0/1/2 del margen
    requerido (base → R3.4 o R3.5 → R3.6), contraoferta, brecha y descuento. Devuelve los
    criterios usados (procedencia) y las reglas activadas en su orden de aplicación.
  - `resolver_decision_sm3_cypher`: mapea la categoría difusa de SM3-CONV al tipo de
    decisión del dominio y habilita la contraoferta solo cuando toca negociar.

La difusa SM3-CONV se sigue evaluando con `inferir_sm3_conv_cypher` del orquestador
(Mamdani en Cypher): no se duplica la base de reglas difusas.
"""

# ------------------------------------------------------------------------------
# Cuantización decimal: la misma que aplicaba la política escrita en Python
# ------------------------------------------------------------------------------
# `round(x, decimales)` de Python redondea el valor binario IEEE-754 exacto (medio al par),
# mientras que `round()` de Cypher redondea la representación decimal y no coincide en los
# empates decimales inexactos (por ejemplo `round(6.55, 1)`: 6.5 en Python, 6.6 en Cypher).
# Para conservar las decisiones y los importes sin cálculo en Python, la cuantización se
# resuelve con aritmética entera explícita en la consulta:
#
#   1. Se descartan los casos triviales: null, cero (conservando su signo) y valores por
#      debajo de medio cuanto, que redondean a cero con el signo del valor.
#   2. El valor absoluto se normaliza como `m · 2^(est − 52)`, con `est` deducido por
#      logaritmo y corregido comparando con la potencia efectiva; el escalado por potencias
#      de dos no pierde bits, así que `m` es la mantisa entera exacta de 53 bits.
#   3. `valor · 10^decimales = numerador · 2^dos / denominador`, todo entero
#      (`denominador` = 125 cuando se redondea a miles, o sea decimales negativos).
#   4. Se divide con enteros, se compara el resto con la mitad del divisor y se desempata
#      al par (medio al par). Si el valor ya es múltiplo exacto del cuanto, se devuelve tal
#      cual, sin pasar por la división en punto flotante.
#
# Verificado contra `round()` de Python (ver docs/DECISION_NEO4J.md) con importes,
# ratios, subnormales y magnitudes grandes hasta 1,7e308. El atajo ULP >= cuanto evita
# la pérdida de dígitos y el overflow que expusieron los primeros ensayos. Las matrices
# cubren valores y fronteras, no constituyen una prueba exhaustiva de todos los doubles.
# SM2-RIE reutiliza este fragmento para entregar a demanda un riesgo ya cuantizado:
# no es sólo presentación cuando un score alimenta otra inferencia.
_CUERPO_CUANTIZADOR = """
WITH valor, decimales,
     CASE WHEN valor IS NULL OR valor = 0.0 THEN null ELSE abs(valor) END AS a,
     CASE WHEN valor IS NULL OR valor = 0.0 THEN 0 WHEN valor < 0 THEN -1 ELSE 1 END AS signo
WITH valor, decimales, a, signo,
     CASE WHEN a IS NULL THEN null ELSE toInteger(floor(log(a) / log(2.0))) END AS e0
WITH valor, decimales, a, signo, e0,
     CASE WHEN a IS NULL THEN null
          WHEN a >= 2.0 ^ (e0 + 1) THEN e0 + 1
          WHEN a < 2.0 ^ e0 THEN e0 - 1
          ELSE e0 END AS est
WITH valor, decimales, a, signo, est,
     (est IS NOT NULL AND est < -60) AS diminuto
// Si la separación binaria 2^(est − 52) ya es mayor o igual al cuanto decimal (0,1 / 0,01 /
// 1.000), la cuantización mueve el valor menos de medio cuanto y el double representable más
// cercano al resultado decimal es el propio valor. Tampoco hay empates posibles: con 1 o 2
// decimales, `ulp >= 10^-decimales` obliga a que `valor · 10^decimales` no pueda ser un
// semientero; con miles, `ulp >= 1000` obliga a que el valor sea múltiplo de 1024 y 500 no
// lo es. Por eso se devuelve el valor antes de cualquier cuenta que pueda desbordar enteros.
WITH valor, decimales, a, signo, est, diminuto,
     CASE WHEN est IS NULL THEN null
          ELSE 2.0 ^ (est - 52) >= (CASE decimales WHEN 1 THEN 0.1 WHEN 2 THEN 0.01 ELSE 1000.0 END)
     END AS ya_representable
WITH valor, decimales, a, signo, est, diminuto, ya_representable,
     CASE WHEN a IS NULL OR diminuto OR ya_representable THEN null
          ELSE toInteger(a * 2.0 ^ (52 - est)) END AS m,
     CASE WHEN a IS NULL OR diminuto OR ya_representable THEN null
          ELSE est - 52 + decimales END AS dos
WITH valor, decimales, signo, m, dos, diminuto, ya_representable,
     CASE decimales WHEN 2 THEN abs(m) * 25 WHEN 1 THEN abs(m) * 5 ELSE abs(m) END AS numerador,
     CASE decimales WHEN -3 THEN 125 ELSE 1 END AS denominador
WITH valor, decimales, signo, m, dos, numerador, denominador, diminuto, ya_representable,
     CASE WHEN m IS NULL THEN null WHEN decimales >= 0 AND dos >= 0 THEN true ELSE false END AS exacto,
     CASE WHEN diminuto THEN true
          WHEN m IS NULL THEN null
          WHEN decimales < 0 THEN -dos >= 48
          ELSE -dos >= 63 END AS cero
WITH valor, decimales, signo, dos, numerador, denominador, exacto, cero, ya_representable,
     CASE WHEN exacto OR cero THEN null
          WHEN dos > 0 THEN numerador * toInteger(2.0 ^ dos)
          ELSE numerador END AS numerador2,
     CASE WHEN exacto OR cero THEN null
          WHEN dos > 0 THEN denominador
          ELSE denominador * toInteger(2.0 ^ -dos) END AS divisor
WITH valor, decimales, signo, exacto, cero, ya_representable, numerador2, divisor,
     CASE WHEN divisor IS NULL THEN 0 ELSE numerador2 / divisor END AS cuociente
WITH valor, decimales, signo, exacto, cero, ya_representable, cuociente, divisor,
     CASE WHEN divisor IS NULL THEN null ELSE numerador2 - cuociente * divisor END AS resto
WITH valor, decimales, signo, exacto, cero, ya_representable, cuociente, resto, divisor,
     CASE WHEN divisor IS NULL OR divisor = 0 THEN 0
          WHEN 2 * resto > divisor THEN 1
          WHEN 2 * resto = divisor AND cuociente % 2 = 1 THEN 1
          ELSE 0 END AS incremento
WITH valor, decimales, signo, exacto, cero, ya_representable, resto, cuociente + incremento AS entero,
     (resto = 0) AS multiplo_exacto,
     CASE decimales WHEN 1 THEN 10.0 WHEN 2 THEN 100.0 ELSE 1000.0 END AS escala
WITH CASE WHEN valor IS NULL THEN null
          WHEN valor = 0.0 THEN valor
          WHEN ya_representable THEN valor
          WHEN cero THEN (CASE WHEN signo < 0 THEN -0.0 ELSE 0.0 END)
          WHEN exacto OR multiplo_exacto THEN valor
          WHEN entero = 0 THEN (CASE WHEN signo < 0 THEN -0.0 ELSE 0.0 END)
          WHEN decimales < 0 THEN toFloat(signo * entero) * escala
          ELSE toFloat(signo * entero) / escala END AS q
"""


def _cuantizar(valor: str, decimales: int, salida: str) -> str:
    """
    Fragmento Cypher que cuantiza `valor` con `decimales` (1, 2 o -3) y publica el
    resultado como `salida`. Es una utilidad numérica, no un motor de reglas: la expresión
    de entrada la escribe la consulta que la usa (texto fijo del módulo, nunca del aviso).
    """
    # El subquery declara qué variable externa importa (cláusula de alcance de Neo4j 5).
    return (f"CALL ({valor}) {{\n  WITH {valor} AS valor, {decimales} AS decimales\n"
            + _CUERPO_CUANTIZADOR + f"RETURN q AS {salida}\n}}\n")


# ------------------------------------------------------------------------------
# Consultas Cypher: toda la política y la aritmética financiera de SM3
# ------------------------------------------------------------------------------
# Los umbrales, márgenes y primas se leen de :CriterioExperto dentro de la consulta: el
# adapter Python nunca recibe un criterio para decidir, solo lo devuelve como procedencia.
# Un VMA igual a cero no se evalúa (la política anterior dividía por cero); se informa con
# el código `division_por_cero` y el adapter reproduce la misma excepción observable.
CONSULTA_CRISP = """
// SM3 — política crisp, aritmética y cuantización decimal resueltas en el grafo.
WITH toFloat($precio) AS precio, toFloat($costo_rep) AS costo, toFloat($vma) AS vma,
     toFloat($n_interv) AS n_interv, $riesgo AS riesgo, $demanda AS demanda
MATCH (cr:CriterioExperto {nombre: 'ratio_reparacion_max'})
MATCH (cmb:CriterioExperto {nombre: 'margen_base'})
MATCH (cal:CriterioExperto {nombre: 'margen_alta_liquidez'})
MATCH (cra:CriterioExperto {nombre: 'margen_riesgo_alto'})
MATCH (cum:CriterioExperto {nombre: 'umbral_intervenciones'})
MATCH (cpf:CriterioExperto {nombre: 'prima_fallas'})
WITH cr, cmb, cal, cra, cum, cpf, precio, costo, vma, n_interv, riesgo, demanda,
     vma = 0.0 AS division_por_cero,
     CASE WHEN vma = 0.0 THEN null ELSE 100.0 * (vma - precio - costo) / vma END AS margen_bruto,
     CASE WHEN vma > 0 THEN costo / vma ELSE 0.0 END AS ratio_bruto
""" + _cuantizar("margen_bruto", 1, "margen_neto") + _cuantizar("ratio_bruto", 2, "ratio_reparacion") + """
// R3.7 y luego R3.8: gana el primer filtro crisp que se cumple.
WITH *, CASE WHEN ratio_reparacion > toFloat(cr.valor) THEN 'R3.7'
             WHEN riesgo = 'Alto' AND demanda = 'Baja' THEN 'R3.8' END AS regla_descarte
// Margen requerido: paso 0 (base), paso 1 (R3.4 o R3.5, excluyentes), paso 2 (R3.6).
WITH *, CASE WHEN regla_descarte IS NOT NULL THEN null
             WHEN demanda = 'Alta' AND riesgo = 'Bajo' THEN toFloat(cal.valor)
             WHEN riesgo = 'Alto' THEN CASE WHEN toFloat(cra.valor) > toFloat(cmb.valor) THEN toFloat(cra.valor) ELSE toFloat(cmb.valor) END
             ELSE toFloat(cmb.valor) END AS margen_paso1
WITH *, CASE WHEN margen_paso1 IS NULL THEN null
             WHEN n_interv >= toFloat(cum.valor) THEN margen_paso1 + toFloat(cpf.valor)
             ELSE margen_paso1 END AS margen_req
// Contraoferta: VMA − costo − margen requerido, redondeada a miles.
WITH *, CASE WHEN margen_req IS NULL THEN null
             ELSE vma - costo - vma * margen_req / 100.0 END AS contraoferta_bruta
""" + _cuantizar("contraoferta_bruta", -3, "contraoferta_redondeada") + """
// Nunca negativa: un redondeo por debajo de cero se informa como cero.
WITH *, CASE WHEN contraoferta_bruta IS NULL THEN null
             WHEN contraoferta_redondeada > 0 THEN contraoferta_redondeada
             ELSE 0.0 END AS contraoferta
// Descuento a pedir sobre el precio publicado: solo tiene sentido si la contraoferta es menor.
WITH *, CASE WHEN contraoferta IS NULL THEN null
             WHEN contraoferta < precio THEN 100.0 * (precio - contraoferta) / precio
             ELSE null END AS descuento_bruto,
       CASE WHEN margen_req IS NULL THEN null ELSE margen_neto - margen_req END AS brecha_bruta
""" + _cuantizar("descuento_bruto", 1, "descuento_cuantizado") + _cuantizar("brecha_bruta", 1, "brecha") + """
WITH *, CASE WHEN contraoferta IS NULL THEN null
             WHEN descuento_cuantizado IS NULL THEN 0.0
             ELSE descuento_cuantizado END AS descuento
// Procedencia: los criterios que usó efectivamente la rama aplicada, en su orden de lectura.
WITH *, CASE WHEN regla_descarte IS NOT NULL THEN [cr]
             ELSE [cr, cmb]
                  + CASE WHEN demanda = 'Alta' AND riesgo = 'Bajo' THEN [cal]
                         WHEN riesgo = 'Alto' THEN [cra] ELSE [] END
                  + [cum]
                  + CASE WHEN n_interv >= toFloat(cum.valor) THEN [cpf] ELSE [] END
        END AS criterios
// Traza: el texto de cada regla aplicada, tal como se informa en el dictamen.
WITH *, CASE WHEN regla_descarte = 'R3.7' THEN ['R3.7: costo / VMA > CE ratio_reparacion_max → DescartarPorRiesgo']
             WHEN regla_descarte = 'R3.8' THEN ['R3.8: riesgo Alto y demanda Baja → DescartarPorRiesgo']
             ELSE [] + CASE WHEN demanda = 'Alta' AND riesgo = 'Bajo'
                            THEN ['R3.4: demanda Alta y riesgo Bajo → margen requerido = CE margen_alta_liquidez']
                            WHEN riesgo = 'Alto'
                            THEN ['R3.5: riesgo Alto → margen requerido = máx(margen, CE margen_riesgo_alto)']
                            ELSE [] END
                  + CASE WHEN n_interv >= toFloat(cum.valor)
                         THEN ['R3.6: intervenciones ≥ CE umbral_intervenciones → + CE prima_fallas']
                         ELSE [] END
        END AS reglas_activadas
RETURN CASE WHEN regla_descarte IS NULL THEN null ELSE 'DescartarPorRiesgo' END AS decision,
       regla_descarte AS regla,
       margen_neto, ratio_reparacion, margen_req, brecha, descuento, contraoferta,
       toFloat(cr.valor) AS ratio_max,
       division_por_cero,
       reglas_activadas,
       [c IN criterios | {nombre: c.nombre, id: c.id, valor: c.valor, unidad: c.unidad,
                          version: c.version, estado: c.estado_validacion}] AS criterios
"""

# Mapeo de la categoría difusa de SM3-CONV al tipo de decisión del dominio. Está declarado
# en la consulta (inferencia), no en Python; la contraoferta solo se informa al negociar.
# El grafo no representa hoy esta correspondencia como relación (ver docs/DECISION_NEO4J.md).
CONSULTA_DECISION = """
WITH $categoria AS categoria, toFloat($contraoferta) AS contraoferta
RETURN CASE categoria WHEN 'Comprar' THEN 'Comprar'
                      WHEN 'Negociar' THEN 'ComprarConOfertaMenor'
                      WHEN 'Descartar' THEN 'DescartarPorRiesgo' END AS decision,
       CASE WHEN categoria = 'Negociar' THEN contraoferta END AS contraoferta_sugerida_ars
"""


def _una_fila(driver, base: str, consulta: str, parametros: dict) -> dict:
    """
    Ejecuta la consulta y devuelve su única fila como dict, o None si no respondió.

    El driver y la base llegan como parámetros explícitos desde el orquestador: así una
    prueba puede inyectar un Neo4j aislado sin reemplazar la configuración del motor.
    """
    if not driver:
        return None
    with driver.session(database=base) as sesion:
        fila = sesion.run(consulta, **parametros).single()
    return dict(fila) if fila else None


def inferir_sm3_crisp_cypher(driver, base: str, precio: float, costo_rep: float, vma: float,
                             n_interv: int, riesgo: str, demanda: str) -> dict:
    """
    Política crisp de SM3 resuelta en Neo4j: margen neto y ratio de reparación
    cuantizados, R3.7, R3.8, margen requerido (base → R3.4 o R3.5 → R3.6), contraoferta,
    brecha y descuento.

    Devuelve la decisión y la regla aplicada cuando corresponde descartar, los criterios
    usados con su procedencia y las reglas activadas en orden. Devuelve None si el grafo
    no responde o falta algún criterio de la política.
    """
    return _una_fila(driver, base, CONSULTA_CRISP, {
        "precio": precio, "costo_rep": costo_rep, "vma": vma, "n_interv": n_interv,
        "riesgo": riesgo, "demanda": demanda,
    })


def resolver_decision_sm3_cypher(driver, base: str, categoria: str, contraoferta: float) -> dict:
    """
    Traduce la categoría difusa de SM3-CONV al tipo de decisión y habilita la contraoferta
    solo cuando la decisión es negociar. Devuelve None si el grafo no responde.
    """
    return _una_fila(driver, base, CONSULTA_DECISION,
                     {"categoria": categoria, "contraoferta": contraoferta})
