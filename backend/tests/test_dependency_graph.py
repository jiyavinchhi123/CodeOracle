"""Tests for dependency graph building."""

from app.analyzers.base import ParsedFile
from app.analyzers.dependency_graph import build_dependency_graph
from app.models.analysis import DependencyGraph


def _pf(path: str, *, language: str = "python", imports=None, classes=None) -> ParsedFile:
    return ParsedFile(
        path=path,
        language=language,
        line_count=10,
        size_bytes=100,
        content="",
        imports=imports or [],
        classes=classes or [],
        functions=[],
    )


def test_unique_node_ids_and_disambiguated_labels():
    files = [
        _pf("ai-service/main.py"),
        _pf("backend/main.py"),
        _pf("src/main/java/com/example/Customer.java", language="java"),
        _pf(
            "src/main/java/com/example/repository/CustomerRepository.java",
            language="java",
            classes=[{"name": "CustomerRepository", "extends": "BaseRepository", "implements": ["CrudRepo"], "bases": []}],
        ),
    ]
    graph = build_dependency_graph(files)
    ids = [n.id for n in graph.nodes]
    labels = [n.label for n in graph.nodes]

    assert len(ids) == len(set(ids))
    assert "ai-service/main.py" in ids
    assert "backend/main.py" in ids
    assert labels.count("main.py") == 0
    assert "ai-service/main.py" in labels
    assert "backend/main.py" in labels


def test_import_and_inheritance_edges_with_stats():
    files = [
        _pf(
            "app/service.py",
            imports=[{"module": "app.model", "names": ["User"]}],
            classes=[{"name": "UserService", "bases": ["BaseService"], "extends": None, "implements": []}],
        ),
        _pf("app/model.py"),
        _pf("app/base.py", classes=[{"name": "BaseService", "bases": [], "extends": None, "implements": []}]),
    ]
    graph = build_dependency_graph(files)

    assert graph.stats.total_nodes == 3
    assert graph.stats.total_edges >= 1
    assert graph.stats.edge_type_counts.get("import", 0) >= 1

    for edge in graph.edges:
        assert edge.source in {n.id for n in graph.nodes}
        assert edge.target in {n.id for n in graph.nodes}
        assert edge.source != edge.target


def test_legacy_string_nodes_coerced():
    legacy = {
        "nodes": ["ai-service/main.py", "backend/main.py"],
        "edges": [{"source": "ai-service/main.py", "target": "backend/main.py", "edge_type": "import"}],
    }
    graph = DependencyGraph.model_validate(legacy)
    assert len(graph.nodes) == 2
    assert graph.nodes[0].id == "ai-service/main.py"
    assert graph.nodes[0].label == "ai-service/main.py"
    assert graph.stats.total_nodes == 2
    assert graph.stats.total_edges == 1


def test_java_implements_edge_type():
    files = [
        _pf(
            "src/main/java/com/example/App.java",
            language="java",
            classes=[
                {
                    "name": "App",
                    "bases": ["Runnable"],
                    "extends": None,
                    "implements": ["Runnable"],
                }
            ],
        ),
        _pf(
            "src/main/java/com/example/Runnable.java",
            language="java",
            classes=[{"name": "Runnable", "bases": [], "extends": None, "implements": []}],
        ),
    ]
    graph = build_dependency_graph(files)
    types = {e.edge_type for e in graph.edges}
    assert "implements" in types or "inherits" in types
