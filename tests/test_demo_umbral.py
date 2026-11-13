"""Cobertura de la Pieza #4: el umbral económico, con su oráculo a la vista.

`demo/umbral-economico/` es la primera pieza de este escaparate que **no porta
un motor existente**: no había ninguno en el corpus, así que el motor se escribió
aquí y su falsador no puede ser "el port coincide con el original". Su falsador
compara **dos cómputos independientes del mismo número** y los exige idénticos
bit a bit: la suma término a término de `E[K]` contra su forma cerrada
`(1-u^m)/p`, dentro de `umbral.py`; y el motor JS contra el oráculo Python, dentro
del fixture.

De ahí la consecuencia que esta pieza sí puede declarar y las dos anteriores no:
el oráculo es público (`fuente_publica: true`), porque vive en este mismo
repositorio y cualquiera puede correrlo. Y esa declaración no se cree: el test
`test_el_oraculo_corre_en_limpio` lo copia solo, a un directorio temporal, y lo
ejecuta con `python3 -I` — sin `PYTHONPATH`, sin sitio de usuario, sin el corpus,
desde otro directorio de trabajo.

Los conteos que la página muestra son estables porque el fixture lo comprueba:
6 estados del bloque `frontera` se sientan exactamente sobre `p·V = C`, y la
afirmación de la pieza es que **el signo de la política no depende de `m`**. Si
esos estados dejaran de caer en la banda declarada, la afirmación perdería su
banco de pruebas y el fixture daría RC 5.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO = REPO_ROOT / "demo" / "umbral-economico"
PARIDAD = DEMO / "verificar_paridad.py"
UI = DEMO / "verificar_ui.js"
ORACULO = DEMO / "umbral.py"
FIXTURE = DEMO / "fixture.json"
ARCHIVOS = ("index.html", "motor.js", "verificar_ui.js")


def _copia_temporal(tmp: str) -> Path:
    copia = Path(tmp) / "demo"
    copia.mkdir()
    for nombre in ARCHIVOS:
        shutil.copy2(DEMO / nombre, copia / nombre)
    return copia


def _corre_ui(carpeta: Path, timeout: float = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", str(carpeta / "verificar_ui.js")],
        capture_output=True, text=True, cwd=str(carpeta), timeout=timeout,
    )


def _copia_completa(tmp: str) -> Path:
    copia = Path(tmp) / "demo"
    copia.mkdir()
    for ruta in DEMO.iterdir():
        if ruta.is_file() and ruta.suffix in (".py", ".js", ".html", ".json"):
            shutil.copy2(ruta, copia / ruta.name)
    return copia


def _corre_paridad(carpeta: Path, timeout: float = 600) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(carpeta / "verificar_paridad.py")],
        capture_output=True, text=True, cwd=str(carpeta), timeout=timeout,
    )


@unittest.skipUnless(DEMO.is_dir(), "la demo no está en este árbol")
class DemoUmbralTests(unittest.TestCase):
    def test_paridad_exacta_contra_el_oraculo(self) -> None:
        """Sin tolerancia: este motor no tiene una sola operación transcendente."""
        p = _corre_paridad(DEMO)
        self.assertEqual(p.returncode, 0, f"RC {p.returncode}: {(p.stderr or p.stdout).strip()[:2000]}")
        self.assertIn("PARIDAD OK", p.stdout)
        self.assertIn("0 discrepancias, tolerancia 0", p.stdout)
        self.assertIn("estados: 250", p.stdout)
        self.assertIn("claves exactas: 13", p.stdout)
        self.assertIn("UI OK", p.stdout)

    def test_el_oraculo_corre_en_limpio_sin_el_corpus(self) -> None:
        """Un solo archivo, aislado, desde otro directorio: la fricción de entrada es cero.

        `-I` ignora `PYTHONPATH` y el sitio de usuario. Si el oráculo necesitara
        algo del corpus, este test no podría ni arrancarlo — que es exactamente
        lo que descalificó al analizador de grafos como primera demo.
        """
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy2(ORACULO, Path(tmp) / "umbral.py")
            p = subprocess.run(
                [sys.executable, "-I", "umbral.py", "--self-test"],
                capture_output=True, text=True, cwd=tmp, timeout=600,
                env={"PATH": "/usr/bin:/bin"},
            )
        self.assertEqual(p.returncode, 0, f"RC {p.returncode}: {(p.stderr or p.stdout).strip()[:2000]}")
        self.assertIn("G1..G10 OK", p.stdout)
        importas = [ln.split()[1] for ln in ORACULO.read_text(encoding="utf-8").splitlines()
                    if ln.startswith("import ")]
        self.assertEqual(sorted(importas), ["json", "math", "sys"], "el oráculo dejó de ser stdlib puro")

    def test_el_fixture_declara_su_procedencia_y_su_frontera(self) -> None:
        """`fuente_publica: true` no es una etiqueta: el archivo que cita está al lado."""
        datos = json.loads(FIXTURE.read_text(encoding="utf-8"))
        procedencia = datos["procedencia"]
        self.assertIs(procedencia["fuente_publica"], True)
        self.assertEqual(procedencia["sha256_oraculo"],
                         hashlib.sha256(ORACULO.read_bytes()).hexdigest(),
                         "el fixture se congeló contra otro oráculo")
        promesas = datos["promesas"]
        self.assertEqual(promesas["estados"], 250)
        self.assertEqual(promesas["tolerancia"], 0.0)
        frontera = datos["frontera"]
        self.assertEqual(len(frontera), promesas["frontera"])
        banda = promesas["banda"]
        pegados = [e for e in frontera
                   if abs(e["p"] * e["V"] - e["C"]) <= banda * max(e["V"], e["C"])]
        self.assertEqual(len(pegados), promesas["cerca_del_umbral"],
                         "la frontera dejó de estar donde la pieza dice que está")

    def test_el_check_ignora_solo_al_observador(self) -> None:
        """`procedencia.python` es el recibo, no el sujeto: fuera del sujeto y nada más.

        Medido: el mismo oráculo da los mismos 4 270 valores en 3.9.6 y en
        3.12.13, pero el intérprete se nombra en el fixture. Compararlo byte a
        byte puso la CI en rojo sobre un oráculo correcto (RC 5 en 3.12, RC 0 en
        3.9.6, 2 bytes de diferencia). Este test fija las dos mitades: el campo
        del observador no muerde, y cualquier otro campo del mismo bloque sí.
        """
        def check(carpeta: Path) -> subprocess.CompletedProcess:
            return subprocess.run(
                [sys.executable, "generar_fixture.py", "--check"],
                capture_output=True, text=True, cwd=str(carpeta), timeout=600,
            )

        def pisa(carpeta: Path, ruta: tuple, valor) -> None:
            datos = json.loads((carpeta / "fixture.json").read_text(encoding="utf-8"))
            datos[ruta[0]][ruta[1]] = valor
            (carpeta / "fixture.json").write_text(
                json.dumps(datos, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            carpeta = _copia_completa(tmp)
            self.assertEqual(check(carpeta).returncode, 0, "la copia limpia ya no cuadra")

            pisa(carpeta, ("procedencia", "python"), "0.0.0")
            blanco = check(carpeta)
            self.assertEqual(blanco.returncode, 0,
                             f"el intérprete del observador volvió a mandar: {blanco.stderr[:400]}")
            self.assertIn("procedencia/python=0.0.0", blanco.stdout,
                          "el check no declara qué dejó fuera del sujeto")

            pisa(carpeta, ("procedencia", "semilla"), 1)
            sujeto = check(carpeta)
            self.assertEqual(sujeto.returncode, 5,
                             f"un campo del sujeto dejó de morder: {sujeto.stdout[:400]}")
            self.assertIn("cambió el contrato del Monte Carlo", sujeto.stderr,
                          "el RC 5 dejó de decir qué se movió")

    def test_la_pagina_no_toca_el_corpus_privado(self) -> None:
        """Cero enlaces a repositorios privados: el 404 se midió en vivo y se corrigió."""
        html = (DEMO / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("platino-labs", html)
        self.assertNotIn('href="http', html, "la pieza no enlaza hacia fuera: el hub enlaza hacia ella")

    @unittest.skipUnless(shutil.which("node"), "sin node no se ejecuta el motor")
    def test_el_verificador_de_paridad_muerde_en_cada_capa(self) -> None:
        """Cinco roturas, cinco RC distintos: cada capa falla por su cuenta.

        Una sola mutación no distingue "el oráculo se movió" de "el motor divergió"
        de "la página no arranca". Sin esta tabla, un verificador que devolviera
        RC 1 por cualquier cosa pasaría el test anterior sin medir nada.
        """
        ruido = ("  return p * V - C;\n}", "  return p * V * (1 - 1e-15) - C;\n}")
        # (nombre, mutar motor, dejar la página atrás, regenerar fixture, RC esperado)
        roturas = [
            ("el motor cambia y el fixture no se regenera", True, False, False, 5),
            ("el motor cambia y el fixture sí se regenera", True, False, True, 1),
            ("el motor cambia sólo en el archivo canónico", True, True, True, 7),
            ("la página deja de arrancar con el motor intacto", False, False, False, 6),
            # el defecto real del 12-Nov-2026: el pie anunciaba 26 880 valores y 40
            # estados con paridad exacta de 4 270. Nadie los contaba contra el pie.
            ("el pie anuncia cifras que nadie contó", False, False, False, 8),
        ]
        for nombre, mutar_motor, dejar_pagina, regenerar, esperado in roturas:
            with self.subTest(mutacion=nombre), tempfile.TemporaryDirectory() as tmp:
                copia = _copia_completa(tmp)
                if mutar_motor:
                    for archivo in ("motor.js", "index.html"):
                        texto = (copia / archivo).read_text(encoding="utf-8")
                        self.assertIn(ruido[0], texto, f"la mutación no aplica en {archivo}")
                        (copia / archivo).write_text(texto.replace(ruido[0], ruido[1], 1), encoding="utf-8")
                if dejar_pagina:
                    shutil.copy2(DEMO / "index.html", copia / "index.html")
                if regenerar:
                    r = subprocess.run([sys.executable, "generar_fixture.py"], cwd=str(copia),
                                       capture_output=True, text=True, timeout=600)
                    self.assertEqual(r.returncode, 0, r.stderr[:800])
                if esperado == 8:
                    html = (copia / "index.html").read_text(encoding="utf-8")
                    self.assertIn("4 270 valores analíticos", html)
                    (copia / "index.html").write_text(
                        html.replace("4 270 valores analíticos", "26 880 valores analíticos", 1),
                        encoding="utf-8")
                if esperado == 6:
                    html = (copia / "index.html").read_text(encoding="utf-8")
                    ancla = "var TEXTO = {"
                    self.assertIn(ancla, html)
                    html = html.replace(
                        '"use strict";\n\n' + ancla,
                        '"use strict";\n\ndocument.getElementById("no-existe").textContent = "x";\n\n' + ancla, 1)
                    (copia / "index.html").write_text(html, encoding="utf-8")
                p = _corre_paridad(copia)
                self.assertEqual(p.returncode, esperado,
                                 f"{nombre}: esperaba RC {esperado}, dio RC {p.returncode}: "
                                 f"{(p.stderr or p.stdout).strip()[:600]}")

    @unittest.skipUnless(shutil.which("node"), "sin node no se ejecuta el motor")
    def test_la_pagina_muerde_en_cada_aserto(self) -> None:
        """Trece roturas sobre las 18 aserciones, cada una nombrada por la suya.

        Las cinco que faltan (A2 arranque, A3 la tabla, A10 presets, A12
        determinismo, A15 controles) miden que la pieza está ahí, no que un
        pintor dibuje bien; su mutación natural revienta el arranque y entonces
        el fallo sale por A2 en vez de por la suya, que es justo lo que este test
        no debe aceptar como prueba.

        Una mutación que revienta el arranque no prueba nada: la página tiene que
        seguir arrancando y el fallo salir por el aserto que le toca.
        """
        roturas = [
            ("la frontera clavada en una x fija", "A5",
             "ctx.fillRect(xp(pmin) - 1, y0, 2, y1 - y0);",
             "ctx.fillRect(x0 + 100, y0, 2, y1 - y0);"),
            ("la curva de ruina usa tu p y no el umbral", "A6",
             "var yy = yr(supervivenciaTrasM(est.r.p_min, i));",
             "var yy = yr(supervivenciaTrasM(est.p, i));"),
            ("un rótulo de canvas sin pasar por el diccionario", "A7",
             "ctx.fillText(T.eje_ruina, 6, y0 - 8);",
             'ctx.fillText("ruina acumulada", 6, y0 - 8);'),
            ("una cifra impresa truncada", "A8",
             "if (a >= 0.001) return x.toFixed(dec === undefined ? 4 : dec);",
             "return x.toFixed(2);"),
            ("getContext sin guarda", "A13",
             'var ctx = cv.getContext("2d");\n  if (!ctx) return;\n'
             "  ctx.clearRect(0, 0, cv.width, cv.height);\n  var T = TEXTO[est.idioma];\n"
             "  var W = cv.width, H = cv.height, ML = 46",
             'var ctx = cv.getContext("2d");\n'
             "  ctx.clearRect(0, 0, cv.width, cv.height);\n  var T = TEXTO[est.idioma];\n"
             "  var W = cv.width, H = cv.height, ML = 46"),
            ("el preset sólido se queda sin margen de ruina", "A4",
             '{ id: "solido", pp: 350, V: 100, C: 10, m: 8 },',
             '{ id: "solido", pp: 350, V: 100, C: 10, m: 5 },'),
            ("un enlace a un repositorio privado", "A14",
             '<div class="pie" id="pie"></div>',
             '<div class="pie" id="pie"></div>'
             '<a href="https://github.com/alexisromtz-lab/platino-labs">origen</a>'),
            ("la identidad imprime otro producto", "A11",
             'fmt(r.C / r.p, 4) + ") = "', 'fmt(r.C, 4) + ") = "'),
            ("el botón de idioma no repinta", "A9",
             'est.idioma = est.idioma === "es" ? "en" : "es";\n    pintar();',
             'est.idioma = est.idioma === "es" ? "en" : "es";'),
            ("falta una clave en el diccionario EN", "A1",
             '    nivel_50: "50 %",\n    nivel_10: "10 %",', '    nivel_10: "10 %",'),
            # defecto real del 12-Nov-2026, visto en el render y no en el RC: sin
            # clearRect, pasar a EN pinta el rotulo ingles encima del espanol.
            ("el lienzo de ruina no se limpia al repintar", "A18",
             "  ctx.clearRect(0, 0, cv.width, cv.height);\n  var T = TEXTO[est.idioma];\n"
             "  var W = cv.width, H = cv.height, ML = 56",
             "  var T = TEXTO[est.idioma];\n  var W = cv.width, H = cv.height, ML = 56"),
            ("la barra de m clavada en una x fija", "A17",
             "ctx.fillRect(xm(est.m) - 2, y0 - 4, 4, y1 - y0 + 8);",
             "ctx.fillRect(x0 + 40, y0 - 4, 4, y1 - y0 + 8);"),
            # el defecto real del 12-Nov-2026: la copia en ES declarada dentro del
            # bloque EN. A7 no puede verlo (la cadena figura en el diccionario EN,
            # la puso ahi la copia); A16 si.
            ("una clave declarada dos veces en el bloque EN", "A16",
             '    fuera_mapa: "p_min off the map: C > V, no attempt pays",\n    veredicto_ok: "It pays',
             '    fuera_mapa: "p_min off the map: C > V, no attempt pays",\n'
             '    fuera_mapa: "p_min fuera del mapa: C > V, ningún intento paga",\n    veredicto_ok: "It pays'),
        ]
        for nombre, aguja, viejo, nuevo in roturas:
            with self.subTest(mutacion=nombre), tempfile.TemporaryDirectory() as tmp:
                copia = _copia_temporal(tmp)
                html = (copia / "index.html").read_text(encoding="utf-8")
                self.assertIn(viejo, html, f"la mutación no aplica: {viejo!r}")
                (copia / "index.html").write_text(html.replace(viejo, nuevo, 1), encoding="utf-8")
                p = _corre_ui(copia)
                self.assertEqual(p.returncode, 1, f"{nombre}: esperaba RC 1, dio {p.returncode}")
                self.assertIn(aguja, p.stderr, f"{nombre}: el fallo no nombra la causa")

    @unittest.skipUnless(shutil.which("node"), "sin node no se ejecuta el motor")
    def test_una_edicion_inocua_no_dispara_el_verificador(self) -> None:
        """Control negativo: si cualquier edición diera RC 1, la tabla de arriba no valdría."""
        with tempfile.TemporaryDirectory() as tmp:
            copia = _copia_temporal(tmp)
            html = (copia / "index.html").read_text(encoding="utf-8")
            self.assertIn("</body>", html, "el HTML no tiene </body>")
            (copia / "index.html").write_text(
                html.replace("</body>", "<!-- comentario sin efecto -->\n</body>", 1),
                encoding="utf-8",
            )
            p = _corre_ui(copia)
            self.assertEqual(p.returncode, 0, f"una edición inocua dio RC {p.returncode}: {p.stderr[:800]}")


if __name__ == "__main__":
    unittest.main()
