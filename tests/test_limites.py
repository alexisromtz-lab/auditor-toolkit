"""El bloque de límites no se ruega: se exige, y esto lo demuestra.

Medido el `2026-11-14`: tres de las cuatro páginas del escaparate demostraban su
tesis y **no** decían qué dejaban fuera. El verificador de cada página miraba la
paridad numérica, nunca la existencia del bloque, así que borrarlo entero daba
`RC 0` en las cuatro.

Aqui se falsifica `tools/verificar_limites.py` por mutación sobre copias
temporales: cada caso borra **una** cosa de la página real y exige que el
verificador lo nombre. Si un caso queda verde, el verificador mide otra cosa.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFICADOR = REPO_ROOT / "tools" / "verificar_limites.py"
PAGINA = REPO_ROOT / "demo" / "clasificador-de-campos" / "index.html"
READMES = ("README.md", "README.es.md")


def correr(raiz: Path | None = None) -> subprocess.CompletedProcess[str]:
    argumentos = [sys.executable, str(VERIFICADOR)]
    if raiz is not None:
        argumentos += ["--root", str(raiz)]
    return subprocess.run(argumentos, capture_output=True, text=True, cwd=REPO_ROOT)


class CopiaDelEscaparate:
    """Una copia mutable del escaparate, fuera del repositorio."""

    def __init__(self) -> None:
        self._carpeta = tempfile.TemporaryDirectory()
        self.raiz = Path(self._carpeta.name)
        shutil.copytree(REPO_ROOT / "demo", self.raiz / "demo")
        for nombre in READMES:
            shutil.copy2(REPO_ROOT / nombre, self.raiz / nombre)

    @property
    def pagina(self) -> Path:
        return self.raiz / "demo" / "clasificador-de-campos" / "index.html"

    def __enter__(self) -> "CopiaDelEscaparate":
        return self

    def __exit__(self, *_excepcion) -> None:
        self._carpeta.cleanup()

    def mutar(self, ruta: Path, viejo: str, nuevo: str) -> None:
        texto = ruta.read_text(encoding="utf-8")
        if viejo not in texto:
            raise AssertionError("la mutación no encuentra su ancla: %r" % viejo[:60])
        ruta.write_text(texto.replace(viejo, nuevo, 1), encoding="utf-8")


class ElEscaparateRealTests(unittest.TestCase):
    def test_las_mutaciones_no_tocan_el_repositorio(self) -> None:
        """El banco muta copias: si mutara el sujeto, se mediría a sí mismo."""
        import hashlib

        antes = hashlib.sha256(PAGINA.read_bytes()).hexdigest()
        with CopiaDelEscaparate() as copia:
            copia.mutar(copia.pagina, '<section id="limites"', '<section id="alcance"')
            self.assertEqual(correr(copia.raiz).returncode, 1)
        despues = hashlib.sha256(PAGINA.read_bytes()).hexdigest()
        self.assertEqual(antes, despues, "una mutación escribió en la página real")

    def test_las_cuatro_paginas_declaran_su_limite(self) -> None:
        resultado = correr()
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("4 páginas declaran", resultado.stdout)

    def test_cada_pagina_publica_al_menos_dos_limites(self) -> None:
        resultado = correr()
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        for nombre in (
            "clasificador-de-campos",
            "nulo-con-dientes",
            "piso-de-deteccion",
            "umbral-economico",
        ):
            self.assertIn("demo/%s" % nombre, resultado.stdout)
        self.assertEqual(resultado.stdout.count("limites=2  OK"), 4)


class MutacionesTests(unittest.TestCase):
    """Cada una rompe una sola cosa y el verificador tiene que nombrarla."""

    def test_borrar_la_seccion_entera_queda_en_rojo(self) -> None:
        with CopiaDelEscaparate() as copia:
            copia.mutar(copia.pagina, '<section id="limites"', '<section id="alcance"')
            resultado = correr(copia.raiz)
            self.assertEqual(resultado.returncode, 1, resultado.stdout)
            self.assertIn("no declara lo que no prueba", resultado.stderr)

    def test_sin_data_limites_queda_en_rojo(self) -> None:
        with CopiaDelEscaparate() as copia:
            copia.mutar(copia.pagina, ' data-limites="2"', "")
            resultado = correr(copia.raiz)
            self.assertEqual(resultado.returncode, 1)
            self.assertIn("no declara data-limites", resultado.stderr)

    def test_un_solo_limite_no_basta(self) -> None:
        with CopiaDelEscaparate() as copia:
            copia.mutar(copia.pagina, '<section id="limites" data-limites="2">', '<section id="limites" data-limites="1">')
            copia.mutar(copia.pagina, '      <li data-i18n="lim_2">', '      <!-- ')
            copia.mutar(copia.pagina, "not that the class is right.</li>", "not that the class is right. -->")
            resultado = correr(copia.raiz)
            self.assertEqual(resultado.returncode, 1)
            self.assertIn("el mínimo es 2", resultado.stderr)

    def test_declarar_dos_y_publicar_uno_queda_en_rojo(self) -> None:
        with CopiaDelEscaparate() as copia:
            copia.mutar(copia.pagina, '      <li data-i18n="lim_2">', '      <!-- ')
            copia.mutar(copia.pagina, "not that the class is right.</li>", "not that the class is right. -->")
            resultado = correr(copia.raiz)
            self.assertEqual(resultado.returncode, 1)
            self.assertIn("declara 2 límites y publica 1", resultado.stderr)

    def test_un_limite_vacio_queda_en_rojo(self) -> None:
        with CopiaDelEscaparate() as copia:
            copia.mutar(
                copia.pagina,
                '<li data-i18n="lim_1">This page does not certify the 9+3 physical degrees of freedom '
                "of the field, nor a Maxwell solution; those stay <code>NO_MEDIDO</code>. It classifies, "
                "it does not solve.</li>",
                '<li data-i18n="lim_1"></li>',
            )
            resultado = correr(copia.raiz)
            self.assertEqual(resultado.returncode, 1)
            self.assertIn("no dice nada verificable", resultado.stderr)

    def test_un_limite_comentado_no_cuenta(self) -> None:
        """Un `<li>` con el texto dentro de un comentario no lo lee nadie."""
        with CopiaDelEscaparate() as copia:
            copia.mutar(
                copia.pagina,
                '<li data-i18n="lim_1">This page does not certify the 9+3 physical degrees of freedom '
                "of the field, nor a Maxwell solution; those stay <code>NO_MEDIDO</code>. It classifies, "
                "it does not solve.</li>",
                '<li data-i18n="lim_1"><!--This page does not certify the 9+3 physical degrees of '
                "freedom of the field, nor a Maxwell solution; those stay NO_MEDIDO. It classifies, "
                "it does not solve.--></li>",
            )
            resultado = correr(copia.raiz)
            self.assertEqual(resultado.returncode, 1)
            self.assertIn("no dice nada verificable", resultado.stderr)

    def test_un_limite_sin_negacion_queda_en_rojo(self) -> None:
        with CopiaDelEscaparate() as copia:
            copia.mutar(
                copia.pagina,
                "zero drift proves the two paths agree, not that the class is right.</li>",
                "zero drift proves that both readings agree with each other.</li>",
            )
            resultado = correr(copia.raiz)
            self.assertEqual(resultado.returncode, 1)
            self.assertIn("no contiene una negación explícita", resultado.stderr)

    def test_borrar_el_titulo_queda_en_rojo(self) -> None:
        with CopiaDelEscaparate() as copia:
            copia.mutar(
                copia.pagina,
                '    <h2 data-i18n="lim_titulo">What this page does not prove</h2>\n',
                "",
            )
            resultado = correr(copia.raiz)
            self.assertEqual(resultado.returncode, 1)
            self.assertIn("no tiene <h2>", resultado.stderr)

    def test_una_traduccion_que_falta_queda_en_rojo(self) -> None:
        with CopiaDelEscaparate() as copia:
            copia.mutar(
                copia.pagina,
                "      lim_1: 'This page does not certify the 9+3 physical degrees of freedom of the field, "
                "nor a Maxwell solution; those stay <code>NO_MEDIDO</code>. It classifies, it does not solve.',\n",
                "",
            )
            resultado = correr(copia.raiz)
            self.assertEqual(resultado.returncode, 1)
            self.assertIn("falta en al menos una traducción", resultado.stderr)

    def test_un_readme_sin_la_cita_queda_en_rojo(self) -> None:
        with CopiaDelEscaparate() as copia:
            copia.mutar(copia.raiz / "README.es.md", "`tools/verificar_limites.py`", "`tools/otro.py`")
            resultado = correr(copia.raiz)
            self.assertEqual(resultado.returncode, 1)
            self.assertIn("README.es.md no cita verificar_limites.py", resultado.stderr)


class CodigosTests(unittest.TestCase):
    """Un cero tiene que significar algo: fuera del sujeto no hay cero."""

    def test_sin_demos_es_no_medido_y_no_es_cero(self) -> None:
        with CopiaDelEscaparate() as copia:
            shutil.rmtree(copia.raiz / "demo")
            resultado = correr(copia.raiz)
            self.assertEqual(resultado.returncode, 2, resultado.stdout)
            self.assertIn("NO_MEDIDO", resultado.stderr)

    def test_una_carpeta_sin_pagina_tiene_su_propio_codigo(self) -> None:
        with CopiaDelEscaparate() as copia:
            (copia.raiz / "demo" / "vacia").mkdir()
            resultado = correr(copia.raiz)
            self.assertEqual(resultado.returncode, 3, resultado.stdout)
            self.assertIn("no tiene index.html", resultado.stderr)


if __name__ == "__main__":
    unittest.main()
