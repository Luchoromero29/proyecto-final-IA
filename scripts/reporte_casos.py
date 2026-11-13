#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera docs/PRUEBAS_PUBLICACIONES.md: los 61 casos críticos con su propósito y el
veredicto de la última corrida registrada.

El corpus (app/tests/casos_publicaciones.json) dice qué es cada caso y qué se espera.
El log de la corrida dice qué pasó la última vez. Este script los cruza para que nadie
tenga que leer JSON y logs a mano.

Uso, desde la raíz del repositorio:

    python scripts/reporte_casos.py                       # usa el log más reciente
    python scripts/reporte_casos.py --log docs/ejecuciones/<archivo>.log
    python scripts/reporte_casos.py --salida otro.md

No llama al LLM, no abre Neo4j y no ejecuta casos: sólo lee archivos.
"""

import argparse
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CORPUS_PATH = RAIZ / "app" / "tests" / "casos_publicaciones.json"
EJECUCIONES = RAIZ / "docs" / "ejecuciones"
SALIDA_POR_DEFECTO = RAIZ / "docs" / "PRUEBAS_PUBLICACIONES.md"

ETIQUETAS = {
    "aceptacion": "aceptación",
    "caracterizacion": "caracterización",
    "defecto_conocido": "defecto conocido",
    "sonda": "sonda",
}

INICIO_CASO = re.compile(r"^\[(PC-\d+)\]\s+(.*?)\s+\((.*?)\s*·\s*(.*?)\)\s*$")
CAMPO = re.compile(r"^\s{2}([a-záéíóúñ_]+):\s?(.*)$")
VEREDICTOS = (
    ("✔", "cumple"),
    ("✘", "no cumple"),
    ("SONDA", "sonda"),
)


def cargar_casos():
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["casos"]


def log_mas_reciente():
    logs = sorted(EJECUCIONES.glob("*61*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[0] if logs else None


def parsear_log(ruta):
    """Devuelve (resultados por id, resumen de cierre, proveedor y base declarados)."""
    resultados, resumen, proveedor, base = {}, "", "", ""
    actual = None
    for linea in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
        if linea.startswith("LLM configurado:") and not proveedor:
            proveedor = linea.split(":", 1)[1].strip()
        elif linea.startswith("Neo4j:") and not base:
            base = linea.split(":", 1)[1].strip()
        elif "Casos intentados:" in linea:
            resumen = linea.strip()
        m = INICIO_CASO.match(linea)
        if m:
            actual = m.group(1)
            resultados[actual] = {"observado": "", "esperado": "", "sonda": "", "veredicto": ""}
            continue
        if actual is None or linea.startswith("[") or not linea.strip():
            if not linea.strip():
                actual = None
            continue
        if any(marca in linea for marca, _ in VEREDICTOS):
            for marca, valor in VEREDICTOS:
                if marca in linea:
                    resultados[actual]["veredicto"] = valor
                    break
            continue
        m = CAMPO.match(linea)
        if m:
            clave, valor = m.group(1), m.group(2).strip()
            if clave in resultados[actual]:
                resultados[actual][clave] = valor
            elif clave == "esperado":
                resultados[actual]["esperado"] = valor
    return resultados, resumen, proveedor, base


def limpiar(texto):
    return (texto or "").replace("|", r"\|").strip()


def generar(casos, resultados, resumen, proveedor, base, origen):
    partes = [
        "# Casos críticos de publicaciones",
        "",
        "> Documento generado por `scripts/reporte_casos.py`. No lo edites a mano: se regenera",
        "> cruzando el corpus (`app/tests/casos_publicaciones.json`), que dice qué es cada caso y",
        "> qué se espera, con el log de la última corrida, que dice qué pasó.",
        "",
        "## Última corrida registrada",
        "",
        f"- **Log**: `{origen}`",
        f"- **Resultado**: {resumen or 'sin resumen en el log'}",
        f"- **Proveedor LLM**: {proveedor or 'no declarado en el log'}",
        f"- **Base usada**: {base or 'no declarada en el log'}",
        "",
        "Las sondas no se cuentan como aprobadas ni fallidas: son casos sin expectativa",
        "acordada y se revisan a mano (ver el final de este documento).",
        "",
        "La base indicada es la que usó esa corrida. Si después las mismas semillas se",
        "promovieron a otra base, la equivalencia queda registrada en el guardas JSON de esa",
        "promoción, no acá.",
        "",
        "## Los 61 casos",
        "",
        "| Caso | Grupo | Clasificación | Propósito | Última corrida |",
        "|---|---|---|---|---|",
    ]
    for caso in casos:
        r = resultados.get(caso["id"], {})
        partes.append(
            "| {id} | {grupo} | {clasif} | {proposito} | {veredicto} |".format(
                id=caso["id"],
                grupo=limpiar(caso["grupo"]),
                clasif=ETIQUETAS.get(caso["clasificacion"], caso["clasificacion"]),
                proposito=limpiar(caso["titulo"]),
                veredicto=r.get("veredicto") or "sin registro",
            )
        )

    sondas = [c for c in casos if c["clasificacion"] == "sonda"]
    partes += [
        "",
        "## Sondas: qué queda por decidir",
        "",
        f"Son {len(sondas)} casos sin expectativa automática. Convertir una sonda en aceptación",
        "es acordar el comportamiento correcto, respaldarlo con el experto si corresponde y",
        "recién entonces agregarle su `espera` en el corpus.",
    ]
    for caso in sondas:
        r = resultados.get(caso["id"], {})
        partes += [
            "",
            f"### {caso['id']} — {limpiar(caso['titulo']).removeprefix('Sonda: ')}",
            "",
            f"- **Pregunta**: {limpiar(caso.get('sonda', 'sin pregunta registrada'))}",
            f"- **Observado en la última corrida**: {limpiar(r.get('observado')) or 'sin registro'}",
            f"- **Por qué importa**: {limpiar(caso.get('por_que_critico', 'sin nota'))}",
        ]

    faltantes = [c["id"] for c in casos if c["id"] not in resultados]
    partes += ["", "## Cobertura del log", ""]
    if faltantes:
        partes.append(
            "El log no registra estos casos del corpus: " + ", ".join(faltantes) + ". "
            "Una corrida completa tiene los 61."
        )
    else:
        partes.append("El log registra los 61 casos del corpus, sin omisiones.")

    partes += [
        "",
        "## Cómo se regenera",
        "",
        "```bash",
        "python scripts/probar_publicaciones.py --ejecutar   # deja el log en docs/ejecuciones/",
        "python scripts/reporte_casos.py                     # regenera este documento",
        "```",
        "",
    ]
    return "\n".join(partes)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--log", help="log de corrida a usar (por defecto, el más reciente)")
    parser.add_argument("--salida", default=str(SALIDA_POR_DEFECTO), help="documento a escribir")
    args = parser.parse_args()

    origen = Path(args.log) if args.log else log_mas_reciente()
    if origen is None or not origen.is_file():
        raise SystemExit("[reporte] no encontré ningún log de corrida en docs/ejecuciones/")
    resultados, resumen, proveedor, base = parsear_log(origen)
    casos = cargar_casos()
    if not resultados:
        raise SystemExit(f"[reporte] el log {origen.name} no tiene bloques de casos")

    salida = Path(args.salida)
    salida.write_text(
        generar(casos, resultados, resumen, proveedor, base, origen.name), encoding="utf-8"
    )
    print(f"[reporte] {salida.relative_to(RAIZ)}: {len(casos)} casos, {len(resultados)} con registro")


if __name__ == "__main__":
    main()
