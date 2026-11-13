"""Cobertura de la Pieza #3: el piso de deteccion, portado al navegador.

`demo/piso-de-deteccion/` publica el instrumento `piso_de_deteccion.py` como
pagina autocontenida. La garantia tampoco es aqui una promesa: 16 campos por
perfil se comparan bit a bit contra el oraculo Python, las 108 compuertas se
comparan en entero exacto, y `verificar_ui.js` ejecuta los dos `<script>`
contra un DOM simulado.

Lo que esta pieza NO puede prometer, y declara en lugar de esconder: los tres
cocientes `estimador_ratio_*` no son exactos. `tau = |div_central - div_exacta|`
es una diferencia que cancela, y `Math.exp` de V8 (fdlibm) y `np.exp` (libm)
difieren en 908 de 9216 nodos por 1 ULP. El cociente amplifica ese ULP hasta
5.6e-13 relativos. Se contrata 1e-11 y el verificador publica el peor medido.

Los conteos que la pagina muestra si son estables, y eso lo comprueba el
fixture: en 108 compuertas, `cerca_del_umbral == 0`, es decir ningun nodo cae a
menos de 1e-9 relativo de su umbral. Si eso dejara de ser cierto, el fixture
dejaria de servir como contrato y el verificador daria RC 2.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO = REPO_ROOT / "demo" / "piso-de-deteccion"
PARIDAD = DEMO / "verificar_paridad.py"
UI = DEMO / "verificar_ui.js"
ARCHIVOS = ("index.html", "casos.json", "verificar_ui.js")


def _copia_temporal(tmp: str) -> Path:
    copia = Path(tmp) / "demo"
    copia.mkdir()
    for nombre in ARCHIVOS:
        shutil.copy2(DEMO / nombre, copia / nombre)
    return copia


def _correr_ui(carpeta: Path, timeout: float = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", str(carpeta / "verificar_ui.js")],
        capture_output=True, text=True, cwd=str(carpeta), timeout=timeout,
    )


@unittest.skipUnless(DEMO.is_dir(), "la demo no esta en este arbol")
class DemoPisoTests(unittest.TestCase):
    def test_paridad_del_motor_con_el_fixture(self) -> None:
        """Bits exactos, cocientes bajo cota declarada, compuertas exactas."""
        p = subprocess.run(
            [sys.executable, str(PARIDAD)],
            capture_output=True, text=True, cwd=str(DEMO), timeout=600,
        )
        self.assertEqual(p.returncode, 0, f"RC {p.returncode}: {(p.stderr or p.stdout).strip()[:2000]}")
        self.assertIn("PARIDAD OK", p.stdout)
        self.assertIn("campos exactos 80/80", p.stdout)
        self.assertIn("compuertas: 108", p.stdout)
        self.assertIn("con piso ciego 108", p.stdout)

    def test_el_fixture_cumple_su_promesa_de_estabilidad(self) -> None:
        """Ningun nodo a menos de 1e-9 del umbral: los conteos no dependen del port.

        Es la unica razon por la que una pagina puede afirmar "92 % de los nodos
        violan" sin que ese numero sea un artefacto de implementacion.
        """
        datos = json.loads((DEMO / "casos.json").read_text(encoding="utf-8"))
        self.assertIs(datos["procedencia"]["fuente_publica"], False)
        self.assertEqual(len(datos["perfiles"]), 5)
        self.assertEqual(len(datos["compuertas"]), 108)
        cerca = [c for c in datos["compuertas"] if c["esperado"]["cerca_del_umbral"] != 0]
        self.assertEqual(cerca, [], "hay compuertas con nodos pegados al umbral")
        ciegas = [c for c in datos["compuertas"] if c["esperado"]["piso_ciego"]]
        self.assertEqual(len(ciegas), 108, "el piso dejo de ser ciego a la contaminacion")

    def test_la_malla_esta_capada_por_coste_medido(self) -> None:
        """N se queda en 128: medido 127 ms en 128 y 665 ms en 256 por interaccion.

        Un slider que tarda dos tercios de segundo deja de ser una demostracion.
        """
        html = (DEMO / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('value="256"', html, "alguien subio la malla por encima del coste medido")
        self.assertIn('value="128"', html)

    @unittest.skipUnless(shutil.which("node"), "sin node no se ejecuta el motor")
    def test_la_pagina_arranca_y_pinta_las_cuatro_celdas(self) -> None:
        p = _correr_ui(DEMO)
        self.assertEqual(p.returncode, 0, f"RC {p.returncode}: {p.stderr.strip()[:2000]}")
        self.assertIn("UI OK", p.stdout)

    @unittest.skipUnless(shutil.which("node"), "sin node no se ejecuta el motor")
    def test_el_verificador_de_ui_muerde_en_cada_aserto(self) -> None:
        """Diez roturas, cada una con el aserto que debe nombrarla.

        Una mutacion que revienta el arranque no prueba nada: la pagina tiene
        que seguir arrancando y el fallo salir por el aserto que le toca.
        """
        roturas = [
            ("la tesis: se apaga la contaminacion del preset",
             "ciego: { delta: 0.5, margen: 1, eps: 1 }", "ciego: { delta: 0, margen: 1, eps: 1 }",
             "A5"),
            ("una traduccion al ingles que desaparece",
             'est_viola: "violates",', 'est_violaSinTexto: "violates",', "est_viola"),
            ("una cifra de entrada recortada",
             "function decimalCrudo(v) { return String(v); }",
             "function decimalCrudo(v) { return v.toFixed(1); }", "A8"),
            ("la celda ciega recibe el residuo honesto",
             'pintarMapa("mapa-const-contaminado", c.contaminado.R, c.contaminado.th,',
             'pintarMapa("mapa-const-contaminado", c.honesto.R, c.honesto.th,', "A9"),
            ("el preset de falso rojo deja de ser falso",
             "falso_rojo: { delta: 0, margen: 1, eps: 0.5 }",
             "falso_rojo: { delta: 0, margen: 1, eps: 1 }", "A6"),
            ("la tabla de medidas se queda corta",
             "for (var i = 0; i < filas.length; i++) {",
             "for (var i = 0; i < filas.length - 5; i++) {", "A10"),
            ("un enlace al repositorio privado",
             "</footer>",
             '</footer><p><a href="https://github.com/alexisromtz-lab/platino-labs/x">x</a></p>',
             "A12"),
            ("un preset que el control redondea al paso",
             'id="ctl-delta" min="0" max="1.2" step="0.01"',
             'id="ctl-delta" min="0" max="1.2" step="0.02"', "A13"),
            ("un rotulo de canvas que no pasa por el diccionario",
             "ctx.fillText(T.TEXTO[est.idioma].perfil_eje, izq, H - 10);",
             'ctx.fillText("τ(x) en y = 0, escala log", izq, H - 10);', "A14"),
            ("una etiqueta de tabla fija en espanol",
             "[t.fila_mascara, cifra(p.mascara_fraccion)]",
             '["máscara", cifra(p.mascara_fraccion)]', "A14"),
        ]
        for nombre, viejo, nuevo, aguja in roturas:
            with self.subTest(mutacion=nombre), tempfile.TemporaryDirectory() as tmp:
                copia = _copia_temporal(tmp)
                html = (copia / "index.html").read_text(encoding="utf-8")
                self.assertIn(viejo, html, f"la mutacion no aplica: {viejo!r}")
                (copia / "index.html").write_text(html.replace(viejo, nuevo, 1), encoding="utf-8")
                p = _correr_ui(copia)
                self.assertEqual(p.returncode, 1, f"{nombre}: esperaba RC 1, dio {p.returncode}")
                self.assertIn(aguja, p.stderr, f"{nombre}: el fallo no nombra la causa")

    @unittest.skipUnless(shutil.which("node"), "sin node no se ejecuta el motor")
    def test_una_edicion_inocua_no_dispara_el_verificador(self) -> None:
        """Control negativo: si cualquier edicion diera RC 1, las siete de arriba no valdrian."""
        with tempfile.TemporaryDirectory() as tmp:
            copia = _copia_temporal(tmp)
            html = (copia / "index.html").read_text(encoding="utf-8")
            self.assertIn("</body>", html, "el HTML no tiene </body>")
            (copia / "index.html").write_text(
                html.replace("</body>", "<!-- comentario sin efecto -->\n</body>", 1),
                encoding="utf-8",
            )
            p = _correr_ui(copia)
            self.assertEqual(p.returncode, 0, f"una edicion inocua dio RC {p.returncode}: {p.stderr[:800]}")


if __name__ == "__main__":
    unittest.main()
