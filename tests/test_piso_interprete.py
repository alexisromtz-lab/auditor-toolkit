"""HUELLA-PISO-INTERPRETE-TEST-20261113 — the declared floor had no reader, and the wall was one line.

Measured on `2026-11-13` against `main` at `c5e8581`: this README declared Python **3.12**
as the requirement because the ingest called `Path.write_text(newline=...)`, which does not
exist before 3.10. On a clean clone with the `python3` that ships with macOS (**3.9.6**) the
first documented command therefore died with a `TypeError` traceback — a failure with no
cause, which is the class this toolkit exists to redden. Replacing that single call with
`open(..., newline="\\n")` made the **whole** documented pipeline (ingest, index, sensitivity
and publisher) return `RC 0` on 3.9.6, so the declared ceiling was not a property of the
code: it was a property of one call site.

Two things are locked here and they measure different subjects:

1. **The decision boundary** — `_causa_interprete` returns a named cause below the floor and
   `None` at or above it. Falsifier: move `PISO_PYTHON` to `(3, 13)` and the first case goes
   red, because a supported interpreter would start being refused.
2. **The call site** — no `write_text` in `tools/` passes `newline=`. Falsifier: put it back
   and the syntax-tree case goes red. This one measures **form, not behaviour**: it cannot
   tell whether the replacement writes the same bytes. What it protects is that the floor
   cannot be raised again in silence by the same one-liner.

Declared blind spot: nothing here runs on an interpreter older than the one running the
suite. The floor is exercised by the `floor-python` CI job, which installs 3.9 and runs the
documented commands — this file only pins where the refusal lives.
"""
from __future__ import annotations

import ast
import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INGEST = REPO_ROOT / "tools" / "ingesta_ast_v2.py"


def _cargar_ingest():
    spec = importlib.util.spec_from_file_location("ingesta_ast_v2_piso", INGEST)
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


class FloorDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ingest = _cargar_ingest()

    def test_below_the_floor_the_cause_is_named(self) -> None:
        causa = self.ingest._causa_interprete((3, 8, 18, "final", 0))
        self.assertIsNotNone(causa)
        self.assertIn("INTERPRETE_INSUFICIENTE", causa)
        self.assertIn("3.9", causa)
        self.assertIn("3.8", causa)

    def test_at_and_above_the_floor_there_is_no_cause(self) -> None:
        for version in ((3, 9, 0), (3, 12, 13), (4, 0, 0)):
            with self.subTest(version=version):
                self.assertIsNone(self.ingest._causa_interprete(version))

    def test_the_floor_is_the_one_the_readme_declares(self) -> None:
        """El piso del código y el del README son el mismo sujeto o son dos fuentes."""
        piso = ".".join(str(parte) for parte in self.ingest.PISO_PYTHON)
        for nombre in ("README.md", "README.es.md"):
            with self.subTest(readme=nombre):
                texto = (REPO_ROOT / nombre).read_text(encoding="utf-8")
                self.assertIn(f"Python **{piso}", texto)


class NoRaisedFloorTests(unittest.TestCase):
    def test_no_write_text_receives_a_newline_keyword(self) -> None:
        for ruta in sorted((REPO_ROOT / "tools").glob("*.py")):
            arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
            for nodo in ast.walk(arbol):
                if not isinstance(nodo, ast.Call):
                    continue
                funcion = nodo.func
                nombre = getattr(funcion, "attr", getattr(funcion, "id", ""))
                if nombre != "write_text":
                    continue
                claves = {palabra.arg for palabra in nodo.keywords}
                with self.subTest(archivo=ruta.name, linea=nodo.lineno):
                    self.assertNotIn(
                        "newline",
                        claves,
                        f"{ruta.name}:{nodo.lineno} sube el piso de Python sin declararlo; "
                        'usar open(..., newline="\\n")',
                    )


if __name__ == "__main__":
    unittest.main()
