#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenera casos.json desde el oraculo congelado.

    python3 generar_casos.py --oraculo <ruta a piso_de_deteccion.py>

El oraculo NO vive en este repositorio publico: vive en el corpus privado de
Platino Labs. Este script lo recibe por ruta y no lo copia. Si no lo tienes,
el fixture congelado (casos.json) sigue siendo el contrato verificable; lo que
no puedes hacer es regenerarlo.

La promesa que este generador debe cumplir esta declarada y la comprueba
verificar_paridad.py: en las 108 compuertas, cerca_del_umbral == 0, es decir,
ningun nodo cae a menos de 1e-9 relativo de su umbral. Si eso deja de ser
cierto, los conteos que la pagina muestra dejan de ser estables entre
implementaciones y el fixture no vale como contrato.
"""
import argparse
import importlib.util
import json
import os
import sys

import numpy as np

PERFILES = [(8.0, 32), (8.0, 48), (8.0, 64), (8.0, 96), (16.0, 64)]
BASES = [(8.0, 32), (8.0, 64), (8.0, 96)]
DELTAS = [0.0, 0.25, 0.5, 1.0]
MARGENES = [1.0, 1.5, 2.0]
EPS = [1.0, 0.5, 0.1]


def carga_oraculo(ruta):
    spec = importlib.util.spec_from_file_location("piso_de_deteccion", ruta)
    if spec is None or spec.loader is None:
        raise SystemExit("RC 5 · el oraculo no se puede importar: " + ruta)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def genera(m):
    perfiles = []
    for L, N in PERFILES:
        perfiles.append({"L": L, "N": N, "esperado": m.medir(L=L, N=N)})

    compuertas = []
    for L, N in BASES:
        X, Y, h = m.rejilla(L, N)
        Bx, By = m.campo_monopolo(X, Y)
        tau_h, R_h = m.piso_medido(Bx, By, X, Y, h)
        mask = m.mascara_relevante(Bx, By)
        tau_max = float(np.max(tau_h))
        th = m.tau_estimado(Bx, By, h)

        for d in DELTAS:
            delta = d * tau_max
            Bxc, Byc = m.contaminacion_divergencia(Bx, By, X, Y, delta)
            _, R_c = m.piso_medido(Bxc, Byc, X, Y, h)
            th_c = m.tau_estimado(Bxc, Byc, h)
            ciego = abs(float(np.max(th_c[mask])) - float(np.max(th[mask]))) < 1e-9 * tau_max

            for mg in MARGENES:
                loc = m.veredicto_local(R_c, th_c, mg, mask, abstol=m.C4_ANALITICO * h ** 4)
                eps_abs = mg * th_c + m.C4_ANALITICO * h ** 4
                exceso = np.abs(R_c) - eps_abs
                cerca = int(np.count_nonzero(
                    (np.abs(exceso) <= 1e-9 * np.maximum(eps_abs, 1e-300)) & mask))
                for k in EPS:
                    eps = k * tau_max
                    const = m.veredicto_constante(R_c, eps, mask)
                    compuertas.append({
                        "L": L, "N": N, "delta_rel": d, "margen": mg, "eps_rel": k,
                        "esperado": {
                            "local_violaciones": loc["violaciones"],
                            "local_fraccion_violada": loc["fraccion_violada"],
                            "local_rechazado": loc["rechazado"],
                            "local_exceso_max": loc["exceso_max"],
                            "const_violaciones": const["violaciones"],
                            "const_rechazado": const["rechazado"],
                            "piso_ciego": bool(ciego),
                            "cerca_del_umbral": cerca,
                            "n_mascara": int(np.count_nonzero(mask)),
                            "tau_max": tau_max,
                        },
                    })

    return {
        "procedencia": {
            "fuente_publica": False,
            "oraculo": "tools/piso_de_deteccion.py",
            "verificable": "la pagina contra este fixture: verificar_paridad.py",
            "regenerar": "python3 generar_casos.py --oraculo <ruta al oraculo>",
            "nota": "generado con numpy 2.5.4 / CPython 3.12",
        },
        "perfiles": perfiles,
        "compuertas": compuertas,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oraculo", required=True)
    ap.add_argument("--salida", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "casos.json"))
    args = ap.parse_args()

    datos = genera(carga_oraculo(args.oraculo))
    cerca = sum(1 for c in datos["compuertas"] if c["esperado"]["cerca_del_umbral"] != 0)
    with open(args.salida, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("escrito %s · %d perfiles · %d compuertas · cerca_del_umbral != 0: %d"
          % (args.salida, len(datos["perfiles"]), len(datos["compuertas"]), cerca))
    return 0 if cerca == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
