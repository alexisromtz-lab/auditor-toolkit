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
        self.assertIn("SELF-TEST OK: 24/24", proceso.stdout)

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

    def test_huella_del_ci_no_se_suma_al_clon(self) -> None:
        """Un clon puede ser el propio CI. La huella se publica, no se agrega."""
        github = {
            "estrellas": 0,
            "forks": 0,
            "vistas": 2,
            "vistas_unicas": 2,
            "clones": 488,
            "clones_unicos": 168,
            "corridas": 121,
        }
        filas = self.m.construir_filas([], github)
        totales = self.m.totalizar(filas)
        self.assertEqual(totales["CLON"], 488, "la huella del CI no se resta sola")
        self.assertEqual(totales["LECTOR"], 2)
        self.assertNotIn("HUELLA_PROPIA", totales)
        huella = [f for f in filas if f["clase"] == "HUELLA_PROPIA"]
        self.assertEqual(len(huella), 1)
        self.assertEqual(huella[0]["metrica"], "runs_ci")
        self.assertEqual(huella[0]["valor"], 121)

    def test_todo_clon_publicado_lleva_su_huella(self) -> None:
        """Desde el arreglo, un CLON sin runs_ci no es interpretable.

        Los bloques anteriores al 17-Nov-2026 son el registro del defecto: por eso
        la aserción cae sobre el bloque más reciente, que es el que un lector mira.
        """
        bloques: dict[str, set[str]] = {}
        for fila in _filas():
            bloques.setdefault(fila["fecha_hora"], set()).add(fila["metrica"])
        ultimo = max(bloques)
        self.assertIn("clones", bloques[ultimo])
        self.assertIn("runs_ci", bloques[ultimo], f"{ultimo}: clon sin co-variable")

    def test_clase_pedida_sin_filas_es_no_medido(self) -> None:
        self.assertIsNone(self.m.totalizar([], {"DESCARGA"})["DESCARGA"])

    def test_la_huella_no_se_vende_como_explicacion_total(self) -> None:
        """Si el CI explicara el clon, la conclusión "rastreo ajeno" sobraría.

        Medido 17-Nov-2026: 2 x 121 = 242 contra 488 clones. Un instrumento que
        publicara cobertura cercana a 1 estaría vendiendo una explicación.
        """
        github = {
            "estrellas": 0,
            "forks": 0,
            "vistas": 2,
            "vistas_unicas": 2,
            "clones": 488,
            "clones_unicos": 168,
            "corridas": 121,
        }
        filas = self.m.construir_filas([], github)
        cobertura = self.m.cobertura_huella(
            self.m._valor_github(filas, "runs_ci"), self.m._valor_github(filas, "clones")
        )
        self.assertIsNotNone(cobertura)
        self.assertGreater(cobertura, 0.0)
        self.assertLess(cobertura, 0.6, "el CI no explica el conteo de clones")

    def test_canal_exige_repo_y_sale_con_20(self) -> None:
        """Un argumento malo no es NO_MEDIDO: el contrato reserva 2 para eso."""
        proceso = subprocess.run(
            [sys.executable, str(INSTRUMENTO), "--canal"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proceso.returncode, 20, proceso.stderr)

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
