#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gate_pre_escritura.py — port a Python del arnes de PRE-VUELO (A2.1).

HUELLA-PRE-WRITE-GATE-PY-20261015

PROPOSITO
  Verificador DETERMINISTA de la tupla de autorizacion de escritura, sin bash.
  Antes de mutar un archivo, la orden viaja con su contrato de destino:
  TARGET (absoluto) · BLOB_PRE (git hash-object) · HUELLA (fragmento literal
  exclusivo del texto a insertar) · LINEAS_PRE (conteo de lineas previo).
  Si cualquiera de las cuatro condiciones falla, NO se escribe: el gate
  bloquea y nombra la causa.

UNIVERSO DECLARADO: el archivo TARGET declarado en la tupla (no un directorio,
  no un arbol, no un lote). En modo --plan el universo es una tupla por linea.
MOTOR: python3 stdlib + git (subprocess). Sin dependencias externas.
REGLA DE VEREDICTO: RC 0 (PRE-VUELO OK) | RC 10/11/17 (NO BLOQUEANTE) | resto (FALLO CERRADO)

INVARIANTE CENTRAL:
  Autorizar(TARGET) <=>
      huella(orden) no habita TARGET
      Y blob(disco) == blob(contrato)
      Y lineas(disco) == lineas(contrato)
      Y estado(TARGET, git) == limpio (SOLO tracked-dirty: un objeto NUEVO
        sin historia en el indice no es "sucio", es RC 17)
  El gate certifica la AUSENCIA de la huella y la IGUALDAD de blob y lineas.
  No certifica intencion.

TABLA DE CAUSAS (RC)
   0  PRE_VUELO_OK          listo para recibir edicion
  10  OBJETO_INEXISTENTE    TARGET no existe (en A2.1: autoriza CREACION)
  11  HUELLA_YA_HABITA      la huella ya esta en el destino: COLISION, la fila
                            ya esta escrita. Cumplimiento pasivo: cero escrituras
  12  DESFASE_DE_OBJETO     blob(disco) != blob(contrato): arbol en movimiento
  13  ESTADO_SUCIO          TARGET TRACKED con modificaciones no adjudicadas.
                            SOLO tracked-dirty (divergencia declarada, ver abajo)
  14  SIN_REPO              TARGET no vive en un arbol git (fail-closed)
  15  LINEAS_DISTINTAS      lineas(disco) != lineas(contrato)
  17  OBJETO_NUEVO          TARGET existe en disco SIN historia en el indice
                            (untracked). NO bloquea: crear es el caso primario
  20  CONTRATO_INCOMPLETO   tupla incompleta, TARGET no absoluto, LINEAS_PRE
                            no entero
  30  MOTOR_INCOMPLETO      git ausente: el gate no puede medir (fail-closed)
  31  UNIVERSO_VACIO        0 tuplas en el plan: nada que medir (fail-closed)

DEFECTOS DECLARADOS DEL REFERENTE BASH (tools/gate_pre_escritura.sh, 80 l)
  - Declara RC 15 en su cabecera y NO lo implementa: el cuerpo termina en el
    paso 4 (exit 13) y no imprime linea de exito. Este port SI implementa
    RC 15 y la linea `PRE-VUELO OK`.
  - RC 128 con TARGET relativo: git re-basa con `-C dirname(TARGET)` y resuelve
    la ruta dos veces (fatal: could not open). Sale por 128, fuera de contrato.
    Este port no puede llegar a 128: la ruta relativa se rechaza en RC 20.
  - El propio gate vive sin versionar en git (estado `??`): el instrumento que
    guarda todas las escrituras no esta custodiado por el arbol que mide.
  - COLAPSO DE DOS ESTADOS (D2, medido 15-Oct-2026): `git status --porcelain`
    SIN `--untracked-files=no` NO distingue (a) tracked-dirty de (b) objeto
    nuevo sin historia en el indice: el referente responde RC 13 a los dos.
    CONTROL MEDIDO: el MISMO comando con `--untracked-files=no` da VACIO para
    el untracked => git SI los distingue y el referente los colapsaba.
    Efecto medido: el referente da RC 13 a la operacion PRIMARIA de A2.1
    (agente escribe archivo NUEVO) y a la edicion de sus propias piezas sin
    versionar. Este port SEPARA: RC 13 = tracked-dirty (bloqueante); untracked
    con tupla valida = RC 17 (NO bloqueante, se sigue midiendo).

RESIDUO DECLARADO (PLANO CIEGO FUERA DEL GATE)
  - No mide INTENCION: mide forma (huella, blob, lineas, estado), no el
    proposito del que escribe.
  - No cubre al que no corre el gate: el acto que no lo invoca no queda medido.
  - RC 13 mira SOLO el estado de TARGET y SOLO su cara TRACKED-DIRTY: no mira
    el untracked (que sale RC 17) ni el resto del arbol.
  - RC 17 declara una AUSENCIA DE HISTORIA, no un desfase: no dice que el
    objeto sea correcto, dice que el indice no lo tenia.
  - No cubre la red ni el escritor remoto: mide el disco local en ese instante.
  - No cubre el intervalo entre la corrida y la escritura: si otra mano escribe
    despues del RC 0, el gate ya no esta mirando (el par (objeto, instante)
    cambia de clase).

DIVERGENCIA DECLARADA
  `wc -l` del referente bash cuenta BYTES 0x0A, no lineas logicas: un archivo
  sin salto final tiene n-1. Este port reproduce esa aritmetica EXACTA
  (data.count(b"\\n")) y declara la unidad: LINEAS = saltos de linea.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

VERSION = "pre-write-gate-py-20261015"

MOTOR = "python3 stdlib + git (subprocess); sin dependencias externas"
UNIVERSO = "el archivo TARGET de la tupla (no un directorio, no un arbol)"
INVARIANTE = (
    "Autorizar(TARGET) <=> huella(orden) no habita TARGET "
    "y blob(disco) == blob(contrato) "
    "y lineas(disco) == lineas(contrato) "
    "y estado(TARGET, git) == limpio"
)
REGLA = "RC 0 (PRE-VUELO OK) | RC 10/11/17 (NO BLOQUEANTE) | resto (FALLO CERRADO)"

RESIDUO = (
    "No mide INTENCION: mide forma, no el proposito del que escribe.",
    "No cubre al que no corre el gate: el acto que no lo invoca no queda medido.",
    "RC 13 mira SOLO el estado TRACKED-DIRTY de TARGET, no el untracked (RC 17) ni el resto del arbol.",
    "RC 17 declara AUSENCIA DE HISTORIA en el indice, no un desfase de objeto.",
    "No cubre la red ni el escritor remoto: mide el disco local en ese instante.",
    "No cubre el intervalo corrida->escritura: el par (objeto, instante) cambia.",
    "RC 16 mide la RESTA del manifiesto contra origin/main: sin base o sin git responde RC 30, no 0.",
)

CAUSAS = {
    0: ("PRE_VUELO_OK", "PRE-VUELO OK"),
    10: ("OBJETO_INEXISTENTE", "COLISION: TARGET no existe."),
    11: ("HUELLA_YA_HABITA", "COLISION DETECTADA: la huella ya habita el destino."),
    12: ("DESFASE_DE_OBJETO", "DESFASE DE OBJETO: blob(disco) != blob(contrato)."),
    13: ("ESTADO_SUCIO", "ESTADO SUCIO: TARGET tracked con modificaciones no adjudicadas."),
    14: ("SIN_REPO", "SIN REPO: TARGET no vive en un arbol git. Fail-closed."),
    15: ("LINEAS_DISTINTAS", "LINEAS DISTINTAS: medido != contrato."),
    16: ("RESTA_NO_DECLARADA", "RESTA NO DECLARADA: fila borrada del manifiesto sin retiro registrado. Fail-closed."),
    17: ("OBJETO_NUEVO", "OBJETO NUEVO: existe en disco sin historia en el indice. NO bloquea."),
    18: ("RETIRO_HUERFANO", "RETIRO HUERFANO: el retiro declarado no tiene objeto: el TARGET sigue vivo en disco o declarado. Fail-closed."),
    20: ("CONTRATO_INCOMPLETO", "CONTRATO INCOMPLETO: tupla ausente o no absoluta."),
    30: ("MOTOR_INCOMPLETO", "MOTOR INCOMPLETO: git ausente. Fail-closed."),
    31: ("UNIVERSO_VACIO", "UNIVERSO VACIO: 0 tuplas. Nada que medir. Fail-closed."),
}

# Causas que NO bloquean una escritura en cadena (creacion / ya escrito /
# objeto nuevo sin historia en el indice).
NO_BLOQUEANTES = (0, 10, 11, 17)
# Causas que bloquean una escritura en cadena.
BLOQUEANTES = (12, 13, 14, 15, 16, 18, 20, 30, 31)


# --------------------------------------------------------------------------
# motor
# --------------------------------------------------------------------------
def _git(args, cwd):
    """Corre git sin locks opcionales. Devuelve (rc, stdout, stderr)."""
    try:
        p = subprocess.run(
            ["git", "-C", cwd, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except FileNotFoundError:
        return 127, "", "git ausente"
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def _lineas(ruta):
    """Unidad declarada: SALTOS DE LINEA (identico a `wc -l`)."""
    with open(ruta, "rb") as fh:
        return fh.read().count(b"\n")


def _resolver_rc(res):
    """Rellena nombre y mensaje tipados a partir de res['rc']."""
    nombre, base = CAUSAS.get(res["rc"], ("CAUSA_DESCONOCIDA", "causa no tipada"))
    res["causa"] = nombre
    res["mensaje_base"] = base
    return res


def evaluar(target, blob_pre, huella, lineas_pre=None, _raiz_git=None):
    """Evalua la tupla. NO escribe nada. Devuelve dict con rc, causa y medidas.

    Orden de las guardas (identico al referente bash, salvo la divergencia D2):
      RC 20 tupla/ruta -> RC 10 existencia -> RC 11 huella ->
      RC 14 arbol git -> RC 12 blob -> RC 13 tracked-dirty -> RC 15 lineas ->
      RC 17 objeto nuevo -> RC 0
    RC 17 va DESPUES de RC 15 a proposito: un bloqueante (15) no se enmascara
    por un declarativo (17).
    """
    res = {
        "target": target,
        "blob_pre": blob_pre,
        "huella": huella,
        "lineas_pre": lineas_pre,
        "blob_medido": None,
        "lineas_medidas": None,
        "lineas_evaluadas": False,
        "objeto_nuevo": False,
        "detalle": "",
        "no_medido": [],
        "rc": 0,
    }

    # --- guarda 1: contrato (tupla completa + ruta absoluta) ---------------
    if not target or not blob_pre or not huella:
        res["rc"] = 20
        res["detalle"] = (
            "Orden sin tupla de destino (TARGET, BLOB_PRE, HUELLA): "
            "rechazo por defecto de contrato. Cero escrituras."
        )
        return _resolver_rc(res)
    if not target.startswith(os.sep):
        res["rc"] = 20
        res["detalle"] = (
            "TARGET debe ser absoluto. El gate re-basa la ruta: "
            "relativa = base doble. Cero escrituras."
        )
        return _resolver_rc(res)
    if lineas_pre is not None and not str(lineas_pre).strip():
        # HUELLA-B20-PARIDAD-LINEAS-20261020
        # El gemelo bash recibe el 4o parametro con `${4:-}`: para el, "ausente" y
        # "vacio" son el MISMO caso. Este motor los separaba: "" -> int("") ->
        # RC 20, mientras bash saltaba la guarda de lineas -> RC 0. Mismo input,
        # dos RC. Se converge al gemelo, que es el unico que NO puede representar
        # la distincion. `-` sigue siendo el marcador explicito de "no declarado".
        lineas_pre = None
    if lineas_pre is not None:
        try:
            lineas_pre = int(str(lineas_pre).strip())
        except (TypeError, ValueError):
            res["rc"] = 20
            res["detalle"] = "LINEAS_PRE debe ser entero (o `-` si no se declara). Cero escrituras."
            return _resolver_rc(res)
        res["lineas_pre"] = lineas_pre

    # --- guarda 2: el objeto existe (RC 10) --------------------------------
    if not os.path.isfile(target):
        # HUELLA-GATE-FAIL-CLOSED-TREE-PY-20261020
        # RC 10 es NO_BLOQUEANTE: AUTORIZA una escritura. Salia ANTES de la
        # guarda 4 (arbol git), asi que firmaba creacion sobre un arbol
        # INEXISTENTE. Medido antes del fix: TARGET=/Users/marlene/
        # directorio_inexistente/test.py -> RC 10 (fail-open). El banco no lo
        # veia porque B5_SINREPO materializa el archivo (existe -> guarda 4).
        # Se sube al ancestro EXISTENTE mas cercano y se exige arbol git; si no
        # lo es -> RC 14. Subdirectorio nuevo DENTRO del repo sigue -> RC 10.
        ancestro = os.path.dirname(os.path.abspath(target))
        while not os.path.isdir(ancestro) and os.path.dirname(ancestro) != ancestro:
            ancestro = os.path.dirname(ancestro)
        rc_arbol, out_arbol, _err_arbol = _git(
            ["rev-parse", "--is-inside-work-tree"], ancestro
        )
        if rc_arbol != 0 or out_arbol.strip() != "true":
            res["rc"] = 30 if rc_arbol == 127 else 14
            res["detalle"] = (
                "TARGET no cae dentro de un arbol git (ancestro existente mas "
                "cercano: %s). No se puede firmar la creacion. Fail-closed." % ancestro
            )
            return _resolver_rc(res)
        res["rc"] = 10
        res["detalle"] = "TARGET no existe (regla A2.1: RC 10 autoriza CREACION)."
        return _resolver_rc(res)

    # --- guarda 3: la huella ya habita el destino (RC 11) ------------------
    with open(target, "rb") as fh:
        datos = fh.read()
    if huella.encode("utf-8") in datos:
        res["rc"] = 11
        res["detalle"] = (
            "la huella ya habita %s. COLISION: la fila ya esta escrita. "
            "Cumplimiento pasivo: cero escrituras." % target
        )
        return _resolver_rc(res)

    # --- guarda 4: el destino vive en un arbol git (RC 14) -----------------
    cwd = _raiz_git or os.path.dirname(os.path.abspath(target))
    rc, out, err = _git(["rev-parse", "--is-inside-work-tree"], cwd)
    if rc != 0 or out.strip() != "true":
        res["rc"] = 30 if rc == 127 else 14
        res["detalle"] = "TARGET no vive en un arbol git: el gate no puede validar identidad."
        return _resolver_rc(res)

    # --- guarda 5: blob declarado == blob en disco (RC 12) -----------------
    rc, out, err = _git(["hash-object", "--", target], cwd)
    res["blob_medido"] = out.strip() or None
    if rc != 0 or res["blob_medido"] != blob_pre:
        res["rc"] = 12
        res["detalle"] = "esperado %s, medido %s. Arbol en movimiento." % (
            blob_pre,
            res["blob_medido"],
        )
        return _resolver_rc(res)

    # --- guarda 6: estado limpio en git (RC 13 = SOLO tracked-dirty) --------
    # DIVERGENCIA DECLARADA (D2, 15-Oct-2026): el referente bash usa
    # `git status --porcelain` SIN `--untracked-files=no` y por eso colapsa dos
    # estados distintos en el mismo RC 13: (a) TARGET tracked con cambios no
    # adjudicados y (b) TARGET nuevo, sin historia en el indice. CONTROL:
    # `--untracked-files=no` da VACIO para el untracked => git SI distingue.
    # Aqui: (a) = RC 13 (bloquea); (b) = RC 17 (no bloquea, se sigue midiendo).
    rc, out, err = _git(["status", "--porcelain", "--untracked-files=no", "--", target], cwd)
    if rc != 0 or out.strip():
        res["rc"] = 13
        res["detalle"] = (
            "TARGET tracked con modificaciones no adjudicadas. "
            "(No incluye objetos sin historia en el indice: esos son RC 17.)"
        )
        return _resolver_rc(res)
    rc, out, err = _git(["status", "--porcelain", "--untracked-files=normal", "--", target], cwd)
    if rc == 0 and out.strip().startswith("??"):
        res["objeto_nuevo"] = True

    # --- guarda 7: lineas declaradas == lineas en disco (RC 15) ------------
    if lineas_pre is None:
        res["no_medido"].append("lineas_pre no declarado: RC 15 NO evaluado")
    else:
        res["lineas_medidas"] = _lineas(target)
        res["lineas_evaluadas"] = True
        if res["lineas_medidas"] != lineas_pre:
            res["rc"] = 15
            res["detalle"] = "esperado %d, medido %d (unidad: saltos de linea)." % (
                lineas_pre,
                res["lineas_medidas"],
            )
            return _resolver_rc(res)

    # --- RC 17: objeto nuevo sin historia en el indice (NO bloquea) --------
    if res["objeto_nuevo"]:
        res["rc"] = 17
        res["detalle"] = (
            "TARGET existe en disco con su blob y sus lineas conformes, pero el "
            "indice git NO lo tiene: el port DIVERGE del referente bash, que lo "
            "leia como RC 13. Declara AUSENCIA DE HISTORIA, no desfase. "
            "NO bloquea: crear es la operacion primaria de A2.1."
        )
        return _resolver_rc(res)

    # --- RC 0: aprobado ----------------------------------------------------
    res["rc"] = 0
    if res["no_medido"]:
        res["detalle"] = "lineas NO declaradas: verde PARCIAL, no verde pleno."
    else:
        res["detalle"] = "listo para recibir edicion."
    return _resolver_rc(res)


# --------------------------------------------------------------------------
# impresion
# --------------------------------------------------------------------------
def imprimir_cabecera():
    print("UNIVERSO DECLARADO: %s" % UNIVERSO)
    print("MOTOR: %s" % MOTOR)
    print("REGLA DE VEREDICTO: %s" % REGLA)
    print("INVARIANTE: %s" % INVARIANTE)
    print("RESIDUO DECLARADO (PLANO CIEGO FUERA DEL GATE):")
    for r in RESIDUO:
        print("  - %s" % r)


def _fmt_causas(rc):
    return "{rc:%s|%s}" % (rc, CAUSAS.get(rc, ("CAUSA_DESCONOCIDA",))[0])


def _palabra_veredicto(rc):
    """Palabra atada a NO_BLOQUEANTES: un RC que no bloquea no se imprime FALLO CERRADO."""
    if rc == 0:
        return "PRE-VUELO OK"
    if rc in NO_BLOQUEANTES:
        return "NO BLOQUEANTE"
    return "FALLO CERRADO"


def imprimir(res, json_mode=False):
    if json_mode:
        print(json.dumps(res, ensure_ascii=False, sort_keys=True))
        return
    imprimir_cabecera()
    print("TARGET MEDIDO: %s" % res["target"])
    print("BLOB_PRE: %s" % res["blob_pre"])
    print("BLOB_MEDIDO: %s" % res["blob_medido"])
    print("HUELLA: %s" % res["huella"])
    print("LINEAS_PRE: %s" % res["lineas_pre"])
    print("LINEAS_MEDIDAS: %s" % res["lineas_medidas"])
    print("OBJETO_NUEVO (sin historia en el indice): %s" % res.get("objeto_nuevo", False))
    for nm in res["no_medido"]:
        print("NO MEDIDO: %s" % nm)
    print("CAUSAS PRESENTES: %s" % _fmt_causas(res["rc"]))
    print("DETALLE: %s" % res["detalle"])
    if res["rc"] == 0:
        sufijo = " (PARCIAL: %s)" % "; ".join(res["no_medido"]) if res["no_medido"] else ""
        print("VEREDICTO: %s%s" % (_palabra_veredicto(0), sufijo))
    else:
        print("VEREDICTO: %s RC=%d" % (_palabra_veredicto(res["rc"]), res["rc"]))


# --------------------------------------------------------------------------
# modo lote (--plan)
# --------------------------------------------------------------------------
# HUELLA-PATCH-RELATIVIZAR-TARGET-20261018
def _raiz_repo_plan(ruta):
    """Raiz del repo que contiene el plan. Fallback: dirname del plan."""
    base = os.path.dirname(os.path.abspath(ruta)) or os.sep
    rc, out, _err = _git(["rev-parse", "--show-toplevel"], base)
    if rc == 0 and out.strip():
        return out.strip()
    return base


def _resolver_target_plan(target, raiz):
    """Vuelve absoluto el TARGET de una tupla. Relativo = relativo a la raiz del repo.

    Medido 18-Oct-2026: el manifiesto guardaba rutas absolutas de un Mac; en el runner
    ninguna existe => RC 10 por fila => lote "OK" sin medir blob ni lineas (falso cero).
    Orden: (1) absoluto y existente, se devuelve tal cual; (2) absoluto que cae dentro de
    la raiz, se recorta el prefijo y se re-resuelve adentro; (3) relativo => raiz + ruta;
    (4) si nada existe se devuelve el original y el RC 10 lo informa (no se inventa ruta).
    """
    if os.path.isabs(target) and os.path.isfile(target):
        return target
    cands = []
    if os.path.isabs(target):
        pref = raiz.rstrip(os.sep) + os.sep
        if target.startswith(pref):
            cands.append(os.path.join(raiz, target[len(pref):]))
    else:
        cands.append(os.path.join(raiz, target))
        cands.append(os.path.join(raiz, os.path.normpath(target)))
    for c in cands:
        if os.path.isfile(c):
            return c
    return target


# HUELLA-PATCH-RESTA-DECLARADA-20261018
DECLARADAS_REL = "pre-write-gate/tuplas.declaradas.tsv"
RETIRADAS_REL = "pre-write-gate/tuplas.retiradas.tsv"


# HUELLA-FIX-PARSER-TSV-20261018
def _filas_retiradas(raiz):
    """TARGETs con retiro registrado. Sin archivo o fila de != 4 campos => None."""
    ruta = os.path.join(raiz, RETIRADAS_REL)
    if not os.path.isfile(ruta):
        return None
    filas = []
    with open(ruta, "r", encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.rstrip("\r\n")
            if not linea.strip() or linea.startswith("#"):
                continue
            campos = linea.split("\t")
            if len(campos) != 4 or any(not campo.strip() for campo in campos):
                return None
            filas.append(os.path.normpath(campos[0].strip()))
    return filas


# HUELLA-PATCH-RETIRO-HUERFANO-20261018
def _campos_manifiesto(linea):
    """Parte una fila declarada. TAB es el contrato; el fixture de banco usa espacios."""
    campos = [campo.strip() for campo in linea.split("\t")]
    if len(campos) != 4:
        campos = linea.split()
    return campos


def _filas_declaradas(raiz):
    """TARGETs con fila declarada vigente. Sin archivo o fila de != 4 campos => None."""
    ruta = os.path.join(raiz, DECLARADAS_REL)
    if not os.path.isfile(ruta):
        return None
    filas = []
    with open(ruta, "r", encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.rstrip("\r\n")
            if not linea.strip() or linea.startswith("#"):
                continue
            campos = _campos_manifiesto(linea)
            if len(campos) != 4 or any(not campo for campo in campos):
                return None
            filas.append(os.path.normpath(campos[0]))
    return filas


def _resta_vacia():
    """Forma canonica de la resta (UNICA fuente de claves y de tipos).

    HUELLA-FIX-JSON-SCHEMA-PLAN-20261018: el Esquema Congelado exige
    `huerfanos` y `sin_retiro` SIEMPRE list (vacio `[]`) y `n_sin_retiro`
    SIEMPRE int (vacio `0`). Una sola fabrica evita que las rutas diverjan.
    """
    return {
        "rc": 0,
        "borradas": [],
        "sin_retiro": [],
        "huerfanos": [],
        "n_sin_retiro": 0,
        "detalle": "",
    }


def auditar_resta(raiz):
    """RC 16 si una fila fue borrada sin retiro; RC 18 si el retiro no tiene objeto.

    RC 18 (RETIRO_HUERFANO): un TARGET con retiro declarado que sigue vivo en
    disco o sigue declarado en el manifiesto. El retiro se declara, el objeto no
    se retira => el retiro es huerfano y el falsador nace inerte.
    Fail-closed: sin git o sin base (origin/main) responde RC 30, nunca 0.
    """
    res = _resta_vacia()
    retiradas = _filas_retiradas(raiz)
    declaradas = _filas_declaradas(raiz)
    faltantes = [
        rel
        for rel, valor in ((RETIRADAS_REL, retiradas), (DECLARADAS_REL, declaradas))
        if valor is None
    ]
    if faltantes:
        res["rc"] = 30
        res["detalle"] = (
            "MOTOR INCOMPLETO: %s ausente o con fila de != 4 campos. Fail-closed."
            % " + ".join(faltantes)
        )
        return res
    rc, out, err = _git(
        ["diff", "--no-color", "--unified=0", "origin/main", "--", DECLARADAS_REL],
        raiz,
    )
    if rc != 0:
        res["rc"] = 30
        res["detalle"] = (
            "MOTOR INCOMPLETO: git diff origin/main fallo (rc=%d): %s. Fail-closed."
            % (rc, (err or "").strip()[:200])
        )
        return res
    for linea in out.split("\n"):
        if not linea.startswith("-") or linea.startswith("---"):
            continue
        cuerpo = linea[1:].strip()
        if not cuerpo or cuerpo.startswith("#"):
            continue
        target = cuerpo.split()[0]
        if target not in res["borradas"]:
            res["borradas"].append(target)
    for target in res["borradas"]:
        if os.path.normpath(target) not in retiradas:
            res["sin_retiro"].append(target)
    declaradas_set = set(declaradas)
    for target in retiradas:
        norm = os.path.normpath(target)
        vive_disco = os.path.isfile(os.path.join(raiz, norm))
        sigue_declarado = norm in declaradas_set
        if (vive_disco or sigue_declarado) and target not in res["huerfanos"]:
            res["huerfanos"].append(target)
    detalles = []
    if res["sin_retiro"]:
        res["rc"] = 16
        detalles.extend(
            "ERROR: %s fue borrado sin registrar su retiro." % t
            for t in res["sin_retiro"]
        )
    if res["huerfanos"]:
        if res["rc"] == 0:
            res["rc"] = 18
        detalles.extend(
            "ERROR: retiro huerfano de %s: sigue vivo en disco o declarado." % t
            for t in res["huerfanos"]
        )
    if detalles:
        res["detalle"] = " ".join(detalles)
    elif res["borradas"]:
        res["detalle"] = "resta declarada: %d borradas, todas con retiro." % len(
            res["borradas"]
        )
    # HUELLA-FIX-JSON-SCHEMA-PLAN-20261018: contador SIEMPRE int, derivado de la lista.
    res["n_sin_retiro"] = len(res["sin_retiro"])
    return res


def correr_plan(ruta, json_mode=False):
    """Lee una tupla por linea: TARGET BLOB_PRE HUELLA LINEAS_PRE (`-` = sin declarar)."""
    if not os.path.isfile(ruta):
        res = {
            "target": ruta,
            "rc": 31,
            # HUELLA-FIX-JSON-TOPLEVEL-20261018: nivel superior con las cinco claves
            # del pre-registro (plan/rc/tuplas/bloqueos/resta). `target` y `causa`
            # viajan como extras declarados; `bloqueos` vacio porque no hay tuplas.
            "plan": ruta,
            "causa": CAUSAS[31][0],
            "detalle": "plan inexistente: 0 tuplas. Nada que medir. Fail-closed.",
            "tuplas": [],
            "bloqueos": [],
            # HUELLA-FIX-JSON-SCHEMA-PLAN-20261018: misma forma que la ruta normal
            # (huerfanos/sin_retiro list, n_sin_retiro int) para que el consumidor
            # no caiga en KeyError. La resta NO se audito: se declara en detalle y
            # el rc superior (31) es el que decide.
            "resta": dict(_resta_vacia(), detalle="no medido: universo vacio (RC 31)."),
        }
        if json_mode:
            print(json.dumps(res, ensure_ascii=False, sort_keys=True))
        else:
            imprimir_cabecera()
            print("PLAN: %s" % ruta)
            print("TUPLAS MEDIDAS: 0")
            print("VEREDICTO LOTE: FALLO CERRADO RC=31")
        return 31

    raiz_repo = _raiz_repo_plan(ruta)
    resta = auditar_resta(raiz_repo)
    tuplas = []
    with open(ruta, "r", encoding="utf-8") as fh:
        for n, linea in enumerate(fh, 1):
            s = linea.strip()
            if not s or s.startswith("#"):
                continue
            campos = s.split()
            if len(campos) != 4:
                tuplas.append(
                    {
                        "linea": n,
                        "rc": 20,
                        "causa": CAUSAS[20][0],
                        "detalle": "tupla de %d campos (se exigen 4)." % len(campos),
                    }
                )
                continue
            target, blob_pre, huella, lp = campos
            lineas_pre = None if lp == "-" else lp
            target = _resolver_target_plan(target, raiz_repo)
            r = evaluar(target, blob_pre, huella, lineas_pre)
            r["linea"] = n
            tuplas.append(r)

    if not tuplas:
        res = {
            "target": ruta,
            "rc": 31,
            # HUELLA-FIX-JSON-TOPLEVEL-20261018: misma razon que en la ruta anterior.
            "plan": ruta,
            "causa": CAUSAS[31][0],
            "detalle": "0 tuplas utiles. Nada que medir. Fail-closed.",
            "tuplas": [],
            "bloqueos": [],
            # HUELLA-FIX-JSON-SCHEMA-PLAN-20261018: misma forma que la ruta normal
            # (huerfanos/sin_retiro list, n_sin_retiro int) para que el consumidor
            # no caiga en KeyError. La resta NO se audito: se declara en detalle y
            # el rc superior (31) es el que decide.
            "resta": dict(_resta_vacia(), detalle="no medido: universo vacio (RC 31)."),
        }
        if json_mode:
            print(json.dumps(res, ensure_ascii=False, sort_keys=True))
        else:
            imprimir_cabecera()
            print("PLAN: %s" % ruta)
            print("TUPLAS MEDIDAS: 0")
            print("VEREDICTO LOTE: FALLO CERRADO RC=31")
        return 31

    bloqueos = [t["rc"] for t in tuplas if t["rc"] in BLOQUEANTES]
    if resta["rc"] in BLOQUEANTES:
        bloqueos.append(resta["rc"])
    bloqueos.sort()
    rc = min(bloqueos) if bloqueos else 0

    if json_mode:
        print(
            json.dumps(
                {"plan": ruta, "rc": rc, "tuplas": tuplas, "bloqueos": bloqueos, "resta": resta},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return rc

    imprimir_cabecera()
    print("PLAN: %s" % ruta)
    print("TUPLAS MEDIDAS: %d" % len(tuplas))
    for t in tuplas:
        print(
            "  l.%s rc=%s %s %s | %s"
            % (
                t.get("linea", "-"),
                t["rc"],
                CAUSAS.get(t["rc"], ("CAUSA_DESCONOCIDA",))[0],
                t.get("target", ""),
                t.get("detalle", ""),
            )
        )
    print("RESTA: borradas=%d sin_retiro=%d" % (len(resta["borradas"]), len(resta["sin_retiro"])))
    print("RESTA HUERFANOS: %d" % len(resta.get("huerfanos", [])))
    if resta["detalle"]:
        print("RESTA DETALLE: %s" % resta["detalle"])
    print("BLOQUEOS: %s" % (bloqueos if bloqueos else "ninguno"))
    print("VEREDICTO LOTE: %s RC=%d" % ("OK" if rc == 0 else "FALLO CERRADO", rc))
    return rc


# --------------------------------------------------------------------------
# banco must-fail (cadenas en memoria; scratch en tmpdir FUERA del corpus)
# --------------------------------------------------------------------------
def _repo_scratch():
    """Crea un repo git desechable en tmpdir. Devuelve (dirs, dirp, target, blob, lineas)."""
    dirs = tempfile.TemporaryDirectory(prefix="pwg_banco_")
    dirp = dirs.name
    for cmd in (
        ["init", "-q"],
        ["config", "user.email", "gate@example.invalid"],
        ["config", "user.name", "gate"],
        ["config", "commit.gpgsign", "false"],
    ):
        _git(cmd, dirp)
    target = os.path.join(dirp, "destino.md")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("# destino\n\ncuerpo estable\n")
    _git(["add", "--", target], dirp)
    _git(["commit", "-q", "-m", "base"], dirp)
    rc, out, _ = _git(["hash-object", "--", target], dirp)
    return dirs, dirp, target, out.strip(), _lineas(target)


def _repo_scratch_retiros():
    """Crea un repo scratch con una fila retirada frente a origin/main."""
    dirs = tempfile.TemporaryDirectory(prefix="pwg_retiros_")
    raiz = dirs.name
    for cmd in (
        ["init", "-q"],
        ["config", "user.email", "gate@example.invalid"],
        ["config", "user.name", "gate"],
        ["config", "commit.gpgsign", "false"],
    ):
        _git(cmd, raiz)

    carpeta = os.path.join(raiz, "pre-write-gate")
    os.makedirs(carpeta)
    plan = os.path.join(carpeta, "tuplas.declaradas.tsv")
    with open(plan, "w", encoding="utf-8") as fh:
        fh.write("src/retirado.py blob-prueba HUELLA-RETIRO 4\n")
    with open(os.path.join(carpeta, "tuplas.retiradas.tsv"), "w", encoding="utf-8") as fh:
        fh.write("# target blob_pre motivo huella\n")

    _git(["add", "--", DECLARADAS_REL, RETIRADAS_REL], raiz)
    _git(["commit", "-q", "-m", "manifiesto base"], raiz)
    _git(["update-ref", "refs/remotes/origin/main", "HEAD"], raiz)
    with open(plan, "w", encoding="utf-8"):
        pass
    return dirs, raiz, plan, "src/retirado.py", "blob-prueba"


def correr_banco():
    """20 casos, cada uno con rc Y causa esperados. Escribe SOLO en tmpdir."""
    print("BANCO MUST-FAIL (cadenas en memoria; scratch en tmpdir FUERA del corpus)")
    print("ESCRITURAS DECLARADAS: solo tmpdir; CERO escrituras al corpus.")

    dirs, dirp, target, blob, lineas = _repo_scratch()  # HUELLA-FIX-NLINEAS-20261018
    huella = "HUELLA-BANCO-PWG-20261015"
    rcs = {}

    def caso(cid, esperado_causa, esperado_rc, *args, **kw):
        r = evaluar(*args, **kw)
        ok = r["rc"] == esperado_rc and r["causa"] == esperado_causa
        print(
            "CASO %-14s rc=%-3s esperado=%-3s causa=%-20s %s"
            % (cid, r["rc"], esperado_rc, r["causa"], "OK" if ok else "ROJO")
        )
        if not ok:
            print("      detalle: %s" % r["detalle"])
        rcs[cid] = ok
        return r

    # B1 tupla incompleta -> 20
    caso("B1_TUPLA", "CONTRATO_INCOMPLETO", 20, target, blob, "")
    # B2 ruta relativa -> 20 (en bash era RC 128: defecto declarado)
    caso("B2_RELATIVA", "CONTRATO_INCOMPLETO", 20, "destino.md", blob, huella, lineas)
    # B3 objeto inexistente -> 10 (autoriza creacion)
    caso("B3_INEXIST", "OBJETO_INEXISTENTE", 10, os.path.join(dirp, "no_existe.md"), blob, huella, 0)
    # B4 huella ya presente -> 11 (cumplimiento pasivo)
    caso("B4_HUELLA", "HUELLA_YA_HABITA", 11, target, blob, "# destino", None)
    # B5 sin arbol git -> 14
    solo = tempfile.TemporaryDirectory(prefix="pwg_sinrepo_")
    fuera = os.path.join(solo.name, "suelto.md")
    with open(fuera, "w", encoding="utf-8") as fh:
        fh.write("sin repo\n")
    caso("B5_SINREPO", "SIN_REPO", 14, fuera, blob, huella, None)
    # B17 directorio INEXISTENTE fuera de todo arbol -> 14 (fail-open cerrado)
    # HUELLA-GATE-FAIL-CLOSED-TREE-PY-20261020: B5 no cubria este plano porque
    # materializa el archivo. Aqui el objeto NO existe y su ancestro tampoco:
    # antes del fix el gate respondia 10 (autorizaba escribir en la nada).
    caso(
        "B17_TREE_FANT",
        "SIN_REPO",
        14,
        os.path.join(solo.name, "sin_dir", "fantasma.md"),
        blob,
        huella,
        None,
    )
    # B18 subdirectorio INEXISTENTE dentro del repo -> 10 (la luz verde intacta)
    caso(
        "B18_SUBDIR_NEW",
        "OBJETO_INEXISTENTE",
        10,
        os.path.join(dirp, "sub_nuevo", "x.md"),
        blob,
        huella,
        0,
    )
    # B6 blob desfase -> 12
    caso("B6_BLOB", "DESFASE_DE_OBJETO", 12, target, "0" * 40, huella, lineas)
    # B7 limpio con lineas -> 0
    caso("B7_LIMPIO", "PRE_VUELO_OK", 0, target, blob, huella, lineas)
    # B8 limpio sin lineas declaradas -> 0 PARCIAL (RC 15 no evaluado)
    r8 = caso("B8_PARCIAL", "PRE_VUELO_OK", 0, target, blob, huella, None)
    print("      no_medido: %s" % (r8["no_medido"] or "ninguno"))
    # B9 lineas distintas -> 15
    caso("B9_LINEAS", "LINEAS_DISTINTAS", 15, target, blob, huella, lineas + 1)
    # B10 estado sucio (blob real, huella ausente) -> 13
    with open(target, "a", encoding="utf-8") as fh:
        fh.write("linea de otra mano\n")
    rc, out, _ = _git(["hash-object", "--", target], dirp)
    caso("B10_SUCIO", "ESTADO_SUCIO", 13, target, out.strip(), huella, _lineas(target))
    # B11 objeto NUEVO sin historia en el indice -> 17 (no bloquea; divergencia D2)
    nuevo = os.path.join(dirp, "nuevo.md")
    with open(nuevo, "w", encoding="utf-8") as fh:
        fh.write("objeto nuevo\n")
    rc, out, _ = _git(["hash-object", "--", nuevo], dirp)
    blob_nuevo = out.strip()
    caso("B11_NUEVO", "OBJETO_NUEVO", 17, nuevo, blob_nuevo, huella, _lineas(nuevo))
    # B12 objeto nuevo CON lineas distintas -> 15: el bloqueante NO se enmascara
    caso("B12_NUEVO_LINEAS", "LINEAS_DISTINTAS", 15, nuevo, blob_nuevo, huella, _lineas(nuevo) + 1)

    retiro_dirs, retiro_root, retiro_plan, retiro_target, retiro_blob = _repo_scratch_retiros()
    auditoria = auditar_resta(retiro_root)
    ok = auditoria["rc"] == 16 and auditoria["sin_retiro"] == [retiro_target]
    print(
        "CASO B13_RETIRO_SIN_REG rc=%-3s esperado=16  causa=%-20s %s"
        % (auditoria["rc"], CAUSAS[16][0], "OK" if ok else "ROJO")
    )
    rcs["B13_RETIRO_SIN_REG"] = ok

    with open(os.path.join(os.path.dirname(retiro_plan), "tuplas.retiradas.tsv"), "a", encoding="utf-8") as fh:
        # HUELLA-BANCO-RETIRO-MOTIVO-SIN-ESPACIOS-20261018: MOTIVO = UN SOLO TOKEN.
        # El contrato de columnas se parte por espacios (s.split()): un motivo con
        # espacios da 6 campos y el motor hace fail-closed (RC 30) por dato, no por codigo.
        fh.write("%s\t%s\tretirado_por_prueba\tHUELLA-BANCO-RETIRO-20261018\n" % (retiro_target, retiro_blob))
    auditoria = auditar_resta(retiro_root)
    ok = (
        auditoria["rc"] == 0
        and not auditoria["sin_retiro"]
        and auditoria["detalle"].startswith("resta declarada")
    )
    print(
        "CASO B14_RETIRO_REG  rc=%-3s esperado=0   causa=%-20s %s"
        % (auditoria["rc"], CAUSAS[auditoria["rc"]][0], "OK" if ok else "ROJO")
    )
    rcs["B14_RETIRO_REG"] = ok

    # B15 retiro HUERFANO por objeto VIVO EN DISCO -> 18
    # HUELLA-BANCO-RETIRO-HUERFANO-DISCO-20261018: la fila de retiro ya existe
    # (B14) y el TARGET se materializa en disco; el retiro queda sin objeto.
    os.makedirs(os.path.join(retiro_root, os.path.dirname(retiro_target)), exist_ok=True)
    with open(os.path.join(retiro_root, retiro_target), "w", encoding="utf-8") as fh:
        fh.write("el objeto sigue vivo\n")
    auditoria = auditar_resta(retiro_root)
    ok = auditoria["rc"] == 18 and auditoria["huerfanos"] == [retiro_target]
    print(
        "CASO B15_RETIRO_VIVO  rc=%-3s esperado=18  causa=%-20s %s"
        % (auditoria["rc"], CAUSAS[auditoria["rc"]][0], "OK" if ok else "ROJO")
    )
    rcs["B15_RETIRO_VIVO"] = ok

    # B16 retiro HUERFANO por objeto TODAVIA DECLARADO -> 18
    # HUELLA-BANCO-RETIRO-HUERFANO-DECLARADO-20261018: se restituye la fila
    # declarada (identica a origin/main: el diff queda vacio) y se borra el
    # objeto del disco; el unico testigo que queda es la declaracion.
    with open(retiro_plan, "w", encoding="utf-8") as fh:
        fh.write("%s %s %s 4\n" % (retiro_target, retiro_blob, "HUELLA-RETIRO"))
    os.remove(os.path.join(retiro_root, retiro_target))
    auditoria = auditar_resta(retiro_root)
    ok = (
        auditoria["rc"] == 18
        and auditoria["huerfanos"] == [retiro_target]
        and not auditoria["borradas"]
    )
    print(
        "CASO B16_RETIRO_DECL rc=%-3s esperado=18  causa=%-20s %s"
        % (auditoria["rc"], CAUSAS[auditoria["rc"]][0], "OK" if ok else "ROJO")
    )
    rcs["B16_RETIRO_DECL"] = ok
    retiro_dirs.cleanup()

    # B19 la palabra del veredicto esta atada a NO_BLOQUEANTES
    # HUELLA-GATE-FIX-MENSAJE-RC10-20261020: el motor imprimia "FALLO CERRADO RC=10"
    # sobre un codigo que NO bloquea la escritura en cadena (D13 textual). Aqui la
    # palabra se ata al registro: solo un RC bloqueante puede decir FALLO CERRADO, y
    # los dos registros deben partir CAUSAS sin dejar codigo sin clasificar.
    desclasificados = set(CAUSAS) - set(NO_BLOQUEANTES) - set(BLOQUEANTES)
    contradicen = [
        rc
        for rc in CAUSAS
        if (_palabra_veredicto(rc) == "FALLO CERRADO") == (rc in NO_BLOQUEANTES)
    ]
    ok = not desclasificados and not contradicen
    print(
        "CASO B19_VEREDICTO   rc=%-3s esperado=0   causa=%-20s %s"
        % (0 if ok else 20, CAUSAS[0][0], "OK" if ok else "ROJO")
    )
    if not ok:
        print("      desclasificados: %s | contradicen: %s" % (sorted(desclasificados), contradicen))
    rcs["B19_VEREDICTO"] = ok

    # B20 paridad de gemelos en el eje LINEAS_PRE
    # HUELLA-B20-PARIDAD-LINEAS-20261020: medido antes del fix, con BLOB_PRE
    # completo y LINEAS_PRE="", el gemelo bash devolvia RC 0 (su guarda 5 es
    # `[ -n "$LINEAS_PRE" ]`) y este motor RC 20 (int("") -> ValueError). Mismo
    # input, dos RC: la paridad NO se declara en prosa, se corre el .sh sobre el
    # MISMO scratch y se exige el mismo RC en los tres planos del eje.
    # Scratch propio: B10 deja el target del banco sucio (blob viejo -> 12).
    # Nota: el plano divergente da RC 15 (LINEAS_DISTINTAS) en AMBOS gemelos;
    # RC 12 es desfase de BLOB, no de lineas.
    p_dirs, _p_dirp, p_target, p_blob, p_lineas = _repo_scratch()
    gemelo = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "tools",
        "gate_pre_escritura.sh",
    )

    def _paridad(lineas_pre):
        arg = "" if lineas_pre in (None, "") else str(lineas_pre)
        res = evaluar(p_target, p_blob, huella, lineas_pre)
        proc = subprocess.run(
            ["bash", gemelo, p_target, p_blob, huella, arg],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return res, proc.returncode

    if not os.path.isfile(gemelo):
        ok = False
        print(
            "CASO B20_PARIDAD      gemelo AUSENTE: %s | la paridad no se puede medir"
            % gemelo
        )
    else:
        fallos = []
        for etiqueta, valor, esperado in (
            ("vacio", "", 0),
            ("conforme", p_lineas, 0),
            ("divergente", p_lineas + 1, 15),
        ):
            res, rc_sh = _paridad(valor)
            if not (res["rc"] == rc_sh == esperado):
                fallos.append(
                    "%s: port=%s gemelo=%s esperado=%s" % (etiqueta, res["rc"], rc_sh, esperado)
                )
            if etiqueta == "vacio" and res["lineas_evaluadas"]:
                fallos.append("vacio: el port EVALUO lineas (verde pleno, no parcial)")
        ok = not fallos
        print(
            "CASO B20_PARIDAD      rc=%-3s esperado=0   causa=%-20s %s"
            % (0 if ok else 20, CAUSAS[0][0], "OK" if ok else "ROJO")
        )
        if fallos:
            print("      divergencias: %s" % "; ".join(fallos))
    rcs["B20_PARIDAD"] = ok
    p_dirs.cleanup()

    dirs.cleanup()
    solo.cleanup()

    n_ok = sum(1 for v in rcs.values() if v)
    n = len(rcs)
    print("CASOS: %d, VERDES: %d, ROJOS: %d" % (n, n_ok, n - n_ok))
    if n_ok != n:
        print("VEREDICTO BANCO: CONTRATO ROTO RC=2")
        return 2
    print("VEREDICTO BANCO: VERDE (%d/%d) RC=0" % (n_ok, n))
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="gate_pre_escritura",
        description="Arnes de PRE-VUELO obligatorio y bloqueante (A2.1). Sin corrida previa con RC 0 esta PROHIBIDO abrir o mutar el archivo.",
    )
    ap.add_argument("target", nargs="?", default=None, help="ruta ABSOLUTA del archivo a mutar")
    ap.add_argument("blob_pre", nargs="?", default=None, help="git hash-object previo")
    ap.add_argument("huella", nargs="?", default=None, help="fragmento literal exclusivo del texto a insertar")
    ap.add_argument("lineas_pre", nargs="?", default=None, help="wc -l previo (`-` si no se declara)")
    ap.add_argument("--plan", default=None, help="lote: archivo con una tupla por linea (4 campos)")
    ap.add_argument("--json", action="store_true", help="salida cruda JSON (sin cabecera humana)")
    ap.add_argument("--self-test", action="store_true", dest="self_test", help="corre el banco must-fail")
    ap.add_argument("--must-fail", action="store_true", dest="must_fail", help="alias de --self-test")
    ap.add_argument("--version", action="version", version=VERSION)
    ns = ap.parse_args(argv)

    if ns.self_test or ns.must_fail:
        return correr_banco()
    if ns.plan:
        return correr_plan(ns.plan, json_mode=ns.json)

    lineas_pre = None if ns.lineas_pre in (None, "-") else ns.lineas_pre
    res = evaluar(ns.target, ns.blob_pre, ns.huella, lineas_pre)
    imprimir(res, json_mode=ns.json)
    return res["rc"]


if __name__ == "__main__":
    raise SystemExit(main())
