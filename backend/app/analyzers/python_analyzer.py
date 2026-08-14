import ast
from typing import Optional

from app.analyzers.base import BaseAnalyzer, ParsedFile
from app.utils.security import count_lines


class PythonAnalyzer(BaseAnalyzer):
    def can_analyze(self, path: str) -> bool:
        return path.endswith(".py")

    def analyze_file(self, path: str, content: str) -> ParsedFile:
        line_count = count_lines(content)
        parsed = ParsedFile(
            path=path,
            language="python",
            line_count=line_count,
            size_bytes=len(content.encode("utf-8")),
            content=content,
        )
        try:
            tree = ast.parse(content, filename=path)
        except SyntaxError as exc:
            parsed.parse_error = f"Syntax error: {exc.msg} (line {exc.lineno})"
            return parsed

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    parsed.imports.append({"module": alias.name, "names": [], "line": node.lineno})
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [a.name for a in node.names]
                parsed.imports.append({"module": module, "names": names, "line": node.lineno})

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                methods = [
                    n.name
                    for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                bases = []
                for b in node.bases:
                    if isinstance(b, ast.Name):
                        bases.append(b.id)
                    elif isinstance(b, ast.Attribute):
                        bases.append(ast.unparse(b))
                parsed.classes.append({
                    "name": node.name,
                    "line_start": node.lineno,
                    "line_end": node.end_lineno or node.lineno,
                    "docstring": ast.get_docstring(node),
                    "methods": methods,
                    "bases": bases,
                })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = [arg.arg for arg in node.args.args]
                parsed.functions.append({
                    "name": node.name,
                    "line_start": node.lineno,
                    "line_end": node.end_lineno or node.lineno,
                    "docstring": ast.get_docstring(node),
                    "parameters": params,
                })

        return parsed
