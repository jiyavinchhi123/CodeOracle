from pathlib import Path

from app.ai.provider import LLMProvider, extract_json_block
from app.ai.utils import map_limited
from app.analyzers.base import ParsedFile
from app.config import Settings
from app.models.analysis import ModernizationResult, RefactoredFile


class ModernizerService:
    def __init__(self, provider: LLMProvider, ai_mode: str, settings: Settings) -> None:
        self.provider = provider
        self.ai_mode = ai_mode
        self.settings = settings

    async def modernize(
        self, parsed_files: list[ParsedFile], limit: int | None = None
    ) -> ModernizationResult:
        cap = limit or self.settings.ai_max_modernize_files
        candidates = sorted(
            [
                pf for pf in parsed_files
                if not pf.parse_error
                and "_generated_tests" not in pf.path
                and "_refactored" not in pf.path
                and ".modern." not in pf.path
            ],
            key=lambda p: p.line_count,
        )[:cap]

        if self.ai_mode == "llm":
            files = await map_limited(
                candidates,
                self._llm_modernize,
                limit=self.settings.llm_max_concurrency,
            )
            files = [f for f in files if f]
        else:
            files = [self._heuristic_modernize(pf) for pf in candidates]

        ai_generated = self.ai_mode == "llm"
        summary = (
            "AI-suggested modernizations based on analyzed source files."
            if ai_generated
            else "Heuristic refactorings applied using static analysis rules (no LLM configured)."
        )
        return ModernizationResult(files=files, overall_summary=summary, ai_generated=ai_generated)

    async def _llm_modernize(self, pf: ParsedFile) -> RefactoredFile | None:
        snippet = pf.content[:2500]
        user = f"""Suggest modernization for this {pf.language} file.
Only refactor based on visible code. Do not add unrelated features.

File: {pf.path}
```
{snippet}
```

Return JSON:
{{
  "refactored_content": "full refactored file content",
  "explanation": "what changed and why",
  "changes_summary": ["change 1", "change 2"]
}}"""
        try:
            raw = await self.provider.complete(
                "You modernize legacy code conservatively. Respond with JSON only.",
                user,
                max_tokens=2000,
            )
            data = extract_json_block(raw)
            if data and data.get("refactored_content"):
                ref_path = Path(pf.path).stem + ".modern" + Path(pf.path).suffix
                return RefactoredFile(
                    original_path=pf.path,
                    refactored_path=ref_path,
                    original_content=pf.content,
                    refactored_content=data["refactored_content"],
                    explanation=data.get("explanation", ""),
                    changes_summary=data.get("changes_summary", []),
                )
        except Exception:
            pass
        return self._heuristic_modernize(pf)

    def _heuristic_modernize(self, pf: ParsedFile) -> RefactoredFile:
        content = pf.content
        changes: list[str] = []
        refactored = content

        if pf.language == "python":
            refactored, py_changes = self._modernize_python(content)
            changes.extend(py_changes)
        elif pf.language == "java":
            refactored, java_changes = self._modernize_java(content)
            changes.extend(java_changes)

        if not changes:
            changes.append("No automatic changes applied; code structure preserved.")

        ref_path = Path(pf.path).stem + ".modern" + Path(pf.path).suffix
        return RefactoredFile(
            original_path=pf.path,
            refactored_path=ref_path,
            original_content=pf.content,
            refactored_content=refactored,
            explanation="Heuristic modernization: " + "; ".join(changes),
            changes_summary=changes,
        )

    def _modernize_python(self, content: str) -> tuple[str, list[str]]:
        changes: list[str] = []
        new_lines = [line.rstrip() for line in content.splitlines()]
        if any(line.startswith("def ") and "->" not in line for line in new_lines):
            changes.append("Consider adding return type hints to functions")
        changes.append("Normalized trailing whitespace")
        return "\n".join(new_lines) + ("\n" if content.endswith("\n") else ""), changes

    def _modernize_java(self, content: str) -> tuple[str, list[str]]:
        changes = ["Normalized trailing whitespace"]
        new_lines = [line.rstrip() for line in content.splitlines()]
        if "import java.util.Vector" in content:
            changes.append("Consider replacing java.util.Vector with ArrayList")
        return "\n".join(new_lines) + ("\n" if content.endswith("\n") else ""), changes
