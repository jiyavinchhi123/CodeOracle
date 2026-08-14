from collections import Counter

from app.analyzers.base import ParsedFile
from app.models.analysis import (
    DependencyEdge,
    DependencyGraph,
    DependencyGraphStats,
    DependencyNode,
)
from app.utils.security import module_path_from_file


def build_dependency_graph(parsed_files: list[ParsedFile]) -> DependencyGraph:
    """Build import/reference graph from parsed files."""
    paths = [_normalize_path(pf.path) for pf in parsed_files]
    path_set = set(paths)
    labels = _build_disambiguated_labels(paths)
    module_to_file = _build_module_index(parsed_files)

    nodes = [
        DependencyNode(
            id=path,
            path=path,
            label=labels[path],
            language=pf.language,
            kind="module",
        )
        for pf, path in zip(parsed_files, paths)
    ]

    edges: list[DependencyEdge] = []
    seen: set[tuple[str, str, str]] = set()

    for pf, source in zip(parsed_files, paths):
        for imp in pf.imports:
            module = imp.get("module", "")
            if not module:
                continue
            target = _resolve_import(module, pf, module_to_file, parsed_files)
            _add_edge(edges, seen, source, target, "import", path_set)

        if pf.language == "java":
            for cls in pf.classes:
                parent = cls.get("extends")
                if parent:
                    target = _resolve_type(parent, pf, module_to_file, parsed_files)
                    _add_edge(edges, seen, source, target, "inherits", path_set)
                for impl in cls.get("implements") or []:
                    target = _resolve_type(impl, pf, module_to_file, parsed_files)
                    _add_edge(edges, seen, source, target, "implements", path_set)
        else:
            for cls in pf.classes:
                for base in cls.get("bases", []):
                    target = _resolve_type(base, pf, module_to_file, parsed_files)
                    _add_edge(edges, seen, source, target, "inherits", path_set)

    edge_type_counts: dict[str, int] = Counter(e.edge_type for e in edges)
    stats = DependencyGraphStats(
        total_nodes=len(nodes),
        total_edges=len(edges),
        edge_type_counts=dict(sorted(edge_type_counts.items())),
    )
    return DependencyGraph(nodes=nodes, edges=edges, stats=stats)


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def _build_disambiguated_labels(paths: list[str]) -> dict[str, str]:
    basenames = Counter(p.rsplit("/", 1)[-1] for p in paths)
    labels: dict[str, str] = {}
    for path in paths:
        basename = path.rsplit("/", 1)[-1]
        if basenames[basename] == 1:
            labels[path] = basename
            continue
        parts = path.split("/")
        if len(parts) >= 2:
            labels[path] = "/".join(parts[-2:])
        else:
            labels[path] = basename
    return labels


def _build_module_index(parsed_files: list[ParsedFile]) -> dict[str, str]:
    module_to_file: dict[str, str] = {}
    for pf in parsed_files:
        path = _normalize_path(pf.path)
        mod = module_path_from_file(path)
        module_to_file[mod] = path
        if pf.language == "java":
            package = _java_package_from_path(path)
            class_name = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            if package:
                module_to_file[f"{package}.{class_name}"] = path
            module_to_file[class_name] = path
    return module_to_file


def _java_package_from_path(path: str) -> str:
    normalized = _normalize_path(path)
    marker = "/java/"
    idx = normalized.find(marker)
    if idx == -1:
        return ""
    rel = normalized[idx + len(marker) :]
    parts = rel.replace(".java", "").split("/")
    if len(parts) <= 1:
        return ""
    return ".".join(parts[:-1])


def _add_edge(
    edges: list[DependencyEdge],
    seen: set[tuple[str, str, str]],
    source: str,
    target: str | None,
    edge_type: str,
    path_set: set[str],
) -> None:
    if not target or target == source or target not in path_set:
        return
    key = (source, target, edge_type)
    if key in seen:
        return
    seen.add(key)
    edges.append(DependencyEdge(source=source, target=target, edge_type=edge_type))


def _resolve_import(
    module: str,
    source_file: ParsedFile,
    module_to_file: dict[str, str],
    parsed_files: list[ParsedFile],
) -> str | None:
    if module in module_to_file:
        return module_to_file[module]

    if source_file.language == "python":
        source_mod = module_path_from_file(_normalize_path(source_file.path))
        for candidate in _python_candidates(source_mod, module):
            if candidate in module_to_file:
                return module_to_file[candidate]

    if source_file.language == "java":
        simple = module.split(".")[-1]
        if module in module_to_file:
            return module_to_file[module]
        for pf in parsed_files:
            if pf.language != "java":
                continue
            path = _normalize_path(pf.path)
            if path.endswith(f"/{simple}.java") or path.endswith(f"{simple}.java"):
                package = _java_package_from_path(path)
                if module == f"{package}.{simple}" if package else simple:
                    return path

    suffix = module.split(".")[-1]
    matches = [
        path
        for mod, path in module_to_file.items()
        if mod == suffix or mod.endswith(f".{suffix}")
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _python_candidates(source_mod: str, import_mod: str) -> list[str]:
    parts = source_mod.split(".") if source_mod else []
    candidates = [import_mod]
    if parts:
        candidates.append(".".join(parts[:-1] + [import_mod]) if parts[:-1] else import_mod)
        candidates.append(f"{source_mod}.{import_mod}")
    return candidates


def _resolve_type(
    type_name: str,
    source_file: ParsedFile,
    module_to_file: dict[str, str],
    parsed_files: list[ParsedFile],
) -> str | None:
    simple = type_name.split(".")[-1]
    if type_name in module_to_file:
        return module_to_file[type_name]
    if simple in module_to_file:
        matches = [path for mod, path in module_to_file.items() if mod.endswith(f".{simple}") or mod == simple]
        if len(matches) == 1:
            return matches[0]
        if simple in module_to_file:
            return module_to_file[simple]

    same_file_matches = []
    for pf in parsed_files:
        for cls in pf.classes:
            if cls["name"] == simple:
                same_file_matches.append(_normalize_path(pf.path))
    if len(same_file_matches) == 1:
        return same_file_matches[0]

    if source_file.language == "java":
        source_package = _java_package_from_path(_normalize_path(source_file.path))
        if source_package:
            candidate = f"{source_package}.{simple}"
            if candidate in module_to_file:
                return module_to_file[candidate]
    return None
