#!/usr/bin/env python3
"""verificar_invariante_orden.py — la invariante de orden como propiedad medida.

Un ciclo de importacion no es un bug: es un bug CONDICIONAL AL ORDEN. Si el
paquete siempre carga `base` antes que `operations`, el ciclo no puede dispararse.
Django tiene 17 SCC y ninguno rompe en uso normal porque `django/db/utils.py:116`
hace `import_module("%s.base" % backend_name)`.

Este instrumento no predice. Ejecuta, tres veces por lector, en interprete limpio:

    P  positivo  import <lector>                  -> ROMPE_CICLO si el ciclo dispara
    N  negativo  import <destino>; import <lector> -> REPARA si el orden lo cura
    C  canonico  la ruta del propio framework      -> INMUNE si el cargador pasa

P y N son el mismo experimento cambiando UNA variable: el orden. Por eso el
control negativo no es un extra: es la unica prueba de que la causa es el orden
y no el entorno.

La leccion de GDAL esta codificada: un ImportError que NO diga "partially
initialized" o "circular import" se registra como OTRO y no cuenta como ciclo.
Una mascara por dependencia ausente nunca vuelve a ser un hallazgo.

    ./venv/bin/python verificar_invariante_orden.py --self-test
    ./venv/bin/python verificar_invariante_orden.py --paquete django \\
        --escrutinio escrutinio_django_v3.tsv --salida invariante_django.tsv \\
        --preludio "import django; django.setup()" \\
        --env DJANGO_SETTINGS_MODULE=settings_probe \\
        --env PYTHONPATH=<esta-carpeta>/bench

RC: 0 medido · 1 discrepancia de control · 2 argumentos · 3 el paquete no importa.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import os
import subprocess
import sys
import tempfile

CONTENEDORES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
TRY = tuple(t for t in (ast.Try, getattr(ast, "TryStar", None)) if t is not None)


# --------------------------------------------------------------------------
# resolucion de imports: que nombres liga una sentencia
# --------------------------------------------------------------------------
def _absoluto(modname: str, es_paquete: bool, nivel: int, modulo: str | None) -> str:
    if nivel == 0:
        return modulo or ""
    partes = modname.split(".")
    corte = len(partes) - nivel + (1 if es_paquete else 0)
    base = partes[:max(corte, 0)]
    if modulo:
        base = base + modulo.split(".")
    return ".".join(base)


class _Ligaduras(ast.NodeVisitor):
    """Sentencias de import con su contexto de ejecucion."""

    def __init__(self, modname: str, es_paquete: bool) -> None:
        self.modname = modname
        self.es_paquete = es_paquete
        self.pila: list[ast.AST] = []
        self.hallazgos: list[tuple[int, str, set[str]]] = []

    def _ctx(self) -> str:
        if any(isinstance(n, CONTENEDORES) for n in self.pila):
            return "funcion"
        if any(isinstance(n, TRY) for n in self.pila):
            return "try"
        if any(isinstance(n, ast.If) for n in self.pila):
            return "type_checking"
        return "modulo"

    def visit_FunctionDef(self, node):  # noqa: N802
        self.pila.append(node)
        self.generic_visit(node)
        self.pila.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815

    def visit_ClassDef(self, node):  # noqa: N802
        self.pila.append(node)
        self.generic_visit(node)
        self.pila.pop()

    def visit_Lambda(self, node):  # noqa: N802
        self.pila.append(node)
        self.generic_visit(node)
        self.pila.pop()

    def visit_Try(self, node):  # noqa: N802
        self.pila.append(node)
        self.generic_visit(node)
        self.pila.pop()

    def visit_If(self, node):  # noqa: N802
        guarda = any(
            isinstance(n, ast.Name) and n.id == "TYPE_CHECKING"
            for n in ast.walk(node.test or ast.Constant(None))
        )
        if guarda:
            self.pila.append(node)
            self.generic_visit(node)
            self.pila.pop()
        else:
            # un `if` normal se ejecuta: sus imports son module-level
            self.generic_visit(node)

    def visit_Import(self, node):  # noqa: N802
        objetivos = {a.name for a in node.names}
        self.hallazgos.append((node.lineno, self._ctx(), objetivos))

    def visit_ImportFrom(self, node):  # noqa: N802
        base = _absoluto(self.modname, self.es_paquete, node.level, node.module)
        objetivos = set()
        for a in node.names:
            if a.name == "*":
                continue
            objetivos.add(f"{base}.{a.name}" if base else a.name)
        if node.module and base:
            objetivos.add(base)
        self.hallazgos.append((node.lineno, self._ctx(), objetivos))


def ligaduras(modname: str, ruta: str, es_paquete: bool):
    try:
        with open(ruta, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
    except (SyntaxError, UnicodeDecodeError, OSError):
        return None
    v = _Ligaduras(modname, es_paquete)
    v.visit(tree)
    return v.hallazgos


# --------------------------------------------------------------------------
# poblacion
# --------------------------------------------------------------------------
def arbol(paquete: str) -> tuple[str, bool]:
    spec = importlib.util.find_spec(paquete)
    if spec is None or not spec.origin:
        raise SystemExit(f"RC 3: el paquete {paquete!r} no se puede localizar")
    return os.path.dirname(spec.origin), spec.submodule_search_locations is not None


def modulos_de(paquete: str, raiz: str) -> dict[str, tuple[str, bool]]:
    salida: dict[str, tuple[str, bool]] = {}
    for actual, _dirs, ficheros in os.walk(raiz):
        for f in ficheros:
            if not f.endswith(".py"):
                continue
            ruta = os.path.join(actual, f)
            rel = os.path.relpath(ruta, raiz)
            partes = rel[:-3].split(os.sep)
            es_paquete = partes[-1] == "__init__"
            if es_paquete:
                partes = partes[:-1]
            nombre = ".".join([paquete] + partes)
            if nombre == paquete and not es_paquete:
                continue
            salida[nombre] = (ruta, es_paquete)
    return salida


def lectores(paquete: str, raiz: str, miembros: set[str]) -> list[tuple[str, int, str, set[str]]]:
    """(lector, linea, contexto, destinos_del_scc) fuera del SCC, a nivel modulo."""
    salida = []
    for nombre, (ruta, es_paquete) in modulos_de(paquete, raiz).items():
        if nombre in miembros:
            continue
        for linea, ctx, objetivos in ligaduras(nombre, ruta, es_paquete) or []:
            dentro = objetivos & miembros
            if dentro:
                salida.append((nombre, linea, ctx, dentro))
    return salida


def leer_escrutinio(ruta: str) -> list[tuple[int, int, set[str]]]:
    filas = []
    with open(ruta, encoding="utf-8") as fh:
        cab = fh.readline().split("\t")
        i_scc = cab.index("scc")
        i_tam = cab.index("tam")
        i_miem = cab.index("miembros")
        for linea in fh:
            c = linea.rstrip("\n").split("\t")
            if len(c) <= i_miem:
                continue
            m = {x for x in c[i_miem].split(";") if x}
            if not m:
                continue
            filas.append((int(c[i_scc]), int(c[i_tam]), m))
    return filas


# --------------------------------------------------------------------------
# sondas: ejecucion, no prediccion
# --------------------------------------------------------------------------
def sonda(python: str, preludio: str, lineas: str, env_extra: dict[str, str]) -> tuple[str, str]:
    codigo = (preludio + "\n" if preludio.strip() else "") + lineas
    env = dict(os.environ)
    env.update(env_extra)
    p = subprocess.run([python, "-c", codigo], capture_output=True, text=True, env=env)
    if p.returncode == 0:
        return "PASA", ""
    ultima = [x for x in p.stderr.strip().splitlines() if x.strip()]
    fin = ultima[-1] if ultima else ""
    if "ImportError" in p.stderr and (
        "partially initialized" in p.stderr or "circular import" in p.stderr
    ):
        return "ROMPE_CICLO", fin
    return "OTRO", fin


def clasificar(python, preludio, env_extra, lector, destinos, miembros, universo=None) -> dict:
    """P positivo, N negativo. N prueba cada candidato como predecesor: el que el
    lector lee puede ser el roto, asi que fijar uno solo convertiria el control
    negativo en una moneda al aire. Y el reparador NO tiene por que vivir en el
    SCC que se rompe: medido en django, `oracle.operations` rompe a traves de
    db.models y solo lo repara `oracle.base`, que es de otro ciclo. Por eso se
    reportan los dos vecindarios."""
    pos, m_pos = sonda(python, preludio, f"import {lector}", env_extra)
    fila = {"lector": lector, "positivo": pos, "negativo": "-", "negativo_global": "-",
            "reparan_por": [], "reparan_por_global": [], "mensaje": m_pos}
    if pos != "ROMPE_CICLO":
        return fila

    def _prueba(candidatos):
        for d in candidatos:
            if d == lector or d.startswith(lector + "."):
                continue
            neg, _ = sonda(python, preludio, f"import {d}\nimport {lector}", env_extra)
            if neg == "PASA":
                return d
        return None

    local = _prueba([d for d in sorted(miembros) if d != lector])
    if local:
        fila["reparan_por"] = [local]
    fila["negativo"] = "PASA" if local else "ROMPE"

    # vecindario propio primero (barato y es el que el lector toca), luego el resto
    prefijo = lector.rsplit(".", 2)[0]
    resto = [d for d in sorted(universo or miembros) if d != lector]
    cerca = [d for d in resto if d.startswith(prefijo)]
    lejos = [d for d in resto if not d.startswith(prefijo)]
    glob = local or _prueba(cerca) or _prueba(lejos)
    if glob:
        fila["reparan_por_global"] = [glob]
    fila["negativo_global"] = "PASA" if glob else "ROMPE"
    return fila


# --------------------------------------------------------------------------
# control sintetico: positivo Y negativo, con el mismo codigo que se mide
# --------------------------------------------------------------------------
SINTETICO = {
    "__init__.py": "",
    "base.py": (
        "class Database:\n"
        "    pass\n"
        "from .operations import DatabaseOperations\n"
    ),
    "operations.py": (
        "from .utils import BoundVar\n"
        "class DatabaseOperations:\n"
        "    pass\n"
    ),
    "utils.py": (
        "from .base import Database\n"
        "class BoundVar:\n"
        "    pass\n"
    ),
    "consumer_bad.py": "from .operations import DatabaseOperations\n",
    "consumer_ok.py": "from .base import Database\n",
}


def self_test(python: str) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        pkg = os.path.join(tmp, "synciclo")
        os.makedirs(pkg)
        for nombre, cuerpo in SINTETICO.items():
            with open(os.path.join(pkg, nombre), "w", encoding="utf-8") as fh:
                fh.write(cuerpo)
        env = {"PYTHONPATH": tmp}
        miembros = {"synciclo.base", "synciclo.operations", "synciclo.utils"}

        # 1. el ciclo dispara cuando se entra por operations
        pos, _ = sonda(python, "", "import synciclo.operations", env)
        # 2. y NO dispara cuando base va primero: el control negativo
        neg, _ = sonda(python, "", "import synciclo.base\nimport synciclo.operations", env)
        # 3. el lector inseguro rompe y se repara con base delante; el seguro pasa
        malo = clasificar(python, "", env, "synciclo.consumer_bad",
                          {"synciclo.operations"}, miembros)
        bueno = clasificar(python, "", env, "synciclo.consumer_ok",
                           {"synciclo.base"}, miembros)
        # 4. la mascara por dependencia ausente NO cuenta como ciclo
        otro, _ = sonda(python, "", "import modulo_que_no_existe_xyz", env)

        fallos = []
        if pos != "ROMPE_CICLO":
            fallos.append(f"control positivo: esperaba ROMPE_CICLO, dio {pos}")
        if neg != "PASA":
            fallos.append(f"control negativo: esperaba PASA, dio {neg}")
        if malo["positivo"] != "ROMPE_CICLO":
            fallos.append(f"consumer_bad: esperaba ROMPE_CICLO, dio {malo['positivo']}")
        if malo["negativo"] != "PASA":
            fallos.append(f"consumer_bad no se repara con base delante: {malo['reparan_por']}")
        if bueno["positivo"] != "PASA":
            fallos.append(f"consumer_ok: esperaba PASA, dio {bueno['positivo']}")
        if otro == "ROMPE_CICLO":
            fallos.append("una dependencia ausente conto como ciclo: la leccion de GDAL no esta aplicada")

        for f in fallos:
            print(f"FALLA  {f}")
        print(f"self-test: positivo={pos} negativo={neg} otro={otro} "
              f"malo={malo['positivo']}/{malo['negativo']} bueno={bueno['positivo']}")
        return 1 if fallos else 0


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--paquete")
    ap.add_argument("--escrutinio")
    ap.add_argument("--salida")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--preludio", default="")
    ap.add_argument("--env", action="append", default=[], metavar="K=V")
    ap.add_argument("--cargador", default="", help="ruta canonica del framework")
    a = ap.parse_args()

    if a.self_test:
        return self_test(a.python)
    if not (a.paquete and a.escrutinio and a.salida):
        ap.print_usage()
        return 2

    env_extra = {}
    for kv in a.env:
        if "=" not in kv:
            return 2
        k, v = kv.split("=", 1)
        env_extra[k] = v

    raiz, _es_pkg = arbol(a.paquete)
    filas = leer_escrutinio(a.escrutinio)

    cargador = ""
    if a.cargador:
        cargador, m = sonda(a.python, a.preludio, a.cargador, env_extra)
        print(f"cargador canonico: {cargador}  {m}")

    salida = [
        "paquete\tscc\ttam\tlectores_modulo\trompen\treparan\treparan_global\totro\tcelda\tdetalle"
    ]
    universo = sorted({m for _s, _t, ms in filas for m in ms})
    for scc, tam, miembros in filas:
        hallados = lectores(a.paquete, raiz, miembros)
        seguros = [h for h in hallados if h[2] == "modulo"]
        medidos = [
            clasificar(a.python, a.preludio, env_extra, h[0], h[3], miembros, universo)
            for h in seguros
        ]
        rompen = [m for m in medidos if m["positivo"] == "ROMPE_CICLO"]
        reparan = [m for m in rompen if m["negativo"] == "PASA"]
        reparan_g = [m for m in rompen if m["negativo_global"] == "PASA"]
        otros = [m for m in medidos if m["positivo"] == "OTRO"]
        if not rompen:
            celda = "INERTE"
        elif cargador == "PASA":
            celda = "INMUNE_CONSTRUCCION"
        elif cargador == "ROMPE_CICLO":
            celda = "MINA_VIVA"
        else:
            celda = "MINA_VIVA"
        detalle = ";".join(
            f"{m['lector']}:{m['positivo']}/{m['negativo']}/{m['negativo_global']}"
            f"[{(m['reparan_por_global'] or ['-'])[0]}]"
            for m in rompen
        ) or "-"
        salida.append(
            f"{a.paquete}\t{scc}\t{tam}\t{len(hallados)}\t{len(rompen)}\t"
            f"{len(reparan)}\t{len(reparan_g)}\t{len(otros)}\t{celda}\t{detalle}"
        )

    with open(a.salida, "w", encoding="utf-8") as fh:
        fh.write("\n".join(salida) + "\n")
    for linea in salida:
        print(linea)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
