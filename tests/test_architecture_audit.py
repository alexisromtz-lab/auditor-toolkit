"""HUELLA-ARCHITECTURE-AUDIT-TEST-20261029 Integration coverage for the public audit workflow."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INGESTOR = REPO_ROOT / "tools" / "ingesta_ast_v2.py"
ANALYZER = REPO_ROOT / "tools" / "calculate_arch_index.py"
PUBLISHER = REPO_ROOT / "tools" / "publish_architecture_snapshot.py"


class ArchitectureAuditIntegrationTests(unittest.TestCase):
    def test_ingest_analyze_and_publish_observed_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "sample-repository"
            source_root = repository / "src"
            source_root.mkdir(parents=True)
            sources = {
                "a.py": "from . import b\nvalue = 'a'\n",
                "b.py": "from . import a\nvalue = 'b'\n",
                "c.py": "value = 'c'\n",
            }
            for relative, source in sources.items():
                (source_root / relative).write_text(source, encoding="utf-8")

            subprocess.run(["git", "init", "--quiet", str(repository)], check=True)
            subprocess.run(["git", "-C", str(repository), "config", "user.name", "Audit Test"], check=True)
            subprocess.run(["git", "-C", str(repository), "config", "user.email", "audit-test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(repository), "add", "src"], check=True)
            subprocess.run(["git", "-C", str(repository), "commit", "--quiet", "-m", "sample"], check=True)
            commit = subprocess.run(
                ["git", "-C", str(repository), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            ingested = subprocess.run(
                [
                    sys.executable, str(INGESTOR), str(repository), commit,
                    "--source-root", "src", "--package", "sample",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            analyzed = subprocess.run(
                [
                    sys.executable, str(ANALYZER), "-", "--repo", "example/sample",
                    "--repo-root", str(repository), "--commit", commit,
                    "--source-root", str(source_root),
                ],
                input=ingested.stdout,
                check=True,
                capture_output=True,
                text=True,
            )
            report = json.loads(analyzed.stdout)
            expected_bytes = sum(len(source.encode("utf-8")) for source in sources.values())
            self.assertEqual(report["module_count"], 3)
            self.assertEqual(report["source_file_count"], 3)
            self.assertEqual(report["cyclic_scc_count"], 1)
            self.assertEqual(report["source_bytes"], expected_bytes)
            self.assertEqual(report["cyclic_components"][0]["modules"], ["sample.a", "sample.b"])

            report_path = Path(temporary_directory) / "architecture.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            readme = Path(temporary_directory) / "README.md"
            readme.write_text("# Sample repository\n\nProject description.\n", encoding="utf-8")
            run_url = "https://github.com/example/sample/actions/runs/123"
            publisher_command = [
                sys.executable, str(PUBLISHER), "--report", str(report_path),
                "--readme", str(readme), "--run-url", run_url,
                "--observed-at", "2026-10-29T00:00:00Z",
            ]
            first_publish = subprocess.run(
                publisher_command, check=True, capture_output=True, text=True
            )
            published_readme = readme.read_text(encoding="utf-8")
            second_publish = subprocess.run(
                publisher_command, check=True, capture_output=True, text=True
            )
            self.assertEqual(first_publish.stdout.strip(), "README_UPDATED")
            self.assertEqual(second_publish.stdout.strip(), "README_UNCHANGED")
            self.assertIn(
                "![Static Python scan: 3 modules, 1 cyclic SCC — "
                "observation, not a certification]",
                published_readme,
            )
            self.assertIn("| Python modules | 3 |", published_readme)
            self.assertIn("| Cyclic components (SCC) | 1 |", published_readme)
            self.assertIn(f"| Python source bytes | {expected_bytes} bytes |", published_readme)
            self.assertIn(f"Commit: `{commit}`", published_readme)
            self.assertEqual(readme.read_text(encoding="utf-8"), published_readme)

            # El escudo publica las cifras medidas; un genérico «Audited» no es una medición.
            self.assertIn(
                "https://img.shields.io/badge/static%20scan-"
                "3%20modules%20%C2%B7%201%20cyclic%20SCC-6C48B1",
                published_readme,
            )
            self.assertNotIn("Audited by Platino Labs", published_readme)
            self.assertIn("**What this does not show.**", published_readme)
            self.assertIn("not a security audit", published_readme)
            self.assertIn("these numbers are stale", published_readme)


class BadgeHonestyTests(unittest.TestCase):
    def test_badge_message_carries_the_counts_it_reports(self) -> None:
        sys.path.insert(0, str(REPO_ROOT / "tools"))
        try:
            from publish_architecture_snapshot import _badge_url
        finally:
            sys.path.pop(0)
        self.assertEqual(
            _badge_url(11, 0),
            "https://img.shields.io/badge/static%20scan-"
            "11%20modules%20%C2%B7%200%20cyclic%20SCC-6C48B1",
        )
        self.assertNotEqual(_badge_url(11, 0), _badge_url(11, 1))


if __name__ == "__main__":
    unittest.main()
