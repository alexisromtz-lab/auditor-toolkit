#!/usr/bin/env python3
"""Mecanica posicional del ciclo: por que 1449 modulos dan 0 rupturas de ORDEN.

El censo (censar_forma.py) cuenta ciclos. El ejecutor (escrutar_instalado.py)
mide si rompen. Medido 16-Nov-2026 sobre cinco ecosistemas: 17 SCC de tamano
>=2, 16 con "arista viva", **0 rupturas por orden** y 3 por dependencia ausente.

Un cero sin mecanismo no es ciencia, es una casilla. Este instrumento contesta
*por que*. La ruptura por orden exige una lectura de NOMBRE sobre un modulo a
medio construir. Una sentencia `from M import n` solo lee el nombre cuando `n`
NO es un submodulo de `M` (si lo es, liga el objeto modulo: lectura tardia). Y
solo rompe si `n` todavia no existe en `M` en el instante en que la sentencia
corre, es decir, si en `M` la ligadura de `n` cae DESPUES del primer import de
`M` hacia dentro del ciclo —ahi es donde `M` se bloquea y devuelve el control.

Ese es el modelo. La prediccion pre-registrada esta en PREREGISTRO_mecanismo.txt
y su falsador es un SCC con lectura INSEGURA cuya ejecucion dio PASA.

REFUTADO COMO PREDICTOR (medido 17-Nov-2026). El falsador se cumplio 11 veces
sobre 11 SCC con veredicto de ejecucion limpio. Tres correcciones sucesivas
—submodulo medido contra el SCC, corte leido del destino en vez del origen, y
regla padre-primero— bajaron las lecturas inseguras de 1107 a 625 sin mover el
veredicto: 17 SCC · 11 ROMPE · 625 lecturas, contra 2 rupturas reales.
La razon es estructural, no un bug: dentro de un SCC todo par de modulos se
alcanza mutuamente, asi que "esta t a medio ejecutar" NO es decidible desde el
AST — depende de la pila de importacion, o sea del punto de entrada. NO PUBLICAR
como detector. `inseguras` es una COTA SUPERIOR y un ranking de sospecha; el
unico oraculo es escrutar_instalado.py. Los 2 SCC que si rompen se encontraron
por ejecucion, no por este modelo.

Veredictos por lectura de nombre (arista m -> t, nombre n):
  SEGURA    n ya esta ligado en t antes de que t entre al ciclo
  GUARDADA  iria a romper, pero la sentencia vive en un try/except: degrada en
            silencio en vez de fallar (nombre sin ligar, excepcion tragada)
  INSEGURA  n no existe cuando t se bloquea: esto SI rompe
  NO_MEDIDO t fallo antes por dependencia ausente; la lectura nunca se alcanzo

    <venv>/bin/python mecanismo_ciclos.py --paquete django --salida m.tsv
    <venv>/bin/python mecanismo_ciclos.py --self-test
"""

from __future__ import annotations

import argparse
import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import censar_forma as cf  # noqa: E402
import escrutar_instalado as es  # noqa: E402


# --------------------------------------------------------------------------
# ligaduras a nivel de modulo, con su primera linea
# --------------------------------------------------------------------------
def _nombres_de(objetivo, put, linea):
    if objetivo is None:
        return
    for n in ast.walk(objetivo):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            put(n.id, linea)
        elif hasattr(ast, "MatchAs") and isinstance(n, ast.MatchAs) and n.name:
            put(n.name, linea)


def ligaduras(tree) -> dict:
    """{nombre: primera linea} de lo que se liga a nivel de modulo.

    El cuerpo de una clase NO liga en el modulo (liga atributos), asi que no se
    recorre. El de una funcion tampoco: corre despues. Un `if` o un `try` a
    nivel de modulo SI liga, porque corre al importar.
    """
    salida = {}

    def put(nombre, linea):
        if nombre not in salida or linea < salida[nombre]:
            salida[nombre] = linea

    def cuerpo(nodos):
        for n in nodos:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                put(n.name, n.lineno)
                continue
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    if a.name == "*":
                        continue
                    put(a.asname or a.name.split(".")[0], n.lineno)
                continue
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    _nombres_de(t, put, n.lineno)
                continue
            if isinstance(n, (ast.AnnAssign, ast.AugAssign)):
                _nombres_de(n.target, put, n.lineno)
                continue
            if isinstance(n, (ast.For, ast.AsyncFor)):
                _nombres_de(n.target, put, n.lineno)
                cuerpo(n.body)
                cuerpo(n.orelse)
                continue
            if isinstance(n, (ast.While, ast.AsyncWith, ast.With, ast.If)):
                if isinstance(n, (ast.With, ast.AsyncWith)):
                    for it in n.items:
                        _nombres_de(it.optional_vars, put, n.lineno)
                cuerpo(n.body)
                cuerpo(n.orelse)
                continue
            if isinstance(n, ast.Try):
                cuerpo(n.body)
                for h in n.handlers:
                    if h.name:
                        put(h.name, h.lineno)
                    cuerpo(h.body)
                cuerpo(n.orelse)
                cuerpo(n.finalbody)
                continue
            if hasattr(ast, "Match") and isinstance(n, ast.Match):
                for c in n.cases:
                    cuerpo(c.body)
                continue
            # asignaciones por walrus dentro de una expresion de nivel de modulo
            for hijo in ast.walk(n):
                if isinstance(hijo, ast.NamedExpr) and isinstance(hijo.target, ast.Name):
                    put(hijo.target.id, n.lineno)

    cuerpo(tree.body)
    return salida


# --------------------------------------------------------------------------
# sentencias import con su contexto lexico y su linea
# --------------------------------------------------------------------------
def sentencias_import(tree) -> list:
    """[(linea, contexto, nodo)] de toda sentencia import del modulo.

    contexto: modulo | clase | funcion | type_checking | try
    """
    salida = []

    def visitar(nodos, ctx):
        for n in nodos:
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                salida.append((n.lineno, ctx, n))
                continue
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visitar(n.body, "funcion")
                continue
            if isinstance(n, ast.ClassDef):
                visitar(n.body, "clase")
                continue
            if isinstance(n, ast.If):
                if cf.test_es_type_checking(n.test):
                    visitar(n.body, "type_checking")
                else:
                    visitar(n.body, ctx)
                visitar(n.orelse, ctx)
                continue
            if isinstance(n, ast.Try):
                visitar(n.body, "try")
                for h in n.handlers:
                    visitar(h.body, "try")
                visitar(n.orelse, ctx)
                visitar(n.finalbody, "try")
                continue
            if hasattr(ast, "Match") and isinstance(n, ast.Match):
                for c in n.cases:
                    visitar(c.body, ctx)
                continue
            for campo in ("body", "orelse", "finalbody"):
                interno = getattr(n, campo, None)
                if isinstance(interno, list) and interno and isinstance(interno[0], ast.stmt):
                    visitar(interno, ctx)

    visitar(tree.body, "modulo")
    return salida


def base_absoluta(modname: str, paquetes: set, nivel: int, modulo: str) -> str:
    """Modulo absoluto sobre el que se aplica un `from ... import`."""
    if not nivel:
        return modulo
    partes = modname.split(".") if modname in paquetes else modname.split(".")[:-1]
    subir = (nivel or 1) - 1
    if subir:
        partes = partes[: len(partes) - subir] if subir <= len(partes) else []
    return ".".join(partes + ([modulo] if modulo else []))


def aristas_de(modname, code, nombres, paquetes, componente) -> list:
    """Aristas del modulo hacia dentro del SCC, con forma y linea.

    Cada elemento: (destino, nombre, forma, linea, contexto).
    forma: submodulo (liga objeto modulo) | modulo (liga objeto modulo) |
           nombre (LEE un nombre del destino)
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    salida = []
    for linea, ctx, n in sentencias_import(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                destinos = cf.resolver(modname, ("abs", a.name, 0), nombres, paquetes)
                for d in sorted(destinos):
                    if d in componente and d != modname:
                        salida.append((d, None, "modulo", linea, ctx))
            continue
        base = base_absoluta(modname, paquetes, n.level, n.module or "")
        for a in n.names:
            if a.name == "*":
                continue
            cand = (base + "." + a.name) if base else a.name
            # `from P import x`: si `P.x` es un modulo, liga el OBJETO modulo y
            # CPython cae a sys.modules aunque P este a medio construir. Por eso
            # la prueba es contra `nombres` (todo el paquete), no contra el SCC:
            # preguntarlo contra el SCC convierte cada `from .. import compat` en
            # una lectura de nombre y fabrica las 1107 inseguras de la 1a corrida.
            if cand in nombres:
                if cand in componente and cand != modname:
                    salida.append((cand, a.name, "submodulo", linea, ctx))
                continue
            if base in componente and base != modname:
                salida.append((base, a.name, "nombre", linea, ctx))
    return salida


def primera_interna(modname, code, nombres, paquetes, componente):
    """Primera linea de `modname` que importa hacia dentro del SCC.

    Ahi se bloquea el modulo y devuelve el control: todo lo ligado antes existe,
    todo lo ligado despues no existe todavia para quien lo lea desde el ciclo.
    """
    lineas = [ar[3] for ar in aristas_de(modname, code, nombres, paquetes, componente)
              if ar[4] in ("modulo", "clase", "try")]
    return min(lineas) if lineas else None


# --------------------------------------------------------------------------
# analisis de un SCC
# --------------------------------------------------------------------------
def analizar(modulos, componente, nombres, paquetes, dep=None) -> dict:
    """Clasifica cada lectura de nombre del SCC. `dep` = modulos que fallaron
    por dependencia ausente y por tanto nunca alcanzaron la lectura."""
    dep = dep or set()
    liga = {}
    corte = {}
    for m in componente:
        try:
            liga[m] = ligaduras(ast.parse(modulos[m]))
        except SyntaxError:
            liga[m] = {}
        corte[m] = primera_interna(m, modulos[m], nombres, paquetes, componente)
    filas = []
    for m in sorted(componente):
        for destino, nombre, forma, linea, ctx in aristas_de(
                m, modulos[m], nombres, paquetes, componente):
            if forma != "nombre":
                continue
            t = corte[destino]
            if m in dep or destino in dep:
                veredicto = "NO_MEDIDO"
            elif ctx == "type_checking":
                veredicto = "SEGURA"
            elif ctx == "funcion":
                veredicto = "SEGURA"
            elif nombre in liga[destino] and t is not None and liga[destino][nombre] < t:
                veredicto = "SEGURA"
            # regla padre-primero: un hijo nunca esta a medio ejecutar cuando su
            # padre lo importa, asi que se ejecuta entero y liga el nombre antes
            # de que la lectura ocurra. Medido: los 4 residuos de django_filters
            # son exactamente este caso (`__init__` leyendo de su hijo).
            elif destino.startswith(m + "."):
                veredicto = "SEGURA_HIJO"
            elif ctx == "try":
                veredicto = "GUARDADA"
            else:
                veredicto = "INSEGURA"
            filas.append({"src": m, "dst": destino, "nombre": nombre,
                          "forma": forma, "linea": linea, "ctx": ctx,
                          "corte": t, "veredicto": veredicto})
    cuenta = {}
    for f in filas:
        cuenta[f["veredicto"]] = cuenta.get(f["veredicto"], 0) + 1
    if cuenta.get("INSEGURA"):
        pred = "ROMPE"
    elif cuenta.get("GUARDADA"):
        pred = "SILENCIO"
    elif cuenta.get("NO_MEDIDO") and not cuenta.get("SEGURA"):
        pred = "NO_MEDIDO"
    else:
        pred = "PASA"
    return {"pred": pred, "filas": filas, "cuenta": cuenta}


# --------------------------------------------------------------------------
# control positivo
# --------------------------------------------------------------------------
def control() -> tuple:
    """El ciclo de manual: a lee B de b, b lee A de a, ninguno ligado antes."""
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "control_orden", "p")
    modulos = {}
    for f in ("__init__.py", "a.py", "b.py"):
        with open(os.path.join(base, f), encoding="utf-8") as fh:
            modulos["p" if f == "__init__.py" else "p." + f[:-3]] = fh.read()
    nombres, paquetes, grafo = es.grafo_de(modulos)
    comps = cf.sccs(grafo)
    if not comps:
        return False, "el control no forma SCC"
    r = analizar(modulos, comps[0], nombres, paquetes)
    inseg = [f for f in r["filas"] if f["veredicto"] == "INSEGURA"]
    if r["pred"] != "ROMPE" or len(inseg) < 2:
        return False, "el control da %s con %d inseguras (esperaba ROMPE con 2)" % (
            r["pred"], len(inseg))
    return True, "control ROMPE con %d lecturas inseguras" % len(inseg)


def self_test() -> int:
    ok, motivo = control()
    print("[%s] control positivo: %s" % ("OK" if ok else "FALLA", motivo))

    # un ciclo que liga ANTES de importar no rompe: el modelo debe decir PASA
    fuente_a = "class A:\n    pass\n\nfrom p.b import B\n\nx = A\n"
    fuente_b = "class B:\n    pass\n\nfrom p.a import A\n\ny = B\n"
    modulos = {"p": "", "p.a": fuente_a, "p.b": fuente_b}
    nombres, paquetes, grafo = es.grafo_de(modulos)
    comps = cf.sccs(grafo)
    orden_ok = bool(comps)
    if orden_ok:
        r = analizar(modulos, comps[0], nombres, paquetes)
        orden_ok = r["pred"] == "PASA" and not r["cuenta"].get("INSEGURA")
        motivo2 = "ciclo ligado antes de importar da %s" % r["pred"]
    else:
        motivo2 = "el segundo control no forma SCC"
    print("[%s] control negativo: %s" % ("OK" if orden_ok else "FALLA", motivo2))

    # un `import p.b` suelto no lee ningun nombre: no puede ser INSEGURA
    m3 = {"p": "", "p.a": "import p.b\n\nx = 1\n", "p.b": "import p.a\n\ny = 2\n"}
    nombres, paquetes, grafo = es.grafo_de(m3)
    comps = cf.sccs(grafo)
    solo_modulo = bool(comps) and not any(
        f["forma"] != "modulo" for f in analizar(m3, comps[0], nombres, paquetes)["filas"])
    print("[%s] control forma: `import m` no produce lecturas de nombre" %
          ("OK" if solo_modulo else "FALLA"))

    verde = ok and orden_ok and solo_modulo
    print("\n%s" % ("3/3 OK" if verde else "FALLA"))
    return 0 if verde else 1


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--venv", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv"))
    ap.add_argument("--paquete", default="")
    ap.add_argument("--sp", default="")
    ap.add_argument("--dep", default="", help="modulos con fallo de dependencia, separados por coma")
    ap.add_argument("--salida", default="")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return self_test()
    if not a.paquete:
        print("NO_MEDIDO: falta --paquete")
        return 20

    sp = a.sp or es.site_packages(a.venv)
    modulos, _ = es.modulos_instalados(sp, a.paquete)
    nombres, paquetes, grafo = es.grafo_de(modulos)
    comps = cf.sccs(grafo)
    dep = {x.strip() for x in a.dep.split(",") if x.strip()}

    print("%s: %d modulos · %d SCC>=2%s" % (
        a.paquete, len(modulos), len(comps), (" · %d dep-ausente" % len(dep)) if dep else ""))
    filas = []
    for i, c in enumerate(sorted(comps, key=lambda x: -len(x)), 1):
        r = analizar(modulos, c, nombres, paquetes, dep)
        cu = r["cuenta"]
        det = ";".join("%s lee %s.%s (L%d)" % (f["src"], f["dst"], f["nombre"], f["linea"])
                       for f in r["filas"] if f["veredicto"] in ("INSEGURA", "GUARDADA"))[:300]
        filas.append((a.paquete, i, len(c), r["pred"], cu.get("INSEGURA", 0),
                      cu.get("GUARDADA", 0), cu.get("NO_MEDIDO", 0), det))
        print("  scc %2d tam %3d · lectura-nombre %2d · inseguras %d · guardadas %d · %s"
              % (i, len(c), len(r["filas"]), cu.get("INSEGURA", 0), cu.get("GUARDADA", 0),
                 r["pred"]))

    inseg = sum(f[4] for f in filas)
    guard = sum(f[5] for f in filas)
    print("\n--- mecanismo ---")
    print("  prediccion posicional: %d SCC ROMPE · %d SILENCIO · %d PASA" % (
        sum(1 for f in filas if f[3] == "ROMPE"),
        sum(1 for f in filas if f[3] == "SILENCIO"),
        sum(1 for f in filas if f[3] == "PASA")))
    print("  lecturas de nombre inseguras %d · guardadas %d · no_medidas %d" % (
        inseg, guard, sum(f[6] for f in filas)))

    if a.salida:
        with open(a.salida, "w", encoding="utf-8") as fh:
            fh.write("paquete\tscc\ttam\tprediccion_posicional\tinseguras\tguardadas\tno_medidas\tdetalle\n")
            for f in filas:
                fh.write("\t".join(str(x).replace("\t", " ") for x in f) + "\n")
        print("\nescritas %d filas en %s" % (len(filas), a.salida))
    return 0


if __name__ == "__main__":
    sys.exit(main())
