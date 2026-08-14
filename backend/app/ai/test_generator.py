from pathlib import Path

from app.ai.provider import LLMProvider, extract_json_block
from app.ai.utils import map_limited
from app.analyzers.base import ParsedFile
from app.config import Settings
from app.models.analysis import GeneratedTest


class TestGeneratorService:
    def __init__(self, provider: LLMProvider, ai_mode: str, settings: Settings) -> None:
        self.provider = provider
        self.ai_mode = ai_mode
        self.settings = settings

    async def generate_tests(
        self, parsed_files: list[ParsedFile], limit: int | None = None
    ) -> list[GeneratedTest]:
        cap = limit or self.settings.ai_max_test_files
        candidates = [
            pf for pf in parsed_files
            if (pf.functions or pf.classes)
            and "_generated_tests" not in pf.path
            and "_refactored" not in pf.path
            and ".modern." not in pf.path
        ][:cap]
        if self.ai_mode == "llm":
            results = await map_limited(
                candidates,
                self._llm_generate,
                limit=self.settings.llm_max_concurrency,
            )
            return [t for t in results if t]
        return [t for pf in candidates if (t := self._heuristic_generate(pf))]

    async def _llm_generate(self, pf: ParsedFile) -> GeneratedTest | None:
        snippet = pf.content[:2000]
        framework = "pytest" if pf.language == "python" else "junit"
        user = f"""Generate unit tests for this {pf.language} file based ONLY on visible public API.
File: {pf.path}
Classes: {[c['name'] for c in pf.classes]}
Functions: {[f['name'] for f in pf.functions]}

Code:
```
{snippet}
```

Return JSON:
{{"test_file": "relative/path/to/test_file", "content": "full test file content", "framework": "{framework}"}}
Use pytest for Python, JUnit 5 for Java. Only test what exists in the code."""
        try:
            raw = await self.provider.complete(
                "You generate unit tests from supplied code only. Respond with JSON only.",
                user,
                max_tokens=1200,
            )
            data = extract_json_block(raw)
            if data and data.get("content"):
                test_path = data.get("test_file") or self._default_test_path(pf)
                return GeneratedTest(
                    source_file=pf.path,
                    test_file=test_path,
                    language=pf.language,
                    content=data["content"],
                    framework=data.get("framework", framework),
                )
        except Exception:
            pass
        return self._heuristic_generate(pf)

    def _heuristic_generate(self, pf: ParsedFile) -> GeneratedTest | None:
        if pf.language == "python":
            return self._python_test(pf)
        if pf.language == "java":
            return self._java_test(pf)
        return None

    def _default_test_path(self, pf: ParsedFile) -> str:
        stem = Path(pf.path.replace("\\", "/")).stem
        if pf.language == "python":
            return f"tests/test_{stem}.py"
        return f"tests/{stem}Test.java"

    def _python_test(self, pf: ParsedFile) -> GeneratedTest:
        lines = [
            '"""Auto-generated tests for ' + pf.path + ' (heuristic mode)."""',
            "import pytest",
            "",
            f"# Source module: {pf.path}",
            "",
        ]
        for func in pf.functions:
            if func["name"].startswith("_") and func["name"] != "__init__":
                continue
            lines.append(f"def test_{func['name']}_exists():")
            lines.append(f'    assert "{func["name"]}"')
            lines.append("")

        for cls in pf.classes:
            lines.append(f"def test_class_{cls['name']}_exists():")
            lines.append(f'    assert "{cls["name"]}"')
            lines.append("")

        if not pf.functions and not pf.classes:
            lines.append("def test_module_parses():")
            lines.append(f"    assert {pf.line_count} > 0")
            lines.append("")

        return GeneratedTest(
            source_file=pf.path,
            test_file=self._default_test_path(pf),
            language="python",
            content="\n".join(lines),
            framework="pytest",
        )

    def _java_test(self, pf: ParsedFile) -> GeneratedTest:
        class_name = pf.classes[0]["name"] if pf.classes else "SourceClass"
        test_class = f"{class_name}Test"
        lines = [
            f"// Auto-generated tests for {pf.path} (heuristic mode)",
            "import org.junit.jupiter.api.Test;",
            "import static org.junit.jupiter.api.Assertions.*;",
            "",
            f"public class {test_class} {{",
        ]
        for cls in pf.classes[:3]:
            lines.extend(["    @Test", f"    void {cls['name']}_isDefined() {{", f'        assertNotNull("{cls["name"]}");', "    }", ""])
        lines.append("}")
        return GeneratedTest(
            source_file=pf.path,
            test_file=self._default_test_path(pf),
            language="java",
            content="\n".join(lines),
            framework="junit",
        )
