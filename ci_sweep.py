#!/usr/bin/env python3
"""Sweep paginated GitHub PR checks without treating missing data as green."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_SHARDS = ("sim_wh_n150", "sim_bh_p150")
DEFAULT_BLAMED_FILE = "tests/ttnn/unit_tests/operations/transformers/test_prefetcher_worker_pipes.py"
CACHE_VERSION = 1


class ApiError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class GhApi:
    def __init__(self, cache_path: Path | None, ttl: int, retries: int, delay: float) -> None:
        self.cache_path = cache_path
        self.ttl = ttl
        self.retries = retries
        self.delay = delay
        self.cache: dict[str, dict[str, Any]] = {"version": CACHE_VERSION, "entries": {}}
        if cache_path and cache_path.exists():
            try:
                loaded = json.loads(cache_path.read_text(encoding="utf-8"))
                if loaded.get("version") != CACHE_VERSION or not isinstance(loaded.get("entries"), dict):
                    raise ValueError("unsupported cache format")
                self.cache = loaded
            except (OSError, json.JSONDecodeError, AttributeError, ValueError) as exc:
                raise ApiError(f"invalid cache {cache_path}: {exc}") from exc

    def request(self, endpoint: str, *, paginate: bool = False) -> Any:
        key = ("paginate:" if paginate else "") + endpoint
        cached = self.cache["entries"].get(key)
        if cached and time.time() - cached.get("fetched_at", 0) <= self.ttl:
            return cached["data"]
        command = ["gh", "api"]
        if paginate:
            command.extend(["--paginate", "--slurp"])
        command.append(endpoint)
        for attempt in range(self.retries + 1):
            if self.delay:
                time.sleep(self.delay)
            try:
                result = subprocess.run(command, capture_output=True, text=True, check=False)
            except OSError as exc:
                raise ApiError(f"cannot run gh: {exc}") from exc
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                except json.JSONDecodeError as exc:
                    raise ApiError("GitHub API returned invalid JSON") from exc
                self.cache["entries"][key] = {"fetched_at": time.time(), "data": data}
                return data
            detail = result.stderr.strip()
            retryable = re.search(r"rate limit|secondary rate|abuse|429|502|503|504|timed out", detail, re.I)
            if not retryable or attempt == self.retries:
                raise ApiError(f"gh api failed: {detail or 'unknown error'}")
            retry_after = re.search(r"retry after (\d+) seconds?", detail, re.I)
            wait = int(retry_after.group(1)) if retry_after else min(2 ** attempt, 60)
            time.sleep(wait)
        raise ApiError("GitHub API retries exhausted")

    def save(self) -> None:
        if self.cache_path:
            atomic_write(self.cache_path, json.dumps(self.cache, ensure_ascii=False, indent=2) + "\n")


def paginated_items(payload: Any, key: str) -> list[dict[str, Any]]:
    pages = payload if isinstance(payload, list) else [payload]
    result: list[dict[str, Any]] = []
    for page in pages:
        if isinstance(page, dict) and isinstance(page.get(key), list):
            result.extend(item for item in page[key] if isinstance(item, dict))
    return result


def list_pulls(api: GhApi, repo: str, limit: int) -> tuple[list[dict[str, Any]], bool]:
    pulls: list[dict[str, Any]] = []
    page = 1
    while len(pulls) < limit:
        endpoint = f"repos/{repo}/pulls?state=open&per_page=100&page={page}&sort=updated&direction=desc"
        batch = api.request(endpoint)
        if not isinstance(batch, list):
            raise ApiError("pull request page was not a JSON array")
        pulls.extend(item for item in batch if isinstance(item, dict))
        if len(batch) < 100:
            break
        page += 1
    capped = len(pulls) >= limit
    return pulls[:limit], capped


def classify_checks(check_runs: list[dict[str, Any]], shards: tuple[str, ...]) -> tuple[str, list[dict[str, Any]]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for run in check_runs:
        name = str(run.get("name", ""))
        if not any(shard in name for shard in shards):
            continue
        app = run.get("app") or {}
        key = (name, str(app.get("slug", "")))
        rank = (int(run.get("run_attempt", 0)), str(run.get("updated_at", "")))
        prior = latest.get(key)
        prior_app = (prior or {}).get("app") or {}
        prior_rank = (int((prior or {}).get("run_attempt", 0)), str((prior or {}).get("updated_at", "")))
        if prior is None or rank >= prior_rank:
            latest[key] = run
    matches = sorted(latest.values(), key=lambda run: str(run.get("name", "")))
    detail = [{"name": run.get("name"), "status": run.get("status"), "conclusion": run.get("conclusion")} for run in matches]
    if not matches:
        return "SIN_CHECKS", detail
    if any(run.get("conclusion") == "failure" for run in matches):
        return "ROJO", detail
    if any(run.get("status") != "completed" for run in matches):
        return "PENDIENTE", detail
    if all(run.get("conclusion") in {"success", "neutral", "skipped"} for run in matches):
        return "VERDE", detail
    return "NO_VERIFICABLE", detail


def pull_files(api: GhApi, repo: str, number: int) -> set[str]:
    payload = api.request(f"repos/{repo}/pulls/{number}/files?per_page=100", paginate=True)
    files: set[str] = set()
    pages = payload if isinstance(payload, list) else [payload]
    for page in pages:
        if isinstance(page, list):
            files.update(str(item.get("filename")) for item in page if isinstance(item, dict) and item.get("filename"))
        elif isinstance(page, dict):
            files.update(str(item.get("filename")) for item in page.get("files", []) if isinstance(item, dict) and item.get("filename"))
    return files


def inspect_pull(api: GhApi, repo: str, pull: dict[str, Any], shards: tuple[str, ...], blamed_file: str, measured_at: str) -> dict[str, Any]:
    number = int(pull["number"])
    head = pull.get("head") or {}
    sha = head.get("sha")
    record: dict[str, Any] = {
        "repo": repo,
        "pr": number,
        "estado": "NO_VERIFICABLE",
        "causa": "NO_EVALUADA",
        "url": pull.get("html_url", f"https://github.com/{repo}/pull/{number}"),
        "fecha_medicion": measured_at,
        "sha_medicion": sha,
        "shards": [],
    }
    if not sha:
        record["causa"] = "SHA_HEAD_AUSENTE"
        return record
    try:
        payload = api.request(f"repos/{repo}/commits/{sha}/check-runs?per_page=100", paginate=True)
        runs = paginated_items(payload, "check_runs")
        record["estado"], record["shards"] = classify_checks(runs, shards)
        if record["estado"] == "ROJO":
            record["causa"] = "CANDIDATA_FUERA_DEL_DIFF" if blamed_file not in pull_files(api, repo, number) else "CAUSA_EN_DIFF"
        elif record["estado"] == "SIN_CHECKS":
            record["causa"] = "SIN_CHECKS_EN_SHA"
        elif record["estado"] == "NO_VERIFICABLE":
            record["causa"] = "CONCLUSION_NO_CLASIFICADA"
        else:
            record["causa"] = "NO_APLICA"
    except ApiError as exc:
        record["causa"] = f"ERROR_API: {exc}"
    return record


def self_test() -> int:
    cases = [
        ([], "SIN_CHECKS"),
        ([{"name": "sim_wh_n150", "status": "completed", "conclusion": "failure"}], "ROJO"),
        ([{"name": "sim_bh_p150", "status": "in_progress", "conclusion": None}], "PENDIENTE"),
        ([{"name": "sim_wh_n150", "status": "completed", "conclusion": "success"}], "VERDE"),
        ([{"name": "sim_wh_n150", "status": "completed", "conclusion": "cancelled"}], "NO_VERIFICABLE"),
    ]
    for runs, expected in cases:
        actual, _ = classify_checks(runs, DEFAULT_SHARDS)
        if actual != expected:
            print(f"FALLO: esperado {expected}, medido {actual}", file=sys.stderr)
            return 1
    print(f"SELF-TEST: {len(cases)}/{len(cases)} VERDE")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="GitHub owner/repository")
    parser.add_argument("--out", default="-", help="JSON destination (default: stdout)")
    parser.add_argument("--limit", type=int, default=1000, help="maximum open PRs to inventory")
    parser.add_argument("--shards", nargs="+", default=list(DEFAULT_SHARDS))
    parser.add_argument("--blamed-file", default=DEFAULT_BLAMED_FILE)
    parser.add_argument("--cache", type=Path, default=Path.home() / ".cache/auditor-toolkit/ci_sweep.json")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--cache-ttl", type=int, default=900, help="cache lifetime in seconds")
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--request-delay", type=float, default=0.1)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.repo or "/" not in args.repo or args.limit < 1 or args.cache_ttl < 0 or args.retries < 0 or args.request_delay < 0:
        parser.error("--repo owner/name is required; numeric limits must be nonnegative and --limit must be positive")
    measured_at = utc_now()
    api = GhApi(None if args.no_cache else args.cache.expanduser(), args.cache_ttl, args.retries, args.request_delay)
    try:
        pulls, capped = list_pulls(api, args.repo, args.limit)
        records = [inspect_pull(api, args.repo, pull, tuple(args.shards), args.blamed_file, measured_at) for pull in pulls]
        api.save()
    except ApiError as exc:
        print(json.dumps({"repo": args.repo, "estado": "ERROR", "causa": str(exc), "fecha_medicion": measured_at}, ensure_ascii=False), file=sys.stderr)
        return 2
    counts = {state: sum(record["estado"] == state for record in records) for state in ("ROJO", "VERDE", "PENDIENTE", "SIN_CHECKS", "NO_VERIFICABLE")}
    report = {"repo": args.repo, "fecha_medicion": measured_at, "limit": args.limit, "tope_alcanzado": capped, "inventariados": len(records), "conteos": counts, "shards": args.shards, "archivo_culpable_evaluado": args.blamed_file, "registros": records}
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out == "-":
        sys.stdout.write(rendered)
    else:
        atomic_write(Path(args.out).expanduser(), rendered)
    return 0 if not any(record["estado"] == "NO_VERIFICABLE" for record in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
