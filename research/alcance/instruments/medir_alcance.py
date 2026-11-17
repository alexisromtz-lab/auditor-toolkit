#!/usr/bin/env python3
"""medir_alcance.py — etapa 0 del embudo: ¿la pieza abre la puerta al objeto?

El embudo medido tiene cuatro etapas: candidato (AST) -> ruptura (ejecucion
real) -> consumidor (busqueda publica) -> recepcion (¿alguien leyo?). Todas
suponen una quinta cosa que nadie medía: que el lector pueda LLEGAR. Una pieza
puede describir un objeto con precision perfecta y no ofrecer ninguna puerta.

Medido 17-Nov-2026 en el articulo 5059635 de dev.to: nombraba el repositorio una
vez, entre acentos graves, y `github.com` aparecia 0 veces en todo su cuerpo. El
autor habia auditado las cifras de esa pieza tres veces y nunca si era
alcanzable. Un instrumento puede medir el objeto con precision y no medir su
puerta.

Este lector mide la puerta. Reglas que NO negocia:

1. Nombrar no es enlazar. `auditor-toolkit` entre acentos graves describe el
   objeto y no lo alcanza: se publica SOLO_TEXTO, detalle code_span.

2. Una URL desnuda no es un enlace hasta que la plataforma la linkifique. Aqui
   se reporta SOLO_TEXTO/url_desnuda, jamas ENLACE. El motivo no es pesimismo:
   un falso rojo se corrige anadiendo corchetes, y un falso verde autoriza
   publicar una pieza huerfana creyendo que tiene puerta.

3. Un bloque cercado y un code span no contienen enlaces: dentro de ellos todo
   es SOLO_TEXTO. Es el mismo error que (1) con otra sintaxis.

4. Una URL mas profunda SI alcanza al objeto: `.../repo/tree/main` abre la
   puerta de `.../repo`. Un hermano NO: `.../repo-extra` es otro objeto. Se
   compara por frontera de ruta, no por prefijo de cadena.

5. El esquema no distingue puerta (http y https alcanzan lo mismo) pero la ruta
   si. Se normaliza el esquema y el host; nunca la ruta ni la consulta.

6. Una imagen no es una puerta. `![portada](url)` pinta un pixel; el objeto no
   se alcanza pinchandolo. Se descarta antes de buscar enlaces y se reporta
   SOLO_TEXTO/imagen, no url_desnuda: la URL existe en el fuente pero el lector
   no la ve escrita ni puede pincharla, asi que atribuir la causa a "url
   desnuda" seria senalar el defecto equivocado.

7. Pieza ilegible => NO_MEDIDO, nunca HUERFANO. Decir "no enlaza" de una pieza
   que no se pudo leer es un cero de poblacion vacia, que es la mentira que
   este corpus prohibe. Medido 17-Nov-2026: el mismo error imprimia DESCARGA 0
   cuando Zenodo no se habia consultado.

8. La copia no es el objeto. `--origen` compara la pieza PUBLICADA contra el
   original: si el original enlaza y la publicada no, se publica
   origen=divergente. La rama contraria NO es "coincide" —las dos fuentes no
   dicen lo mismo— sino origen=sin_divergencia, que solo afirma lo medido: la
   pieza no perdio ninguna puerta que el original tuviera. Sin `--origen` se
   publica origen=sin_origen, que tampoco es "sin_divergencia".

9. Este lector no es un parser CommonMark: mide presencia de URL en posicion de
   enlace. Los enlaces por referencia se resuelven (definicion + uso); una
   definicion que nadie usa se reporta referencia_sin_uso, porque el lector
   tampoco la ve.

10. La cabecera del TSV se escribe una sola vez: dos cabeceras parten cualquier
    parser.

11. El codigo de salida ES el veredicto, porque esto es una compuerta y no un
    medidor: 0 ALCANZABLE · 1 PARCIAL o SIN_ALCANCE · 2 NO_MEDIDO · 20 argumentos.
    Un NO_MEDIDO nunca degrada a 1 ni a 0.

Uso:
    python3 medir_alcance.py --pieza 5059635 \
        --debe https://github.com/alexisromtz-lab/auditor-toolkit \
        --origen ~/Desktop/devto-articulo-final.md \
        --tsv research/alcance/data/ALCANCE.tsv
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

UA = "platino-labs-alcance/1.0"

CABECERA = "fecha_hora\tpieza\thuella\tobjeto\testado\tdetalle\tveredicto\torigen"

ESTADOS = ("ENLACE", "SOLO_TEXTO", "HUERFANO", "NO_MEDIDO")
# El veredicto es agregado y tiene su propio vocabulario: PARCIAL y ALCANZABLE
# no son estados de un objeto y no deben confundirse con ellos.
VEREDICTOS = ("ALCANZABLE", "PARCIAL", "SIN_ALCANCE", "NO_MEDIDO")
# De la puerta mas cercana a la mas lejana: una URL desnuda solo necesita
# corchetes; una mencion ni siquiera tiene la direccion escrita.
PRIORIDAD_DETALLE = ("url_desnuda", "referencia_sin_uso", "code_span", "imagen", "fence", "mencion")

# La columna `origen` tiene su propio vocabulario, y sin lector se rellenaba. El
# self-test comprueba que ninguna etiqueta emitida queda fuera de esta tupla.
ORIGENES = ("divergente", "sin_divergencia", "sin_origen", "origen_ilegible")

RE_FENCE = re.compile(r"^\s{0,3}(```|~~~)")
# (?<!!) descarta imagenes: `![alt](url)` pinta un pixel, no abre una puerta.
RE_MD_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)")
RE_AUTOLINK = re.compile(r"<((?:https?|ftp)://[^>\s]+)>")
RE_IMAGE = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)")
RE_REF_DEF = re.compile(r"^\s{0,3}\[([^\]]+)\]:\s*<?(\S+?)>?\s*$")
RE_REF_USE = re.compile(r"\[([^\]]*)\]\[([^\]]*)\]")
RE_REF_USE_SHORT = re.compile(r"\[([^\]]+)\](?!\(|\[|:)")
RE_CODE_SPAN = re.compile(r"`+([^`]*)`+")
RE_BARE_URL = re.compile(r"https?://[^\s)>\]]+")


# ------------------------------------------------------------- normalizacion


def _norm(url: str) -> str:
    """Esquema y host normalizados; la ruta se respeta tal cual."""
    limpio = url.strip().strip("<>").strip()
    limpio = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", "", limpio)
    limpio = limpio.rstrip("/")
    if limpio.endswith(".git"):
        limpio = limpio[:-4]
    host, _, resto = limpio.partition("/")
    return (host.lower() + ("/" + resto if resto else "")).rstrip("/")


def _nombre_corto(objeto: str) -> str:
    partes = [p for p in _norm(objeto).split("/") if p]
    return partes[-1] if partes else ""


def _menciona(texto: str, objeto: str) -> bool:
    nombre = _nombre_corto(objeto)
    return bool(nombre) and nombre.lower() in texto.lower()


def _alcanza(candidato: str, objeto: str) -> bool:
    """Una subruta alcanza al objeto; un hermano con prefijo comun no."""
    c, o = _norm(candidato), _norm(objeto)
    if not c or not o:
        return False
    if c == o:
        return True
    return c.startswith(o) and len(c) > len(o) and c[len(o)] in "/#?"


# ---------------------------------------------------------------- clasificador


def clasificar(texto: str | None, objeto: str) -> tuple[str, str]:
    """Devuelve (estado, detalle) de UN objeto dentro de UNA pieza."""
    if texto is None:
        return ("NO_MEDIDO", "ilegible")
    if not _norm(objeto):
        return ("NO_MEDIDO", "objeto_vacio")

    fuera: list[str] = []
    definiciones: dict[str, str] = {}
    vistas: set[str] = set()
    en_fence = False

    for linea in texto.splitlines():
        if RE_FENCE.match(linea):
            en_fence = not en_fence
            continue
        if en_fence:
            if _menciona(linea, objeto):
                vistas.add("fence")
            continue
        definida = RE_REF_DEF.match(linea)
        if definida:
            definiciones[definida.group(1).strip().lower()] = definida.group(2)
            continue
        fuera.append(linea)

    # 1. La puerta de verdad: enlace en linea o autolink.
    for linea in fuera:
        for hallado in RE_MD_LINK.finditer(linea):
            if _alcanza(hallado.group(1), objeto):
                return ("ENLACE", "markdown")
    for linea in fuera:
        for hallado in RE_AUTOLINK.finditer(linea):
            if _alcanza(hallado.group(1), objeto):
                return ("ENLACE", "autolink")

    # 2. Enlaces por referencia: la definicion sola no es puerta, hace falta uso.
    usadas: set[str] = set()
    for linea in fuera:
        for hallado in RE_REF_USE.finditer(linea):
            clave = (hallado.group(2) or hallado.group(1) or "").strip().lower()
            if clave:
                usadas.add(clave)
        for hallado in RE_REF_USE_SHORT.finditer(linea):
            usadas.add(hallado.group(1).strip().lower())
    for clave, url in definiciones.items():
        if _alcanza(url, objeto):
            if clave in usadas:
                return ("ENLACE", "referencia")
            vistas.add("referencia_sin_uso")

    # 3. Lo que nombra sin abrir: code span, imagen, URL desnuda, mencion.
    for linea in fuera:
        for hallado in RE_CODE_SPAN.finditer(linea):
            if _menciona(hallado.group(1), objeto):
                vistas.add("code_span")
        sin_codigo = RE_CODE_SPAN.sub(" ", linea)
        for hallado in RE_IMAGE.finditer(sin_codigo):
            if _alcanza(hallado.group(1), objeto):
                vistas.add("imagen")
        sin_imagen = RE_IMAGE.sub(" ", sin_codigo)
        for hallado in RE_BARE_URL.finditer(sin_imagen):
            if _alcanza(hallado.group(0), objeto):
                vistas.add("url_desnuda")
        if _menciona(sin_codigo, objeto):
            vistas.add("mencion")

    for detalle in PRIORIDAD_DETALLE:
        if detalle in vistas:
            return ("SOLO_TEXTO", detalle)
    return ("HUERFANO", "ausente")


class _LectorHTML(HTMLParser):
    """Separa lo que un lector PUEDE pulsar de lo que solo PUEDE leer.

    No es un lector de pagina: es el cuerpo servido por la plataforma. El chrome
    del sitio (menu, perfil del autor, barra lateral) enlaza a GitHub por su
    cuenta y contarlo seria un falso verde de fabrica.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anclas: list[tuple[str, str]] = []
        self.codigo: list[str] = []
        self.imagenes: list[tuple[str, str]] = []
        self.texto: list[str] = []
        self._prof_ancla = 0
        self._prof_codigo = 0
        self._buf_ancla: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        valores = dict(attrs)
        if tag == "a":
            self._prof_ancla += 1
            self._buf_ancla = []
            self.anclas.append((valores.get("href") or "", ""))
        elif tag in ("code", "pre"):
            self._prof_codigo += 1
        elif tag == "img":
            self.imagenes.append((valores.get("src") or "", valores.get("alt") or ""))

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._prof_ancla:
            self._prof_ancla -= 1
            href, _ = self.anclas[-1]
            self.anclas[-1] = (href, " ".join(self._buf_ancla))
            self._buf_ancla = []
        elif tag in ("code", "pre") and self._prof_codigo:
            self._prof_codigo -= 1

    def handle_data(self, data: str) -> None:
        if self._prof_ancla:
            self._buf_ancla.append(data)
        elif self._prof_codigo:
            self.codigo.append(data)
        else:
            self.texto.append(data)


def clasificar_html(html_texto: str | None, objeto: str) -> tuple[str, str]:
    """Igual que `clasificar`, pero sobre el cuerpo RENDERIZADO de la pieza.

    Un `<a href>` que alcanza es la puerta. Todo lo demas nombra sin abrir, con
    el mismo vocabulario de detalles: la plataforma no inventa causas nuevas.
    """
    if html_texto is None:
        return ("NO_MEDIDO", "ilegible")
    if not _norm(objeto):
        return ("NO_MEDIDO", "objeto_vacio")

    lector = _LectorHTML()
    lector.feed(html_texto)
    lector.close()

    for href, _texto in lector.anclas:
        if _alcanza(href, objeto):
            return ("ENLACE", "html")

    vistas: set[str] = set()
    for href, texto in lector.anclas:
        if _menciona(texto, objeto) or _menciona(href, objeto):
            vistas.add("mencion")
    if _menciona(" ".join(lector.codigo), objeto):
        vistas.add("code_span")
    for src, alt in lector.imagenes:
        if _alcanza(src, objeto):
            vistas.add("imagen")
        if _menciona(alt, objeto):
            vistas.add("mencion")
    suelto = " ".join(lector.texto)
    # El texto suelto se escanea candidato a candidato, igual que en markdown:
    # `_alcanza` compara desde el principio del candidato, no en cualquier punto.
    for hallado in RE_BARE_URL.finditer(suelto):
        if _alcanza(hallado.group(0), objeto):
            vistas.add("url_desnuda")
    if _menciona(suelto, objeto):
        vistas.add("mencion")

    for detalle in PRIORIDAD_DETALLE:
        if detalle in vistas:
            return ("SOLO_TEXTO", detalle)
    return ("HUERFANO", "ausente")


def veredicto(estados: list[str]) -> str:
    if not estados or all(e == "NO_MEDIDO" for e in estados):
        return "NO_MEDIDO"
    if all(e == "ENLACE" for e in estados):
        return "ALCANZABLE"
    if any(e == "ENLACE" for e in estados):
        return "PARCIAL"
    return "SIN_ALCANCE"


# --------------------------------------------------------------------- filas


def _huella(texto: str | None) -> str:
    if texto is None:
        return "NO_MEDIDO"
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:12]


def construir_filas(
    pieza: str,
    texto: str | None,
    objetos: list[str],
    origen_texto: str | None = None,
    origen_pedido: bool = False,
) -> list[dict]:
    return _filas_desde_estados(
        pieza, texto, objetos, [clasificar(texto, objeto) for objeto in objetos], origen_texto, origen_pedido
    )


def _filas_desde_estados(
    pieza: str,
    texto: str | None,
    objetos: list[str],
    medidos: list[tuple[str, str]],
    origen_texto: str | None = None,
    origen_pedido: bool = False,
) -> list[dict]:
    """Arma las filas a partir de una clasificacion ya hecha: markdown o render."""
    huella = _huella(texto)
    juicio = veredicto([estado for estado, _ in medidos])
    origen_medidos = (
        [clasificar(origen_texto, objeto)[0] for objeto in objetos]
        if origen_texto is not None
        else None
    )
    filas: list[dict] = []
    for indice, objeto in enumerate(objetos):
        estado, detalle = medidos[indice]
        if origen_pedido and origen_texto is None:
            etiqueta = "origen_ilegible"
        elif origen_medidos is None:
            etiqueta = "sin_origen"
        elif origen_medidos[indice] == "ENLACE" and estado != "ENLACE":
            etiqueta = "divergente"
        else:
            etiqueta = "sin_divergencia"
        filas.append(
            {
                "pieza": pieza,
                "huella": huella,
                "objeto": objeto,
                "estado": estado,
                "detalle": detalle,
                "veredicto": juicio,
                "origen": etiqueta,
            }
        )
    return filas


def a_tsv(filas: list[dict], momento: str, con_cabecera: bool = True) -> str:
    """Cabecera solo la primera vez: dos cabeceras parten cualquier parser."""
    lineas = [CABECERA] if con_cabecera else []
    for fila in filas:
        lineas.append(
            "\t".join(
                [
                    momento,
                    fila["pieza"],
                    fila["huella"],
                    fila["objeto"],
                    fila["estado"],
                    fila["detalle"],
                    fila["veredicto"],
                    fila["origen"],
                ]
            )
        )
    return "\n".join(lineas) + "\n"


def linea_alcance(filas: list[dict]) -> str:
    """Un NO_MEDIDO no se imprime como 0/N: 0 de una poblacion vacia es mentira."""
    if not filas:
        return "ALCANCE: NO_MEDIDO (sin objetos pedidos)"
    medidos = sum(1 for f in filas if f["estado"] != "NO_MEDIDO")
    if medidos == 0:
        return f"ALCANCE: NO_MEDIDO ({len(filas)} objeto(s) sin medir)"
    alcanzables = sum(1 for f in filas if f["estado"] == "ENLACE")
    return f"ALCANCE: {alcanzables}/{medidos} objetos alcanzables"


def imprimir_resumen(filas: list[dict], momento: str) -> None:
    if not filas:
        print("SIN FILAS: no se midio ningun objeto.")
        return
    ancho = max(len(f["objeto"]) for f in filas) + 2
    print(f"pieza: {filas[0]['pieza']}  huella: {filas[0]['huella']}  {momento}")
    print(f"{'objeto'.ljust(ancho)}{'estado'.ljust(12)}{'detalle'.ljust(20)}origen")
    print("-" * (ancho + 44))
    for fila in filas:
        print(
            fila["objeto"].ljust(ancho)
            + fila["estado"].ljust(12)
            + fila["detalle"].ljust(20)
            + fila["origen"]
        )
    print("-" * (ancho + 44))
    print(linea_alcance(filas))
    print(f"VEREDICTO: {filas[0]['veredicto']}")
    divergentes = sum(1 for f in filas if f["origen"] == "divergente")
    if divergentes:
        print(f"ORIGEN_DIVERGE: {divergentes} objeto(s) enlazados en el original y no en la pieza publicada")


# -------------------------------------------------------------------- lectura


def _json_devto(articulo: int) -> dict | None:
    peticion = urllib.request.Request(
        f"https://dev.to/api/articles/{articulo}", headers={"User-Agent": UA}
    )
    try:
        with urllib.request.urlopen(peticion, timeout=20) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except Exception:  # ilegible: NO_MEDIDO, no "no enlaza"
        return None
    return datos if isinstance(datos, dict) else None


def _texto_devto(articulo: int) -> str | None:
    datos = _json_devto(articulo) or {}
    cuerpo = datos.get("body_markdown")
    return cuerpo if isinstance(cuerpo, str) else None


def _html_devto(articulo: int) -> str | None:
    """El cuerpo que la plataforma SIRVIO, sin el chrome del sitio."""
    datos = _json_devto(articulo) or {}
    cuerpo = datos.get("body_html")
    return cuerpo if isinstance(cuerpo, str) else None


def leer_pieza(pieza: str, render: bool = False) -> tuple[str, str | None]:
    """Devuelve (etiqueta, texto). texto None significa NO_MEDIDO."""
    sufijo = "#render" if render else ""
    if re.fullmatch(r"\d+", pieza):
        ident = int(pieza)
        lector = _html_devto if render else _texto_devto
        return (f"devto/{ident}{sufijo}", lector(ident))
    if pieza.startswith("devto:"):
        ident = pieza.split(":", 1)[1]
        if not ident.isdigit():
            return (pieza + sufijo, None)
        lector = _html_devto if render else _texto_devto
        return (f"devto/{ident}{sufijo}", lector(int(ident)))
    ruta = Path(pieza).expanduser()
    try:
        return (f"archivo:{ruta.name}{sufijo}", ruta.read_text(encoding="utf-8"))
    except OSError:
        return (f"archivo:{ruta.name}{sufijo}", None)


def leer_origen(origen: str | None) -> str | None:
    """El original contra el que se mide divergencia: un .md o el markdown de dev.to."""
    if not origen:
        return None
    if re.fullmatch(r"\d+", origen):
        return _texto_devto(int(origen))
    if origen.startswith("devto:"):
        ident = origen.split(":", 1)[1]
        return _texto_devto(int(ident)) if ident.isdigit() else None
    try:
        return Path(origen).expanduser().read_text(encoding="utf-8")
    except OSError:
        return None


# ------------------------------------------------------------------ self-test


def self_test() -> int:
    """Cada regla del docstring con su caso, y sus controles negativos."""
    objeto = "https://github.com/alexisromtz-lab/auditor-toolkit"
    pruebas: list[tuple[str, object, object]] = []

    def caso(nombre: str, obtenido, esperado) -> None:
        pruebas.append((nombre, obtenido, esperado))

    # 1. enlace en linea
    caso("01 markdown", clasificar("[repo](%s)" % objeto, objeto), ("ENLACE", "markdown"))
    # 2. autolink
    caso("02 autolink", clasificar("<%s>" % objeto, objeto), ("ENLACE", "autolink"))
    # 3. nombrar sin enlazar
    caso("03 mencion", clasificar("use auditor-toolkit hoy", objeto), ("SOLO_TEXTO", "mencion"))
    # 4. code span: el defecto medido el 17-Nov-2026
    caso("04 code span", clasificar("mira `auditor-toolkit`", objeto), ("SOLO_TEXTO", "code_span"))
    # 5. dentro de un bloque cercado no hay enlace
    caso(
        "05 fence",
        clasificar("```\n[repo](%s)\n```" % objeto, objeto),
        ("SOLO_TEXTO", "fence"),
    )
    # 6. URL desnuda no es enlace (falso rojo barato, falso verde caro)
    caso("06 url desnuda", clasificar("en %s" % objeto, objeto), ("SOLO_TEXTO", "url_desnuda"))
    # 7. una imagen no es una puerta, y su causa no es "url desnuda"
    caso("07 imagen", clasificar("![portada](%s)" % objeto, objeto), ("SOLO_TEXTO", "imagen"))
    caso(
        "07b imagen ajena",
        clasificar("![auditor-toolkit](https://ejemplo.mx/x.png)", objeto),
        ("SOLO_TEXTO", "mencion"),
    )
    # 8. la subruta si alcanza
    caso(
        "08 subruta",
        clasificar("[research](%s/tree/main/research)" % objeto, objeto),
        ("ENLACE", "markdown"),
    )
    # 9. el hermano con prefijo comun no alcanza
    caso(
        "09 hermano",
        clasificar("[otro](%s-extra)" % objeto, objeto),
        ("SOLO_TEXTO", "mencion"),
    )
    # 10. enlace por referencia usado
    caso(
        "10 referencia usada",
        clasificar("[repo][r]\n\n[r]: %s" % objeto, objeto),
        ("ENLACE", "referencia"),
    )
    # 11. definicion que nadie usa: el lector tampoco la ve
    caso(
        "11 referencia sin uso",
        clasificar("[r]: %s\n\ntexto" % objeto, objeto),
        ("SOLO_TEXTO", "referencia_sin_uso"),
    )
    # 12. objeto ausente del todo
    caso("12 ausente", clasificar("nada que ver", objeto), ("HUERFANO", "ausente"))
    # 13. pieza ilegible: NO_MEDIDO, jamas HUERFANO
    caso("13 ilegible", clasificar(None, objeto), ("NO_MEDIDO", "ilegible"))
    # 14. la URL mas la mencion a la vez: gana la mas cercana a la puerta
    caso(
        "14 prioridad de detalle",
        clasificar("`auditor-toolkit` y %s" % objeto, objeto),
        ("SOLO_TEXTO", "url_desnuda"),
    )
    # 15. veredicto agregado
    caso("15a veredicto alcanzable", veredicto(["ENLACE", "ENLACE"]), "ALCANZABLE")
    caso("15b veredicto parcial", veredicto(["ENLACE", "HUERFANO"]), "PARCIAL")
    caso("15c veredicto sin alcance", veredicto(["HUERFANO", "SOLO_TEXTO"]), "SIN_ALCANCE")
    caso("15d veredicto no medido", veredicto(["NO_MEDIDO", "NO_MEDIDO"]), "NO_MEDIDO")
    # 16. origen divergente: la copia enlaza, la pieza publicada no
    filas = construir_filas(
        "devto/1", "mira `auditor-toolkit`", [objeto], origen_texto="[repo](%s)" % objeto
    )
    caso("16 origen divergente", (filas[0]["origen"], filas[0]["veredicto"]), ("divergente", "SIN_ALCANCE"))
    # 17. sin origen no se declara coincidencia
    filas = construir_filas("devto/1", "[repo](%s)" % objeto, [objeto])
    caso("17 sin origen", filas[0]["origen"], "sin_origen")
    # 17b. origen pedido pero ilegible no se declara "sin origen"
    filas = construir_filas("devto/1", "x", [objeto], None, origen_pedido=True)
    caso("17b origen ilegible", filas[0]["origen"], "origen_ilegible")
    # 18. TSV: una cabecera y ocho columnas en toda fila
    enlazada = "[r](%s)" % objeto
    filas = construir_filas("devto/1", enlazada, [objeto], enlazada)
    tsv = a_tsv(filas, "2026-11-17T00:00:00Z")
    lineas = [l for l in tsv.splitlines() if l]
    caso("18a tsv cabecera", lineas[0], CABECERA)
    caso("18b tsv columnas", {len(l.split("\t")) for l in lineas}, {8})
    # 19. sin cabecera al anexar
    caso("19a anexo sin cabecera", a_tsv(filas, "x", con_cabecera=False).count(CABECERA), 0)
    caso("19b dos anexos una cabecera", (a_tsv(filas, "x") + a_tsv(filas, "y", con_cabecera=False)).count("fecha_hora"), 1)
    # 19b. un veredicto no reutiliza la palabra de un estado
    caso("19c vocabularios disjuntos", set(VEREDICTOS) & {"ENLACE", "SOLO_TEXTO"}, set())
    # 20. control negativo: poblacion vacia no produce cero falso
    caso("20 lista vacia", veredicto([]), "NO_MEDIDO")
    caso("20b objeto vacio", clasificar("texto", "")[0], "NO_MEDIDO")
    # 21. el resumen tampoco imprime 0/N cuando no midio nada
    filas = construir_filas("devto/1", None, [objeto])
    caso("21a alcance no medido", linea_alcance(filas), "ALCANCE: NO_MEDIDO (1 objeto(s) sin medir)")
    caso("21b dice NO_MEDIDO", "0/" in linea_alcance(filas), False)
    filas = construir_filas("devto/1", "[r](%s)" % objeto, [objeto, "https://github.com/alexisromtz-lab/otro"])
    caso("21c alcance parcial", linea_alcance(filas), "ALCANCE: 1/2 objetos alcanzables")

    # 22. el render es otra FUENTE del mismo sujeto: mismo vocabulario de causas
    caso("22a html ancla", clasificar_html('<p>mira <a href="%s">el repo</a></p>' % objeto, objeto), ("ENLACE", "html"))
    caso("22b html code span", clasificar_html("<p>era <code>auditor-toolkit</code></p>", objeto), ("SOLO_TEXTO", "code_span"))
    caso(
        "22c html nombra sin abrir",
        clasificar_html('<p><a href="https://example.com">auditor-toolkit</a></p>', objeto),
        ("SOLO_TEXTO", "mencion"),
    )
    caso("22d html url desnuda", clasificar_html("<p>en %s</p>" % objeto, objeto), ("SOLO_TEXTO", "url_desnuda"))
    caso(
        "22e html imagen",
        clasificar_html('<img src="%s/raw/main/portada.png" alt="portada">' % objeto, objeto),
        ("SOLO_TEXTO", "imagen"),
    )
    caso(
        "22f html entidad",
        clasificar_html('<a href="%s?utm=x&amp;y=1">repo</a>' % objeto, objeto),
        ("ENLACE", "html"),
    )
    caso("22g html ilegible", clasificar_html(None, objeto), ("NO_MEDIDO", "ilegible"))
    caso("22h html ajeno", clasificar_html('<a href="https://example.com">nada</a>', objeto), ("HUERFANO", "ausente"))
    caso(
        "22i html hermano",
        clasificar_html('<a href="%s-extra">repo</a>' % objeto, objeto),
        ("SOLO_TEXTO", "mencion"),
    )
    # 23. el veredicto sale del render; la divergencia, del markdown que lo origino
    md_original = "[el repo](%s)" % objeto
    html_servido = "<p>el repo</p>"
    filas = _filas_desde_estados(
        "devto/1#render", html_servido, [objeto], [clasificar_html(html_servido, objeto)], md_original, True
    )
    caso("23a estado del render", (filas[0]["estado"], filas[0]["detalle"]), ("HUERFANO", "ausente"))
    caso("23b el markdown tenia la puerta", filas[0]["origen"], "divergente")
    filas = _filas_desde_estados(
        "devto/1#render", '<a href="%s">r</a>' % objeto, [objeto], [("ENLACE", "html")], "en %s" % objeto, True
    )
    caso("23c plataforma anade puerta no es coincidencia", filas[0]["origen"], "sin_divergencia")
    # 24. la columna origen tiene vocabulario con lector: nada emitido queda fuera
    emitidas = {
        construir_filas("p", "x", [objeto])[0]["origen"],
        construir_filas("p", "x", [objeto], None, origen_pedido=True)[0]["origen"],
        construir_filas("p", "x", [objeto], md_original)[0]["origen"],
        construir_filas("p", md_original, [objeto], md_original)[0]["origen"],
    }
    caso("24a etiquetas de origen conocidas", emitidas <= set(ORIGENES), True)
    caso("24b las cuatro se ejercitan", len(emitidas), 4)

    fallos = [(nombre, obtenido, esperado) for nombre, obtenido, esperado in pruebas if obtenido != esperado]
    for nombre, obtenido, esperado in fallos:
        print(f"FALLO {nombre}: obtenido {obtenido!r} != esperado {esperado!r}")
    if fallos:
        print(f"SELF-TEST FALLA: {len(fallos)} defecto(s)")
    print(f"SELF-TEST OK: {len(pruebas) - len(fallos)}/{len(pruebas)} (enlace, autolink, code span, fence, "
          "url desnuda, imagen, subruta, hermano, referencia, ilegible, alcance parcial, origen divergente, "
          "html servido)")
    return 1 if fallos else 0


# --------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mide si una pieza publicada abre la puerta al objeto que describe."
    )
    parser.add_argument("--pieza", help="ruta a un .md o id numerico de dev.to")
    parser.add_argument("--debe", action="append", default=[], help="URI que la pieza deberia alcanzar (repetible)")
    parser.add_argument("--origen", help="original contra el que medir divergencia: .md o devto:<id>")
    parser.add_argument(
        "--render",
        action="store_true",
        help="mide el cuerpo RENDERIZADO (body_html) en vez del markdown",
    )
    parser.add_argument("--tsv", help="ruta donde anexar las filas")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.pieza or not args.debe:
        print("ERROR DE ARGUMENTOS: hacen falta --pieza y al menos un --debe, o --self-test", file=sys.stderr)
        return 20

    pieza, texto = leer_pieza(args.pieza, render=args.render)
    origen_texto = leer_origen(args.origen)
    if args.render:
        # El render es el objeto; el markdown es el origen. La clasificacion va
        # sobre lo servido, pero la divergencia se mide contra lo escrito.
        estados = [clasificar_html(texto, obj) for obj in args.debe]
        filas = _filas_desde_estados(pieza, texto, args.debe, estados, origen_texto, bool(args.origen))
    else:
        filas = construir_filas(pieza, texto, args.debe, origen_texto, origen_pedido=bool(args.origen))
    momento = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    imprimir_resumen(filas, momento)

    if args.tsv:
        nuevo = not os.path.exists(args.tsv)
        with open(args.tsv, "a", encoding="utf-8") as salida:
            salida.write(a_tsv(filas, momento, con_cabecera=nuevo))
        print(f"\n  filas anexadas a {args.tsv}")

    juicio = filas[0]["veredicto"]
    return {"ALCANZABLE": 0, "PARCIAL": 1, "SIN_ALCANCE": 1, "NO_MEDIDO": 2}[juicio]


if __name__ == "__main__":
    sys.exit(main())
