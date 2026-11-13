"""HUELLA-CASE-STUDY-CONTRACT-TEST-20261113 — a case study that cannot be reproduced is prose.

The defect this guards against is measured, not imagined: the first version of the
two-readings table in `README.md` carried two rows (`click`, `rich`) measured over the
whole repository and three rows (`requests`, `httpx`, `attrs`) measured over the package.
Nothing in the file said which was which, so a reader could not tell a different
measurement from a wrong one. Three rows reproduced and two did not.

From here on, any `case_studies/arch-*.md` must declare, at the start of a line, the
universe it measured, the commit, the corpus SHA-256 and the command that produced it;
and its bash block must contain the two-reading command. Falsifier: delete the `Commit:`
line from `case_studies/arch-two-readings-20261113.md` and this file goes red.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_STUDIES = REPO_ROOT / "case_studies"
GLOB = "arch-*.md"

DECLARACIONES = ("Universe:", "Commit:", "Corpus SHA-256:", "Command:")
_RE_BLOQUE_BASH = re.compile(r"```bash\n(.*?)```", re.DOTALL)
_RE_SHA40 = re.compile(r"\b[0-9a-f]{40}\b")
_RE_SHA256 = re.compile(r"\b[0-9a-f]{64}\b")


def defectos(nombre: str, texto: str) -> list[str]:
    """Los defectos de contrato de un caso de estudio; cadena vacía no es lista vacía."""
    fallos = [
        f"{nombre}: falta la declaracion {declaracion!r} al inicio de una linea"
        for declaracion in DECLARACIONES
        if not re.search(rf"^{re.escape(declaracion)}", texto, re.MULTILINE)
    ]
    bloques = _RE_BLOQUE_BASH.findall(texto)
    if not bloques:
        fallos.append(f"{nombre}: sin bloque ```bash — no hay comando que lo reproduzca")
    else:
        bash = "\n".join(bloques)
        for pieza in ("ingesta_ast_v2.py", "--graph-sensitivity"):
            if pieza not in bash:
                fallos.append(f"{nombre}: el bloque bash no invoca {pieza!r}")
    if not _RE_SHA40.search(texto):
        fallos.append(f"{nombre}: ningun commit completo de 40 hex")
    if not _RE_SHA256.search(texto):
        fallos.append(f"{nombre}: ningun corpus SHA-256 de 64 hex")
    return fallos


class CaseStudyContractTests(unittest.TestCase):
    def test_every_arch_case_study_is_reproducible(self) -> None:
        casos = sorted(CASE_STUDIES.glob(GLOB))
        self.assertTrue(casos, f"universo vacio: {CASE_STUDIES}/{GLOB}")
        fallos = [
            defecto
            for caso in casos
            for defecto in defectos(caso.name, caso.read_text(encoding="utf-8"))
        ]
        self.assertEqual(fallos, [])

    def test_the_falsifier_bites(self) -> None:
        texto = (CASE_STUDIES / "arch-two-readings-20261113.md").read_text(encoding="utf-8")
        self.assertEqual(defectos("completo.md", texto), [])

        sin_commit = "\n".join(
            linea for linea in texto.splitlines() if not linea.startswith("Commit:")
        )
        self.assertIn("falta la declaracion 'Commit:'", "\n".join(defectos("sin-commit.md", sin_commit)))

        sin_comando = "\n".join(
            linea for linea in texto.splitlines() if "--graph-sensitivity" not in linea
        )
        self.assertTrue(defectos("sin-comando.md", sin_comando))


if __name__ == "__main__":
    unittest.main()
