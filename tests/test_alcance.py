"""HUELLA-ALCANCE-TEST-20261117 — la etapa 0 del embudo, con sus dos controles.

Un lector de puertas que solo sabe decir rojo no ha demostrado que sepa decir
verde, y uno que imprime "0/1" cuando no pudo leer la pieza miente con la misma
cara que un cero de poblacion vacia. Aqui se ejecuta su self-test y se comprueba
que la tabla publicada conserva las dos propiedades que el defecto del
17-Nov-2026 volvio obligatorias: una pieza que nombra el objeto sin enlazarlo es
HUERFANO, y una pieza ilegible es NO_MEDIDO, nunca HUERFANO.
"""
from __future__ import annotations

import csv
import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CARPETA = REPO_ROOT / "research" / "alcance"
INSTRUMENTO = CARPETA / "instruments" / "medir_alcance.py"
TSV = CARPETA / "data" / "ALCANCE.tsv"
COLUMNAS = [
    "fecha_hora",
    "pieza",
    "huella",
    "objeto",
    "estado",
    "detalle",
    "veredicto",
    "origen",
]
ESTADOS = {"ENLACE", "SOLO_TEXTO", "HUERFANO", "NO_MEDIDO"}
VEREDICTOS = {"ALCANZABLE", "PARCIAL", "SIN_ALCANCE", "NO_MEDIDO"}
ORIGENES = {"divergente", "sin_divergencia", "sin_origen", "origen_ilegible"}
NO_MEDIDO = "NO_MEDIDO"
OBJETO = "https://github.com/alexisromtz-lab/auditor-toolkit"


def _cargar_modulo():
    especificacion = importlib.util.spec_from_file_location("medir_alcance", INSTRUMENTO)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def _filas() -> list[dict]:
    with TSV.open(encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo, delimiter="\t"))


class TestAlcance(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.m = _cargar_modulo()

    def test_self_test_del_instrumento(self) -> None:
        proceso = subprocess.run(
            [sys.executable, str(INSTRUMENTO), "--self-test"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(proceso.returncode, 0, proceso.stdout + proceso.stderr)
        # La forma, no el numero: una regla nueva no puede romper esta prueba,
        # pero perder una vieja si. Un literal 32/32 se desactualiza en silencio.
        coincidencia = re.search(r"SELF-TEST OK: (\d+)/(\d+)", proceso.stdout)
        self.assertIsNotNone(coincidencia, proceso.stdout)
        aprobadas, totales = (int(grupo) for grupo in coincidencia.groups())
        self.assertEqual(aprobadas, totales, "una regla del self-test no paso")
        self.assertGreaterEqual(totales, 32, "se perdieron reglas del self-test")

    def test_tsv_tiene_una_sola_cabecera(self) -> None:
        texto = TSV.read_text(encoding="utf-8")
        self.assertEqual(
            texto.count("fecha_hora\tpieza"), 1, "dos cabeceras parten cualquier parser"
        )

    def test_tsv_bien_formado(self) -> None:
        with TSV.open(encoding="utf-8", newline="") as archivo:
            filas = list(csv.reader(archivo, delimiter="\t"))
        self.assertEqual(filas[0], COLUMNAS)
        for numero, fila in enumerate(filas, 1):
            self.assertEqual(len(fila), len(COLUMNAS), f"la fila {numero} no tiene 8 columnas")

    def test_estados_publicados_son_del_vocabulario(self) -> None:
        filas = _filas()
        self.assertTrue(filas)
        for fila in filas:
            self.assertIn(fila["estado"], ESTADOS)
            self.assertIn(fila["veredicto"], VEREDICTOS)
            self.assertIn(
                fila["detalle"],
                {
                    "markdown",
                    "autolink",
                    "referencia",
                    "url_desnuda",
                    "referencia_sin_uso",
                    "code_span",
                    "imagen",
                    "fence",
                    "mencion",
                    "ausente",
                    "ilegible",
                    "objeto_vacio",
                    "html",
                },
            )
            self.assertIn(fila["origen"], ORIGENES)

    def test_nombrar_no_es_enlazar(self) -> None:
        """El defecto medido: el nombre entre acentos graves no abre la puerta."""
        self.assertEqual(
            self.m.clasificar("mira `auditor-toolkit` y ya", OBJETO),
            ("SOLO_TEXTO", "code_span"),
        )
        self.assertEqual(
            self.m.clasificar("[repo](%s)" % OBJETO, OBJETO), ("ENLACE", "markdown")
        )

    def test_url_desnuda_no_es_enlace(self) -> None:
        """Falso rojo deliberado: un falso verde autoriza publicar huerfano."""
        self.assertEqual(self.m.clasificar("en %s" % OBJETO, OBJETO), ("SOLO_TEXTO", "url_desnuda"))

    def test_imagen_no_es_puerta(self) -> None:
        self.assertEqual(
            self.m.clasificar("![portada](%s)" % OBJETO, OBJETO), ("SOLO_TEXTO", "imagen")
        )

    def test_subruta_alcanza_y_hermano_no(self) -> None:
        self.assertTrue(self.m._alcanza(OBJETO + "/tree/main/research", OBJETO))
        self.assertTrue(self.m._alcanza(OBJETO + "/", OBJETO))
        self.assertTrue(self.m._alcanza("http://" + OBJETO.split("//", 1)[1], OBJETO))
        self.assertFalse(self.m._alcanza(OBJETO + "-extra", OBJETO))

    def test_pieza_ilegible_es_no_medido(self) -> None:
        """Un cero de poblacion vacia no es un defecto del objeto."""
        self.assertEqual(self.m.clasificar(None, OBJETO), ("NO_MEDIDO", "ilegible"))
        self.assertEqual(self.m.veredicto(["NO_MEDIDO"]), NO_MEDIDO)
        self.assertEqual(self.m.veredicto([]), NO_MEDIDO)

    def test_alcance_no_imprime_cero_de_poblacion_vacia(self) -> None:
        filas = self.m.construir_filas("devto/1", None, [OBJETO])
        linea = self.m.linea_alcance(filas)
        self.assertIn(NO_MEDIDO, linea)
        self.assertNotIn("0/", linea)

    def test_origen_divergente_declara_la_copia(self) -> None:
        """La copia no es el objeto: si el original enlaza y la pieza no, se dice."""
        filas = self.m.construir_filas(
            "devto/1", "`auditor-toolkit`", [OBJETO], origen_texto="[r](%s)" % OBJETO
        )
        self.assertEqual(filas[0]["origen"], "divergente")
        ilegible = self.m.construir_filas("devto/1", "x", [OBJETO], None, origen_pedido=True)
        self.assertEqual(ilegible[0]["origen"], "origen_ilegible")
        self.assertEqual(filas[0]["veredicto"], "SIN_ALCANCE")
        sin_origen = self.m.construir_filas("devto/1", "[r](%s)" % OBJETO, [OBJETO])
        self.assertEqual(sin_origen[0]["origen"], "sin_origen")

    def test_rc_es_el_veredicto(self) -> None:
        """La compuerta no devuelve 0 si la pieza no abre la puerta."""
        import tempfile

        with tempfile.TemporaryDirectory() as carpeta:
            huerfana = Path(carpeta) / "huerfana.md"
            huerfana.write_text("mira `auditor-toolkit` y ya", encoding="utf-8")
            alcanzable = Path(carpeta) / "alcanzable.md"
            alcanzable.write_text("mira [el repo](%s)" % OBJETO, encoding="utf-8")

            codigos = []
            for pieza in (huerfana, alcanzable):
                proceso = subprocess.run(
                    [sys.executable, str(INSTRUMENTO), "--pieza", str(pieza), "--debe", OBJETO],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                codigos.append(proceso.returncode)
                self.assertIn("VEREDICTO", proceso.stdout, proceso.stderr)

        self.assertEqual(codigos[0], 1, "una pieza huerfana no puede salir con RC 0")
        self.assertEqual(codigos[1], 0, "una pieza alcanzable debe salir con RC 0")

    def test_la_fila_del_articulo_vivo_se_conserva(self) -> None:
        """La tabla es append-only: corregir el articulo agrega fila, no edita esta.

        Si esta prueba cae, alguien reescribio la historia de la medicion en vez
        de anotar la nueva.
        """
        huerfanas = [
            f for f in _filas() if f["pieza"] == "devto/5059635" and f["estado"] == "SOLO_TEXTO"
        ]
        self.assertTrue(huerfanas, "la fila medida del articulo vivo desaparecio de la tabla")
        self.assertEqual(huerfanas[0]["detalle"], "code_span")
        self.assertEqual(huerfanas[0]["origen"], "divergente")

    def test_la_transicion_queda_anexada(self) -> None:
        """19:56 huerfano, 20:05 alcanzable: la correccion es una fila nueva."""
        filas = [
            f for f in _filas() if f["pieza"] in ("devto/5059635", "devto/5059635#render")
        ]
        self.assertEqual({f["estado"] for f in filas}, {"SOLO_TEXTO", "ENLACE"})
        fechas = [f["fecha_hora"] for f in filas]
        self.assertEqual(fechas, sorted(fechas), "la tabla dejo de estar ordenada por tiempo")

    def test_el_render_es_un_lector_no_un_buscador(self) -> None:
        """Buscar `href=` en el HTML crudo da falso verde: dentro de <code> tambien aparece."""
        self.assertEqual(
            self.m.clasificar_html('<p><a href="%s">el repo</a></p>' % OBJETO, OBJETO),
            ("ENLACE", "html"),
        )
        escapado = '<p><code>&lt;a href="%s"&gt;x&lt;/a&gt;</code></p>' % OBJETO
        self.assertEqual(self.m.clasificar_html(escapado, OBJETO), ("SOLO_TEXTO", "code_span"))
        nombre = "<p>mira <code>auditor-toolkit</code> y ya</p>"
        self.assertEqual(self.m.clasificar_html(nombre, OBJETO), ("SOLO_TEXTO", "code_span"))

    def test_render_ilegible_es_no_medido(self) -> None:
        self.assertEqual(self.m.clasificar_html(None, OBJETO), ("NO_MEDIDO", "ilegible"))
        self.assertEqual(self.m.clasificar_html("<p>x</p>", ""), ("NO_MEDIDO", "objeto_vacio"))

    def test_origenes_es_un_vocabulario_con_lector(self) -> None:
        """La etiqueta que el instrumento escribe es la que esta prueba declara."""
        self.assertEqual(set(self.m.ORIGENES), ORIGENES)
        self.assertEqual(len(set(self.m.ORIGENES)), len(self.m.ORIGENES), "etiquetas repetidas")
        self.assertFalse(set(self.m.ORIGENES) & set(self.m.ESTADOS), "origen no es estado")
        ambos = self.m.construir_filas(
            "devto/1", "[r](%s)" % OBJETO, [OBJETO], origen_texto="[r](%s)" % OBJETO
        )
        self.assertEqual(ambos[0]["origen"], "sin_divergencia")

    def test_render_de_punta_a_punta_sobre_archivo(self) -> None:
        with tempfile.TemporaryDirectory() as carpeta:
            pieza = Path(carpeta) / "pieza.html"
            pieza.write_text('<p><a href="%s">repo</a></p>' % OBJETO, encoding="utf-8")
            proceso = subprocess.run(
                [sys.executable, str(INSTRUMENTO), "--pieza", str(pieza), "--render", "--debe", OBJETO],
                capture_output=True,
                text=True,
                timeout=120,
            )
        self.assertEqual(proceso.returncode, 0, proceso.stdout + proceso.stderr)
        self.assertIn("#render", proceso.stdout)
        self.assertIn("ENLACE", proceso.stdout)


    def test_especificacion_reconoce_las_superficies(self) -> None:
        """El despacho se decide antes de la red: se puede probar sin tocar el mundo."""
        casos = {
            "5059635": ("devto", ("5059635",)),
            "devto:5059635": ("devto", ("5059635",)),
            "zenodo:24323318": ("zenodo", ("24323318",)),
            "gh:alexisromtz-lab/auditor-toolkit": ("gh", ("alexisromtz-lab/auditor-toolkit", "")),
            "gh:alexisromtz-lab/auditor-toolkit@v0.2.0": (
                "gh",
                ("alexisromtz-lab/auditor-toolkit", "v0.2.0"),
            ),
            "https://example.org/x": ("url", ("https://example.org/x",)),
            "research/alcance/data/ALCANCE.tsv": ("archivo", ("research/alcance/data/ALCANCE.tsv",)),
            "devto:abc": ("desconocida", ()),
            "zenodo:": ("desconocida", ()),
            "gh:sin-barra": ("desconocida", ()),
        }
        for pieza, esperado in casos.items():
            with self.subTest(pieza=pieza):
                self.assertEqual(self.m.especificacion(pieza), esperado)

    def test_peldano_que_no_existe_es_rc_20(self) -> None:
        """GitHub releases no publica `body_html`: pedirlo no es NO_MEDIDO, es un error.

        Un NO_MEDIDO ahi promete una medicion que no puede llegar nunca.
        """
        proceso = subprocess.run(
            [
                sys.executable,
                str(INSTRUMENTO),
                "--pieza",
                "gh:alexisromtz-lab/auditor-toolkit@v0.2.0",
                "--render",
                "--debe",
                OBJETO,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(proceso.returncode, 20, proceso.stdout + proceso.stderr)
        self.assertIn("no expone body_html", proceso.stderr)
        self.assertNotIn("NO_MEDIDO", proceso.stdout)

    def test_puerta_lateral_no_vuelve_verde_el_cuerpo(self) -> None:
        """El campo de codigo del deposito es otra superficie: se publica aparte."""
        self.assertEqual(
            self.m.codigo_declarado({"metadata": {"custom": {"code:codeRepository": OBJETO}}}),
            [OBJETO],
        )
        self.assertEqual(self.m.identificadores_relacionados({"metadata": {"custom": {}}}), [])
        self.assertEqual(
            self.m.codigo_declarado({"metadata": {"custom": {"otro:campo": OBJETO}}}), []
        )


if __name__ == "__main__":
    unittest.main()
