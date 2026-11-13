"""Cobertura de la Pieza #2: el nulo de remuestreo, portado al navegador.

`demo/nulo-con-dientes/` publica el motor certificado `nulo_de_remuestreo.py`
como pagina autocontenida. Su garantia no es una promesa: `verificar_paridad.py`
compara cada salida del motor del HTML contra el oraculo Python sobre un fixture
congelado, y `verificar_ui.js` ejecuta los dos `<script>` contra un DOM simulado.

La garantia interesante no es "los flotantes coinciden bit a bit" —no puede
serlo, `x**2` en CPython llama a la libm del sistema, que no redondea
correctamente— sino que **el veredicto nunca diverge**: los cinco campos
discretos son identicos en los 140 casos, y los flotantes quedan dentro de una
cota de ULP declarada y medida.

Este archivo hace tres cosas: propaga el RC de los dos verificadores, y falsa
al verificador de UI con seis mutaciones para que no se quede en promesa.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO = REPO_ROOT / "demo" / "nulo-con-dientes"
PARIDAD = DEMO / "verificar_paridad.py"
UI = DEMO / "verificar_ui.js"
ARCHIVOS = ("index.html", "casos.json", "verificar_ui.js")


def _copia_temporal(tmp: str) -> Path:
    copia = Path(tmp) / "demo"
    copia.mkdir()
    for nombre in ARCHIVOS:
        shutil.copy2(DEMO / nombre, copia / nombre)
    return copia


def _correr_ui(carpeta: Path, timeout: float = 90) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", str(carpeta / "verificar_ui.js")],
        capture_output=True, text=True, cwd=str(carpeta), timeout=timeout,
    )


@unittest.skipUnless(DEMO.is_dir(), "la demo no esta en este arbol")
class DemoNuloTests(unittest.TestCase):
    def test_paridad_del_motor_con_el_oraculo(self) -> None:
        """Los campos discretos identicos y los flotantes bajo la cota declarada."""
        p = subprocess.run(
            [sys.executable, str(PARIDAD)],
            capture_output=True, text=True, cwd=str(DEMO), timeout=600,
        )
        self.assertEqual(p.returncode, 0, f"RC {p.returncode}: {p.stderr.strip()[:1500]}")
        self.assertIn("PARIDAD:", p.stdout)
        self.assertIn("discretos", p.stdout)
        self.assertIn("ULP", p.stdout)

    @unittest.skipUnless(shutil.which("node"), "sin node no se ejecuta el motor")
    def test_la_pagina_arranca_y_reproduce_el_caso_de_arranque(self) -> None:
        """Los dos <script> arrancan contra un DOM simulado y escriben los readouts."""
        p = _correr_ui(DEMO)
        self.assertEqual(p.returncode, 0, f"RC {p.returncode}: {p.stderr.strip()[:1500]}")
        self.assertIn("UI:", p.stdout)
        self.assertIn("cruz_porSerie_b20_rho0.9_n900_r200", p.stdout)

    @unittest.skipUnless(shutil.which("node"), "sin node no se ejecuta el motor")
    def test_un_bloque_no_numerico_no_cuelga_la_pagina(self) -> None:
        """En vivo, el primer toque de slider dejaba la pestana girando.

        `Math.min(NaN, n)` es NaN en JS y el `while` del remuestreador por
        bloques nunca crecia; en Python toda comparacion con NaN es False, asi
        que `max(1, min(nan, n))` da 1 y el oraculo no cuelga. El motor replica
        la semantica del oraculo. Aqui se deshace esa replica y se exige que la
        pagina vuelva a colgarse: si no se cuelga, el aserto A9 no muerde y la
        proteccion es decorativa.
        """
        with tempfile.TemporaryDirectory() as tmp:
            copia = _copia_temporal(tmp)
            html = (copia / "index.html").read_text(encoding="utf-8")
            endurecido = "bloque = _maxPy(1, _minPy(bloque, n));"
            self.assertIn(endurecido, html, "la mutacion no aplica: cambio la forma del guardia")
            (copia / "index.html").write_text(
                html.replace(endurecido, "bloque = Math.max(1, Math.min(bloque, n));"),
                encoding="utf-8",
            )
            with self.assertRaises(subprocess.TimeoutExpired):
                _correr_ui(copia, timeout=25)

    @unittest.skipUnless(shutil.which("node"), "sin node no se ejecuta el motor")
    def test_el_verificador_de_ui_muerde_en_cada_aserto(self) -> None:
        """Cinco roturas, cada una con el aserto que debe nombrarla.

        Una mutacion que revienta el arranque no prueba nada: la pagina tiene
        que seguir arrancando y el fallo salir por el aserto que le toca.
        """
        roturas = [
            ("un id que no existe",
             'id="v-emp"', 'id="v-empp"', "v-emp"),
            ("un estado sin traduccion al espanol",
             "NO_MEDIDO: ['No hay nada que medir'", "NO_MEDIDO_SIN_TEXTO: ['No hay nada que medir'",
             "NO_MEDIDO"),
            ("un valor de entrada recortado",
             "'rho = ' + String(est.rho)", "'rho = ' + est.rho.toFixed(2)", "exacta"),
            ("un lienzo que no se pinta",
             'id="lienzo-nulo"', 'id="lienzo-nulo-sin-pintar"', "lienzo-nulo"),
            ("un slider por omision desviado",
             "bloque: 20, nul: 'porSerie'", "bloque: 5, nul: 'porSerie'", "cruz_porSerie"),
            ("un nulo sin etiqueta",
             "porSerie: 'blocks per series", "porSerieSinTexto: 'blocks per series",
             "nul-txt-porSerie"),
        ]
        for nombre, viejo, nuevo, aguja in roturas:
            with self.subTest(mutacion=nombre), tempfile.TemporaryDirectory() as tmp:
                copia = _copia_temporal(tmp)
                html = (copia / "index.html").read_text(encoding="utf-8")
                self.assertIn(viejo, html, f"la mutacion no aplica: {viejo!r}")
                (copia / "index.html").write_text(html.replace(viejo, nuevo), encoding="utf-8")
                p = _correr_ui(copia)
                self.assertEqual(p.returncode, 1,
                                 f"{nombre}: esperaba RC 1, dio {p.returncode}")
                self.assertIn(aguja, p.stderr, f"{nombre}: el fallo no nombra la causa")

    @unittest.skipUnless(shutil.which("node"), "sin node no se ejecuta el motor")
    def test_una_edicion_inocua_no_dispara_el_verificador(self) -> None:
        """Control negativo: si cualquier edicion diera RC 1, las cinco de arriba no valdrian."""
        with tempfile.TemporaryDirectory() as tmp:
            copia = _copia_temporal(tmp)
            html = (copia / "index.html").read_text(encoding="utf-8")
            self.assertIn("</body>", html, "el HTML no tiene </body>")
            (copia / "index.html").write_text(
                html.replace("</body>", "<!-- comentario sin efecto -->\n</body>"),
                encoding="utf-8",
            )
            p = _correr_ui(copia)
            self.assertEqual(p.returncode, 0, f"una edicion inocua dio RC {p.returncode}: {p.stderr[:800]}")


if __name__ == "__main__":
    unittest.main()
