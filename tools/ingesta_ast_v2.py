#!/usr/bin/env python3
"""Generate a deterministic ingesta_ast/v2 import corpus from a pinned checkout.

The repository HEAD must equal the supplied full commit SHA. ``--source-root`` is
relative to the repository root; use ``--package`` to keep module names stable
across clones. The command reads only Python source files and fails closed if the
checkout, tracked-file set, source bytes, or AST cannot be verified.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

HUELLA = "HUELLA-INGESTA-AST-V2-PRODUCTOR-20261028"
SCHEMA = "ingesta_ast/v2"
IGNORED_DIRS = {"__pycache__"}


class IngestaError(Exception):
    """A source snapshot cannot be ingested without losing evidence."""


def _git(repo_root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        raise IngestaError("no se encontró el ejecutable git") from None
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", "replace").strip()
        raise IngestaError(f"git {args[0]} falló: {detail}") from None
    return result.stdout


def _repo_root(path: Path) -> Path:
    try:
        root = path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise IngestaError(f"repositorio inexistente o ilegible: {exc}") from None
    if not root.is_dir():
        raise IngestaError(f"la ruta del repositorio no es un directorio: {root}")
    git_root = Path(os.fsdecode(_git(root, "rev-parse", "--show-toplevel")).strip())
    if git_root.resolve() != root:
        raise IngestaError(f"la ruta debe ser la raíz del checkout: {git_root}")
    return root


def _validate_commit(repo_root: Path, commit: str) -> str:
    if re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit) is None:
        raise IngestaError("--commit requiere un SHA Git completo de 40 o 64 caracteres")
    actual = os.fsdecode(_git(repo_root, "rev-parse", "--verify", "HEAD")).strip()
    if actual != commit:
        raise IngestaError(f"HEAD no coincide con --commit: HEAD={actual} declarado={commit}")
    return os.fsdecode(_git(repo_root, "rev-parse", "--show-object-format")).strip()


def _source_root(repo_root: Path, argument: str) -> tuple[Path, str]:
    relative = PurePosixPath(argument)
    if relative.is_absolute() or ".." in relative.parts:
        raise IngestaError("--source-root debe ser una ruta relativa dentro del repositorio")

    candidate = repo_root.joinpath(*relative.parts)
    cursor = repo_root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise IngestaError(f"--source-root no puede atravesar un enlace simbólico: {argument}")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise IngestaError(f"raíz de fuentes inexistente o ilegible ({argument}): {exc}") from None
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        raise IngestaError("--source-root queda fuera del checkout") from None
    if not resolved.is_dir():
        raise IngestaError(f"--source-root no es un directorio: {argument}")
    rel = resolved.relative_to(repo_root).as_posix() or "."
    return resolved, rel


def _eligible_python_path(relative: str) -> bool:
    path = PurePosixPath(relative)
    return path.suffix == ".py" and not any(
        part.startswith(".") or part in IGNORED_DIRS for part in path.parts[:-1]
    )


def _tracked_python_files(
    repo_root: Path, commit: str, source_root_rel: str
) -> tuple[dict[str, tuple[str, str]], str]:
    object_format = os.fsdecode(_git(repo_root, "rev-parse", "--show-object-format")).strip()
    if object_format not in {"sha1", "sha256"}:
        raise IngestaError(f"formato de objetos Git no soportado: {object_format}")

    args = ["ls-tree", "-r", "-z", "--full-tree", commit]
    if source_root_rel != ".":
        args.extend(["--", source_root_rel])
    raw_tree = _git(repo_root, *args)
    result: dict[str, tuple[str, str]] = {}
    prefix = f"{source_root_rel}/" if source_root_rel != "." else ""

    for entry in raw_tree.split(b"\0"):
        if not entry:
            continue
        try:
            metadata, path_bytes = entry.split(b"\t", 1)
            mode, kind, oid = metadata.decode("ascii").split()
            path_from_repo = path_bytes.decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            raise IngestaError("git ls-tree devolvió una entrada no interpretable") from None
        if prefix:
            if not path_from_repo.startswith(prefix):
                continue
            relative = path_from_repo[len(prefix):]
        else:
            relative = path_from_repo
        if not _eligible_python_path(relative):
            continue
        if kind != "blob" or mode == "120000":
            raise IngestaError(f"fuente Python no regular en el commit: {relative}")
        result[relative] = (mode, oid)
    return result, object_format


def _worktree_python_files(source_root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}

    def fail_walk(error: OSError) -> None:
        name = error.filename or source_root
        raise IngestaError(
            f"{type(error).__name__} al recorrer fuentes Python {name}: {error}"
        ) from None

    try:
        for current, directories, filenames in os.walk(
            source_root, topdown=True, followlinks=False, onerror=fail_walk
        ):
            directories[:] = sorted(
                name for name in directories
                if not name.startswith(".") and name not in IGNORED_DIRS
            )
            for filename in sorted(filenames):
                if filename.endswith(".py"):
                    path = Path(current, filename)
                    relative = path.relative_to(source_root).as_posix()
                    result[relative] = path
    except OSError as exc:
        raise IngestaError(
            f"{type(exc).__name__} al recorrer fuentes Python: {exc}"
        ) from None
    return result


def _git_blob_oid(data: bytes, object_format: str) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.new(object_format, header + data).hexdigest()


def _read_source(
    path: Path, relative: str, expected_oid: str, object_format: str
) -> bytes:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise IngestaError(
            f"{type(exc).__name__} al leer fuente Python {relative}: {exc}"
        ) from None
    actual_oid = _git_blob_oid(data, object_format)
    if actual_oid != expected_oid:
        raise IngestaError(
            f"hash de fuente divergente respecto al commit para {relative}: "
            f"esperado={expected_oid} obtenido={actual_oid}"
        )
    return data


def _catches_import_error(handler: ast.ExceptHandler) -> bool:
    def matches(node: ast.expr | None) -> bool:
        if isinstance(node, ast.Name):
            return node.id in {"ImportError", "ModuleNotFoundError"}
        if isinstance(node, ast.Tuple):
            return any(matches(item) for item in node.elts)
        return False

    return matches(handler.type)


class _ImportCollector(ast.NodeVisitor):
    def __init__(self, relative: str) -> None:
        self.relative = relative
        self.records: list[dict[str, Any]] = []
        self.modalities: list[str] = []
        self.scope_depth = 0
        self.type_checking_names = {"TYPE_CHECKING"}
        self.typing_modules = {"typing", "typing_extensions"}

    def _modality(self) -> str:
        if "type_checking" in self.modalities:
            return "type_checking"
        if "except_import" in self.modalities:
            return "except_import"
        return "required"

    def _add(self, module: str, name: str | None) -> None:
        self.records.append({
            "rel": self.relative,
            "modalidad": self._modality(),
            "modulo": module,
            "nombre": name,
        })

    def _visit_with(self, node: ast.AST, modality: str | None) -> None:
        if modality is None:
            self.visit(node)
            return
        self.modalities.append(modality)
        try:
            self.visit(node)
        finally:
            self.modalities.pop()

    def _is_type_checking(self, node: ast.expr) -> bool:
        if isinstance(node, ast.Name):
            return node.id in self.type_checking_names
        return (
            isinstance(node, ast.Attribute)
            and node.attr == "TYPE_CHECKING"
            and isinstance(node.value, ast.Name)
            and node.value.id in self.typing_modules
        )

    def visit_If(self, node: ast.If) -> None:
        test = node.test
        type_branch = "body"
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            is_type_checking = self._is_type_checking(test.operand)
            type_branch = "orelse"
        else:
            is_type_checking = self._is_type_checking(test)
        if not is_type_checking:
            self.generic_visit(node)
            return
        for statement in node.body:
            self._visit_with(statement, "type_checking" if type_branch == "body" else None)
        for statement in node.orelse:
            self._visit_with(statement, "type_checking" if type_branch == "orelse" else None)

    def visit_Try(self, node: ast.Try) -> None:
        optional = any(_catches_import_error(handler) for handler in node.handlers)
        for statement in node.body:
            self._visit_with(statement, "except_import" if optional else None)
        for handler in node.handlers:
            self.visit(handler)
        for statement in node.orelse:
            self.visit(statement)
        for statement in node.finalbody:
            self.visit(statement)

    def visit_TryStar(self, node: ast.AST) -> None:
        optional = any(_catches_import_error(handler) for handler in node.handlers)
        for statement in node.body:
            self._visit_with(statement, "except_import" if optional else None)
        for handler in node.handlers:
            self.visit(handler)
        for statement in node.orelse:
            self.visit(statement)
        for statement in node.finalbody:
            self.visit(statement)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._add(alias.name, None)
            if self.scope_depth == 0 and alias.name in self.typing_modules and alias.asname:
                self.typing_modules.add(alias.asname)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        for alias in node.names:
            self._add(module, alias.name)
            if (
                self.scope_depth == 0
                and node.level == 0
                and node.module in self.typing_modules
                and alias.name == "TYPE_CHECKING"
                and alias.asname
            ):
                self.type_checking_names.add(alias.asname)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope_depth += 1
        try:
            self.generic_visit(node)
        finally:
            self.scope_depth -= 1

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.scope_depth += 1
        try:
            self.generic_visit(node)
        finally:
            self.scope_depth -= 1

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope_depth += 1
        try:
            self.generic_visit(node)
        finally:
            self.scope_depth -= 1


def _imports_for_source(raw: bytes, relative: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(raw, filename=relative, type_comments=True)
    except (SyntaxError, UnicodeError) as exc:
        location = f"{relative}:{exc.lineno}" if isinstance(exc, SyntaxError) else relative
        raise IngestaError(f"AST inválido en {location}: {exc}") from None
    collector = _ImportCollector(relative)
    collector.visit(tree)
    return collector.records


def ingest(
    repository: Path,
    commit: str,
    *,
    source_root: str = ".",
    package: str | None = None,
) -> dict[str, Any]:
    repo_root = _repo_root(repository)
    object_format = _validate_commit(repo_root, commit)
    source_path, source_root_rel = _source_root(repo_root, source_root)
    package_name = package or (Path(source_root_rel).name if source_root_rel != "." else repo_root.name)
    if not package_name or not all(part.isidentifier() for part in package_name.split(".")):
        raise IngestaError(f"nombre de paquete Python no válido: {package_name!r}")

    tracked, object_format = _tracked_python_files(repo_root, commit, source_root_rel)
    actual = _worktree_python_files(source_path)
    missing = sorted(set(tracked) - set(actual))
    extra = sorted(set(actual) - set(tracked))
    if missing or extra:
        raise IngestaError(
            "universo de archivos Python difiere del commit: "
            f"faltan={missing[:5]} sobran={extra[:5]}"
        )
    if not tracked:
        raise IngestaError(f"no hay archivos Python elegibles bajo {source_root_rel}")

    archive_records: list[dict[str, str]] = []
    imports: list[dict[str, Any]] = []
    for relative in sorted(tracked):
        _, expected_oid = tracked[relative]
        raw = _read_source(actual[relative], relative, expected_oid, object_format)
        archive_records.append({
            "rel": relative,
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
        imports.extend(_imports_for_source(raw, relative))

    imports.sort(key=lambda record: (
        record["rel"], record["modulo"], record["nombre"] or "", record["modalidad"]
    ))
    return {
        "esquema": SCHEMA,
        "huella": HUELLA,
        "paquete": package_name,
        "raiz": source_root_rel,
        "source": {"commit": commit},
        "n_ilegibles": 0,
        "archivos": archive_records,
        "imports": imports,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Produce un corpus determinista ingesta_ast/v2 desde un checkout fijado."
    )
    parser.add_argument("repository", type=Path, help="raíz del repositorio local")
    parser.add_argument("commit", help="SHA Git completo que debe coincidir con HEAD")
    parser.add_argument(
        "--source-root", default=".",
        help="raíz del paquete relativa al repositorio (default: .)",
    )
    parser.add_argument(
        "--package", help="nombre de módulo estable; default: nombre de --source-root"
    )
    parser.add_argument(
        "--output", default="-",
        help="destino JSON; '-' escribe a stdout (default: -)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        corpus = ingest(
            args.repository,
            args.commit,
            source_root=args.source_root,
            package=args.package,
        )
        serialized = json.dumps(
            corpus, ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n"
        if args.output == "-":
            sys.stdout.write(serialized)
        else:
            Path(args.output).write_text(serialized, encoding="utf-8", newline="\n")
    except (IngestaError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
