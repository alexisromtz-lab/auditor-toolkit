#!/usr/bin/env python3
"""Auditoría local, de solo lectura, de workflows GitHub Actions.

Uso:
  python3 tools/auditar_supply_chain.py
  python3 tools/auditar_supply_chain.py --root /ruta/al/checkout
  python3 tools/auditar_supply_chain.py --repo owner/name
  python3 tools/auditar_supply_chain.py --owner alexisromtz-lab --include-forks
  python3 tools/auditar_supply_chain.py --self-test

Sin --root, enumera repos accesibles del owner con `gh`, excluye forks y lee
cada default branch por GitHub API. No clona, no escribe y no imprime YAML ni
valores potencialmente sensibles. Un universo vacío o no legible nunca pasa.

SC-1 requiere permisos raíz explícitos y prohíbe scopes write heredados; una
concesión write a nivel de job se informa para revisión. SC-2 reutiliza el
criterio del gate existente para refs inmutables. SC-3 cubre tanto
pull_request_target como workflow_run y delega la detección al mismo gate.
"""
# HUELLA-AUDITORIA-SUPPLY-CHAIN-20261022
# HUELLA-AUDITAR-REPO-AJENO-20261030: --repo owner/name audita UN repo ajeno por
# GitHub API de solo lectura (sin clonar, sin escribir, sin token extra). El
# nombre se valida antes de la primera llamada: REPO_INVALIDO y RC 2, nunca red.
# HUELLA-AUDITORIA-SUPPLY-CHAIN-DETALLE-20261022
# HUELLA-AUDITORIA-SUPPLY-CHAIN-SC3-ALCANCE-20261022
# HUELLA-AUDITORIA-SUPPLY-CHAIN-ADJUDICADAS-20261022
# HUELLA-AUDITORIA-SUPPLY-CHAIN-ADJUDICADO-OVERALL-20261022
# HUELLA-SC1-DETAIL-SCOPE-20261030: SC1 era la única clase sin `detail`: calculaba
# `writes` (job) y `root_writes` (root) y los descartaba. Ahora publica el conjunto
# de scopes ordenado, que es lo que permite agrupar 211 hallazgos en patrones. No
# hay lista blanca (borraría los write reales) y no se declara seguro: la seguridad
# es scope x evento y el trigger sigue NO_MEDIDO (PyYAML mapea `on:` a True).
from __future__ import annotations

import argparse
import importlib.util
import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

_AQUI = Path(__file__).resolve().parent

try:
    _spec = importlib.util.spec_from_file_location(
        "gate_workflows_ci", _AQUI / "gate_workflows_ci.py")
    gate = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(gate)
except SystemExit as exc:  # PyYAML ausente: el gate declara RC 30 al importarse.
    gate = None
    MOTOR_ERROR = "DEPENDENCIA_GATE_AUSENTE_RC_%s" % exc.code
except Exception:
    gate = None
    MOTOR_ERROR = "GATE_NO_IMPORTABLE"
else:
    MOTOR_ERROR = None


class AuditError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _finding(
    code: str,
    invariant: str,
    status: str,
    workflow: str,
    job: str = "-",
    detail: str = "",
) -> dict:
    return {
        "code": code,
        "invariant": invariant,
        "status": status,
        "workflow": workflow,
        "job": job,
        "detail": detail[:160],
    }


def _permission_findings(text: str, workflow_path: str) -> list[dict]:
    """Evalúa solo permisos declarados; defaults de repo/org son invisibles."""
    try:
        data = gate.yaml.safe_load(text)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []

    findings = []
    root_permissions = data.get("permissions")
    if root_permissions is None:
        findings.append(_finding("SC1_ROOT_PERMISSIONS_MISSING", "SC-1", "FAIL", workflow_path))
    elif isinstance(root_permissions, str):
        value = root_permissions.strip().lower()
        if value == "write-all":
            findings.append(_finding("SC1_ROOT_WRITE_ALL", "SC-1", "FAIL", workflow_path))
        elif value == "read-all":
            findings.append(_finding("SC1_ROOT_READ_ALL_REVIEW", "SC-1", "REVIEW", workflow_path))
        else:
            findings.append(_finding("SC1_ROOT_PERMISSIONS_INVALID", "SC-1", "FAIL", workflow_path))
    elif isinstance(root_permissions, dict):
        root_writes = sorted(
            str(scope) for scope, permission in root_permissions.items()
            if str(permission).strip().lower() == "write"
        )
        if root_writes:
            findings.append(_finding(
                "SC1_ROOT_WRITE_INHERITED", "SC-1", "FAIL", workflow_path,
                detail=",".join(root_writes),
            ))
        elif any(str(value).strip().lower() not in {"read", "none"} for value in root_permissions.values()):
            findings.append(_finding("SC1_ROOT_PERMISSION_VALUE_UNKNOWN", "SC-1", "REVIEW", workflow_path))
    else:
        findings.append(_finding("SC1_ROOT_PERMISSIONS_INVALID", "SC-1", "FAIL", workflow_path))

    jobs = data.get("jobs")
    if isinstance(jobs, dict):
        for job_name, job in sorted(jobs.items(), key=lambda item: str(item[0])):
            if not isinstance(job, dict):
                continue
            permissions = job.get("permissions")
            if isinstance(permissions, str):
                if permissions.strip().lower() == "write-all":
                    findings.append(_finding("SC1_JOB_WRITE_ALL_REVIEW", "SC-1", "REVIEW", workflow_path, str(job_name)))
            elif isinstance(permissions, dict):
                writes = sorted(
                    scope for scope, permission in permissions.items()
                    if str(permission).strip().lower() == "write"
                )
                if writes:
                    findings.append(_finding(
                        "SC1_JOB_WRITE_SCOPE_REVIEW", "SC-1", "REVIEW", workflow_path,
                        str(job_name), detail=",".join(writes),
                    ))

    return findings


def _analyze_files(files: list[tuple[str, str]], con_manifiesto: bool = False) -> dict:
    if gate is None:
        return {"status": "UNVERIFIABLE", "findings": [], "error": MOTOR_ERROR}
    if not files:
        vacio = {
            "status": "NO_MEASUREMENT",
            "findings": [_finding("UNIVERSO_VACIO", "UNIVERSE", "NO_MEASUREMENT", ".github/workflows")],
            "error": None,
        }
        if con_manifiesto:
            vacio["archivos"] = []
        return vacio

    findings = []
    unparseable = False
    for workflow_path, text in sorted(files, key=lambda item: item[0]):
        gate_findings = gate.analizar(text, workflow_path)
        if any(item.get("rc") == 32 for item in gate_findings):
            unparseable = True
            findings.append(_finding("YAML_INVALIDO", "GATE", "UNVERIFIABLE", workflow_path))
            continue

        findings.extend(_permission_findings(text, workflow_path))
        for item in gate_findings:
            rc = item.get("rc")
            if rc == 32:
                continue
            findings.append(_finding(
                "GATE_RC_%s_%s" % (rc, item.get("causa", "HALLAZGO")),
                "GATE",
                "FAIL",
                workflow_path,
                str(item.get("job", "-")),
                str(item.get("detalle", "")),
            ))

    if unparseable:
        status = "UNVERIFIABLE"
    elif any(item["status"] == "FAIL" for item in findings):
        status = "FINDINGS"
    elif findings:
        status = "REVIEW"
    else:
        status = "PASS"
    # HUELLA-SUPPLY-DENOMINADOR-20261031 — el denominador viaja con el numerador.
    # Sin `workflows`, toda tasa calculada desde `findings` es una cota superior
    # disfrazada: solo se ven los workflows donde algo se declaro.
    # HUELLA-SUPPLY-MANIFIESTO-20261031 — un workflow limpio no aparece en ningun
    # `finding`, asi que el conteo no deja leer «14 auditados, 7 con hallazgos» vs
    # «14 con algo»: falta la identidad de los limpios. El manifiesto publica la
    # superficie leida. Sin sha por archivo: `ref` es un commit y `git/trees/{ref}`
    # resuelve los blobs; un sha cuyo contenido no se guarda no se verifica. Bandera,
    # no campo permanente: la procedencia se paga cuando se pide.
    resultado = {"status": status, "findings": findings, "error": None, "workflows": len(files)}
    if con_manifiesto:
        resultado["archivos"] = sorted(item[0] for item in files)
    return resultado


def _local_files(root: Path) -> list[tuple[str, str]]:
    workflows_dir = root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return []
    files = []
    for path in sorted(workflows_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}:
            try:
                files.append((path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")))
            except (OSError, UnicodeError):
                raise AuditError("WORKFLOW_NO_LEGIBLE")
    return files


def _gh_json(arguments: list[str]):
    try:
        result = subprocess.run(
            ["gh", *arguments], capture_output=True, text=True, check=False,
        )
    except OSError:
        raise AuditError("GH_CLI_NO_DISPONIBLE")
    if result.returncode:
        raise AuditError("GH_API_NO_DISPONIBLE")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise AuditError("RESPUESTA_GH_INVALIDA")


def _workflows_por_carpeta(full_name: str, commit: str) -> list[dict]:
    """Los workflows de `.github/workflows` leidos sin arbol recursivo.

    El arbol recursivo de un repo grande vuelve `truncated: true` (medido:
    twentyhq/twenty, 47 103 entradas) y morir ahi deja el denominador del sector
    sin su decimo repo. La carpeta se pide sola: devuelve sus hijos directos con
    su `sha` de blob y no depende del tamano del repo.

    La sonda va anclada al `commit` ya resuelto y no a la rama por defecto. Sin
    `?ref=` el listado se lee en la punta viva mientras el JSON publica el
    `commit` resuelto antes: si la rama se mueve entre las dos llamadas, el
    `--manifiesto` certifica rutas que no son las de su propio `ref`. La rama
    sana no tiene ese hueco porque pide el arbol de `commit`.

    El error se renombra en vez de propagarse generico: `GH_API_NO_DISPONIBLE`
    no distingue «el repo no tiene la carpeta» de «la API se cayo», y aqui la
    sonda que falla tiene nombre propio. No se atrapa para devolver vacio: una
    lista vacia se leeria como universo vacio, que es un veredicto, y una API
    rota no es un veredicto.
    """
    try:
        entradas = _gh_json(
            ["api", "repos/%s/contents/.github/workflows?ref=%s" % (full_name, commit)]
        )
    except AuditError as exc:
        raise AuditError("CARPETA_WORKFLOWS_ILEGIBLE") from exc
    if not isinstance(entradas, list):
        raise AuditError("CARPETA_WORKFLOWS_INVALIDA")
    return [
        entry for entry in entradas
        if entry.get("type") == "file"
        and "/" not in str(entry.get("name", ""))
        and Path(str(entry.get("name", ""))).suffix.lower() in {".yml", ".yaml"}
    ]


def _remote_files(full_name: str) -> tuple[str, list[tuple[str, str]]]:
    metadata = _gh_json(["api", "repos/%s" % full_name])
    branch = metadata.get("default_branch")
    if not branch:
        raise AuditError("DEFAULT_BRANCH_AUSENTE")

    encoded_branch = quote(str(branch), safe="")
    ref = _gh_json(["api", "repos/%s/git/ref/heads/%s" % (full_name, encoded_branch)])
    commit = ref.get("object", {}).get("sha")
    if not commit:
        raise AuditError("DEFAULT_BRANCH_SHA_AUSENTE")

    # HUELLA-SUPPLY-TREE-TRUNCADO-20261031 — un arbol truncado no es un repo sin
    # workflows. Antes se moria con ARBOL_GIT_TRUNCADO; ahora se mide la carpeta.
    # La rama del arbol NO se toca para los repos que ya median: cambiar el camino
    # de los nueve repos firmados habria movido una linea base que hoy es
    # reproducible byte a byte. Solo el truncado cambia de sonda, y por eso el
    # diff del censo de los nueve tiene que seguir dando RC 0.
    tree = _gh_json(["api", "repos/%s/git/trees/%s?recursive=1" % (full_name, commit)])
    if tree.get("truncated"):
        paths = _workflows_por_carpeta(full_name, commit)
    else:
        paths = [
            entry for entry in tree.get("tree", [])
            if entry.get("type") == "blob"
            and entry.get("path", "").startswith(".github/workflows/")
            and "/" not in entry.get("path", "")[len(".github/workflows/"):]
            and Path(entry.get("path", "")).suffix.lower() in {".yml", ".yaml"}
        ]

    files = []
    for entry in sorted(paths, key=lambda item: item["path"]):
        blob = _gh_json(["api", "repos/%s/git/blobs/%s" % (full_name, entry["sha"])])
        if blob.get("encoding") != "base64":
            raise AuditError("BLOB_NO_BASE64")
        try:
            text = base64.b64decode(blob.get("content", ""), validate=False).decode("utf-8")
        except (ValueError, UnicodeError):
            raise AuditError("WORKFLOW_NO_UTF8")
        files.append((entry["path"], text))
    return str(commit), files


def _remote_result(full_name: str, con_manifiesto: bool = False) -> dict:
    """Un solo repo ajeno por nombre completo: sin clonar, sin escribir."""
    partes = full_name.split("/") if full_name else []
    if len(partes) != 2 or not all(parte.strip() for parte in partes):
        raise AuditError("REPO_INVALIDO")
    commit, files = _remote_files(full_name)
    result = _analyze_files(files, con_manifiesto)
    metadata = _gh_json(["api", "repos/%s" % full_name])
    return {
        "repository": full_name,
        "source": "github_api_read_only",
        "visibility": metadata.get("visibility"),
        "ref": commit,
        **result,
    }


def _local_result(root: Path, con_manifiesto: bool = False) -> dict:
    root = root.resolve()
    if not root.is_dir():
        raise AuditError("ROOT_NO_EXISTE")
    result = _analyze_files(_local_files(root), con_manifiesto)
    return {
        "repository": root.name,
        "source": "local",
        "ref": None,
        **result,
    }


def _remote_results(owner: str, include_forks: bool, con_manifiesto: bool = False) -> list[dict]:
    repos = _gh_json([
        "repo", "list", owner, "--limit", "1000",
        "--json", "nameWithOwner,isFork,visibility",
    ])
    if not isinstance(repos, list):
        raise AuditError("LISTA_REPOS_INVALIDA")
    selected = [
        repo for repo in repos
        if include_forks or not repo.get("isFork", False)
    ]
    results = []
    for repo in sorted(selected, key=lambda item: item.get("nameWithOwner", "")):
        full_name = repo.get("nameWithOwner")
        if not full_name:
            results.append({"repository": "?", "source": "github_api", "ref": None,
                            "status": "UNVERIFIABLE", "findings": [], "error": "NOMBRE_REPO_AUSENTE"})
            continue
        try:
            commit, files = _remote_files(full_name)
            result = _analyze_files(files, con_manifiesto)
            results.append({
                "repository": full_name,
                "source": "github_api_read_only",
                "visibility": repo.get("visibility"),
                "ref": commit,
                **result,
            })
        except AuditError as exc:
            results.append({
                "repository": full_name,
                "source": "github_api_read_only",
                "visibility": repo.get("visibility"),
                "ref": None,
                "status": "UNVERIFIABLE",
                "findings": [],
                "error": exc.code,
            })
    return results


def _registry_huerfanas(rows: list[dict], usadas: set[int]) -> list[dict]:
    return [
        {"index": i, "code": rows[i].get("code"), "workflow": rows[i].get("workflow")}
        for i in range(len(rows))
        if i not in usadas
    ]


def _load_adjudicadas(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise AuditError("ADJUDICADAS_ILEGIBLES")
    rows = data.get("adjudicadas") if isinstance(data, dict) else data
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise AuditError("ADJUDICADAS_INVALIDAS")
    return rows


def _recompute_status(result: dict) -> None:
    statuses = {item.get("status") for item in result.get("findings", [])}
    if "UNVERIFIABLE" in statuses:
        result["status"] = "UNVERIFIABLE"
    elif "FAIL" in statuses:
        result["status"] = "FINDINGS"
    elif "REVIEW" in statuses:
        result["status"] = "REVIEW"
    elif "ADJUDICADO" in statuses:
        result["status"] = "ADJUDICADO"
    else:
        result["status"] = "PASS"


def _apply_adjudicadas(results: list[dict], rows: list[dict]) -> list[dict]:
    """Baja a ADJUDICADO solo las filas declaradas; deja motivo y acta a la vista."""
    usadas: set[int] = set()
    for result in results:
        for finding in result.get("findings", []):
            if finding.get("status") not in {"FAIL", "REVIEW"}:
                continue
            for index, row in enumerate(rows):
                if row.get("code") != finding.get("code"):
                    continue
                if row.get("workflow") and row["workflow"] != finding.get("workflow"):
                    continue
                if row.get("job") and row["job"] != finding.get("job"):
                    continue
                finding["status"] = "ADJUDICADO"
                finding["motivo"] = str(row.get("motivo", ""))[:200]
                finding["acta"] = str(row.get("acta", ""))[:200]
                usadas.add(index)
                break
        if result.get("findings"):
            _recompute_status(result)
    return _registry_huerfanas(rows, usadas)


def _por_codigo(results: list[dict]) -> dict:
    """Desglose por codigo con TRES terminos: ocurrencias, workflows y repos.

    Un `n` solo no distingue «607 hallazgos» de «159 workflows»: el mismo codigo
    se repite varias veces dentro de un workflow. La clave de workflow es el par
    (repo, ruta) y no la ruta sola, porque dos repos comparten
    `.github/workflows/ci.yml` y contar rutas colapsaria dos superficies en una.
    """
    tabla: dict[str, dict] = {}
    for result in results:
        repo = str(result.get("repository") or "?")
        for finding in result.get("findings") or []:
            code = str(finding.get("code") or "?")
            fila = tabla.setdefault(
                code,
                {
                    "invariant": str(finding.get("invariant") or "?"),
                    "n": 0,
                    "workflows": set(),
                    "repos": set(),
                },
            )
            fila["n"] += 1
            fila["workflows"].add((repo, str(finding.get("workflow") or "?")))
            fila["repos"].add(repo)
    return {
        code: {
            "invariant": fila["invariant"],
            "n": fila["n"],
            "workflows": len(fila["workflows"]),
            "repos": len(fila["repos"]),
        }
        for code, fila in sorted(tabla.items())
    }


def _summary(results: list[dict]) -> dict:
    counts = {key: 0 for key in ("PASS", "FINDINGS", "REVIEW", "ADJUDICADO", "NO_MEASUREMENT", "UNVERIFIABLE")}
    for result in results:
        status = result.get("status", "UNVERIFIABLE")
        counts[status] = counts.get(status, 0) + 1
    if counts["UNVERIFIABLE"] or counts["NO_MEASUREMENT"]:
        overall = "INCOMPLETE"
    elif counts["FINDINGS"]:
        overall = "FINDINGS"
    elif counts["REVIEW"]:
        overall = "REVIEW"
    elif counts["ADJUDICADO"]:
        overall = "ADJUDICADO"
    else:
        overall = "PASS"
    # HUELLA-SUPPLY-PORCODIGO-20261031 — `counts` cuenta repos por status y no dice
    # QUE codigo aparece: el censo del enjambre desglosa por (repo, codigo) y esta
    # ruta se quedaba un piso por detras. El desglose viaja con su denominador
    # (`workflows` leidos, no `findings` emitidos) para que la tasa se pueda
    # calcular sin volver a derivar la superficie: un numerador sin denominador
    # con nombre es una cota superior disfrazada.
    return {
        "overall": overall,
        "repositories": len(results),
        "counts": counts,
        "workflows": sum(int(result.get("workflows") or 0) for result in results),
        "por_codigo": _por_codigo(results),
    }


def _self_test() -> tuple[list[dict], bool]:
    cases = [
        (
            "SC1_ROOT_PERMISSIONS_EXPLICIT",
            "permissions:\n  contents: read\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps: []\n",
            set(),
        ),
        (
            "SC1_ROOT_PERMISSIONS_MISSING",
            "jobs:\n  check:\n    runs-on: ubuntu-latest\n    steps: []\n",
            {"SC1_ROOT_PERMISSIONS_MISSING"},
        ),
        (
            "SC2_FLOATING_REF",
            "permissions:\n  contents: read\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n",
            {"GATE_RC_5_REF_MUTABLE"},
        ),
        (
            "SC3_POISONED_TRIGGER",
            "permissions:\n  contents: write\non:\n  pull_request_target:\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683\n        with:\n          ref: ${{ github.event.pull_request.head.sha }}\n",
            {"GATE_RC_3_DISPARADOR_ENVENENADO"},
        ),
        (
            "SC3_WORKFLOW_RUN",
            "permissions:\n  contents: write\non:\n  workflow_run:\n    workflows: [CI]\n    types: [completed]\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683\n        with:\n          ref: ${{ github.event.workflow_run.head_sha }}\n",
            {"GATE_RC_3_DISPARADOR_ENVENENADO"},
        ),
        (
            "SC1_ROOT_WRITE_ALL",
            "permissions: write-all\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps: []\n",
            {"SC1_ROOT_WRITE_ALL"},
        ),
        (
            "SC1_ROOT_READ_ALL_REVIEW",
            "permissions: read-all\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps: []\n",
            {"SC1_ROOT_READ_ALL_REVIEW"},
        ),
        (
            "SC1_ROOT_PERMISSIONS_INVALID_STR",
            "permissions: banana\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps: []\n",
            {"SC1_ROOT_PERMISSIONS_INVALID"},
        ),
        (
            "SC1_ROOT_PERMISSIONS_INVALID_LIST",
            "permissions:\n  - contents\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps: []\n",
            {"SC1_ROOT_PERMISSIONS_INVALID"},
        ),
        (
            "SC1_ROOT_WRITE_INHERITED",
            "permissions:\n  contents: write\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps: []\n",
            {"SC1_ROOT_WRITE_INHERITED"},
        ),
        (
            "SC1_ROOT_PERMISSION_VALUE_UNKNOWN",
            "permissions:\n  contents: admin\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps: []\n",
            {"SC1_ROOT_PERMISSION_VALUE_UNKNOWN"},
        ),
        # HUELLA-SUPPLY-SELFTEST-14-FILAS-20261031 — los 7 codigos SC1_ROOT_* quedan
        # asertados uno a uno; sin estas filas un port que rompa una rama devuelve verde.
    ]
    rows = []
    for name, text, expected in cases:
        result = _analyze_files([(name + ".yml", text)])
        measured = {item["code"] for item in result["findings"]}
        ok = expected.issubset(measured)
        rows.append({"case": name, "expected": sorted(expected), "measured": sorted(measured), "ok": ok})

    # HUELLA-SC1-DETAIL-SELFTEST-20261031 — el `detail` es el campo que colapsa 10
    # hallazgos en 5 patrones, y ninguna fila lo asertaba: `measured` compara solo
    # codigos. Se aserta el conjunto EXACTO, no «no vacio y ordenado»: perder un
    # scope conserva las dos propiedades y pierde el patron. Las dos filas cubren
    # las dos ramas (root y job), que son las dos que descartaban el calculo.
    detalle_root = {
        "workflow": "detalle_root.yml",
        "text": (
            "permissions:\n"
            "  id-token: write\n"
            "  attestations: write\n"
            "  contents: read\n"
            "jobs:\n"
            "  check:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps: []\n"
        ),
        "expected": [("SC1_ROOT_WRITE_INHERITED", "-", "attestations,id-token")],
    }
    detalle_job_fuera_de_orden = {
        "workflow": "detalle_job.yml",
        "text": (
            "permissions:\n"
            "  contents: read\n"
            "jobs:\n"
            "  release:\n"
            "    runs-on: ubuntu-latest\n"
            "    permissions:\n"
            "      pull-requests: write\n"
            "      contents: write\n"
            "    steps: []\n"
        ),
        "expected": [("SC1_JOB_WRITE_SCOPE_REVIEW", "release", "contents,pull-requests")],
    }
    for caso in (detalle_root, detalle_job_fuera_de_orden):
        resultado = _analyze_files([(caso["workflow"], caso["text"])])
        medido = [
            (item["code"], item["job"], item["detail"])
            for item in resultado["findings"]
            if item["code"].startswith("SC1_")
        ]
        rows.append({
            "case": "SC1_DETAIL_%s" % caso["workflow"].split(".")[0].upper(),
            "expected": ["%s|%s|%s" % fila for fila in caso["expected"]],
            "measured": ["%s|%s|%s" % fila for fila in medido],
            "ok": medido == caso["expected"],
        })

    # HUELLA-SUPPLY-MANIFIESTO-20261031 — dos workflows, uno con hallazgo y uno
    # limpio. El limpio es el falsador: un manifiesto derivado de `findings` lo
    # pierde y el conteo seguiria diciendo 2. La segunda fila es el nulo de la
    # bandera: sin `--manifiesto` el campo no existe, no existe vacio.
    con_manifiesto = _analyze_files([
        ("zeta.yml", "jobs:\n  check:\n    runs-on: ubuntu-latest\n    steps: []\n"),
        ("alfa.yml", "permissions:\n  contents: read\njobs: {}\n"),
    ], con_manifiesto=True)
    sin_bandera = _analyze_files([
        ("zeta.yml", "jobs:\n  check:\n    runs-on: ubuntu-latest\n    steps: []\n"),
    ])
    rows.append({
        "case": "MANIFIESTO_PUBLICA_SUPERFICIE",
        "expected": ["alfa.yml,zeta.yml", "sin archivos"],
        "measured": [
            ",".join(con_manifiesto.get("archivos", [])),
            "con archivos" if "archivos" in sin_bandera else "sin archivos",
        ],
        "ok": (
            con_manifiesto.get("archivos") == ["alfa.yml", "zeta.yml"]
            and "archivos" not in sin_bandera
        ),
    })

    # HUELLA-SUPPLY-PORCODIGO-20261031 — tres falsadores en una fila y un nulo.
    # (A) `workflows = n` daria 3 en vez de 2: el codigo GATE_RC_5 aparece dos veces
    # dentro del mismo `ci.yml` de alfa. (B) clave por ruta sola daria 1 en vez de 2:
    # beta repite la ruta `ci.yml` en otro repo. (C) `repos = len(results)` daria 2
    # en SC1_ROOT_PERMISSIONS_MISSING, que solo vive en alfa. El denominador se falsa
    # con `limpio.yml`: 3 workflows leidos y 2 con hallazgo; derivarlo de `findings`
    # da 2 y hace la tasa una cota superior.
    resumen_por_codigo = _summary([
        {"repository": "alfa", **_analyze_files([
            (
                "ci.yml",
                "jobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n"
                "      - uses: actions/checkout@v4\n"
                "      - uses: actions/setup-node@v4\n",
            ),
            ("limpio.yml", "permissions:\n  contents: read\njobs: {}\n"),
        ])},
        {"repository": "beta", **_analyze_files([
            (
                "ci.yml",
                "permissions:\n  contents: read\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - uses: actions/checkout@v4\n",
            ),
        ])},
    ])
    ref = resumen_por_codigo["por_codigo"].get("GATE_RC_5_REF_MUTABLE", {})
    perm_missing = resumen_por_codigo["por_codigo"].get("SC1_ROOT_PERMISSIONS_MISSING", {})
    rows.append({
        "case": "POR_CODIGO_PUBLICA_DENOMINADOR",
        "expected": ["REF:n=3/wf=2/repos=2", "PERM:n=1/wf=1/repos=1", "workflows=3"],
        "measured": [
            "REF:n=%s/wf=%s/repos=%s" % (ref.get("n"), ref.get("workflows"), ref.get("repos")),
            "PERM:n=%s/wf=%s/repos=%s" % (
                perm_missing.get("n"), perm_missing.get("workflows"), perm_missing.get("repos"),
            ),
            "workflows=%s" % resumen_por_codigo.get("workflows"),
        ],
        "ok": (
            ref.get("n") == 3 and ref.get("workflows") == 2 and ref.get("repos") == 2
            and perm_missing.get("n") == 1 and perm_missing.get("workflows") == 1
            and perm_missing.get("repos") == 1
            and resumen_por_codigo.get("workflows") == 3
        ),
    })

    # El nulo: universo medido y limpio. `por_codigo` no existe fabricando una fila,
    # existe vacio — `{}` junto a `workflows=1` distingue «cero codigos sobre
    # superficie medida» de «nada medido» (ahi `workflows` es 0 y no hay tasa que
    # derivar). Un `por_codigo` derivado de `status` publicaria una fila igual.
    resumen_limpio = _summary([
        {"repository": "solo", **_analyze_files([
            ("a.yml", "permissions:\n  contents: read\njobs: {}\n"),
        ])},
    ])
    rows.append({
        "case": "POR_CODIGO_NULO_ES_VACIO",
        "expected": ["por_codigo={}", "workflows=1", "overall=PASS"],
        "measured": [
            "por_codigo=%s" % resumen_limpio.get("por_codigo"),
            "workflows=%s" % resumen_limpio.get("workflows"),
            "overall=%s" % resumen_limpio.get("overall"),
        ],
        "ok": (
            resumen_limpio.get("por_codigo") == {}
            and resumen_limpio.get("workflows") == 1
            and resumen_limpio.get("overall") == "PASS"
        ),
    })

    empty = _analyze_files([])
    empty_ok = empty["status"] == "NO_MEASUREMENT"
    rows.append({"case": "EMPTY_UNIVERSE_FAILS_CLOSED", "expected": ["NO_MEASUREMENT"],
                 "measured": [empty["status"]], "ok": empty_ok})

    con_write = _analyze_files([(
        "adj.yml",
        "permissions:\n  contents: read\njobs:\n  check:\n    runs-on: ubuntu-latest\n"
        "    permissions:\n      contents: write\n    steps: []\n",
    )])
    adjudicado = {"repository": "adj", **con_write}
    huerfanas = _apply_adjudicadas(
        [adjudicado], [{"code": "SC1_JOB_WRITE_SCOPE_REVIEW", "workflow": "adj.yml", "job": "check"}]
    )
    rows.append({
        "case": "ADJUDICADO_BAJA_A_LEDGER",
        "expected": ["ADJUDICADO", "0 huerfanas"],
        "measured": [adjudicado["status"], "%d huerfanas" % len(huerfanas)],
        "ok": adjudicado["status"] == "ADJUDICADO" and not huerfanas,
    })

    limpio = {"repository": "adj", **_analyze_files([("adj.yml", "permissions:\n  contents: read\njobs: {}\n")])}
    huerfanas = _apply_adjudicadas([limpio], [{"code": "SC1_JOB_WRITE_SCOPE_REVIEW", "workflow": "otro.yml"}])
    rows.append({
        "case": "ADJUDICACION_HUERFANA_SE_ACUSA",
        "expected": ["PASS", "1 huerfanas"],
        "measured": [limpio["status"], "%d huerfanas" % len(huerfanas)],
        "ok": limpio["status"] == "PASS" and len(huerfanas) == 1,
    })

    return rows, all(row["ok"] for row in rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inventario de Supply Chain Security para GitHub Actions.")
    parser.add_argument("--owner", default="alexisromtz-lab", help="owner/org para el inventario por gh")
    parser.add_argument("--root", type=Path, help="audita un checkout local en vez del owner remoto")
    parser.add_argument("--repo", help="audita UN repo ajeno por nombre completo (owner/name), sin clonar")
    parser.add_argument("--include-forks", action="store_true", help="incluye forks en el inventario remoto")
    parser.add_argument("--self-test", action="store_true", help="ejecuta pruebas en memoria, sin red ni escrituras")
    parser.add_argument(
        "--manifiesto",
        action="store_true",
        help="publica la superficie auditada (rutas de workflow leidas), no solo su conteo",
    )
    parser.add_argument(
        "--adjudicadas",
        type=Path,
        help="libro de exclusiones explicitas; baja a ADJUDICADO solo las filas declaradas",
    )
    args = parser.parse_args(argv)

    if gate is None:
        payload = {"status": "UNVERIFIABLE", "error": MOTOR_ERROR, "results": []}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    if args.self_test:
        rows, ok = _self_test()
        print(json.dumps({
            "schema": "platino.supply-chain-audit.v2",
            "status": "PASS" if ok else "FAIL",
            "self_test": rows,
        }, ensure_ascii=False, indent=2))
        return 0 if ok else 1

    if args.repo and args.root:
        print(json.dumps({
            "schema": "platino.supply-chain-audit.v2",
            "status": "UNVERIFIABLE",
            "error": "ARGUMENTOS_INCOMPATIBLES",
            "results": [],
        }, ensure_ascii=False, indent=2))
        return 2

    try:
        if args.root:
            results = [_local_result(args.root, args.manifiesto)]
        elif args.repo:
            results = [_remote_result(args.repo, args.manifiesto)]
        else:
            results = _remote_results(args.owner, args.include_forks, args.manifiesto)
        adjudicadas = {"filas": 0, "huerfanas": []}
        if args.adjudicadas:
            rows = _load_adjudicadas(args.adjudicadas)
            huerfanas = _apply_adjudicadas(results, rows)
            adjudicadas = {"filas": len(rows), "huerfanas": huerfanas}
        summary = _summary(results)
        if adjudicadas["huerfanas"]:
            summary["overall"] = "FINDINGS"
        payload = {
            "schema": "platino.supply-chain-audit.v2",
            "owner": None if (args.root or args.repo) else args.owner,
            "source": "local" if args.root else "github_api_read_only",
            "policy": {
                "SC-1": "permisos raíz explícitos; write heredado bloqueado; write de job requiere revisión",
                "SC-2": "refs remotas fijadas a SHA completo; acciones locales excluidas",
                "SC-3": "pull_request_target/workflow_run + checkout no confiable en contexto privilegiado",
                "SC-3_alcance": (
                    "solo dispara cuando coexisten ref no confiable y contexto privilegiado "
                    "(write scopes o secretos); un pull_request_target sin privilegio no se marca"
                ),
                "frontera": "superficie declarada del YAML; no certifica runtime ni politicas del proveedor",
                "additional_gate_checks": sorted(gate.CAUSAS),
                "blind_spots": list(gate.RESIDUO),
            },
            "summary": summary,
            "adjudicadas": adjudicadas,
            "results": results,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        if summary["overall"] == "PASS":
            return 0
        if summary["overall"] == "ADJUDICADO":
            return 0
        if summary["overall"] == "INCOMPLETE":
            return 2
        return 1
    except AuditError as exc:
        print(json.dumps({
            "schema": "platino.supply-chain-audit.v2",
            "status": "UNVERIFIABLE",
            "error": exc.code,
            "results": [],
        }, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
