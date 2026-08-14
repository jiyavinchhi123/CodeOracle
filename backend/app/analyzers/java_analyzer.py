import javalang

from app.analyzers.base import BaseAnalyzer, ParsedFile
from app.utils.security import count_lines


class JavaAnalyzer(BaseAnalyzer):
    def can_analyze(self, path: str) -> bool:
        return path.endswith(".java")

    def analyze_file(self, path: str, content: str) -> ParsedFile:
        line_count = count_lines(content)
        parsed = ParsedFile(
            path=path,
            language="java",
            line_count=line_count,
            size_bytes=len(content.encode("utf-8")),
            content=content,
        )
        try:
            tree = javalang.parse.parse(content)
        except (javalang.parser.JavaSyntaxError, RecursionError) as exc:
            parsed.parse_error = f"Parse error: {exc}"
            return parsed

        package = tree.package.name if tree.package else ""
        for imp in tree.imports or []:
            parsed.imports.append({
                "module": imp.path,
                "names": ["*"] if imp.wildcard else [imp.path.split(".")[-1]],
                "line": 0,
                "package": package,
            })

        for path_item, node in tree.filter(javalang.tree.ClassDeclaration):
            methods = [
                m.name
                for m in node.methods or []
            ]
            bases = []
            extends = node.extends.name if node.extends else None
            implements = [impl.name for impl in node.implements or []]
            if extends:
                bases.append(extends)
            bases.extend(implements)
            parsed.classes.append({
                "name": node.name,
                "line_start": 0,
                "line_end": 0,
                "docstring": None,
                "methods": methods,
                "bases": bases,
                "extends": extends,
                "implements": implements,
            })

        for path_item, node in tree.filter(javalang.tree.InterfaceDeclaration):
            methods = [m.name for m in node.methods or []]
            parsed.classes.append({
                "name": node.name,
                "line_start": 0,
                "line_end": 0,
                "docstring": None,
                "methods": methods,
                "bases": [],
            })

        for path_item, node in tree.filter(javalang.tree.MethodDeclaration):
            params = [p.name for p in node.parameters] if node.parameters else []
            parsed.functions.append({
                "name": node.name,
                "line_start": 0,
                "line_end": 0,
                "docstring": None,
                "parameters": params,
            })

        return parsed
