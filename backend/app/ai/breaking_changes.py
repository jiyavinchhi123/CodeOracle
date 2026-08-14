from app.ai.provider import LLMProvider, extract_json_block
from app.analyzers.base import ParsedFile
from app.models.analysis import BreakingChange, BreakingChangeReport, RefactoredFile


class BreakingChangeService:
    def __init__(self, provider: LLMProvider, ai_mode: str) -> None:
        self.provider = provider
        self.ai_mode = ai_mode

    async def analyze(
        self,
        parsed_files: list[ParsedFile],
        refactored: list[RefactoredFile],
    ) -> BreakingChangeReport:
        if self.ai_mode == "llm" and refactored:
            report = await self._llm_analyze(refactored)
            if report.changes:
                return report
        return self._heuristic_analyze(parsed_files, refactored)

    async def _llm_analyze(self, refactored: list[RefactoredFile]) -> BreakingChangeReport:
        summaries = []
        for rf in refactored[:5]:
            summaries.append({
                "file": rf.original_path,
                "changes": rf.changes_summary,
                "explanation": rf.explanation[:500],
            })
        user = f"""Analyze potential breaking changes from these refactorings.
Only report changes evidenced in the diff summaries.

{summaries}

Return JSON:
{{
  "summary": "overall assessment",
  "changes": [
    {{"title": "...", "description": "...", "severity": "low|medium|high", "affected_files": ["..."], "recommendation": "..."}}
  ]
}}"""
        try:
            raw = await self.provider.complete(
                "You analyze breaking changes conservatively. Respond with JSON only.",
                user,
                max_tokens=2000,
            )
            data = extract_json_block(raw)
            if data:
                changes = [BreakingChange(**c) for c in data.get("changes", [])]
                return BreakingChangeReport(changes=changes, summary=data.get("summary", ""))
        except Exception:
            pass
        return BreakingChangeReport()

    def _heuristic_analyze(
        self,
        parsed_files: list[ParsedFile],
        refactored: list[RefactoredFile],
    ) -> BreakingChangeReport:
        changes: list[BreakingChange] = []
        ref_map = {rf.original_path: rf for rf in refactored}

        for pf in parsed_files:
            rf = ref_map.get(pf.path)
            if not rf:
                continue
            orig_names = {c["name"] for c in pf.classes} | {f["name"] for f in pf.functions}
            # Detect removed public symbols (simple line-based heuristic)
            if rf.refactored_content != rf.original_content:
                for cls in pf.classes:
                    if cls["name"] not in rf.refactored_content:
                        changes.append(
                            BreakingChange(
                                title=f"Removed class '{cls['name']}'",
                                description=f"Class {cls['name']} present in original but not found in refactored content.",
                                severity="high",
                                affected_files=[pf.path],
                                recommendation="Verify all callers before deploying.",
                            )
                        )
                for func in pf.functions:
                    if not func["name"].startswith("_") and func["name"] not in rf.refactored_content:
                        changes.append(
                            BreakingChange(
                                title=f"Removed function '{func['name']}'",
                                description=f"Function {func['name']} may have been removed or renamed.",
                                severity="medium",
                                affected_files=[pf.path],
                                recommendation="Update imports and call sites.",
                            )
                        )

        # Parse errors as warnings
        for pf in parsed_files:
            if pf.parse_error:
                changes.append(
                    BreakingChange(
                        title=f"Parse error in {pf.path}",
                        description=pf.parse_error,
                        severity="low",
                        affected_files=[pf.path],
                        recommendation="Fix syntax errors before refactoring.",
                    )
                )

        summary = f"Found {len(changes)} potential issue(s) from static comparison."
        if not changes:
            summary = "No breaking changes detected by static analysis."
        return BreakingChangeReport(changes=changes, summary=summary)
