#!/usr/bin/env python3
"""verificar_limites — ¿cada página publica lo que no prueba?

Una página del escaparate demuestra su tesis. Una página que no declara su
límite no es un instrumento: es una promesa. Este verificador exige que cada
`demo/<nombre>/index.html` publique un bloque

    <section id="limites" data-limites="N"> … </section>

con exactamente N elementos `<li>` (N >= 2), cada uno con texto sustantivo y
con una negación explícita, y con su clave de idioma presente en todas las
traducciones del archivo.

Contrato de códigos:

    RC 0 = todas las páginas declaran su límite y los README lo dicen
    RC 1 = hay una página (o un README) que no cumple; se nombra cuál y por qué
    RC 2 = NO_MEDIDO: no se encontró ninguna página que verificar
    RC 3 = una carpeta de demo sin `index.html`

Límite declarado: mide que el bloque **exista y sea sustantivo**, no que el
límite declarado sea verdadero ni que sea el límite que importa. Un texto
plausible pero falso pasa este verificador. Eso lo paga quien escribe el
límite; el verificador sólo impide que el bloque desaparezca en silencio, se
quede sin traducción o se reduzca a una línea vacía.

Segundo límite: cuenta apariciones de la clave de idioma en el archivo. Una
clave repetida dentro del texto de un solo idioma contaría como si estuviera
en dos. Se declara y no se resuelve: parsear JavaScript para distinguirlo
costaría más de lo que compra.

Tercer límite: lee el HTML, no lo renderiza. Un `<li>` que existe y que el CSS
esconde (`display:none`) cuenta como declarado. Los comentarios `<!-- … -->` se
descuentan sobre el documento entero antes de contar nada, porque un comentario
que abraza la etiqueta completa deja el `<li>` visible a un `findall`. Medido el
14-Nov-2026: hasta esta corrección, comentar un límite entero daba RC 0; el
banco sólo cubría el caso de comentar el texto *dentro* del `<li>`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

LIMITES_MINIMOS = 2
PALABRAS_MINIMAS = 8
PALABRAS_MINIMAS_TITULO = 2
NEGACIONES = ("no", "not", "never", "neither", "ni", "sin")
APARICIONES_POR_CLAVE = 3
ATRIBUTOS_DE_IDIOMA = ("data-t", "data-i18n")
READMES = ("README.md", "README.es.md")
CITA_OBLIGATORIA = "verificar_limites.py"

RC_OK = 0
RC_VIOLACION = 1
RC_NO_MEDIDO = 2
RC_SIN_PAGINA = 3


def sin_comentarios(fragmento):
    """Quita `<!-- … -->`: ese texto está en el archivo y no lo lee nadie.

    Se aplica al documento entero, no sólo al texto de cada `<li>`: si el
    comentario abraza la etiqueta completa, el `<li>` sigue existiendo para un
    `findall` y el límite cuenta como publicado.
    """
    return re.sub(r"<!--.*?-->", " ", fragmento, flags=re.S)


def texto_visible(fragmento):
    """Texto que vería una persona: sin comentarios, sin etiquetas, espacios colapsados."""
    sin_etiquetas = re.sub(r"<[^>]+>", " ", sin_comentarios(fragmento))
    return " ".join(sin_etiquetas.split())


def clave_de_idioma(etiqueta):
    """La clave de traducción declarada en una etiqueta de apertura, o None."""
    for atributo in ATRIBUTOS_DE_IDIOMA:
        encontrado = re.search(re.escape(atributo) + r'\s*=\s*"([^"]+)"', etiqueta)
        if encontrado:
            return encontrado.group(1)
    return None


def contiene_negacion(texto):
    """Una negación explícita: sin ella el bloque no declara un límite."""
    palabras = re.findall(r"[^\W\d_]+", texto.lower(), re.UNICODE)
    return any(palabra in NEGACIONES for palabra in palabras)


def cobertura(html, clave, donde):
    """La clave tiene que viajar en todas las traducciones del archivo."""
    patron = r"(?<![\w-])" + re.escape(clave) + r"(?![\w-])"
    apariciones = len(re.findall(patron, html))
    if apariciones >= APARICIONES_POR_CLAVE:
        return []
    return [
        "%s usa la clave %r y aparece %d vez/veces (mínimo %d): "
        "falta en al menos una traducción" % (donde, clave, apariciones, APARICIONES_POR_CLAVE)
    ]


def revisar_pagina(ruta):
    """Devuelve (fallos, numero_de_limites_declarados)."""
    html = sin_comentarios(ruta.read_text(encoding="utf-8"))
    apertura = re.search(r'<section\b[^>]*\bid\s*=\s*"limites"[^>]*>', html)
    if not apertura:
        return ['no hay <section id="limites">: la página no declara lo que no prueba'], 0

    fallos = []
    etiqueta = apertura.group(0)
    declarados = re.search(r'data-limites\s*=\s*"(\d+)"', etiqueta)
    if declarados:
        declarados = int(declarados.group(1))
    else:
        fallos.append('la sección de límites no declara data-limites="N"')

    resto = html[apertura.end():]
    cierre = resto.find("</section>")
    if cierre < 0:
        return fallos + ["la sección de límites no cierra"], 0
    cuerpo = resto[:cierre]

    titulo = re.search(r"<h2\b([^>]*)>(.*?)</h2>", cuerpo, re.S)
    if not titulo:
        fallos.append("la sección de límites no tiene <h2>: no se anuncia como tal")
    else:
        texto_titulo = texto_visible(titulo.group(2))
        if len(texto_titulo.split()) < PALABRAS_MINIMAS_TITULO:
            fallos.append("el título de la sección no dice nada: %r" % texto_titulo)
        clave_titulo = clave_de_idioma(titulo.group(1))
        if clave_titulo:
            fallos.extend(cobertura(html, clave_titulo, "el título de la sección"))

    items = re.findall(r"<li\b([^>]*)>(.*?)</li>", cuerpo, re.S)
    if declarados is not None and len(items) != declarados:
        fallos.append(
            "declara %d límites y publica %d" % (declarados, len(items))
        )
    if len(items) < LIMITES_MINIMOS:
        fallos.append(
            "publica %d límite(s) y el mínimo es %d: un límite único no distingue "
            "el alcance de la excusa" % (len(items), LIMITES_MINIMOS)
        )

    for indice, (etiqueta_item, contenido) in enumerate(items, 1):
        texto = texto_visible(contenido)
        if len(texto.split()) < PALABRAS_MINIMAS:
            fallos.append(
                "el límite %d no dice nada verificable: %r" % (indice, texto)
            )
        if not contiene_negacion(texto):
            fallos.append(
                "el límite %d no contiene una negación explícita: %r"
                % (indice, texto[:80])
            )
        clave_item = clave_de_idioma(etiqueta_item)
        if clave_item:
            fallos.extend(cobertura(html, clave_item, "el límite %d" % indice))

    return fallos, len(items)


def revisar_readmes(raiz):
    """Los README tienen que citar la regla; una regla sin lector no existe."""
    fallos = []
    for nombre in READMES:
        ruta = raiz / nombre
        if not ruta.is_file():
            fallos.append("%s no existe y es donde se anuncia la regla" % nombre)
            continue
        if CITA_OBLIGATORIA not in ruta.read_text(encoding="utf-8"):
            fallos.append(
                "%s no cita %s: la regla no está anunciada donde se lee"
                % (nombre, CITA_OBLIGATORIA)
            )
    return fallos


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Exige que cada página del escaparate declare lo que no prueba."
    )
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Raíz del escaparate (por defecto, el padre de tools/).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Publica el censo en JSON en vez de la tabla legible.",
    )
    argumentos = parser.parse_args(argv)
    raiz = Path(argumentos.root).resolve()

    carpeta_demos = raiz / "demo"
    if not carpeta_demos.is_dir():
        print("RC 2 · NO_MEDIDO: no existe %s" % carpeta_demos, file=sys.stderr)
        return RC_NO_MEDIDO

    paginas = sorted(
        ruta / "index.html" for ruta in carpeta_demos.iterdir() if ruta.is_dir()
    )
    if not paginas:
        print("RC 2 · NO_MEDIDO: %s no contiene demos" % carpeta_demos, file=sys.stderr)
        return RC_NO_MEDIDO

    fallos = []
    censo = []
    sin_pagina = 0
    for pagina in paginas:
        nombre = "%s/%s" % (pagina.parent.parent.name, pagina.parent.name)
        if not pagina.is_file():
            fallos.append("%s no tiene index.html" % nombre)
            sin_pagina += 1
            censo.append({"pagina": nombre, "limites": None, "fallos": ["falta index.html"]})
            continue
        fallos_pagina, limites = revisar_pagina(pagina)
        censo.append({"pagina": nombre, "limites": limites, "fallos": fallos_pagina})
        fallos.extend("%s: %s" % (nombre, f) for f in fallos_pagina)

    fallos.extend(revisar_readmes(raiz))

    if argumentos.json:
        print(json.dumps({"censo": censo, "fallos": fallos}, ensure_ascii=False, indent=2))
    else:
        for fila in censo:
            limites = "?" if fila["limites"] is None else fila["limites"]
            estado = "OK" if not fila["fallos"] else "%d fallo(s)" % len(fila["fallos"])
            print("%-38s limites=%s  %s" % (fila["pagina"], limites, estado))
        for nombre in READMES:
            estado = "no citado" if any(nombre in f for f in fallos) else "cita la regla"
            print("%-38s %s" % (nombre, estado))

    if fallos:
        if sin_pagina and len(fallos) == sin_pagina:
            codigo = RC_SIN_PAGINA
        else:
            codigo = RC_VIOLACION
        print("", file=sys.stderr)
        for fallo in fallos:
            print("  ✗ " + fallo, file=sys.stderr)
        print(
            "RC %d · %d fallo(s): una página que no declara su límite no es un instrumento"
            % (codigo, len(fallos)),
            file=sys.stderr,
        )
        return codigo

    print(
        "RC 0 · %d páginas declaran lo que no prueban, en todos sus idiomas"
        % len(paginas)
    )
    return RC_OK


if __name__ == "__main__":
    sys.exit(main())
