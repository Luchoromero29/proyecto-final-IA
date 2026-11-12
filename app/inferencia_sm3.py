#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SM3 — Inferencia de la operación en Neo4j (S9).

La aritmética financiera, la cuantización decimal, la política crisp de la operación, el
margen requerido, la contraoferta sugerida y el mapeo de la categoría difusa al tipo de
decisión se resuelven en consultas Cypher explícitas. Este módulo NO decide ni calcula
nada de negocio: no lee criterios para condicionar un resultado, no evalúa umbrales y no
redondea. Devuelve lo que el grafo resolvió.

La política del margen (pasos, condiciones, exclusión entre R3.4/R3.5 y operación
asignar/máximo/sumar de cada efecto) y la precisión de cada cuantización son DATOS del
grafo (`cypher/Grupo_20_PG3_politicas_bloque.cypher`). El mecanismo finito que los evalúa
son `_EVALUAR_CONDICIONES` (comparadores `=`, `<`, `>=`, `ausente`, `presente`; OR dentro
del grupo y AND entre grupos) y el cuantizador IEEE de `_cuantizar`.

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


def _cuantizar(valor: str, decimales, salida: str) -> str:
    """
    Fragmento Cypher que cuantiza `valor` con `decimales` (1, 2 o -3) y publica el
    resultado como `salida`. Es una utilidad numérica, no un motor de reglas: la expresión
    de entrada la escribe la consulta que la usa (texto fijo del módulo, nunca del aviso).

    `decimales` puede ser el literal de la política que todavía es mecanismo (RIE) o el
    nombre de una variable que la consulta leyó del grafo (`:PasoCalculo.decimales`).
    """
    # El subquery declara qué variables externas importa (cláusula de alcance de Neo4j 5).
    if isinstance(decimales, int):
        cabecera = f"CALL ({valor}) {{\n  WITH {valor} AS valor, {decimales} AS decimales\n"
    else:
        cabecera = (f"CALL ({valor}, {decimales}) {{\n"
                    f"  WITH {valor} AS valor, {decimales} AS decimales\n")
    return cabecera + _CUERPO_CUANTIZADOR + f"RETURN q AS {salida}\n}}\n"


# ------------------------------------------------------------------------------
# Mecanismo finito de evaluación de condiciones declaradas en el grafo
# ------------------------------------------------------------------------------
# Las etapas del bloque (margen de SM3, estado comercial de SM2 y clasificación final)
# declaran sus condiciones como datos: `campo` de un mapa de hechos, `operador` finito,
# operando literal o `CriterioExperto` enlazado, y el grupo de conjunción en `REQUIERE`.
# Un grupo se cumple con cualquiera de sus condiciones (OR) y la regla con todos sus
# grupos (AND), como en SM1; una regla sin condiciones se cumple siempre. El mapa de
# hechos y el operador son el mecanismo; qué campo, qué valor y qué grupo son política.
#
# Entrada: la variable `entrada` con `{reglas: [{regla, ...}], hechos: {...}}`.
# Salida: una fila por regla con `regla`, `datos`, `filas` y `cumplida`.
_EVALUAR_CONDICIONES = """
CALL (entrada) {
  UNWIND entrada.reglas AS candidata
  WITH candidata, candidata.regla AS regla
  OPTIONAL MATCH (regla)-[requiere:REQUIERE]->(cond:Condicion)
  OPTIONAL MATCH (cond)-[:USA_CRITERIO]->(criterio:CriterioExperto)
  WITH candidata, regla, requiere, cond, criterio,
       CASE WHEN cond IS NULL THEN null ELSE entrada.hechos[cond.campo] END AS valor
  WITH candidata, regla, requiere, cond, criterio, valor,
       CASE WHEN valor IS NULL THEN null
            WHEN valor IS :: INTEGER OR valor IS :: FLOAT THEN toFloat(valor) END AS numero,
       CASE WHEN cond.valor IS NOT NULL AND (cond.valor IS :: INTEGER OR cond.valor IS :: FLOAT)
            THEN toFloat(cond.valor)
            WHEN cond.valor IS NOT NULL THEN cond.valor END AS literal,
       CASE WHEN criterio.valor IS NOT NULL AND
                 (criterio.valor IS :: INTEGER OR criterio.valor IS :: FLOAT)
            THEN toFloat(criterio.valor) END AS operando
  WITH candidata, regla, requiere, cond, criterio, valor, numero,
       CASE WHEN cond IS NULL THEN null
            WHEN cond.operador = 'ausente' THEN valor IS NULL
            WHEN cond.operador = 'presente' THEN valor IS NOT NULL
            WHEN cond.operador = '=' THEN valor IS NOT NULL AND valor = cond.valor
            WHEN cond.operador = '<' THEN coalesce(numero < coalesce(literal, operando), false)
            WHEN cond.operador = '>=' THEN coalesce(numero >= coalesce(literal, operando), false)
            END AS cumplida
  WITH regla, head(collect(candidata)) AS datos,
       collect(CASE WHEN cond IS NULL THEN null ELSE
                 {grupo: requiere.grupo, cumplida: cumplida, campo: cond.campo,
                  criterio: criterio} END) AS crudos
  WITH regla, datos, [f IN crudos WHERE f IS NOT NULL] AS filas
  WITH regla, datos, filas, [f IN filas | f.grupo] AS grupos
  RETURN regla, datos, datos.orden AS orden, filas,
         all(g IN grupos WHERE any(f IN filas WHERE f.grupo = g AND f.cumplida)) AS cumplida
}
"""


# ------------------------------------------------------------------------------
# Consultas Cypher: toda la política y la aritmética financiera de SM3
# ------------------------------------------------------------------------------
# Los umbrales, márgenes y primas se leen de :CriterioExperto dentro de la consulta: el
# adapter Python nunca recibe un criterio para decidir, solo lo devuelve como procedencia.
# La política del margen (pasos, condiciones, exclusión y operación de cada efecto) y la
# precisión de cada cuantización se leen de la etapa (`VersionPoliticas`, `Regla`,
# `Condicion` y `PasoCalculo`): cambiar esos datos cambia el resultado sin editar Python.
# Un VMA igual a cero no se evalúa (la política anterior dividía por cero); se informa con
# el código `division_por_cero` y el adapter reproduce la misma excepción observable.
CONSULTA_CRISP = """
// SM3 — política crisp, aritmética y cuantización decimal resueltas en el grafo.
WITH toFloat($precio) AS precio, toFloat($costo_rep) AS costo, toFloat($vma) AS vma,
     toFloat($n_interv) AS n_interv, $riesgo AS riesgo, $demanda AS demanda
// Política de cálculo (I7): qué resultado se cuantiza, con qué precisión y cuál es el
// límite no negativo de la contraoferta son datos del grafo. La expresión aritmética de
// cada paso y el algoritmo IEEE del cuantizador siguen siendo mecanismo fijo.
CALL () {
  OPTIONAL MATCH (vp:VersionPoliticas {etapa:'SM3-calculo', activa:true})
  WITH collect(DISTINCT vp) AS hallados
  WITH size(hallados) AS n, CASE WHEN size(hallados) = 1 THEN hallados[0] END AS vp
  OPTIONAL MATCH (vp)-[:INCLUYE]->(paso:PasoCalculo)
  WITH n, vp, collect(DISTINCT paso) AS crudos
  WITH n, [p IN crudos WHERE p IS NOT NULL] AS pasos, coalesce(vp.ids_requeridos, []) AS requeridos
  WITH n, pasos, requeridos,
       [d IN ['margen_neto', 'ratio_reparacion', 'contraoferta', 'descuento', 'brecha']
        WHERE size([p IN pasos WHERE p.destino = d]) <> 1] AS destinos,
       [p IN pasos WHERE NOT p.decimales IN [1, 2, -3]] AS precisiones,
       [i IN requeridos WHERE NOT any(p IN pasos WHERE p.id = i)] AS faltantes,
       [p IN pasos WHERE p.destino = 'contraoferta' AND
        NOT (p.limite_inferior_ars IS :: INTEGER OR p.limite_inferior_ars IS :: FLOAT)] AS limites
  RETURN pasos,
    CASE WHEN n = 1 AND size(destinos) = 0 AND size(precisiones) = 0 AND size(faltantes) = 0
              AND size(limites) = 0 AND size(pasos) = size(requeridos)
         THEN [] ELSE ['configuración de cálculo de SM3: manifiesto, pasos, destino o '
                    + 'precisión de cuantización no válidos'] END AS problemas_calculo
}
WITH precio, costo, vma, n_interv, riesgo, demanda, problemas_calculo,
     head([p IN pasos WHERE p.destino = 'margen_neto']).decimales AS d_margen_neto,
     head([p IN pasos WHERE p.destino = 'ratio_reparacion']).decimales AS d_ratio,
     head([p IN pasos WHERE p.destino = 'contraoferta']).decimales AS d_contraoferta,
     head([p IN pasos WHERE p.destino = 'contraoferta']).limite_inferior_ars AS contraoferta_minima,
     head([p IN pasos WHERE p.destino = 'descuento']).decimales AS d_descuento,
     head([p IN pasos WHERE p.destino = 'brecha']).decimales AS d_brecha
WHERE size(problemas_calculo) = 0
WITH *, vma = 0.0 AS division_por_cero,
     CASE WHEN vma = 0.0 THEN null ELSE 100.0 * (vma - precio - costo) / vma END AS margen_bruto,
     CASE WHEN vma > 0 THEN costo / vma ELSE 0.0 END AS ratio_bruto
""" + _cuantizar("margen_bruto", "d_margen_neto", "margen_neto") + _cuantizar("ratio_bruto", "d_ratio", "ratio_reparacion") + """
// R3.7: el campo, el comparador y el criterio salen de la Regla existente y de su vínculo
// USA_CRITERIO. Configuración ausente/ambigua/inválida no produce fila (error explícito).
MATCH (r37:Regla {id:'R3.7'})
WITH *, [(r37)-[:USA_CRITERIO]->(c:CriterioExperto) | c] AS criterios37
WITH *, CASE WHEN size(criterios37) = 1 AND r37.filtro_campo = 'ratio_reparacion'
              AND r37.filtro_comparador IN ['>', '<']
             THEN criterios37[0] END AS ce37
WHERE ce37 IS NOT NULL AND ce37.valor IS NOT NULL
// R3.8: las categorías de riesgo y de demanda que disparan el descarte salen de la Regla
// existente y se validan contra los conjuntos que el grafo declara para cada variable difusa.
// Configuración ausente, ambigua o inválida no produce fila (mismo error explícito que R3.7).
MATCH (r38:Regla {id:'R3.8'})
WHERE r38.filtro_riesgo IS NOT NULL AND r38.filtro_demanda IS NOT NULL
  AND EXISTS { MATCH (:VariableDifusa {nombre:'Riesgo_Obsolescencia'})-[:TIENE_CONJUNTO]->
                     (:ConjuntoDifuso {etiqueta: r38.filtro_riesgo}) }
  AND EXISTS { MATCH (:VariableDifusa {nombre:'Demanda_Comercial'})-[:TIENE_CONJUNTO]->
                     (:ConjuntoDifuso {etiqueta: r38.filtro_demanda}) }
// R3.7 y luego R3.8: gana el primer filtro crisp que se cumple.
WITH *, CASE WHEN r37.filtro_comparador = '>' AND ratio_reparacion > toFloat(ce37.valor) THEN 'R3.7'
             WHEN r37.filtro_comparador = '<' AND ratio_reparacion < toFloat(ce37.valor) THEN 'R3.7'
             WHEN riesgo = r38.filtro_riesgo AND demanda = r38.filtro_demanda THEN 'R3.8' END AS regla_descarte
// Margen requerido: el manifiesto de la etapa, las reglas, sus condiciones (con su grupo),
// la exclusión, el destino y la operación de cada efecto son datos del grafo. La
// combinación asignar / máximo / sumar y el comparador son mecanismo finito.
CALL () {
  OPTIONAL MATCH (vp:VersionPoliticas {etapa:'SM3-margen', activa:true})
  WITH collect(DISTINCT vp) AS hallados
  WITH size(hallados) AS n, CASE WHEN size(hallados) = 1 THEN hallados[0] END AS vp
  OPTIONAL MATCH (vp)-[:INCLUYE]->(miembro)
  WITH n, vp, collect(DISTINCT miembro) AS crudos
  WITH n, vp, [m IN crudos WHERE m IS NOT NULL] AS miembros, coalesce(vp.ids_requeridos, []) AS requeridos
  OPTIONAL MATCH (vp)-[:INCLUYE]->(rm:Regla)
  OPTIONAL MATCH (rm)-[:USA_CRITERIO]->(ce:CriterioExperto)
  WITH n, miembros, requeridos, rm, collect(DISTINCT ce) AS criterios
  ORDER BY rm.prioridad_inferencia
  WITH n, miembros, requeridos,
       collect(CASE WHEN rm IS NULL THEN null ELSE
                 {regla: rm, orden: rm.prioridad_inferencia, destino: rm.efecto_destino,
                  operacion: rm.efecto_operacion, rol: rm.rol, exclusion: rm.grupo_exclusion,
                  traza: rm.traza_texto, criterios: criterios} END) AS crudos
  WITH n, miembros, requeridos, [c IN crudos WHERE c IS NOT NULL] AS reglas
  WITH n, miembros, requeridos, reglas,
       [i IN requeridos WHERE NOT any(m IN miembros WHERE m.id = i)] AS faltantes,
       [m IN miembros WHERE NOT m.id IN requeridos] AS ajenos,
       [r IN reglas WHERE r.orden IS NULL OR NOT r.orden IS :: INTEGER] AS sin_orden,
       [r IN reglas WHERE NOT coalesce(r.operacion, '') IN ['asignar', 'maximo', 'sumar']] AS operaciones,
       [r IN reglas WHERE NOT coalesce(r.destino, '') IN ['margen_paso1', 'margen_req']] AS destinos,
       [i IN range(0, size(requeridos) - 1)
        WHERE i > 0 AND any(j IN range(0, i - 1) WHERE requeridos[j] = requeridos[i])] AS repetidos
  WITH n, reglas, size(faltantes) + size(ajenos) + size(sin_orden) + size(operaciones)
       + size(destinos) + size(repetidos) AS errores,
       size(reglas) AS incluidas, size(requeridos) AS declaradas
  RETURN reglas,
    CASE WHEN n = 1 AND errores = 0 AND incluidas > 0 AND incluidas = declaradas
         THEN [] ELSE ['configuración del margen de SM3: manifiesto de etapa, reglas incluidas, '
                    + 'orden, destino u operación no válidos'] END AS problemas_margen
}
WITH *, {reglas: reglas, hechos: {riesgo: riesgo, demanda: demanda, n_interv: n_interv}} AS entrada
""" + _EVALUAR_CONDICIONES + """
WITH * ORDER BY orden
// Se agrega una fila por regla evaluada, en el orden de prioridad declarado; la lista
// explícita evita arrastrar los candidatos.
WITH precio, costo, vma, n_interv, riesgo, demanda, problemas_calculo,
     d_margen_neto, d_ratio, d_contraoferta, contraoferta_minima, d_descuento, d_brecha,
     division_por_cero, margen_bruto, ratio_bruto, margen_neto, ratio_reparacion,
     ce37, r38, regla_descarte, problemas_margen,
     collect({regla: regla, datos: datos, filas: filas, cumplida: cumplida,
              efectos: [c IN datos.criterios
                         WHERE NOT any(f IN filas
                                       WHERE f.criterio IS NOT NULL AND f.criterio = c)]})
        AS evaluadas_margen
WITH *, [e IN evaluadas_margen WHERE e.cumplida] AS aplicables_margen,
     [e IN evaluadas_margen WHERE size(e.efectos) <> 1] AS efecto_ambiguo,
     [e IN evaluadas_margen
      WHERE any(f IN e.filas WHERE NOT f.campo IN ['riesgo', 'demanda', 'n_interv'])] AS campos_ajenos
WITH *, [e IN aplicables_margen WHERE e.datos.exclusion IS NOT NULL] AS excluyentes
WITH *, [e IN excluyentes WHERE any(o IN excluyentes WHERE o.regla.id <> e.regla.id
                                     AND o.datos.exclusion = e.datos.exclusion)] AS conflictos_margen,
     [e IN aplicables_margen
      WHERE NOT (e.efectos[0].valor IS :: INTEGER OR e.efectos[0].valor IS :: FLOAT)] AS valores_invalidos
WITH *, [e IN aplicables_margen WHERE e.datos.destino = 'margen_paso1'] AS pasos1,
     [e IN aplicables_margen WHERE e.datos.destino = 'margen_req'] AS pasos_req,
     CASE WHEN size(problemas_margen) = 0 AND size(efecto_ambiguo) = 0 AND size(campos_ajenos) = 0
              AND size(conflictos_margen) = 0 AND size(valores_invalidos) = 0
          THEN [] ELSE ['configuración del margen de SM3: efectos, criterios, hechos, valores '
                     + 'o exclusión no válidos'] END AS problemas_margen_total
WHERE size(problemas_margen_total) = 0
// Paso 0 y paso 1 (R3.4 o R3.5, excluyentes entre sí), en orden de prioridad declarado.
WITH *, reduce(acc = null, e IN pasos1 |
       CASE e.datos.operacion
         WHEN 'asignar' THEN e.efectos[0].valor * 1.0
         WHEN 'maximo' THEN CASE WHEN acc IS NULL THEN e.efectos[0].valor * 1.0
                                 WHEN e.efectos[0].valor * 1.0 > acc THEN e.efectos[0].valor * 1.0
                                 ELSE acc END
         WHEN 'sumar' THEN acc + e.efectos[0].valor * 1.0 END) AS margen_paso1_datos
WITH *, CASE WHEN regla_descarte IS NOT NULL THEN null ELSE margen_paso1_datos END AS margen_paso1
// Paso 2 (R3.6): se combina sobre el margen del paso anterior según la operación declarada.
WITH *, CASE WHEN margen_paso1 IS NULL THEN null ELSE
       reduce(acc = margen_paso1, e IN pasos_req |
         CASE e.datos.operacion
           WHEN 'asignar' THEN e.efectos[0].valor * 1.0
           WHEN 'maximo' THEN CASE WHEN e.efectos[0].valor * 1.0 > acc THEN e.efectos[0].valor * 1.0
                                   ELSE acc END
           WHEN 'sumar' THEN acc + e.efectos[0].valor * 1.0 END) END AS margen_req
// Contraoferta: VMA − costo − margen requerido, redondeada a miles.
WITH *, CASE WHEN margen_req IS NULL THEN null
             ELSE vma - costo - vma * margen_req / 100.0 END AS contraoferta_bruta
""" + _cuantizar("contraoferta_bruta", "d_contraoferta", "contraoferta_redondeada") + """
// Nunca por debajo del límite que declara el paso de cálculo (hoy cero): el redondeo no
// convierte la oferta en negativa.
WITH *, CASE WHEN contraoferta_bruta IS NULL THEN null
             WHEN contraoferta_redondeada > contraoferta_minima THEN contraoferta_redondeada
             ELSE contraoferta_minima END AS contraoferta
// Descuento a pedir sobre el precio publicado: solo tiene sentido si la contraoferta es menor.
WITH *, CASE WHEN contraoferta IS NULL THEN null
             WHEN contraoferta < precio THEN 100.0 * (precio - contraoferta) / precio
             ELSE null END AS descuento_bruto,
       CASE WHEN margen_req IS NULL THEN null ELSE margen_neto - margen_req END AS brecha_bruta
""" + _cuantizar("descuento_bruto", "d_descuento", "descuento_cuantizado") + _cuantizar("brecha_bruta", "d_brecha", "brecha") + """
WITH *, CASE WHEN contraoferta IS NULL THEN null
             WHEN descuento_cuantizado IS NULL THEN 0.0
             ELSE descuento_cuantizado END AS descuento
// Procedencia: los criterios que usó efectivamente la rama aplicada, en su orden de lectura
// (base del margen, paso 1 aplicado, umbrales de la etapa y prima del paso 2 si se aplicó).
WITH *, [e IN aplicables_margen WHERE e.datos.destino = 'margen_paso1' AND e.datos.rol = 'base'
         | e.efectos[0]] AS criterios_base,
     [e IN aplicables_margen WHERE e.datos.destino = 'margen_paso1'
                               AND coalesce(e.datos.rol, '') <> 'base' | e.efectos[0]] AS criterios_paso1,
     reduce(acc = [], grupo IN [e IN evaluadas_margen WHERE e.datos.destino = 'margen_req' | e.filas] |
            acc + [f IN grupo WHERE f.criterio IS NOT NULL | f.criterio]) AS criterios_umbral,
     [e IN aplicables_margen WHERE e.datos.destino = 'margen_req' | e.efectos[0]] AS criterios_requerido
WITH *, CASE WHEN regla_descarte IS NOT NULL THEN [ce37]
             ELSE [ce37] + criterios_base + criterios_paso1 + criterios_umbral + criterios_requerido
        END AS criterios
// Traza: el texto de cada regla aplicada viene de la Regla, en orden de prioridad.
WITH *, CASE WHEN regla_descarte = 'R3.7' THEN ['R3.7: costo / VMA > CE ratio_reparacion_max → DescartarPorRiesgo']
             WHEN regla_descarte = 'R3.8'
             THEN ['R3.8: riesgo ' + r38.filtro_riesgo + ' y demanda ' + r38.filtro_demanda + ' → DescartarPorRiesgo']
             ELSE [e IN aplicables_margen WHERE e.datos.traza IS NOT NULL | e.datos.traza]
        END AS reglas_activadas
RETURN CASE WHEN regla_descarte IS NULL THEN null ELSE 'DescartarPorRiesgo' END AS decision,
       regla_descarte AS regla,
       margen_neto, ratio_reparacion, margen_req, brecha, descuento, contraoferta,
       toFloat(ce37.valor) AS ratio_max,
       division_por_cero,
       reglas_activadas,
       [c IN criterios | {nombre: c.nombre, id: c.id, valor: c.valor, unidad: c.unidad,
                          version: c.version, estado: c.estado_validacion}] AS criterios
"""

# Correspondencia y habilitación leídas del conjunto existente, no elegidas por categoría.
# La lista de tipos admitidos valida el contrato público; no asigna una decisión a un nombre.
# Configuración ausente/ambigua/inválida conserva la fila nula que rechaza el orquestador.
CONSULTA_DECISION = """
WITH $categoria AS categoria, toFloat($contraoferta) AS contraoferta
OPTIONAL MATCH (:VariableDifusa {nombre:'Conveniencia'})-[:TIENE_CONJUNTO]->(c:ConjuntoDifuso)
WHERE c.etiqueta = categoria
WITH contraoferta, collect(c) AS conjuntos
WITH contraoferta, CASE WHEN size(conjuntos)=1 THEN head(conjuntos) END AS candidato
WITH contraoferta, CASE WHEN candidato.representacion_version = 'politicas-P1-v1'
       AND candidato.resultado_decision IN ['Comprar', 'ComprarConOfertaMenor', 'DescartarPorRiesgo']
       AND candidato.contraoferta_habilitada IN [true, false] THEN candidato END AS conocimiento
RETURN conocimiento.resultado_decision AS decision,
       CASE WHEN conocimiento.contraoferta_habilitada THEN contraoferta END AS contraoferta_sugerida_ars
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
    Lee la decisión y la habilitación de contraoferta del conjunto difuso de SM3-CONV.
    Sin correspondencia válida devuelve la fila nula; sin respuesta del driver, None.
    """
    return _una_fila(driver, base, CONSULTA_DECISION,
                     {"categoria": categoria, "contraoferta": contraoferta})
