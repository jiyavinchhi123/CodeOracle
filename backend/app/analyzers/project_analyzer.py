from pathlib import Path

from app.analyzers.base import ParsedFile
from app.analyzers.dependency_graph import build_dependency_graph
from app.analyzers.java_analyzer import JavaAnalyzer
from app.analyzers.python_analyzer import PythonAnalyzer
from app.models.analysis import (
    ClassInfo,
    DependencyGraph,
    FileInfo,
    FunctionInfo,
    LanguageStats,
    ProjectSummary,
)
from app.utils.security import MAX_FILE_BYTES, build_file_tree, detect_language, is_analyzable_source


class ProjectAnalyzer:
    def __init__(self) -> None:
        self._analyzers = [PythonAnalyzer(), JavaAnalyzer()]

    def discover_files(self, workspace: Path) -> list[str]:
        files: list[str] = []
        for path in workspace.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(workspace).as_posix()
            if is_analyzable_source(rel):
                files.append(rel)
        return sorted(files)

    def analyze_workspace(self, workspace: Path, project_name: str) -> tuple[
        ProjectSummary, dict, dict[str, str], list[ParsedFile], DependencyGraph
    ]:
        rel_paths = self.discover_files(workspace)
        parsed_files: list[ParsedFile] = []
        file_contents: dict[str, str] = {}
        lang_stats: dict[str, LanguageStats] = {}

        for rel in rel_paths:
            full = workspace / rel
            try:
                raw = full.read_bytes()
            except OSError:
                continue
            if len(raw) > MAX_FILE_BYTES:
                continue
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                content = raw.decode("latin-1", errors="replace")

            file_contents[rel] = content
            lang = detect_language(rel) or "unknown"

            parsed = self._analyze_content(rel, content)
            parsed_files.append(parsed)

            if lang not in lang_stats:
                lang_stats[lang] = LanguageStats(language=lang, file_count=0, line_count=0)
            lang_stats[lang].file_count += 1
            lang_stats[lang].line_count += parsed.line_count

        file_infos = [
            FileInfo(
                path=pf.path,
                language=pf.language,
                line_count=pf.line_count,
                size_bytes=pf.size_bytes,
            )
            for pf in parsed_files
        ]

        summary = ProjectSummary(
            name=project_name,
            total_files=len(parsed_files),
            total_lines=sum(pf.line_count for pf in parsed_files),
            languages=sorted(lang_stats.values(), key=lambda x: x.language),
            files=file_infos,
        )

        tree = build_file_tree([pf.path for pf in parsed_files])
        graph = build_dependency_graph(parsed_files)
        return summary, tree, file_contents, parsed_files, graph

    def _analyze_content(self, path: str, content: str) -> ParsedFile:
        for analyzer in self._analyzers:
            if analyzer.can_analyze(path):
                return analyzer.analyze_file(path, content)
        lang = detect_language(path) or "unknown"
        from app.analyzers.base import ParsedFile as PF
        return PF(
            path=path,
            language=lang,
            line_count=content.count("\n") + 1,
            size_bytes=len(content.encode("utf-8")),
            content=content,
        )

    @staticmethod
    def to_class_infos(parsed: ParsedFile) -> list[ClassInfo]:
        return [
            ClassInfo(
                name=c["name"],
                line_start=c.get("line_start", 0),
                line_end=c.get("line_end", 0),
                docstring=c.get("docstring"),
                methods=c.get("methods", []),
                bases=c.get("bases", []),
            )
            for c in parsed.classes
        ]

    @staticmethod
    def to_function_infos(parsed: ParsedFile) -> list[FunctionInfo]:
        return [
            FunctionInfo(
                name=f["name"],
                line_start=f.get("line_start", 0),
                line_end=f.get("line_end", 0),
                docstring=f.get("docstring"),
                parameters=f.get("parameters", []),
            )
            for f in parsed.functions
        ]
