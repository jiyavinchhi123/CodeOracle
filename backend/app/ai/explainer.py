from app.ai.nl_generator import (
    build_structural_class_summary,
    build_structural_function_summary,
    build_structural_module_summary,
    explain_class_nl,
    explain_function_nl,
    explain_module_nl,
)
from app.ai.provider import LLMProvider, extract_json_block
from app.ai.utils import map_limited
from app.analyzers.base import ParsedFile
from app.analyzers.semantic_extractor import extract_python_function_semantics
from app.config import Settings
from app.models.analysis import ExplanationEntry, ModuleExplanation
from app.models.nl_detail import NaturalLanguageDetail


SYSTEM_PROMPT = """You are CodeOracle, a legacy codebase analysis assistant.
Analyze ONLY what is present in the supplied code.
Provide separate structural metadata and natural-language explanations.
Do NOT invent behavior not evidenced in the code.
Respond with valid JSON only."""


class ExplainerService:
    def __init__(self, provider: LLMProvider, ai_mode: str, settings: Settings) -> None:
        self.provider = provider
        self.ai_mode = ai_mode
        self.settings = settings

    async def explain_modules(
        self, parsed_files: list[ParsedFile], limit: int | None = None
    ) -> list[ModuleExplanation]:
        cap = limit or self.settings.ai_max_explain_files
        targets = parsed_files[:cap]
        all_paths = [pf.path for pf in parsed_files]
        if self.ai_mode == "llm":
            return await map_limited(
                targets,
                lambda pf: self._llm_explain(pf, all_paths),
                limit=self.settings.llm_max_concurrency,
            )
        return [self._explain(pf, all_paths) for pf in targets]

    async def _llm_explain(self, pf: ParsedFile, all_paths: list[str]) -> ModuleExplanation:
        snippet = pf.content[:3500]
        user = f"""Analyze this {pf.language} file: {pf.path}

Project context: {len(all_paths)} source files in repository.

Code:
```
{snippet}
```

Return JSON with SPECIFIC behavior from the code — no generic filler phrases.
Each explanation must cite actual logic, conditions, return values, and calls visible in the snippet.
Use human-friendly prose for "nl" sections — NOT step-by-step AST traces or arrow chains.
{{
  "structural_summary": "concise structural metadata",
  "nl": {{
    "purpose": "what this module does and why it exists",
    "how_it_works": "summary of important logic in natural language",
    "input_desc": "important dependencies and inputs",
    "output_desc": "what the module exposes or returns",
    "important_behavior": "validation, edge cases, side effects"
  }},
  "role_in_project": "one sentence on project role",
  "responsibilities": ["responsibility 1", "responsibility 2"],
  "classes": [{{
    "name": "...",
    "line_start": 0,
    "line_end": 0,
    "structural": "bases, methods, line numbers",
    "nl": {{
      "purpose": "...",
      "how_it_works": "...",
      "input_desc": "...",
      "output_desc": "...",
      "important_behavior": "..."
    }},
    "methods": [{{
      "name": "...",
      "structural": "parameters, lines",
      "nl": {{
        "purpose": "...",
        "how_it_works": "...",
        "input_desc": "...",
        "output_desc": "...",
        "important_behavior": "..."
      }}
    }}]
  }}],
  "functions": [{{
    "name": "...",
    "line_start": 0,
    "line_end": 0,
    "structural": "parameters, lines",
    "nl": {{
      "purpose": "...",
      "how_it_works": "...",
      "input_desc": "...",
      "output_desc": "...",
      "important_behavior": "..."
    }}
  }}]
}}"""
        try:
            raw = await self.provider.complete(SYSTEM_PROMPT, user, max_tokens=2000)
            data = extract_json_block(raw)
            if data:
                return self._from_llm_json(pf, data)
        except Exception:
            pass
        return self._explain(pf, all_paths)

    def _from_llm_json(self, pf: ParsedFile, data: dict) -> ModuleExplanation:
        mod = self._explain(pf, [])
        mod.structural_summary = data.get("structural_summary") or mod.structural_summary
        mod.nl = self._nl_from_json(data.get("nl"), mod.nl)
        mod.explanation = mod.nl.to_summary() or data.get("explanation", mod.explanation)
        mod.role_in_project = data.get("role_in_project") or mod.role_in_project
        mod.responsibilities = data.get("responsibilities") or mod.responsibilities
        mod.summary = mod.explanation

        if data.get("classes"):
            mod.classes = [self._entry_from_json(c, nested_methods=True) for c in data["classes"]]
        if data.get("functions"):
            mod.functions = [self._entry_from_json(f) for f in data["functions"]]
        return mod

    def _nl_from_json(self, data: dict | None, fallback: NaturalLanguageDetail) -> NaturalLanguageDetail:
        if not data:
            return fallback
        return NaturalLanguageDetail(
            purpose=data.get("purpose") or fallback.purpose,
            how_it_works=data.get("how_it_works") or fallback.how_it_works,
            input_desc=data.get("input_desc") or fallback.input_desc,
            output_desc=data.get("output_desc") or fallback.output_desc,
            important_behavior=data.get("important_behavior") or fallback.important_behavior,
            technical_detail=data.get("technical_detail") or fallback.technical_detail,
        )

    def _entry_from_json(self, item: dict, nested_methods: bool = False) -> ExplanationEntry:
        methods = []
        if nested_methods and item.get("methods"):
            methods = [self._entry_from_json(m) for m in item["methods"]]
        nl = self._nl_from_json(item.get("nl"), NaturalLanguageDetail())
        if not nl.purpose and item.get("explanation"):
            nl.purpose = item["explanation"]
        return ExplanationEntry(
            name=item.get("name", ""),
            line_start=item.get("line_start", 0),
            line_end=item.get("line_end", 0),
            structural=item.get("structural", ""),
            explanation=nl.to_summary() or item.get("explanation", ""),
            nl=nl,
            methods=methods,
        )

    def _explain(self, pf: ParsedFile, all_paths: list[str]) -> ModuleExplanation:
        nl = explain_module_nl(pf, all_paths)
        imports = []
        for i in pf.imports[:12]:
            mod = i.get("module", "")
            names = i.get("names") or []
            if mod and names:
                imports.append(f"{mod} ({', '.join(names[:3])})")
            elif mod:
                imports.append(mod)

        classes = [self._explain_class(cls, pf) for cls in pf.classes]
        functions = [self._explain_function(func, pf) for func in pf.functions]

        explanation = nl["explanation"]
        mod_nl: NaturalLanguageDetail = nl["nl"]
        if nl.get("technical_detail"):
            mod_nl.technical_detail = nl["technical_detail"]

        return ModuleExplanation(
            path=pf.path,
            language=pf.language,
            line_count=pf.line_count,
            imports=imports,
            structural_summary=build_structural_module_summary(pf),
            explanation=explanation,
            nl=mod_nl,
            role_in_project=nl["role_in_project"],
            responsibilities=nl["responsibilities"],
            classes=classes,
            functions=functions,
            summary=explanation,
        )

    def _explain_class(self, cls: dict, pf: ParsedFile) -> ExplanationEntry:
        method_entries = []
        for method_name in cls.get("methods", []):
            if method_name.startswith("__") and method_name not in ("__init__",):
                continue
            func_dict = self._method_dict(pf, cls["name"], method_name)
            method_entries.append(self._explain_function(func_dict, pf, class_name=cls["name"]))

        nl_detail = explain_class_nl(cls, pf)
        return ExplanationEntry(
            name=cls["name"],
            line_start=cls.get("line_start", 0),
            line_end=cls.get("line_end", 0),
            structural=build_structural_class_summary(cls),
            explanation=nl_detail.to_summary(),
            nl=nl_detail,
            methods=method_entries,
        )

    def _explain_function(
        self, func: dict, pf: ParsedFile, class_name: str | None = None
    ) -> ExplanationEntry:
        nl_detail = explain_function_nl(func, pf, class_name)
        return ExplanationEntry(
            name=func["name"],
            line_start=func.get("line_start", 0),
            line_end=func.get("line_end", 0),
            structural=build_structural_function_summary(func),
            explanation=nl_detail.to_summary(),
            nl=nl_detail,
        )

    def _method_dict(self, pf: ParsedFile, class_name: str, method_name: str) -> dict:
        sem = extract_python_function_semantics(pf.content, method_name) if pf.language == "python" else {}
        return {
            "name": method_name,
            "line_start": 0,
            "line_end": 0,
            "parameters": sem.get("parameters") or ([ "self"] if pf.language == "python" else []),
            "docstring": sem.get("docstring"),
        }
