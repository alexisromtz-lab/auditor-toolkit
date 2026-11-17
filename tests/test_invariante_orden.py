"""HUELLA-FRONTERA-IMPORT-TEST-20261117 — una cifra publicada que no se puede
volver a derivar del dato es prosa.

El defecto que esto vigila se midio: el README de esta carpeta afirmaba 13 / 4 / 0
celdas y 5 pares rotos, y esas cifras solo existian en el README. Si el dato
cambia y el texto no, un lector no distingue una medicion nueva de una vieja.
Aqui el README no se lee: se mide la tabla y se compara.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CARPETA = REPO_ROOT / "research" / "frontera-import"
INSTRUMENTO = CARPETA / "instruments" / "verificar_invariante_orden.py"
TOTAL = CARPETA / "data" / "invariante_total.tsv"

CELDAS_ESPERADAS = {"INERTE": 13, "INMUNE_CONSTRUCCION": 4, "MINA_VIVA": 0}


def _filas() -> list[dict[str, str]]:
    texto = TOTAL.read_text(encoding="utf-8").splitlines()
    cabecera = texto[0].split("\t")
    return [dict(zip(cabecera, linea.split("\t"))) for linea in texto[1:] if linea.strip()]


class InvarianteOrdenTests(unittest.TestCase):
    def test_el_instrumento_no_esta_ciego(self) -> None:
        """Sin auto-test verde, cualquier tabla que produzca es un cero sin lector."""
        proceso = subprocess.run(
            [sys.executable, str(INSTRUMENTO), "--self-test"],
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(proceso.returncode, 0, proceso.stdout + proceso.stderr)
        self.assertIn("positivo=ROMPE_CICLO", proceso.stdout)
        self.assertIn("negativo=PASA", proceso.stdout)

    def test_las_celdas_publicadas_salen_del_dato(self) -> None:
        filas = _filas()
        self.assertEqual(len(filas), 17, "la poblacion pre-registrada son 17 SCC")
        conteo: dict[str, int] = {}
        for fila in filas:
            conteo[fila["celda"]] = conteo.get(fila["celda"], 0) + 1
        # una celda con cero no aparece al contar: se compara con las cuatro
        # celdas declaradas, no con las que el dato trae.
        observado = {celda: conteo.get(celda, 0) for celda in CELDAS_ESPERADAS}
        self.assertEqual(observado, CELDAS_ESPERADAS)
        self.assertLessEqual(
            set(conteo), set(CELDAS_ESPERADAS), "celda no pre-registrada en la tabla"
        )

    def test_toda_ruptura_tiene_reparador_nombrado(self) -> None:
        """Una ruptura sin reparador medido es MINA_VIVA, no una celda inmunе."""
        for fila in _filas():
            if int(fila["rompen"]) == 0:
                continue
            self.assertGreater(
                int(fila["reparan_global"]),
                0,
                f"{fila['paquete']} SCC{fila['scc']} rompe sin reparador medido",
            )
            self.assertIn("PASA[", fila["detalle"], f"SCC{fila['scc']} sin modulo reparador citado")

    def test_el_predictor_refutado_no_se_presenta_como_oraculo(self) -> None:
        docstring = (CARPETA / "instruments" / "mecanismo_ciclos.py").read_text(encoding="utf-8")
        self.assertIn("REFUTADO COMO PREDICTOR", docstring)


if __name__ == "__main__":
    unittest.main()
