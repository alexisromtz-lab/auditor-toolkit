#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verificar_paridad.py — el motor del navegador contra el oraculo Python.

QUE MIDE
--------
`index.html` contiene un `<script id="motor">` que es un puerto a JavaScript de
`nulo_de_remuestreo.py`. Un puerto puede divergir de su original sin que la
pagina deje de funcionar: los numeros salen, se ven razonables, y dicen otra
cosa. Este verificador extrae ese bloque —el MISMO texto que ejecuta el
navegador, no una copia paralela— lo corre bajo `node` sobre un fixture
congelado, y exige IGUALDAD EXACTA.

Exacta significa que cada numero se compara como su patron de bits IEEE-754 de
64 bits, no como texto ni con tolerancia. Dos motores que difieren en un ulp
son dos motores distintos, y aqui importa: el verificador devuelve un codigo de
retorno a partir de una comparacion `abs(media) <= banda` con banda = 0.2. Un
ulp no cambia el veredicto de hoy; una divergencia de flujo de bits si, y no se
anuncia.

LO QUE COSTO ENCONTRAR
----------------------
Portar las formulas no basta. Los remuestreadores consumen
`random.Random(semilla)`; si el flujo de enteros de 32 bits no coincide, los
mismos remuestreadores producen otras series y la paridad falla por una causa
que no aparece en el codigo del remuestreador. El puerto reproduce MT19937,
`random()`, `getrandbits`, `randbelow`, `randrange` y `shuffle` de CPython 3.12.

Y `randbelow` usa `n.bit_length()`, no `ceil(log2 n)`. Difieren cuando `n` es
potencia de dos —`bit_length(32) = 6`, `ceil(log2 32) = 5`—: con el equivocado,
el rechazo consume un entero de menos y todo el flujo se desplaza una posicion.
Medido antes de escribir la pagina: el primer `shuffle` divergia en el indice 9,
y los ocho anteriores coincidian.

CODIGOS
-------
RC 0  paridad exacta en todos los casos
RC 1  divergencia (nombra caso, campo, bit esperado y bit obtenido)
RC 2  el fixture no cuadra con el numero de casos que produce este archivo
RC 3  falta un archivo (HTML sin `<script id="motor">`, fixture ausente)
RC 4  no hay `node` en PATH
RC 5  el oraculo no se pudo importar o no publica lo que este archivo usa
RC 6  el motor da paridad pero la pagina no arranca (`verificar_ui.js` falla)

USO
---
    python3 verificar_paridad.py              # mide contra casos.json (RC 0/1/6)
    python3 verificar_paridad.py --oraculo P  # regenera casos.json desde el oraculo

LIMITE DECLARADO
----------------
Mide el motor y el contrato de arranque, no pixeles. Un CSS roto pasa con RC 0.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
HTML = AQUI / "index.html"
FIXTURE = AQUI / "casos.json"
UI = AQUI / "verificar_ui.js"

BANDA = 0.2
NIVEL = 0.95

# Campos flotantes y campos discretos se comparan distinto, y la diferencia es
# el hallazgo, no una comodidad.
#
# El oraculo eleva al cuadrado con `x ** 2`, que en CPython va a la `pow` de la
# libm del sistema. `pow(x, 2)` NO esta correctamente redondeada: medido en esta
# maquina, difiere de `x*x` en 375 de 300 000 valores (0,125 %), y ni V8 ni
# glibc reproducen a Apple libm (265 de 200 000 discrepancias). `x*x` en cambio
# es el producto IEEE-754, exactamente igual en Python y en JS (0 de 200 000).
#
# Consecuencia: ningun puerto fiel puede igualar esos bits sin reimplementar la
# libm del sistema, y un fixture que lo exigiera estaria clavado a una version
# de libm. Se porta `x*x` (que es MAS exacto) y se acota la diferencia con el
# ULP medido. Los campos discretos —los que deciden el veredicto de la pagina—
# se exigen identicos: ahi no hay redondeo que excuse nada.
FLOTANTES = ("empirico", "media_nula", "q_lo", "q_hi")
EXACTOS = ("destruye", "discrimina", "estado", "rc", "n_muestras")
CAMPOS = FLOTANTES + EXACTOS

# Medido sobre la bateria completa con el motor actual: 1 ULP, y solo en
# `media_nula`. El techo se declara en 4 —cuatro veces lo observado— porque mas
# alla ya no seria ruido de redondeo sino una divergencia de formula.
ULP_MAX = 4


# --- el fixture -----------------------------------------------------------


def par_ar(semilla: int, n: int, rho: float) -> list[list[float]]:
    """Generador de entrada de la pagina. Espejo de `par_ar` del motor.

    No es parte del oraculo: `verificar_nulo` recibe `datos` como argumento.
    Vive aqui para que la serie que el oraculo mide sea exactamente la que la
    pagina pinta, y para que cada caso del fixture se pueda reconstruir.
    """
    r = random.Random(semilla)
    x = [0.0]
    for _ in range(n - 1):
        x.append(rho * x[-1] + (2.0 * r.random() - 1.0))
    y = []
    for i in range(n):
        y.append(0.5 * x[i] + 0.5 * (2.0 * r.random() - 1.0))
    return [x, y]


NULOS = {
    "rotacion": lambda nulo, b: "rotacion",
    "iid": lambda nulo, b: "iid",
    "bloques": lambda nulo, b: ("bloques", b),
    "porSerie": lambda nulo, b: ("porSerie", b),
    "iidPorSerie": lambda nulo, b: "iidPorSerie",
}


def casos() -> list[dict]:
    """La bateria. Cubre los cuatro estados y los dos invariantes.

    NO se elige a mano lo que sale bien: si un estado no aparece, el fixture
    lo dira y el hueco se vera.
    """
    out: list[dict] = []
    for rho in (0.0, 0.3, 0.6, 0.9):
        for n in (400, 900):
            for rep in (60, 200):
                for nul, bloque in (("rotacion", 20), ("iid", 20),
                                    ("bloques", 1), ("bloques", 5), ("bloques", 20)):
                    out.append({"nombre": f"auto_{nul}_b{bloque}_rho{rho}_n{n}_r{rep}",
                                "inv": "auto", "nul": nul, "bloque": bloque,
                                "rho": rho, "n": n, "rep": rep,
                                "semilla_dato": 0, "semilla_nulo": 0})
                for nul, bloque in (("porSerie", 1), ("porSerie", 20), ("iidPorSerie", 20)):
                    out.append({"nombre": f"cruz_{nul}_b{bloque}_rho{rho}_n{n}_r{rep}",
                                "inv": "cruz", "nul": nul, "bloque": bloque,
                                "rho": rho, "n": n, "rep": rep,
                                "semilla_dato": 0, "semilla_nulo": 0})
    # NULO_NO_DISCRIMINA no se alcanza con series largas: el intervalo del nulo
    # queda mas estrecho que BANDA y todo lo medible lo rebasa. Solo aparece con
    # series cortas y senal debil, donde el ruido del nulo se traga el dato.
    # Estos tres casos vienen de un barrido sobre el oraculo, no de una corazonada.
    for rho, n, semilla in ((0.41, 50, 0), (0.23, 70, 1), (0.17, 90, 1)):
        out.append({"nombre": f"nodiscrimina_rho{rho}_n{n}",
                    "inv": "auto", "nul": "iid", "bloque": 20,
                    "rho": rho, "n": n, "rep": 200,
                    "semilla_dato": semilla, "semilla_nulo": 0})
    # la semilla del nulo mueve todo el flujo: si el puerto la ignora, estos
    # casos lo delatan y los demas no.
    for semilla in (1, 7, 12345):
        for nul, bloque in (("rotacion", 20), ("iid", 20), ("bloques", 20)):
            out.append({"nombre": f"semilla{semilla}_{nul}",
                        "inv": "auto", "nul": nul, "bloque": bloque,
                        "rho": 0.9, "n": 400, "rep": 60,
                        "semilla_dato": semilla, "semilla_nulo": semilla})
    return out


# --- el oraculo -----------------------------------------------------------


def cargar_oraculo(ruta: Path):
    import importlib.util
    if not ruta.exists():
        raise SystemExit(f"RC 5: oraculo ausente: {ruta}")
    spec = importlib.util.spec_from_file_location("oraculo_nulo", ruta)
    if spec is None or spec.loader is None:
        raise SystemExit(f"RC 5: no se pudo preparar la carga de {ruta}")
    mod = importlib.util.module_from_spec(spec)
    # `@dataclass` y las anotaciones resuelven tipos via sys.modules[__module__]:
    # sin registrar el modulo, la carga revienta con un TypeError que no
    # menciona ni el archivo ni la causa.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    for nombre in ("verificar_nulo", "remuestreo_rotacion", "remuestreo_iid",
                   "remuestreo_bloques", "remuestreo_bloques_por_serie",
                   "autocorrelacion", "correlacion_cruzada"):
        if not hasattr(mod, nombre):
            raise SystemExit(f"RC 5: el oraculo no publica `{nombre}`")
    return mod


def resolver_py(o, c: dict):
    b = c["bloque"]
    nul = c["nul"]
    if nul == "rotacion":
        rem = o.remuestreo_rotacion
    elif nul == "iid":
        rem = o.remuestreo_iid
    elif nul == "bloques":
        rem = lambda xs, rng, _b=b: o.remuestreo_bloques(xs, rng, _b)
    elif nul == "porSerie":
        rem = lambda p, rng, _b=b: o.remuestreo_bloques_por_serie(p, rng, _b)
    elif nul == "iidPorSerie":
        rem = lambda p, rng: [o.remuestreo_iid(s, rng) for s in p]
    else:
        raise SystemExit(f"RC 5: nulo desconocido en el fixture: {nul}")

    if c["inv"] == "cruz":
        est = lambda p: o.correlacion_cruzada(p[0], p[1])
    else:
        est = lambda xs: o.autocorrelacion(xs, 1)
    return rem, est


def bits(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    return struct.pack(">d", float(v)).hex()


def medir_py(o, c: dict) -> dict:
    rem, est = resolver_py(o, c)
    par = par_ar(c["semilla_dato"], c["n"], c["rho"])
    datos = par if c["inv"] == "cruz" else par[0]
    r = o.verificar_nulo(rem, datos, est, repeticiones=c["rep"],
                         semilla=c["semilla_nulo"], banda=BANDA, nivel=NIVEL)
    return {
        "nombre": c["nombre"],
        "empirico": bits(r.get("empirico")),
        "media_nula": bits(r.get("media_nula")),
        "q_lo": bits(r.get("q_lo")),
        "q_hi": bits(r.get("q_hi")),
        "destruye": r.get("destruye"),
        "discrimina": r.get("discrimina"),
        "estado": r.get("estado"),
        "rc": r.get("rc"),
        # el oraculo no publica las muestras; se re-cuentan para dejar
        # constancia de cuantas consumio cada caso.
        "n_muestras": 0 if r.get("estado") == "NO_MEDIDO" else c["rep"],
    }


# --- el motor del HTML ----------------------------------------------------

DRIVER = r"""
const fs = require('fs');
const bat = JSON.parse(fs.readFileSync(process.argv[2], 'utf8')).casos;

function bits(v) {
  if (v === null || v === undefined) return null;
  if (typeof v === 'boolean') return v;
  const b = new ArrayBuffer(8);
  new DataView(b).setFloat64(0, v);
  return Array.from(new Uint8Array(b)).map(function (x) {
    return x.toString(16).padStart(2, '0');
  }).join('');
}

function remDe(c) {
  const b = c.bloque;
  if (c.nul === 'rotacion') return remuestreo_rotacion;
  if (c.nul === 'iid') return remuestreo_iid;
  if (c.nul === 'bloques') return function (xs, rng) { return remuestreo_bloques(xs, rng, b); };
  if (c.nul === 'porSerie') return function (p, rng) { return remuestreo_bloques_por_serie(p, rng, b); };
  if (c.nul === 'iidPorSerie') return remuestreo_iid_por_serie;
  throw new Error('nulo desconocido: ' + c.nul);
}

function estDe(c) {
  if (c.inv === 'cruz') return function (p) { return correlacion_cruzada(p[0], p[1]); };
  return function (xs) { return autocorrelacion(xs, 1); };
}

const salida = bat.map(function (c) {
  const par = par_ar(c.semilla_dato, c.n, c.rho);
  const datos = (c.inv === 'cruz') ? par : par[0];
  const r = verificar_nulo(remDe(c), datos, estDe(c), c.rep, c.semilla_nulo, BANDA, 0.95);
  return {
    nombre: c.nombre,
    empirico: bits(r.empirico),
    media_nula: bits(r.media_nula),
    q_lo: bits(r.q_lo),
    q_hi: bits(r.q_hi),
    destruye: (r.destruye === undefined) ? null : r.destruye,
    discrimina: (r.discrimina === undefined) ? null : r.discrimina,
    estado: r.estado,
    rc: r.rc,
    n_muestras: r.muestras ? r.muestras.length : 0
  };
});
process.stdout.write(JSON.stringify(salida));
"""


def extraer_motor(html: str) -> str:
    m = re.search(r'<script id="motor">(.*?)</script>', html, re.S)
    if not m:
        raise SystemExit('RC 3: el HTML no tiene <script id="motor">; no hay nada que medir')
    return m.group(1)


def correr_node(motor: str, fixture: Path) -> list[dict]:
    if shutil.which("node") is None:
        raise SystemExit("RC 4: no hay `node` en PATH; sin el no se ejecuta el motor del HTML")
    with tempfile.TemporaryDirectory(prefix="paridad_nulo_") as tmp:
        js = Path(tmp) / "motor_y_driver.js"
        js.write_text(motor + "\n" + DRIVER, encoding="utf-8")
        p = subprocess.run(["node", str(js), str(fixture)], capture_output=True, text=True)
        if p.returncode != 0:
            raise SystemExit(f"RC 4: node fallo (RC {p.returncode}): {p.stderr.strip()[:900]}")
        return json.loads(p.stdout)


# --- comparacion ----------------------------------------------------------


def _clave(bits_hex: str) -> int:
    """Patron IEEE-754 a entero ordenado: la distancia entre dos claves es el
    numero de representables que hay entre los dos valores."""
    u = int(bits_hex, 16)
    return -(u & ~(1 << 63)) if (u >> 63) else u


def _ulp(a: str, b: str) -> int:
    return abs(_clave(a) - _clave(b))


def comparar(esperado: list[dict], obtenido: list[dict]) -> tuple[list[str], dict]:
    fallos: list[str] = []
    peor = {c: 0 for c in FLOTANTES}
    if len(esperado) != len(obtenido):
        return ([f"el motor devolvio {len(obtenido)} casos; el fixture tiene {len(esperado)}"],
                {"max_ulp": 0, "por_campo": peor})
    for e, g in zip(esperado, obtenido):
        if e["nombre"] != g.get("nombre"):
            fallos.append(f"{e['nombre']}: el motor nombra {g.get('nombre')!r}")
            continue
        for campo in FLOTANTES:
            a, b = e.get(campo), g.get(campo)
            if a is None or b is None:
                if a is not b:
                    fallos.append(f"{e['nombre']}.{campo}: oraculo={a!r} motor={b!r}")
                continue
            d = _ulp(a, b)
            peor[campo] = max(peor[campo], d)
            if d > ULP_MAX:
                fallos.append(f"{e['nombre']}.{campo}: {d} ULP (techo {ULP_MAX}) "
                              f"oraculo={a} motor={b}")
        for campo in EXACTOS:
            a, b = e.get(campo), g.get(campo)
            if a != b:
                fallos.append(f"{e['nombre']}.{campo}: oraculo={a!r} motor={b!r}")
    return fallos, {"max_ulp": max(peor.values()) if peor else 0, "por_campo": peor}


def estados(esperado: list[dict]) -> dict:
    cuenta: dict[str, int] = {}
    for e in esperado:
        cuenta[e["estado"]] = cuenta.get(e["estado"], 0) + 1
    return cuenta


def correr_ui() -> tuple[bool, str]:
    if not UI.exists() or shutil.which("node") is None:
        return True, "UI no medida (falta verificar_ui.js o node)"
    p = subprocess.run(["node", str(UI)], capture_output=True, text=True, cwd=str(AQUI))
    return p.returncode == 0, (p.stdout + p.stderr).strip()


def procedencia(oraculo: Path) -> dict:
    """Lo que se publica sobre de donde viene el fixture.

    El oraculo vive en un repositorio PRIVADO. Publicar su URL daria un enlace
    que da 404 a cualquiera que no tenga acceso: una cita que nadie puede
    seguir no es procedencia. Se declara el hecho y se da el comando que SI se
    puede correr sobre el material publico.
    """
    return {
        "fuente_publica": False,
        "oraculo": oraculo.name,
        "verificable": ("la pagina contra este fixture: verificar_paridad.py "
                        "(sin --oraculo)"),
        "regenerar": "verificar_paridad.py --oraculo <ruta al oraculo>",
    }


# --- main -----------------------------------------------------------------


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Paridad bit a bit del motor del navegador contra el oraculo.")
    ap.add_argument("--oraculo", type=Path, help="ruta a nulo_de_remuestreo.py; regenera casos.json")
    ap.add_argument("--sin-ui", action="store_true", help="no ejecutar verificar_ui.js")
    args = ap.parse_args(argv)

    if not HTML.exists():
        raise SystemExit(f"RC 3: falta {HTML}")
    motor = extraer_motor(HTML.read_text(encoding="utf-8"))
    bateria = casos()

    if args.oraculo:
        o = cargar_oraculo(args.oraculo)
        esperado = [medir_py(o, c) for c in bateria]
        doc = {
            "procedencia": procedencia(args.oraculo),
            "banda": BANDA,
            "nivel": NIVEL,
            "casos": [dict(c, esperado=e) for c, e in zip(bateria, esperado)],
        }
        FIXTURE.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        cuenta = estados(esperado)
        print(f"REGENERADO {FIXTURE.name}: {len(bateria)} casos desde {args.oraculo}")
        for k in sorted(cuenta):
            print(f"  {k}: {cuenta[k]}")
        return 0

    if not FIXTURE.exists():
        raise SystemExit(f"RC 3: falta {FIXTURE}; genera el fixture con --oraculo")
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    congelado = doc["casos"]
    if len(congelado) != len(bateria):
        raise SystemExit(
            f"RC 2: el fixture tiene {len(congelado)} casos y este archivo produce "
            f"{len(bateria)}. No es divergencia del motor: es un fixture viejo. "
            "Regeneralo con --oraculo."
        )
    esperado = [c["esperado"] for c in congelado]
    nombres = [c["nombre"] for c in congelado]

    obtenido = correr_node(motor, FIXTURE)
    # el motor reconstruye la bateria desde el fixture: si los nombres cambian,
    # se compara contra lo congelado por nombre, no por posicion.
    por_nombre = {g.get("nombre"): g for g in obtenido}
    ordenado = [por_nombre.get(nm, {"nombre": nm}) for nm in nombres]

    fallos, medido = comparar(esperado, ordenado)
    cuenta = estados(esperado)
    resumen = " · ".join(f"{k}={v}" for k, v in sorted(cuenta.items()))

    if fallos:
        print(f"RC 1: {len(fallos)} divergencias en {len(esperado)} casos ({resumen})", file=sys.stderr)
        for f in fallos[:20]:
            print(f"  {f}", file=sys.stderr)
        if len(fallos) > 20:
            print(f"  ... y {len(fallos) - 20} mas", file=sys.stderr)
        return 1

    if not args.sin_ui:
        ok, salida = correr_ui()
        if not ok:
            print("RC 6: el motor da paridad pero la pagina no arranca", file=sys.stderr)
            print(salida, file=sys.stderr)
            return 6

    detalle = " ".join(f"{c}={medido['por_campo'][c]}" for c in FLOTANTES)
    print(f"PARIDAD: {len(esperado)} casos ({resumen})")
    print(f"  discretos (estado · rc · destruye · discrimina · muestras): identicos")
    print(f"  flotantes: max {medido['max_ulp']} ULP de {ULP_MAX} declarados ({detalle})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
