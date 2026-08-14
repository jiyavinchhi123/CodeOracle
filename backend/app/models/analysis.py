from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    INGESTING = "ingesting"
    ANALYZING = "analyzing"
    AI_PROCESSING = "ai_processing"
    COMPLETED = "completed"
    FAILED = "failed"


class LanguageStats(BaseModel):
    language: str
    file_count: int
    line_count: int


class FileInfo(BaseModel):
    path: str
    language: str
    line_count: int
    size_bytes: int


class FunctionInfo(BaseModel):
    name: str
    line_start: int
    line_end: int
    docstring: Optional[str] = None
    parameters: list[str] = Field(default_factory=list)


class ClassInfo(BaseModel):
    name: str
    line_start: int
    line_end: int
    docstring: Optional[str] = None
    methods: list[str] = Field(default_factory=list)
    bases: list[str] = Field(default_factory=list)


from app.models.nl_detail import NaturalLanguageDetail


class ExplanationEntry(BaseModel):
    name: str
    line_start: int = 0
    line_end: int = 0
    structural: str = ""
    explanation: str = ""
    nl: NaturalLanguageDetail = Field(default_factory=NaturalLanguageDetail)
    methods: list["ExplanationEntry"] = Field(default_factory=list)


class ModuleExplanation(BaseModel):
    path: str
    language: str = ""
    line_count: int = 0
    imports: list[str] = Field(default_factory=list)
    structural_summary: str = ""
    explanation: str = ""
    nl: NaturalLanguageDetail = Field(default_factory=NaturalLanguageDetail)
    role_in_project: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    classes: list[ExplanationEntry] = Field(default_factory=list)
    functions: list[ExplanationEntry] = Field(default_factory=list)
    summary: str = ""


class DependencyNode(BaseModel):
    id: str
    path: str
    label: str
    language: str = ""
    kind: str = "module"


class DependencyEdge(BaseModel):
    source: str
    target: str
    edge_type: str = "import"


class DependencyGraphStats(BaseModel):
    total_nodes: int = 0
    total_edges: int = 0
    edge_type_counts: dict[str, int] = Field(default_factory=dict)


def _disambiguated_labels(paths: list[str]) -> dict[str, str]:
    from collections import Counter

    basenames = Counter(p.rsplit("/", 1)[-1] for p in paths)
    labels: dict[str, str] = {}
    for path in paths:
        basename = path.rsplit("/", 1)[-1]
        if basenames[basename] == 1:
            labels[path] = basename
        elif len(path.split("/")) >= 2:
            labels[path] = "/".join(path.split("/")[-2:])
        else:
            labels[path] = basename
    return labels


def _coerce_legacy_graph_data(data: Any) -> Any:
    if not isinstance(data, dict):
        return data

    nodes = data.get("nodes")
    if nodes and isinstance(nodes[0], str):
        normalized = [p.replace("\\", "/") for p in nodes]
        labels = _disambiguated_labels(normalized)
        data["nodes"] = [
            {
                "id": path,
                "path": path,
                "label": labels[path],
                "language": _guess_language(path),
                "kind": "module",
            }
            for path in normalized
        ]

    edges = data.get("edges") or []
    for edge in edges:
        if isinstance(edge, dict) and edge.get("edge_type") == "extends":
            edge["edge_type"] = "inherits"

    if not data.get("stats"):
        edge_type_counts: dict[str, int] = {}
        for edge in edges:
            edge_type = edge.get("edge_type", "import") if isinstance(edge, dict) else "import"
            edge_type_counts[edge_type] = edge_type_counts.get(edge_type, 0) + 1
        data["stats"] = {
            "total_nodes": len(data.get("nodes") or []),
            "total_edges": len(edges),
            "edge_type_counts": edge_type_counts,
        }

    return data


def _guess_language(path: str) -> str:
    if path.endswith(".py"):
        return "python"
    if path.endswith(".java"):
        return "java"
    return ""


class DependencyGraph(BaseModel):
    nodes: list[DependencyNode] = Field(default_factory=list)
    edges: list[DependencyEdge] = Field(default_factory=list)
    stats: DependencyGraphStats = Field(default_factory=DependencyGraphStats)

    @model_validator(mode="before")
    @classmethod
    def coerce_legacy_nodes(cls, data: Any) -> Any:
        return _coerce_legacy_graph_data(data)


class GeneratedTest(BaseModel):
    source_file: str
    test_file: str
    language: str
    content: str
    framework: str


class TestResult(BaseModel):
    name: str
    status: str
    message: Optional[str] = None
    duration_ms: Optional[float] = None


class TestExecutionResult(BaseModel):
    framework: str
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    coverage_percent: Optional[float] = None
    tests: list[TestResult] = Field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    execution_note: str = ""


class RefactoredFile(BaseModel):
    original_path: str
    refactored_path: str
    original_content: str
    refactored_content: str
    explanation: str
    changes_summary: list[str] = Field(default_factory=list)


class ModernizationResult(BaseModel):
    files: list[RefactoredFile] = Field(default_factory=list)
    overall_summary: str = ""
    ai_generated: bool = False


class BreakingChange(BaseModel):
    title: str
    description: str
    severity: str
    affected_files: list[str] = Field(default_factory=list)
    recommendation: str = ""


class BreakingChangeReport(BaseModel):
    changes: list[BreakingChange] = Field(default_factory=list)
    summary: str = ""


class ProjectSummary(BaseModel):
    name: str
    total_files: int
    total_lines: int
    languages: list[LanguageStats] = Field(default_factory=list)
    files: list[FileInfo] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    job_id: str
    status: AnalysisStatus
    summary: Optional[ProjectSummary] = None
    file_tree: dict[str, Any] = Field(default_factory=dict)
    file_contents: dict[str, str] = Field(default_factory=dict)
    modules: list[ModuleExplanation] = Field(default_factory=list)
    dependency_graph: Optional[DependencyGraph] = None
    generated_tests: list[GeneratedTest] = Field(default_factory=list)
    test_results: Optional[TestExecutionResult] = None
    modernization: Optional[ModernizationResult] = None
    breaking_changes: Optional[BreakingChangeReport] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    ai_mode: str = "heuristic"


class AnalysisJob(BaseModel):
    id: str
    status: AnalysisStatus = AnalysisStatus.PENDING
    source_type: str
    source_label: str
    workspace_path: str
    progress: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
