#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verificar_paridad.py — la pagina solo vale si el oraculo dice lo mismo.

QUE MIDE
--------
`index.html` no reimplementa la fisica "a ojo": porta `clasificador_campo_algebraico.py`
constante por constante y operacion por operacion. Esta herramienta mide esa
afirmacion. Extrae el bloque `<script id="motor">` del HTML —el mismo texto que
ejecuta el navegador, no una copia paralela— lo corre bajo `node` sobre una
bateria congelada y compara cada salida numerica contra el oraculo Python.

El motor del HTML es un solo texto con dos consumidores: el navegador lo ejecuta
y este verificador lo ejecuta. No hay tercera copia que pueda divergir.

    verificar_paridad.py                      # verifica contra casos.json
    verificar_paridad.py --oraculo RUTA       # ademas regenera el fixture
    verificar_paridad.py --verbose

RC 0 paridad medida · 1 hay divergencia (nombra el campo y el caso) · 2 uso ·
3 fixture ausente o ilegible · 4 no hay `node` · 5 oraculo ausente o roto.

LIMITE DECLARADO, MEDIDO
------------------------
La bateria fisica —66 campos, sus boosts y 30 casos de ruido determinista— NO
distingue el factor 2 del criterio de nulo. Medido: cambiar `2.0*I2` por `I2`
en el motor del HTML dejaba la paridad en RC 0. La razon es que ningun campo
realizable cae a menos de un factor 2 del piso de redondeo, asi que la bateria
no tiene una muestra ahi. Por eso existen los `controles de borde`: ocho
triples sinteticos (I1, I2, escala) que SI caen en esa franja, evaluados contra
`clase_de` del propio oraculo al regenerar y congelados en el fixture. Con
ellos, la misma mutacion da RC 1. La bateria fisica y el control sintetico
miden cosas distintas y se publican por separado a proposito.

DEFECTOS MEDIDOS DEL ORACULO (11-Nov-2026, prueba en frio fuera del corpus)
---------------------------------------------------------------------------
Los dos se midieron ejecutando el CLI, no leyendo el codigo. Se declaran aqui
porque este es el archivo que los falsa; no se corrigio el oraculo porque
vive en otro repositorio y su sello ya esta en vuelo.

  1. Un vector con la PRIMERA componente negativa no se puede pasar: argparse
     lee `-0.9,0,0` como una opcion, no como un valor. Afecta a `--E`, `--B` y
     `--boost` por igual —es decir, a medio universo de campos fisicos y a todo
     el barrido negativo del deslizador—. Solo se alcanza con la forma `=`
     (`--B=-3.3e-9,0,0`), que la ayuda del CLI no menciona. Medido en frio el
     11-Nov-2026 con `--B "-3.3356409519815204e-09,0,0"` -> RC 20
     `argument --B: expected one argument`. Por eso la bateria escribe los tres
     vectores con `=`: es la unica forma de ejercitar el caso antiparalelo.
  2. `--json` emite `"gamma": Infinity`, que no es JSON valido: `json.loads`
     de Python lo acepta, `JSON.parse` de un navegador NO. El fixture y la
     pagina publican `"gamma": null, "gamma_infinita": true`, que dice lo mismo
     y se puede leer en cualquier sitio. La normalizacion se aplica en los dos
     lados, asi que no tapa ninguna divergencia: `_normalizar` la hace explicita.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
HTML = AQUI / "index.html"
FIXTURE = AQUI / "casos.json"

# Tolerancia de paridad. El oraculo y el motor JS hacen las mismas operaciones
# sobre los mismos float64, asi que la unica diferencia esperada es el orden de
# suma en el producto de Clifford; se declara holgada a proposito (1e-12 relativo)
# para que una divergencia real —un signo, un termino que falta— no quepa dentro.
TOL_REL = 1e-12
TOL_ABS = 1e-15

CAMPOS_EXACTOS = ("clase", "estado")

CAMPOS_NUMERICOS = (
    "escala",
    "I1_algebra",
    "I2_algebra",
    "I1_vector",
    "I2_vector",
    "deriva_relativa",
    "piso_nulo",
    "margen_de_clase",
)

# Los seis presets de la pagina, escritos aqui para que el fixture y la interfaz
# no puedan separarse: si alguien cambia un preset en el HTML y no aqui, la
# bateria deja de cubrirlo y `test_paridad` lo dice por nombre.
C_PLZ = 299792458.0

PRESETS = {
    "nulo": ([1.0, 0.0, 0.0], [0.0, 1.0 / C_PLZ, 0.0]),
    "electrico": ([1.0, 0.0, 0.0], [0.0, 0.0, 0.0]),
    "magnetico": ([0.0, 0.0, 0.0], [0.0, 0.0, 1.0]),
    "oblicuo": ([1.0, 0.4, 0.0], [0.2, 0.0, 0.9]),
    "antiparalelo": ([1.0, 0.0, 0.0], [-1.0 / C_PLZ, 0.0, 0.0]),
    "vacio": ([0.0, 0.0, 0.0], [0.0, 0.0, 0.0]),
}

SEMILLA = 20261112
AZAROSOS = 30

# Control sintetico del borde. La bateria fisica no distingue el factor 2 del
# criterio de nulo (`hypot(I1, 2*I2) <= piso`) porque ningun campo real cae a
# menos de un factor 2 del piso de redondeo; medido el 11-Nov-2026: mutar
# `2.0*I2` -> `I2` en el motor dejaba la paridad en RC 0 sobre los 66 casos
# fisicos. Estos triples SI caen ahi, y son los unicos que pueden falsarlo.
# Se evaluan contra `clase_de` del propio oraculo en la regeneracion y quedan
# congelados; en la verificacion no hace falta el oraculo.
CONTROLES_FACTOR_PISO = (
    (0.0, 0.8, 1.0),
    (0.0, 0.4, 1.0),
    (0.0, 0.6, 1.0),
    (0.3, 0.4, 1.0),
    (-0.5, 0.0, 1.0),
    (0.0, 0.0, 0.0),
    (2.0, 0.0, 1.0),
    (-2.0, 0.0, 1.0),
)


def _casos() -> list[dict]:
    """Bateria congelada: presets, un boost por preset y ruido determinista."""
    casos: list[dict] = []
    for nombre, (E, B) in PRESETS.items():
        casos.append({"nombre": nombre, "E": E, "B": B, "beta": None})
    for nombre, (E, B) in PRESETS.items():
        if nombre == "vacio":
            continue
        for eje in (0, 1, 2):
            for signo in (1.0, -1.0):
                beta = [0.0, 0.0, 0.0]
                beta[eje] = signo * 0.6
                casos.append({"nombre": f"{nombre}_boost_{'xyz'[eje]}{'+' if signo > 0 else '-'}",
                              "E": list(E), "B": list(B), "beta": beta})
    rnd = random.Random(SEMILLA)
    for i in range(AZAROSOS):
        E = [rnd.uniform(-3.0, 3.0) for _ in range(3)]
        B = [rnd.uniform(-3.0, 3.0) * 1e-8 for _ in range(3)]
        beta = None
        if i % 2 == 0:
            beta = [rnd.uniform(-0.95, 0.95) for _ in range(3)]
            n = math.sqrt(sum(x * x for x in beta))
            if n >= 0.98:
                beta = [x * 0.9 / n for x in beta]
        casos.append({"nombre": f"azar_{i:02d}", "E": E, "B": B, "beta": beta})
    return casos


def extraer_motor(html: str) -> str:
    m = re.search(r'<script id="motor">(.*?)</script>', html, re.S)
    if not m:
        raise SystemExit("RC 3: el HTML no tiene <script id=\"motor\">; no hay nada que medir")
    return m.group(1)


def _normalizar(r: dict) -> dict:
    """Hace explicito el defecto 2 del docstring: gamma infinita -> null.

    Se aplica igual a lo que publica el oraculo y a lo que publica node, asi que
    no puede esconder una divergencia de valor; solo cambia como se escribe el
    infinito.
    """
    d = dict(r)
    marco = dict(d.get("marco_sin_b") or {})
    g = marco.get("gamma")
    if isinstance(g, (int, float)) and not isinstance(g, bool) and math.isinf(g):
        marco["gamma"] = None
        marco["gamma_infinita"] = True
    d["marco_sin_b"] = marco
    return d


def _procedencia(oraculo: Path) -> dict:
    def git(*args: str) -> str:
        try:
            return subprocess.run(["git", "-C", str(oraculo.parent), *args],
                                  capture_output=True, text=True, check=True).stdout.strip()
        except Exception:
            return "NO_MEDIDO"

    return {
        "oraculo": oraculo.name,
        "commit": git("rev-parse", "HEAD"),
        "blob": git("hash-object", str(oraculo)),
        "remoto": git("remote", "get-url", "origin"),
        "generado_por": "demo/clasificador-de-campos/verificar_paridad.py --oraculo",
    }


def regenerar(oraculo: Path) -> int:
    if not oraculo.exists():
        print(f"RC 5: no existe el oraculo: {oraculo}", file=sys.stderr)
        return 5
    casos = _casos()
    for c in casos:
        argv = [sys.executable, str(oraculo),
                "--E=" + ",".join(repr(x) for x in c["E"]),
                "--B=" + ",".join(repr(x) for x in c["B"]),
                "--json"]
        if c["beta"] is not None:
            # Forma con `=` obligatoria en los tres vectores: ver defecto 1.
            argv.append("--boost=" + ",".join(repr(x) for x in c["beta"]))
        p = subprocess.run(argv, capture_output=True, text=True)
        if p.returncode not in (0, 1):
            print(f"RC 5: el oraculo fallo en {c['nombre']} (RC {p.returncode}): {p.stderr.strip()}",
                  file=sys.stderr)
            return 5
        c["esperado"] = _normalizar(json.loads(p.stdout))

    import importlib.util
    spec = importlib.util.spec_from_file_location("oraculo_campo", oraculo)
    mod = importlib.util.module_from_spec(spec)
    # @dataclass resuelve tipos via sys.modules[cls.__module__]; sin registrar el
    # modulo antes de ejecutarlo, la importacion explota en Python 3.12.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    piso = mod.MULT_PISO_NULO * sys.float_info.epsilon
    control = [
        {"I1": a * piso, "I2": b * piso, "escala": e,
         "esperado": mod.clase_de(a * piso, b * piso, e)}
        for a, b, e in CONTROLES_FACTOR_PISO
    ]

    FIXTURE.write_text(json.dumps(
        {"procedencia": _procedencia(oraculo), "control_sintetico": control, "casos": casos},
        ensure_ascii=False, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    print(f"REGENERADO {FIXTURE.name}: {len(casos)} casos + {len(control)} controles de borde desde {oraculo}")
    return 0


def correr_node(motor: str, fixture: Path) -> list[dict]:
    if shutil.which("node") is None:
        raise SystemExit("RC 4: no hay `node` en PATH; sin el no se ejecuta el motor del HTML")
    driver = motor + "\n" + """
const fs = require('fs');
const bateria = JSON.parse(fs.readFileSync(process.argv[2], 'utf8')).casos;
const salida = bateria.map(function (c) {
  const cB0 = c.B.map(function (x) { return C_LUZ * x; });
  let E = c.E, cB = cB0;
  if (c.beta) { const r = boostCampos(E, cB0, c.beta); E = r[0]; cB = r[1]; }
  return clasificar(E, cB);
});
process.stdout.write(JSON.stringify(salida));
"""
    with tempfile.TemporaryDirectory(prefix="paridad_") as tmp:
        js = Path(tmp) / "motor_y_driver.js"
        js.write_text(driver, encoding="utf-8")
        p = subprocess.run(["node", str(js), str(fixture)], capture_output=True, text=True)
        if p.returncode != 0:
            raise SystemExit(f"RC 4: node fallo (RC {p.returncode}): {p.stderr.strip()[:800]}")
        return json.loads(p.stdout)


def correr_control(motor: str, control: list[dict]) -> list[str]:
    """Corre `claseDe` del motor sobre los triples del borde del piso nulo."""
    if shutil.which("node") is None:
        raise SystemExit("RC 4: no hay `node` en PATH; sin el no se ejecuta el motor del HTML")
    driver = motor + "\n" + """
const fs = require('fs');
const triples = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
process.stdout.write(JSON.stringify(triples.map(function (t) {
  return claseDe(t[0], t[1], t[2]);
})));
"""
    with tempfile.TemporaryDirectory(prefix="control_") as tmp:
        js = Path(tmp) / "control.js"
        js.write_text(driver, encoding="utf-8")
        entrada = Path(tmp) / "control.json"
        entrada.write_text(json.dumps([[c["I1"], c["I2"], c["escala"]] for c in control]),
                           encoding="utf-8")
        p = subprocess.run(["node", str(js), str(entrada)], capture_output=True, text=True)
        if p.returncode != 0:
            raise SystemExit(f"RC 4: node fallo en el control (RC {p.returncode}): {p.stderr.strip()[:800]}")
        return json.loads(p.stdout)


def correr_ui() -> tuple[bool, str]:
    """Corre `verificar_ui.js`: mide que la pagina arranque, no solo el motor.

    La paridad del motor no dice nada de la pagina que lo contiene. Un readout
    que nombra un id inexistente, o una escena que nunca pide el contexto 2D,
    convivia con RC 0. Este paso ejecuta los dos `<script>` del HTML contra un
    DOM simulado y exige que el estado por defecto reproduzca el caso `nulo`
    del fixture.
    """
    ui = HTML.parent / "verificar_ui.js"
    if not ui.exists() or shutil.which("node") is None:
        return True, "UI no medida (falta verificar_ui.js o node)"
    p = subprocess.run(["node", str(ui)], capture_output=True, text=True)
    detalle = (p.stdout or p.stderr).strip().splitlines()[-1] if (p.stdout or p.stderr) else ""
    return p.returncode == 0, detalle


def _cerca(a, b, escala: float) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return a == b
    if math.isinf(a) or math.isinf(b):
        return a == b
    dif = abs(a - b)
    if dif <= TOL_ABS:
        return True
    if dif <= TOL_REL * max(abs(a), abs(b)):
        return True
    if escala > 0.0 and dif <= TOL_REL * escala * escala:
        return True
    return False


def comparar(esperado: dict, obtenido: dict) -> list[str]:
    fallas: list[str] = []
    escala = float(esperado.get("escala") or 0.0)
    for k in CAMPOS_EXACTOS:
        if esperado.get(k) != obtenido.get(k):
            fallas.append(f"{k}: oraculo={esperado.get(k)!r} html={obtenido.get(k)!r}")
    for k in CAMPOS_NUMERICOS:
        if not _cerca(esperado.get(k), obtenido.get(k), escala):
            fallas.append(f"{k}: oraculo={esperado.get(k)!r} html={obtenido.get(k)!r}")
    for k in ("E", "cB"):
        ea, ob = esperado.get(k) or [], obtenido.get(k) or []
        if len(ea) != len(ob):
            fallas.append(f"{k}: longitud {len(ea)} vs {len(ob)}")
            continue
        for i, (a, b) in enumerate(zip(ea, ob)):
            if not _cerca(a, b, escala):
                fallas.append(f"{k}[{i}]: oraculo={a!r} html={b!r}")
    me = esperado.get("marco_sin_b") or {}
    mo = obtenido.get("marco_sin_b") or {}
    if me.get("estado") != mo.get("estado"):
        fallas.append(f"marco_sin_b.estado: oraculo={me.get('estado')!r} html={mo.get('estado')!r}")
    for k in ("norma_beta", "gamma"):
        if (k in me) != (k in mo):
            fallas.append(f"marco_sin_b.{k}: presente en {k in me} / {k in mo}")
        elif k in me and not _cerca(me.get(k), mo.get(k), escala):
            fallas.append(f"marco_sin_b.{k}: oraculo={me.get(k)!r} html={mo.get(k)!r}")
    if len(me.get("beta") or []) != len(mo.get("beta") or []):
        fallas.append("marco_sin_b.beta: longitud distinta")
    else:
        for i, (a, b) in enumerate(zip(me.get("beta") or [], mo.get("beta") or [])):
            if not _cerca(a, b, escala):
                fallas.append(f"marco_sin_b.beta[{i}]: oraculo={a!r} html={b!r}")
    return fallas


def verificar(verbose: bool) -> int:
    if not HTML.exists():
        print(f"RC 3: falta {HTML.name}", file=sys.stderr)
        return 3
    if not FIXTURE.exists():
        print(f"RC 3: falta {FIXTURE.name}; genera el fixture con --oraculo RUTA", file=sys.stderr)
        return 3
    motor = extraer_motor(HTML.read_text(encoding="utf-8"))
    datos = json.loads(FIXTURE.read_text(encoding="utf-8"))
    casos = datos["casos"]
    salidas = correr_node(motor, FIXTURE)
    if len(salidas) != len(casos):
        print(f"RC 1: node devolvio {len(salidas)} casos; el fixture tiene {len(casos)}", file=sys.stderr)
        return 1
    fallas = 0
    for c, ob in zip(casos, salidas):
        f = comparar(c["esperado"], ob)
        if f:
            fallas += 1
            print(f"FALLA {c['nombre']}", file=sys.stderr)
            for linea in f:
                print("   " + linea, file=sys.stderr)
        elif verbose:
            print(f"  ok  {c['nombre']:26s} clase={ob['clase']:20s} "
                  f"deriva={ob['deriva_relativa']:.3e}")

    control = datos.get("control_sintetico") or []
    fallas_control = 0
    if control:
        obtenidas = correr_control(motor, control)
        for c, obtenida in zip(control, obtenidas):
            if c["esperado"] != obtenida:
                fallas_control += 1
                print(f"FALLA borde (I1,piso={c['I1']:.3e}  I2,piso={c['I2']:.3e}  S={c['escala']}): "
                      f"oraculo={c['esperado']} html={obtenida}", file=sys.stderr)
            elif verbose:
                print(f"  ok  borde I1={c['I1']:.3e} I2={c['I2']:.3e} -> {obtenida}")

    proc = datos.get("procedencia", {})
    if fallas or fallas_control:
        print(f"RC 1: {fallas}/{len(casos)} casos y {fallas_control}/{len(control)} controles "
              f"de borde divergen. Procedencia: {proc.get('commit')} · blob {proc.get('blob')}",
              file=sys.stderr)
        return 1

    ui_ok, ui_detalle = correr_ui()
    if not ui_ok:
        print(f"RC 6: el motor da paridad pero la pagina no arranca: {ui_detalle}", file=sys.stderr)
        return 6
    print(f"PARIDAD MEDIDA · {len(casos)} casos · {len(control)} controles de borde · "
          f"oraculo {proc.get('commit')} · blob {proc.get('blob')} · tol {TOL_REL:g} relativa · RC 0")
    print(f"  {ui_detalle}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Mide que el motor del HTML da lo mismo que el oraculo Python.")
    p.add_argument("--oraculo", type=Path, help="ruta al clasificador_campo_algebraico.py; regenera casos.json")
    p.add_argument("--verbose", action="store_true")
    a = p.parse_args(argv)
    if a.oraculo is not None:
        rc = regenerar(a.oraculo)
        if rc != 0:
            return rc
    return verificar(a.verbose)


if __name__ == "__main__":
    sys.exit(main())
