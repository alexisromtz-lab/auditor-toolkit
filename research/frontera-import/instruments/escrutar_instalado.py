#!/usr/bin/env python3
"""Brazo de ejecucion: contrasta la prediccion estatica contra lo que Python hace.

El censo AST (censar_forma.py) etiqueta un ciclo como VIVO_* cuando alguna arista
lee, al importar, un nombre de otro miembro del SCC. Esa etiqueta es una
*hipotesis*, no un hecho: dos corridas ya la refutaron sobre el mismo Django.

Este escrutador toma el grafo de un paquete YA INSTALADO, enumera sus SCC y
ejecuta en interprete limpio el `import` de cada miembro. La columna `ejecucion`
es la verdad; la etiqueta estatica queda como prediccion a contrastar.

    <venv>/bin/python escrutar_instalado.py --paquete django

No instala nada y no escribe en el paquete: solo lo importa en subprocesos.
"""

from __future__ import annotations

import argparse
import ast
import glob
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import censar_forma as cf  # noqa: E402


def site_packages(venv: str) -> str:
    cands = sorted(glob.glob(os.path.join(venv, "lib", "python*", "site-packages")))
    if not cands:
        raise SystemExit("NO_MEDIDO: no encontre site-packages en %s" % venv)
    return cands[-1]


def modulos_instalados(sp: str, paquete: str) -> tuple:
    """{modulo: codigo} del paquete instalado, con `paquete` como raiz."""
    raiz = os.path.join(sp, paquete)
    if not os.path.isdir(raiz):
        raise SystemExit("NO_MEDIDO: %s no existe" % raiz)
    modulos = {}
    for actual, _, ficheros in os.walk(raiz):
        for f in ficheros:
            if not f.endswith(".py"):
                continue
            ruta = os.path.join(actual, f)
            rel = os.path.relpath(ruta, sp)[:-3].replace(os.sep, ".")
            if rel.endswith(".__init__"):
                rel = rel[: -len(".__init__")]
            with open(ruta, "r", encoding="utf-8", errors="replace") as fh:
                modulos[rel] = fh.read()
    return modulos, raiz


def grafo_de(modulos: dict) -> tuple:
    nombres = set(modulos)
    paquetes = {n for n in nombres if any(o.startswith(n + ".") for o in nombres)}
    grafo = {}
    for nombre, code in modulos.items():
        try:
            tree = ast.parse(code)
        except SyntaxError:
            grafo[nombre] = set()
            continue
        destinos = set()
        for imp in cf.imports_en_import(tree, nombre):
            destinos |= cf.resolver(nombre, imp, nombres, paquetes)
        destinos.discard(nombre)
        grafo[nombre] = destinos
    return nombres, paquetes, grafo


FIRMAS_ORDEN = (
    "partially initialized module",
    "circular import",
    "cannot import name",
    "has no attribute",
)
FIRMAS_DEPENDENCIA = (
    "No module named",
    "Could not find the",
    "Error loading",
    "ImproperlyConfigured",
    "Library not loaded",
)


def causa(texto: str) -> str:
    """Separa fallo por orden de importacion de fallo por dependencia ausente.

    Sin esta separacion el `import` falla igual y el contraste se anota como
    acierto de la metrica: las tres rupturas que aparecen en Django instalado
    (GDAL, oracledb, psycopg2) no las provoca ciclo alguno.
    """
    for firma in FIRMAS_ORDEN:
        if firma in texto:
            return "ORDEN"
    for firma in FIRMAS_DEPENDENCIA:
        if firma in texto:
            return "DEPENDENCIA"
    return "OTRO"


def importar(venv: str, modulo: str, sp: str = "") -> tuple:
    """(ok, motivo, causa). `cwd` fuera del paquete para no leer el arbol por accidente."""
    exe = os.path.join(venv, "bin", "python")
    env = dict(os.environ)
    if sp:
        env["PYTHONPATH"] = sp
    p = subprocess.run([exe, "-c", "import %s" % modulo],
                       capture_output=True, text=True, cwd="/tmp", env=env, timeout=120)
    if p.returncode == 0:
        return True, "", "-"
    lineas = [l for l in (p.stderr or "").strip().splitlines() if l.strip()]
    texto = "\n".join(lineas)
    return False, (lineas[-1][:110] if lineas else "rc=%d" % p.returncode), causa(texto)


def self_test() -> int:
    """Falsador del brazo de ejecucion: el ciclo de manual tiene que salir ORDEN.

    Sin este caso, un `0 rupturas` sobre cuatro ecosistemas no se distingue de un
    ejecutor ciego. Medido 16-Nov-2026: `p.a` y `p.b` se leen mutuamente en el
    cuerpo y `import p.a` levanta `cannot import name ... partially initialized`.
    """
    import tempfile

    fallos = 0

    def caso(nombre, ok):
        nonlocal fallos
        print("  %-52s %s" % (nombre, "OK" if ok else "FALLA"))
        if not ok:
            fallos += 1

    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "p"))
        open(os.path.join(tmp, "p", "__init__.py"), "w").close()
        with open(os.path.join(tmp, "p", "a.py"), "w") as fh:
            fh.write("from p.b import B\n\nclass A:\n    pass\n")
        with open(os.path.join(tmp, "p", "b.py"), "w") as fh:
            fh.write("from p.a import A\n\nclass B:\n    pass\n")
        modulos, _ = modulos_instalados(tmp, "p")
        nombres, paquetes, grafo = grafo_de(modulos)
        componentes = cf.sccs(grafo)
        caso("el ciclo de manual forma un SCC>=2", len(componentes) == 1 and len(componentes[0]) == 2)
        venv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv")
        ok, motivo, k = importar(venv, "p.a", tmp)
        caso("el ejecutor ve la ruptura de orden (causa=%s)" % k, (not ok) and k == "ORDEN")
        etiqueta = cf.clasificar(modulos, "p")[0]
        caso("el predictor estatico FALLA en este caso (etiqueta=%s)" % etiqueta,
             etiqueta != "VIVO_HOJA")
    print("\n  %s" % ("self-test OK" if not fallos else "self-test: %d FALLA" % fallos))
    return 0 if not fallos else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--venv", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv"))
    ap.add_argument("--paquete", default="")
    ap.add_argument("--salida", default="")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--sp", default="",
                    help="raiz alternativa de paquetes (control sintetico)")
    a = ap.parse_args()

    if a.self_test:
        return self_test()
    if not a.paquete:
        raise SystemExit("NO_MEDIDO: falta --paquete")

    sp = a.sp or site_packages(a.venv)
    modulos, _ = modulos_instalados(sp, a.paquete)
    nombres, paquetes, grafo = grafo_de(modulos)
    estado, _, aristas, mayor, det = cf.clasificar(modulos, a.paquete)
    componentes = cf.sccs(grafo)

    print("paquete=%s  modulos=%d  aristas=%d  scc>=2=%d  ciclo_max=%d"
          % (a.paquete, len(nombres), aristas, len(componentes), mayor))
    print("prediccion estatica: %s  (%s)\n" % (estado, det))

    filas = []
    for i, c in enumerate(sorted(componentes, key=len, reverse=True), 1):
        vivos = []
        for m in sorted(c):
            if m not in modulos:
                continue
            ar = cf.arista_viva(modulos[m], m, c, nombres, paquetes)
            if ar:
                vivos.append("%s lee %s.%s" % ar)
        fallos, causas = [], set()
        for m in sorted(c):
            ok, motivo, k = importar(a.venv, m, a.sp)
            if not ok:
                causas.add(k)
                fallos.append("%s -> [%s] %s" % (m, k, motivo))
        de_orden = "ORDEN" in causas
        veredicto = ("ORDEN" if de_orden
                     else "DEPENDENCIA" if "DEPENDENCIA" in causas
                     else "OTRO" if "OTRO" in causas else "PASA")
        pred = "VIVO" if vivos else "INERTE"
        acierto = "ACEPTA" if (pred == "VIVO") == de_orden else "FALLA"
        print("[scc %2d] tam=%-3d pred=%-7s ejecucion=%-11s %s"
              % (i, len(c), pred, veredicto, acierto))
        print("         miembros: %s" % ", ".join(sorted(c)))
        if vivos:
            for v in vivos[:3]:
                print("         arista viva: %s" % v)
        for f in fallos[:2]:
            print("         FALLO: %s" % f)
        filas.append((i, len(c), pred, veredicto, acierto,
                      ";".join(sorted(c)), " | ".join(vivos), " | ".join(fallos)))

    orden = sum(1 for f in filas if f[3] == "ORDEN")
    vivos_n = sum(1 for f in filas if f[2] == "VIVO")
    print("\n--- contraste ---")
    print("  scc>=2 %d · con arista viva %d · ruptura por ORDEN %d · falsos positivos %d"
          % (len(filas), vivos_n, orden,
             sum(1 for f in filas if f[2] == "VIVO" and f[3] != "ORDEN")))
    print("  presupuesto: ejecutar %d `import` basta para cubrir la clase ORDEN en %d modulos"
          % (len({m for f in filas for m in f[5].split(";") if m}), len(nombres)))

    if a.salida:
        with open(a.salida, "w", encoding="utf-8") as fh:
            fh.write("scc\ttam\tprediccion\tejecucion\tcontraste\tmiembros\taristas_vivas\tfallos\n")
            for f in filas:
                fh.write("\t".join(str(x).replace("\t", " ") for x in f) + "\n")
        print("\nescritas %d filas en %s" % (len(filas), a.salida))
    return 0


if __name__ == "__main__":
    sys.exit(main())
