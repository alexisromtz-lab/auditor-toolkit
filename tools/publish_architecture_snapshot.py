#!/usr/bin/env python3
"""HUELLA-ARCHITECTURE-README-PUBLISHER-20261029 Update the README snapshot idempotently."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

START_MARKER = "<!-- PLATINO-LABS-ARCHITECTURE-AUDIT:START -->"
END_MARKER = "<!-- PLATINO-LABS-ARCHITECTURE-AUDIT:END -->"


def _non_negative_integer(report: dict[str, Any], key: str) -> int:
    value = report.get(key)
    if type(value) is not int or value < 0:
        raise ValueError(f"el reporte requiere {key} como entero no negativo")
    return value


def _badge_url(modules: int, cycles: int) -> str:
    """El escudo lleva las cifras medidas: un badge genérico no es una medición."""
    return (
        "https://img.shields.io/badge/static%20scan-"
        f"{modules}%20modules%20%C2%B7%20{cycles}%20cyclic%20SCC-6C48B1"
    )


def _render(report: dict[str, Any], run_url: str, observed_at: str) -> str:
    commit = report.get("commit")
    if not isinstance(commit, str) or re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit) is None:
        raise ValueError("el reporte requiere un commit Git completo")
    modules = _non_negative_integer(report, "module_count")
    cycles = _non_negative_integer(report, "cyclic_scc_count")
    source_bytes = _non_negative_integer(report, "source_bytes")

    parsed_url = urlsplit(run_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc or any(
        character in run_url for character in "\r\n ()"
    ):
        raise ValueError("run_url debe ser un URL HTTPS sin espacios ni paréntesis")
    try:
        datetime.strptime(observed_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise ValueError("observed_at debe usar formato UTC YYYY-MM-DDTHH:MM:SSZ") from None

    return "\n".join((
        START_MARKER,
        f"[![Static Python scan: {modules:,} modules, {cycles:,} cyclic SCC — "
        f"observation, not a certification]({_badge_url(modules, cycles)})]({run_url})",
        "",
        "### Static architecture scan · observed metrics (not a certification)",
        "",
        "| Observed metric | Value |",
        "|---|---:|",
        f"| Python modules | {modules:,} |",
        f"| Cyclic components (SCC) | {cycles:,} |",
        f"| Python source bytes | {source_bytes:,} bytes |",
        "",
        f"Commit: `{commit}` · Observed at: `{observed_at}` (UTC) · [Workflow run]({run_url})",
        "",
        "**What this shows.** How many tracked Python files are eligible for static analysis, "
        "how many of their dependency components close a cycle, and how many bytes they total — "
        "measured on the single commit cited above.",
        "",
        "**What this does not show.** It is not a security audit, not a quality score, not a "
        "certification, not an endorsement and not a comparison against other repositories. "
        "Zero cyclic components does not mean the code is safe; cycles do not mean it is unsound. "
        "The numbers are produced by the workflow run linked above; if that run is older than the "
        "commit you are reading, the workflow is not running and these numbers are stale.",
        END_MARKER,
    ))


def _insert_near_title(contents: str, block: str) -> str:
    heading = re.search(r"(?m)^# [^\r\n]*(?:\r?\n|$)", contents)
    if heading is None:
        prefix = "" if not contents or contents.endswith("\n") else "\n"
        return f"{contents}{prefix}\n{block}\n"
    newline = "\r\n" if "\r\n" in contents else "\n"
    block = block.replace("\n", newline)
    suffix = contents[heading.end():].lstrip("\r\n")
    return f"{contents[:heading.end()]}{newline}{block}{newline}{suffix}"


def update_readme(readme_path: Path, report: dict[str, Any], run_url: str, observed_at: str) -> bool:
    contents = readme_path.read_text(encoding="utf-8")
    block = _render(report, run_url, observed_at)
    starts = contents.count(START_MARKER)
    ends = contents.count(END_MARKER)
    if starts != ends or starts > 1:
        raise ValueError("el README tiene marcadores de auditoría incompletos o duplicados")
    if starts == 1:
        start = contents.index(START_MARKER)
        end = contents.index(END_MARKER)
        if end < start:
            raise ValueError("el marcador final precede al marcador inicial")
        block_end = end + len(END_MARKER)
        updated = contents[:start] + block + contents[block_end:]
    else:
        updated = _insert_near_title(contents, block)
    if updated == contents:
        return False
    with readme_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(updated)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True, help="JSON del índice de arquitectura")
    parser.add_argument("--readme", type=Path, required=True, help="README.md que recibirá el bloque agregado")
    parser.add_argument("--run-url", required=True, help="URL HTTPS de la ejecución de GitHub Actions")
    parser.add_argument("--observed-at", required=True, help="hora UTC ISO-8601 terminada en Z")
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError("la raíz del reporte debe ser un objeto JSON")
        changed = update_readme(args.readme, report, args.run_url, args.observed_at)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print("README_UPDATED" if changed else "README_UNCHANGED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
