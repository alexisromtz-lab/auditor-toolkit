#!/usr/bin/env python3
"""Calcula componentes cíclicos de imports y LOC desde ingesta_ast/v2.

LOC cuenta líneas físicas con tokens Python distintos de comentarios y espacios;
la ingesta y el checkout se vinculan por SHA-256 de cada archivo y por commit Git.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tokenize
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = "ARCH_INDEX_TARJAN_CONDENSACION_20261028"
IGNORED_MODALITIES = {"type_checking"}
LOC_METHOD = "physical source lines containing Python tokens (comments/blank excluded)"


def _module_for_rel(package: str, rel: str) -> str:
    path = PurePosixPath(rel)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".py":
        raise ValueError(f"ruta Python inválida en corpus: {rel!r}")
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    suffix = ".".join(parts)
    return f"{package}.{suffix}" if suffix else package


def _python_files(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for current, directories, filenames in os.walk(root):
        directories[:] = sorted(
            name for name in directories
            if not name.startswith(".") and name != "__pycache__"
        )
        for filename in sorted(filenames):
            if filename.endswith(".py"):
                path = Path(current, filename)
                result[path.relative_to(root).as_posix()] = path
    return result


def _loc_count(text: str) -> int:
    ignored = {
        tokenize.COMMENT,
        tokenize.DEDENT,
        tokenize.ENCODING,
        tokenize.ENDMARKER,
        tokenize.INDENT,
        tokenize.NEWLINE,
        tokenize.NL,
    }
    physical_lines = text.splitlines()
    code_lines: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type in ignored or not token.string.strip():
            continue
        first, last = token.start[0], token.end[0]
        for line_number in range(first, last + 1):
            if 1 <= line_number <= len(physical_lines) and physical_lines[line_number - 1].strip():
                code_lines.add(line_number)
    return len(code_lines)


def _source_package(module: str, rel: str) -> str:
    if PurePosixPath(rel).name == "__init__.py":
        return module
    parent, separator, _ = module.rpartition(".")
    return parent if separator else module


def _resolve_import_base(raw_module: str, source_package: str) -> str:
    leading_dots = len(raw_module) - len(raw_module.lstrip("."))
    suffix = raw_module[leading_dots:]
    if not leading_dots:
        return raw_module
    package_parts = source_package.split(".") if source_package else []
    if leading_dots > len(package_parts):
        return ""
    base_parts = package_parts[: len(package_parts) - leading_dots + 1]
    if suffix:
        base_parts.extend(suffix.split("."))
    return ".".join(base_parts)


def _target_modules(
    record: dict[str, Any],
    source_package: str,
    package: str,
    modules: dict[str, str],
) -> tuple[list[str], str]:
    raw_module = record.get("modulo")
    if not isinstance(raw_module, str):
        raise ValueError("import sin campo modulo de tipo string")
    base = _resolve_import_base(raw_module, source_package)
    if not base:
        return [], "invalid_relative"
    if base != package and not base.startswith(package + "."):
        return [], "external"

    imported_name = record.get("nombre")
    candidates: list[str] = []
    if isinstance(imported_name, str) and imported_name != "*":
        child = f"{base}.{imported_name}"
        if child in modules:
            candidates.append(child)
    if base in modules and base not in candidates:
        candidates.append(base)
    return candidates, "internal" if candidates else "unresolved_internal"


def _expand_package_initializers(
    target: str,
    package: str,
    modules: dict[str, str],
    initializers: set[str],
) -> set[str]:
    parts = target.split(".")
    root_depth = len(package.split("."))
    expanded = {target}
    for depth in range(root_depth, len(parts)):
        parent = ".".join(parts[:depth])
        if parent in initializers:
            expanded.add(parent)
    return {module for module in expanded if module in modules}


def _build_import_graph(
    package: str,
    archive_records: list[dict[str, Any]],
    imports: list[dict[str, Any]],
    *,
    expand_initializers: bool = True,
) -> tuple[dict[str, set[str]], dict[str, str], dict[str, Any]]:
    modules: dict[str, str] = {}
    module_by_rel: dict[str, str] = {}
    initializers: set[str] = set()
    for record in archive_records:
        if not isinstance(record, dict) or not isinstance(record.get("rel"), str):
            raise ValueError("registro de archivo inválido en el corpus")
        rel = record["rel"]
        module = _module_for_rel(package, rel)
        if module in modules:
            raise ValueError(f"colisión de módulo Python {module}: {modules[module]} y {rel}")
        modules[module] = rel
        module_by_rel[rel] = module
        if PurePosixPath(rel).name == "__init__.py":
            initializers.add(module)

    graph = {module: set() for module in modules}
    modality_counts: dict[str, int] = {}
    type_checking_excluded = 0
    external_imports = 0
    unresolved_internal_imports = 0
    invalid_relative_imports = 0
    resolved_import_records = 0

    for record in imports:
        if not isinstance(record, dict) or record.get("rel") not in module_by_rel:
            raise ValueError("arista de import sin archivo fuente en el corpus")
        modality = record.get("modalidad")
        if not isinstance(modality, str):
            raise ValueError("arista de import sin modalidad declarada")
        modality_counts[modality] = modality_counts.get(modality, 0) + 1
        if modality in IGNORED_MODALITIES:
            type_checking_excluded += 1
            continue

        rel = record["rel"]
        source_module = module_by_rel[rel]
        source_package = _source_package(source_module, rel)
        targets, classification = _target_modules(record, source_package, package, modules)
        if classification == "external":
            external_imports += 1
            continue
        if classification == "invalid_relative":
            invalid_relative_imports += 1
            continue
        if classification == "unresolved_internal":
            unresolved_internal_imports += 1
            continue

        target_set: set[str] = set()
        for target in targets:
            if expand_initializers:
                target_set.update(
                    _expand_package_initializers(target, package, modules, initializers)
                )
            else:
                target_set.add(target)
        for target_module in target_set:
            if target_module == source_module and record.get("nombre") is not None:
                continue
            graph[source_module].add(target_module)
            resolved_import_records += 1

    return graph, modules, {
        "initializer_count": len(initializers),
        "import_modalities": dict(sorted(modality_counts.items())),
        "type_checking_imports_excluded": type_checking_excluded,
        "external_import_records": external_imports,
        "unresolved_internal_import_records": unresolved_internal_imports,
        "invalid_relative_import_records": invalid_relative_imports,
        "resolved_import_records": resolved_import_records,
    }


def strongly_connected_components(graph: dict[str, set[str]]) -> list[list[str]]:
    """Iterative Tarjan, avoiding recursion limits on large package graphs."""
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    active: list[str] = []
    on_active: set[str] = set()
    components: list[list[str]] = []

    for root in sorted(graph):
        if root in indices:
            continue
        indices[root] = lowlinks[root] = index
        index += 1
        active.append(root)
        on_active.add(root)
        frames: list[tuple[str, Any, str | None]] = [
            (root, iter(sorted(graph[root])), None)
        ]

        while frames:
            node, children, parent = frames[-1]
            try:
                child = next(children)
            except StopIteration:
                frames.pop()
                if parent is not None:
                    lowlinks[parent] = min(lowlinks[parent], lowlinks[node])
                if lowlinks[node] == indices[node]:
                    component: list[str] = []
                    while True:
                        member = active.pop()
                        on_active.remove(member)
                        component.append(member)
                        if member == node:
                            break
                    components.append(sorted(component))
                continue

            if child not in graph:
                raise ValueError(f"arista a módulo fuera del grafo: {child}")
            if child not in indices:
                indices[child] = lowlinks[child] = index
                index += 1
                active.append(child)
                on_active.add(child)
                frames.append((child, iter(sorted(graph[child])), node))
            elif child in on_active:
                lowlinks[node] = min(lowlinks[node], indices[child])

    return sorted(components)


def _cyclic_components(graph: dict[str, set[str]]) -> list[list[str]]:
    return [
        component for component in strongly_connected_components(graph)
        if len(component) > 1 or component[0] in graph[component[0]]
    ]


def _topological_order(dag: dict[int, set[int]]) -> list[int]:
    """Kahn determinista; una arista de vuelta significa que no hubo condensación."""
    indegree = {node: 0 for node in dag}
    for targets in dag.values():
        for target in targets:
            if target not in indegree:
                raise ValueError(f"arista a componente fuera del DAG: {target}")
            indegree[target] += 1
    ready = sorted(node for node, degree in indegree.items() if degree == 0)
    order: list[int] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for target in sorted(dag[node]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
        ready.sort()
    if len(order) != len(dag):
        raise ValueError("el grafo condensado no es acíclico; SCC incompatible")
    return order


def _longest_path_depths(dag: dict[int, set[int]], order: list[int]) -> dict[int, int]:
    depths = {node: 0 for node in dag}
    for node in order:
        for target in dag[node]:
            depths[target] = max(depths[target], depths[node] + 1)
    return depths


def _components_reaching(dag: dict[int, set[int]], seeds: list[int]) -> set[int]:
    """Componentes que alcanzan alguna semilla: dependen transitivamente de ella."""
    reverse: dict[int, set[int]] = {node: set() for node in dag}
    for source, targets in dag.items():
        for target in targets:
            reverse[target].add(source)
    seen = set(seeds)
    pending = list(seeds)
    while pending:
        node = pending.pop()
        for predecessor in reverse[node]:
            if predecessor not in seen:
                seen.add(predecessor)
                pending.append(predecessor)
    return seen


def condense_graph(graph: dict[str, set[str]]) -> dict[str, Any]:
    """DAG de condensación: Tarjan + orden topológico, con las aristas internas colapsadas."""
    components = strongly_connected_components(graph)
    component_of: dict[str, int] = {}
    for cid, component in enumerate(components):
        for module in component:
            component_of[module] = cid
    dag: dict[int, set[int]] = {cid: set() for cid in range(len(components))}
    for source, targets in graph.items():
        if source not in component_of:
            raise ValueError(f"módulo fuera del grafo: {source}")
        for target in targets:
            if target not in component_of:
                raise ValueError(f"arista a módulo fuera del grafo: {target}")
            src_cid, dst_cid = component_of[source], component_of[target]
            if src_cid != dst_cid:
                dag[src_cid].add(dst_cid)
    order = _topological_order(dag)
    cyclic_ids = [
        cid for cid, component in enumerate(components)
        if len(component) > 1 or component[0] in graph[component[0]]
    ]
    exposed = _components_reaching(dag, cyclic_ids) - set(cyclic_ids)
    depths = _longest_path_depths(dag, order)
    largest = components[0] if components else []
    for component in components:
        if len(component) > len(largest):
            largest = component
    return {
        "components": components,
        "cyclic_components": [components[cid] for cid in cyclic_ids],
        "cyclic_component_ids": cyclic_ids,
        "dag": dag,
        "topological_order": order,
        "is_acyclic": True,
        "edge_count": sum(len(targets) for targets in dag.values()),
        "depth": max(depths.values()) if depths else 0,
        "largest_scc": largest,
        "exposed_component_ids": sorted(exposed),
        "exposed_module_count": sum(len(components[cid]) for cid in exposed),
    }


def _graph_summary(graph: dict[str, set[str]]) -> dict[str, Any]:
    cyclic = _cyclic_components(graph)
    sizes = sorted((len(component) for component in cyclic), reverse=True)
    condensation = condense_graph(graph)
    largest_scc = condensation["largest_scc"]
    return {
        "node_count": len(graph),
        "unique_internal_edges": sum(len(targets) for targets in graph.values()),
        "cyclic_scc_count": len(cyclic),
        "cyclic_component_sizes_descending": sizes,
        "largest_cyclic_scc_size": sizes[0] if sizes else 0,
        "condensation_node_count": len(condensation["dag"]),
        "condensation_edge_count": condensation["edge_count"],
        "condensation_depth": condensation["depth"],
        "largest_scc_size": len(largest_scc),
        "largest_scc_modules": list(largest_scc),
        "exposed_to_cycle_component_count": len(condensation["exposed_component_ids"]),
        "exposed_to_cycle_module_count": condensation["exposed_module_count"],
    }


def analyze_graph_sensitivity(
    corpus: dict[str, Any], corpus_bytes: bytes
) -> dict[str, Any]:
    if corpus.get("esquema") != "ingesta_ast/v2":
        raise ValueError(f"esquema AST no compatible: {corpus.get('esquema')!r}")
    projection = corpus.get("projection")
    if not isinstance(projection, dict) or projection.get("version") != "graph-input/1":
        raise ValueError("la sensibilidad exige una proyección graph-input/1")
    package = corpus.get("paquete")
    if not isinstance(package, str) or not package or not all(
        part.isidentifier() for part in package.split(".")
    ):
        raise ValueError(f"paquete no válido: {package!r}")
    archive_records = corpus.get("archivos")
    imports = corpus.get("imports")
    if not isinstance(archive_records, list) or not archive_records:
        raise ValueError("la proyección debe declarar archivos como lista no vacía")
    if not isinstance(imports, list):
        raise ValueError("la proyección debe declarar imports como lista")
    if corpus.get("n_ilegibles", 0) != 0:
        raise ValueError(f"el ingestor dejó archivos Python ilegibles: {corpus.get('n_ilegibles')}")

    baseline_graph, modules, graph_stats = _build_import_graph(
        package, archive_records, imports
    )
    ablated_graph, ablated_modules, ablated_stats = _build_import_graph(
        package, archive_records, imports, expand_initializers=False
    )
    if modules != ablated_modules or graph_stats["initializer_count"] != ablated_stats["initializer_count"]:
        raise ValueError("el universo de módulos cambió entre grafos")
    baseline = _graph_summary(baseline_graph)
    without_expansion = _graph_summary(ablated_graph)
    return {
        "schema_version": "ARCH_GRAPH_SENSITIVITY_20261028",
        "huella": "HUELLA-ARCH-GRAPH-SENSITIVITY-20261028",
        "graph_input_version": projection["version"],
        "graph_input_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
        "package": package,
        "source_bytes_verified": False,
        "initializer_count": graph_stats["initializer_count"],
        "import_record_count": len(imports),
        "type_checking_imports_excluded": graph_stats["type_checking_imports_excluded"],
        "method": (
            "Compare the declared graph with a graph that retains direct resolved import targets "
            "but omits only ancestor __init__.py expansion; type_checking imports are excluded "
            "from both graphs."
        ),
        "baseline": baseline,
        "without_initializer_expansion": without_expansion,
        "cyclic_scc_delta_without_expansion": (
            without_expansion["cyclic_scc_count"] - baseline["cyclic_scc_count"]
        ),
    }


def _load_input(path: str) -> tuple[dict[str, Any], bytes]:
    raw = sys.stdin.buffer.read() if path == "-" else Path(path).read_bytes()
    corpus = json.loads(raw)
    if not isinstance(corpus, dict):
        raise ValueError("el JSON raíz debe ser un objeto")
    return corpus, raw


def _git_head(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def analyze(
    corpus: dict[str, Any],
    corpus_bytes: bytes,
    repo: str,
    repo_root: Path,
    expected_commit: str,
    source_root_arg: Path | None = None,
) -> dict[str, Any]:
    if corpus.get("esquema") != "ingesta_ast/v2":
        raise ValueError(f"esquema AST no compatible: {corpus.get('esquema')!r}")
    package = corpus.get("paquete")
    if not isinstance(package, str) or not package or not all(
        part.isidentifier() for part in package.split(".")
    ):
        raise ValueError(f"paquete no válido: {package!r}")
    if not expected_commit or _git_head(repo_root) != expected_commit:
        raise ValueError("HEAD del checkout no coincide con --commit")

    source_root = (source_root_arg or Path(str(corpus.get("raiz", "")))).resolve()
    if not source_root.is_dir():
        raise ValueError(f"raíz de fuentes inexistente: {source_root}")
    archive_records = corpus.get("archivos")
    imports = corpus.get("imports")
    if not isinstance(archive_records, list) or not isinstance(imports, list):
        raise ValueError("el corpus debe declarar archivos e imports como listas")
    if corpus.get("n_ilegibles", 0) != 0:
        raise ValueError(f"el ingestor dejó archivos Python ilegibles: {corpus.get('n_ilegibles')}")
    loci = {record.get("locus") for record in archive_records if isinstance(record, dict)}
    if len(loci) > 1:
        raise ValueError("el índice exige una sola raíz/locus por corrida")

    actual_files = _python_files(source_root)
    declared: dict[str, dict[str, Any]] = {}
    for record in archive_records:
        if not isinstance(record, dict) or not isinstance(record.get("rel"), str):
            raise ValueError("registro de archivo inválido en el corpus")
        rel = record["rel"]
        if rel in declared:
            raise ValueError(f"archivo duplicado en corpus: {rel}")
        declared[rel] = record
    missing = sorted(set(declared) - set(actual_files))
    extra = sorted(set(actual_files) - set(declared))
    if missing or extra:
        raise ValueError(f"universo de fuentes desfasado; faltan={missing[:5]}, sobran={extra[:5]}")

    loc = 0
    source_bytes = 0
    source_hashes: dict[str, str] = {}
    for rel in sorted(declared):
        raw = actual_files[rel].read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != declared[rel].get("sha256"):
            raise ValueError(f"SHA-256 de fuente no coincide con ingesta: {rel}")
        source_hashes[rel] = digest
        source_bytes += len(raw)
        loc += _loc_count(raw.decode("utf-8", "replace"))
    if loc == 0:
        raise ValueError("LOC es cero; índice no definido")

    graph, modules, graph_stats = _build_import_graph(
        package, list(declared.values()), imports
    )
    condensation = condense_graph(graph)
    components = condensation["components"]
    cyclic = condensation["cyclic_components"]
    largest_scc = condensation["largest_scc"]
    unique_edges = sum(len(targets) for targets in graph.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "repo": repo,
        "commit": expected_commit,
        "package": package,
        "source_root": str(source_root),
        "corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
        "ingestor_schema": corpus["esquema"],
        "ingestor_huella": corpus.get("huella"),
        "source_file_count": len(declared),
        "module_count": len(modules),
        "module_count_method": "unique Python modules derived from declared source files",
        "source_bytes": source_bytes,
        "source_bytes_method": "sum of exact bytes of eligible Python source files",
        "source_files_sha256": source_hashes,
        "physical_lines_lf": sum(actual_files[rel].read_bytes().count(b"\n") for rel in declared),
        "physical_lines_splitlines": sum(
            len(actual_files[rel].read_bytes().decode("utf-8", "replace").splitlines())
            for rel in declared
        ),
        "loc": loc,
        "loc_method": LOC_METHOD,
        "import_records": len(imports),
        "import_modalities": graph_stats["import_modalities"],
        "type_checking_imports_excluded": graph_stats["type_checking_imports_excluded"],
        "external_import_records": graph_stats["external_import_records"],
        "unresolved_internal_import_records": graph_stats["unresolved_internal_import_records"],
        "invalid_relative_import_records": graph_stats["invalid_relative_import_records"],
        "resolved_import_records": graph_stats["resolved_import_records"],
        "unique_internal_edges": unique_edges,
        "all_scc_count": len(components),
        "cyclic_scc_count": len(cyclic),
        "index_per_10000_loc": cyclic.__len__() * 10000 / loc,
        "formula": "cyclic_scc_count / (loc / 10000)",
        "cyclic_components": [
            {"size": len(component), "modules": component}
            for component in cyclic
        ],
        "scc_definition": "component size > 1 or a self-loop",
        "condensation_node_count": len(condensation["dag"]),
        "condensation_edge_count": condensation["edge_count"],
        "condensation_is_acyclic": condensation["is_acyclic"],
        "condensation_depth": condensation["depth"],
        "condensation_method": "Tarjan SCC iterativo + orden topologico de Kahn; aristas internas colapsadas",
        "largest_scc_size": len(largest_scc),
        "largest_scc_modules": list(largest_scc),
        "largest_scc_share": len(largest_scc) / len(graph) if graph else 0.0,
        "exposed_to_cycle_component_count": len(condensation["exposed_component_ids"]),
        "exposed_to_cycle_module_count": condensation["exposed_module_count"],
        "exposure_definition": "componentes que alcanzan un SCC ciclico via DAG de condensacion",
        "runtime_scope": "required, runtime_data, and except_import; type_checking excluded",
    }


def _self_test() -> None:
    graph = {
        "a": {"b"},
        "b": {"a", "c"},
        "c": {"c"},
        "d": set(),
        "e": {"a"},
    }
    expected = [["a", "b"], ["c"], ["d"], ["e"]]
    actual = strongly_connected_components(graph)
    if actual != expected:
        raise AssertionError(f"Tarjan self-test: expected {expected}, received {actual}")
    condensation = condense_graph(graph)
    if condensation["is_acyclic"] is not True:
        raise AssertionError("condensacion self-test: el DAG declaro ciclo")
    if condensation["edge_count"] != 2:
        raise AssertionError(
            f"condensacion self-test: aristas esperadas 2, recibidas {condensation['edge_count']}"
        )
    if sorted(condensation["topological_order"]) != [0, 1, 2, 3]:
        raise AssertionError("condensacion self-test: orden topologico incompleto")
    if condensation["largest_scc"] != ["a", "b"]:
        raise AssertionError(
            f"condensacion self-test: SCC maximo esperado ['a', 'b'], recibido {condensation['largest_scc']}"
        )
    if condensation["exposed_module_count"] != 1:
        raise AssertionError(
            f"condensacion self-test: expuestos esperados 1, recibidos {condensation['exposed_module_count']}"
        )
    print("SELF-TEST OK: 4 SCC, 2 cyclic SCC")
    print("SELF-TEST CONDENSACION OK: DAG aciclico, 2 aristas, SCC maximo 2, 1 modulo expuesto")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus_json", nargs="?", help="JSON de ingesta_ast/v2 o '-' para stdin")
    parser.add_argument("--repo", help="slug del repositorio medido")
    parser.add_argument("--repo-root", type=Path, help="checkout Git cuya HEAD se ratifica")
    parser.add_argument("--commit", help="SHA completo esperado en HEAD")
    parser.add_argument("--source-root", type=Path, help="raíz ingerida; por defecto usa corpus.raiz")
    parser.add_argument("--graph-sensitivity", action="store_true", help="compara la proyección con y sin expansión de inicializadores")
    parser.add_argument("--self-test", action="store_true", help="ejecuta el control mínimo de Tarjan")
    args = parser.parse_args(argv)
    if args.self_test:
        _self_test()
        return 0
    if args.graph_sensitivity and not args.corpus_json:
        parser.error("graph-sensitivity requiere una proyección graph-input/1")

    try:
        corpus, raw = _load_input(args.corpus_json) if args.corpus_json else ({}, b"")
        if args.graph_sensitivity:
            result = analyze_graph_sensitivity(corpus, raw)
        else:
            if not args.repo or not args.repo_root or not args.commit:
                parser.error("se requieren corpus_json, --repo, --repo-root y --commit")
            result = analyze(
                corpus,
                raw,
                args.repo,
                args.repo_root.resolve(),
                args.commit,
                args.source_root,
            )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError,
            subprocess.CalledProcessError, tokenize.TokenError, IndentationError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
