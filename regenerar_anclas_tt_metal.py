#!/usr/bin/env python3
"""Verify the public tt-metal diagnostic anchors against GitHub's current state."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPOSITORY = "tenstorrent/tt-metal"
EXPECTED_PR_STATE = "open"
EXPECTED_ANCHORS = 12
ANCHOR_RE = re.compile(r"https://github\.com/tenstorrent/tt-metal/pull/(\d+)#issuecomment-(\d+)")
SHARDS = ("sim_wh_n150", "sim_bh_p150")
CASE_STUDY = Path(__file__).resolve().parent / "case_studies" / "tt-metal.md"


class ApiError(Exception):
    def __init__(self, message: str, *, not_found: bool = False) -> None:
        super().__init__(message)
        self.not_found = not_found


def gh_json(endpoint: str) -> Any:
    try:
        response = subprocess.run(
            ["gh", "api", endpoint], capture_output=True, text=True, check=False
        )
    except OSError as exc:
        raise ApiError(f"cannot run gh: {exc}") from exc
    if response.returncode:
        detail = response.stderr.strip()
        raise ApiError(
            "GitHub API returned 404" if "404" in detail else "GitHub API request failed",
            not_found="404" in detail,
        )
    try:
        return json.loads(response.stdout)
    except json.JSONDecodeError as exc:
        raise ApiError("GitHub API returned invalid JSON") from exc


def read_anchors() -> list[tuple[int, int]]:
    pairs = [
        (int(pr), int(comment))
        for pr, comment in ANCHOR_RE.findall(CASE_STUDY.read_text(encoding="utf-8"))
    ]
    if len(pairs) != EXPECTED_ANCHORS or len(set(pairs)) != EXPECTED_ANCHORS:
        raise ValueError(
            f"expected {EXPECTED_ANCHORS} unique PR/comment anchors; found {len(pairs)}"
        )
    return pairs


def shard_result(check_runs: list[dict[str, Any]]) -> dict[str, Any]:
    per_shard: dict[str, list[dict[str, Any]]] = {shard: [] for shard in SHARDS}
    for check in check_runs:
        name = str(check.get("name", ""))
        for shard in SHARDS:
            if shard in name:
                per_shard[shard].append(
                    {"name": name, "status": check.get("status"), "conclusion": check.get("conclusion")}
                )
    all_matches = [run for runs in per_shard.values() for run in runs]
    if not all_matches:
        status = "NO_ENCONTRADO"
    elif any(run.get("conclusion") == "failure" for run in all_matches):
        status = "ROJO"
    elif any(run.get("status") != "completed" for run in all_matches):
        status = "PENDIENTE"
    elif all(run.get("conclusion") in {"success", "neutral", "skipped"} for run in all_matches):
        status = "VERDE"
    else:
        status = "OTRO"
    return {"status": status, "by_shard": per_shard}


def inspect_anchor(pr_number: int, comment_id: int) -> dict[str, Any]:
    pr_url = f"https://github.com/{REPOSITORY}/pull/{pr_number}"
    entry: dict[str, Any] = {
        "pr": pr_number,
        "pr_url": pr_url,
        "comment_id": comment_id,
        "comment_url": f"{pr_url}#issuecomment-{comment_id}",
        "expected_state": EXPECTED_PR_STATE,
        "current_state": None,
        "merged": None,
        "comment_present": None,
        "shards": {"status": "NO_VERIFICADO", "by_shard": {}},
        "stale_reasons": [],
        "errors": [],
    }
    try:
        pr = gh_json(f"repos/{REPOSITORY}/pulls/{pr_number}")
        entry["current_state"] = pr.get("state")
        entry["merged"] = pr.get("merged_at") is not None
        if pr.get("state") != EXPECTED_PR_STATE or entry["merged"]:
            entry["stale_reasons"].append("estado_del_PR_cambio")
        head_sha = pr.get("head", {}).get("sha")
    except ApiError as exc:
        entry["errors"].append(f"pr_api: {exc}")
        head_sha = None

    try:
        comment = gh_json(f"repos/{REPOSITORY}/issues/comments/{comment_id}")
        entry["comment_present"] = (
            comment.get("id") == comment_id
            and f"/pull/{pr_number}#issuecomment-{comment_id}" in comment.get("html_url", "")
        )
        if not entry["comment_present"]:
            entry["stale_reasons"].append("comentario_no_coincide_con_ancla")
    except ApiError as exc:
        entry["comment_present"] = False if exc.not_found else None
        if exc.not_found:
            entry["stale_reasons"].append("comentario_diagnostico_ya_no_existe")
        else:
            entry["errors"].append(f"comment_api: {exc}")

    if head_sha:
        try:
            checks = gh_json(
                f"repos/{REPOSITORY}/commits/{head_sha}/check-runs?per_page=100"
            )
            entry["shards"] = shard_result(checks.get("check_runs", []))
        except ApiError as exc:
            entry["errors"].append(f"check_runs_api: {exc}")
    else:
        entry["errors"].append("check_runs_api: head SHA unavailable")

    if entry["stale_reasons"]:
        entry["status"] = "ANCLA_CADUCA"
    elif entry["errors"]:
        entry["status"] = "NO_VERIFICABLE"
    elif entry["shards"]["status"] != "ROJO":
        entry["status"] = "SHARD_NO_ROJO_ACTUAL"
    else:
        entry["status"] = "ANCLA_VIGENTE"
    return entry


def main() -> int:
    try:
        anchors = read_anchors()
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2

    results = [inspect_anchor(pr, comment) for pr, comment in anchors]
    if any(item["status"] == "ANCLA_CADUCA" for item in results):
        status = "ANCLA_CADUCA"
    elif any(item["status"] == "NO_VERIFICABLE" for item in results):
        status = "NO_VERIFICABLE"
    elif any(item["status"] == "SHARD_NO_ROJO_ACTUAL" for item in results):
        status = "SHARD_NO_ROJO_ACTUAL"
    else:
        status = "ANCLAS_VIGENTES"
    report = {
        "repository": REPOSITORY,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "expected_pr_state": EXPECTED_PR_STATE,
        "shards_checked": list(SHARDS),
        "anchors_checked": len(results),
        "anchors": results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "ANCLAS_VIGENTES" else 1


if __name__ == "__main__":
    sys.exit(main())
