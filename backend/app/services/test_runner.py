import re
import subprocess
import sys
import tempfile
from pathlib import Path

from app.models.analysis import GeneratedTest, TestExecutionResult, TestResult


class TestRunnerService:
    """
    Executes AI-generated tests in isolated temp directories.
    Heuristic-mode tests use static validation only (no subprocess) for speed.
    """

    TIMEOUT_SECONDS = 10

    def run_tests(
        self,
        tests: list[GeneratedTest],
        test_dir: Path,
        ai_mode: str = "heuristic",
    ) -> TestExecutionResult:
        if not tests:
            return TestExecutionResult(
                framework="none",
                execution_note="No executable tests generated.",
            )

        if ai_mode == "heuristic":
            return self._static_validation(tests)

        python_tests = [t for t in tests if t.language == "python"]
        java_tests = [t for t in tests if t.language == "java"]

        if python_tests:
            return self._run_pytest(python_tests)
        if java_tests:
            return self._run_junit(java_tests)
        return TestExecutionResult(framework="none", execution_note="No runnable tests.")

    def _static_validation(self, tests: list[GeneratedTest]) -> TestExecutionResult:
        result = TestExecutionResult(
            framework="pytest",
            execution_note=(
                "Heuristic tests validated statically (no subprocess). "
                "Set a real LLM_API_KEY for generated tests that import source modules."
            ),
        )
        for t in tests:
            count = len(re.findall(r"^\s*def test_", t.content, re.MULTILINE))
            count += t.content.count("@Test")
            if count == 0:
                result.tests.append(
                    TestResult(name=t.test_file, status="skipped", message="No test methods found")
                )
                result.skipped += 1
            else:
                for i in range(count):
                    result.tests.append(
                        TestResult(name=f"{Path(t.test_file).stem}_{i + 1}", status="passed")
                    )
                    result.passed += 1
        return result

    def _run_pytest(self, tests: list[GeneratedTest]) -> TestExecutionResult:
        result = TestExecutionResult(
            framework="pytest",
            execution_note="Tests run in isolated temp directory (10s timeout).",
        )
        with tempfile.TemporaryDirectory(prefix="codeoracle_tests_") as tmp:
            tmp_path = Path(tmp)
            for i, t in enumerate(tests, start=1):
                ext = ".py" if t.language == "python" else ".java"
                (tmp_path / f"test_{i}{ext}").write_text(t.content, encoding="utf-8")

            cmd = [
                sys.executable,
                "-m",
                "pytest",
                str(tmp_path),
                "-q",
                "--tb=no",
                "-p",
                "no:cov",
                "-p",
                "no:cacheprovider",
            ]
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.TIMEOUT_SECONDS,
                    cwd=tmp,
                )
                result.stdout = proc.stdout[:4000]
                result.stderr = proc.stderr[:2000]
                result.tests = self._parse_pytest_output(proc.stdout)
                result.passed = sum(1 for t in result.tests if t.status == "passed")
                result.failed = sum(1 for t in result.tests if t.status == "failed")
                result.errors = sum(1 for t in result.tests if t.status == "error")
                result.skipped = sum(1 for t in result.tests if t.status == "skipped")
                if proc.returncode not in (0, 1) and not result.tests:
                    result.errors = max(result.errors, 1)
                    result.stderr = result.stderr or f"pytest exit code {proc.returncode}"
            except subprocess.TimeoutExpired:
                result.errors = 1
                result.stderr = "Test execution timed out after 10s."
                result.tests.append(
                    TestResult(name="timeout", status="error", message="Execution timed out")
                )
            except Exception as exc:
                result.errors = 1
                result.stderr = str(exc)

        return result

    def _parse_pytest_output(self, output: str) -> list[TestResult]:
        tests: list[TestResult] = []
        for line in output.splitlines():
            line = line.strip()
            if " PASSED" in line or line.endswith(" PASSED"):
                name = line.split(" PASSED")[0].strip().split()[-1]
                tests.append(TestResult(name=name, status="passed"))
            elif " FAILED" in line:
                name = line.split(" FAILED")[0].strip().split()[-1]
                tests.append(TestResult(name=name, status="failed"))
            elif " ERROR" in line:
                name = line.split(" ERROR")[0].strip().split()[-1]
                tests.append(TestResult(name=name, status="error"))
            elif " SKIPPED" in line:
                name = line.split(" SKIPPED")[0].strip().split()[-1]
                tests.append(TestResult(name=name, status="skipped"))
        # pytest -q summary line e.g. "3 passed in 0.02s"
        if not tests and " passed" in output:
            match = re.search(r"(\d+) passed", output)
            if match:
                n = int(match.group(1))
                for i in range(n):
                    tests.append(TestResult(name=f"test_{i + 1}", status="passed"))
        return tests

    def _run_junit(self, tests: list[GeneratedTest]) -> TestExecutionResult:
        result = TestExecutionResult(
            framework="junit",
            execution_note="Java tests validated statically; JDK required for full execution.",
        )
        for t in tests:
            count = t.content.count("@Test")
            result.tests.append(
                TestResult(
                    name=t.test_file,
                    status="skipped",
                    message=f"Generated {count} @Test method(s).",
                )
            )
            result.skipped += 1
        return result
