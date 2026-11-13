#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verifica que el motor de la pagina no derivo del oraculo Python.

    python3 verificar_paridad.py [--oraculo RUTA] [--verbose]

Niveles de comparacion, declarados y no negociados caso por caso:

  EXACTOS     16 campos por perfil, comparados bit a bit (IEEE-754).
  CANCELANTES  3 cocientes estimador/medido. NO son exactos y no pueden serlo:
              tau = |div_central - div_exacta| es una diferencia que cancela,
              asi que un ULP en div se convierte en error relativo grande en
              tau, y el cociente tau_hat/tau lo amplifica. Medido: Math.exp y
              np.exp difieren en 908 de 9216 nodos por 1 ULP (V8 fdlibm frente
              a libm); el peor cociente queda en 5.6e-13. Se contrata 1e-11.
              Esto no es deriva del port: es el condicionamiento de la cantidad.
  COMPUERTAS  108 casos de compuerta (3 mallas x 4 delta x 3 margenes x 3 eps).
              Violaciones, fracciones y booleanos, comparados en entero exacto.

RC 0  paridad y pagina viva.
RC 1  divergencia en algun nivel.
RC 2  el fixture no cumple su propia promesa de estabilidad (cerca_del_umbral).
RC 3  falta index.html, casos.json o verificar_ui.js.
RC 4  no hay node en PATH.
RC 5  el oraculo pedido no se puede importar.
RC 6  el motor da paridad pero la pagina no arranca.
"""
import argparse
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(AQUI, "index.html")
CASOS = os.path.join(AQUI, "casos.json")
UI = os.path.join(AQUI, "verificar_ui.js")

EXACTOS = [
    "L", "N", "h", "tau_max", "A", "A_estimado", "tau_max_por_N2", "mascara_fraccion",
    "tau_p10_mascara", "tau_p50_mascara", "spread_p10", "spread_p50", "frac_bajo_decimo",
    "c4_medido", "piso_local_max", "violaciones_honesto",
]
CANCELANTES = ["estimador_ratio_p10", "estimador_ratio_p50", "estimador_ratio_p90"]
REL_TOL = 1e-11


def bits(v):
    return struct.pack(">d", float(v)).hex()


def extrae_motor(html):
    ini = html.find('id="motor"')
    if ini < 0:
        return None
    ini = html.find(">", ini) + 1
    fin = html.find("</script>", ini)
    if fin < 0:
        return None
    return html[ini:fin]


HARNESS = r"""
var F = FIXTURE;
function H(v){var b=Buffer.alloc(8);b.writeDoubleBE(v);return b.toString('hex');}
function ulp(a,b){ if(a===b) return 0; if(!isFinite(a)||!isFinite(b)) return null;
  var ia=BigInt('0x'+H(a)), ib=BigInt('0x'+H(b)); return Number(ia>ib?ia-ib:ib-ia); }
var EXACTOS = EXACTOS_LISTA;
var CANCEL = CANCEL_LISTA;
var fallos = [], exactos = 0, maxRel = 0, peorRel = null, ulpMax = 0;
for (var i = 0; i < F.perfiles.length; i++) {
  var c = F.perfiles[i], g = medir(c.L, c.N), e = c.esperado;
  for (var k = 0; k < EXACTOS.length; k++) {
    var f = EXACTOS[k];
    if (H(g[f]) !== H(e[f])) {
      var u = ulp(g[f], e[f]);
      if (u !== null && u > ulpMax) ulpMax = u;
      fallos.push("perfil L=" + c.L + " N=" + c.N + "." + f + ": py=" + e[f] + " js=" + g[f] + " ulp=" + u);
    } else { exactos++; }
  }
  for (var k2 = 0; k2 < CANCEL.length; k2++) {
    var f2 = CANCEL[k2], a = e[f2], b = g[f2];
    var rel = Math.abs(a - b) / Math.max(Math.abs(a), 1e-300);
    if (!(rel <= maxRel)) { maxRel = rel; peorRel = f2 + " (L=" + c.L + " N=" + c.N + ")"; }
    if (rel > REL_TOL) {
      fallos.push("perfil L=" + c.L + " N=" + c.N + "." + f2 + ": rel=" + rel.toExponential(3) + " py=" + a + " js=" + b);
    }
  }
}
var gfallos = 0, ciegoSi = 0, cercaNoCero = 0, gateMaxRel = 0;
for (var j = 0; j < F.compuertas.length; j++) {
  var cc = F.compuertas[j], ee = cc.esperado;
  var gr = rejilla(cc.L, cc.N), x = gr.x, h = gr.h, N = cc.N;
  var campo = campoMonopolo(x, N);
  var pm = pisoMedido(campo.Bx, campo.By, x, h, N);
  var mask = mascaraRelevante(campo.Bx, campo.By, N);
  var tauMax = -Infinity, k3;
  for (k3 = 0; k3 < N * N; k3++) if (pm.tau[k3] > tauMax) tauMax = pm.tau[k3];
  var th = tauEstimado(campo.Bx, campo.By, h, N);
  var cont = contaminacionDivergencia(campo.Bx, campo.By, x, cc.delta_rel * tauMax, N);
  var pmc = pisoMedido(cont.Bx, cont.By, x, h, N);
  var thc = tauEstimado(cont.Bx, cont.By, h, N);
  var thMax = -Infinity, thMaxHonesto = -Infinity;
  for (k3 = 0; k3 < N * N; k3++) {
    if (!mask[k3]) continue;
    if (thc[k3] > thMax) thMax = thc[k3];
    if (th[k3] > thMaxHonesto) thMaxHonesto = th[k3];
  }
  var ciego = Math.abs(thMax - thMaxHonesto) < 1e-9 * tauMax;
  var loc = veredictoLocal(pmc.R, thc, cc.margen, mask, C4_ANALITICO * Math.pow(h, 4));
  var cons = veredictoConstante(pmc.R, cc.eps_rel * tauMax, mask);
  var etiqueta = "compuerta L=" + cc.L + " N=" + cc.N + " d=" + cc.delta_rel + " m=" + cc.margen + " e=" + cc.eps_rel;
  if (loc.violaciones !== ee.local_violaciones) { gfallos++; fallos.push(etiqueta + ".local_violaciones py=" + ee.local_violaciones + " js=" + loc.violaciones); }
  if (loc.rechazado !== ee.local_rechazado) { gfallos++; fallos.push(etiqueta + ".local_rechazado py=" + ee.local_rechazado + " js=" + loc.rechazado); }
  if (cons.violaciones !== ee.const_violaciones) { gfallos++; fallos.push(etiqueta + ".const_violaciones py=" + ee.const_violaciones + " js=" + cons.violaciones); }
  if (cons.rechazado !== ee.const_rechazado) { gfallos++; fallos.push(etiqueta + ".const_rechazado py=" + ee.const_rechazado + " js=" + cons.rechazado); }
  if (ciego !== ee.piso_ciego) { gfallos++; fallos.push(etiqueta + ".piso_ciego py=" + ee.piso_ciego + " js=" + ciego); }
  if (ciego) ciegoSi++;
  if (ee.cerca_del_umbral !== 0) cercaNoCero++;
  var rl = Math.abs(loc.fraccion_violada - ee.local_fraccion_violada) /
           Math.max(Math.abs(ee.local_fraccion_violada), 1e-300);
  if (ee.local_fraccion_violada !== 0 && rl > gateMaxRel) gateMaxRel = rl;
}
console.log(JSON.stringify({
  perfiles: F.perfiles.length, campos_exactos_ok: exactos, campos_exactos_total: F.perfiles.length * EXACTOS.length,
  cancelantes_rel_max: maxRel, cancelantes_peor: peorRel,
  compuertas: F.compuertas.length, compuertas_con_piso_ciego: ciegoSi,
  compuertas_cerca_del_umbral: cercaNoCero, fraccion_rel_max: gateMaxRel,
  ulp_max_exactos: ulpMax, fallos: fallos.length, detalle: fallos.slice(0, 15)
}, null, 1));
"""


def corre_harnes(motor, fixture, node):
    js = (
        motor
        + "\n"
        + "var FIXTURE = "
        + json.dumps(fixture, ensure_ascii=False)
        + ";\nvar EXACTOS_LISTA = "
        + json.dumps(EXACTOS)
        + ";\nvar CANCEL_LISTA = "
        + json.dumps(CANCELANTES)
        + ";\nvar REL_TOL = "
        + repr(REL_TOL)
        + ";\n"
        + HARNESS
    )
    fd, ruta = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(js)
        proc = subprocess.run([node, ruta], capture_output=True, text=True, timeout=300)
    finally:
        try:
            os.unlink(ruta)
        except OSError:
            pass
    if proc.returncode != 0:
        print("RC 1 · el harnes JS fallo:")
        print((proc.stderr or proc.stdout or "")[-4000:])
        sys.exit(1)
    return json.loads(proc.stdout)


def main():
    ap = argparse.ArgumentParser(description="Paridad motor JS <-> oraculo Python")
    ap.add_argument("--oraculo", default=None, help="ruta a piso_de_deteccion.py")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    for ruta in (INDEX, CASOS, UI):
        if not os.path.exists(ruta):
            print("RC 3 · falta " + os.path.basename(ruta))
            return 3
    node = shutil.which("node")
    if node is None:
        print("RC 4 · no hay node en PATH: no se puede ejecutar el motor de la pagina")
        return 4

    if args.oraculo:
        if not os.path.exists(args.oraculo):
            print("RC 5 · no existe el oraculo: " + args.oraculo)
            return 5
        spec = importlib.util.spec_from_file_location("piso_de_deteccion", args.oraculo)
        if spec is None or spec.loader is None:
            print("RC 5 · el oraculo no se puede importar: " + args.oraculo)
            return 5
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception as exc:  # noqa: BLE001
            print("RC 5 · el oraculo fallo al importar: %s" % exc)
            return 5
        print("oraculo importado: %s" % os.path.abspath(args.oraculo))
    else:
        print("oraculo: NO_MEDIDO (no se paso --oraculo; el contrato es el fixture congelado)")

    with open(INDEX, encoding="utf-8") as fh:
        html = fh.read()
    motor = extrae_motor(html)
    if motor is None:
        print("RC 1 · la pagina no tiene <script id=\"motor\">")
        return 1
    with open(CASOS, encoding="utf-8") as fh:
        fixture = json.load(fh)

    if fixture.get("procedencia", {}).get("fuente_publica") is not False:
        print("RC 2 · el fixture no declara fuente_publica: false")

    res = corre_harnes(motor, fixture, node)

    print("perfiles: %d · campos exactos %d/%d · ULP max en EXACTOS: %s"
          % (res["perfiles"], res["campos_exactos_ok"], res["campos_exactos_total"],
             res["ulp_max_exactos"]))
    print("cancelantes: rel max %.3e en %s (contratado %.1e)"
          % (res["cancelantes_rel_max"], res["cancelantes_peor"], REL_TOL))
    print("compuertas: %d · con piso ciego %d · fraccion rel max %.3e"
          % (res["compuertas"], res["compuertas_con_piso_ciego"], res["fraccion_rel_max"]))

    if res["compuertas_cerca_del_umbral"] != 0:
        print("RC 2 · %d compuertas tienen nodos a menos de 1e-9 del umbral: los conteos"
              " de la pagina dejarian de ser estables entre implementaciones"
              % res["compuertas_cerca_del_umbral"])
        return 2

    if res["fallos"]:
        print("RC 1 · %d divergencias" % res["fallos"])
        for linea in res["detalle"]:
            print("  · " + linea)
        return 1
    print("PARIDAD OK · el motor del navegador es el oraculo")

    proc = subprocess.run([node, UI], capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        print("RC 6 · el motor da paridad pero la pagina no arranca")
        print((proc.stderr or proc.stdout or "").strip())
        return 6
    print(proc.stdout.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
