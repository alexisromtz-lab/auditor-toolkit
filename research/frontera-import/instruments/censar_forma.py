#!/usr/bin/env python3
"""Censo AST-only de la precondicion estructural del cribador de frontera.

Pregunta que contesta: cuantos paquetes reales de PyPI admiten la forma que el
cribador necesita para tener sujeto, es decir

    A) un ciclo de importacion *entre modulos del mismo paquete* (SCC >= 2,
       excluyendo el __init__ de la raiz), y
    B) un __init__ que importa, en tiempo de import, hacia ese ciclo.

Sin A y B no hay ruptura que medir: el cribador devolveria INALCANZABLE en todo
y eso no lo refuta, solo muestra que la forma no esta ahi.

No instala nada y no ejecuta codigo de terceros: descarga el sdist, lee los .py
del archivo comprimido en memoria y los parsea con ast.

Uso:
    python3 censar_forma.py --top 60 --salida censo.tsv
    python3 censar_forma.py --self-test
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import sys
import tarfile
import time
import unicodedata
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

LISTA = "https://raw.githubusercontent.com/hugovk/top-pypi-packages/main/top-pypi-packages-30-days.min.json"
MAX_MB = 25
TIMEOUT = 60
UA = {"User-Agent": "auditor-toolkit-censo/0.1 (+https://alexisromtz-lab.github.io/auditor-toolkit/)"}

BASURA = {"test", "tests", "testing", "docs", "doc", "examples", "example",
          "build", "dist", "benchmarks", "scripts", "ci", "vendor"}


# --------------------------------------------------------------------------
# red
# --------------------------------------------------------------------------
def traer(url: str, limite: int = 0) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read(limite) if limite else r.read()


def json_pypi(proj: str) -> dict:
    return json.loads(traer("https://pypi.org/pypi/%s/json" % proj))


def elegir_sdist(data: dict):
    urls = data.get("urls") or []
    sd = [u for u in urls if u.get("packagetype") == "sdist"]
    if not sd:
        return None, "sin_sdist"
    sd.sort(key=lambda u: 0 if u["filename"].endswith(".tar.gz") else 1)
    mejor = sd[0]
    if (mejor.get("size") or 0) > MAX_MB * 1024 * 1024:
        return None, "sdist_%dMB" % ((mejor.get("size") or 0) // (1024 * 1024))
    return mejor, None


# --------------------------------------------------------------------------
# lectura del sdist sin escribir a disco
# --------------------------------------------------------------------------
def leer_py(blob: bytes, nombre: str) -> dict:
    """Devuelve {ruta_relativa: bytes} de los .py del sdist."""
    out = {}
    if nombre.endswith((".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")):
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:*") as tf:
            for m in tf.getmembers():
                if not (m.isfile() and m.name.endswith(".py")) or m.size > 2_000_000:
                    continue
                f = tf.extractfile(m)
                if f is None:
                    continue
                out[m.name] = f.read()
    elif nombre.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            for i in zf.infolist():
                if i.is_dir() or not i.filename.endswith(".py") or i.file_size > 2_000_000:
                    continue
                out[i.filename] = zf.read(i)
    else:
        raise ValueError("formato no soportado: %s" % nombre)
    return out


def raiz_comun(rutas) -> str:
    partes = [p.split("/") for p in rutas]
    if not partes:
        return ""
    primero = partes[0][0]
    if all(len(p) > 1 and p[0] == primero for p in partes):
        return primero + "/"
    return ""


def normaliza(n: str) -> str:
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode()
    return re.sub(r"[-_.]+", "_", n).lower()


# --------------------------------------------------------------------------
# grafo
# --------------------------------------------------------------------------
def modulos_del_paquete(archivos: dict, proj: str):
    """Elige el paquete raiz y devuelve {modulo: codigo}."""
    rutas = sorted(archivos)
    base = raiz_comun(rutas)
    rel = {p[len(base):]: c for p, c in archivos.items() if base == "" or p.startswith(base)}
    if any(r.startswith("src/") for r in rel):
        rel = {r[4:]: c for r, c in rel.items() if r.startswith("src/")}

    tops = {}
    for r in rel:
        partes = r.split("/")
        if len(partes) >= 2 and partes[0] not in BASURA:
            tops.setdefault(partes[0], []).append(r)
    if not tops:
        return None, "sin_paquete"

    objetivo = normaliza(proj)
    elegido = None
    for t in tops:
        if normaliza(t) == objetivo:
            elegido = t
            break
    if elegido is None:
        elegido = max(tops, key=lambda t: len(tops[t]))

    modulos = {}
    for r, code in rel.items():
        if not r.startswith(elegido + "/"):
            continue
        partes = r[len(elegido) + 1:].split("/")
        if partes[-1] == "__init__.py":
            nombre = ".".join([elegido] + partes[:-1])
        else:
            nombre = ".".join([elegido] + partes)[:-3]
        modulos[nombre] = code
    return (modulos, None) if modulos else (None, "sin_modulos")


def test_es_type_checking(nodo) -> bool:
    try:
        return "TYPE_CHECKING" in ast.dump(nodo)
    except Exception:
        return False


def imports_en_import(tree, modname: str) -> set:
    """Imports que SI se ejecutan al importar el modulo (fuera de funciones)."""
    encontrados = set()

    def visitar(nodos):
        for n in nodos:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(n, ast.If):
                if not test_es_type_checking(n.test):
                    visitar(n.body)
                visitar(n.orelse)
                continue
            if isinstance(n, (ast.With, ast.AsyncWith, ast.Try)):
                visitar(n.body)
                continue
            if isinstance(n, ast.ClassDef):
                visitar(n.body)
                continue
            if isinstance(n, ast.Import):
                for a in n.names:
                    encontrados.add(("abs", a.name, 0))
            elif isinstance(n, ast.ImportFrom):
                encontrados.add(("rel" if n.level else "abs",
                                 n.module or "", n.level,
                                 tuple(a.name for a in n.names)))
    visitar(tree.body)
    return encontrados


def resolver(modname: str, imp, modulos: set, paquetes: set) -> set:
    """Convierte un import en nombres de modulo internos existentes.

    La base de un import relativo es el *paquete que contiene* al modulo, y ese
    paquete es el propio modulo cuando es un __init__. Confundirlo trunca un
    nivel de mas y el censo se queda ciego justo en el caso que busca.
    """
    salida = set()
    if imp[0] == "abs":
        partes = imp[1].split(".")
        for i in range(len(partes), 0, -1):
            cand = ".".join(partes[:i])
            if cand in modulos:
                salida.add(cand)
                break
        return salida

    _, modulo, nivel, nombres = imp
    if modname in paquetes:
        partes_pkg = modname.split(".")
    else:
        partes_pkg = modname.split(".")[:-1]
    subir = (nivel or 1) - 1
    if subir:
        partes_pkg = partes_pkg[: len(partes_pkg) - subir] if subir <= len(partes_pkg) else []
    prefijo = ".".join(partes_pkg + ([modulo] if modulo else []))
    # `from . import x` nombra al paquete contenedor como prefijo: contarlo como
    # destino fabrica aristas hacia la raiz y ciclos que no existen. Solo cuenta
    # el prefijo cuando hay un submodulo explicito (`from .x import y`).
    if modulo and prefijo in modulos:
        salida.add(prefijo)
    for nm in nombres:
        cand = (prefijo + "." + nm) if prefijo else nm
        if cand in modulos:
            salida.add(cand)
    return salida


# --------------------------------------------------------------------------
# vivo vs inerte: la arista que de verdad detona
# --------------------------------------------------------------------------
def usos_modulo(tree) -> set:
    """Nombres que se LEEN en codigo que corre al importar el modulo.

    Un acceso dentro del cuerpo de una funcion no detona nada: corre despues.
    Uno dentro del cuerpo de una clase SI, porque el cuerpo de la clase se
    ejecuta en el acto. Las anotaciones se excluyen a proposito: con
    `from __future__ import annotations` no se evaluan, y contarlas fabrica
    justo el falso positivo que refuta el censo (ver `--proyectos django`).
    """

    def expr(nodo):
        pila = [nodo]
        while pila:
            n = pila.pop()
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                usados.add(n.id)
            elif isinstance(n, ast.Attribute):
                raiz = n
                while isinstance(raiz, ast.Attribute):
                    raiz = raiz.value
                if isinstance(raiz, ast.Name):
                    usados.add(raiz.id)
            pila.extend(ast.iter_child_nodes(n))

    def cuerpo(nodos):
        for n in nodos:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for d in n.decorator_list:
                    expr(d)
                for d in n.args.defaults:
                    expr(d)
                for d in n.args.kw_defaults:
                    if d is not None:
                        expr(d)
                continue
            if isinstance(n, ast.ClassDef):
                for d in n.decorator_list:
                    expr(d)
                for b in n.bases:
                    expr(b)
                for k in n.keywords:
                    expr(k.value)
                cuerpo(n.body)
                continue
            if isinstance(n, ast.If):
                if test_es_type_checking(n.test):
                    cuerpo(n.orelse)
                else:
                    expr(n.test)
                    cuerpo(n.body)
                    cuerpo(n.orelse)
                continue
            if isinstance(n, (ast.For, ast.AsyncFor)):
                expr(n.iter)
                expr(n.target)
                cuerpo(n.body)
                cuerpo(n.orelse)
                continue
            if isinstance(n, ast.While):
                expr(n.test)
                cuerpo(n.body)
                cuerpo(n.orelse)
                continue
            if isinstance(n, (ast.With, ast.AsyncWith)):
                for i in n.items:
                    expr(i.context_expr)
                cuerpo(n.body)
                continue
            if isinstance(n, ast.Try):
                cuerpo(n.body)
                for h in n.handlers:
                    cuerpo(h.body)
                cuerpo(n.orelse)
                cuerpo(n.finalbody)
                continue
            if isinstance(n, ast.AnnAssign):
                if n.value is not None:
                    expr(n.value)
                continue
            if isinstance(n, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)):
                continue
            expr(n)

    usados = set()
    cuerpo(tree.body)
    return usados


def enlaces_modulo(tree, modname: str, nombres: set, paquetes: set) -> dict:
    """{nombre_local: modulo_destino} de los imports que corren al importar."""
    enlaces = {}

    def visitar(nodos):
        for n in nodos:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(n, ast.ClassDef):
                visitar(n.body)
                continue
            if isinstance(n, ast.If):
                if not test_es_type_checking(n.test):
                    visitar(n.body)
                visitar(n.orelse)
                continue
            if isinstance(n, (ast.With, ast.AsyncWith, ast.Try)):
                visitar(n.body)
                continue
            if isinstance(n, ast.Import):
                for a in n.names:
                    destinos = resolver(modname, ("abs", a.name, 0), nombres, paquetes)
                    if destinos:
                        enlaces[a.asname or a.name.split(".")[0]] = sorted(destinos)[0]
            elif isinstance(n, ast.ImportFrom):
                nivel = n.level
                for a in n.names:
                    if a.name == "*":
                        continue
                    destinos = resolver(
                        modname,
                        ("rel" if nivel else "abs", n.module or "", nivel, (a.name,)),
                        nombres, paquetes)
                    if destinos:
                        enlaces[a.asname or a.name] = sorted(destinos)[0]

    visitar(tree.body)
    return enlaces


def arista_viva(code: str, modname: str, componente: set, nombres: set, paquetes: set):
    """Arista del ciclo que lee, al importar, un nombre de un miembro sin terminar.

    Entrar a un SCC por cualquier hoja deja siempre un modulo a medio construir;
    si nadie lee de ese modulo antes de salir del cuerpo, el ciclo es inerte y
    el `import` pasa. Es la diferencia que separa `wontfix` de bug real.

    REFUTADO 16-Nov-2026: falta `local in usados`. El `from X import v` *es* una
    lectura en tiempo de import aunque `v` no se vuelva a nombrar, asi que este
    predicado da falso negativo en el ciclo de manual (`p.a`<->`p.b` sale INERTE
    y rompe con `partially initialized`). Medido: precision 0/15 sobre django
    6.1.3, pydantic 2.14.3, sqlalchemy 2.1.9 y celery 5.7.0 — las unicas tres
    rupturas fueron GDAL, oracledb y psycopg2 ausentes, no el ciclo. Se conserva
    solo para etiquetar candidatos; la verdad la da `escrutar_instalado.py`.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    usados = usos_modulo(tree)
    for local, destino in sorted(enlaces_modulo(tree, modname, nombres, paquetes).items()):
        if destino in componente and destino != modname and local in usados:
            return (modname, local, destino)
    return None


def sccs(grafo: dict) -> list:
    """Tarjan iterativo. Devuelve SCCs de tamano >= 2."""
    indice, low, stack, en_pila, res = {}, {}, [], set(), []
    contador = [0]

    for raiz in grafo:
        if raiz in indice:
            continue
        trabajo = [(raiz, 0)]
        while trabajo:
            v, i = trabajo.pop()
            if i == 0:
                indice[v] = low[v] = contador[0]
                contador[0] += 1
                stack.append(v)
                en_pila.add(v)
            recurse = False
            hijos = list(grafo.get(v, ()))
            while i < len(hijos):
                w = hijos[i]
                i += 1
                if w not in indice:
                    trabajo.append((v, i))
                    trabajo.append((w, 0))
                    recurse = True
                    break
                if w in en_pila:
                    low[v] = min(low[v], indice[w])
            if recurse:
                continue
            if low[v] == indice[v]:
                comp = []
                while True:
                    w = stack.pop()
                    en_pila.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                if len(comp) >= 2:
                    res.append(set(comp))
            if trabajo:
                padre = trabajo[-1][0]
                low[padre] = min(low[padre], low[v])
    return res


def ancestros(ciclo: set, paquetes: set, raiz: str) -> set:
    """__init__ que se ejecutan antes de cualquier miembro del ciclo.

    `import pkg.sub.base` ejecuta `pkg/__init__` y `pkg/sub/__init__`. En Django
    el que detona el ciclo es el de `.../sqlite3/`, no el de la raiz: mirar solo
    la raiz deja ciego el caso que se busca.
    """
    anc = {m for m in paquetes if all(x.startswith(m + ".") for x in ciclo)}
    anc.add(raiz)
    return anc - ciclo


def clasificar(modulos: dict, raiz: str):
    nombres = set(modulos)
    paquetes = {n for n in nombres if any(o.startswith(n + ".") for o in nombres)}
    grafo = {}
    for nombre, code in modulos.items():
        try:
            tree = ast.parse(code)
        except SyntaxError:
            continue
        destinos = set()
        for imp in imports_en_import(tree, nombre):
            destinos |= resolver(nombre, imp, nombres, paquetes)
        destinos.discard(nombre)
        grafo[nombre] = destinos

    componentes = sccs(grafo)
    aristas = sum(len(v) for v in grafo.values())
    if not componentes:
        return "NO", len(nombres), aristas, 0, ""

    # Un SCC no es una ruptura: solo lo es si alguna arista lee, al importar, un
    # nombre del miembro que quedo a medias. Django 6.1.3 tiene 11 SCC y los
    # cuatro `import` del ciclo de sqlite3 pasan limpios en interprete limpio:
    # contar ciclos a secas certificaria un riesgo que la ejecucion refuta.
    vivos = []
    for c in componentes:
        for m in sorted(c):
            if m in modulos:
                arista = arista_viva(modulos[m], m, c, nombres, paquetes)
                if arista:
                    vivos.append((c, arista))
                    break
    mayor = max(len(c) for c in componentes)
    if not vivos:
        detalle = "inerte=" + ",".join(sorted(sorted(c)[0] for c in componentes)[:3])
        return "INERTE", len(nombres), aristas, mayor, detalle

    con_raiz = [(c, a) for c, a in vivos if raiz in c]
    if con_raiz:
        c, a = con_raiz[0]
        detalle = "vivo=%s lee %s.%s" % (a[0], a[2], a[1])
        return "VIVO_RAIZ", len(nombres), aristas, mayor, detalle

    c, a = vivos[0]
    detalle = "vivo=%s lee %s.%s" % (a[0], a[2], a[1])
    golpes = set()
    for anc in ancestros(c, paquetes, raiz):
        golpes |= grafo.get(anc, set()) & c
    if golpes:
        detalle += " | via=" + ",".join(sorted(golpes)[:2])
    return "VIVO_HOJA", len(nombres), aristas, mayor, detalle


# --------------------------------------------------------------------------
# un paquete
# --------------------------------------------------------------------------
def censar(proj: str) -> dict:
    fila = {"proyecto": proj, "estado": "NO_MEDIDO", "modulos": 0,
            "aristas": 0, "ciclo_max": 0, "detalle": ""}
    try:
        data = json_pypi(proj)
        sdist, motivo = elegir_sdist(data)
        if sdist is None:
            fila["detalle"] = motivo
            return fila
        blob = traer(sdist["url"])
        archivos = leer_py(blob, sdist["filename"])
        modulos, motivo = modulos_del_paquete(archivos, proj)
        if modulos is None:
            fila["detalle"] = motivo
            return fila
        raiz = sorted(modulos, key=len)[0].split(".")[0]
        estado, nm, ne, cm, det = clasificar(modulos, raiz)
        fila.update(estado=estado, modulos=nm, aristas=ne, ciclo_max=cm, detalle=det)
        return fila
    except Exception as exc:  # el censo no se cae por un paquete
        fila["detalle"] = "%s: %s" % (type(exc).__name__, str(exc)[:60])
        return fila


# --------------------------------------------------------------------------
def self_test() -> int:
    """El censo se prueba con mutantes: la misma forma, viva e inerte."""
    fallos = 0
    casos = 0

    def caso(nombre, modulos, raiz, esperado):
        nonlocal fallos, casos
        casos += 1
        estado, _, _, _, det = clasificar(modulos, raiz)
        ok = estado == esperado
        print("  %-56s %-10s %s" % (nombre, estado, "OK" if ok else "FALLA esperaba " + esperado))
        if not ok:
            fallos += 1
            print("      detalle:", det)

    # --- la forma si detona: alguien lee al hermano a nivel de modulo -------
    caso("vivo: base<->features y base lee features.W al importar",
         {"p": b"from . import base\n",
          "p.base": b"from . import features\nfeatures.W\n",
          "p.features": b"from .base import W\nclass W: pass\n"},
         "p", "VIVO_HOJA")

    # --- la MISMA forma, muda al importar: forma de Django ------------------
    caso("inerte: el mismo ciclo, la lectura esta dentro de una funcion",
         {"p": b"from . import base\n",
          "p.base": b"from . import features\ndef f():\n    return features.W\n",
          "p.features": b"from .base import W\nclass W: pass\n"},
         "p", "INERTE")

    caso("inerte: la lectura es una ANOTACION (no se evalua al importar)",
         {"p": b"from . import base\n",
          "p.base": b"from . import features\ndef f(x: features.W):\n    return x\n",
          "p.features": b"from .base import W\nclass W: pass\n"},
         "p", "INERTE")

    caso("vivo: la lectura esta en el cuerpo de una CLASE (si se ejecuta)",
         {"p": b"from . import base\n",
          "p.base": b"from . import features\nclass W(features.Base): pass\n",
          "p.features": b"from .base import W\nclass Base: pass\n"},
         "p", "VIVO_HOJA")

    # --- formas que no son ciclo -------------------------------------------
    caso("sin ciclo",
         {"p": b"from . import base\n", "p.base": b"from . import sub\n", "p.sub": b"X=1\n"},
         "p", "NO")

    caso("import perezoso dentro de una funcion: no hay arista",
         {"p": b"from . import base\n",
          "p.base": b"def f():\n    from . import features\n    return features\n",
          "p.features": b"from .base import W\nclass W: pass\n"},
         "p", "NO")

    caso("TYPE_CHECKING no crea la arista del ancestro (el ciclo sigue vivo)",
         {"p": b"from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from . import base\n",
          "p.base": b"from . import features\nfeatures.W\n",
          "p.features": b"from .base import W\nclass W: pass\n"},
         "p", "VIVO_HOJA")

    # --- la raiz dentro del ciclo ------------------------------------------
    caso("la raiz misma dentro del ciclo vivo",
         {"p": b"from . import main\n",
          "p.main": b"import p\np.X\n"},
         "p", "VIVO_RAIZ")

    # --- forma de Django: la raiz calla, el __init__ interno es el que habla
    caso("forma de Django: raiz muda, el __init__ interno importa al ciclo",
         {"p": b"__version__ = '1'\n",
          "p.sub": b"from . import base\n",
          "p.sub.base": b"from . import features\nfeatures.W\n",
          "p.sub.features": b"from .base import W\nclass W: pass\n"},
         "p", "VIVO_HOJA")

    print("self-test: %d/%d" % (casos - fallos, casos))
    return 1 if fallos else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=60)
    ap.add_argument("--proyectos", default="",
                    help="lista explicita separada por comas (control positivo)")
    ap.add_argument("--salida", default="censo.tsv")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()

    if a.proyectos:
        universo = [(p.strip(), 0) for p in a.proyectos.split(",") if p.strip()]
        lista = {"last_update": "(control)", "source": "explicito", "rows": []}
        print("control explicito: %s\n" % ", ".join(p for p, _ in universo))
    else:
        lista = json.loads(traer(LISTA))
        universo = [(r["project"], r["download_count"]) for r in lista["rows"][: a.top]]
        print("universo: top %d de %d · last_update=%s · fuente=%s"
              % (a.top, len(lista["rows"]), lista["last_update"], lista["source"]))
    print("corte de tamano: %d MB por sdist\n" % MAX_MB)

    filas, t0 = [], time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        futuros = {ex.submit(censar, p): (p, d) for p, d in universo}
        for i, f in enumerate(as_completed(futuros), 1):
            fila = f.result()
            desc = futuros[f][1]
            fila["descargas"] = desc
            filas.append(fila)
            print("[%3d/%d] %-28s %-13s mod=%-4d ar=%-4d %s"
                  % (i, a.top, fila["proyecto"], fila["estado"],
                     fila["modulos"], fila["aristas"], fila["detalle"][:40]))

    filas.sort(key=lambda f: -f["descargas"])
    with open(a.salida, "w", encoding="utf-8") as fh:
        cols = ["proyecto", "estado", "modulos", "aristas", "ciclo_max", "detalle", "descargas"]
        fh.write("\t".join(cols) + "\n")
        for f in filas:
            fh.write("\t".join(str(f[c]).replace("\t", " ") for c in cols) + "\n")

    from collections import Counter
    cuenta = Counter(f["estado"] for f in filas)
    print("\n--- resultado ---")
    for estado, n in cuenta.most_common():
        print("  %-13s %d" % (estado, n))
    print("  escritas %d filas en %s · %.1f s" % (len(filas), a.salida, time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
