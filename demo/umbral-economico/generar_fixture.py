#!/usr/bin/env python3
"""Congela la llave de respuestas de «umbral» desde el oráculo.

El fixture es el contrato: la página no promete «da lo mismo», promete coincidir
con este archivo, que a su vez lo produce `umbral.py`. Las dos mitades son
públicas — es la primera pieza del escaparate que puede decir eso, porque no
había un motor interno que portar: el motor se escribió dos veces desde cero.

    python3 generar_fixture.py            # reescribe fixture.json
    python3 generar_fixture.py --check    # RC 0 si el fixture congelado sigue siendo el que el oráculo produce

Regenerarlo a mano después de tocar el oráculo es el único modo de que un cambio
de motor no se cuele: `verificar_paridad.py` compara el archivo con lo que el
oráculo produce ahora, y falla en RC 5 si divergen.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import umbral  # noqa: E402  (después de ajustar sys.path)

RUTA_FIXTURE = os.path.join(AQUI, "fixture.json")

# El barrido se declara aquí y el fixture lo publica: una malla que sólo vive en
# el generador no la puede auditar quien lee el contrato.
P_BARRIDO = [0.005, 0.06, 0.105, 0.35, 0.7, 0.9]
V_BARRIDO = [3.0, 10.0, 100.0, 400.0, 1000.0]
C_BARRIDO = [0.25, 1.0, 10.0, 100.0]
M_BARRIDO = [1, 200]

# Los cuatro presets de la página, con simulación: son los estados que un
# visitante ve al pulsar un botón, y llevan Monte Carlo porque ahí importa que
# la simulación también coincida, no sólo la cuenta cerrada.
PRESETS = [
    ("al-filo", 0.105, 100.0, 10.0, 5),
    ("solido", 0.35, 100.0, 10.0, 8),
    ("bajo-umbral", 0.06, 100.0, 10.0, 100),
    ("una-bala", 0.5, 1000.0, 100.0, 1),
]

# Estados sentados EXACTAMENTE sobre la frontera p·V = C. Son el caso que rompe
# cualquier métrica de error relativa: aquí un cociente de diferencias divide por
# cero, y la paridad sólo tiene sentido midiendo el error contra la escala del
# problema. Se incluyen a propósito para que la página no pueda olvidarlos.
FRONTERA = [
    (0.01, 25.0, 0.25, 5),
    (0.1, 10.0, 1.0, 5),
    (0.2, 5.0, 1.0, 8),
    (0.5, 200.0, 100.0, 2),
    (0.9, 10.0, 9.0, 1),
    (0.25, 400.0, 100.0, 12),
]

BANDA = 1e-12


def _sha256(ruta: str) -> str:
    h = hashlib.sha256()
    with io.open(ruta, "rb") as f:
        for trozo in iter(lambda: f.read(1 << 16), b""):
            h.update(trozo)
    return h.hexdigest()


def _estado(p: float, V: float, C: float, m: int, n: int = 0) -> dict:
    r = umbral.medir(p, V, C, m, n=n)
    return {
        "p": p, "V": V, "C": C, "m": m,
        "esperado": {k: v for k, v in sorted(r.items()) if k != "montecarlo"},
        "en_banda": bool(abs(r["ev_intento"]) <= BANDA * max(V, C)),
        "montecarlo": r.get("montecarlo"),
    }


def construir() -> dict:
    estados = []
    for p in P_BARRIDO:
        for V in V_BARRIDO:
            for C in C_BARRIDO:
                for m in M_BARRIDO:
                    estados.append(_estado(p, V, C, m))

    presets = []
    for nombre, p, V, C, m in PRESETS:
        e = _estado(p, V, C, m, n=umbral.N_MONTECARLO_DEFECTO)
        e["nombre"] = nombre
        presets.append(e)

    frontera = [_estado(p, V, C, m) for p, V, C, m in FRONTERA]

    todos = estados + presets + frontera
    en_banda = sum(1 for e in todos if e["en_banda"])
    return {
        "procedencia": {
            "fuente_publica": True,
            "oraculo": "umbral.py",
            "sha256_oraculo": _sha256(os.path.join(AQUI, "umbral.py")),
            "motor": "motor.js",
            "sha256_motor": _sha256(os.path.join(AQUI, "motor.js")),
            "comando": "python3 generar_fixture.py",
            "python": ".".join(str(x) for x in sys.version_info[:3]),
            "n_montecarlo": umbral.N_MONTECARLO_DEFECTO,
            "semilla": umbral.SEMILLA_DEFECTO,
        },
        "promesas": {
            "estados": len(todos),
            "del_barrido": len(estados),
            "presets": len(presets),
            "frontera": len(frontera),
            "claves_exactas": list(umbral.CLAVES_EXACTAS),
            "tolerancia": 0.0,
            "cerca_del_umbral": en_banda,
            "banda": BANDA,
        },
        "barrido": {"p": P_BARRIDO, "V": V_BARRIDO, "C": C_BARRIDO, "m": M_BARRIDO},
        "estados": estados,
        "presets": presets,
        "frontera": frontera,
    }


def serializa(datos: dict) -> str:
    return json.dumps(datos, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


def _motivos(actual: dict, datos: dict) -> list:
    """Nombra qué se movió. Un RC que no dice qué cambió obliga a adivinar."""
    motivos = []
    a, b = actual.get("procedencia", {}), datos["procedencia"]
    if a.get("sha256_oraculo") != b["sha256_oraculo"]:
        motivos.append("cambió el oráculo (umbral.py): %s… → %s…"
                       % (str(a.get("sha256_oraculo"))[:8], b["sha256_oraculo"][:8]))
    if a.get("sha256_motor") != b["sha256_motor"]:
        motivos.append("cambió el motor (motor.js): el fixture se congeló contra otra build")
    if a.get("semilla") != b["semilla"] or a.get("n_montecarlo") != b["n_montecarlo"]:
        motivos.append("cambió el contrato del Monte Carlo (semilla o n)")
    if actual.get("promesas") != datos["promesas"]:
        motivos.append("cambiaron las promesas declaradas")
    for bloque in ("estados", "presets", "frontera"):
        if actual.get(bloque) != datos[bloque]:
            motivos.append("cambiaron los valores de %s" % bloque)
    return motivos


def main(argv) -> int:
    datos = construir()
    texto = serializa(datos)
    if "--check" in argv:
        if not os.path.exists(RUTA_FIXTURE):
            print("RC 5 · no hay fixture congelado: corre sin --check para crearlo", file=sys.stderr)
            return 5
        actual = io.open(RUTA_FIXTURE, encoding="utf-8").read()
        if actual != texto:
            try:
                motivos = _motivos(json.loads(actual), datos)
            except ValueError:
                motivos = ["el fixture congelado no es JSON válido"]
            print("RC 5 · el fixture congelado ya no es lo que el oráculo produce", file=sys.stderr)
            for m in motivos or ["divergencia no clasificada"]:
                print("       · " + m, file=sys.stderr)
            print("       regenera con: python3 generar_fixture.py", file=sys.stderr)
            return 5
        print("RC 0 · fixture congelado == oráculo (%d bytes)" % len(texto.encode("utf-8")))
        return 0
    io.open(RUTA_FIXTURE, "w", encoding="utf-8").write(texto)
    print("fixture.json · %d bytes · %d estados · %d en banda" % (
        len(texto.encode("utf-8")), datos["promesas"]["estados"],
        datos["promesas"]["cerca_del_umbral"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
