"""Generate human-friendly natural-language explanations from source code."""

from __future__ import annotations

from app.analyzers.base import ParsedFile
from app.analyzers.semantic_extractor import (
    extract_java_method_semantics,
    extract_module_semantics,
    extract_python_class_semantics,
    extract_python_function_semantics,
    infer_module_role,
    module_docstring,
)
from app.models.nl_detail import NaturalLanguageDetail


def explain_module_nl(pf: ParsedFile, all_paths: list[str]) -> dict:
    role = infer_module_role(pf.path, pf, all_paths)
    doc = module_docstring(pf.content) if pf.language == "python" else None
    mod_sem = extract_module_semantics(pf.content) if pf.language == "python" else {}
    nl = build_module_nl(pf, doc, mod_sem, role)

    return {
        "nl": nl,
        "explanation": nl.to_summary(),
        "role_in_project": role,
        "responsibilities": nl.important_behavior.split("; ") if nl.important_behavior else [],
        "technical_detail": _module_technical_detail(pf, mod_sem),
    }


def build_module_nl(
    pf: ParsedFile, doc: str | None, mod_sem: dict, role: str
) -> NaturalLanguageDetail:
    # Purpose
    if doc:
        purpose = doc.rstrip(".")
    else:
        problem = _infer_problem_solved(pf, None)
        purpose = problem or f"Provides {pf.language} functionality for `{pf.path}`."

    # How it works — component collaboration in prose
    how_parts: list[str] = []
    if mod_sem.get("app_objects"):
        how_parts.append(
            f"Initializes `{', '.join(mod_sem['app_objects'])}` and registers the handlers defined in this file."
        )
    names: list[str] = []
    for cls in pf.classes[:4]:
        names.append(f"class `{cls['name']}`")
    for func in pf.functions[:4]:
        if not func["name"].startswith("_"):
            names.append(f"`{func['name']}()`")
    if names:
        how_parts.append(f"It defines {', '.join(names)} that callers import or route to.")

    how_it_works = " ".join(how_parts) if how_parts else role

    # Input — what this module depends on
    input_desc = ""
    if pf.imports:
        imps = []
        for i in pf.imports[:6]:
            mod = i.get("module", "")
            names = i.get("names") or []
            if mod and names and names != ["*"]:
                imps.append(f"`{mod}` ({', '.join(names[:3])})")
            elif mod:
                imps.append(f"`{mod}`")
        input_desc = "Relies on: " + ", ".join(imps) + "."

    # Output — what this module exposes
    output_parts: list[str] = []
    for func in pf.functions[:5]:
        if func["name"].startswith("_"):
            continue
        sem = extract_python_function_semantics(pf.content, func["name"]) if pf.language == "python" else {}
        if sem.get("decorators"):
            output_parts.append(f"{func['name']} as {sem['decorators'][0]}")
        else:
            output_parts.append(f"function `{func['name']}`")
    for cls in pf.classes[:3]:
        output_parts.append(f"class `{cls['name']}`")
    output_desc = "Exposes: " + ", ".join(output_parts) + "." if output_parts else ""

    important = role
    if pf.parse_error:
        important += f"; Parse warning: {pf.parse_error}"

    return NaturalLanguageDetail(
        purpose=purpose,
        how_it_works=how_it_works,
        input_desc=input_desc,
        output_desc=output_desc,
        important_behavior=important,
    )


def explain_class_nl(cls: dict, pf: ParsedFile) -> NaturalLanguageDetail:
    sem = extract_python_class_semantics(pf.content, cls["name"]) if pf.language == "python" else {}
    doc = cls.get("docstring") or sem.get("docstring")
    fields = sem.get("fields") or []
    methods = cls.get("methods") or sem.get("methods") or []
    bases = cls.get("bases") or sem.get("bases") or []
    name = cls["name"]

    if doc:
        purpose = f"`{name}` — {doc.rstrip('.')}"
    elif "Controller" in name:
        purpose = f"`{name}` handles HTTP requests and maps them to service operations."
    elif "Service" in name:
        purpose = f"`{name}` contains the business rules for its domain."
    elif "Repository" in name:
        purpose = f"`{name}` reads and writes persisted records."
    elif any(x in name for x in ("Model", "Entity", "DTO")):
        purpose = f"`{name}` represents a data structure used across the application."
    else:
        purpose = f"`{name}` groups related data and behavior for one part of the domain."

    pub_methods = [m for m in methods if not m.startswith("_") or m == "__init__"]
    how_parts = []
    if bases:
        how_parts.append(f"It builds on {', '.join(bases)}.")
    if fields:
        how_parts.append(f"It stores {', '.join(fields[:4])}.")
    if pub_methods:
        summaries = []
        for m in pub_methods[:5]:
            s = _brief_method_summary({"name": m}, pf, name)
            summaries.append(f"`{m}` {s}")
        how_parts.append("Callers interact through " + "; ".join(summaries) + ".")
    how_it_works = " ".join(how_parts) if how_parts else f"Instances of `{name}` coordinate the methods defined in this class."

    input_desc = f"Inherits from {', '.join(bases)}." if bases else "No superclass — standalone class."
    output_desc = f"Provides methods: {', '.join(pub_methods[:8])}." if pub_methods else ""

    important = ""
    if fields:
        important = f"Maintains typed fields: {', '.join(fields[:5])}."

    technical = build_structural_class_summary(cls)

    return NaturalLanguageDetail(
        purpose=purpose,
        how_it_works=how_it_works,
        input_desc=input_desc,
        output_desc=output_desc,
        important_behavior=important,
        technical_detail=technical,
    )


def explain_function_nl(
    func: dict, pf: ParsedFile, class_name: str | None = None
) -> NaturalLanguageDetail:
    if pf.language == "python":
        sem = extract_python_function_semantics(pf.content, func["name"])
        return _function_nl_from_semantics(func, pf, sem, class_name)
    sem = extract_java_method_semantics(pf.content, func["name"])
    return _java_function_nl(func, pf, sem, class_name)


def _function_nl_from_semantics(
    func: dict, pf: ParsedFile, sem: dict, class_name: str | None
) -> NaturalLanguageDetail:
    name = func["name"]
    doc = func.get("docstring") or sem.get("docstring")
    params = sem.get("parameters") or [p for p in (func.get("parameters") or []) if p != "self"]
    steps = sem.get("steps") or []

    # Purpose
    if doc:
        purpose = doc.rstrip(".")
    elif sem.get("decorators"):
        purpose = f"Handles {sem['decorators'][0]} via `{name}`."
    else:
        purpose = _purpose_from_name_and_sem(name, sem, params)

    how_it_works = _steps_to_prose(steps, sem, name)

    input_desc = _describe_inputs(params, sem)
    output_desc = _describe_output(sem)
    important = _describe_important_behavior(sem)
    technical = " → ".join(steps[:10]) if steps else build_structural_function_summary(func)

    return NaturalLanguageDetail(
        purpose=purpose,
        how_it_works=how_it_works,
        input_desc=input_desc,
        output_desc=output_desc,
        important_behavior=important,
        technical_detail=technical,
    )


def _java_function_nl(
    func: dict, pf: ParsedFile, sem: dict, class_name: str | None
) -> NaturalLanguageDetail:
    name = func["name"]
    params = func.get("parameters") or []
    steps = sem.get("steps") or []

    purpose = _purpose_from_name_and_sem(name, sem, params)
    how_it_works = _steps_to_prose(steps, sem, name)
    input_desc = _describe_inputs(params, sem)
    output_desc = _describe_output(sem)
    important = _describe_important_behavior(sem)
    technical = " → ".join(steps[:10]) if steps else build_structural_function_summary(func)

    return NaturalLanguageDetail(
        purpose=purpose,
        how_it_works=how_it_works,
        input_desc=input_desc,
        output_desc=output_desc,
        important_behavior=important,
        technical_detail=technical,
    )


def _purpose_from_name_and_sem(name: str, sem: dict, params: list[str]) -> str:
    lower = name.lower()
    if lower in ("main", "run", "start"):
        return "Starts the application runtime."
    if lower.startswith(("get", "fetch", "find")):
        return f"Retrieves data using {', '.join(params)}." if params else "Retrieves data from a source."
    if lower.startswith(("create", "add", "insert")):
        return f"Creates a new record from {', '.join(params)}." if params else "Creates a new entity."
    if lower.startswith(("update", "save", "set")):
        return f"Updates existing state with {', '.join(params)}." if params else "Persists updated values."
    if lower.startswith(("delete", "remove")):
        return "Removes an existing record or resource."
    if lower.startswith(("validate", "check", "is_")):
        return "Validates input or state and reports whether it is acceptable."
    if sem.get("decorators"):
        return f"Serves {sem['decorators'][0]}."
    return f"Implements the `{name}` operation."


def _steps_to_prose(steps: list[str], sem: dict, name: str) -> str:
    if not steps:
        return f"The `{name}` implementation is declared but contains no extractable body statements."

    sentences: list[str] = []

    validations = [s for s in steps if s.startswith("Checks")]
    raises = [s for s in steps if s.startswith("Raises") or "raises" in s.lower()]
    assigns = [s for s in steps if s.startswith("Sets") or s.startswith("Assigns")]
    calls = [s for s in steps if s.startswith("Calls") or s.startswith("Invokes")]
    returns = [s for s in steps if s.startswith("Returns")]

    if validations or raises:
        val_text = validations[0].replace("Checks `", "").replace("`", "") if validations else ""
        if raises:
            suffix = f" ({val_text})" if val_text else ""
            sentences.append(
                f"First it validates input{suffix} and rejects invalid cases."
            )
        elif validations:
            sentences.append(f"It evaluates whether `{val_text}` before continuing.")

    if assigns:
        var_names = []
        for a in assigns[:2]:
            if "`" in a:
                var_names.append(a.split("`")[1])
        if var_names:
            sentences.append(f"It computes intermediate values such as `{', '.join(var_names)}`.")

    ext_calls = [c for c in sem.get("calls", []) if c.split("(")[0].split(".")[-1] != name]
    if ext_calls:
        delegates = [f"`{c.split('(')[0]}`" for c in ext_calls[:3]]
        sentences.append(
            f"It delegates work to {', '.join(delegates)}."
        )
    elif calls:
        sentences.append("It invokes helper functions to complete the operation.")

    if returns:
        ret_val = returns[0].replace("Returns `", "").replace("`", "")
        sentences.append(f"Finally it returns `{ret_val}` to the caller.")

    return " ".join(sentences) if sentences else f"It executes {len(steps)} logical step(s) defined in source."


def _describe_inputs(params: list[str], sem: dict) -> str:
    if not params:
        if sem.get("class_name"):
            return "Operates on the class instance (`self`)."
        return "No parameters."
    parts = [f"`{p}`" for p in params]
    ann = sem.get("return_annotation")
    text = f"Accepts: {', '.join(parts)}."
    if ann:
        text += f" (declared in context of return type `{ann}`)"
    return text


def _describe_output(sem: dict) -> str:
    if sem.get("returns"):
        return f"Returns `{sem['returns'][0]}` to the caller."
    if sem.get("return_annotation"):
        return f"Annotated to return `{sem['return_annotation']}`."
    assigns = [s for s in sem.get("steps", []) if s.startswith("Sets")]
    if assigns:
        return "Mutates local state; no explicit return value detected."
    return "No return value identified in static analysis."


def _describe_important_behavior(sem: dict) -> str:
    notes: list[str] = []
    if sem.get("decorators"):
        notes.extend(sem["decorators"])
    if sem.get("raises"):
        notes.append(f"Raises {sem['raises'][0]} on invalid input")
    if sem.get("is_async"):
        notes.append("Async — must be awaited")
    side = [c for c in sem.get("calls", [])][:3]
    if side:
        notes.append(f"Side effects via {', '.join(side)}")
    return "; ".join(notes)


def _brief_method_summary(func: dict, pf: ParsedFile, class_name: str) -> str:
    sem = extract_python_function_semantics(pf.content, func["name"]) if pf.language == "python" else {}
    if sem.get("docstring"):
        return sem["docstring"][:80].rstrip(".")
    if sem.get("decorators"):
        return sem["decorators"][0]
    return "handles an operation"


def _module_technical_detail(pf: ParsedFile, mod_sem: dict) -> str:
    parts = []
    if mod_sem.get("top_level"):
        parts.append("Definitions: " + "; ".join(mod_sem["top_level"][:8]))
    return " | ".join(parts)


def _infer_problem_solved(pf: ParsedFile, doc: str | None) -> str:
    if doc:
        return doc[:200].rstrip(".")
    pl = pf.path.lower()
    if "auth" in pl:
        return "User authentication and credential handling"
    if "payment" in pl:
        return "Payment processing"
    if pl.endswith("main.py"):
        return "Application bootstrap and HTTP routing"
    return ""


def build_structural_module_summary(pf: ParsedFile) -> str:
    parts = [f"Language: {pf.language}", f"Lines: {pf.line_count}"]
    if pf.imports:
        imps = []
        for i in pf.imports[:8]:
            mod = i.get("module", "")
            names = i.get("names") or []
            if names and names != ["*"]:
                imps.append(f"{mod} ({', '.join(names[:3])})")
            elif mod:
                imps.append(mod)
        parts.append(f"Imports: {'; '.join(imps)}")
    if pf.classes:
        parts.append(f"Classes: {', '.join(c['name'] for c in pf.classes)}")
    if pf.functions:
        parts.append(f"Functions: {', '.join(f['name'] for f in pf.functions)}")
    if pf.parse_error:
        parts.append(f"Parse note: {pf.parse_error}")
    return " | ".join(parts)


def build_structural_class_summary(cls: dict) -> str:
    parts = [f"Class: {cls['name']}"]
    if cls.get("line_start"):
        parts.append(f"Lines: {cls.get('line_start')}–{cls.get('line_end')}")
    if cls.get("bases"):
        parts.append(f"Bases: {', '.join(cls['bases'])}")
    if cls.get("methods"):
        parts.append(f"Methods: {', '.join(cls['methods'])}")
    if cls.get("docstring"):
        parts.append("Docstring present")
    return " | ".join(parts)


def build_structural_function_summary(func: dict) -> str:
    parts = [f"Function: {func['name']}"]
    if func.get("line_start"):
        parts.append(f"Lines: {func.get('line_start')}–{func.get('line_end')}")
    params = func.get("parameters") or []
    if params:
        parts.append(f"Parameters: {', '.join(params)}")
    if func.get("docstring"):
        parts.append("Docstring present")
    return " | ".join(parts)
