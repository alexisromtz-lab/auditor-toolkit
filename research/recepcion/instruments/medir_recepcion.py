#!/usr/bin/env python3
"""medir_recepcion.py — cuarta etapa del embudo: ¿alguien leyó lo publicado?

El embudo medido hasta hoy tiene tres etapas: candidato (AST) -> ruptura
(ejecucion real) -> consumidor (busqueda publica). Le falta la cuarta: la
recepcion. Sin ella, "estamos ganando presencia" es una opinion, no un estado.

Reglas que este instrumento NO negocia:

1. Un clon no es un lector. Se publica aparte y nunca se suma a los lectores.
   Medido 17-Nov-2026: 488 clones y 168 unicos frente a 2 vistas en 14 dias
   (ratio 244:1). Ninguna audiencia humana produce eso: es rastreo automatico.

2. En Zenodo, la clave agregada `downloads` de una version hereda el total del
   concepto. La cifra propia de la version es `version_downloads`. Usar la
   primera en una tabla por version cuenta doble. Medido 17-Nov-2026: v0.2.0
   declara downloads=1 y version_downloads=0 -- el zip nuevo no se ha
   descargado nunca, y el 1 es del v0.1.0.

3. `clones` ya contiene `clones_unicos`: sumarlos inventa clones que no
   existen. Se publican en dos clases distintas y no se agregan entre si.

4. Superficie ilegible => NO_MEDIDO. Nunca 0. Un cero por fallo de red es la
   mentira estadistica que este corpus prohibe.

5. dev.to es una superficie DISTINTA de github y zenodo. Sus clases son
   LECTOR_DEVTO y SENAL_DEVTO y NO se suman a LECTOR/SENAL. Motivo medido: quien
   lee el articulo no es quien vio el repositorio. Sumarlos inventa una
   audiencia; y como `page_views_count` exige credencial de autor, sumarlo
   degradaria el LECTOR medido (2) a NO_MEDIDO y borraria la linea base.

6. `page_views_count` de dev.to solo viaja con llave de autor. Sin
   DEVTO_API_KEY no hay cifra: NO_MEDIDO, jamas 0. Las reacciones y los
   comentarios si son publicos y se miden igual.

7. Ninguna fila certifica que la pieza este publicada si no se mide. La fila
   ESTADO_PIEZA publica `publicado` y `horas_desde_publicacion` para que la
   ventana de una prediccion sea auditable desde la tabla y no desde la prosa.
   Medido 17-Nov-2026: un pre-registro declaro "la publicacion no ha ocurrido"
   365 s despues de que ocurriera.

8. La cabecera se escribe una sola vez. Un TSV append-only con dos cabeceras y
   una linea en blanco parte cualquier parser. Medido 17-Nov-2026: RECEPCION.tsv
   tenia cabecera en la linea 1 y en la 12.

Uso:
    medir_recepcion.py --recid 24323318 --repo alexisromtz-lab/auditor-toolkit --articulo 5059635
    medir_recepcion.py --recid 24323318 --repo alexisromtz-lab/auditor-toolkit
    medir_recepcion.py --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

ESPERA_S = 20
VENTANA_GITHUB = "14d"       # la API de trafico devuelve una ventana movil
VENTANA_ZENODO = "lifetime"  # los stats de Zenodo son acumulados
VENTANA_DEVTO = "lifetime"   # reacciones y comentarios son acumulados

MEDIDO = "MEDIDO"
NO_MEDIDO = "NO_MEDIDO"


# ---------------------------------------------------------------- transporte


def _json_remoto(url: str) -> dict:
    peticion = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "platino-recepcion/1"},
    )
    with urllib.request.urlopen(peticion, timeout=ESPERA_S) as respuesta:
        return json.loads(respuesta.read().decode("utf-8"))


def _json_gh(ruta: str) -> dict | None:
    """GitHub exige credencial; si no la hay, devuelve None (NO_MEDIDO)."""
    try:
        proceso = subprocess.run(
            ["gh", "api", f"repos/{ruta}"],
            capture_output=True,
            text=True,
            timeout=ESPERA_S,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proceso.returncode != 0:
        return None
    try:
        return json.loads(proceso.stdout)
    except json.JSONDecodeError:
        return None


# ------------------------------------------------------------------ lectura


def leer_zenodo(recid: int) -> list[dict]:
    """Una fila por version. Usa version_* y no la clave agregada."""
    documento = _json_remoto(f"https://zenodo.org/api/records/{recid}/versions")
    filas = []
    for entrada in documento.get("hits", {}).get("hits", []):
        metadatos = entrada.get("metadata", {}) or {}
        stats = entrada.get("stats", {}) or {}
        filas.append(
            {
                "id": entrada.get("id"),
                "version": metadatos.get("version") or "NO_ETIQUETADA",
                "doi": entrada.get("doi"),
                "descargas": stats.get("version_downloads"),
                "vistas": stats.get("version_views"),
            }
        )
    return filas


def leer_github(repo: str) -> dict:
    base = _json_gh(repo)
    vistas = _json_gh(f"{repo}/traffic/views")
    clones = _json_gh(f"{repo}/traffic/clones")
    return {
        "estrellas": None if base is None else base.get("stargazers_count"),
        "forks": None if base is None else base.get("forks_count"),
        "vistas": None if vistas is None else vistas.get("count"),
        "vistas_unicas": None if vistas is None else vistas.get("uniques"),
        "clones": None if clones is None else clones.get("count"),
        "clones_unicos": None if clones is None else clones.get("uniques"),
    }


def _vistas_devto(articulo: int, publico: dict) -> int | None:
    """`page_views_count` solo viaja con llave de autor. Sin llave, NO_MEDIDO."""
    if publico.get("page_views_count") is not None:
        return publico["page_views_count"]
    llave = os.environ.get("DEVTO_API_KEY")
    if not llave:
        return None
    try:
        peticion = urllib.request.Request(
            f"https://dev.to/api/articles/{articulo}",
            headers={"Accept": "application/json", "api-key": llave,
                     "User-Agent": "platino-recepcion/1"},
        )
        with urllib.request.urlopen(peticion, timeout=ESPERA_S) as respuesta:
            return json.loads(respuesta.read().decode("utf-8")).get("page_views_count")
    except Exception:
        return None


def leer_devto(articulo: int) -> dict:
    """Superficie publica: reacciones y comentarios. Vistas exigen credencial.

    `alcanzable` separa "no publicado" (0 medido) de "no leido" (NO_MEDIDO).
    """
    try:
        publico = _json_remoto(f"https://dev.to/api/articles/{articulo}")
    except Exception:  # inalcanzable o 404: NO_MEDIDO, no cero
        return {"alcanzable": False, "publicado": None, "reacciones": None,
                "comentarios": None, "vistas": None}
    return {
        "alcanzable": True,
        "publicado": publico.get("published_at"),
        "reacciones": publico.get("positive_reactions_count"),
        "comentarios": publico.get("comments_count"),
        "vistas": _vistas_devto(articulo, publico),
    }


# ---------------------------------------------------------------- agregacion


def celda(superficie: str, metrica: str, valor, unidad: str, clase: str, ventana: str):
    """Una fila de la tabla. valor None => NO_MEDIDO, jamas 0."""
    return {
        "superficie": superficie,
        "metrica": metrica,
        "valor": valor,
        "unidad": unidad,
        "clase": clase,
        "ventana": ventana,
        "estado": NO_MEDIDO if valor is None else MEDIDO,
    }


def _horas_desde(marca_iso: str | None) -> float | None:
    """Horas transcurridas desde una marca ISO. Hace auditable la ventana."""
    if not marca_iso:
        return None
    try:
        marca = datetime.fromisoformat(marca_iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if marca.tzinfo is None:
        marca = marca.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - marca).total_seconds() / 3600.0, 2)


def construir_filas(zenodo: list[dict], github: dict, devto: dict | None = None) -> list[dict]:
    filas = []
    for version in zenodo:
        etiqueta = f"zenodo/{version['version']}"
        filas.append(
            celda(etiqueta, "descargas_zip", version["descargas"], "descarga", "DESCARGA", VENTANA_ZENODO)
        )
        filas.append(
            celda(etiqueta, "vistas_registro", version["vistas"], "vista", "LECTOR", VENTANA_ZENODO)
        )
    filas.append(celda("github", "vistas_pagina", github["vistas"], "vista", "LECTOR", VENTANA_GITHUB))
    filas.append(celda("github", "estrellas", github["estrellas"], "estrella", "SENAL", VENTANA_GITHUB))
    filas.append(celda("github", "forks", github["forks"], "fork", "SENAL", VENTANA_GITHUB))
    # Los clones se miden, se publican y NO se suman: no son lectores.
    filas.append(celda("github", "clones", github["clones"], "clon", "CLON", VENTANA_GITHUB))
    filas.append(celda("github", "clones_unicos", github["clones_unicos"], "clon_unico", "CLON_UNICO", VENTANA_GITHUB))
    if devto is not None:
        # Clases propias: no se suman a LECTOR/SENAL (ver regla 5 del docstring).
        filas.append(celda("devto", "vistas_pagina", devto["vistas"], "vista", "LECTOR_DEVTO", VENTANA_DEVTO))
        filas.append(celda("devto", "reacciones", devto["reacciones"], "reaccion", "SENAL_DEVTO", VENTANA_DEVTO))
        filas.append(celda("devto", "comentarios", devto["comentarios"], "comentario", "SENAL_DEVTO", VENTANA_DEVTO))
        if devto["alcanzable"]:
            publicado = 1 if devto["publicado"] else 0
            horas = _horas_desde(devto["publicado"])
        else:
            publicado = None
            horas = None
        filas.append(celda("devto", "publicado", publicado, "booleano", "ESTADO_PIEZA", VENTANA_DEVTO))
        filas.append(celda("devto", "horas_desde_publicacion", horas, "hora", "ESTADO_PIEZA", VENTANA_DEVTO))
    return filas


CLASES_CONTABLES = ("LECTOR", "DESCARGA", "SENAL", "CLON", "CLON_UNICO",
                    "LECTOR_DEVTO", "SENAL_DEVTO")


def totalizar(filas: list[dict], pedidas=None) -> dict:
    """Suma por clase. Un NO_MEDIDO contamina su total con None, no con 0.

    Con `pedidas` se publica solo lo que se pregunto: una clase pedida sin filas
    es NO_MEDIDO, jamas 0. Un cero de poblacion vacia no es un cero medido.
    """
    presentes = {f["clase"] for f in filas if f["clase"] in CLASES_CONTABLES}
    clases = set(CLASES_CONTABLES) if pedidas is None else (presentes | set(pedidas))
    totales: dict[str, int | None] = {}
    for clase in CLASES_CONTABLES:
        if clase not in clases:
            continue
        del_grupo = [f for f in filas if f["clase"] == clase]
        if any(f["estado"] == NO_MEDIDO for f in del_grupo):
            totales[clase] = None
        elif del_grupo:
            totales[clase] = sum(f["valor"] for f in del_grupo)
        else:
            totales[clase] = None
    return totales


# ------------------------------------------------------------------ salidas

CABECERA = "fecha_hora\tsuperficie\tmetrica\tvalor\tunidad\tclase\tventana\testado"


def a_tsv(filas: list[dict], momento: str, con_cabecera: bool = True) -> str:
    """Cabecera solo la primera vez: dos cabeceras parten cualquier parser."""
    lineas = [CABECERA] if con_cabecera else []
    for fila in filas:
        valor = "NO_MEDIDO" if fila["valor"] is None else str(fila["valor"])
        lineas.append(
            "\t".join(
                [
                    momento,
                    fila["superficie"],
                    fila["metrica"],
                    valor,
                    fila["unidad"],
                    fila["clase"],
                    fila["ventana"],
                    fila["estado"],
                ]
            )
        )
    return "\n".join(lineas) + "\n"


def imprimir_resumen(filas: list[dict], totales: dict) -> None:
    ancho = max(len(f["superficie"]) for f in filas) + 2
    print(f"{'superficie'.ljust(ancho)}{'metrica'.ljust(18)}{'valor'.rjust(10)}  {'ventana'.ljust(9)}estado")
    print("-" * (ancho + 46))
    for fila in filas:
        valor = "NO_MEDIDO" if fila["valor"] is None else f"{fila['valor']:,}"
        print(
            fila["superficie"].ljust(ancho)
            + fila["metrica"].ljust(18)
            + valor.rjust(10)
            + "  "
            + fila["ventana"].ljust(9)
            + fila["estado"]
        )
    print()
    for clase, valor in totales.items():
        texto = "NO_MEDIDO" if valor is None else f"{valor:,}"
        print(f"  {clase.ljust(20)}{texto.rjust(10)}")
    print()
    print("  CLON y CLON_UNICO se publican aparte: NO se suman a LECTOR")
    print("  ni entre si (un unico ya esta contenido en el conteo).")
    print("  LECTOR_DEVTO y SENAL_DEVTO son otra superficie y NO se suman a LECTOR/SENAL.")


# --------------------------------------------------------------- self-test


def self_test() -> int:
    fallos = []

    def comprobar(nombre: str, obtenido, esperado) -> None:
        if obtenido != esperado:
            fallos.append(f"{nombre}: esperado {esperado!r}, obtenido {obtenido!r}")

    # 1. Cero medido es un hecho, no una ausencia.
    ceros = [celda("z", "descargas_zip", 0, "descarga", "DESCARGA", VENTANA_ZENODO)]
    comprobar("cero medido", totalizar(ceros)["DESCARGA"], 0)
    comprobar("cero estado", ceros[0]["estado"], MEDIDO)

    # 2. Fallo de red => NO_MEDIDO, nunca 0.
    caido = [celda("z", "descargas_zip", None, "descarga", "DESCARGA", VENTANA_ZENODO)]
    comprobar("fallo total", totalizar(caido)["DESCARGA"], None)
    comprobar("fallo estado", caido[0]["estado"], NO_MEDIDO)

    # 3. Un NO_MEDIDO contaminado con ceros sigue siendo NO_MEDIDO.
    mixto = [
        celda("a", "vistas", 5, "vista", "LECTOR", VENTANA_ZENODO),
        celda("b", "vistas", None, "vista", "LECTOR", VENTANA_ZENODO),
    ]
    comprobar("mixto", totalizar(mixto)["LECTOR"], None)

    # 4. Los clones nunca entran en LECTOR.
    github = {"estrellas": 0, "forks": 0, "vistas": 2, "vistas_unicas": 2, "clones": 488, "clones_unicos": 168}
    filas = construir_filas([], github)
    totales = totalizar(filas)
    comprobar("clon fuera de lector", totales["LECTOR"], 2)
    comprobar("clon conteo", totales["CLON"], 488)
    comprobar("clon unico", totales["CLON_UNICO"], 168)
    comprobar("no hay clase agregada de clones", "CLON_NO_ATRIBUIDO" in totales, False)

    # 5. Por version se usa version_*, no la clave agregada heredada.
    heredada = [{"id": 1, "version": "v0.2.0", "doi": "x", "descargas": 0, "vistas": 0}]
    filas5 = construir_filas(heredada, {"estrellas": None, "forks": None, "vistas": None,
                                        "vistas_unicas": None, "clones": None, "clones_unicos": None})
    comprobar("version propia", filas5[0]["valor"], 0)
    comprobar("github caido", totales_github_caido(filas5), None)

    # 6. dev.to inalcanzable NO contamina LECTOR ni se lee como cero.
    caido_devto = {"alcanzable": False, "publicado": None, "reacciones": None,
                   "comentarios": None, "vistas": None}
    filas6 = construir_filas([], github, caido_devto)
    totales6 = totalizar(filas6)
    comprobar("devto no contamina lector", totales6["LECTOR"], 2)
    comprobar("devto caido", totales6["LECTOR_DEVTO"], None)
    comprobar("devto publicado NO_MEDIDO", [f["estado"] for f in filas6
                                            if f["metrica"] == "publicado"][0], NO_MEDIDO)

    # 7. Reacciones de dev.to y estrellas de github son poblaciones distintas.
    vivo_devto = {"alcanzable": True, "publicado": "2026-11-17T19:24:53Z",
                  "reacciones": 7, "comentarios": 2, "vistas": None}
    filas7 = construir_filas([], github, vivo_devto)
    totales7 = totalizar(filas7)
    comprobar("senal github intacta", totales7["SENAL"], 0)
    comprobar("senal devto propia", totales7["SENAL_DEVTO"], 9)
    comprobar("vistas devto sin llave", totales7["LECTOR_DEVTO"], None)
    comprobar("publicado medido", [f["valor"] for f in filas7
                                   if f["metrica"] == "publicado"][0], 1)

    # 8. Clase pedida sin filas => NO_MEDIDO. Un cero de poblacion vacia no es
    #    un cero medido (defecto medido en el control negativo de 17-Nov-2026).
    comprobar("clase pedida sin filas", totalizar(ceros, {"DESCARGA", "CLON_UNICO"})["CLON_UNICO"], None)
    comprobar("clase no pedida no se publica", "SENAL" in totalizar(ceros, {"DESCARGA"}), False)

    # 9. La cabecera se escribe una sola vez: dos cabeceras parten cualquier
    #    parser (defecto medido en RECEPCION.tsv el 17-Nov-2026, lineas 1 y 12).
    comprobar("cabecera primera vez", a_tsv(ceros, "t").count(CABECERA), 1)
    comprobar("cabecera anexada", a_tsv(ceros, "t", con_cabecera=False).count(CABECERA), 0)

    if fallos:
        print(f"SELF-TEST FALLA: {len(fallos)} defecto(s)")
        for fallo in fallos:
            print(f"  - {fallo}")
        return 1
    print("SELF-TEST OK: 15/15 (cero medido, fallo NO_MEDIDO, mixto, clon aislado, clon no aditivo, "
          "version propia, github caido, devto no contamina, devto caido, devto senal propia, devto publicado, "
          "clase pedida sin filas, clase no pedida, cabecera unica, cabecera anexada)")
    return 0


def totales_github_caido(filas: list[dict]) -> int | None:
    return totalizar(filas)["LECTOR"]


# --------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mide la recepcion de una pieza publicada.")
    parser.add_argument("--recid", type=int, help="recid de Zenodo (el de la version mas reciente)")
    parser.add_argument("--repo", help="repositorio GitHub en forma owner/nombre")
    parser.add_argument("--articulo", type=int, help="id numerico del articulo en dev.to")
    parser.add_argument("--tsv", help="ruta donde anexar las filas")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.recid and not args.repo and not args.articulo:
        parser.error("hace falta --recid, --repo, --articulo o --self-test")

    zenodo: list[dict] = []
    if args.recid:
        try:
            zenodo = leer_zenodo(args.recid)
        except Exception:  # superficie ilegible: NO_MEDIDO, no cero
            zenodo = [{"version": "NO_LEIDO", "doi": None, "descargas": None, "vistas": None}]

    github = {"estrellas": None, "forks": None, "vistas": None,
              "vistas_unicas": None, "clones": None, "clones_unicos": None}
    if args.repo:
        github = leer_github(args.repo)

    devto = leer_devto(args.articulo) if args.articulo else None

    filas = construir_filas(zenodo, github, devto)
    momento = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pedidas = set()
    if args.recid:
        pedidas |= {"DESCARGA", "LECTOR"}
    if args.repo:
        pedidas |= {"LECTOR", "SENAL", "CLON", "CLON_UNICO"}
    if args.articulo:
        pedidas |= {"LECTOR_DEVTO", "SENAL_DEVTO"}
    imprimir_resumen(filas, totalizar(filas, pedidas))

    if args.tsv:
        nuevo = not os.path.exists(args.tsv)
        with open(args.tsv, "a", encoding="utf-8") as salida:
            salida.write(a_tsv(filas, momento, con_cabecera=nuevo))
        print(f"\n  filas anexadas a {args.tsv}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
