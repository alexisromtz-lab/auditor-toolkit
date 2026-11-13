"""Cobertura de la demo publica: el artefacto no vale si deja de arrancar.

`demo/clasificador-de-campos/` publica un motor de algebra de Clifford en una
pagina autocontenida. Su garantia no es una promesa en el README: es
`verificar_paridad.py`, que compara cada salida del motor del HTML contra el
oraculo Python certificado, y `verificar_ui.js`, que ejecuta la pagina contra un
DOM simulado.

Este archivo existe para que esa garantia corra junto al resto de la bateria del
repositorio. No reimplementa nada: invoca los dos verificadores y propaga su RC.
Si un dia el motor y el oraculo divergen, el fallo aparece aqui.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO = REPO_ROOT / "demo" / "clasificador-de-campos"
PARIDAD = DEMO / "verificar_paridad.py"
UI = DEMO / "verificar_ui.js"


@unittest.skipUnless(DEMO.is_dir(), "la demo no esta en este arbol")
class DemoClasificadorTests(unittest.TestCase):
    def test_paridad_del_motor_con_el_oraculo(self) -> None:
        """El motor del HTML reproduce el fixture congelado, borde incluido."""
        p = subprocess.run(
            [sys.executable, str(PARIDAD)],
            capture_output=True, text=True, cwd=str(DEMO),
        )
        self.assertEqual(
            p.returncode, 0,
            f"RC {p.returncode}: {p.stderr.strip()[:1500]}",
        )
        self.assertIn("PARIDAD MEDIDA", p.stdout)
        self.assertIn("controles de borde", p.stdout)

    @unittest.skipUnless(shutil.which("node"), "sin node no se ejecuta el motor")
    def test_la_pagina_arranca_y_reproduce_el_caso_nulo(self) -> None:
        """Los dos <script> arrancan contra un DOM simulado y escriben los readouts."""
        p = subprocess.run(
            ["node", str(UI)],
            capture_output=True, text=True, cwd=str(DEMO),
        )
        self.assertEqual(
            p.returncode, 0,
            f"RC {p.returncode}: {p.stderr.strip()[:1500]}",
        )
        self.assertIn("UI MEDIDA", p.stdout)
        self.assertIn("NULO_RADIACION", p.stdout)

    @unittest.skipUnless(shutil.which("node"), "sin node no se ejecuta el motor")
    def test_el_verificador_de_ui_muerde_si_falta_un_id(self) -> None:
        """Un verificador que nunca falla no verifica: se le rompe un id a proposito."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            copia = Path(tmp) / "demo"
            copia.mkdir()
            for nombre in ("index.html", "casos.json", "verificar_ui.js"):
                shutil.copy2(DEMO / nombre, copia / nombre)
            html = (copia / "index.html").read_text(encoding="utf-8")
            roto = html.replace("$('rI1')", "$('rI1_que_no_existe')")
            self.assertNotEqual(roto, html, "la mutacion no aplico: el id cambio de forma")
            (copia / "index.html").write_text(roto, encoding="utf-8")
            p = subprocess.run(
                ["node", str(copia / "verificar_ui.js")],
                capture_output=True, text=True, cwd=str(copia),
            )
            self.assertEqual(p.returncode, 1, f"esperaba RC 1, dio {p.returncode}")
            self.assertIn("rI1_que_no_existe", p.stderr)

    @unittest.skipUnless(shutil.which("node"), "sin node no se ejecuta el motor")
    def test_el_verificador_de_ui_muerde_si_un_valor_no_se_publica(self) -> None:
        """Un input estrecho esconde el exponente; el valor completo debe salir en texto.

        Medido en el sitio publicado el 13-Nov-2026: la caja mostraba
        `3.3356409` y el `e-9` caia fuera de ella, asi que el campo nulo se leia
        1e9 veces mas grande de lo que es. La asercion vive en `verificar_ui.js`;
        aqui se falsa, para que no se quede como una promesa del comentario.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            copia = Path(tmp) / "demo"
            copia.mkdir()
            for nombre in ("index.html", "casos.json", "verificar_ui.js"):
                shutil.copy2(DEMO / nombre, copia / nombre)
            html = (copia / "index.html").read_text(encoding="utf-8")
            marcador = ("    [['exacto-e', 'E', ['e0', 'e1', 'e2'], 'V/m'],\n"
                        "     ['exacto-b', 'B', ['b0', 'b1', 'b2'], 'T']].forEach")
            self.assertIn(marcador, html, "la mutacion no aplica: cambio la forma del bloque")
            (copia / "index.html").write_text(html.replace(marcador, "    [].forEach"),
                                              encoding="utf-8")
            p = subprocess.run(
                ["node", str(copia / "verificar_ui.js")],
                capture_output=True, text=True, cwd=str(copia),
            )
            self.assertEqual(p.returncode, 1, f"esperaba RC 1, dio {p.returncode}")
            self.assertIn("exacto", p.stderr)


if __name__ == "__main__":
    unittest.main()
