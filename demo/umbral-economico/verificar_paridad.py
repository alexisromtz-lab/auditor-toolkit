#!/usr/bin/env python3
"""Mide si el motor del navegador sigue dando exactamente lo que da el oráculo.

Tres cosas distintas, y las tres tienen que pasar:

1. **El fixture sigue siendo el que el oráculo produce.** Si alguien toca
   `umbral.py` y no regenera, el contrato se queda midiendo un motor que ya no
   existe: RC 5.
2. **La página embebe el cuerpo de `motor.js` carácter por carácter.** Dos copias
   libres del mismo motor divergen en silencio; aquí divergir es RC 7.
3. **Cada estado del fixture sale idéntico en node.** Sin tolerancia: este motor
   no tiene una sola operación transcendente, así que no hay nada que redondear.
   El único término no exacto es `potencia`, y usa la misma secuencia de
   multiplicaciones que Python: IEEE 754 es determinista.

4. **La cifra que la página publica es la que se acaba de medir.** Una página
   puede dar paridad exacta y anunciar un número que nadie contó: se comprueba
   el pie de las dos lenguas contra el conteo real. RC 8.

Al final invoca `verificar_ui.js`: un motor paritario dentro de una página que no
arranca no es una demostración, es un archivo. RC 6.
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(AQUI, "fixture.json")
MOTOR = os.path.join(AQUI, "motor.js")
PAGINA = os.path.join(AQUI, "index.html")
UI = os.path.join(AQUI, "verificar_ui.js")
CENTINELA = "/* ===== fin del cuerpo portable"

RC_DISCREPANCIA = 1
RC_SIN_NODE = 2
RC_SIN_ARCHIVO = 3
RC_ORACULO_MOVIDO = 5
RC_PAGINA_NO_ARRANCA = 6
RC_CONTRATO_ROTO = 7
RC_CIFRA_NO_MEDIDA = 8


def cuerpo_portable():
    texto = io.open(MOTOR, encoding="utf-8").read()
    i = texto.find(CENTINELA)
    if i < 0:
        return None
    return texto[:i].rstrip() + "\n"


def contrato_de_claves():
    """Las claves exactas declaradas por los dos lados, leídas de su fuente."""
    py = io.open(os.path.join(AQUI, "umbral.py"), encoding="utf-8").read()
    m = re.search(r"CLAVES_EXACTAS = \(([\s\S]*?)\)", py)
    de_py = re.findall(r'"([a-z_0-9]+)"', m.group(1)) if m else None
    js = io.open(MOTOR, encoding="utf-8").read()
    m2 = re.search(r"var CLAVES_EXACTAS = \[([\s\S]*?)\]", js)
    de_js = re.findall(r'"([a-z_0-9]+)"', m2.group(1)) if m2 else None
    return de_py, de_js


def cifras_publicadas():
    """Los enteros que el pie de cada lengua anuncia, en el orden en que salen."""
    html = io.open(PAGINA, encoding="utf-8").read()
    salida = {}
    for idioma in ("es", "en"):
        # las dos claves se llaman igual: la segunda es la del bloque EN
        todos = re.findall(r"\bpie_p2:\s*\"([^\"]*)\"", html)
        if len(todos) < 2:
            return None
        texto = todos[0] if idioma == "es" else todos[1]
        salida[idioma] = [int(g.replace(" ", "").replace("\u00a0", ""))
                          for g in re.findall(r"\d[\d \u00a0]*\d|\d", texto)]
    return salida


def corre_node(ruta_datos):
    """Devuelve lo que el motor de node mide para cada estado del fixture."""
    guion = (
        'var m = require(%s);\n'
        'var d = JSON.parse(require("fs").readFileSync(%s, "utf8"));\n'
        'var out = d.todos.map(function (e) {\n'
        '  var n = e.montecarlo === null ? 0 : e.montecarlo.n;\n'
        '  return m.medir(e.p, e.V, e.C, e.m, n);\n'
        '});\n'
        'process.stdout.write(JSON.stringify(out));\n'
    ) % (json.dumps(MOTOR), json.dumps(ruta_datos))
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "guion.js")
        io.open(ruta, "w", encoding="utf-8").write(guion)
        p = subprocess.run(["node", ruta], capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        raise SystemExit("RC 1 · el motor no corre en node:\n" + p.stderr.strip()[:2000])
    return json.loads(p.stdout)


def main() -> int:
    for ruta in (FIXTURE, MOTOR, PAGINA, UI):
        if not os.path.exists(ruta):
            print("RC %d · falta %s" % (RC_SIN_ARCHIVO, ruta), file=sys.stderr)
            return RC_SIN_ARCHIVO
    if not shutil.which("node"):
        print("RC %d · no hay node: sin motor no hay paridad que medir" % RC_SIN_NODE, file=sys.stderr)
        return RC_SIN_NODE

    # 1 · el oráculo no se movió bajo el fixture
    p = subprocess.run([sys.executable, os.path.join(AQUI, "generar_fixture.py"), "--check"],
                       capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        sys.stderr.write(p.stderr or p.stdout)
        return RC_ORACULO_MOVIDO

    # 2 · la página embebe exactamente el motor canónico
    cuerpo = cuerpo_portable()
    if cuerpo is None:
        print("RC %d · motor.js no tiene el centinela del cuerpo portable" % RC_CONTRATO_ROTO, file=sys.stderr)
        return RC_CONTRATO_ROTO
    html = io.open(PAGINA, encoding="utf-8").read()
    m = re.search(r'<script id="motor">\n([\s\S]*?)</script>', html)
    if not m:
        print("RC %d · la página no tiene <script id=\"motor\">" % RC_CONTRATO_ROTO, file=sys.stderr)
        return RC_CONTRATO_ROTO
    if m.group(1).rstrip() + "\n" != cuerpo:
        print("RC %d · el motor que embebe la página NO es motor.js" % RC_CONTRATO_ROTO, file=sys.stderr)
        print("       dos copias libres del mismo motor divergen en silencio.", file=sys.stderr)
        return RC_CONTRATO_ROTO

    de_py, de_js = contrato_de_claves()
    if not de_py or not de_js:
        print("RC %d · no pude leer CLAVES_EXACTAS de las dos fuentes" % RC_CONTRATO_ROTO, file=sys.stderr)
        return RC_CONTRATO_ROTO
    if list(de_py) != list(de_js):
        print("RC %d · el contrato de claves exactas diverge" % RC_CONTRATO_ROTO, file=sys.stderr)
        print("       python: %s" % ", ".join(de_py), file=sys.stderr)
        print("       js:     %s" % ", ".join(de_js), file=sys.stderr)
        return RC_CONTRATO_ROTO

    # 3 · estado por estado, sin tolerancia
    datos = json.load(io.open(FIXTURE, encoding="utf-8"))
    todos = datos["estados"] + datos["presets"] + datos["frontera"]
    with tempfile.TemporaryDirectory() as tmp:
        volcado = os.path.join(tmp, "datos.json")
        io.open(volcado, "w", encoding="utf-8").write(
            json.dumps({"todos": todos}, separators=(",", ":")))
        medidos = corre_node(volcado)

    if len(medidos) != len(todos):
        print("RC 1 · node devolvió %d estados y el fixture declara %d" % (len(medidos), len(todos)))
        return RC_DISCREPANCIA

    comparados = 0
    fallos = []
    for estado, js in zip(todos, medidos):
        etiqueta = "p=%g V=%g C=%g m=%d" % (estado["p"], estado["V"], estado["C"], estado["m"])
        for clave, esperado in estado["esperado"].items():
            if clave not in js:
                fallos.append("%s · falta la clave %s" % (etiqueta, clave))
                continue
            obtenido = js[clave]
            comparados += 1
            if isinstance(esperado, float) or isinstance(obtenido, float):
                iguales = (esperado == obtenido)
            else:
                iguales = (esperado == obtenido)
            if not iguales:
                fallos.append("%s · %s: oráculo %r, node %r" % (etiqueta, clave, esperado, obtenido))
        esperado_mc = estado["montecarlo"]
        if esperado_mc is None:
            if "montecarlo" in js:
                fallos.append("%s · el motor publica un Monte Carlo que el fixture no declara" % etiqueta)
            continue
        obtenido_mc = js.get("montecarlo")
        if obtenido_mc is None:
            fallos.append("%s · falta el bloque montecarlo" % etiqueta)
            continue
        for clave, valor in esperado_mc.items():
            comparados += 1
            if obtenido_mc.get(clave) != valor:
                fallos.append("%s · montecarlo.%s: oráculo %r, node %r"
                              % (etiqueta, clave, valor, obtenido_mc.get(clave)))

    if fallos:
        print("RC 1 · %d discrepancias en %d valores comparados" % (len(fallos), comparados))
        for f in fallos[:25]:
            print("  " + f)
        if len(fallos) > 25:
            print("  … y %d más" % (len(fallos) - 25))
        return RC_DISCREPANCIA

    # 4 · la cifra impresa en el pie es la que se acaba de contar
    mc_estados = sum(1 for e in todos if e.get("montecarlo") is not None)
    medido = [comparados, len(todos), mc_estados]
    publicadas = cifras_publicadas()
    if publicadas is None:
        print("RC %d · no pude leer las dos cifras del pie" % RC_CIFRA_NO_MEDIDA, file=sys.stderr)
        return RC_CIFRA_NO_MEDIDA
    for idioma, cifras in publicadas.items():
        if cifras != medido:
            print("RC %d · el pie (%s) publica %s y lo medido es %s"
                  % (RC_CIFRA_NO_MEDIDA, idioma, cifras, medido), file=sys.stderr)
            return RC_CIFRA_NO_MEDIDA

    # 5 · un motor paritario dentro de una página que no arranca no es una demo
    p = subprocess.run(["node", UI], capture_output=True, text=True, timeout=300)
    if p.returncode != 0:
        sys.stderr.write(p.stderr or p.stdout)
        print("RC %d · el motor da paridad pero la página no arranca" % RC_PAGINA_NO_ARRANCA,
              file=sys.stderr)
        return RC_PAGINA_NO_ARRANCA

    pr = datos["promesas"]
    print("PARIDAD OK · %d valores exactos, 0 discrepancias, tolerancia 0" % comparados)
    print("  estados: %d (%d barrido · %d presets · %d frontera)"
          % (pr["estados"], pr["del_barrido"], pr["presets"], pr["frontera"]))
    print("  claves exactas: %d · monte Carlo: %d estados con n=%d, semilla %d"
          % (len(pr["claves_exactas"]), mc_estados, datos["procedencia"]["n_montecarlo"],
             datos["procedencia"]["semilla"]))
    print("  frontera p·V = C: %d estados dentro de ±%g·max(V,C)"
          % (pr["cerca_del_umbral"], pr["banda"]))
    print("  cifra publicada en el pie: ES y EN dicen %d · %d · %d" % tuple(medido))
    print("  oráculo público: %s (%s…)" % (datos["procedencia"]["oraculo"],
                                           datos["procedencia"]["sha256_oraculo"][:12]))
    print("  " + p.stdout.strip().splitlines()[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
