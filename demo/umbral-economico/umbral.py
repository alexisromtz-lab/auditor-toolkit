#!/usr/bin/env python3
"""umbral — ¿el intento paga, y sobrevives para cobrarlo?

Un intento cuesta C y, si sale, paga V. Sale con probabilidad p.
La pregunta que todo el mundo hace es «¿pV > C?», y esa pregunta tiene una
respuesta que no depende de cuántos intentos te puedas permitir. Este
instrumento mide las dos cosas a la vez: si el intento paga, y si sobrevives
para cobrarlo.

El núcleo son tres cómputos independientes del mismo número:

1. Suma de términos positivos   E[K] = Σ_{k=1..m} k·p·u^{k-1} + m·u^m
2. Forma cerrada                E[K] = (1 − u^m)/p
3. Monte Carlo                  con un PRNG especificado, no heredado

La razón de tener tres y no uno: cuando no hay oráculo previo contra el que
portar, el falsificador no puede comparar un port con su original — tiene que
comparar dos caminos independientes que deberían llegar al mismo sitio.

Sin dependencias: sólo stdlib. Corre con el `python3` del sistema.
"""

from __future__ import annotations

import json
import math
import sys

SEMILLA_DEFECTO = 20261113
N_MONTECARLO_DEFECTO = 8000   # el contrato fija un solo n; la página y este archivo coinciden

# Barrido de la página. Se declara aquí porque la paridad se mide sobre él.
P_GRID = [0.005, 0.01, 0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.7, 0.9]
V_GRID = [3.0, 10.0, 25.0, 100.0, 400.0]
C_GRID = [0.25, 1.0, 5.0, 20.0]
M_GRID = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 200]


# ---------------------------------------------------------------- núcleo

def potencia(u, m):
    """u**m por elevación al cuadrado.

    Se escribe a mano y no se delega en `**` ni en `Math.pow` porque el
    contrato es que la página y este archivo den el mismo bit: la secuencia
    de multiplicaciones tiene que ser idéntica en los dos lenguajes.
    """
    r = 1.0
    b = u
    e = int(m)
    while e:
        if e & 1:
            r *= b
        b *= b
        e >>= 1
    return r


def supervivencia_tras_m(p, m):
    """P(ningún éxito en m intentos) — la ruina de quien va hasta quedarse seco."""
    return potencia(1.0 - p, m)


def exito_en_m(p, m):
    """P(al menos un éxito en m intentos)."""
    return 1.0 - supervivencia_tras_m(p, m)


def umbral(V, C):
    """p_min = C/V — la probabilidad que hace cero el valor esperado de UN intento."""
    return C / V


def ev_por_intento(p, V, C):
    return p * V - C


def esperanza_intentos_suma(p, m):
    """E[K] por suma directa. Todos los términos son positivos: no hay cancelación."""
    u = 1.0 - p
    t = 1.0
    s = 0.0
    for k in range(1, m + 1):
        s += k * p * t
        t *= u
    return s + m * t


def esperanza_intentos_cerrada(p, m):
    """E[K] = (1 − u^m)/p. Misma cantidad, otro camino."""
    return (1.0 - potencia(1.0 - p, m)) / p


def ev_politica(p, V, C, m):
    """Valor esperado de «intenta hasta acertar o hasta quedarte sin intentos»."""
    return exito_en_m(p, m) * V - C * esperanza_intentos_suma(p, m)


def ev_politica_cerrada(p, V, C, m):
    """q·(V − C/p). La identidad que enseña la página: m no aparece en el signo."""
    return exito_en_m(p, m) * (V - C / p)


def intentos_para(p, objetivo, tope=200000):
    """Menor m tal que la ruina baje de `objetivo`. Búsqueda entera, sin logaritmos.

    Se evita `log` a propósito: una cifra que la página enseña tiene que salir
    del mismo camino en los dos lenguajes, y `log` no es bit-paritario.
    """
    m = 1
    while m <= tope:
        if supervivencia_tras_m(p, m) <= objetivo:
            return m
        m += 1
    return -1


# ---------------------------------------------------------------- PRNG

class Lcg(object):
    """LCG de Numerical Recipes, 32 bits.

    Especificado, no heredado: `Math.imul`/`>>> 0` en JS y `& 0xFFFFFFFF` aquí
    producen la misma secuencia exacta. Por eso el Monte Carlo también puede
    ser paritario bit a bit, en vez de «estadísticamente parecido».
    """

    __slots__ = ("s",)

    def __init__(self, semilla):
        self.s = int(semilla) & 0xFFFFFFFF

    def siguiente(self):
        self.s = (1664525 * self.s + 1013904223) & 0xFFFFFFFF
        return self.s

    def uniforme(self):
        return self.siguiente() / 4294967296.0


def montecarlo(p, V, C, m, n=N_MONTECARLO_DEFECTO, semilla=SEMILLA_DEFECTO):
    """Riqueza final de n corredores que van hasta quedarse secos."""
    gen = Lcg(semilla)
    ruinas = 0
    suma = 0.0
    for _ in range(n):
        k = 0
        neto = -m * C
        while k < m:
            k += 1
            if gen.uniforme() < p:
                neto = V - k * C
                break
        if neto == -m * C:
            ruinas += 1
        suma += neto
    return {
        "n": n,
        "semilla": semilla,
        "ruinas": ruinas,
        "ruina_mc": ruinas / float(n),
        "media_mc": suma / float(n),
    }


# ---------------------------------------------------------------- estado

def medir(p, V, C, m, n=N_MONTECARLO_DEFECTO, semilla=SEMILLA_DEFECTO):
    """Todo lo que la página publica, en un solo sitio.

    Con `n <= 0` no hay Monte Carlo y la clave no se publica: cero intentos no
    es una medición de cero, es la ausencia de la medición.
    """
    u = 1.0 - p
    pmin = umbral(V, C)
    q = exito_en_m(p, m)
    ek_suma = esperanza_intentos_suma(p, m)
    ek_cerrada = esperanza_intentos_cerrada(p, m)
    ruin = supervivencia_tras_m(p, m)
    r = {
        "p": p,
        "V": V,
        "C": C,
        "m": m,
        "u_m": potencia(u, m),
        "p_min": pmin,
        "ratio": p / pmin if pmin else float("inf"),
        "ev_intento": ev_por_intento(p, V, C),
        "q_exito": q,
        "ruina": ruin,
        "ek": ek_suma,
        "ek_cerrada": ek_cerrada,
        "ev_politica": ev_politica(p, V, C, m),
        "ev_politica_cerrada": ev_politica_cerrada(p, V, C, m),
        "perdida_maxima": m * C,
        "m_ruina_50": intentos_para(p, 0.50),
        "m_ruina_10": intentos_para(p, 0.10),
    }
    if n > 0:
        r["montecarlo"] = montecarlo(p, V, C, m, n, semilla)
    return r


CLAVES_EXACTAS = (
    "u_m",
    "p_min",
    "ratio",
    "ev_intento",
    "q_exito",
    "ruina",
    "ek",
    "ek_cerrada",
    "ev_politica",
    "ev_politica_cerrada",
    "perdida_maxima",
    "m_ruina_50",
    "m_ruina_10",
)


# ---------------------------------------------------------------- compuertas

def _rel(a, b):
    """Error relativo, sólo para cantidades que no pueden ser cero."""
    if a == b:
        return 0.0
    d = max(abs(a), abs(b))
    return abs(a - b) / d if d else 0.0


def _err_esc(a, b, escala):
    """Error normalizado por la escala del problema, no por el resultado.

    Un error relativo puro miente en los ceros: cuando `p·V - C` es
    exactamente 0 (8 combinaciones del barrido), dividir por el resultado da
    `1.0` para cualquier ruido y parece una divergencia de magnitud completa.
    """
    d = max(abs(escala), abs(a), abs(b))
    return abs(a - b) / d if d else 0.0


def self_test(verbose=True):
    """G1..G10. Devuelve (rc, lista de fallos).

    Un fallo nombra la compuerta y los números: un «False» no es diagnóstico.
    """
    fallos = []

    def mal(g, msg):
        fallos.append("%s: %s" % (g, msg))

    # G1 — p_min es el cociente exacto de la aritmética, no una estimación.
    for V in V_GRID:
        for C in C_GRID:
            if umbral(V, C) != C / V:
                mal("G1", "umbral(%r,%r) != C/V" % (V, C))

    # G2 — potencia() y ** coinciden dentro de la cota que impone el algoritmo.
    #      Cada cuadrado duplica el error relativo, así que la elevación al
    #      cuadrado está acotada por 2^ceil(log2 m)·eps ≈ 4·m·eps, y se declara
    #      así; no se exige bit a bit porque `**` va a libm y aquí no.
    #      Medido 13-Nov-2026: peor caso 72 ULP (1.04e-14) en p=0.2 m=200.
    eps = 2.220446049250313e-16
    peor = (0.0, None)
    for p in P_GRID:
        for m in M_GRID:
            a = potencia(1.0 - p, m)
            b = (1.0 - p) ** m
            r = _rel(a, b)
            if r > peor[0]:
                peor = (r, (p, m))
    if peor[0] > 4 * max(M_GRID) * eps:
        mal("G2", "potencia vs ** %.3e (>4m·eps=%.3e) en %r"
            % (peor[0], 4 * max(M_GRID) * eps, peor[1]))

    # G3 — las dos rutas de E[K] coinciden.
    peor = 0.0
    for p in P_GRID:
        for m in M_GRID:
            a = esperanza_intentos_suma(p, m)
            b = esperanza_intentos_cerrada(p, m)
            peor = max(peor, _err_esc(a, b, m))
    if peor > 1e-12:
        mal("G3", "E[K] suma vs cerrada %.3e (>1e-12)" % peor)

    # G4 — las dos rutas del valor esperado de la política coinciden.
    peor = 0.0
    for p in P_GRID:
        for V in V_GRID:
            for C in C_GRID:
                for m in M_GRID:
                    a = ev_politica(p, V, C, m)
                    b = ev_politica_cerrada(p, V, C, m)
                    peor = max(peor, _err_esc(a, b, max(V, C)))
    if peor > 1e-12:
        mal("G4", "EV política suma vs cerrada %.3e (>1e-12)" % peor)

    # G5 — el signo del valor esperado NO depende de m. Es la tesis.
    #      Las combinaciones que caen SOBRE el umbral se declaran y se excluyen:
    #      un signo cerca de cero en IEEE es ruido, no una refutación.
    BANDA = 1e-12
    n_distintos = 0
    en_banda = 0
    medidas = 0
    for p in P_GRID:
        for V in V_GRID:
            for C in C_GRID:
                base = p * V - C
                escala = max(V, C)
                if abs(base) <= BANDA * escala:
                    en_banda += 1
                    continue
                esperado = 1 if base > 0 else -1
                for m in M_GRID:
                    ev = ev_politica(p, V, C, m)
                    if abs(ev) <= BANDA * escala:
                        continue
                    medidas += 1
                    if (1 if ev > 0 else -1) != esperado:
                        n_distintos += 1
    if n_distintos:
        mal("G5", "%d combinaciones cambian el signo de EV con m" % n_distintos)
    if medidas < 3000:
        mal("G5", "sólo %d medidas; la compuerta no midió" % medidas)

    # G6 — con m = 1 la política ES el intento único, en ℝ. En IEEE se separa
    #      en el último bit porque 1−(1−p) no es p: se declara la cota.
    peor = 0.0
    for p in P_GRID:
        for V in V_GRID:
            for C in C_GRID:
                peor = max(peor, _err_esc(ev_politica(p, V, C, 1),
                                          ev_por_intento(p, V, C), max(V, C)))
    if peor > 1e-14:
        mal("G6", "m=1 se separa del intento único %.3e (>1e-14)" % peor)

    # G7 — Monte Carlo contra teoría, cota de 4 sigma declarada.
    casos = 0
    for p in (0.05, 0.1, 0.2, 0.35):
        for m in (1, 3, 10, 50):
            exacto = supervivencia_tras_m(p, m)
            if not (0.02 <= exacto <= 0.98):
                continue
            casos += 1
            mc = montecarlo(p, 10.0, 1.0, m, 40000, SEMILLA_DEFECTO)
            sigma = math.sqrt(exacto * (1.0 - exacto) / mc["n"])
            if abs(mc["ruina_mc"] - exacto) > 4 * sigma:
                mal("G7", "ruina MC %.5f vs %.5f (>4σ=%.5f, p=%r m=%r)"
                    % (mc["ruina_mc"], exacto, 4 * sigma, p, m))
    if casos < 8:
        mal("G7", "sólo %d casos en banda; la compuerta no midió" % casos)

    # G8 — la media del Monte Carlo cae dentro de 4 sigma de la varianza medida.
    for p in (0.1, 0.25):
        for m in (5, 20):
            mc = montecarlo(p, 25.0, 2.0, m, 40000, SEMILLA_DEFECTO)
            ev = ev_politica(p, 25.0, 2.0, m)
            # varianza por simulación, medida sobre la misma corrida
            gen = Lcg(SEMILLA_DEFECTO)
            s2 = 0.0
            for _ in range(mc["n"]):
                k = 0
                neto = -m * 2.0
                while k < m:
                    k += 1
                    if gen.uniforme() < p:
                        neto = 25.0 - k * 2.0
                        break
                s2 += (neto - mc["media_mc"]) ** 2
            sigma = math.sqrt(s2 / mc["n"] / mc["n"])
            if abs(mc["media_mc"] - ev) > 4 * sigma:
                mal("G8", "media MC %.5f vs EV %.5f (>4σ=%.5f, p=%r m=%r)"
                    % (mc["media_mc"], ev, 4 * sigma, p, m))

    # G9 — el Monte Carlo es reproducible: misma semilla, mismo bit.
    a = montecarlo(0.13, 7.0, 1.0, 9, 5000, 99)
    b = montecarlo(0.13, 7.0, 1.0, 9, 5000, 99)
    c = montecarlo(0.13, 7.0, 1.0, 9, 5000, 100)
    if a != b:
        mal("G9", "misma semilla, distinto resultado")
    if a == c:
        mal("G9", "semilla distinta, mismo resultado: el PRNG no se está usando")

    # G10 — monotonía: la ruina baja con m y sube con p.
    for p in (0.05, 0.2, 0.4):
        previo = 2.0
        for m in M_GRID:
            r = supervivencia_tras_m(p, m)
            if r > previo + 1e-15:
                mal("G10", "ruina sube con m (p=%r m=%r)" % (p, m))
            previo = r
    for m in (5, 50):
        previo = 2.0
        for p in P_GRID:
            r = supervivencia_tras_m(p, m)
            if r > previo + 1e-15:
                mal("G10", "ruina sube con p (p=%r m=%r)" % (p, m))
            previo = r

    if verbose:
        if fallos:
            for f in fallos:
                print("FALLO " + f)
        print("G5: %d medidas, %d en banda ±%.0e (excluidas), %d discrepancias"
              % (medidas, en_banda, BANDA, n_distintos))
        print("G1..G10 %s (%d fallos)" % ("OK" if not fallos else "ROJO", len(fallos)))
    return (0 if not fallos else 1), fallos


# ---------------------------------------------------------------- CLI

def main(argv):
    if "--self-test" in argv:
        rc, _ = self_test()
        return rc
    p = 0.1
    V = 100.0
    C = 5.0
    m = 20
    for a in argv:
        if "=" in a and a.split("=")[0] in ("p", "V", "C", "m"):
            k, v = a.split("=", 1)
            if k == "p":
                p = float(v)
            elif k == "V":
                V = float(v)
            elif k == "C":
                C = float(v)
            else:
                m = int(v)
    if not (0.0 < p < 1.0) or V <= 0 or C <= 0 or m < 1:
        print("parámetros fuera de rango: p∈(0,1), V>0, C>0, m>=1", file=sys.stderr)
        return 20
    r = medir(p, V, C, m)
    if "--json" in argv:
        print(json.dumps(r, indent=2, sort_keys=True))
        return 0
    print("p_min            %.6f   (C/V)" % r["p_min"])
    print("p/p_min          %.4f" % r["ratio"])
    print("EV un intento    %+.6f" % r["ev_intento"])
    print("P(ruina)         %.6f" % r["ruina"])
    print("E[intentos]      %.6f" % r["ek"])
    print("EV política      %+.6f" % r["ev_politica"])
    print("pérdida máxima   %.2f" % r["perdida_maxima"])
    print("MC ruina         %.6f  (n=%d)" % (r["montecarlo"]["ruina_mc"], r["montecarlo"]["n"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
