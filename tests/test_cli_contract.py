"""HUELLA-CLI-CORPUS-OBLIGATORIO-TEST-20261113 — a flag that cannot work is a lie.

Measured on `2026-11-13` against `main` at `0c079a6`: `--repo`, `--repo-root` and
`--commit` were documented as an alternative input, and the code they reach built an
**empty** corpus and could only raise `esquema AST no compatible: None`. The message the
user saw named the schema; the cause was that the corpus had never been read.

`corpus_json` is the only input. The three flags ratify that corpus against a checkout.
Falsifier: restore the empty-corpus branch and the first case goes red, because the
process still exits `2` but stops saying that the corpus is what is missing.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYZER = REPO_ROOT / "tools" / "calculate_arch_index.py"


def run(*arguments: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ANALYZER), *arguments],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


class CorpusRequirementTests(unittest.TestCase):
    def test_without_corpus_the_error_names_the_corpus(self) -> None:
        result = run("--repo", "demo", "--repo-root", ".", "--commit", "0" * 40)
        self.assertEqual(result.returncode, 2)
        self.assertIn("corpus_json es obligatorio", result.stderr)
        self.assertNotIn("esquema AST no compatible", result.stderr)

    def test_a_corpus_without_checkout_names_the_three_flags(self) -> None:
        result = run("-", stdin="{}")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--repo, --repo-root y --commit", result.stderr)

    def test_the_negative_control_still_runs(self) -> None:
        result = run("--self-test")
        self.assertEqual(result.returncode, 0)
        self.assertIn("SELF-TEST", result.stdout)


if __name__ == "__main__":
    unittest.main()
