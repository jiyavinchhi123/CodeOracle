"""Extract semantic facts from source code for natural-language explanations."""

from __future__ import annotations

import ast
import re
from functools import lru_cache
from typing import Any

from app.analyzers.base import ParsedFile


@lru_cache(maxsize=256)
def _cached_parse(content: str) -> ast.AST | None:
    try:
        return ast.parse(content)
    except SyntaxError:
        return None


def module_docstring(content: str) -> str | None:
    tree = _cached_parse(content)
    if tree is None:
        return None
    return ast.get_docstring(tree)


def extract_python_function_semantics(content: str, func_name: str) -> dict[str, Any]:
    tree = _cached_parse(content)
    if tree is None:
        return {}

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return _python_func_facts(node)
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == func_name:
                    return _python_func_facts(item, class_name=node.name)
    return {}


def extract_python_class_semantics(content: str, class_name: str) -> dict[str, Any]:
    tree = _cached_parse(content)
    if tree is None:
        return {}

    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return _python_class_facts(node)
    return {}


def extract_module_semantics(content: str) -> dict[str, Any]:
    tree = _cached_parse(content)
    if tree is None:
        return {"docstring": None, "top_level": [], "app_objects": []}

    top_level: list[str] = []
    app_objects: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    try:
                        val = ast.unparse(node.value)[:80]
                        top_level.append(f"{t.id} = {val}")
                        if "FastAPI" in val or "Flask" in val or "APIRouter" in val:
                            app_objects.append(t.id)
                    except Exception:
                        top_level.append(t.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            top_level.append(f"function {node.name}()")
        elif isinstance(node, ast.ClassDef):
            top_level.append(f"class {node.name}")

    return {
        "docstring": ast.get_docstring(tree),
        "top_level": top_level[:12],
        "app_objects": app_objects,
    }


def _python_func_facts(
    node: ast.FunctionDef | ast.AsyncFunctionDef, class_name: str | None = None
) -> dict[str, Any]:
    decorators = [_decorator_detail(d) for d in node.decorator_list]
    steps = _extract_body_steps(node.body)
    calls: list[str] = []
    returns: list[str] = []
    raises: list[str] = []

    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            name = _call_detail(sub)
            if name:
                calls.append(name)
        elif isinstance(sub, ast.Return) and sub.value is not None:
            try:
                returns.append(ast.unparse(sub.value)[:100])
            except Exception:
                returns.append("a value")
        elif isinstance(sub, ast.Raise) and sub.exc is not None:
            try:
                raises.append(ast.unparse(sub.exc)[:120])
            except Exception:
                raises.append("an exception")

    ret_ann = None
    if node.returns:
        try:
            ret_ann = ast.unparse(node.returns)
        except Exception:
            pass

    params = [a.arg for a in node.args.args if a.arg != "self"]
    return {
        "class_name": class_name,
        "decorators": [d for d in decorators if d],
        "parameters": params,
        "return_annotation": ret_ann,
        "returns": list(dict.fromkeys(returns))[:3],
        "calls": list(dict.fromkeys(calls))[:10],
        "raises": list(dict.fromkeys(raises))[:5],
        "steps": steps[:12],
        "is_async": isinstance(node, ast.AsyncFunctionDef),
        "docstring": ast.get_docstring(node),
    }


def _extract_body_steps(body: list[ast.stmt]) -> list[str]:
    steps: list[str] = []
    for stmt in body:
        if isinstance(stmt, ast.If):
            try:
                cond = ast.unparse(stmt.test)[:100]
                steps.append(f"Checks `{cond}`")
                if stmt.body:
                    inner = _summarize_stmt(stmt.body[0])
                    if inner:
                        steps.append(f"When true: {inner}")
                if stmt.orelse and isinstance(stmt.orelse[0], ast.Raise):
                    inner = _summarize_stmt(stmt.orelse[0])
                    if inner:
                        steps.append(f"When false: {inner}")
            except Exception:
                steps.append("Evaluates a condition")
        elif isinstance(stmt, ast.Return):
            try:
                val = ast.unparse(stmt.value) if stmt.value else "None"
                steps.append(f"Returns `{val}`")
            except Exception:
                steps.append("Returns a value")
        elif isinstance(stmt, ast.Assign):
            try:
                targets = ", ".join(ast.unparse(t) for t in stmt.targets)
                val = ast.unparse(stmt.value)[:90]
                steps.append(f"Sets `{targets}` = `{val}`")
            except Exception:
                steps.append("Assigns a variable")
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            try:
                steps.append(f"Calls `{ast.unparse(stmt.value)[:100]}`")
            except Exception:
                steps.append("Invokes a function")
        elif isinstance(stmt, ast.Raise):
            try:
                steps.append(f"Raises `{ast.unparse(stmt.exc)[:100]}`")
            except Exception:
                steps.append("Raises an exception")
        elif isinstance(stmt, ast.For):
            try:
                steps.append(f"Loops over `{ast.unparse(stmt.iter)[:80]}`")
            except Exception:
                steps.append("Iterates a collection")
        elif isinstance(stmt, ast.With):
            try:
                items = ", ".join(ast.unparse(i.context_expr)[:40] for i in stmt.items[:2])
                steps.append(f"Uses context manager: {items}")
            except Exception:
                steps.append("Enters a context manager")
    return steps


def _summarize_stmt(stmt: ast.stmt) -> str:
    if isinstance(stmt, ast.Raise):
        try:
            return f"raises {ast.unparse(stmt.exc)[:80]}"
        except Exception:
            return "raises an error"
    if isinstance(stmt, ast.Return):
        try:
            return f"returns {ast.unparse(stmt.value)[:80]}"
        except Exception:
            return "returns"
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        try:
            return f"calls {ast.unparse(stmt.value)[:80]}"
        except Exception:
            return "calls a function"
    if isinstance(stmt, ast.Assign):
        try:
            return f"sets {ast.unparse(stmt.targets[0])} = {ast.unparse(stmt.value)[:60]}"
        except Exception:
            return "assigns a value"
    return ""


def _python_class_facts(node: ast.ClassDef) -> dict[str, Any]:
    methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    bases = []
    for b in node.bases:
        try:
            bases.append(ast.unparse(b))
        except Exception:
            pass
    fields: list[str] = []
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            try:
                ann = ast.unparse(item.annotation) if item.annotation else "Any"
                fields.append(f"{item.target.id}: {ann}")
            except Exception:
                fields.append(item.target.id)
    return {
        "methods": methods,
        "bases": bases,
        "fields": fields[:8],
        "docstring": ast.get_docstring(node),
    }


def _decorator_detail(d: ast.expr) -> str:
    try:
        text = ast.unparse(d)
    except Exception:
        return ""
    lower = text.lower()
    route_match = re.search(r"['\"]([^'\"]+)['\"]", text)
    route = route_match.group(1) if route_match else ""
    if ".get" in lower or "get(" in lower:
        return f"HTTP GET `{route}`" if route else f"GET route ({text[:50]})"
    if ".post" in lower or "post(" in lower:
        return f"HTTP POST `{route}`" if route else f"POST route ({text[:50]})"
    if ".put" in lower or "put(" in lower:
        return f"HTTP PUT `{route}`" if route else f"PUT route ({text[:50]})"
    if ".delete" in lower or "delete(" in lower:
        return f"HTTP DELETE `{route}`" if route else f"DELETE route ({text[:50]})"
    if "staticmethod" in lower:
        return "staticmethod"
    if "classmethod" in lower:
        return "classmethod"
    if "property" in lower:
        return "property"
    return text[:80]


def _call_detail(call: ast.Call) -> str:
    try:
        func = ast.unparse(call.func)
        args = ", ".join(ast.unparse(a)[:30] for a in call.args[:3])
        kw = ", ".join(f"{k.arg}={ast.unparse(k.value)[:20]}" for k in call.keywords[:3] if k.arg)
        detail = func
        if args:
            detail += f"({args})"
        elif kw:
            detail += f"({kw})"
        return detail[:100]
    except Exception:
        return ""


def infer_module_role(path: str, pf: ParsedFile, all_paths: list[str]) -> str:
    p = path.replace("\\", "/")
    pl = p.lower()
    mod_sem = extract_module_semantics(pf.content) if pf.language == "python" else {}

    if mod_sem.get("app_objects"):
        apps = ", ".join(mod_sem["app_objects"])
        return f"Creates `{apps}` and wires the HTTP application for this service."

    if pl.endswith("main.py"):
        endpoints = [f["name"] for f in pf.functions if not f["name"].startswith("_")][:4]
        if endpoints:
            return f"Entry point registering handlers: {', '.join(endpoints)}."
        return "Program entry point that starts the application runtime."

    if "/controller/" in pl or "/controllers/" in pl or "/api/" in pl:
        handlers = [f["name"] for f in pf.functions][:5]
        return f"Maps HTTP requests to: {', '.join(handlers) or 'handlers in this file'}."

    if "/service/" in pl or "/services/" in pl:
        names = [c["name"] for c in pf.classes[:3]] or [f["name"] for f in pf.functions[:3]]
        return f"Encapsulates business rules via {', '.join(names)}."

    if "/model/" in pl or "/models/" in pl or "/dto/" in pl:
        return f"Defines data shapes: {', '.join(c['name'] for c in pf.classes)}."

    if "/repository/" in pl or "/repositories/" in pl:
        return f"Reads/writes persistent storage for {', '.join(c['name'] for c in pf.classes)}."

    folder = p.rsplit("/", 1)[0] if "/" in p else "project root"
    return f"Implements `{folder}` feature logic in {pf.language}."


def extract_java_method_semantics(content: str, method_name: str) -> dict[str, Any]:
    body = extract_java_method_body(content, method_name)
    if not body:
        return {"steps": [], "returns": [], "calls": []}

    steps: list[str] = []
    returns: list[str] = []
    calls: list[str] = []

    for line in body.split(";"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("return "):
            val = line[7:].strip()[:100]
            returns.append(val)
            steps.append(f"Returns `{val}`")
        elif line.startswith("if ") or line.startswith("if("):
            steps.append(f"Checks `{line[:100]}`")
        elif line.startswith("throw ") or " throw " in line:
            steps.append(f"Throws `{line[:100]}`")
        elif re.search(r"\w+\([^)]*\)", line):
            m = re.search(r"(\w+\([^)]*\))", line)
            if m:
                calls.append(m.group(1)[:80])
                steps.append(f"Calls `{m.group(1)[:80]}`")
        elif "=" in line and not line.startswith("="):
            steps.append(f"Assigns `{line[:100]}`")

    return {"steps": steps[:12], "returns": returns[:3], "calls": list(dict.fromkeys(calls))[:8]}


def extract_java_method_body(content: str, method_name: str) -> str:
    pattern = rf"(?:public|private|protected)[\w<>\[\],\s]+\s+{re.escape(method_name)}\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\{{"
    match = re.search(pattern, content)
    if not match:
        return ""
    start = match.end() - 1
    depth = 0
    for i in range(start, min(start + 3000, len(content))):
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0:
                return content[start + 1 : i].strip()
    return ""
