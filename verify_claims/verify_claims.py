#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contrato semantico de manifiestos: la prosa contra el dato.

HUELLA-VERIFY-CLAIMS-20261020
HUELLA-VERIFY-CLAIMS-PARSER-20261020
HUELLA-VERIFY-CLAIMS-PARSER-ESPECIFICO-20261020
HUELLA-VERIFY-CLAIMS-RC-17-ESPERANDO-20261020
HUELLA-VERIFY-CLAIMS-MODO-OBLIGATORIO-Y-SELECTOR-20261021
HUELLA-VERIFY-CLAIMS-SOLVERS-COTEJO-20261021
HUELLA-VERIFY-CLAIMS-FALSADOR-PHANTOM-DATO-20261021
HUELLA-VERIFY-CLAIMS-ANCLA-DATO-20261021
HUELLA-VERIFY-CLAIMS-SONDA-DIGITOS-20261021

El aparato de manifiesto (`verify_manifest.py`) prueba que un `.json` parsea y
que un `.md` tiene lineas. NO prueba que la cifra publicada sea la que el dato
contiene. Este verificador mide eso y nada mas: cada claim de `.github/claims.json`
declara una afirmacion de la prosa, el dato del que sale y la EXPRESION que la
deriva. Se compara derivado contra afirmado bajo una polaridad declarada.

Por que la expresion y no el nombre de la clave: medido en `fotonica-monotile`,
el README publica «28 de 29 bins» mientras el dato guarda `cumple` con
`sum(cumple) == 1`. Un contrato escrito sobre nombres de clave habria puesto en
rojo al unico repo cuyo veredicto es un NEGATIVO honesto. La polaridad lleva el
signo; el nombre no.

Vocabulario cerrado de `polaridad`:

    exacto      derivado == afirmado            (dentro de 1e-9)
    cerca_de    |derivado - afirmado| <= tolerancia
    al_menos    derivado >= afirmado
    complemento total - derivado == afirmado    (`total` es otra expresion)

Dos dialectos de `deriva`, y el claim declara cual usa:

    <expresion>                  se evalua sobre el JSON de `dato` (raiz `dato`)
    parser:<ruta>::<funcion>     se corre el PORTADOR que el repo ya tiene: el
                                 testigo de `tests/` que recomputa la cifra desde
                                 su crudo. `<ruta>` es relativa al repo.

El dialecto `parser:` existe porque hay repos cuyo portador no es un `.json`
sino un testigo que corre el solver entero y asevera el veredicto. Reescribir
esos manifiestos a expresiones los degradaria: una expresion sobre un campo JSON
no puede correr el solver. La herramienta se adapta a la ley, no al reves.

Modo de cada claim `parser:` (`modo` en la salida):

    derivacion   la funcion DEVUELVE la cifra: se aplica `polaridad` contra
                 `afirma`, igual que en el dialecto de expresion.
    testigo      la funcion ASEVERA y no devuelve cifra (`None`): el portador
                 porta la comparacion adentro (prosa contra crudo) y el
                 instrumento NO la re-deriva. Se firma con el modo declarado en
                 voz alta para que nadie lea «CLAIMS_SANO» como un numero
                 recomputado aqui.

`modo` tambien se puede DECLARAR en el claim, y solo con dos palabras
(`MODOS_DECLARADOS`); las otras tres se infieren, y declararlas es inventarlas.

    derivacion          el claim se compromete a recomputar aqui. Si el portador
                        no devuelve cifra, la promesa esta incumplida:
                        MODO_CONTRADICHO.
    testigo_permanente  el claim declara que su cifra NO se re-deriva aqui, y
                        esta OBLIGADO a declarar `motivo` (texto no vacio): una
                        excepcion sin causa es un verde oculto, y sin motivo el
                        repo es `MOTIVO_AUSENTE` (rc=1) y no firma nada. Se firma
                        solo si la derivacion NO cierra hoy: si cerrara, la
                        conversion estaba disponible y el motivo sobraba
                        (DERIVACION_POSIBLE).

`modo` es OBLIGATORIO (HUELLA-VERIFY-CLAIMS-MODO-OBLIGATORIO-Y-SELECTOR-20261021):
un claim sin `modo` no infiere nada, es `MODO_NO_DECLARADO` (rc=1). La unica
excepcion es estructural, no inferida: el claim que ya trae `portador_local`
tiene su modo dicho y declararlo seria contradecirlo. Antes, `modo` ausente
firmaba en silencio el modo que el instrumento adivinaba — catorce claims del
portafolio firmaban sin haber declarado nunca. Un default invisible es un verde
que nadie eligio.

Un repo con
permanentes NO firma `CLAIMS_SANO`: firma `CLAIMS_TESTIGO_PERMANENTE` (rc=0,
contado aparte). Tapa `README_DESALINEADO` por construccion — ese es su precio,
y por eso exige motivo y contador propio.

Frontera de dialecto: `portador_local` (opcional)

Hay claims cuya cifra NO se recomputa con un portador invocable de una sola
llamada: su crudo se COMPONE en runtime (argv armado, fichero temporal, dos
funciones encadenadas). Ese claim declara `portador_local: <ruta del testigo del
propio repo>` y el verificador global no adivina la composicion: imprime
`SKIP: PARSER_ESPECIFICO` y escala el claim al testigo local, que si la conoce.

El salto se paga en voz alta: un claim con `portador_local` impide que su repo
firme `CLAIMS_SANO`; el veredicto del repo pasa a `ESPERANDO_TESTIGO_LOCAL`. Un
salto que se lee como verde es un verde oculto, y es justo el defecto que este
campo existe para no cometer. La prosa del claim SI se coteja aqui: el global no
recomputa la cifra, pero comprueba que la prosa la diga.

La importacion del portador ejecuta codigo del repo medido: es el contrato, no
un descuido. `PROHIBIDO` acota el dialecto de expresion; el de portador se acota
porque el archivo lo escribe el mismo repo que se esta midiendo.

Falsadores y RC:

    SCHEMA_INCOMPLETO       la clase lo exige y no hay .github/claims.json      1
    SCHEMA_VIOLADO          no parsea o le falta un campo obligatorio           1
    POLARIDAD_NO_DECLARADA  polaridad fuera del vocabulario                     1
    VALOR_NO_DERIVABLE      `deriva` no evalua sobre `dato`                     1
    DERIVACION_CIEGA        el valor no cambia al mutar lo que la expresion lee 1
    README_DESALINEADO      derivado != afirmado, o la afirmacion no esta en la 1
                            prosa que el claim declara
    PARSER_AUSENTE          el portador declarado no existe o no define la      1
                            funcion
    PARSER_DISCREPA         el portador corrio y su aseveracion no cierra       1
    PARSER_ROTO             el portador no importa o revienta al correr         1
    PARSER_NO_NUMERICO      el portador devuelve algo que no es cifra ni None   1
    RUTA_AUSENTE            el claim declara `ruta` y esa ruta no resuelve en   1
                            lo que el portador devolvio
    RUTA_DE_OTRO_SOLVER     el claim pide una `ruta` cuyo primer segmento      1
                            nombra a otro solver del que el portador sirve
    SOLVER_DE_DATO_NO_DECLARADO el repo declara `solvers` y el primer segmento  1
                            de `ruta` no esta en esa lista: el claim nombra un
                            solver que el repo no declara
    PHANTOM_DATO            el portador devuelve la MISMA cifra con su `dato`   1
                            vaciado: la cifra no sale de la fuente que declara
                            (modo `--falsador-dato`)
    SIN_BASELINE            el claim no estaba verde antes del vaciado: el      1
                            falsador no puede atribuirle el rojo que el provoca
    DATUM_NO_NEUTRALIZABLE  el `dato` no se puede vaciar dentro de la copia     1
                            (no es archivo regular, o apunta fuera de ella)
    DATUM_ES_PORTADOR       el portador VIVE en el `dato`: vaciarlo borra el    0
                            instrumento, no su fuente — deuda declarada, no verde
    MODO_NO_DECLARADO       el claim no declara `modo`, o declara uno fuera     1
                            del vocabulario: sin declaracion no firma
    MOTIVO_AUSENTE          el claim se declara `testigo_permanente` y no       1
                            justifica el salto
    MOTIVO_HUERFANO         el claim trae `motivo` sin un modo que lo justifique 1
    PARSER_ESPECIFICO_AUSENTE el claim declara `portador_local` y esa ruta no   1
                            existe: un salto sin testigo que lo mida
    SIN_DATO_MECANIZABLE    el repo declara que no puede medir                  1
    CLAIMS_SANO             todos los claims derivan y coinciden                0
    ESPERANDO_TESTIGO_LOCAL el repo tiene claims `portador_local` que el global 17
                            no re-deriva y su testigo local mide (veredicto, no
                            falla: no es un verde, es un pendiente declarado)

El RC del run tiene tres estados, no dos:

    0   todos los repos `CLAIMS_SANO`                                    verde
    1   algun claim fallo (AUSENTE, DISCREPA, ROTO, DESALINEADO, ...)     rojo
    17  algun repo `ESPERANDO_TESTIGO_LOCAL` y ningun fallo           amarillo

`17` existe porque `0` y `1` mienten los dos sobre un claim escalado: `0` lo hace
pasar por verde verificado, `1` lo hace pasar por roto, y no es ninguna de las
dos cosas. Un run con `17` no es un verde: una parte de sus claims la mide un
testigo que este aparato no corre. Lo que el RC no decide es la politica del
gate que lo consume; aqui solo se declara el estado.

El campo `ruta` (opcional) dice DONDE vive la cifra dentro de lo que el portador
devuelve: `raiz.resto`, donde `raiz` es el primer segmento y `resto` resuelve en
el objeto. Gramatica del `resto`, identica a la del testigo de claims del repo:

    a.b              desciende por clave; sobre lista de objetos, proyecta
    a[campo=valor]   filtra la lista por campo == valor
    a#distintos      deduplica la lista
    (una lista al final vale su longitud)

Si el portador devuelve algo que no es un objeto, se envuelve bajo su propia
`raiz`, para que `raiz.campo` se lea igual cuando el crudo no trae envoltorio.

Un portador CON parametro recibe `raiz` como modo y es su propio testigo: si no
sirve a ese solver, lo dice al correr. Uno SIN parametros no recibe nada, y por
eso tiene que NOMBRAR al solver en su cuerpo: si la `raiz` no aparece entre las
cadenas que el portador nombra, el claim es `RUTA_DE_OTRO_SOLVER`. Sin esta ley
el primer segmento se descartaba sin comprobarlo y el selector era decorativo:
medido en `plasma-ade`, `pulso.sellos.filas` sobre un portador de `cw` daba
27.0 con rc=0.

`solvers` (opcional, en la raiz del claims.json): la lista de solvers que el repo
DECLARA. El primer segmento de `ruta` es un selector de solver, y desde
HUELLA-VERIFY-CLAIMS-SOLVERS-COTEJO-20261021 el claim que deriva coteja su
selector contra esa lista declarada: si el selector no esta en `solvers`, es
`SOLVER_DE_DATO_NO_DECLARADO` (rc=1). El cotejo es CONDICIONADO y se lee en voz
alta en la firma (`solvers` por claim): un repo que no declara la lista no tiene
contra que cotejar y su rama no corre, y un `testigo_permanente` queda exento
porque su primer segmento es residuo del crudo congelado, no un selector — esos
claims ya no firman `CLAIMS_SANO`. `solvers` declarado y jamas leido habria sido
una declaracion decorativa mas: la novena de la sesion, sellada en `plasma-ade`
con 0 apariciones en este archivo.

La fisica del `dato` (modo `--falsador-dato`, alias `--falsador-phantom-dato`)

El dialecto `parser:` coteja que el `dato` EXISTA: `os.path.isfile` es toda la
guarda, y `doc = None` deja el documento sin abrir. Un portador que devuelve la
cifra de memoria —sin leer nada— firma `CLAIMS_SANO` si la cifra es la correcta:
medido en `rf-signal-integrity` con el `dato` vaciado a 0 bytes. Los 19 claims
`parser:` del portafolio publicaban `mutaciones: 0` en `--json`: la firma decia,
en voz baja, que ningun control habia corrido.

Este modo corre la sonda que falta. Por repo: copia (sin `.git` ni
`__pycache__`), baseline por claim sobre la copia intacta, y despues los `dato`
de TODOS los medibles se truncan a 0 bytes. Vaciado, NO borrado: borrado, la
guarda `isfile` del camino normal se queja y el fantasma pasa por honesto;
vaciado, la guarda abre paso y solo se rompe quien LEE.

Veredicto por claim, en su propio `try` (el bucle de `main` aborta en el primer
rojo y certificaria uno de ocho):

    PARSER_LEE_DATO         el portador rompe, o la cifra se mueve: lee        0
    PHANTOM_DATO            la cifra sobrevive identica al vaciado: no lee     1
    SIN_BASELINE            el claim no estaba verde: el rojo no es del        1
                            vaciado
    DATUM_NO_NEUTRALIZABLE  el `dato` no se puede vaciar en la copia           1
    DATUM_ES_PORTADOR       el portador VIVE en el `dato`: vaciarlo borra el   0
                            instrumento, no su fuente — deuda declarada
    EXENTO_TESTIGO          `testigo_permanente`: no hay cifra que mover       0
    EXENTO_ESPECIFICO       `portador_local`: lo mide el testigo del repo      0
    FUERA_DE_ALCANCE_...    dialecto de expresion: `_control_de_ceguera` ya    0
                            muta el documento

Ninguna exencion es un `continue` mudo: cada una se imprime con su nombre y se
cuenta aparte. Una exencion que no se imprime es una decorativa esperando turno.

No es la ruta por defecto: cuesta una copia del repo y una corrida completa de
sus portadores (medido: rf 0.4 s · red-green 19 s · plasma ~2 min). El camino
normal conserva la guarda barata, y el acto que certifica la fisica lo invoca.

Frontera: prueba DEPENDENCIA, no CORRECCION. Que la cifra se mueva al vaciar el
`dato` prueba que no puede vivir sin el; no prueba que sea la funcion correcta
de el. La exactitud la firman `afirma` + `tolerancia`.

`SIN_DATO_MECANIZABLE` es el falsador mas importante: es la forma de que el
instrumento diga en voz alta que NO puede medir, en lugar de firmar un verde por
omision.

Uso:

    python3 sim/verify_claims.py REPO [REPO ...]
    python3 sim/verify_claims.py --json REPO [REPO ...]
    python3 sim/verify_claims.py --falsador-dato REPO [REPO ...]
    python3 sim/verify_claims.py --autotest
"""

import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import sys
import tempfile

POLARIDADES = ("exacto", "cerca_de", "al_menos", "complemento")
# HUELLA-VERIFY-CLAIMS-MODO-TESTIGO-PERMANENTE-20261020: de las cinco palabras
# de `modo`, solo estas dos se declaran; las otras tres (expresion, testigo,
# especifico) las infiere el instrumento y declararlas seria inventarlas.
MODOS_DECLARADOS = ("derivacion", "testigo_permanente")
OBLIGATORIOS = ("id", "afirma", "dato", "deriva", "polaridad", "prosa")
PROHIBIDO = (
    "__",
    "import",
    "open",
    "eval",
    "exec",
    "compile",
    "globals",
    "locals",
    "getattr",
    "setattr",
    "os.",
    "sys.",
    "subprocess",
)
EPS = 1e-9

# Estado propio del run con claims escalados: ni verde verificado ni fallo.
RC_ESPERANDO_TESTIGO_LOCAL = 17


class Falla(Exception):
    def __init__(self, codigo, detalle):
        Exception.__init__(self, detalle)
        self.codigo = codigo
        self.detalle = detalle


def _num(texto):
    """Extrae el numero de una afirmacion de prosa: '13.11 %' -> 13.11.

    Admite la forma con etiqueta ('DISCREPA=7'), que es la que hace fuerte el
    cotejo contra la prosa: se busca la CADENA ENTERA, no un digito suelto.
    """
    limpio = texto.replace("\u00a0", " ")
    for tok in limpio.replace("%", " ").replace(",", ".").split():
        try:
            return float(tok)
        except ValueError:
            continue
    hallado = re.search(r"[-+]?\d+(?:\.\d+)?", texto)
    if hallado:
        return float(hallado.group(0))
    raise Falla(
        "SCHEMA_VIOLADO", "la afirmacion %r no trae ningun numero" % texto
    )


class _Nodo(object):
    """Vista del dato que responde a `a.b` y a `a['b']` por igual.

    Sin esto, `dato.medido.residuo` sobre un dict seria un AttributeError y el
    contrato solo admitiria subindices: la expresion se escribe para leerse.
    """

    def __init__(self, valor):
        self._v = valor

    def __getattr__(self, clave):
        if clave.startswith("_"):
            raise AttributeError(clave)
        try:
            return _envolver(self._v[clave])
        except (KeyError, TypeError, IndexError):
            raise AttributeError(clave)

    def __getitem__(self, clave):
        return _envolver(self._v[clave])

    def __len__(self):
        return len(self._v)

    def __iter__(self):
        return iter([_envolver(x) for x in self._v])

    def __repr__(self):
        return repr(self._v)


def _envolver(valor):
    if isinstance(valor, (dict, list)):
        return _Nodo(valor)
    return valor


def _entorno(doc):
    def count(xs, valor):
        return sum(1 for x in xs if x == valor)

    return {
        "dato": _envolver(doc),
        "len": len,
        "sum": sum,
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "int": int,
        "float": float,
        "sorted": sorted,
        "count": count,
        "total": len,
    }


def _evaluar(expr, doc):
    if not isinstance(expr, str) or not expr.strip():
        raise Falla("SCHEMA_VIOLADO", "expresion vacia")
    for malo in PROHIBIDO:
        if malo in expr:
            raise Falla(
                "SCHEMA_VIOLADO", "expresion prohibida (%r) en %r" % (malo, expr)
            )
    try:
        return eval(expr, {"__builtins__": {}}, _entorno(doc))  # noqa: S307
    except Falla:
        raise
    except Exception as e:
        raise Falla(
            "VALOR_NO_DERIVABLE", "%r no evalua sobre el dato: %s: %s"
            % (expr, type(e).__name__, e)
        )


def _parser_ref(deriva):
    """(ruta, funcion) si `deriva` es una referencia a portador, o None.

    Una `deriva` que empieza por `parser:` y no trae la forma completa NO cae al
    dialecto de expresion: seria un `VALOR_NO_DERIVABLE` que culpa a la
    expresion de un error de sintaxis del contrato. Se nombra el defecto.
    """
    if not isinstance(deriva, str):
        return None
    texto = deriva.strip()
    if not texto.startswith("parser:"):
        return None
    m = re.match(r"^parser:(.+?)::([A-Za-z_][A-Za-z0-9_.]*)$", texto)
    if not m:
        raise Falla(
            "SCHEMA_VIOLADO",
            "deriva %r no tiene la forma parser:<ruta>::<funcion>" % deriva,
        )
    return m.group(1), m.group(2)


def _cargar_portador(repo, ruta):
    """Importa el portador por ruta, sin ensuciar `sys.modules` ni `sys.path`."""
    ruta_abs = os.path.abspath(os.path.join(repo, ruta))
    if not os.path.isfile(ruta_abs):
        raise Falla("PARSER_AUSENTE", "el portador no existe: %s" % ruta)
    nombre = "_claims_portador_" + re.sub(r"[^A-Za-z0-9]+", "_", ruta)
    previo = sys.path[:]
    sys.path.insert(0, os.path.dirname(os.path.dirname(ruta_abs)))
    try:
        espec = importlib.util.spec_from_file_location(nombre, ruta_abs)
        if espec is None or espec.loader is None:
            raise Falla("PARSER_AUSENTE", "%s no se puede importar" % ruta)
        modulo = importlib.util.module_from_spec(espec)
        sys.modules[nombre] = modulo
        espec.loader.exec_module(modulo)
        return modulo
    except Falla:
        sys.modules.pop(nombre, None)
        raise
    except BaseException as e:
        sys.modules.pop(nombre, None)
        raise Falla(
            "PARSER_ROTO", "%s no importa: %s: %s" % (ruta, type(e).__name__, e)
        )
    finally:
        sys.path[:] = previo


def _resolver_funcion(modulo, nombre, ruta):
    actual = modulo
    for parte in nombre.split("."):
        if not hasattr(actual, parte):
            raise Falla("PARSER_AUSENTE", "%s no define %r" % (ruta, nombre))
        actual = getattr(actual, parte)
    if not callable(actual):
        raise Falla("PARSER_AUSENTE", "%s:%r no es invocable" % (ruta, nombre))
    return actual


_SEGMENTO = re.compile(
    r"^(?P<clave>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\[(?P<campo>[A-Za-z_][A-Za-z0-9_]*)=(?P<valor>[^\]]+)\])?"
    r"(?:#(?P<op>distintos))?$"
)


def _literal_js(txt):
    t = txt.strip()
    if t.lower() == "true":
        return True
    if t.lower() == "false":
        return False
    for cast in (int, float):
        try:
            return cast(t)
        except ValueError:
            pass
    return t.strip("'\"")


def _resolver_ruta(obj, ruta):
    """Resuelve `a.b[campo=valor].c#distintos`; una lista al final vale su largo."""
    actual = obj
    for segmento in ruta.split("."):
        m = _SEGMENTO.match(segmento)
        if not m:
            raise ValueError("RUTA_INVALIDA: %r no es un segmento valido" % ruta)
        clave = m.group("clave")
        if isinstance(actual, dict):
            if clave not in actual:
                raise ValueError("RUTA_AUSENTE: %r no existe en el crudo" % ruta)
            actual = actual[clave]
        elif isinstance(actual, list) and actual and all(
            isinstance(i, dict) for i in actual
        ):
            if not any(clave in i for i in actual):
                raise ValueError(
                    "RUTA_AUSENTE: %r no proyecta %r sobre la lista" % (ruta, clave)
                )
            actual = [i.get(clave) for i in actual]
        else:
            raise ValueError(
                "RUTA_AUSENTE: %r no desciende sobre %s"
                % (ruta, type(actual).__name__)
            )
        campo = m.group("campo")
        if campo:
            if not isinstance(actual, list):
                raise ValueError("RUTA_INVALIDA: %r filtra sobre algo que no es lista" % ruta)
            esperado = _literal_js(m.group("valor"))
            actual = [
                i for i in actual if isinstance(i, dict) and i.get(campo) == esperado
            ]
        if m.group("op") == "distintos":
            if not isinstance(actual, list):
                raise ValueError("RUTA_INVALIDA: %r #distintos sobre algo que no es lista" % ruta)
            vistos, unicos = set(), []
            for item in actual:
                k = json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
                if k not in vistos:
                    vistos.add(k)
                    unicos.append(item)
            actual = unicos
    return len(actual) if isinstance(actual, list) else actual


# --------------------------------------------------------------------------
# HUELLA-GRAMATICA-DUAL-SHA256-20261020 · el sha256 cruzado de la gramatica
# --------------------------------------------------------------------------
# El dictado pedia «sha256 de la gramatica del global» y «sha256 de la gramatica
# del local». Un sha256 del TEXTO no sirve: las dos copias nombran distinto
# (`_SEGMENTO`/`SEGMENTO`, `_resolver_ruta`/`resolver`) y el hash saldria siempre
# distinto — un sensor ciego que grita sin que la ley cambie. Se hashea la
# CONDUCTA: la matriz de la gramatica sobre los seis fixtures del pre-registro
# `sim/PREREGISTRO_GRAMATICA_DUAL_20261020.md`. Dos copias que resuelven lo mismo
# declaran el mismo hex; la que derive cambia su propio hash y su pin la delata.
CROSS_HASH_GRAMATICA = "c815c06c3e43bf49cc21f3a71c7c52a6e70ba7756f6ea38017d5581ec83d36db"

_CRUDO_CROSS = {
    "escalar": 5,
    "obj": {"cierra": 3},
    "lista": [1, 2, 2, 3],
    "filas": [{"k": "x", "v": 1}, {"k": "y", "v": 2}, {"k": "x", "v": 1}],
}
_FIXTURES_CROSS = (
    ("F1", "obj.cierra"),
    ("F2", "filas[k=x].v"),
    ("F3", "lista#distintos"),
    ("F4", "obj.no_existe"),
    ("F5", "escalar#distintos"),
    ("F6", "filas.k"),
)


def _medir_cross(fn, ruta):
    """El mismo `medir` del arnes congelado: clase, tipo, valor y mensaje."""
    try:
        valor = fn(json.loads(json.dumps(_CRUDO_CROSS)), ruta)
        return ["OK", type(valor).__name__, repr(valor), ""]
    except Exception as e:  # noqa: BLE001
        texto = str(e)
        return [texto.split(":")[0] if ":" in texto else "OTRO", "", "", texto]


def huella_gramatica(fixtures=_FIXTURES_CROSS):
    """sha256 de la conducta de `_resolver_ruta`, no de su texto."""
    matriz = [[fid, *_medir_cross(_resolver_ruta, ruta)] for fid, ruta in fixtures]
    canon = json.dumps(
        matriz, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _exigidos(fn):
    import inspect

    firma = inspect.signature(fn)
    return [
        p
        for p in firma.parameters.values()
        if p.default is p.empty
        and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]


def _en_silencio(fn, *args):
    """La salida del portador no es salida del verificador."""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        return fn(*args)


def _literales(fn):
    """Cadenas que el cuerpo del portador nombra, incluidas las anidadas."""
    vistas, pila, fuera = set(), [getattr(fn, "__code__", None)], []
    while pila:
        codigo = pila.pop()
        if codigo is None or id(codigo) in vistas:
            continue
        vistas.add(id(codigo))
        for constante in codigo.co_consts:
            if isinstance(constante, str):
                fuera.append(constante)
            elif hasattr(constante, "co_consts"):
                pila.append(constante)
    return fuera


def _exigir_selector(fn, devuelto, raiz, ruta, funcion, campo_ruta):
    """Un portador sin parametros tiene que DAR CUENTA de la raiz que le piden.

    Sin esto el primer segmento de `ruta` se descarta sin comprobarlo y el
    selector es decorativo: medido en `plasma-ade`, `pulso.sellos.filas` sobre un
    portador de `cw` devolvio 27.0 con rc=0. Un portador con parametro recibe la
    raiz como modo; uno sin parametros no recibe nada, y le quedan dos formas de
    dar cuenta de ella: devolverla como clave (la raiz vive DENTRO de lo que
    devuelve) o nombrarla en su cuerpo (la raiz elige el solver que corre).
    """
    if not isinstance(devuelto, dict):
        # Lo devuelto no es un objeto: la raiz es la etiqueta con la que el
        # instrumento lo envuelve, y una etiqueta no puede ser de otro solver.
        return
    if raiz in devuelto:
        return
    if raiz in _literales(fn):
        return
    nombrados = sorted({c for c in _literales(fn) if c})
    raise Falla(
        "RUTA_DE_OTRO_SOLVER",
        "%s::%s ni devuelve %r como clave ni lo nombra en su cuerpo (devuelve "
        "%s, nombra %s) y el claim le pide la ruta %r: sin parametros no puede "
        "servir a otro solver"
        % (
            ruta,
            funcion,
            raiz,
            type(devuelto).__name__,
            nombrados or "nada",
            campo_ruta,
        ),
    )


def _portadores_del_repo(repo, claims):
    """(nombres, reciben, raices) de los portadores y de los selectores del repo.

    `raices` son los primeros segmentos de `ruta` de los claims de derivacion:
    la unica definicion de «este solver tiene selector». `nombres` son los
    literales que un portador SIN parametros nombra y que
    pueden ser solvers; `reciben` son los portadores con parametro, que ya
    recibieron la raiz como modo. La forma no dice quien es solver — medido en
    `PREREGISTRO_SOLVERS_MANDATORIO_20261021` §1: por modulo `plasma-ade` daria
    1 (exento, con dos solvers reales) y `red-green-sandbox` 2 (obligado a
    declarar secciones como solvers). El literal si lo dice, y el docstring no:
    `_literales` lo devuelve junto al cuerpo y contarlo inflaria `N`.
    """
    import inspect

    nombres, reciben, vistos = set(), set(), set()
    raices = set()
    for claim in claims:
        if not isinstance(claim, dict) or "portador_local" in claim:
            continue
        if claim.get("modo") != "derivacion":
            continue
        campo_ruta = claim.get("ruta")
        if not campo_ruta or "." not in str(campo_ruta):
            continue
        raices.add(str(campo_ruta).partition(".")[0])
        ref = _parser_ref(claim.get("deriva"))
        if ref is None or ref in vistos:
            continue
        vistos.add(ref)
        ruta, funcion = ref
        fn = _resolver_funcion(_cargar_portador(repo, ruta), funcion, ruta)
        if list(inspect.signature(fn).parameters):
            reciben.add("%s::%s" % (ruta, funcion))
            continue
        docstring = (fn.__doc__ or "").strip()
        for literal in _literales(fn):
            # Solo cuenta como solver el literal que ademas sirve de raiz a un
            # selector de este repo: `Aborta` o `_cargar_receta` son cadenas del
            # cuerpo y no solvers, y medido en `red-green-sandbox` sin este
            # corte `N` salia 4.
            if literal and literal != docstring and literal in raices:
                nombres.add(literal)
    return sorted(nombres), sorted(reciben), sorted(raices)


def _exigir_solvers(repo, claims, solvers):
    """`solvers` deja de ser opt-in: con N >= 2 portadores distintos, obligatorio.

    Sin esto la ausencia de `solvers` se leia como «no aplica» sin que nadie lo
    declarara: la misma ceguera que `modo` inferido. Con un portador o ninguno
    no hay contra que cotejar, pero la ausencia se DECLARA (`NO_APLICABLE`, con
    el motivo medido) en vez de callarse.
    """
    # HUELLA-VERIFY-CLAIMS-SOLVERS-SIN-SELECTOR-RAIZ-20261021: la orfandad se
    # mide contra las raices de los selectores, no contra los portadores que
    # nombran: un portador que RECIBE la raiz no puede nombrarla.
    nombres, reciben, raices = _portadores_del_repo(repo, claims)
    if len(nombres) >= 2:
        if not solvers:
            raise Falla(
                "SOLVERS_SIN_DECLARAR",
                "%d portadores nombran solvers distintos (%s) y el repo no "
                "declara `solvers`: el selector de `ruta` no cotejaria contra "
                "nada" % (len(nombres), ", ".join(nombres)),
            )
        return {
            "portadores": nombres,
            "declarados": list(solvers),
            "sin_selector": [s for s in solvers if s not in raices],
            "veredicto": "COTEJADO",
        }
    if not solvers:
        return {
            "portadores": nombres,
            "reciben": reciben,
            "veredicto": "NO_APLICABLE",
            "detalle": "N=%d · %d portador(es) reciben la raiz como argumento"
            % (len(nombres), len(reciben)),
        }
    # HUELLA-SOLVERS-INNECESARIO-DOC-20261021: el nombre es historico y miente
    # al reves. Significa «la lista declarada no coteja por la ruta
    # `literal in raices`», no «innecesaria para los claims»: medido en
    # `red-green-sandbox`, la lista sirve 8 claims de derivacion cuyos
    # portadores RECIBEN la raiz (`banco` 6, `piloto` 1, `ramas` 1) y ninguno
    # la nombra, asi que `nombres` queda en 0 y el cotejo por nombre no aplica.
    return {
        "portadores": nombres,
        "declarados": list(solvers),
        "sin_selector": [s for s in solvers if s not in raices],
        "veredicto": "SOLVERS_INNECESARIO",
        "detalle": "N=%d: la lista declarada no coteja contra dos solvers"
        % len(nombres),
    }


def _cotejar_solvers(claim, solvers):
    """El primer segmento de `ruta` cotejado contra los `solvers` declarados.

    Devuelve el cotejo que la firma publica, o None cuando no hay nada que
    cotejar. `solvers` es una declaracion del REPO: sin lector seria la novena
    decorativa de la sesion (`plasma-ade` la declara, este archivo no la leia).
    Muerde solo donde puede: sin lista declarada no hay contra que cotejar, y un
    `testigo_permanente` no nombra un solver — su primer segmento es residuo del
    crudo congelado, y esos claims ya no firman `CLAIMS_SANO`.
    """
    campo_ruta = claim.get("ruta")
    if not solvers or not campo_ruta or claim.get("modo") != "derivacion":
        return None
    raiz = str(campo_ruta).partition(".")[0]
    if raiz not in solvers:
        raise Falla(
            "SOLVER_DE_DATO_NO_DECLARADO",
            "el claim %r pide la ruta %r y su selector %r no esta en los "
            "solvers que el repo declara %s: el claim nombra un solver que el "
            "repo no declara" % (claim["id"], campo_ruta, raiz, list(solvers)),
        )
    return {"selector": raiz, "declarados": list(solvers)}


def _derivar_por_portador(claim, repo, ruta, funcion):
    """Corre el portador. Devuelve (cifra|None, modo)."""
    fn = _resolver_funcion(_cargar_portador(repo, ruta), funcion, ruta)
    campo_ruta = claim.get("ruta")
    exigidos = _exigidos(fn)
    if len(exigidos) > 1 or (exigidos and not campo_ruta):
        raise Falla(
            "PARSER_ROTO",
            "%s::%s exige %s y el claim %s declara `ruta` que los nombre"
            % (
                ruta,
                funcion,
                [p.name for p in exigidos],
                "" if campo_ruta else "no",
            ),
        )
    try:
        if not exigidos:
            devuelto = _en_silencio(fn)
        else:
            raiz = str(campo_ruta).partition(".")[0]
            # El modo de un portador se nombra de dos formas en el portafolio:
            # 'banco' (raiz de la ruta) o '--banco' (bandera de la CLI). Se
            # prueban las dos y, si ambas fallan, el error nombra ambas.
            intentos = []
            devuelto = None
            for candidato in (raiz, "--" + raiz):
                try:
                    devuelto = _en_silencio(fn, candidato)
                    break
                except AssertionError as e:
                    raise Falla(
                        "PARSER_DISCREPA",
                        "%s::%s corrio y no cierra: %s"
                        % (ruta, funcion, str(e) or "assert sin mensaje"),
                    )
                except Falla:
                    raise
                except BaseException as e:
                    intentos.append("%r -> %s: %s" % (candidato, type(e).__name__, e))
            else:
                raise Falla(
                    "PARSER_ROTO",
                    "%s::%s no acepta el modo %r: %s"
                    % (ruta, funcion, raiz, " · ".join(intentos)),
                )
    except AssertionError as e:
        raise Falla(
            "PARSER_DISCREPA",
            "%s::%s corrio y no cierra: %s"
            % (ruta, funcion, str(e) or "assert sin mensaje"),
        )
    except Falla:
        raise
    except BaseException as e:
        raise Falla(
            "PARSER_ROTO",
            "%s::%s revienta: %s: %s" % (ruta, funcion, type(e).__name__, e),
        )
    if devuelto is None:
        return None, "testigo"
    if campo_ruta:
        raiz, _, resto = str(campo_ruta).partition(".")
        if not resto:
            raise Falla(
                "SCHEMA_VIOLADO",
                "ruta %r no resuelve nada: falta la clave dentro del crudo"
                % campo_ruta,
            )
        if not exigidos:
            _exigir_selector(fn, devuelto, raiz, ruta, funcion, campo_ruta)
        if not isinstance(devuelto, dict):
            devuelto = {raiz: devuelto}
        try:
            valor = _resolver_ruta(devuelto, resto)
        except ValueError as e:
            raise Falla("RUTA_AUSENTE", "%s (ruta %r)" % (e, campo_ruta))
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise Falla(
                "PARSER_NO_NUMERICO",
                "ruta %r resuelve %s, no una cifra"
                % (campo_ruta, type(valor).__name__),
            )
        return float(valor), "derivacion"
    if isinstance(devuelto, bool) or not isinstance(devuelto, (int, float)):
        raise Falla(
            "PARSER_NO_NUMERICO",
            "%s::%s devuelve %s, ni cifra ni None"
            % (ruta, funcion, type(devuelto).__name__),
        )
    return float(devuelto), "derivacion"


def _cadenas(expr):
    """Cadenas de atributo/subindice que arrancan en `dato` (para el control)."""
    try:
        arbol = ast.parse(expr, mode="eval")
    except SyntaxError:
        return []
    encontradas = []

    def recorrer(nodo):
        if isinstance(nodo, (ast.Attribute, ast.Subscript)):
            raiz = nodo
            partes = []
            while isinstance(raiz, (ast.Attribute, ast.Subscript)):
                if isinstance(raiz, ast.Attribute):
                    partes.append(("attr", raiz.attr))
                    raiz = raiz.value
                else:
                    corte = raiz.slice
                    if isinstance(corte, ast.Constant):
                        partes.append(("key", corte.value))
                    else:
                        partes = None
                        break
                    raiz = raiz.value
            if partes is not None and isinstance(raiz, ast.Name) and raiz.id == "dato":
                encontradas.append(list(reversed(partes)))
        for hijo in ast.iter_child_nodes(nodo):
            recorrer(hijo)

    recorrer(arbol)
    return encontradas


def _mutaciones(valor):
    """Candidatos de mutacion para un valor hoja.

    Se generan VARIOS porque una sola mutacion puede no mover el agregado: quitar
    el ultimo bin de `[True, False, False]` deja `sum` en 1 igual. Declarar ciega
    una expresion correcta por un control flojo es el falso rojo del instrumento.
    """
    if isinstance(valor, bool):
        yield not valor
        return
    if isinstance(valor, int):
        yield valor * 2 + 1
        yield valor + 1
        return
    if isinstance(valor, float):
        yield valor * 2 + 1.0
        yield valor + 0.5
        return
    if isinstance(valor, str):
        yield valor + "_MUT"
        yield "MUT"
        return
    if isinstance(valor, list):
        if valor:
            yield valor[:-1]
            yield valor + valor[:1]
            yield [_primer_mutar(x) for x in valor]
        else:
            yield ["MUT"]
        return
    if isinstance(valor, dict):
        mutado = dict(valor)
        mutado["__MUT__"] = 1
        yield mutado
        yield {}
        return
    yield "MUT"


def _primer_mutar(valor):
    for x in _mutaciones(valor):
        return x
    return "MUT"


def _hoja(doc, partes):
    actual = doc
    for tipo, clave in partes:
        if isinstance(actual, dict):
            if clave not in actual:
                raise KeyError(clave)
            actual = actual[clave]
        elif isinstance(actual, list):
            if not isinstance(clave, int) or not -len(actual) <= clave < len(actual):
                raise KeyError(clave)
            actual = actual[clave]
        else:
            raise KeyError(clave)
    return actual


def _poner(doc, partes, nuevo):
    if not partes:
        raise KeyError("cadena vacia")
    padre = _hoja(doc, partes[:-1]) if len(partes) > 1 else doc
    tipo, clave = partes[-1]
    if isinstance(padre, dict):
        if clave not in padre:
            raise KeyError(clave)
        padre[clave] = nuevo
        return
    if isinstance(padre, list):
        if not isinstance(clave, int) or not -len(padre) <= clave < len(padre):
            raise KeyError(clave)
        padre[clave] = nuevo
        return
    raise KeyError(clave)


def _control_de_ceguera(claim, doc, valor):
    """Muta lo que la expresion LEE. Si el valor no se mueve, la expresion miente."""
    expr = claim["deriva"]
    cadenas = _cadenas(expr)
    if not cadenas:
        raise Falla(
            "DERIVACION_CIEGA",
            "%r no lee nada del dato: el control no puede moverla" % expr,
        )
    probadas = 0
    for partes in cadenas:
        try:
            actual = _hoja(doc, partes)
        except (KeyError, TypeError, IndexError):
            continue
        for candidato in _mutaciones(actual):
            mutado = copy.deepcopy(doc)
            try:
                _poner(mutado, partes, candidato)
            except (KeyError, TypeError, IndexError):
                continue
            probadas += 1
            try:
                despues = _evaluar(expr, mutado)
            except Falla:
                # El dato mutado rompe la derivacion: la expresion SI la lee.
                return probadas
            if despues != valor:
                return probadas
    if probadas == 0:
        raise Falla(
            "DERIVACION_CIEGA",
            "%r nombra rutas que el dato no tiene: el control no pudo mutar nada"
            % expr,
        )
    raise Falla(
        "DERIVACION_CIEGA",
        "%r devuelve el mismo valor con el dato mutado: no deriva del dato" % expr,
    )


def _comparar(claim, doc, valor, afirmado):
    pol = claim["polaridad"]
    if pol == "exacto":
        if abs(valor - afirmado) > EPS:
            raise Falla(
                "README_DESALINEADO",
                "exacto: derivado=%r afirmado=%r" % (valor, afirmado),
            )
    elif pol == "cerca_de":
        tol = claim.get("tolerancia")
        if not isinstance(tol, (int, float)) or isinstance(tol, bool):
            raise Falla(
                "SCHEMA_VIOLADO", "polaridad cerca_de exige 'tolerancia' numerica"
            )
        if abs(valor - afirmado) > tol:
            raise Falla(
                "README_DESALINEADO",
                "cerca_de: |%r - %r| > %r" % (valor, afirmado, tol),
            )
    elif pol == "al_menos":
        if valor < afirmado:
            raise Falla(
                "README_DESALINEADO", "al_menos: derivado=%r < afirmado=%r" % (valor, afirmado)
            )
    elif pol == "complemento":
        if "total" not in claim:
            raise Falla(
                "SCHEMA_VIOLADO", "polaridad complemento exige 'total' (otra expresion)"
            )
        total = _evaluar(claim["total"], doc)
        if abs((total - valor) - afirmado) > EPS:
            raise Falla(
                "README_DESALINEADO",
                "complemento: total(%r) - derivado(%r) = %r != afirmado=%r"
                % (total, valor, total - valor, afirmado),
            )
    else:
        raise Falla("POLARIDAD_NO_DECLARADA", "polaridad %r fuera del vocabulario" % pol)


def _prosa_comparable(txt):
    """Markdown a prosa comparable: sin enfasis, sin backticks, espacios colapsados.

    Sin esto, una afirmacion que el README publica en negrita o en una linea
    partida se leeria como ausente y el instrumento firmaria un rojo por
    maquetacion. Es la misma normalizacion que declara el testigo de claims de
    los repos.
    """
    t = txt.replace("\u2212", "-").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", t)


def _saltar_a_testigo_local(claim, repo):
    """Comprueba que el salto tenga testigo. Sin testigo, es un verde oculto."""
    local = claim["portador_local"]
    if not isinstance(local, str) or not local.strip():
        raise Falla(
            "SCHEMA_VIOLADO", "portador_local debe ser una ruta no vacia, no %r" % local
        )
    for pieza, clave in ((local, "portador_local"), (claim["dato"], "dato")):
        if not os.path.isfile(os.path.join(repo, pieza)):
            raise Falla(
                "PARSER_ESPECIFICO_AUSENTE",
                "%s %r no existe: saltarse el claim sin testigo que lo mida es "
                "un verde oculto" % (clave, pieza),
            )
    return local


def _firmar(claim, repo, valor, afirmado, probadas, modo, declarado=None, solvers=None):
    """Coteja la prosa y firma el claim. Comun a los cuatro modos.

    `modo` es el MECANISMO que el instrumento corrio (expresion, derivacion,
    testigo, testigo_permanente, especifico); `declarado` es lo que el claim
    declaro. Se firman los dos: un claim de expresion que declara `derivacion`
    deriva (por eso declara) y no miente al decir como lo hace.
    """
    ruta_prosa = os.path.join(repo, claim["prosa"])
    if not os.path.isfile(ruta_prosa):
        raise Falla("README_DESALINEADO", "la prosa no existe: %s" % claim["prosa"])
    with open(ruta_prosa, encoding="utf-8") as fh:
        prosa = _prosa_comparable(fh.read())
    if claim["afirma"] not in prosa:
        raise Falla(
            "README_DESALINEADO",
            "la afirmacion %r no aparece en %s: el dato puede ser cierto y la "
            "prosa no decirlo" % (claim["afirma"], claim["prosa"]),
        )
    firma = {
        "id": claim["id"],
        "deriva": claim["deriva"],
        "derivado": valor,
        "afirmado": afirmado,
        "polaridad": claim["polaridad"],
        "mutaciones": probadas,
        "modo": modo,
    }
    if declarado is not None:
        firma["declarado"] = declarado
    if solvers is not None:
        # El cotejo del selector se lee en la firma: «no mordio» y «no corrio»
        # no pueden parecerse. Sin esto, un `solvers` cableado y uno decorativo
        # firmarian lo mismo.
        firma["solvers"] = solvers
    if modo == "testigo_permanente":
        firma["motivo"] = claim["motivo"].strip()
    return firma


def _declaracion(claim):
    """Lee el `modo` que el claim DECLARA, si lo hay, y lo valida.

    `modo` era un campo solo de SALIDA (inferido del portador) y una clave de mas
    se ignoraba en silencio: escribir `"modo": "testigo_permanente"` sin tocar
    este archivo habria sido un campo decorativo — la misma familia del verde que
    no muerde. Ahora una declaracion muerde.
    """
    declarado = claim.get("modo")
    motivo = claim.get("motivo")
    if declarado is None:
        if motivo is not None:
            raise Falla(
                "MOTIVO_HUERFANO",
                "el claim %r trae `motivo` sin declarar modo=testigo_permanente: "
                "un motivo suelto no justifica nada" % claim["id"],
            )
        if "portador_local" in claim:
            # Excepcion estructural: quien lo mide ya esta dicho por
            # `portador_local`, y declarar modo ahi es contradecirlo.
            return None
        raise Falla(
            "MODO_NO_DECLARADO",
            "el claim %r no declara `modo` (%s): el modo no se infiere en "
            "silencio. Un claim que no dice como se mide es un verde sin dueno"
            % (claim["id"], list(MODOS_DECLARADOS)),
        )
    if declarado not in MODOS_DECLARADOS:
        raise Falla(
            "MODO_NO_DECLARADO",
            "el claim %r declara modo=%r, fuera de %s"
            % (claim["id"], declarado, list(MODOS_DECLARADOS)),
        )
    if declarado == "testigo_permanente":
        if not isinstance(motivo, str) or not motivo.strip():
            raise Falla(
                "MOTIVO_AUSENTE",
                "el claim %r se declara testigo_permanente y no dice por que: sin "
                "motivo es un testigo disfrazado" % claim["id"],
            )
    elif motivo is not None:
        raise Falla(
            "MOTIVO_HUERFANO",
            "el claim %r declara modo=derivacion y trae `motivo`: deriva, no hay "
            "salto que justificar" % claim["id"],
        )
    return declarado


def _cotejar(claim, doc, valor, afirmado, declarado):
    """Aplica la polaridad, y hace morder la declaracion del claim.

    `testigo_permanente` se firma solo si la derivacion NO cierra hoy: si
    cerrara, el claim era derivable y el motivo sobraba. `derivacion` exige que
    el portador devuelva cifra: declarar derivacion sobre un testigo es una
    promesa incumplida. Un solo motivo no basta para tapar un rojo: solo el
    `README_DESALINEADO` (el valor se movio) se lee como permanencia; un portador
    roto o discrepo sigue siendo rojo.
    """
    if valor is None:
        if declarado == "derivacion":
            raise Falla(
                "MODO_CONTRADICHO",
                "el claim %r declara modo=derivacion y su portador no devuelve "
                "cifra: solo asevera" % claim["id"],
            )
        return
    try:
        _comparar(claim, doc, float(valor), afirmado)
    except Falla as e:
        if declarado == "testigo_permanente" and e.codigo == "README_DESALINEADO":
            return
        raise
    if declarado == "testigo_permanente":
        raise Falla(
            "DERIVACION_POSIBLE",
            "el claim %r se declara testigo_permanente y su derivacion SI cierra "
            "(derivado=%r, afirmado=%r): el motivo sobra" % (claim["id"], valor, afirmado),
        )


def _verificar_claim(claim, repo, solvers=None):
    if not isinstance(claim, dict):
        raise Falla("SCHEMA_VIOLADO", "el claim no es un objeto JSON")
    faltan = [k for k in OBLIGATORIOS if k not in claim]
    if faltan:
        raise Falla("SCHEMA_VIOLADO", "claves ausentes: %s" % faltan)
    if claim["polaridad"] not in POLARIDADES:
        raise Falla(
            "POLARIDAD_NO_DECLARADA",
            "%r no esta en %s" % (claim["polaridad"], list(POLARIDADES)),
        )
    declarado = _declaracion(claim)
    cotejo = None

    if "portador_local" in claim:
        if declarado is not None:
            raise Falla(
                "MODO_CONTRADICHO",
                "el claim %r declara modo=%r y ademas portador_local: quien lo "
                "mide ya esta dicho, no hay nada que declarar"
                % (claim["id"], declarado),
            )
        local = _saltar_a_testigo_local(claim, repo)
        print(
            "[CLAIMS] %-30s SKIP: PARSER_ESPECIFICO %s -> lo mide %s"
            % (os.path.basename(os.path.abspath(repo)), claim["id"], local)
        )
        return _firmar(claim, repo, None, None, 0, "especifico", declarado)

    ruta_dato = os.path.join(repo, claim["dato"])
    if not os.path.isfile(ruta_dato):
        raise Falla("VALOR_NO_DERIVABLE", "el dato no existe: %s" % claim["dato"])

    ref = _parser_ref(claim["deriva"])
    if ref is None:
        try:
            with open(ruta_dato, encoding="utf-8") as fh:
                doc = json.load(fh)
        except ValueError as e:
            raise Falla("VALOR_NO_DERIVABLE", "el dato no parsea: %s" % e)

        valor = _evaluar(claim["deriva"], doc)
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise Falla(
                "VALOR_NO_DERIVABLE",
                "%r devuelve %s, no un numero"
                % (claim["deriva"], type(valor).__name__),
            )
        probadas = _control_de_ceguera(claim, doc, valor)

        afirmado = _num(claim["afirma"])
        _cotejar(claim, doc, valor, afirmado, declarado)
        modo = "expresion"
    else:
        doc = None
        cotejo = _cotejar_solvers(claim, solvers)
        valor, modo = _derivar_por_portador(claim, repo, ref[0], ref[1])
        probadas = 0
        if modo == "testigo" and declarado is None:
            # El portador porta la comparacion; aqui solo se coteja que la
            # prosa diga lo que el claim dice que dice. Desde que `modo` es
            # obligatorio esta rama es inalcanzable por la via normal: queda
            # como guarda de que un testigo sin declaracion no se coteje.
            afirmado = None
        else:
            if claim["polaridad"] == "complemento":
                raise Falla(
                    "SCHEMA_VIOLADO",
                    "complemento exige una expresion: `total` no se evalua "
                    "sobre un portador",
                )
            afirmado = _num(claim["afirma"])
            _cotejar(claim, doc, valor, afirmado, declarado)

    if declarado == "testigo_permanente":
        modo = declarado
    return _firmar(
        claim, repo, valor, afirmado, probadas, modo, declarado, solvers=cotejo
    )


def _leer_contrato(repo):
    """(huella, claims, solvers, datos) del `.github/claims.json` del repo.

    Una sola puerta al contrato: la verificacion normal y el falsador del `dato`
    leen el mismo vocabulario. Dos lectores del mismo archivo serian dos
    verdades, y la segunda acabaria decorando.
    """
    ruta = os.path.join(repo, ".github", "claims.json")
    if not os.path.isfile(ruta):
        raise Falla(
            "SCHEMA_INCOMPLETO",
            "no hay .github/claims.json: el repo no declara que afirma su prosa",
        )
    try:
        with open(ruta, encoding="utf-8") as fh:
            doc = json.load(fh)
    except ValueError as e:
        raise Falla("SCHEMA_VIOLADO", "claims.json no parsea: %s" % e)
    if not isinstance(doc, dict):
        raise Falla("SCHEMA_VIOLADO", "claims.json no es un objeto JSON")

    estado = doc.get("estado")
    if estado == "SIN_DATO_MECANIZABLE":
        motivo = doc.get("motivo") or "sin motivo declarado"
        raise Falla("SIN_DATO_MECANIZABLE", motivo)
    if estado is not None:
        raise Falla("SCHEMA_VIOLADO", "estado %r no esta en el vocabulario" % estado)
    if not doc.get("huella"):
        raise Falla("SCHEMA_VIOLADO", "falta la huella del contrato")
    claims = doc.get("claims")
    if not isinstance(claims, list) or not claims:
        raise Falla("SCHEMA_VIOLADO", "claims debe ser una lista no vacia")
    solvers = doc.get("solvers")
    if solvers is not None and (
        not isinstance(solvers, list)
        or not solvers
        or not all(isinstance(s, str) and s.strip() for s in solvers)
    ):
        raise Falla(
            "SCHEMA_VIOLADO",
            "solvers debe ser una lista no vacia de nombres: %r no coteja nada"
            % (solvers,),
        )
    datos = doc.get("datos")
    if datos is not None:
        if not isinstance(datos, dict):
            raise Falla(
                "SCHEMA_VIOLADO",
                "datos debe ser un mapa `ruta -> sha256[:16]`: %r no ancla nada"
                % (datos,),
            )
        for rel, digest in sorted(datos.items()):
            if not isinstance(rel, str) or not rel.strip():
                raise Falla("SCHEMA_VIOLADO", "datos tiene una ruta vacia")
            if not isinstance(digest, str) or not re.match(r"^[0-9a-f]{16}$", digest):
                raise Falla(
                    "SCHEMA_VIOLADO",
                    "el ancla de %r es %r, no un sha256[:16] en hexadecimal: un "
                    "digest que no se puede comparar es un ancla decorativa"
                    % (rel, digest),
                )
    return doc["huella"], claims, solvers, datos


def verificar_repo(repo):
    huella, claims, solvers, datos = _leer_contrato(repo)
    ancla = _cotejar_datos(repo, claims, datos)
    ley = _exigir_solvers(repo, claims, solvers)
    try:
        firmados = [_verificar_claim(c, repo, solvers) for c in claims]
    except Falla as e:
        e.solvers = ley
        raise
    return {
        "huella": huella,
        "claims": firmados,
        "solvers": ley,
        "datos": ancla,
        "veredicto": _veredicto_repo(firmados),
    }


def _veredicto_repo(claims):
    """Ni el escalado al testigo local ni el permanente declarado firman «sano»."""
    if any(c["modo"] == "especifico" for c in claims):
        return "ESPERANDO_TESTIGO_LOCAL"
    if any(c["modo"] == "testigo_permanente" for c in claims):
        return "CLAIMS_TESTIGO_PERMANENTE"
    return "CLAIMS_SANO"


def _rc(rojos, esperando):
    """Tres estados: un fallo manda; sin fallos, un escalado no es verde."""
    if rojos:
        return 1
    return RC_ESPERANDO_TESTIGO_LOCAL if esperando else 0


# --------------------------------------------------------------------------
# HUELLA-VERIFY-CLAIMS-ANCLA-DATO-20261021 · el ancla de bytes
# --------------------------------------------------------------------------
# El verificador cotejaba que el `dato` EXISTIERA. Existir no es ser el mismo:
# editar el crudo y no re-sellar el claim pasaba en silencio, y una cifra
# declarada sobre un archivo que ya cambio es una cifra sobre otro archivo.
#
# El ancla vive en la RAIZ del contrato (`datos`: ruta -> sha256[:16]) y no en
# cada claim, por medicion (`ENMIENDA_01_...` §2): `red-green-sandbox` habria
# declarado el mismo digest 10 veces, y un cambio de `sandbox.py` obligaria a
# tocar 10 sitios para decir una sola cosa. Dos verdades del mismo archivo
# divergen; la segunda acaba decorando.
#
# La ausencia se declara, nunca es no-op: `DATO_SIN_ANCLA` rc 1. Un campo que
# solo coteja cuando esta presente es la decorativa nº 12 con otro nombre.
#
# Frontera: el ancla mide IDENTIDAD DE BYTES, no aritmetica. Un portador que
# lee el archivo y calcula mal pasa el ancla y el verificador (si el declarado
# se corrompio junto con la computacion). Lo que sube es el costo de la edicion
# silenciosa, no la garantia de la cuenta.


def _es_datum_de_datos(relativa):
    """¿El datum es un archivo de DATOS y no codigo?

    La sonda de digitos solo puede firmar `DIGITO_MUERTO` sobre datos: en un
    `.py` la cifra de un portador es un RECUENTO estructural, legitimamente
    insensible a los digitos del fuente (medido: `sellos_cw` 0 de 33 constantes).
    """
    return os.path.splitext(relativa)[1].lower() not in (".py", ".pyi", ".pyc")


def _cotejar_datos(repo, claims, datos):
    """El ancla de bytes: cada `dato` que un claim usa vive en la raiz `datos`.

    Un hash por archivo, no por claim (24 claims del portafolio sobre 6
    archivos): el mismo archivo se mide una vez y una edicion del crudo se
    re-sella en un sitio. Un `dato` que no existe en disco NO se acusa aqui:
    lo nombra `VALOR_NO_DERIVABLE` en su claim, que es el diagnostico
    especifico, y un sha256 de lo que no hay no se puede medir.
    """
    requeridos = sorted(
        {c["dato"] for c in claims if isinstance(c, dict) and c.get("dato")}
    )
    if not isinstance(datos, dict):
        raise Falla(
            "DATO_SIN_ANCLA",
            "el contrato no declara el mapa raiz `datos`: %d `dato` distinto(s) "
            "quedarian atados a un archivo que nadie fijo (%s)"
            % (len(requeridos), ", ".join(requeridos)),
        )
    # El ancla cubre lo que EXISTE. Un `dato` que no esta en disco no es un
    # ancla que falta: es un archivo ausente, y su diagnostico especifico es
    # `VALOR_NO_DERIVABLE` en el claim. Un sha256 de lo que no hay no se mide.
    en_disco = [
        rel for rel in requeridos if os.path.isfile(os.path.join(repo, rel))
    ]
    faltan = [rel for rel in en_disco if rel not in datos]
    if faltan:
        raise Falla(
            "DATO_SIN_ANCLA",
            "%d `dato` sin entrada en la raiz `datos`: %s — el claim afirma "
            "sobre un archivo que el contrato no fijo"
            % (len(faltan), ", ".join(faltan)),
        )
    cotejados = {}
    for rel in en_disco:
        ruta = os.path.join(repo, rel)
        with open(ruta, "rb") as fh:
            real = hashlib.sha256(fh.read()).hexdigest()[:16]
        if real != datos[rel]:
            raise Falla(
                "MISMATCH_DATO",
                "el `dato` %r cambio: declarado %s, medido %s — la cifra afirma "
                "sobre un archivo que ya no es el que se declaro"
                % (rel, datos[rel], real),
            )
        cotejados[rel] = real
    # Una entrada que ningun claim usa es memoria, no error: se imprime
    # (`ANCLA_HUERFANA`, rc 0), porque un ancla que nadie lee es la decorativa
    # nº 14 esperando turno.
    huerfanas = sorted(set(datos) - set(requeridos))
    return {
        "declaradas": len(datos),
        "anclados": len(cotejados),
        "huerfanas": huerfanas,
        "veredicto": "COTEJADO",
    }


# --------------------------------------------------------------------------
# HUELLA-VERIFY-CLAIMS-FALSADOR-PHANTOM-DATO-20261021 · la fisica del `dato`
# --------------------------------------------------------------------------
# El dialecto `parser:` cotejaba que el `dato` existiera y nada mas. La sonda es
# vaciar (0 bytes: el archivo sigue existiendo) y no borrar, porque borrado el
# que se queja es la guarda `isfile` y el fantasma pasa por honesto.

VEREDICTOS_DEL_FALSADOR = (
    "PARSER_LEE_DATO",
    "PHANTOM_DATO",
    "SIN_BASELINE",
    "DATUM_NO_NEUTRALIZABLE",
    "EXENTO_TESTIGO",
    "EXENTO_ESPECIFICO",
    "FUERA_DE_ALCANCE_EXPRESION",
    "DATUM_ES_PORTADOR",
)
# Los tres que hacen rojo el acto.
GRAVES_DEL_FALSADOR = ("PHANTOM_DATO", "SIN_BASELINE", "DATUM_NO_NEUTRALIZABLE")
MEDIBLES_DEL_FALSADOR = ("PARSER_LEE_DATO",) + GRAVES_DEL_FALSADOR
EXENTOS_DEL_FALSADOR = (
    "EXENTO_TESTIGO",
    "EXENTO_ESPECIFICO",
    "FUERA_DE_ALCANCE_EXPRESION",
    "DATUM_ES_PORTADOR",
)


def _mismo_archivo(repo, una, otra):
    """¿Las dos rutas de un claim resuelven al mismo archivo del repo?"""
    return os.path.realpath(os.path.join(repo, una)) == os.path.realpath(
        os.path.join(repo, otra)
    )


def _vaciar_dato(repo, relativa):
    """Trunca el `dato` a 0 bytes dentro de la copia. Devuelve None o el motivo.

    Vaciado, no borrado: el archivo sigue existiendo y la guarda `isfile` del
    camino normal abre paso al portador. Borrado, el que se queja es la guarda y
    un portador fantasma pasaria por honesto (medido en `rf-signal-integrity`).
    """
    raiz = os.path.realpath(repo)
    ruta = os.path.realpath(os.path.join(repo, relativa))
    if not ruta.startswith(raiz + os.sep):
        return "el dato %r apunta fuera de la copia" % relativa
    if not os.path.isfile(ruta):
        return "el dato %r no es un archivo regular" % relativa
    try:
        with open(ruta, "w", encoding="utf-8"):
            pass
    except OSError as e:
        return "el dato %r no se puede vaciar: %s" % (relativa, type(e).__name__)
    return None


def _seleccionar_medibles(repo, claims):
    """(firmas exentas, claims que un falsador puede tocar).

    Una sola tabla para el falsador del fantasma y para la sonda de digitos:
    dos selecciones distintas del mismo portafolio serian dos verdades, y la
    segunda acabaria contando exentos como medibles.
    """
    firmas = []
    medibles = []
    for claim in claims:
        cid = claim.get("id")
        if "portador_local" in claim:
            firmas.append({"id": cid, "veredicto": "EXENTO_ESPECIFICO"})
            continue
        ref = _parser_ref(claim.get("deriva"))
        if ref is None:
            firmas.append({"id": cid, "veredicto": "FUERA_DE_ALCANCE_EXPRESION"})
            continue
        if claim.get("modo") == "testigo_permanente":
            firmas.append({"id": cid, "veredicto": "EXENTO_TESTIGO"})
            continue
        if _mismo_archivo(repo, ref[0], claim["dato"]):
            # Tocar el datum borra o corrompe el portador, no su fuente: el
            # veredicto seria vacuamente `PARSER_LEE_DATO`, la misma sonda que
            # borrar. Se declara, se cuenta aparte y no se suma al verde.
            firmas.append({"id": cid, "veredicto": "DATUM_ES_PORTADOR"})
            continue
        medibles.append(claim)
    return firmas, medibles


def _olvidar_modulos(*raices):
    """Saca de `sys.modules` todo modulo cargado desde esas raices.

    Medido: `_portadores_del_repo` importa los portadores del arbol REAL para
    contar solvers y deja en `sys.modules` los modulos que ellos importan
    (`test_canonical_surface` en `red-green-sandbox`). Desde ahi, el portador de
    la COPIA resuelve su propio `import` contra el modulo del arbol real y el
    falsador mide el repo intacto creyendo medir la copia: firmo 7
    `PHANTOM_DATO` sobre claims que SI leen su `dato`. Medido en HEAD sin este
    cambio (o sea: no lo trajo el ancla, lo trajo `SOLVERS-MANDATORIO`), y el
    mismo cache haria invisible cada mutacion de digito en la sonda.
    """
    reales = tuple(os.path.abspath(r) + os.sep for r in raices)
    for nombre in list(sys.modules):
        fichero = getattr(sys.modules.get(nombre), "__file__", None)
        if fichero and fichero.startswith(reales):
            sys.modules.pop(nombre, None)


def _falsar_repo(repo):
    """Barrido del fantasma sobre UN repo: ¿la cifra sale del `dato`?

    Nunca muta el repo medido: copia, mide el baseline sobre la copia intacta,
    vacia los `dato` de los medibles en la copia y barre claim por claim en su
    propio `try`. El bucle de `main` aborta en el primer rojo y certificaria uno
    de ocho (medido en `red-green-sandbox`).
    """
    _, claims, solvers, _datos = _leer_contrato(repo)
    _exigir_solvers(repo, claims, solvers)
    _olvidar_modulos(repo)
    firmas, medibles = _seleccionar_medibles(repo, claims)
    if not medibles:
        return firmas

    copia = tempfile.mkdtemp(prefix="falsador_dato_")
    try:
        destino = os.path.join(copia, "repo")
        shutil.copytree(
            repo, destino, ignore=shutil.ignore_patterns(".git", "__pycache__")
        )
        base = {}
        for claim in medibles:
            _olvidar_modulos(destino)
            try:
                firma = _verificar_claim(claim, destino, solvers)
            except Falla:
                base[claim["id"]] = (False, None)
                continue
            valor = firma.get("derivado")
            base[claim["id"]] = (valor is not None, valor)

        cegados = {}
        for claim in medibles:
            cegados[claim["id"]] = _vaciar_dato(destino, claim["dato"])

        for claim in medibles:
            cid = claim["id"]
            if cegados[cid] is not None:
                firmas.append(
                    {
                        "id": cid,
                        "veredicto": "DATUM_NO_NEUTRALIZABLE",
                        "codigo": "DATUM_NO_NEUTRALIZABLE",
                        "detalle": cegados[cid],
                    }
                )
                continue
            verde, valor_base = base[cid]
            if not verde:
                firmas.append({"id": cid, "veredicto": "SIN_BASELINE"})
                continue
            _olvidar_modulos(destino)
            try:
                firma = _verificar_claim(claim, destino, solvers)
            except Falla as e:
                firmas.append(
                    {
                        "id": cid,
                        "veredicto": "PARSER_LEE_DATO",
                        "codigo": e.codigo,
                        "baseline": valor_base,
                    }
                )
                continue
            derivado = firma.get("derivado")
            firma_nueva = {
                "id": cid,
                "derivado": derivado,
                "baseline": valor_base,
            }
            if derivado is not None and derivado == valor_base:
                firma_nueva["veredicto"] = "PHANTOM_DATO"
            else:
                firma_nueva["veredicto"] = "PARSER_LEE_DATO"
            firmas.append(firma_nueva)
    finally:
        shutil.rmtree(copia, ignore_errors=True)
    return firmas


def _veredicto_falsador(firmas):
    """El peor veredicto del repo: los graves primero, el que lee despues."""
    vistos = [f["veredicto"] for f in firmas]
    for grave in GRAVES_DEL_FALSADOR:
        if grave in vistos:
            return grave
    if "PARSER_LEE_DATO" in vistos:
        return "PARSER_LEE_DATO"
    return "SIN_CLAIMS_MEDIBLES"


def _detalle_falsador(firma):
    """Detalle sin rutas absolutas: `--json` x2 tiene que dar `cmp` identico."""
    partes = []
    if "codigo" in firma:
        partes.append("codigo=%s" % firma["codigo"])
    if "derivado" in firma:
        partes.append("derivado=%r" % firma["derivado"])
    if "baseline" in firma:
        partes.append("baseline=%r" % firma["baseline"])
    if "detalle" in firma:
        partes.append(firma["detalle"])
    return " · ".join(partes) or "sin cifra que mover"


# --------------------------------------------------------------------------
# HUELLA-VERIFY-CLAIMS-SONDA-DIGITOS-20261021 · la sonda, no el falsador
# --------------------------------------------------------------------------
# El acto anterior probo DEPENDENCIA: el portador abre su `dato`. Falta
# CORRECCION: que la cifra sea funcion del CONTENIDO. La Opcion C dictada
# (mutar 1 byte y esperar que el derivado cambie) midio muerta antes de
# escribirse: en un datum correcto el 98,4 % de los sitios son inertes (rf: 4
# de 901 digitos mueven la cifra; plasma `sellos_cw`: 0 de 33).
#
# Por eso esto es SONDA y no falsador, y su regla de rojo es estrecha:
#
#   MUEVE   -> certifica causalidad (la cifra es funcion de ese sitio).
#   ROMPE   -> certifica dependencia debil, ambigua (un aserto interno del
#              solver rompe sin que la cifra derive de ese literal).
#   SILENCIO-> no prueba nada. Solo un barrido EXHAUSTIVO convierte «cero
#              sitios vivos» en una afirmacion; con presupuesto se declara
#              `PODER_INSUFICIENTE` (rc 0): el instrumento no midio y el claim
#              no queda acusado.
#
# Solo `DIGITO_MUERTO` (datum de datos, barrido completo, 0 mueven, 0 rompen)
# y `SONDA_SIN_BASELINE` firman rojo. Sobre un `.py` el mismo resultado se
# declara `SIN_DIGITO_VIVO`: deuda, no verde y no rojo.
#
# Presupuesto en MUTACIONES, nunca en segundos: un tope temporal haria el
# veredicto dependiente de la maquina y romperia `--json` x2 -> cmp.
# Frontera: la sonda NO coteja el ancla — mutar un digito cambia el sha256 del
# archivo, y con el ancla vivo todo barrido seria `MISMATCH_DATO`.

VEREDICTOS_DE_LA_SONDA = (
    "DIGITO_VIVO",
    "SOLO_ROMPE",
    "DIGITO_MUERTO",
    "SIN_DIGITO_VIVO",
    "PODER_INSUFICIENTE",
    "SIN_DIGITOS",
    "SONDA_SIN_BASELINE",
    "DATUM_ES_PORTADOR",
    "EXENTO_TESTIGO",
    "EXENTO_ESPECIFICO",
    "FUERA_DE_ALCANCE_EXPRESION",
)
GRAVES_DE_LA_SONDA = ("DIGITO_MUERTO", "SONDA_SIN_BASELINE")
EXENTOS_DE_LA_SONDA = (
    "DATUM_ES_PORTADOR",
    "EXENTO_TESTIGO",
    "EXENTO_ESPECIFICO",
    "FUERA_DE_ALCANCE_EXPRESION",
)
# Presupuesto por defecto, en mutaciones por claim. Medido: rf cuesta ~7 ms por
# mutacion y su barrido completo son 6 s; plasma cuesta ~6 s por corrida y su
# barrido completo serian ~28 h. Con 8 el peor caso del portafolio son minutos,
# y el barrido completo se pide con `--presupuesto todo` sabiendo lo que cuesta.
PRESUPUESTO_POR_CLAIM = 8


def _sitios_de_digitos(bytes_del_dato):
    """Posiciones de digito ASCII. Un sitio = un DIGITO, no un literal.

    Granularidad declarada: es la que midio el pre-registro (rf: 901 digitos,
    4 vivos). Un barrido por literal numerico cuenta otro denominador y
    publicaria un poder que no es el que se midio.
    """
    return [i for i, b in enumerate(bytes_del_dato) if 48 <= b <= 57]


def _mutar_digito(original, pos):
    """El byte de `pos` como OTRO digito: mismo largo, mismos offsets."""
    nuevo = (original[pos] - 48 + 1) % 10 + 48
    return original[:pos] + bytes([nuevo]) + original[pos + 1 :]


def _sonda_claim(claim, destino, solvers, presupuesto):
    """Barre los digitos del `dato` de UN claim. Devuelve su firma."""
    cid = claim.get("id")
    _olvidar_modulos(destino)
    try:
        firma = _verificar_claim(claim, destino, solvers)
    except Falla as e:
        return {
            "id": cid,
            "veredicto": "SONDA_SIN_BASELINE",
            "detalle": "baseline %s: el rojo no seria de la sonda" % e.codigo,
        }
    base = firma.get("derivado")
    rel = claim["dato"]
    ruta = os.path.realpath(os.path.join(destino, rel))
    raiz = os.path.realpath(destino)
    if not ruta.startswith(raiz + os.sep):
        return {
            "id": cid,
            "veredicto": "SONDA_SIN_BASELINE",
            "detalle": "el dato %r apunta fuera de la copia" % rel,
        }
    with open(ruta, "rb") as fh:
        original = fh.read()
    sitios = _sitios_de_digitos(original)
    if not sitios:
        return {
            "id": cid,
            "veredicto": "SIN_DIGITOS",
            "detalle": "el datum no tiene un digito: no hay canal que mutar",
        }
    tope = len(sitios) if presupuesto is None else min(presupuesto, len(sitios))
    vivos = rompen = 0
    posiciones = []
    for pos in sitios[:tope]:
        with open(ruta, "wb") as fh:
            fh.write(_mutar_digito(original, pos))
        _olvidar_modulos(destino)
        try:
            mutado = _verificar_claim(claim, destino, solvers)
        except Falla as e:
            # `README_DESALINEADO` es como se ve MUEVE desde aqui: la cifra
            # salio del rango declarado. Cualquier otra Falla rompe el datum
            # sin informar de la cifra.
            if e.codigo == "README_DESALINEADO":
                vivos += 1
                if len(posiciones) < 3:
                    posiciones.append(pos)
            else:
                rompen += 1
            continue
        if mutado.get("derivado") != base:
            vivos += 1
            if len(posiciones) < 3:
                posiciones.append(pos)
    with open(ruta, "wb") as fh:
        fh.write(original)

    completo = tope >= len(sitios)
    sonda = {
        "id": cid,
        "dato": rel,
        "sitios": len(sitios),
        "barridos": tope,
        "vivos": vivos,
        "rompen": rompen,
        "completo": completo,
    }
    if posiciones:
        sonda["posiciones"] = posiciones
    if vivos:
        sonda["veredicto"] = "DIGITO_VIVO"
    elif rompen:
        sonda["veredicto"] = "SOLO_ROMPE"
    elif not completo:
        sonda["veredicto"] = "PODER_INSUFICIENTE"
        sonda["detalle"] = (
            "0 vivos en %d de %d sitios: el instrumento no midio, el claim no "
            "esta acusado" % (tope, len(sitios))
        )
    elif _es_datum_de_datos(rel):
        sonda["veredicto"] = "DIGITO_MUERTO"
    else:
        sonda["veredicto"] = "SIN_DIGITO_VIVO"
    return sonda


def _sonda_repo(repo, presupuesto):
    """Una copia por repo, barrido claim por claim: `main` aborta en el primero."""
    _, claims, solvers, _datos = _leer_contrato(repo)
    _exigir_solvers(repo, claims, solvers)
    _olvidar_modulos(repo)
    firmas, medibles = _seleccionar_medibles(repo, claims)
    if not medibles:
        return firmas
    copia = tempfile.mkdtemp(prefix="sonda_digitos_")
    try:
        destino = os.path.join(copia, "repo")
        shutil.copytree(
            repo, destino, ignore=shutil.ignore_patterns(".git", "__pycache__")
        )
        for claim in medibles:
            firmas.append(_sonda_claim(claim, destino, solvers, presupuesto))
    finally:
        shutil.rmtree(copia, ignore_errors=True)
    return firmas


def _detalle_sonda(firma):
    """Detalle sin rutas absolutas ni tiempos: `--json` x2 tiene que dar cmp."""
    partes = []
    if "sitios" in firma:
        partes.append("%d/%d sitios" % (firma["vivos"], firma["sitios"]))
        partes.append("%d barrido(s)" % firma["barridos"])
        partes.append("%d rompe(n)" % firma["rompen"])
    if "posiciones" in firma:
        partes.append("pos=%s" % ",".join(str(p) for p in firma["posiciones"]))
    if "dato" in firma:
        partes.append(firma["dato"])
    if "detalle" in firma:
        partes.append(firma["detalle"])
    return " · ".join(partes) or "sin barrido"


def _sonda(repos, presupuesto, como_json=False):
    """Modo explicito: una copia por repo y un barrido de digitos por claim."""
    salida = {}
    rojos = 0
    for repo in repos:
        nombre = os.path.basename(os.path.abspath(repo))
        try:
            firmas = _sonda_repo(repo, presupuesto)
        except Falla as e:
            salida[nombre] = {"veredicto": e.codigo}
            if e.codigo != "SIN_DATO_MECANIZABLE":
                rojos += 1
            print("[SONDA] %-30s %-24s %s" % (nombre, e.codigo, e.detalle))
            continue
        salida[nombre] = {"claims": firmas}
        for firma in firmas:
            print(
                "[SONDA] %-30s %-26s %-22s %s"
                % (
                    nombre,
                    firma["id"],
                    firma["veredicto"],
                    _detalle_sonda(firma),
                )
            )
            if firma["veredicto"] in GRAVES_DE_LA_SONDA:
                rojos += 1

    conteo = {}
    for valor in salida.values():
        for firma in valor.get("claims", []):
            conteo[firma["veredicto"]] = conteo.get(firma["veredicto"], 0) + 1
    medibles = sum(
        conteo.get(v, 0) for v in VEREDICTOS_DE_LA_SONDA if v not in EXENTOS_DE_LA_SONDA
    )
    exentos = sum(conteo.get(v, 0) for v in EXENTOS_DE_LA_SONDA)
    print(
        "SONDA: %d repo(s) · %d medible(s) · %d DIGITO_VIVO · %d SOLO_ROMPE · "
        "%d DIGITO_MUERTO · %d SIN_DIGITO_VIVO · %d PODER_INSUFICIENTE · "
        "%d SIN_DIGITOS · %d SONDA_SIN_BASELINE · %d exento(s) · presupuesto=%s"
        % (
            len(salida),
            medibles,
            conteo.get("DIGITO_VIVO", 0),
            conteo.get("SOLO_ROMPE", 0),
            conteo.get("DIGITO_MUERTO", 0),
            conteo.get("SIN_DIGITO_VIVO", 0),
            conteo.get("PODER_INSUFICIENTE", 0),
            conteo.get("SIN_DIGITOS", 0),
            conteo.get("SONDA_SIN_BASELINE", 0),
            exentos,
            "todo" if presupuesto is None else presupuesto,
        )
    )
    if como_json:
        print("## JSON")
        print(json.dumps(salida, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if rojos else 0


def _falsador(repos, como_json=False):
    """Modo explicito: una copia por repo y una corrida completa de portadores."""
    salida = {}
    rojos = 0
    for repo in repos:
        nombre = os.path.basename(os.path.abspath(repo))
        try:
            firmas = _falsar_repo(repo)
        except Falla as e:
            salida[nombre] = {"veredicto": e.codigo}
            if e.codigo == "SIN_DATO_MECANIZABLE":
                print(
                    "[FALSADOR] %-30s %-26s %s"
                    % (nombre, "SIN_DATO_MECANIZABLE", e.detalle)
                )
                continue
            rojos += 1
            print("[FALSADOR] %-30s %-26s %s" % (nombre, e.codigo, e.detalle))
            continue
        veredicto = _veredicto_falsador(firmas)
        salida[nombre] = {"veredicto": veredicto, "claims": firmas}
        if veredicto in GRAVES_DEL_FALSADOR:
            rojos += 1
        for firma in firmas:
            print(
                "[FALSADOR] %-30s %-26s %-24s %s"
                % (
                    nombre,
                    firma["id"],
                    firma["veredicto"],
                    _detalle_falsador(firma),
                )
            )

    conteo = {}
    for valor in salida.values():
        for firma in valor.get("claims", []):
            conteo[firma["veredicto"]] = conteo.get(firma["veredicto"], 0) + 1
    medibles = sum(conteo.get(v, 0) for v in MEDIBLES_DEL_FALSADOR)
    exentos = sum(conteo.get(v, 0) for v in EXENTOS_DEL_FALSADOR)
    print(
        "FALSADOR: %d repo(s) · %d medible(s) · %d PARSER_LEE_DATO · "
        "%d PHANTOM_DATO · %d SIN_BASELINE · %d DATUM_NO_NEUTRALIZABLE · "
        "%d exento(s) (testigo=%d · especifico=%d · expresion=%d · "
        "dato_portador=%d)"
        % (
            len(salida),
            medibles,
            conteo.get("PARSER_LEE_DATO", 0),
            conteo.get("PHANTOM_DATO", 0),
            conteo.get("SIN_BASELINE", 0),
            conteo.get("DATUM_NO_NEUTRALIZABLE", 0),
            exentos,
            conteo.get("EXENTO_TESTIGO", 0),
            conteo.get("EXENTO_ESPECIFICO", 0),
            conteo.get("FUERA_DE_ALCANCE_EXPRESION", 0),
            conteo.get("DATUM_ES_PORTADOR", 0),
        )
    )
    if como_json:
        print("## JSON")
        print(json.dumps(salida, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if rojos else 0


def _argumentos(resto):
    """Separa `--presupuesto N|todo` de las rutas: su valor no es un repo.

    El filtro de `main` descarta lo que empieza por `--`, y con esa regla el
    entero de `--presupuesto` caia en la lista de repos y se leia como ruta
    inexistente. Un presupuesto que se confunde con un repo es un instrumento
    que no arranca.
    """
    limpio, presupuesto, i = [], PRESUPUESTO_POR_CLAIM, 0
    while i < len(resto):
        actual = resto[i]
        if actual == "--presupuesto":
            if i + 1 >= len(resto):
                return resto, None, "uso: --presupuesto N | --presupuesto todo"
            valor = resto[i + 1]
            if valor == "todo":
                presupuesto = None
            elif valor.isdigit():
                presupuesto = int(valor)
            else:
                return (
                    resto,
                    None,
                    "uso: --presupuesto N | --presupuesto todo (en mutaciones, "
                    "nunca en segundos)",
                )
            i += 2
            continue
        limpio.append(actual)
        i += 1
    return limpio, presupuesto, None


def _imprimir_orfandad(nombre, ley):
    """Declara —sin arrestar— el solver declarado que no es raiz de un selector.

    No es rojo a proposito: un solver servido solo por claims
    `testigo_permanente` queda fuera de las raices (el filtro es
    `modo == derivacion`), y arrestarlo daria falsos positivos legitimos.
    """
    if not ley or not ley.get("sin_selector"):
        return
    print(
        "[CLAIMS] %-30s %-24s sin selector de derivacion: %s (declarado, no coteja)"
        % (nombre, "SOLVERS_DECLARADO_SIN_SELECTOR", ", ".join(ley["sin_selector"]))
    )


def main(argv):
    resto, presupuesto, error = _argumentos(argv[1:])
    if error is not None:
        print(error)
        return 20
    args = [a for a in resto if not a.startswith("--")]
    como_json = "--json" in argv

    if "--autotest" in argv:
        return _autotest()

    if "--sonda-digitos" in argv:
        if not args:
            print(
                "uso: verify_claims.py --sonda-digitos REPO [REPO ...] "
                "[--presupuesto N | --presupuesto todo]\n"
                "     muta cada digito del `dato` de los claims medibles y mide "
                "si la cifra se mueve (sonda de acoplamiento, no de correccion)"
            )
            return 20
        return _sonda(args, presupuesto, como_json)

    if "--falsador-dato" in argv or "--falsador-phantom-dato" in argv:
        if not args:
            print(
                "uso: verify_claims.py --falsador-dato REPO [REPO ...]\n"
                "     copia cada repo y vacia los `dato` de sus claims medibles"
            )
            return 20
        return _falsador(args, como_json)

    if not args:
        print(
            "uso: verify_claims.py REPO [REPO ...] | --json | "
            "--falsador-dato | --sonda-digitos [--presupuesto N|todo] | "
            "--autotest"
        )
        return 20

    salida = {}
    rojos = 0
    for repo in args:
        nombre = os.path.basename(os.path.abspath(repo))
        try:
            r = verificar_repo(repo)
        except Falla as e:
            rojos += 1
            ley = getattr(e, "solvers", None)
            salida[nombre] = {
                "veredicto": e.codigo,
                "detalle": e.detalle,
                "solvers": ley,
            }
            print("[CLAIMS] %-30s %-24s %s" % (nombre, e.codigo, e.detalle))
            _imprimir_orfandad(nombre, ley)
            continue
        salida[nombre] = {
            "veredicto": r["veredicto"],
            "claims": r["claims"],
            "solvers": r["solvers"],
            "datos": r["datos"],
        }
        if r["datos"]["huerfanas"]:
            print(
                "[CLAIMS] %-30s %-24s %s: entradas que ningun claim usa"
                % (nombre, "ANCLA_HUERFANA", ", ".join(r["datos"]["huerfanas"]))
            )
        if r["solvers"]["veredicto"] in ("NO_APLICABLE", "SOLVERS_INNECESARIO"):
            print(
                "[CLAIMS] %-30s %-24s %s"
                % (nombre, r["solvers"]["veredicto"], r["solvers"]["detalle"])
            )
        _imprimir_orfandad(nombre, r["solvers"])
        for c in r["claims"]:
            if c["modo"] == "especifico":
                print(
                    "[CLAIMS] %-30s %-24s %s: lo mide el testigo local del repo"
                    % (nombre, "ESPERANDO_TESTIGO_LOCAL", c["id"])
                )
                continue
            if c["modo"] == "testigo_permanente":
                print(
                    "[CLAIMS] %-30s %-24s %s: NO re-derivado, motivo=%r"
                    % (nombre, "CLAIMS_TESTIGO_PERMANENTE", c["id"], c["motivo"])
                )
                continue
            print(
                "[CLAIMS] %-30s %-24s %s: derivado=%r afirmado=%r (%s, %d "
                "mutacion/es, modo=%s)"
                % (
                    nombre,
                    "CLAIMS_SANO",
                    c["id"],
                    c["derivado"],
                    c["afirmado"],
                    c["polaridad"],
                    c["mutaciones"],
                    c["modo"],
                )
            )
        if r["veredicto"] != "CLAIMS_SANO":
            escalados = [c["id"] for c in r["claims"] if c["modo"] == "especifico"]
            permanentes = [
                c["id"] for c in r["claims"] if c["modo"] == "testigo_permanente"
            ]
            if escalados:
                print(
                    "[CLAIMS] %-30s %-24s %d claim(s) escalado(s): %s"
                    % (nombre, r["veredicto"], len(escalados), ", ".join(escalados))
                )
            if permanentes:
                print(
                    "[CLAIMS] %-30s %-24s %d permanente(s) declarado(s): %s"
                    % (nombre, r["veredicto"], len(permanentes), ", ".join(permanentes))
                )

    sanos = sum(1 for v in salida.values() if v["veredicto"] == "CLAIMS_SANO")
    esperando = sum(
        1 for v in salida.values() if v["veredicto"] == "ESPERANDO_TESTIGO_LOCAL"
    )
    con_permanentes = sum(
        1 for v in salida.values() if v["veredicto"] == "CLAIMS_TESTIGO_PERMANENTE"
    )
    modos = {}
    for v in salida.values():
        for c in v.get("claims", []):
            modos[c["modo"]] = modos.get(c["modo"], 0) + 1
    anclados = sum(
        v.get("datos", {}).get("anclados", 0) for v in salida.values()
    )
    print(
        "CLAIMS: %d repo(s) · %d sano(s) (%d derivados · %d testigos) · "
        "%d con testigo permanente (%d claim/es declarado/s) · "
        "%d esperando testigo local (%d claim/es) · %d con faltante declarado · "
        "%d dato(s) anclado(s)"
        % (
            len(salida),
            sanos,
            modos.get("expresion", 0) + modos.get("derivacion", 0),
            modos.get("testigo", 0),
            con_permanentes,
            modos.get("testigo_permanente", 0),
            esperando,
            modos.get("especifico", 0),
            len(salida) - sanos - esperando - con_permanentes,
            anclados,
        )
    )
    if como_json:
        print("## JSON")
        print(json.dumps(salida, ensure_ascii=False, indent=2, sort_keys=True))
    return _rc(rojos, esperando)


# --------------------------------------------------------------------------
# Autotest: el verificador contra sus propios falsadores
# --------------------------------------------------------------------------

_AUTOTEST_DATO = {"medido": {"residuo": 0.13113286486070153}, "bins": [True, False, False]}
_AUTOTEST_PROSA = "El residuo plano es 13.11 % y no cumplen 2 de 3 bins.\n"


def _anclar(repo):
    """Ancla en la raiz los `dato` que existan en disco (solo autotest).

    El ancla es obligatoria desde HUELLA-VERIFY-CLAIMS-ANCLA-DATO-20261021, y
    una fixture sin mapa pondria en rojo los 48 casos anteriores por
    construccion: la fixture declara lo que la ley exige.
    """
    ruta = os.path.join(repo, ".github", "claims.json")
    with open(ruta, encoding="utf-8") as fh:
        doc = json.load(fh)
    mapa = {}
    for claim in doc["claims"]:
        rel = claim.get("dato")
        fichero = os.path.join(repo, rel) if rel else None
        if fichero and os.path.isfile(fichero):
            with open(fichero, "rb") as fh:
                mapa[rel] = hashlib.sha256(fh.read()).hexdigest()[:16]
    doc["datos"] = mapa
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    return repo


def _editar_datos(repo, cambio):
    """Edita el mapa `datos` de una fixture ya anclada."""
    ruta = os.path.join(repo, ".github", "claims.json")
    with open(ruta, encoding="utf-8") as fh:
        doc = json.load(fh)
    cambio(doc)
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    return repo


def _caso(tmp, nombre, claims):
    repo = os.path.join(tmp, nombre)
    os.makedirs(os.path.join(repo, ".github"))
    os.makedirs(os.path.join(repo, "data"))
    with open(os.path.join(repo, "data", "d.json"), "w", encoding="utf-8") as fh:
        json.dump(_AUTOTEST_DATO, fh)
    with open(os.path.join(repo, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(_AUTOTEST_PROSA)
    with open(os.path.join(repo, ".github", "claims.json"), "w", encoding="utf-8") as fh:
        json.dump({"huella": "HUELLA-AUTOTEST", "claims": claims}, fh)
    return _anclar(repo)


def _claim(**kw):
    base = {
        "id": "A1",
        "afirma": "13.11",
        "dato": "data/d.json",
        "deriva": "dato.medido.residuo * 100",
        "polaridad": "cerca_de",
        "tolerancia": 0.005,
        "prosa": "README.md",
    }
    base.update(kw)
    return base


# Un portador sin parametros NO recibe el solver: lo unico que dice a quien sirve
# es el literal que nombra. Es la forma real de `plasma-ade` (`res("cw")`).
_PORTADOR_DOS_SOLVERS = (
    'def res(nombre):\n'
    '    return {"filas": [1, 2, 3]}\n'
    '\n'
    '\n'
    'def cifras_cw():\n'
    '    return res("cw")\n'
)

# HUELLA-VERIFY-CLAIMS-SOLVERS-MANDATORIO-20261021: dos portadores sin
# parametros que nombran solvers distintos — el caso que la ley caza cuando el
# repo no declara `solvers`. `_PORTADOR_DOCSTRING_SOLVER` es el falsador del
# criterio: su docstring ES un nombre de solver y no debe contar como literal
# del cuerpo, o `N` saldria 2 donde hay 1.
_PORTADOR_DOS_NOMBRES = (
    'def res(nombre):\n'
    '    return {"filas": [1, 2, 3]}\n'
    '\n'
    '\n'
    'def cifras_a():\n'
    '    return res("a")\n'
    '\n'
    '\n'
    'def cifras_b():\n'
    '    return res("b")\n'
)

_PORTADOR_DOCSTRING_SOLVER = (
    'def res(nombre):\n'
    '    return {"filas": [1, 2, 3]}\n'
    '\n'
    '\n'
    'def cifras_b():\n'
    '    """b"""\n'
    '    return res("a")\n'
)

# Control: dos portadores que RECIBEN la raiz como parametro y tres raices. No
# eligen solver, asi que no declaran ninguno y la ley no debe exigirlo.
_PORTADOR_RECIBE = 'def cifra(modo):\n    return {"filas": [1, 2, 3]}\n'

# HUELLA-VERIFY-CLAIMS-FALSADOR-PHANTOM-DATO-20261021: el par que mide las dos
# puertas. `_PORTADOR_LEE` abre su `dato` y se rompe cuando el `dato` se vacia;
# el fantasma devuelve la cifra sin abrir nada. Los dos firman `CLAIMS_SANO` en
# el camino normal — el fantasma tambien, y esa es exactamente la ceguera que el
# falsador nombra.
_PORTADOR_LEE = (
    'import json\n'
    'import os\n'
    '\n'
    '\n'
    'def cifra():\n'
    '    with open(os.path.join(os.path.dirname(__file__), "d.json")) as fh:\n'
    '        doc = json.load(fh)\n'
    '    return doc["medido"]["residuo"] * 100\n'
)

_PORTADORES = {
    # nombre: (codigo, deriva, afirma, veredicto esperado, campos extra)
    # `modo` es obligatorio desde HUELLA-VERIFY-CLAIMS-MODO-OBLIGATORIO-Y-SELECTOR
    # -20261021: cada fixture declara el suyo, y el que no lo trae prueba el
    # silencio que ya no firma.
    "portador_num": (
        "def cifra():\n    return 13.11286486070153\n",
        "parser:data/portador.py::cifra",
        "13.11",
        "CLAIMS_SANO",
        {"modo": "derivacion"},
    ),
    "portador_testigo_sin_modo": (
        "def testigo():\n    assert True\n    return None\n",
        "parser:data/portador.py::testigo",
        "13.11",
        "MODO_NO_DECLARADO",
        {},
    ),
    "permanente_con_motivo": (
        "def cifra():\n    return 99.99\n",
        "parser:data/portador.py::cifra",
        "13.11",
        "CLAIMS_TESTIGO_PERMANENTE",
        {"modo": "testigo_permanente", "motivo": "el crudo publica el valor de despues"},
    ),
    "permanente_sin_motivo": (
        "def cifra():\n    return 99.99\n",
        "parser:data/portador.py::cifra",
        "13.11",
        "MOTIVO_AUSENTE",
        {"modo": "testigo_permanente"},
    ),
    "permanente_motivo_vacio": (
        "def cifra():\n    return 99.99\n",
        "parser:data/portador.py::cifra",
        "13.11",
        "MOTIVO_AUSENTE",
        {"modo": "testigo_permanente", "motivo": "   "},
    ),
    "permanente_que_deriva": (
        "def cifra():\n    return 13.11286486070153\n",
        "parser:data/portador.py::cifra",
        "13.11",
        "DERIVACION_POSIBLE",
        {"modo": "testigo_permanente", "motivo": "declarado por error"},
    ),
    "declarado_derivacion": (
        "def cifra():\n    return 13.11286486070153\n",
        "parser:data/portador.py::cifra",
        "13.11",
        "CLAIMS_SANO",
        {"modo": "derivacion"},
    ),
    "declarado_derivacion_es_testigo": (
        "def testigo():\n    assert True\n    return None\n",
        "parser:data/portador.py::testigo",
        "13.11",
        "MODO_CONTRADICHO",
        {"modo": "derivacion"},
    ),
    "modo_inventado": (
        "def cifra():\n    return 13.11286486070153\n",
        "parser:data/portador.py::cifra",
        "13.11",
        "MODO_NO_DECLARADO",
        {"modo": "sano_por_decreto"},
    ),
    "motivo_huerfano": (
        "def cifra():\n    return 13.11286486070153\n",
        "parser:data/portador.py::cifra",
        "13.11",
        "MOTIVO_HUERFANO",
        {"motivo": "porque si"},
    ),
    "portador_sin_archivo": (
        None,
        "parser:data/no_existe.py::cifra",
        "13.11",
        "PARSER_AUSENTE",
        {"modo": "derivacion"},
    ),
    "portador_sin_funcion": (
        "def otra():\n    return 1.0\n",
        "parser:data/portador.py::cifra",
        "13.11",
        "PARSER_AUSENTE",
        {"modo": "derivacion"},
    ),
    "portador_discrepa": (
        "def cifra():\n    assert False, 'CRUDO_DIVERGENTE'\n    return 1.0\n",
        "parser:data/portador.py::cifra",
        "13.11",
        "PARSER_DISCREPA",
        {"modo": "derivacion"},
    ),
    "portador_no_numerico": (
        "def cifra():\n    return 'trece'\n",
        "parser:data/portador.py::cifra",
        "13.11",
        "PARSER_NO_NUMERICO",
        {"modo": "derivacion"},
    ),
    "portador_valor_movido": (
        "def cifra():\n    return 99.99\n",
        "parser:data/portador.py::cifra",
        "13.11",
        "README_DESALINEADO",
        {"modo": "derivacion"},
    ),
    "portador_forma_rota": (
        "def cifra():\n    return 0.0\n",
        "parser:data/portador.py",
        "13.11",
        "SCHEMA_VIOLADO",
        {"modo": "derivacion"},
    ),
    "portador_ruta_local": (
        "def cifra(modo):\n    return {'filas': [1, 2, 3]}\n",
        "parser:data/portador.py::cifra",
        "3",
        "CLAIMS_SANO",
        {"modo": "derivacion", "ruta": "dato.filas"},
    ),
    "portador_ruta_ausente": (
        "def cifra(modo):\n    return {modo: {'otra': 1}}\n",
        "parser:data/portador.py::cifra",
        "3",
        "RUTA_AUSENTE",
        {"modo": "derivacion", "ruta": "dato.filas"},
    ),
    "selector_propio": (
        _PORTADOR_DOS_SOLVERS,
        "parser:data/portador.py::cifras_cw",
        "3",
        "CLAIMS_SANO",
        {"modo": "derivacion", "ruta": "cw.filas"},
    ),
    "selector_ajeno": (
        _PORTADOR_DOS_SOLVERS,
        "parser:data/portador.py::cifras_cw",
        "3",
        "RUTA_DE_OTRO_SOLVER",
        {"modo": "derivacion", "ruta": "pulso.filas"},
    ),
    # El residuo de `plasma-ade`: `sellos.` no nombra un solver, y el claim esta
    # congelado como permanente con motivo. Su portador es un testigo (devuelve
    # None), asi que la `ruta` no se resuelve: el cotejo de `solvers` no lo toca.
    "solvers_residuo": (
        "def test_pulso_sellos_cierran():\n    assert True\n    return None\n",
        "parser:data/portador.py::test_pulso_sellos_cierran",
        "13.11",
        "CLAIMS_TESTIGO_PERMANENTE",
        {
            "modo": "testigo_permanente",
            "motivo": "crudo congelado del pulso",
            "ruta": "sellos.filas",
        },
    ),
    "falsador_lector": (
        _PORTADOR_LEE,
        "parser:data/portador.py::cifra",
        "13.11",
        "CLAIMS_SANO",
        {"modo": "derivacion"},
    ),
    "falsador_fantasma": (
        "def cifra():\n    return 13.11286486070153\n",
        "parser:data/portador.py::cifra",
        "13.11",
        "CLAIMS_SANO",
        {"modo": "derivacion"},
    ),
}


def _caso_portador(tmp, nombre, repo_nombre=None, solvers=None):
    codigo, deriva, afirma, _, extra = _PORTADORES[nombre]
    campos = {
        "deriva": deriva,
        "afirma": afirma,
        "polaridad": "cerca_de",
        "tolerancia": 0.005,
    }
    campos.update(extra)
    repo = _caso(tmp, repo_nombre or nombre, [_claim(**campos)])
    if codigo is not None:
        with open(os.path.join(repo, "data", "portador.py"), "w", encoding="utf-8") as fh:
            fh.write(codigo)
    if solvers is not None:
        _con_solvers(repo, solvers)
    return repo


def _con_solvers(repo, solvers):
    """Declara `solvers` en la raiz del claims.json de un caso de autotest."""
    ruta = os.path.join(repo, ".github", "claims.json")
    with open(ruta, encoding="utf-8") as fh:
        doc = json.load(fh)
    doc["solvers"] = solvers
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    return repo


_PORTADOR_LEE_DIGITO = (
    'import json\n'
    'import os\n'
    '\n'
    '\n'
    'def cifra():\n'
    '    with open(os.path.join(os.path.dirname(__file__), "digitos.json")) as fh:\n'
    '        doc = json.load(fh)\n'
    '    return float(doc["n"])\n'
)

# El fantasma de la sonda: devuelve la cifra sin abrir nada. Sobre un datum de
# DATOS eso es `DIGITO_MUERTO` rc 1; sobre un `.py` seria `SIN_DIGITO_VIVO`.
_PORTADOR_CONSTANTE = 'def cifra():\n    return 2.0\n'


def _caso_sonda(tmp, nombre, portador, datum, dato="data/digitos.json"):
    """Claim `parser:` sobre un datum de digitos; el ancla se recalcula al final.

    `datum=None` deja el dato en manos del portador (el caso `DATUM_ES_PORTADOR`,
    donde el archivo que se muta ES el portador).
    """
    claims = [
        _claim(
            dato=dato,
            deriva="parser:data/portador.py::cifra",
            afirma="2",
            polaridad="exacto",
            modo="derivacion",
        )
    ]
    repo = _caso(tmp, nombre, claims)
    with open(os.path.join(repo, "data", "portador.py"), "w", encoding="utf-8") as fh:
        fh.write(portador)
    if datum is not None:
        with open(os.path.join(repo, dato), "w", encoding="utf-8") as fh:
            fh.write(datum)
    return _anclar(repo)


def _caso_local(tmp, nombre, con_testigo=True, prosa=None, extra=None):
    """Claim escalado al testigo local: el global no debe ni importar el portador."""
    campos = {
        "deriva": "parser:data/portador_incomponible.py::cifra",
        "portador_local": "tests/test_claims_witness.py",
    }
    campos.update(extra or {})
    repo = _caso(tmp, nombre, [_claim(**campos)])
    if con_testigo:
        os.makedirs(os.path.join(repo, "tests"))
        with open(
            os.path.join(repo, "tests", "test_claims_witness.py"), "w", encoding="utf-8"
        ) as fh:
            fh.write("HUELLA-AUTOTEST-TESTIGO-LOCAL\n")
    if prosa is not None:
        with open(os.path.join(repo, "README.md"), "w", encoding="utf-8") as fh:
            fh.write(prosa)
    return repo


def _autotest():
    esperado = []

    with tempfile.TemporaryDirectory() as tmp:
        esperado.append(("sano", _caso(tmp, "sano", [_claim(modo="derivacion")]), "CLAIMS_SANO"))
        esperado.append(
            (
                "complemento",
                _caso(
                    tmp,
                    "complemento",
                    [
                        _claim(
                            afirma="2",
                            deriva="sum(dato.bins)",
                            polaridad="complemento",
                            total="len(dato.bins)",
                            modo="derivacion",
                        )
                    ],
                ),
                "CLAIMS_SANO",
            )
        )
        esperado.append(
            (
                "desalineado",
                _caso(tmp, "desalineado", [_claim(afirma="99.99", modo="derivacion")]),
                "README_DESALINEADO",
            )
        )
        esperado.append(
            (
                "ciega",
                _caso(tmp, "ciega", [_claim(deriva="1311.3 / 100", modo="derivacion")]),
                "DERIVACION_CIEGA",
            )
        )
        esperado.append(
            (
                "polaridad",
                _caso(tmp, "polaridad", [_claim(polaridad="mas_o_menos", modo="derivacion")]),
                "POLARIDAD_NO_DECLARADA",
            )
        )
        esperado.append(
            (
                "sin_dato",
                _caso(tmp, "sin_dato", [_claim(dato="data/ausente.json", modo="derivacion")]),
                "VALOR_NO_DERIVABLE",
            )
        )
        esperado.append(
            (
                "sin_prosa",
                _caso(tmp, "sin_prosa", [_claim(afirma="0.13", modo="derivacion")]),
                "README_DESALINEADO",
            )
        )
        sin_claims = os.path.join(tmp, "vacio")
        os.makedirs(sin_claims)
        esperado.append(("incompleto", sin_claims, "SCHEMA_INCOMPLETO"))

        for nombre, (_, _, _, quiero, _) in sorted(_PORTADORES.items()):
            esperado.append((nombre, _caso_portador(tmp, nombre), quiero))

        # HUELLA-VERIFY-CLAIMS-SOLVERS-COTEJO-20261021: el cotejo declarado
        # muerde donde hay lista, y no corre donde no la hay.
        esperado.append(
            (
                "solvers_selector_declarado",
                _caso_portador(
                    tmp, "selector_propio", "solvers_declarado", ["cw", "pulso"]
                ),
                "CLAIMS_SANO",
            )
        )
        esperado.append(
            (
                "solvers_selector_ajeno",
                _caso_portador(tmp, "selector_propio", "solvers_ajeno", ["pulso"]),
                "SOLVER_DE_DATO_NO_DECLARADO",
            )
        )
        esperado.append(
            (
                "solvers_sin_selector",
                _caso_portador(
                    tmp, "portador_num", "solvers_sin_selector", ["cw", "pulso"]
                ),
                "CLAIMS_SANO",
            )
        )
        esperado.append(
            (
                "solvers_mal_formados",
                _caso_portador(tmp, "selector_propio", "solvers_mal_formados", "cw"),
                "SCHEMA_VIOLADO",
            )
        )
        esperado.append(
            (
                "solvers_residuo_permanente",
                _caso_portador(
                    tmp, "solvers_residuo", "solvers_residuo_declarado", ["cw", "pulso"]
                ),
                "CLAIMS_TESTIGO_PERMANENTE",
            )
        )

        esperado.append(
            ("portador_local", _caso_local(tmp, "local"), "ESPERANDO_TESTIGO_LOCAL")
        )
        esperado.append(
            (
                "local_sin_testigo",
                _caso_local(tmp, "local_sin_testigo", con_testigo=False),
                "PARSER_ESPECIFICO_AUSENTE",
            )
        )
        esperado.append(
            (
                "local_prosa_rota",
                _caso_local(
                    tmp, "local_prosa_rota", prosa="El residuo plano es 0.13 %.\n"
                ),
                "README_DESALINEADO",
            )
        )
        esperado.append(
            (
                "modo_con_local",
                _caso_local(
                    tmp,
                    "modo_con_local",
                    extra={"modo": "testigo_permanente", "motivo": "declarado y escalado"},
                ),
                "MODO_CONTRADICHO",
            )
        )

        fallos = 0

        # HUELLA-VERIFY-CLAIMS-FALSADOR-PHANTOM-DATO-20261021: la fisica del
        # `dato`, por claim y en su propio `try`. El lector se rompe al vaciar
        # su fuente; el fantasma sobrevive con la cifra identica.
        casos_falsador = [
            (
                "falsador_lee",
                _caso_portador(tmp, "falsador_lector", "acto_lector"),
                "PARSER_LEE_DATO",
            ),
            (
                "falsador_fantasma",
                _caso_portador(tmp, "falsador_fantasma", "acto_fantasma"),
                "PHANTOM_DATO",
            ),
        ]
        for nombre, repo, quiero in casos_falsador:
            obtenido = _veredicto_falsador(_falsar_repo(repo))
            ok = obtenido == quiero
            print(
                "[AUTOTEST] %-14s esperado=%-24s obtenido=%-24s %s"
                % (nombre, quiero, obtenido, "OK" if ok else "FALLA")
            )
            if not ok:
                fallos += 1

        # HUELLA-VERIFY-CLAIMS-SOLVERS-MANDATORIO-20261021: la ley en su propia
        # tabla. El veredicto del repo no la publica — `N<=1` con y sin lista
        # firman los dos `CLAIMS_SANO`, y solo la declaracion los distingue.
        def _ley_caso(nombre_repo, codigo, claims, solvers=None):
            repo = _caso(tmp, nombre_repo, claims)
            ruta_portador = os.path.join(repo, "data", "portador.py")
            with open(ruta_portador, "w", encoding="utf-8") as fh:
                fh.write(codigo)
            if solvers is not None:
                _con_solvers(repo, solvers)
            return repo

        def _claim_de(ident, funcion, ruta):
            return _claim(
                id=ident,
                deriva="parser:data/portador.py::" + funcion,
                afirma="3",
                modo="derivacion",
                ruta=ruta,
            )

        dos_raices = [_claim_de("A1", "cifras_a", "a.filas"),
                      _claim_de("A2", "cifras_b", "b.filas")]
        casos_ley = [
            (
                "ley_sin_declarar",
                _ley_caso("ley_sin_declarar", _PORTADOR_DOS_NOMBRES, dos_raices),
                ("SOLVERS_SIN_DECLARAR", []),
            ),
            (
                "ley_declarada",
                _ley_caso(
                    "ley_declarada", _PORTADOR_DOS_NOMBRES, dos_raices, ["a", "b"]
                ),
                ("COTEJADO", ["a", "b"]),
            ),
            (
                "ley_docstring",
                _ley_caso(
                    "ley_docstring",
                    _PORTADOR_DOCSTRING_SOLVER,
                    [_claim_de("A1", "cifras_b", "a.filas")],
                ),
                ("NO_APLICABLE", ["a"]),
            ),
            (
                "ley_reciben",
                _ley_caso(
                    "ley_reciben",
                    _PORTADOR_RECIBE,
                    [
                        _claim_de("A1", "cifra", "banco.filas"),
                        _claim_de("A2", "cifra", "piloto.filas"),
                        _claim_de("A3", "cifra", "ramas.filas"),
                    ],
                ),
                ("NO_APLICABLE", []),
            ),
            (
                "ley_innecesario",
                _ley_caso(
                    "ley_innecesario",
                    _PORTADOR_DOS_SOLVERS,
                    [_claim_de("A1", "cifras_cw", "cw.filas")],
                    ["cw"],
                ),
                ("SOLVERS_INNECESARIO", ["cw"]),
            ),
        ]
        for nombre, repo, quiero in casos_ley:
            try:
                doc = verificar_repo(repo)["solvers"]
                obtenido = (doc["veredicto"], doc["portadores"])
            except Falla as e:
                obtenido = (e.codigo, [])
            ok = obtenido == quiero
            print(
                "[AUTOTEST] %-14s esperado=%-24s obtenido=%-24s %s"
                % (nombre, quiero[0], obtenido[0], "OK" if ok else "FALLA")
            )
            if not ok:
                fallos += 1

        # HUELLA-VERIFY-CLAIMS-SOLVERS-ORFANDAD-DECLARADA-20261021: el solver
        # declarado que ningun claim de derivacion coteja se DECLARA en la ley
        # (no se arresta: `testigo_permanente` queda fuera de las raices), y el
        # rojo de otro claim no borra lo ya medido.
        tres_raices = dos_raices + [_claim_de("A3", "cifras_a", "externo.filas")]
        casos_orfandad = [
            (
                "orfandad_declarada",
                _ley_caso(
                    "orfandad_declarada",
                    _PORTADOR_DOS_NOMBRES,
                    dos_raices,
                    ["a", "b", "extra"],
                ),
                ("COTEJADO", ["extra"]),
            ),
            (
                "orfandad_servida",
                _ley_caso(
                    "orfandad_servida", _PORTADOR_DOS_NOMBRES, dos_raices, ["b", "a"]
                ),
                ("COTEJADO", []),
            ),
            (
                "orfandad_en_rojo",
                _ley_caso(
                    "orfandad_en_rojo",
                    _PORTADOR_DOS_NOMBRES,
                    tres_raices,
                    ["a", "b", "extra"],
                ),
                ("SOLVER_DE_DATO_NO_DECLARADO", ["extra"]),
            ),
            (
                # El caso que obligo a medir contra raices: un portador que
                # RECIBE la raiz no puede nombrarla, y con el criterio de
                # portadores `banco/piloto/ramas` se declaraban huerfanos con
                # sus tres selectores servidos (`red-green-sandbox`).
                "orfandad_servida_por_raiz",
                _ley_caso(
                    "orfandad_servida_por_raiz",
                    _PORTADOR_RECIBE,
                    [
                        _claim_de("A1", "cifra", "banco.filas"),
                        _claim_de("A2", "cifra", "piloto.filas"),
                        _claim_de("A3", "cifra", "ramas.filas"),
                    ],
                    ["banco", "piloto", "ramas"],
                ),
                ("SOLVERS_INNECESARIO", []),
            ),
            (
                # Un solver que solo sirve a `testigo_permanente` no tiene
                # raiz de derivacion y se declara: es la razon de no arrestar.
                "orfandad_testigo",
                _caso_portador(
                    tmp, "solvers_residuo", "orfandad_testigo", ["cw", "pulso"]
                ),
                ("SOLVERS_INNECESARIO", ["cw", "pulso"]),
            ),
        ]
        for nombre, repo, quiero in casos_orfandad:
            try:
                doc = verificar_repo(repo)["solvers"]
                obtenido = (doc["veredicto"], doc.get("sin_selector"))
            except Falla as e:
                ley = getattr(e, "solvers", None) or {}
                obtenido = (e.codigo, ley.get("sin_selector"))
            ok = obtenido == quiero
            print(
                "[AUTOTEST] %-14s esperado=%-24s obtenido=%-24s %s"
                % (nombre, quiero[0], obtenido[0], "OK" if ok else "FALLA")
            )
            if not ok:
                fallos += 1

        # HUELLA-VERIFY-CLAIMS-ANCLA-DATO-20261021: el ancla muerde donde debe.
        # La ausencia se DECLARA (`DATO_SIN_ANCLA` rc 1): un campo que solo
        # coteja cuando esta presente es la decorativa nº 12 con otro nombre.
        casos_ancla = [
            (
                "ancla_ok",
                _caso(tmp, "ancla_ok", [_claim(modo="derivacion")]),
                "CLAIMS_SANO",
            ),
            (
                "ancla_sin_mapa",
                _editar_datos(
                    _caso(tmp, "ancla_sin_mapa", [_claim(modo="derivacion")]),
                    lambda d: d.pop("datos", None),
                ),
                "DATO_SIN_ANCLA",
            ),
            (
                "ancla_sin_entrada",
                _editar_datos(
                    _caso(tmp, "ancla_sin_entrada", [_claim(modo="derivacion")]),
                    lambda d: d["datos"].pop("data/d.json", None),
                ),
                "DATO_SIN_ANCLA",
            ),
            (
                "ancla_mismatch",
                _editar_datos(
                    _caso(tmp, "ancla_mismatch", [_claim(modo="derivacion")]),
                    lambda d: d["datos"].__setitem__("data/d.json", "0" * 16),
                ),
                "MISMATCH_DATO",
            ),
            (
                # Una entrada que nadie lee es memoria, no error: se imprime y
                # no firma rojo, pero no puede desaparecer del mapa.
                "ancla_huerfana",
                _editar_datos(
                    _caso(tmp, "ancla_huerfana", [_claim(modo="derivacion")]),
                    lambda d: d["datos"].__setitem__("data/otro.json", "0" * 16),
                ),
                ("CLAIMS_SANO", ["data/otro.json"]),
            ),
        ]
        for nombre, repo, quiero in casos_ancla:
            try:
                doc = verificar_repo(repo)
                obtenido = (
                    (doc["veredicto"], doc["datos"]["huerfanas"])
                    if isinstance(quiero, tuple)
                    else doc["veredicto"]
                )
            except Falla as e:
                obtenido = e.codigo
            ok = obtenido == quiero
            print(
                "[AUTOTEST] %-14s esperado=%-24s obtenido=%-24s %s"
                % (
                    nombre,
                    quiero if isinstance(quiero, str) else quiero[0],
                    obtenido if isinstance(obtenido, str) else obtenido[0],
                    "OK" if ok else "FALLA",
                )
            )
            if not ok:
                fallos += 1

        # HUELLA-VERIFY-CLAIMS-SONDA-DIGITOS-20261021: la sonda mide
        # ACOPLAMIENTO, no correccion. MUEVE certifica causalidad; ROMPE es
        # ambiguo; el silencio no prueba nada, y con presupuesto se declara
        # PODER_INSUFICIENTE en vez de firmar rojo donde no hay poder.
        casos_sonda = [
            (
                "sonda_vivo",
                "sonda_vivo",
                _PORTADOR_LEE_DIGITO,
                '{"n": 2}',
                "data/digitos.json",
                None,
                "DIGITO_VIVO",
            ),
            (
                "sonda_muerto",
                "sonda_muerto",
                _PORTADOR_CONSTANTE,
                '{"n": 2}',
                "data/digitos.json",
                None,
                "DIGITO_MUERTO",
            ),
            (
                "sonda_poder",
                "sonda_poder",
                _PORTADOR_LEE_DIGITO,
                '{"sobra": 5, "n": 2}',
                "data/digitos.json",
                1,
                "PODER_INSUFICIENTE",
            ),
            (
                "sonda_sin_digitos",
                "sonda_sin_digitos",
                _PORTADOR_CONSTANTE,
                '{"n": "dos"}',
                "data/digitos.json",
                None,
                "SIN_DIGITOS",
            ),
            (
                # Mismo silencio total, pero sobre CODIGO: la sonda declara
                # deuda (`SIN_DIGITO_VIVO` rc 0) y no acusa. La regla de rojo
                # es estrecha a proposito: un recuento es digito-inmutable.
                "sonda_py",
                "sonda_py",
                _PORTADOR_CONSTANTE,
                "x = 2\n",
                "data/notas.py",
                None,
                "SIN_DIGITO_VIVO",
            ),
            (
                "sonda_portador",
                "sonda_portador",
                _PORTADOR_CONSTANTE,
                None,
                "data/portador.py",
                None,
                "DATUM_ES_PORTADOR",
            ),
        ]
        for nombre, repo_nombre, portador, datum, dato, presu, quiero in casos_sonda:
            repo = _caso_sonda(tmp, repo_nombre, portador, datum, dato=dato)
            firmas = _sonda_repo(repo, presu)
            obtenido = firmas[-1]["veredicto"] if firmas else "SIN_MEDIBLES"
            ok = obtenido == quiero
            print(
                "[AUTOTEST] %-14s esperado=%-24s obtenido=%-24s %s"
                % (nombre, quiero, obtenido, "OK" if ok else "FALLA")
            )
            if not ok:
                fallos += 1

        for nombre, repo, quiero in esperado:
            try:
                obtenido = verificar_repo(repo)["veredicto"]
            except Falla as e:
                obtenido = e.codigo
            ok = obtenido == quiero
            print(
                "[AUTOTEST] %-14s esperado=%-24s obtenido=%-24s %s"
                % (nombre, quiero, obtenido, "OK" if ok else "FALLA")
            )
            if not ok:
                fallos += 1

        # El RC del run depende del CONJUNTO, no de un repo suelto: se mide
        # sobre `_rc()` y no sobre un caso mas de la lista de arriba.
        casos_rc = [
            ("rc_sano", (0, 0), 0),
            ("rc_fallo", (1, 0), 1),
            ("rc_esperando", (0, 2), RC_ESPERANDO_TESTIGO_LOCAL),
            ("rc_fallo_manda", (1, 2), 1),
        ]
        for nombre, (rojos, escalados), quiero in casos_rc:
            obtenido = _rc(rojos, escalados)
            ok = obtenido == quiero
            print(
                "[AUTOTEST] %-14s esperado=%-24s obtenido=%-24s %s"
                % (nombre, quiero, obtenido, "OK" if ok else "FALLA")
            )
            if not ok:
                fallos += 1

        # HUELLA-GRAMATICA-DUAL-SHA256-20261020: el pin de la conducta y su mordida.
        casos_cross = [
            ("cross_pin", huella_gramatica(), CROSS_HASH_GRAMATICA),
            (
                "cross_muerde",
                huella_gramatica(fixtures=(("F5", "lista#distintos"),)),
                CROSS_HASH_GRAMATICA,
            ),
        ]
        for nombre, obtenido, quiero in casos_cross:
            ok = (obtenido == quiero) if nombre == "cross_pin" else (obtenido != quiero)
            print(
                "[AUTOTEST] %-14s esperado=%-13s obtenido=%-13s %s"
                % (nombre, "== pin" if nombre == "cross_pin" else "!= pin",
                   obtenido[:12], "OK" if ok else "FALLA")
            )
            if not ok:
                fallos += 1

    total = (
        len(esperado)
        + len(casos_rc)
        + len(casos_cross)
        + len(casos_falsador)
        + len(casos_ley)
        + len(casos_orfandad)
        + len(casos_ancla)
        + len(casos_sonda)
    )
    print("AUTOTEST: %d/%d casos" % (total - fallos, total))
    return 0 if fallos == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
