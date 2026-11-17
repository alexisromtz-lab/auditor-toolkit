"""HUELLA-RECEPCION-TEST-20261117 — la cuarta etapa del embudo, con su falsador.

Un instrumento que dice "medimos la recepción" sin control negativo mide su propia
opinión. Aquí se ejecuta su self-test y se comprueba que la tabla publicada no
infla lectores sumando poblaciones anidadas: el defecto medido el 17-Nov-2026 fue
656 clones donde había 488.
"""
from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CARPETA = REPO_ROOT / "research" / "recepcion"
INSTRUMENTO = CARPETA / "instruments" / "medir_recepcion.py"
TSV = CARPETA / "data" / "RECEPCION.tsv"
COLUMNAS = [
    "fecha_hora",
    "superficie",
    "metrica",
    "valor",
    "unidad",
    "clase",
    "ventana",
    "estado",
]
NO_MEDIDO = "NO_MEDIDO"


def _cargar_modulo():
    especificacion = importlib.util.spec_from_file_location("medir_recepcion", INSTRUMENTO)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def _filas() -> list[dict]:
    with TSV.open(encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo, delimiter="\t"))


class TestRecepcion(unittest.TestCase):
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
        self.assertIn("SELF-TEST OK: 15/15", proceso.stdout)

    def test_tsv_tiene_una_sola_cabecera(self) -> None:
        texto = TSV.read_text(encoding="utf-8")
        self.assertEqual(
            texto.count("fecha_hora\tsuperficie"), 1, "dos cabeceras parten cualquier parser"
        )

    def test_tsv_bien_formado(self) -> None:
        with TSV.open(encoding="utf-8", newline="") as archivo:
            filas = list(csv.reader(archivo, delimiter="\t"))
        self.assertEqual(filas[0], COLUMNAS)
        for numero, fila in enumerate(filas, 1):
            self.assertEqual(len(fila), len(COLUMNAS), f"la fila {numero} no tiene 8 columnas")

    def test_clones_no_son_lectores(self) -> None:
        filas = _filas()
        self.assertTrue(filas)
        self.assertNotIn("CLON_NO_ATRIBUIDO", {f["clase"] for f in filas})
        bloques: dict[str, list[dict]] = {}
        for fila in filas:
            bloques.setdefault(fila["fecha_hora"], []).append(fila)
        for momento, bloque in bloques.items():
            clon = sum(
                int(f["valor"]) for f in bloque if f["clase"] == "CLON" and f["valor"] != NO_MEDIDO
            )
            unico = sum(
                int(f["valor"])
                for f in bloque
                if f["clase"] == "CLON_UNICO" and f["valor"] != NO_MEDIDO
            )
            if clon and unico:
                self.assertGreaterEqual(
                    clon, unico, f"{momento}: los únicos están contenidos en los clones"
                )

    def test_estado_pieza_es_auditable(self) -> None:
        publicados = [f for f in _filas() if f["metrica"] == "publicado"]
        self.assertTrue(publicados, "falta ESTADO_PIEZA.publicado: la ventana no es auditable")
        self.assertIn(publicados[-1]["valor"], {"0", "1", NO_MEDIDO})

    def test_horas_desde_no_inventa_cifras(self) -> None:
        self.assertIsNone(self.m._horas_desde(None))
        self.assertIsNone(self.m._horas_desde("no-es-una-fecha"))
        self.assertIsNotNone(self.m._horas_desde("2026-11-17T19:24:53Z"))

    def test_clase_pedida_sin_filas_es_no_medido(self) -> None:
        self.assertIsNone(self.m.totalizar([], {"DESCARGA"})["DESCARGA"])

    def test_devto_no_contamina_lector(self) -> None:
        github = {
            "estrellas": 0,
            "forks": 0,
            "vistas": 2,
            "vistas_unicas": 2,
            "clones": 488,
            "clones_unicos": 168,
        }
        devto = {
            "alcanzable": True,
            "publicado": "2026-11-17T19:24:53Z",
            "reacciones": 5,
            "comentarios": 1,
            "vistas": None,
        }
        totales = self.m.totalizar(self.m.construir_filas([], github, devto))
        self.assertEqual(totales["LECTOR"], 2)
        self.assertIsNone(totales["LECTOR_DEVTO"])
        self.assertEqual(totales["SENAL"], 0)
        self.assertEqual(totales["SENAL_DEVTO"], 6)


if __name__ == "__main__":
    unittest.main()
